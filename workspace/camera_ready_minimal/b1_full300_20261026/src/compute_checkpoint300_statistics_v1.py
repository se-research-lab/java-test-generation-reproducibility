"""Offline statistics from300 audited records; no builds, generation or API calls."""
import csv,json,re,sys
from pathlib import Path
from collections import Counter
from datetime import datetime,timezone
import numpy as np
from maven_adapter_v1 import R,sha,dump

A=R/'completion_amendment_v1';IN=A/'analysis300_checkpoint_v2';OUT=A/'final300_offline_v1'
B=R.parent/'paired49_20261023';ROOT=R.parents[1]
sys.path.insert(0,str(B));import audit

def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def boot(records):
 if not records:return None
 repos=sorted({str(x[0]) for x in records});n=np.array([sum(str(x[0])==r for x in records) for r in repos],dtype=float)
 sums=np.array([sum(float(x[1]) for x in records if str(x[0])==r) for r in repos])
 draw=np.random.default_rng(20261023).integers(0,len(repos),(20000,len(repos)))
 samples=sums[draw].sum(axis=1)/n[draw].sum(axis=1)
 values=[float(x[1]) for x in records]
 return {'n':len(records),'repositories':len(repos),'mean':float(sums.sum()/n.sum()),'median':float(np.median(values)),
         'CI95_repository_percentile':np.percentile(samples,[2.5,97.5]).tolist(),
         'resamples':20000,'seed':20261023,'unit':'whole repository; class-weighted mean'}
def paired(rows,left,right):
 pairs=[(r,float(left(r)),float(right(r))) for r in rows]
 if not pairs:return None
 x=np.array([a for _,a,_ in pairs]);y=np.array([b for _,_,b in pairs]);delta=x-y
 return {'n':len(rows),'repositories':len({r['repo_id'] for r in rows}),
         'left':boot([(r['repo_id'],a) for r,a,_ in pairs]),'right':boot([(r['repo_id'],b) for r,_,b in pairs]),
         'left_minus_right':boot([(r['repo_id'],a-b) for r,a,b in pairs]),
         'left_higher':int((delta>0).sum()),'right_higher':int((delta<0).sum()),'ties':int((delta==0).sum()),
         'paired_probability_left_higher_half_ties':float(((delta>0).sum()+.5*(delta==0).sum())/len(rows)),
         'A12_marginal_all_cross_pairs':float(((x[:,None]>y[None,:]).sum()+.5*(x[:,None]==y[None,:]).sum())/(len(x)*len(y)))}
def gate(rows,field):
 known=[r for r in rows if r[field] is not None];unknown=len(rows)-len(known);passes=sum(r[field] for r in known)
 return {'pass':passes,'fail':len(known)-passes,'unknown':unknown,'total_slots':len(rows),
         'available_denominator':len(known),'available_rate_percent':boot([(r['repo_id'],100*r[field]) for r in known]),
         'full_slot_rate_bounds_percent':[100*passes/len(rows),100*(passes+unknown)/len(rows)]}
def bounds(rows,unknown_predicate=lambda r:r['end_to_end_score_percent'] is None):
 unknown=[r for r in rows if unknown_predicate(r)]
 lower=lambda r:0. if unknown_predicate(r) else r['end_to_end_score_percent']
 upper=lambda r:100. if unknown_predicate(r) else r['end_to_end_score_percent']
 low=paired(rows,lambda r:r['G0_strict'],lower);high=paired(rows,lambda r:r['G0_strict'],upper)
 return {'slots':len(rows),'unknown_n':len(unknown),'unknown_indices':[r['index'] for r in unknown],
         'E1_mean_bounds':[low['right']['mean'],high['right']['mean']],
         'G0_minus_E1_mean_bounds':[high['left_minus_right']['mean'],low['left_minus_right']['mean']],
         'bounds_are_not_CI':True,'zero_fill_sensitivity':low,'hundred_fill_sensitivity':high,
         'bootstrap_endpoint_envelope_descriptive_only':[
             high['left_minus_right']['CI95_repository_percentile'][0],low['left_minus_right']['CI95_repository_percentile'][1]],
         'not_NI_or_equivalence_test':True}
def exportcsv(path,rows):
 fields=list(dict.fromkeys(k for r in rows for k in r))
 with path.open('x',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
  for r in rows:w.writerow({k:json.dumps(v,ensure_ascii=False,sort_keys=True) if isinstance(v,(dict,list)) else v for k,v in r.items()})

def main():
 assert not OUT.exists();OUT.mkdir()
 rows=load(IN/'class_results300.json');assert len(rows)==len({r['class_key'] for r in rows})==300
 # Correct only the missing generation-success field in a reused diagnostic record.
 r3=next(r for r in rows if r['index']==3);d3=load(r3['selected_result']['path']);old3=R/'jobs/003/result.json'
 assert d3['source_checkpoint_result_sha256']==sha(old3) and load(old3)['generation_success']
 r3['generation']='COMPLETE_SUITE_REUSED_FROM_ORIGINAL'
 r3['generation_stage_provenance']={'path':str(old3),'sha256':sha(old3),'note':'Selected diagnostic remeasured the archived suite; no generation-success field in diagnostic JSON'}
 # Component statuses remain separate from the process gate.
 for r in rows:
  r['compile_production_evidence']=r['compile_production'];r['compile_test_evidence']=r['compile_test']
  compiler=[]
  for cmd in r['actual_commands']:
   if cmd['returncode'] in (None,0):continue
   for ref in cmd['logs']:
    p=Path(ref['path']);assert sha(p)==ref['sha256'];text=p.read_text(encoding='utf-8',errors='replace')
    if re.search(r'COMPILATION ERROR|Compilation failure|Compilation failed; see the compiler error output',text,re.I):
     which='production' if cmd['kind']=='compile_or_dependency_audit' and any(x=='compile' or x.endswith(':classes') or x=='classes' for x in cmd['argv']) else 'test' if cmd['kind'] in {'mutation_measurement','test_execution'} else 'undetermined'
     compiler.append({'path':str(p),'sha256':ref['sha256'],'stage':which})
  if any(x['stage']=='production' for x in compiler):r['compile_production_evidence']='FAIL_EXPLICIT_COMPILER_LOG'
  if any(x['stage']=='test' for x in compiler):r['compile_test_evidence']='FAIL_EXPLICIT_COMPILER_LOG'
  r['compiler_failure_evidence']=compiler
  r['PIT_score_observed_zero']=r['observed_mutation_percent']==0 if r['observed_mutation_percent'] is not None else False
  r['policy_zero_without_observed_score']=r['score_basis']=='CONVENTIONAL_PIPELINE_FAILURE_ZERO_NOT_OBSERVED'
  r['nonpassing_suite_with_valid_PIT']=r['PIT']=='VALID_FOCAL_REPORT' and not r['suite_evidence_complete']
  assert r['observed_mutation_percent'] is None or 0<=r['observed_mutation_percent']<=100
  assert r['end_to_end_score_percent'] is None or 0<=r['end_to_end_score_percent']<=100
 known=[r for r in rows if r['end_to_end_score_percent'] is not None]
 observed=[r for r in rows if r['observed_mutation_percent'] is not None]
 fixed=[r for r in rows if r['fixed49']];assert len(fixed)==49
 cohorts={'historical_G0_E0_all300':paired(rows,lambda r:r['G0_strict'],lambda r:r['E0_strict']),
          'historical_G0_E0_fixed49':paired(fixed,lambda r:r['G0_strict'],lambda r:r['E0_strict']),
          'G0_E1_fixed49_same_membership':paired(fixed,lambda r:r['G0_strict'],lambda r:r['end_to_end_score_percent']),
          'G0_E1_evidence_aware_end_to_end_available':paired(known,lambda r:r['G0_strict'],lambda r:r['end_to_end_score_percent']),
          'E1_observed_PIT_only':boot([(r['repo_id'],r['observed_mutation_percent']) for r in observed]),
          'new_common_process_success_diagnostic_only':paired([r for r in known if r['G0_build']==r['process_gate']==1],lambda r:r['G0_strict'],lambda r:r['end_to_end_score_percent'])}
 gates={name:gate(rows,field) for name,field in [('G0_historical_process','G0_build'),('E0_historical_process','E0_build'),('E1_evidence_aware_process','process_gate'),('E1_raw_recorded_process_sensitivity','legacy_raw_process_gate')]}
 paired_gates=[r for r in rows if r['process_gate'] is not None]
 gates['G0_E1_known_paired_table']={str(a)+str(b):sum(r['G0_build']==a and r['process_gate']==b for r in paired_gates) for a in [0,1] for b in [0,1]}
 gates['G0_E1_known_risk_difference_pp']=boot([(r['repo_id'],100*(r['G0_build']-r['process_gate'])) for r in paired_gates])
 for fill in [0,1]:gates['G0_E1_unknown_gate_fill'+str(fill)]=boot([(r['repo_id'],100*(r['G0_build']-(r['process_gate'] if r['process_gate'] is not None else fill))) for r in rows])
 strata={}
 for build in ['maven','gradle']:
  subset=[r for r in rows if r['build_tool']==build];avail=[r for r in subset if r['end_to_end_score_percent'] is not None]
  strata[build]={'n':len(subset),'historical':paired(subset,lambda r:r['G0_strict'],lambda r:r['E0_strict']),
                 'E1_available':paired(avail,lambda r:r['G0_strict'],lambda r:r['end_to_end_score_percent']),
                 'E1_bounds':bounds(subset),'E1_gate':gate(subset,'process_gate'),
                 'G0_gate':gate(subset,'G0_build'),'E0_gate':gate(subset,'E0_build')}
 initial=load(old3)['legacy_strict_mutation_percent'];initialgate=load(old3)['legacy_process_build']
 sensitivities={'original_class3_result':paired(known,lambda r:r['G0_strict'],lambda r:initial if r['index']==3 else r['end_to_end_score_percent']),
                'original_class3_process':boot([(r['repo_id'],100*(initialgate if r['index']==3 else r['process_gate'])) for r in paired_gates]),
                'exclude_nonpassing_native_suite_diagnostic':paired([r for r in known if not r['nonpassing_suite_with_valid_PIT']],lambda r:r['G0_strict'],lambda r:r['end_to_end_score_percent']),
                'hold_nonpassing_native_suite_unresolved_bounds':bounds(rows,lambda r:r['end_to_end_score_percent'] is None or r['nonpassing_suite_with_valid_PIT']),
                'hold112_269_timeout_as_unknown_instead_of_policy_zero':bounds(rows,lambda r:r['end_to_end_score_percent'] is None or r['index'] in [112,269]),
                'K_plus_TIMED_OUT_diagnostic_on_same_E1_observed_rows':boot([(r['repo_id'],r['E1_K_plus_T_diagnostic_percent']) for r in observed])}
 flags=[{k:r[k] for k in ['index','class_key','PIT','test_execution','test_counts','jacoco_focal_evidence','observed_mutation_percent','score_basis','process_gate','nonpassing_suite_with_valid_PIT']} for r in rows if 'MEASUREMENT_EVIDENCE_REVIEW' in r['review_groups']]
 mutants={}
 for label,vals in [('E1',[r['focal_mutants'] for r in observed]),('G0',[sum(r['G0_raw_status_counts'].values()) for r in rows if r['G0_raw_status_counts']])]:
  mutants[label]={'n_classes':len(vals),'min':min(vals),'q25':float(np.percentile(vals,25)),'median':float(np.median(vals)),'q75':float(np.percentile(vals,75)),'max':max(vals),'mean':float(np.mean(vals))}
 summary={'at_utc':datetime.now(timezone.utc).isoformat(),'n':300,'unique_class_keys':300,'full300_complete':False,
          'derived_from_rows_sha256':sha(IN/'class_results300.json'),'cohorts':cohorts,'gates':gates,'strata':strata,
          'full300_partial_identification':bounds(rows),'sensitivities':sensitivities,
          'score_basis_counts':dict(Counter(r['score_basis'] for r in rows)),
          'PIT_observed_zero_count':sum(r['PIT_score_observed_zero'] for r in rows),
          'policy_zero_count':sum(r['policy_zero_without_observed_score'] for r in rows),
          'end_to_end_unresolved_indices':[r['index'] for r in rows if r['end_to_end_unresolved']],
          'amendment30_measurement_unresolved_indices':[r['index'] for r in rows if r['amendment30_measurement_unresolved']],
          'stage_counts':{k:dict(Counter(r[k] for r in rows)) for k in ['generation','compile_production_evidence','compile_test_evidence','test_execution','PIT']},
          'historical_stage_counts':{arm:dict(Counter(r[arm+'_recorded_stage'] for r in rows)) for arm in ['G0','E0']},
          'nonpassing_suite_valid_PIT_indices':[r['index'] for r in rows if r['nonpassing_suite_with_valid_PIT']],
          'mutant_count_distribution':mutants,'new_experiments':0,'new_GPT_API_calls':0}
 formula_sources=[B/'backup/original/scripts_v2/AgoneTest/utils.py',B/'backup/original/scripts_v2/rbl4_v2_runner.py',R/'src/measurement_parser_v1.py',R/'src/measurement_parser_completion_v2.py',R/'src/gradle_measurement_parser_v1.py']
 formula_sources=[p for p in formula_sources if p.is_file()]
 formula={'formula':'round(100*KILLED/N,2)','denominator':'all focal SourceFile+package rows including nested classes',
          'TIMED_OUT_in_numerator':False,'TIMED_OUT_in_denominator':True,
          'scope':'shared original G0/E0 reducer and frozen E1 reducer; do not replace with PIT HTML metric',
          'sources':[{'path':str(p),'sha256':sha(p)} for p in formula_sources],
          'G0_raw_formula_reverified':sum(r['G0_raw_formula_verified'] for r in rows),
          'E0_raw_formula_reverified':sum(r['E0_raw_formula_verified'] for r in rows),
          'E1_raw_formula_reverified':len(observed),
          'historical_limitation':'E0 per-arm metrics and common reducer preserved; surviving shared-workspace reports cannot be independently attributed to E0 for all classes. Do not relabel unowned final reports as E0.',
          'class294':next({k:r[k] for k in ['index','class_key','G0_strict','E0_strict','G0_score_basis','E0_score_basis','observed_mutation_percent','PIT_status_counts','focal_mutants','killed_mutants','E1_K_plus_T_diagnostic_percent','test_counts','process_gate','raw_reports']} for r in rows if r['index']==294),
          'alternative_K_plus_T':'diagnostic arithmetic only; not applied to reported scores or RQs. A global replacement cannot be reconstructed from unavailable arm-specific E0 reports.'}
 dump(OUT/'class_results300.json',rows);dump(OUT/'statistics.json',summary);dump(OUT/'FORMULA_AUDIT.json',formula)
 dump(OUT/'measurement_evidence_review16.json',flags)
 flat=[]
 for r in rows:
  q={k:v for k,v in r.items() if k not in ['actual_commands','compiler_failure_evidence','historical_policy_selection']}
  q['selected_result_path']=r['selected_result']['path'];q['selected_result_sha256']=r['selected_result']['sha256'];q.pop('selected_result')
  flat.append(q)
 exportcsv(OUT/'class_results300.csv',flat)
 exportcsv(OUT/'unresolved_and_policy_zero.csv',[r for r in flat if r['end_to_end_unresolved'] or r['policy_zero_without_observed_score'] or r['amendment30_measurement_unresolved']])
 exportcsv(OUT/'measurement_evidence_review16.csv',flags)
 metrics=[]
 for name,cohort in cohorts.items():
  if cohort is None:continue
  for metric in ['left','right','left_minus_right'] if 'left' in cohort else ['value']:
   v=cohort if metric=='value' else cohort[metric]
   metrics.append({'cohort':name,'metric':metric,'n':v['n'],'repositories':v['repositories'],'mean':v['mean'],'median':v['median'],
                   'CI95_low':v['CI95_repository_percentile'][0],'CI95_high':v['CI95_repository_percentile'][1]})
 exportcsv(OUT/'statistics_summary.csv',metrics)
 audit.log('CHECKPOINT300_STATISTICS_RECOMPUTED',path=str(OUT),statistics_sha256=sha(OUT/'statistics.json'),rows=300,new_experiments=0,GPT_API_calls=0)
 print(json.dumps({'output':str(OUT),'counts':summary['score_basis_counts'],'E1_available':cohorts['G0_E1_evidence_aware_end_to_end_available'],
                   'bounds':{k:v for k,v in summary['full300_partial_identification'].items() if 'sensitivity' not in k},'gate':gates['E1_evidence_aware_process']},indent=2))

if __name__=='__main__':main()
