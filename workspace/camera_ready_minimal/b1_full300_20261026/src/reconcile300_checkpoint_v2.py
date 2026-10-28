"""Offline evidence join by class_key. No experiment entry points are invoked."""
import csv, json, re, sys
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
from offline_evidence_reader_v1 import evidence, commands
from maven_adapter_v1 import R, sha, dump
from parallel_pin_verify_v1 import verify_pins

A=R/'completion_amendment_v1'; B=R.parent/'paired49_20261023'; ROOT=R.parents[1]
OUT=A/'analysis300_checkpoint_v1'
sys.path.insert(0,str(B));import audit

def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def readcsv(p):
 with Path(p).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def pin(p):return {'path':str(p),'sha256':sha(p)}

def historical_report(j,hist,logs):
 """Only attribute the surviving shared-workspace report with an execution chain."""
 module=Path(j['source_candidate']['source_repo'])/j['module']
 base=module/('target/pit-reports' if j['build_tool']=='maven' else 'build/reports/pitest')
 reports=list(base.rglob('mutations.csv')) if base.exists() else []
 source=Path(j['source_candidate']['source_repo'])/j['focal_path']
 match=re.search(r'^\s*package\s+([\w.]+)\s*;',source.read_text(encoding='utf-8',errors='replace'),re.M)
 package=match.group(1) if match else ''
 result={'shared_workspace':str(module),'report_candidates':[pin(p) for p in reports],
         'owner':None,'ownership_reason':'No uniquely attributable surviving report',
         'focal_status_counts':None,'K_over_N_percent':None,'K_plus_T_over_N_diagnostic_percent':None}
 if len(reports)!=1:return result
 with reports[0].open(encoding='utf-8-sig',newline='') as f:raw=list(csv.reader(f))
 if not raw or not all(len(x)==7 for x in raw):return result
 focal=[x for x in raw if x[0].removesuffix('.java')==j['focal_class'] and x[1].rpartition('.')[0]==package]
 if not focal:return result
 segments={}
 for arm in ['gpt','evosuite']:
  x=logs[(j['class_key'],arm)];p=Path(x['log_path'])
  if not p.exists() or sha(p)!=x['log_sha256']:continue
  lines=p.read_text(encoding='utf-8',errors='replace').splitlines()
  # The recorded line bounds are one-based and inclusive in the historical audit.
  segments[arm]='\n'.join(lines[max(0,x['start_line']-1):x['end_line']])
 g=segments.get('gpt','');e=segments.get('evosuite','')
 success=lambda s:'Package command completed' in s
 measurement=lambda s:'--//loading maven execution..//' in s or '--//loading gradle execution..//' in s
 if not j['source_candidate'].get('shared_compiledrepos'):
  if int(hist['gpt_compilation'])==1 and success(g):
   result.update(owner='G0',ownership_reason='Per-class saved workspace; later GPT arm package completion after E0; frozen log hash verified')
  elif int(hist['evosuite_compilation'])==1 and success(e) and not measurement(g):
   result.update(owner='E0',ownership_reason='Per-class saved workspace; E0 package completion; no later GPT measurement invocation in arm segment')
 counts=Counter(x[5] for x in focal);n=len(focal)
 result.update(focal_status_counts=dict(counts),focal_mutants=n,killed_mutants=counts['KILLED'],timed_out_mutants=counts['TIMED_OUT'],
               K_over_N_percent=round(100*counts['KILLED']/n,2),K_plus_T_over_N_diagnostic_percent=round(100*(counts['KILLED']+counts['TIMED_OUT'])/n,2))
 if result['owner']:
  arm='gpt' if result['owner']=='G0' else 'evosuite'
  result['frozen_score_matches']=hist[arm+'_mutation_coverage']!='' and abs(float(hist[arm+'_mutation_coverage'])-result['K_over_N_percent'])<0.011
  if not result['frozen_score_matches']:
   result['owner']=None;result['ownership_reason']='Execution-chain candidate has a metric mismatch; not certified and frozen value not changed'
 return result

def main():
 assert not OUT.exists();OUT.mkdir();(OUT/'rows').mkdir()
 cp=A/'checkpoint30_v1'
 for line in (cp/'SHA256SUMS.txt').read_text().splitlines():
  expected,name=line.split('  ',1);assert Path(name).name==name and sha(cp/name)==expected
 verify_pins(load(A/'input_audit/baseline_pins.json'))
 audit.verify()
 jobs=load(R/'manifest300.json'); census={x['class_key']:x for x in load(A/'input_audit/class_census300.json')}
 checkpoint={x['class_key']:x for x in load(cp/'selected30.json')}
 hist_path=ROOT/'scripts_v2/results/runs/full300_merged_20260724_paper/metrics_wide.csv'
 history={x['class_key']:x for x in readcsv(hist_path)}
 stages={(x['class_key'],x['arm']):x for x in load(R/'analysis_camera_ready_rq45_v1/historical_arm_scoped_evidence600.json')}
 assert len(jobs)==len(census)==len(history)==300 and len(checkpoint)==30
 dump(OUT/'protocol.json',{'at_utc':datetime.now(timezone.utc).isoformat(),'scope':'offline300 checkpoint join and reanalysis',
      'authoritative_selection':'checkpoint30 selected_result by class_key overrides only the30 amendment slots; other270 preserved',
      'formula':'round(100*KILLED/all SourceFile+package focal rows including nested classes,2)',
      'TIMED_OUT':'included in denominator; excluded from numerator, in every arm',
      'zero_policy':'actual frozen-generation or measurement process failure can receive conventional end-to-end0; observed mutation remains null',
      'unresolved':'unqualified provider, adapter blocked before generation, or undefined zero-mutant denominator remain null in evidence-aware end-to-end score',
      'cluster_bootstrap':{'resamples':20000,'seed':20261023,'unit':'repository','estimand':'class-weighted paired mean'},
      'historical_wide':pin(hist_path),'checkpoint30':pin(cp/'selected30.json'),
      'no_new_experiments':True,'no_GPT_calls':True,'no_new_NI_claim':True,'all_original_values_preserved':True})
 rows=[]; rawpins={}; hist_reports=[]
 for j in jobs:
  i=j['sample_index_1based'];key=j['class_key'];c=census[key];h=history[key]
  assert int(h['sample_index'])+1==i
  selected=Path(checkpoint[key]['selected_result'] if key in checkpoint else c['previous_E1']['E1_result_path'])
  if key in checkpoint:assert sha(selected)==checkpoint[key]['result_sha256']
  ev=evidence(j,selected);raw=ev.pop('raw');cmd=ev.pop('commands')
  row={'index':i,'class_key':key,'repo_id':j['repo_id'],'build_tool':j['build_tool'],'seed':j['seed'],
       'fixed49':c['previous_E1']['fixed_historical49'],'amendment30':key in checkpoint,'review_groups':c['groups'],
       'selected_result':pin(selected),'selected_legacy_strict':raw['legacy_strict_mutation_percent'],**ev}
  for arm,prefix in [('gpt','G0'),('evosuite','E0')]:
   row[prefix+'_build']=int(h[arm+'_compilation']);row[prefix+'_strict']=float(h[arm+'_strict_mutation_coverage'])
   row[prefix+'_archived_mutation']=float(h[arm+'_mutation_coverage']) if h[arm+'_mutation_coverage']!='' else None
   row[prefix+'_recorded_stage']=stages[(key,arm)]['recorded_stage']
   row[prefix+'_score_basis']='ARCHIVED_GATE_PASS_METRIC' if row[prefix+'_build'] and row[prefix+'_archived_mutation'] is not None else 'HISTORICAL_POLICY_ZERO_NOT_OBSERVED_MUTATION'
   row[prefix+'_historical_log']=pin(stages[(key,arm)]['log_path'])
   assert row[prefix+'_strict']==(row[prefix+'_archived_mutation'] if row[prefix+'_build'] and row[prefix+'_archived_mutation'] is not None else 0.0)
  row['generation_calls_in_selected_stage']=raw.get('generation_calls')
  row['source_guard']=raw.get('source_guard');row['production_bytecode_guard']=raw.get('production_bytecode_guard')
  row['legacy_raw_process_gate']=raw['legacy_process_build']
  row['test_only_process_gate']=raw.get('test_only_process_gate')
  row['end_to_end_score_percent']=None;row['score_basis']='UNRESOLVED'
  adapter='GRADLE_TASK_REGISTRATION' in c['groups'];testonly=raw.get('test_only_process_gate') is not None
  row['process_gate']=None if adapter or testonly else raw['legacy_process_build']
  if testonly:row['PIT']='UNRESOLVED_PROVIDER_NOT_QUALIFIED'
  if adapter:
   row['generation']='NOT_STARTED_ADAPTER_BLOCK';row['score_basis']='UNRESOLVED_ADAPTER_TASK_BEFORE_GENERATION'
  elif testonly:row['score_basis']='UNRESOLVED_PROVIDER_TEST_ONLY'
  elif row['PIT']=='VALID_FOCAL_REPORT' and row['process_gate']==1:
   row['end_to_end_score_percent']=row['observed_mutation_percent'];row['score_basis']='OBSERVED_PIT_AND_PROCESS_GATE'
  elif row['process_gate']==0 and any(x['started'] and x['kind'] in {'generation','mutation_measurement','test_execution'} for x in cmd):
   row['end_to_end_score_percent']=0.0;row['score_basis']='CONVENTIONAL_PIPELINE_FAILURE_ZERO_NOT_OBSERVED'
  elif row['PIT']=='ZERO_FOCAL_MUTANTS':row['score_basis']='UNDEFINED_ZERO_FOCAL_MUTANTS'
  row['PIT_process_timeout']=any(x['kind']=='mutation_measurement' and x['timeout'] for x in cmd)
  row['PIT_measurement_unresolved']=row['observed_mutation_percent'] is None
  row['end_to_end_unresolved']=row['end_to_end_score_percent'] is None
  row['amendment30_measurement_unresolved']=row['amendment30'] and row['PIT_measurement_unresolved']
  row['E1_TIMED_OUT_mutants']=row['PIT_status_counts'].get('TIMED_OUT',0)
  row['E1_K_plus_T_diagnostic_percent']=round(100*(row['killed_mutants']+row['E1_TIMED_OUT_mutants'])/row['focal_mutants'],2) if row['observed_mutation_percent'] is not None else None
  row['test_counts']={k:sum(int(x.get(k,0)) for x in raw.get('surefire_suites',[])) for k in ['tests','errors','failures','skipped']}
  row['actual_commands']=cmd
  hist_report=historical_report(j,h,stages);hist_reports.append({'index':i,'class_key':key,**hist_report})
  row['historical_raw_report_owner']=hist_report['owner']
  for prefix in ['G0','E0']:
   row[prefix+'_raw_formula_verified']=hist_report['owner']==prefix
   row[prefix+'_raw_status_counts']=hist_report['focal_status_counts'] if hist_report['owner']==prefix else None
  for p in row['raw_reports']+[row['selected_result']]+hist_report['report_candidates']:rawpins[p['path']]=p['sha256']
  dump(OUT/'rows'/f'{i:03d}.json',row);rows.append(row)
  if i%20==0:print('RECONCILED',i,flush=True)
 assert len({r['class_key'] for r in rows})==300 and sum(r['amendment30'] for r in rows)==30
 dump(OUT/'class_results300.json',rows);dump(OUT/'historical_report_formula_audit300.json',hist_reports);dump(OUT/'raw_report_pins.json',rawpins)
 counts={'PIT':dict(Counter(r['PIT'] for r in rows)),'score_basis':dict(Counter(r['score_basis'] for r in rows)),
         'amendment30_unresolved':[r['index'] for r in rows if r['amendment30_measurement_unresolved']],
         'end_to_end_unresolved':[r['index'] for r in rows if r['end_to_end_unresolved']],
         'historical_raw_owner_counts':dict(Counter(x['owner'] or 'UNRESOLVED' for x in hist_reports))}
 dump(OUT/'reconciliation_counts.json',counts)
 audit.log('CHECKPOINT300_OFFLINE_RECONCILED',rows=300,output=str(OUT),output_sha256=sha(OUT/'class_results300.json'),new_experiment_calls=0,GPT_API_calls=0)
 print(json.dumps(counts,indent=2))

if __name__=='__main__':main()
