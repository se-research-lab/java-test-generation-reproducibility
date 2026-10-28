"""Read-only E1 execution census: merge archived command history and later jobs.
No experimental imports, subprocess calls, Java, build system or network calls.
"""
import csv,json,re,hashlib,sys
from pathlib import Path
from collections import Counter,defaultdict
from datetime import datetime,timezone,timedelta
R=Path(__file__).resolve().parents[1];ROOT=R.parents[1];B=R.parent/'paired49_20261023';F=R/'completion_amendment_v1/final300_offline_v1';H=R/'policy_attempt_history_v2';O=R/'audit_e1_execution_20261028_v1'
sys.path.insert(0,str(B));import audit
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,v):
 with Path(p).open('x',encoding='utf-8') as f:json.dump(v,f,ensure_ascii=False,indent=2);f.write('\n')
def csvread(p):
 with Path(p).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def export(name,rows):
 keys=list(dict.fromkeys(k for r in rows for k in r))
 with (O/name).open('x',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=keys);w.writeheader()
  for r in rows:w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in r.items()})
def path(x):return Path(x) if Path(x).is_absolute() else ROOT/x
pins={};issues=[]
def pin(p,expected=None):
 p=Path(p);key=str(p)
 if not p.is_file():issues.append({'path':key,'issue':'MISSING'});return None
 if key not in pins:pins[key]=sha(p)
 if expected and pins[key]!=expected:issues.append({'path':key,'issue':'HASH_MISMATCH','expected':expected,'actual':pins[key]})
 return {'path':key,'sha256':pins[key]}
patterns={
 'LICENSE_HEADER':r'(?i)(some files do not have the expected license header|license.*(?:failed|missing|header)|failed.*license)',
 'PIT_MINION':r'(?i)(minion.*(?:died|exited|error)|coverage generation minion|coverage.*minion)',
 'UNSUPPORTED_BYTECODE':r'(?i)(unsupported class(?: file)?(?: major)? version|unsupported major|class file version|ASM.*version)',
 'CLASS_LOADING':r'(?i)(ClassNotFoundException|NoClassDefFoundError|should be in target project, but could not be found|Error while initializing target class)',
 'BYTECODE_INSTRUMENTATION':r'(?i)(InnerClasses attribute|MockMethodAdvice|MockMethodDispatcher|bytebuddy|IllegalArgumentException)',
 'MISSING_TASK':r"(?i)(task .*(?:not found|not available)|cannot locate tasks)",
 'COMPILE_DIAGNOSTIC':r'(?i)(COMPILATION ERROR|Compilation failure|cannot find symbol|Compilation failed; see)',
 'TEST_FAILURE':r'(?i)(there were failing tests|tests failed|AssertionError|ExceptionInInitializerError)',
 'DEPENDENCY_RESOLUTION':r'(?i)(could not resolve|could not find|cannot access .*offline|no cached version)',
 'JUNIT_PROVIDER':r'(?i)(junit.*(?:provider|not found|NoClassDefFound)|provider.*junit)',
 'POM_PARSE':r'(?i)(non-parseable pom|malformed pom|unrecognised tag)',
 'DISK_FULL':r'(?i)(no space left|not enough space|disk full)',
 'TIMEOUT_TEXT':r'(?i)(timed out|timeout exceeded|timeout after)'}
logcache={}
def log_evidence(p):
 p=Path(p)
 if not p.is_file():return []
 key=str(p)
 if key in logcache:return logcache[key]
 ref=pin(p);lines=p.read_text(encoding='utf-8',errors='replace').splitlines();found=[]
 for kind,pattern in patterns.items():
  matches=[(i+1,t) for i,t in enumerate(lines) if re.search(pattern,t)]
  for line,t in matches[:2]:found.append({'kind':kind,**ref,'line':line,'excerpt':t[:350]})
 logcache[key]=found;return found
def stages(argv):
 if '-jar' in argv and any('evosuite' in x.lower() for x in argv):return 'GENERATION_NEW_SEARCH'
 if any('mutationCoverage' in x or x.endswith('pitest') for x in argv):return 'MEASUREMENT_EXISTING_SUITE'
 if any(x in ['test','verify'] or x.endswith('b1NativeTest') or ('surefire-plugin:' in x and x.endswith(':test')) for x in argv):return 'TEST_EXECUTION_EXISTING_SUITE'
 return 'COMPILE_OR_DEPENDENCY_AUDIT'
def originfolder(p):return p.parent.parent.parent if p.name=='plan.json' else p.parent
def main():
 assert not O.exists();O.mkdir()
 rows=load(F/'class_results300.json');assert len(rows)==len({r['class_key'] for r in rows})==300
 for line in (F/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
  h,name=line.split('  ',1);pin(F/name,h)
 byindex={r['index']:r for r in rows};commands={};old=csvread(H/'command_history_all.csv');pin(H/'command_history_all.csv')
 for h in old:
  p=path(h['record_path']);pin(p,h['record_sha256']);argv=json.loads(h['logical_argv_json']) if h['logical_argv_json'] else []
  c={'index':int(h['index']),'class_key':h['class_key'],'phase':h['phase'],'stage':h['stage'],'attempt_kind':h['attempt_kind'],'record_path':str(p),'record_sha256':h['record_sha256'],'folder':str(originfolder(p)),'started':h['process_started']=='True','start_utc':h['event_time_utc'],'returncode':int(h['returncode']) if h['returncode'] else None,'termination_reason':h['termination_reason'],'timeout_seconds':float(h['timeout_seconds']) if h['timeout_seconds'] else None,'elapsed_seconds':float(h['elapsed_seconds']) if h['elapsed_seconds'] else None,'seed':h['seed'],'argv':argv,'logs':[str(path(h[k])) for k in ['stdout_path','stderr_path'] if h[k]],'technical_retry_marker':h['technical_retry_marker'],'historical_selection_role':h['selection_role']}
  commands[str(p).lower()]=c
 folders=[]
 for folder in sorted((R/'jobs').iterdir()):
  m=re.match(r'^(\d{3})(?:_|$)',folder.name)
  if not folder.is_dir() or not m:continue
  i=int(m.group(1));assert i in byindex
  plans=sorted((folder/'commands').glob('*/plan.json'))
  phase='COMPLETION_'+folder.name[4:] if '_completion_' in folder.name else 'GRADLE_FROZEN_V1' if folder.name.endswith('_gradle_v1') else folder.name
  for p in plans:
   key=str(p).lower()
   if key in commands:continue
   d=load(p);argv=d['argv'];start=p.parent/'started.json';finish=p.parent/'finished.json';s=load(start) if start.exists() else {};e=load(finish) if finish.exists() else {}
   pin(p);pin(start) if start.exists() else None;pin(finish) if finish.exists() else None
   logs=[]
   for name in ['stdout','stderr']:
    q=p.parent/(name+'.txt')
    if q.exists():pin(q,e.get(name+'_sha256'));logs.append(str(q))
   stage=stages(argv);kind='POST_OUTCOME_COMPLETION' if '_completion_' in folder.name else 'FROZEN_GRADLE_EXECUTION'
   commands[key]={'index':i,'class_key':byindex[i]['class_key'],'phase':phase,'stage':stage,'attempt_kind':kind,'record_path':str(p),'record_sha256':sha(p),'folder':str(folder),'started':bool(s),'start_utc':s.get('started_utc',d.get('planned_utc')),'finish_utc':e.get('finished_utc'),'returncode':e.get('returncode'),'termination_reason':e.get('reason'),'timeout_seconds':d.get('timeout_seconds'),'elapsed_seconds':e.get('elapsed_seconds'),'seed':argv[argv.index('-seed')+1] if '-seed' in argv else None,'argv':argv,'logs':logs,'technical_retry_marker':None,'historical_selection_role':None}
  roots=[]
  for p in sorted(folder.iterdir()):
   if p.is_file() and p.suffix.lower() in {'.json','.diff','.md'}:roots.append(pin(p))
  foldercommands=[c for c in commands.values() if c['folder']==str(folder)]
  folders.append({'index':i,'class_key':byindex[i]['class_key'],'folder':str(folder),'metadata':roots,'commands':len(foldercommands),'started_commands':sum(c['started'] for c in foldercommands),'generation_starts':sum(c['started'] and c['stage']=='GENERATION_NEW_SEARCH' for c in foldercommands),'measurement_starts':sum(c['started'] and c['stage']=='MEASUREMENT_EXISTING_SUITE' for c in foldercommands),'has_result':(folder/'result.json').exists(),'has_unresolved_record':(folder/'unresolved.json').exists()})
 # E49 lineage paths are preserved from the verified historical command census.
 byclass=defaultdict(list)
 for c in commands.values():
  c['error_markers']=[e for p in c['logs'] for e in log_evidence(p)]
  c['folder_is_final_selected']=str(Path(byindex[c['index']]['selected_result']['path']).parent).lower()==c['folder'].lower()
  byclass[c['index']].append(c)
 native=load(H/'native_source_hash_evidence.json')
 for e in native:pin(path(e['path']),e['generated_sha256'])
 native_count=len(native)
 for folder in sorted((R/'jobs').iterdir()):
  p=folder/'native_generated.json'
  if p.is_file():
   for e in load(p).get('files',[]):pin(e['path'],e['sha256']);native_count+=1
 summaryrows=[];errorrows=[]
 for r in rows:
  pin(r['selected_result']['path'],r['selected_result']['sha256']);d=load(r['selected_result']['path']);cs=byclass[r['index']]
  gen=[c for c in cs if c['stage']=='GENERATION_NEW_SEARCH' and c['started']]
  measure=[c for c in cs if c['stage']=='MEASUREMENT_EXISTING_SUITE' and c['started']]
  selectedlogs=[e for cmd in r['actual_commands'] for ref in cmd['logs'] for e in log_evidence(ref['path'])]
  for cmd in r['actual_commands']:
   for ref in cmd['logs']:pin(ref['path'],ref['sha256'])
  kinds={e['kind'] for e in selectedlogs}
  has_suite=r['generation'].startswith('COMPLETE_SUITE')
  if r['observed_mutation_percent'] is not None:category='VALID_OBSERVED_PIT'
  elif r['PIT']=='ZERO_FOCAL_MUTANTS':category='NO_FOCAL_MUTANTS'
  elif r['generation']=='NOT_STARTED_ADAPTER_BLOCK':category='ADAPTER_TASK_BEFORE_GENERATION'
  elif 'JUNIT3_SUPPORT' in r['review_groups']:category='JUNIT3_TEST_ONLY_PIT_UNQUALIFIED'
  elif r['PIT_process_timeout']:category='WHOLE_MEASUREMENT_TIMEOUT'
  elif has_suite and r['test_execution']=='FAIL':category='NATIVE_TEST_EXECUTION_FAILURE'
  elif has_suite and 'PIT_MINION' in kinds:category='PIT_MINION_FAILURE'
  elif has_suite and 'LICENSE_HEADER' in kinds:category='LICENSE_CHECK_FAILURE'
  elif has_suite:category='MEASUREMENT_FAILURE_REQUIRES_REVIEW'
  else:
   selectedgen=[c for c in gen if c['folder_is_final_selected']];last=selectedgen[-1] if selectedgen else (gen[-1] if gen else None)
   mk={e['kind'] for e in last['error_markers']} if last else set()
   if last and (last['termination_reason']=='TIMEOUT' or last['returncode']==124):category='GENERATION_PROCESS_TIMEOUT'
   elif 'UNSUPPORTED_BYTECODE' in mk:category='GENERATION_UNSUPPORTED_BYTECODE'
   elif 'CLASS_LOADING' in mk:category='GENERATION_CLASS_LOADING_OR_INIT'
   elif 'BYTECODE_INSTRUMENTATION' in mk:category='GENERATION_INSTRUMENTATION'
   else:category='GENERATION_UNSUCCESSFUL_OTHER'
   selectedlogs=[e for c in selectedgen or gen[-1:] for e in c['error_markers']]
  inventory=d.get('inventory') or {};genbyfolder=Counter(c['folder'] for c in gen)
  rc={k:r[k] for k in ['index','class_key','repo_id','build_tool','seed','fixed49','amendment30','generation','compile_production_evidence','compile_test_evidence','test_execution','test_counts','PIT','process_gate','observed_mutation_percent','end_to_end_score_percent','score_basis','focal_mutants','killed_mutants','E1_TIMED_OUT_mutants','nonpassing_suite_with_valid_PIT','selected_result']}
  rc.update(has_complete_suite=has_suite,has_observed_PIT=r['observed_mutation_percent'] is not None,complete_suite_without_observed_PIT=has_suite and r['observed_mutation_percent'] is None,category=category,actual_generation_processes=len(gen),measurement_processes=len(measure),all_command_records=len(cs),any_generation_started=bool(gen),phases=list(dict.fromkeys(c['phase'] for c in cs)),generation_folder_counts=dict(genbyfolder),declared_technical_retries=sum(c['attempt_kind']=='PREDECLARED_TECHNICAL_SANITIZED_CLASSPATH_RETRY' and c['started'] for c in gen),placeholder_methods=inventory.get('no_behavior_placeholder_count'),behavior_test_methods=inventory.get('behavior_test_method_count'),evidence=selectedlogs)
  summaryrows.append(rc)
  for e in selectedlogs:errorrows.append({'index':r['index'],'class_key':r['class_key'],'category':category,**e})
 # Recompute the scientific counts; do not modify or replace the sealed table.
 counters={'keys':len(summaryrows),'generation_started_classes':sum(x['any_generation_started'] for x in summaryrows),'complete_suites':sum(x['has_complete_suite'] for x in summaryrows),'observed_PIT':sum(x['has_observed_PIT'] for x in summaryrows),'complete_suite_without_observed_PIT':sum(x['complete_suite_without_observed_PIT'] for x in summaryrows),'generation_unsuccessful':sum(x['generation']=='UNSUCCESSFUL' for x in summaryrows),'adapter_not_started':sum(x['generation']=='NOT_STARTED_ADAPTER_BLOCK' for x in summaryrows),'actual_generation_processes':sum(x['actual_generation_processes'] for x in summaryrows),'measurement_processes':sum(x['measurement_processes'] for x in summaryrows),'command_records':len(commands),'actual_started_commands':sum(c['started'] for c in commands.values()),'final_categories':dict(Counter(x['category'] for x in summaryrows)),'process_gate':dict(Counter(str(x['process_gate']) for x in summaryrows)),'test_execution':dict(Counter(x['test_execution'] for x in summaryrows))}
 assert counters['complete_suites']==253 and counters['observed_PIT']==221 and counters['complete_suite_without_observed_PIT']==32
 phase=[]
 for name in sorted({c['phase'] for c in commands.values()}):
  cs=[c for c in commands.values() if c['phase']==name];times=sorted(c['start_utc'] for c in cs if c['start_utc'] and c['start_utc'].startswith('2026-'))
  phase.append({'phase':name,'classes':sorted({c['index'] for c in cs}),'command_records':len(cs),'started_commands':sum(c['started'] for c in cs),'generation_starts':sum(c['started'] and c['stage']=='GENERATION_NEW_SEARCH' for c in cs),'measurement_starts':sum(c['started'] and c['stage']=='MEASUREMENT_EXISTING_SUITE' for c in cs),'first_recorded_utc':times[0] if times else None,'last_start_recorded_utc':times[-1] if times else None})
 results={'at_utc':datetime.now(timezone.utc).isoformat(),'status':'PASS' if not issues else 'INTEGRITY_FINDINGS','counts':counters,'issues':issues,'phase_counts':phase,'verified_unique_files':len(pins),'native_source_hash_checks':native_count,'scope':'Selected E1 lineage, historical linked diagnostics, all indexed current B1 job folders; excludes unrelated abandoned/synthetic/repeated experiments','new_experiments':0}
 dump(O/'summary.json',results);dump(O/'classes300.json',summaryrows);dump(O/'command_attempts.json',list(commands.values()));dump(O/'job_folders.json',folders)
 dump(O/'verified_input_hashes.json',[{'path':p,'sha256':h} for p,h in sorted(pins.items())]);dump(O/'error_evidence.json',errorrows)
 export('classes300.csv',[{k:v for k,v in r.items() if k!='evidence'} for r in summaryrows]);export('generated_without_valid_measurement32.csv',[{k:v for k,v in r.items() if k!='evidence'} for r in summaryrows if r['complete_suite_without_observed_PIT']]);export('phase_counts.csv',phase)
 export('generation_unsuccessful37.csv',[{k:v for k,v in r.items() if k!='evidence'} for r in summaryrows if r['generation']=='UNSUCCESSFUL']);export('adapter_not_started10.csv',[{k:v for k,v in r.items() if k!='evidence'} for r in summaryrows if r['generation']=='NOT_STARTED_ADAPTER_BLOCK'])
 export('error_evidence.csv',errorrows);export('command_attempts.csv',[{k:v for k,v in c.items() if k!='error_markers'} for c in commands.values()]);export('job_folders.csv',folders)
 audit.log('E1_FULL_EXECUTION_READONLY_AUDIT',path=str(O),summary_sha256=sha(O/'summary.json'),counts=counters,issues=len(issues),new_experiments=0)
 print(json.dumps(results,indent=2,ensure_ascii=False))
if __name__=='__main__':main()
