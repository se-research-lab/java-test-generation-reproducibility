"""Offline G0/E0/E1 evidence synthesis. No experiment commands; no recoding of inputs."""
import csv, json, re, sys, hashlib
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import numpy as np

R = Path(__file__).resolve().parents[1]
B = R.parent / 'paired49_20261023'
ROOT = R.parents[1]
H = ROOT / 'scripts_v2/results/runs/full300_merged_20260724_paper'
O = R / 'analysis_camera_ready_rq45_v1'
sys.path.insert(0, str(B)); import audit

def read(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def csvrows(p):
    with Path(p).open(encoding='utf-8-sig', newline='') as f: return list(csv.DictReader(f))
def dump(name, value):
    with (O/name).open('x', encoding='utf-8') as f: json.dump(value,f,ensure_ascii=False,indent=2)
def num(v): return float(v) if v not in (None,'') else 0.0

assert not O.exists(); O.mkdir()
audit.verify()
inputs = {}
def pin(p):
    p=Path(p); inputs[str(p)]=audit.sha(p); return p
historical=csvrows(pin(H/'metrics_long.csv'))
jobs=read(pin(R/'manifest300.json'))
selection={r['index']:r for r in read(pin(R/'policy_attempt_history_v2/selection_current.json'))}
inventory={int(r['index']):r for r in csvrows(pin(R/'audit/generated_test_build_failures_v1/class_inventory300.csv'))}
gradle={r['index']:r for r in read(pin(R/'audit/gradle_full40_completion_check_v1/verification.json'))['rows']}
completion=read(pin(R/'runtime/gradle_full40_v1/complete.json'))
assert completion['attempted_or_preflight_checked']==40
lookup={(r['class_key'],r['arm']):r for r in historical}; assert len(lookup)==600
rows=[]
for job in jobs:
    i=job['sample_index_1based']; key=job['class_key']; g=lookup[key,'gpt']; e=lookup[key,'evosuite']
    row={'index':i,'class_key':key,'repo_id':job['repo_id'],'build_tool':job['build_tool'],
        'G0_build':int(g['compilation']),'G0_strict':num(g['strict_mutation_coverage']),
        'E0_build':int(e['compilation']),'E0_strict':num(e['strict_mutation_coverage']),
        'G0_recorded_stage':g['fail_stage'],'E0_recorded_stage':e['fail_stage'],
        'fixed_historical49':bool(job['reused_result'])}
    if job['build_tool']=='gradle':
        gr=gradle[i]; row['E1_category']=gr['category']; folder=R/'jobs'/f'{i:03d}_gradle_v1'
        p=folder/'result.json'; row['generation_complete']=gr['native_complete']
        row['E1_lineage']='Gradle40 frozen v1'
    else:
        inv=inventory[i]
        row['E1_category']=inv['failure_kind'] or inv['category']
        row['generation_complete']=inv['native_suite_complete']=='True'
        row['E1_lineage']=selection[i]['selected_phase']
        p=ROOT/selection[i]['selected_result_path'] if selection[i]['selected_result_path'] else None
    if p and p.exists():
        if job['build_tool']=='maven': assert audit.sha(p)==selection[i]['selected_result_sha256']
        d=read(pin(p)); row.update(E1_build=int(d['legacy_process_build']),E1_strict=float(d['legacy_strict_mutation_percent']),
            E1_suite_evidence=d['strict_suite_evidence'],E1_measurement_evidence=d['strict_measurement_evidence'],E1_result_path=str(p))
    else: row.update(E1_build=None,E1_strict=None,E1_suite_evidence=None,E1_measurement_evidence=None,E1_result_path=None)
    row['E1_acceptance_caveat']=('post-outcome diagnostic selection' if i==3 else 'harness failure recorded as zero; attribution unresolved' if row['E1_category']=='NO_GENERATION_HARNESS_TASK_MISSING' else 'unscored; not zero-filled' if row['E1_build'] is None else 'operational pipeline result; not a causal oracle-quality measure')
    rows.append(row)
assert len(rows)==300 and len({x['class_key'] for x in rows})==300
known=[r for r in rows if r['E1_build'] is not None]; unknown=[r for r in rows if r['E1_build'] is None]
assert len(known)==270 and len(unknown)==30 and sum(r['E1_build'] for r in known)==204
assert sum(r['G0_build'] for r in rows)==61

def stats(group, arm='E1', bootstrap=True):
    g=np.array([r['G0_strict'] for r in group]); e=np.array([r[arm+'_strict'] for r in group]); d=g-e
    gb=np.array([r['G0_build'] for r in group]); eb=np.array([r[arm+'_build'] for r in group])
    table={'both':int(((gb==1)&(eb==1)).sum()),'G_only':int(((gb==1)&(eb==0)).sum()),'E_only':int(((gb==0)&(eb==1)).sum()),'neither':int(((gb==0)&(eb==0)).sum())}
    result={'n':len(group),'G_mean':float(g.mean()),'E_mean':float(e.mean()),'G_median':float(np.median(g)),
        'E_median':float(np.median(e)),'mean_difference_pp':float(d.mean()),'median_difference_pp':float(np.median(d)),
        'G_higher':int((d>1e-9).sum()),'E_higher':int((d < -1e-9).sum()),'ties':int((abs(d)<=1e-9).sum()),
        'G_build':int(gb.sum()),'E_build':int(eb.sum()),'paired_build_table':table,
        'build_difference_pp':float(100*(gb-eb).mean()),
        'A12_cross_arm':float(((g[:,None]>e[None,:]).sum()+.5*(g[:,None]==e[None,:]).sum())/(len(g)**2))}
    if bootstrap:
        repos=sorted({r['repo_id'] for r in group}); sums=np.array([[sum((r['G0_strict']-r[arm+'_strict']) for r in group if r['repo_id']==repo),sum(100*(r['G0_build']-r[arm+'_build']) for r in group if r['repo_id']==repo),sum(r['repo_id']==repo for r in group)] for repo in repos])
        draws=np.random.default_rng(20261023).integers(0,len(repos),size=(20000,len(repos))); res=sums[draws].sum(axis=1)
        result['repository_bootstrap']={'replicates':20000,'seed':20261023,'repository_order':repos,'mean_difference_CI95':np.quantile(res[:,0]/res[:,2],[.025,.975]).tolist(),'build_difference_CI95':np.quantile(res[:,1]/res[:,2],[.025,.975]).tolist(),'interpretation':'exploratory class-weighted mean, whole-repository resampling; not NI or run-to-run variance'}
    return result

def bounds(excluded):
    fixed=[r for r in rows if r['E1_build'] is not None and r['index'] not in excluded]
    nmissing=300-len(fixed); total=sum(r['E1_strict'] for r in fixed); build=sum(r['E1_build'] for r in fixed); gtotal=sum(r['G0_strict'] for r in rows)
    return {'fixed_rows':len(fixed),'unresolved_rows':nmissing,'E1_build_count_bounds':[build,build+nmissing],
        'E1_build_rate_bounds_percent':[100*build/300,100*(build+nmissing)/300],
        'G_minus_E_build_rate_bounds_pp':[100*(61-build-nmissing)/300,100*(61-build)/300],
        'G_minus_E_strict_mean_bounds_pp':[(gtotal-total-100*nmissing)/300,(gtotal-total)/300],
        'type':'deterministic bounds, NOT confidence intervals or NI tests; keep denominator 300'}
fixed49=[r for r in rows if r['fixed_historical49']]
cohorts={'E0_full300':stats(rows,'E0'),'E1_observed270':stats(known),
         'E1_observed_Maven240':stats([r for r in known if r['build_tool']=='maven']),
         'E1_observed_Gradle30':stats([r for r in known if r['build_tool']=='gradle']),
         'E1_fixed_historical49':stats(fixed49),
         'E1_new_common_success_diagnostic_only':stats([r for r in known if r['G0_build'] and r['E1_build']])}
task_ids={r['index'] for r in rows if r['E1_category']=='NO_GENERATION_HARNESS_TASK_MISSING'}
boundsets={'raw_policy_30_unscored':bounds(set()),'task_integration_40_unresolved':bounds(task_ids),'task_and_posthoc003_41_unresolved':bounds(task_ids|{3})}
cohorts['E1_observed270_initial003_sensitivity']=stats([{**r,'E1_build':0,'E1_strict':0.0} if r['index']==3 else r for r in known])

# Arm-specific log segmentation. Diagnostic flags may overlap and are not causal labels.
flags={
 'compiler_marker':r'COMPILATION ERROR|Compilation failure|compilation errors|testCompile.*failed',
 'generated_test_location':r'[^\n]*RBL4[^\n]*\.java:\[\d+[,\d]*\][^\n]*',
 'unresolved_symbol':r'cannot find symbol',
 'missing_package':r'package [^\n]+ does not exist',
 'type_or_signature':r'incompatible types|cannot be applied to given types|no suitable (?:method|constructor)',
 'access_control':r'has private access|has protected access|cannot be accessed from outside',
 'syntax_or_duplicate':r"already defined|duplicate class|illegal start|reached end of file|';' expected|not a statement",
 'production_path':r'[^\n]*src[\\/]main[\\/]java[^\n]*\.java:\[\d+[,\d]*\][^\n]*',
 'artifact_or_plugin_resolution':r'could not be resolved|Could not resolve|Failed to read artifact descriptor|Could not find artifact|Could not transfer artifact|No cached version',
 'license_header':r'license-maven-plugin[^\n]*check-file-header|file\(s\) with no header',
 'test_execution_failure':r'(?:Failures|Errors):\s*[1-9]\d*|<<< FAILURE|<<< ERROR|AssertionFailedError',
 'forked_vm_failure':r'forked VM terminated|VM crash|System.exit called',
 'PIT_minion_failure':r'Coverage generation minion exited abnormally',
 'E0_copy_path_bug':r"project_df_evosuite.*referenced before assignment",
 'unsupported_bytecode':r'Unsupported class file major version|bad class file|wrong version',
}
historical_evidence=[]
for h in historical:
    i=int(h['original_manifest_index'])+1
    paths=list((H/'class_logs'/h['source_run_id']).glob(f"{int(h['source_run_sample_index']):03d}_*.stdout.log"))
    record={'index':i,'class_key':h['class_key'],'arm':h['arm'],'recorded_stage':h['fail_stage'],'recorded_gate':int(h['compilation']),'flags':{},'excerpts':{}}
    if h['fail_stage']=='maven_reactor_prewarm_failed':
        record['scope']='PREPROCESSING_NO_GENERATION'; historical_evidence.append(record);continue
    assert len(paths)==1,(i,paths)
    p=paths[0]; text=p.read_text(encoding='utf-8',errors='replace')
    markers=list(re.finditer(r'^STARTING (evosuite|gpt-4o-mini-2024-07-18) test typ[^\n]*',text,re.M))
    wanted='evosuite' if h['arm']=='evosuite' else 'gpt-4o-mini-2024-07-18'
    found=[(j,m) for j,m in enumerate(markers) if m.group(1)==wanted]
    record.update(log_path=str(p),log_sha256=inputs.setdefault(str(p),audit.sha(p)))
    if len(found)!=1: record['scope']='AMBIGUOUS_OR_MISSING_ARM_MARKER'; historical_evidence.append(record);continue
    j,m=found[0];end=markers[j+1].start() if j+1<len(markers) else len(text);block=text[m.start():end]
    start_line=text.count('\n',0,m.start())+1
    record.update(scope='ARM_SCOPED',start_line=start_line,end_line=text.count('\n',0,end)+1,segment_sha256=hashlib.sha256(block.encode()).hexdigest())
    for name,pattern in flags.items():
        matches=list(re.finditer(pattern,block,re.I));record['flags'][name]=bool(matches)
        if matches:record['excerpts'][name]=[{'line':start_line+block.count('\n',0,x.start()),'text':block[block.rfind('\n',0,x.start())+1:block.find('\n',x.end()) if block.find('\n',x.end())!=-1 else len(block)][:1000]} for x in matches[:2]]
    historical_evidence.append(record)
hist_summary={}
for arm in ('gpt','evosuite'):
    group=[r for r in historical_evidence if r['arm']==arm];failed=[r for r in group if r['recorded_gate']==0]
    hist_summary[arm]={'stages':dict(Counter(r['recorded_stage'] for r in group)),
       'arm_scoped_logs':sum(r['scope']=='ARM_SCOPED' for r in group),
       'failed_rows_with_markers_overlapping':{f:sum(r['flags'].get(f,False) for r in failed) for f in flags},
       'failed_rows_without_listed_markers':sum(not any(r['flags'].values()) for r in failed),
       'compile_label_with_generated_test_location':sum(r['recorded_stage']=='generated_test_compile_failed' and r['flags'].get('generated_test_location',False) for r in group)}
summary={'created_utc':datetime.now(timezone.utc).isoformat(),'cohorts':cohorts,'bounds':boundsets,
    'E1_category_counts':dict(Counter(r['E1_category'] for r in rows)),
    'E1_native_complete':sum(r['generation_complete'] for r in rows),
    'E1_observed_gate':sum(r['E1_build'] for r in known),'E1_unscored':len(unknown),
    'E1_gate_pass_missing_suite_evidence':[r['index'] for r in known if r['E1_build'] and not r['E1_suite_evidence']],
    'E1_gate_pass_missing_measurement_evidence':[r['index'] for r in known if r['E1_build'] and not r['E1_measurement_evidence']],
    'historical_log_evidence':hist_summary,'no_new_NI_test':True,'G0_changed':False,'no_experiment_calls':True}
assert abs(cohorts['E1_fixed_historical49']['mean_difference_pp']-(-.7216326530612245))<1e-8
dump('class_evidence300.json',rows);dump('historical_arm_scoped_evidence600.json',historical_evidence);dump('analysis.json',summary);dump('input_hashes.json',inputs)
for p,h in inputs.items(): assert audit.sha(p)==h
audit.verify();audit.verify_chain()
audit.log('B1_CAMERA_READY_RQ45_OFFLINE_ANALYSIS',analysis_sha256=audit.sha(O/'analysis.json'),input_manifest_sha256=audit.sha(O/'input_hashes.json'),experiment_calls=0,G0_modified=False)
print(json.dumps(summary,ensure_ascii=False,indent=2))
