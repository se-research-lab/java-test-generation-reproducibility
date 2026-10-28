"""Read-only input audit and post-review statistics; never runs generators/builds."""
from pathlib import Path
import hashlib
import json
import platform
import sys
import numpy as np
import pandas as pd
import scipy
from scipy import stats

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
OLD = ROOT / 'scripts_v2/results/runs/full300_merged_20260724_paper'
V6 = ROOT / 'review_reports/v6_final_20261021/data/attempts_1080.csv'
AVAIL = ROOT / 'review_reports/reuse_audit_v1_20261021T112500/evidence/G0_AVAILABILITY_300.csv'
SEED, DRAWS = 20261023, 20000

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

inputs = [OLD/'metrics_wide.csv', OLD/'metrics_long.csv', V6, AVAIL,
          ROOT/'FISAT2026_Buildability_Mutation_Strength.pdf', ROOT/'Reviewer.txt']
before = {str(p):sha(p) for p in inputs}
w = pd.read_csv(OLD/'metrics_wide.csv')
l = pd.read_csv(OLD/'metrics_long.csv')
a = pd.read_csv(V6)
assert len(w)==300 and w.class_key.nunique()==300
assert len(l)==600 and not l.duplicated(['class_key','arm']).any()
assert w.groupby('repo_id').size().eq(10).all() and w.repo_id.nunique()==30
assert len(a)==1080 and not a.duplicated(['class_key','arm','replicate']).any()
for arm in ['gpt','evosuite']:
    expected = w[f'{arm}_mutation_coverage'].where(w[f'{arm}_compilation'].eq(1),0).fillna(0)
    assert np.allclose(expected,w[f'{arm}_strict_mutation_coverage'])

def summary(z, raw=False):
    stem = '' if raw else 'strict_'
    g,e = (z[f'{arm}_{stem}mutation_coverage'].to_numpy() for arm in ['gpt','evosuite'])
    assert np.isfinite(g).all() and np.isfinite(e).all()
    d = np.round(g-e,8)
    wins,losses,ties = int((d>0).sum()),int((d<0).sum()),int((d==0).sum())
    frame=z[['repo_id']].copy()
    frame['d']=d
    frame['build_d']=100*(z.gpt_compilation-z.evosuite_compilation)
    agg=frame.groupby('repo_id')[['d','build_d']].agg(['sum','count'])
    ix=np.random.default_rng(SEED).integers(0,len(agg),(DRAWS,len(agg)))
    ci={c:np.quantile(agg[(c,'sum')].to_numpy()[ix].sum(1)/agg[(c,'count')].to_numpy()[ix].sum(1),[.025,.975]).tolist() for c in ['d','build_d']}
    b=int(((z.gpt_compilation==1)&(z.evosuite_compilation==0)).sum())
    c=int(((z.gpt_compilation==0)&(z.evosuite_compilation==1)).sum())
    return dict(n=len(z),repositories=int(z.repo_id.nunique()),gpt_build=int(z.gpt_compilation.sum()),evo_build=int(z.evosuite_compilation.sum()),
        gpt_mean=float(g.mean()),evo_mean=float(e.mean()),gpt_median=float(np.median(g)),evo_median=float(np.median(e)),
        mean_diff=float(d.mean()),median_diff=float(np.median(d)),wins=wins,losses=losses,ties=ties,
        paired_directional_probability=(wins+.5*ties)/len(d),
        marginal_A12=float(stats.mannwhitneyu(g,e,method='asymptotic').statistic/(len(g)*len(e))),
        cluster_percentile_95ci=ci,
        wilcoxon_unshifted_two_sided_p=float(stats.wilcoxon(d,method='approx').pvalue) if np.any(d) else None,
        both_build=int(((z.gpt_compilation==1)&(z.evosuite_compilation==1)).sum()),
        neither_build=int(((z.gpt_compilation==0)&(z.evosuite_compilation==0)).sum()),
        gpt_only=b,evo_only=c,mcnemar_exact_secondary_p=float(stats.binomtest(min(b,c),b+c,.5).pvalue) if b+c else None)

s49=w[(w.gpt_compilation==1)&(w.evosuite_compilation==1)].copy()
assert len(s49)==49 and s49.build_tool.str.lower().eq('maven').all()
manifest=s49[['class_key','repo_id','focal_class','focal_path','module','build_tool','gpt_mutation_coverage','evosuite_mutation_coverage']].copy()
av=pd.read_csv(AVAIL)
manifest=manifest.merge(av[['class_key','commit_sha','G0_path','G0_sha256','focal_source_sha256']],on='class_key',validate='one_to_one')
manifest['G0_file_exists']=manifest.G0_path.map(lambda p:Path(p).is_file())
manifest['G0_hash_matches']=manifest.apply(lambda r:sha(r.G0_path)==r.G0_sha256 if r.G0_file_exists else False,axis=1)
assert manifest.G0_hash_matches.all()
primary=a[a.replicate.eq(0)]
assert len(primary)==600 and set(primary.class_key)==set(w.class_key)
e49=primary[primary.arm.eq('E1') & primary.class_key.isin(s49.class_key)].copy()
assert len(e49)==49
echecks=[]
for row in e49.itertuples():
    attempt=json.loads(Path(row.attempt_path).read_text(encoding='utf-8'))
    cmd=attempt.get('generation',{}).get('complete_process',{}).get('argv',[])
    files=attempt.get('generation',{}).get('raw_java_files',[])
    hashes=all(Path(f['path']).is_file() and sha(f['path'])==f['sha256'] for f in files)
    assert attempt['class_key']==row.class_key
    echecks.append(dict(class_key=row.class_key,E1_attempt_path=row.attempt_path,
        E1_finished=attempt.get('state')=='finished',E1_assertions_true='-Dassertions=true' in cmd,
        E1_mutation_assertion_strategy='-Dassertion_strategy=MUTATION' in cmd,
        E1_raw_java_count=len(files),E1_existing_java_hashes_match=hashes,
        E1_P_success=int(row.P_success),E1_P_mutation_valid=int(row.P_mutation_valid),
        E1_C_success=int(row.C_process_success),E1_C_mutation_valid=int(row.C_mutation_valid),
        E1_stage=row.stage,E1_total_mutants=row.total_mutants))
manifest=manifest.merge(pd.DataFrame(echecks),on='class_key',validate='one_to_one')
manifest.to_csv(OUT/'historical_common49_manifest.csv',index=False,encoding='utf-8-sig')
assert manifest.E1_finished.all() and manifest.E1_assertions_true.all() and manifest.E1_existing_java_hashes_match.all()

v6={}
for label,sub in [('all300',primary),('fixed_historical49',primary[primary.class_key.isin(s49.class_key)])]:
    v6[label]={}
    for view,suc,val,score in [('P','P_success','P_mutation_valid','P_score_pct'),('C','C_process_success','C_mutation_valid','C_score_pct')]:
        g=sub[sub.arm.ne('E1')].set_index('class_key')
        e=sub[sub.arm.eq('E1')].set_index('class_key').reindex(g.index)
        assert g.index.is_unique and len(g)==len(e) and not e.repo_id.isna().any()
        gs=g[score].where(g[val].eq(1),0).fillna(0)
        es=e[score].where(e[val].eq(1),0).fillna(0)
        v6[label][view]=dict(classes=len(g),gpt_success=int(g[suc].sum()),evo_success=int(e[suc].sum()),
            gpt_valid=int(g[val].sum()),evo_valid=int(e[val].sum()),both_success=int((g[suc].eq(1)&e[suc].eq(1)).sum()),
            both_valid=int((g[val].eq(1)&e[val].eq(1)).sum()),mean_diff=float((gs-es).mean()))
ties=w[np.isclose(w.strict_mutation_diff_gpt_minus_evosuite,0)]
stages=pd.crosstab(l.fail_stage.fillna('(missing)'),l.arm).reset_index()
stages.to_csv(OUT/'historical_failure_stages.csv',index=False,encoding='utf-8-sig')
repeated_keys=a[a.replicate.gt(0)].class_key.unique()
repeated=a[a.class_key.isin(repeated_keys)].copy()
assert len(repeated_keys)==60 and len(repeated)==600
assert repeated.groupby(['class_key','arm']).size().eq(5).all()
repeat_summary={}
for view,val,score in [('P','P_mutation_valid','P_score_pct'),('C','C_mutation_valid','C_score_pct')]:
    repeated['strict']=repeated[score].where(repeated[val].eq(1),0).fillna(0)
    byclass=repeated.groupby(['class_key','arm']).strict.agg(['mean','std'])
    repeat_summary[view]={str(arm):dict(mean_class_score=float(rows['mean'].mean()),mean_within_class_sd=float(rows['std'].mean()),median_within_class_sd=float(rows['std'].median())) for arm,rows in byclass.groupby(level='arm')}
diag=json.loads((ROOT/'output/camera_ready_review/diagnostics.json').read_text(encoding='utf-8'))
verified_signatures={}
for row in diag['gradle_details']:
    content=Path(row['log']).read_text(encoding='utf-8',errors='replace')
    assert all(signature in content for _,signature in row['signatures'])
    category=row['classification']
    verified_signatures[category]=verified_signatures.get(category,0)+1
out=dict(status='post-review analysis only; no generation or measurement rerun',
    settings=dict(seed=SEED,draws=DRAWS,bootstrap='whole-repository percentile, class-weighted ratio of sums',python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__,pandas=pd.__version__),
    hashes=before,all300=summary(w),historical_common49=summary(s49,True),maven260=summary(w[w.build_tool.str.lower().eq('maven')]),
    remaining240=summary(w[w.split_name.eq('remaining240')]),
    ties_by_build={str(k):int(v) for k,v in ties.groupby(['gpt_compilation','evosuite_compilation']).size().items()},
    V6_export_recomputed=v6,
    V6_repeats_recomputed=repeat_summary, historical_gradle_log_signatures_verified=verified_signatures,
    common49_artifact_audit=dict(g0_existing_hash_match=int(manifest.G0_hash_matches.sum()),e1_finished=int(manifest.E1_finished.sum()),e1_assertions_true=int(manifest.E1_assertions_true.sum()),e1_with_raw_java=int((manifest.E1_raw_java_count>0).sum()),e1_hashes_match=int(manifest.E1_existing_java_hashes_match.sum()),e1_stages=manifest.E1_stage.value_counts().to_dict()),
    known_limits=['Historical metrics contain rounded percentages, not verified raw mutant counts.', 'V6 whole-study summaries recomputed from exported attempt CSV; only the fixed49 E1 attempt files and generated Java hashes were directly audited here.', 'No G0/H1 remeasurement was executed; no assertion-only causal estimate.', 'Absent raw E1 Java is retained as failure, not called successful artifact verification.'])
assert before=={str(p):sha(p) for p in inputs}
out['source_inputs_unchanged']=True
(OUT/'analysis.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in out.items() if k not in ['hashes','settings','known_limits']},ensure_ascii=False,indent=2))
