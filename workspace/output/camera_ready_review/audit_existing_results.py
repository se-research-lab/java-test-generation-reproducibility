"""Read-only, post-review reanalysis of the frozen FISAT 2026 results.

No generation or measurement is rerun. Output statistics use the rounded
percentages retained in metrics_wide.csv. Bootstrap resamples whole repositories
and retains all selected class pairs; this is not a population sampling correction.
"""
from pathlib import Path
import hashlib
import json
import platform
import numpy as np
import pandas as pd
import scipy
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / 'scripts_v2/results/runs/full300_merged_20260724_paper'
OUT = Path(__file__).resolve().parent
B = 20000
SEED = 20261012
w = pd.read_csv(RUN / 'metrics_wide.csv')
l = pd.read_csv(RUN / 'metrics_long.csv')
assert len(w) == 300 and w.class_key.nunique() == 300
assert len(l) == 600 and not l.duplicated(['class_key', 'arm']).any()
assert w.groupby('repo_id').size().eq(10).all()
assert w.repo_id.nunique() == 30
for a in ['gpt', 'evosuite']:
    for metric in ['mutation', 'branch', 'line', 'method']:
        expected = w[f'{a}_{metric}_coverage'].where(w[f'{a}_compilation'].eq(1), 0).fillna(0)
        assert np.allclose(w[f'{a}_strict_{metric}_coverage'], expected)

def ci(v):
    return [float(x) for x in np.quantile(v, [.025, .975])]

def cluster_boot(df, cols):
    """Ratio-of-sums preserves class-weighted estimand in unequal subsets."""
    frame = df.groupby('repo_id')[cols].agg(['sum', 'count'])
    rng = np.random.default_rng(SEED)
    ix = rng.integers(0, len(frame), (B, len(frame)))
    return {c: ci(frame[(c, 'sum')].to_numpy()[ix].sum(axis=1) /
                  frame[(c, 'count')].to_numpy()[ix].sum(axis=1)) for c in cols}

def paired_report(df, raw=False):
    prefix = '' if raw else 'strict_'
    gc, ec = f'gpt_{prefix}mutation_coverage', f'evosuite_{prefix}mutation_coverage'
    z = df.dropna(subset=[gc, ec]).copy()
    g, e = z[gc].to_numpy(), z[ec].to_numpy()
    d = np.round(g-e, 8)
    z['mutation_diff'] = d
    z['build_diff'] = 100 * (z.gpt_compilation-z.evosuite_compilation)
    win, loss, tie = int((d>0).sum()), int((d<0).sum()), int((d==0).sum())
    b = int(((z.gpt_compilation==1)&(z.evosuite_compilation==0)).sum())
    c = int(((z.gpt_compilation==0)&(z.evosuite_compilation==1)).sum())
    nz = d[d != 0]
    ranks = stats.rankdata(abs(nz))
    rbc = float((ranks[nz>0].sum()-ranks[nz<0].sum())/ranks.sum()) if len(nz) else None
    idx = np.random.default_rng(SEED).integers(0, len(d), (B, len(d)))
    pair_ci = ci(d[idx].mean(axis=1))
    report = dict(n=len(z), repositories=int(z.repo_id.nunique()),
        gpt_build=int(z.gpt_compilation.sum()), evo_build=int(z.evosuite_compilation.sum()),
        gpt_mean=float(g.mean()), evo_mean=float(e.mean()),
        gpt_median=float(np.median(g)), evo_median=float(np.median(e)),
        mean_diff=float(d.mean()), median_diff=float(np.median(d)),
        gpt_higher=win, evo_higher=loss, ties=tie,
        paired_superiority=(win+.5*tie)/len(d),
        independent_A12=float(stats.mannwhitneyu(g,e,method='asymptotic').statistic/(len(g)*len(e))),
        paired_rank_biserial=rbc, iid_pair_mean_diff_ci=pair_ci,
        repository_cluster_mean_ci=cluster_boot(z,['mutation_diff','build_diff']),
        sign_test_p=float(stats.binomtest(win,win+loss,.5).pvalue) if win+loss else None,
        wilcoxon_unshifted_two_sided_p=float(stats.wilcoxon(d,method='approx').pvalue) if len(nz) else None,
        both_build=int(((z.gpt_compilation==1)&(z.evosuite_compilation==1)).sum()),
        neither_build=int(((z.gpt_compilation==0)&(z.evosuite_compilation==0)).sum()),
        gpt_only_build=b, evo_only_build=c,
        mcnemar_exact_two_sided_p=float(stats.binomtest(min(b,c),b+c,.5).pvalue) if b+c else None)
    return report

both = w[(w.gpt_compilation==1)&(w.evosuite_compilation==1)].copy()
maven = w[w.build_tool.str.lower().eq('maven')].copy()
ties = w[np.isclose(w.strict_mutation_diff_gpt_minus_evosuite, 0)].copy()
tie_groups = ties.groupby(['gpt_compilation','evosuite_compilation']).size()
fail_stage = pd.crosstab(l.fail_stage, l.arm).to_dict(orient='index')
fail_owner = pd.crosstab(l.failure_owner, l.arm).to_dict(orient='index')
repo = w.assign(mutation_diff=w.strict_mutation_diff_gpt_minus_evosuite,
                build_diff=100*(w.gpt_compilation-w.evosuite_compilation)).groupby('repo_id').agg(
    classes=('class_key','size'),gpt_build=('gpt_compilation','sum'),evo_build=('evosuite_compilation','sum'),
    gpt_strict_mutation=('gpt_strict_mutation_coverage','mean'),
    evo_strict_mutation=('evosuite_strict_mutation_coverage','mean'),
    mutation_diff=('mutation_diff','mean'),build_diff=('build_diff','mean'))
leave_one = []
for rid in repo.index:
    sub=w[w.repo_id != rid]
    leave_one.append({'omitted_repo':str(rid),'mutation_mean_diff':float(sub.strict_mutation_diff_gpt_minus_evosuite.mean()),
                     'build_diff':float(100*(sub.gpt_compilation-sub.evosuite_compilation).mean())})
g = w[w.gpt_compilation==1].copy()
g['gpt_mutation']=g.gpt_mutation_coverage
g['gpt_branch']=g.gpt_branch_coverage
ref = dict(gpt_compiled_mutation_mean=float(g.gpt_mutation.mean()),
           gpt_compiled_mutation_median=float(g.gpt_mutation.median()),
           gpt_compiled_mutation_repositories=int(g.repo_id.nunique()),
           cluster_ci=cluster_boot(g,['gpt_mutation','gpt_branch']),
           reference_is_reported_mean=True)
shift = []
d=w.strict_mutation_diff_gpt_minus_evosuite.to_numpy()
for margin in [0,1,2,5,10]:
    r=stats.wilcoxon(np.round(d+margin,8),alternative='greater',method='approx')
    shift.append({'margin_pp':margin,'statistic':float(r.statistic),'p':float(r.pvalue)})
out = dict(provenance={'run':str(RUN),'date':'2026-10-12','status':'post-review exploratory reanalysis; original configuration only',
    'bootstrap_resamples':B,'bootstrap_seed':SEED,'python':platform.python_version(),'scipy':scipy.__version__,
    'numpy':np.__version__,'pandas':pd.__version__,
    'sha256':{n:hashlib.sha256((RUN/n).read_bytes()).hexdigest() for n in ['metrics_wide.csv','metrics_long.csv']}},
    all300=paired_report(w),common49=paired_report(both,True),maven260=paired_report(maven),
    at_least_one_build170=paired_report(w[(w.gpt_compilation==1)|(w.evosuite_compilation==1)]),
    gradle40=paired_report(w[w.build_tool.str.lower().eq('gradle')]),
    ties_by_build_status={str(k):int(v) for k,v in tie_groups.items()},
    failure_stages=fail_stage,failure_owners=fail_owner,
    repository_means_direction={'gpt_higher':int((repo.mutation_diff>0).sum()),'evo_higher':int((repo.mutation_diff<0).sum()),
       'tied':int((repo.mutation_diff==0).sum())},
    leave_one_repo_out=leave_one,reference_comparison=ref,margin_sensitivity=shift,
    split={k:paired_report(v) for k,v in w.groupby('split_name')})
(OUT/'reanalysis.json').write_text(json.dumps(out,indent=2,ensure_ascii=False),encoding='utf-8')
(OUT/'repository_aggregates.json').write_text(repo.reset_index().to_json(orient='records',indent=2),encoding='utf-8')
(OUT/'common_success_49.json').write_text(both[['class_key','repo_id','gpt_mutation_coverage','evosuite_mutation_coverage']].to_json(orient='records',indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in out.items() if k not in ['leave_one_repo_out','split']},indent=2))
