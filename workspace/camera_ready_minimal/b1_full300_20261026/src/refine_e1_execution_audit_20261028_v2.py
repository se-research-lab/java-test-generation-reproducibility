"""Offline refinement: preserve old non-execution placeholder events distinctly.
Add generation-internal compiler diagnostics; never change experimental results.
"""
import json,csv,re,hashlib,shutil,sys,math
from pathlib import Path
from collections import Counter,defaultdict
from datetime import datetime,timezone
R=Path(__file__).resolve().parents[1];ROOT=R.parents[1];B=R.parent/'paired49_20261023';I=R/'audit_e1_execution_20261028_v1';O=R/'audit_e1_execution_20261028_v2';F=R/'completion_amendment_v1/final300_offline_v1';H=R/'policy_attempt_history_v2'
sys.path.insert(0,str(B));import audit
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(name,v):
 with (O/name).open('x',encoding='utf-8') as f:json.dump(v,f,ensure_ascii=False,indent=2);f.write('\n')
def export(name,rows):
 fields=list(dict.fromkeys(k for r in rows for k in r))
 with (O/name).open('x',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
  for r in rows:w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in r.items()})
def evidence(c,pattern,label):
 out=[]
 for s in c['logs']:
  p=Path(s)
  if not p.is_file():continue
  lines=p.read_text(encoding='utf-8',errors='replace').splitlines()
  hits=[(i+1,x) for i,x in enumerate(lines) if re.search(pattern,x,re.I)]
  for line,text in hits[:3]:out.append({'kind':label,'path':str(p),'sha256':sha(p),'line':line,'excerpt':text[:400]})
 return out
assert not O.exists();O.mkdir()
oldsummary=load(I/'summary.json')
assert len(oldsummary['issues'])==40 and all(x['path']==str(ROOT) and x['issue']=='MISSING' for x in oldsummary['issues'])
commands=[c for c in load(I/'command_attempts.json') if c['record_path']!=str(ROOT)]
with (H/'command_history_all.csv').open(encoding='utf-8-sig',newline='') as f:placeholders=[x for x in csv.DictReader(f) if not x['record_path']]
assert len(placeholders)==40 and all(x['stage']=='NO_CORPUS_EXECUTION' and x['process_started']=='False' for x in placeholders)
dump('prior_nonexecution_status40.json',placeholders)
rows=load(I/'classes300.json');byindex={r['index']:r for r in rows};byclass=defaultdict(list)
for c in commands:byclass[c['index']].append(c)
profile=load(R/'protocol.json')['generation_options'];profiles=[];technical=[]
for c in commands:
 if c['stage']!='GENERATION_NEW_SEARCH' or not c['started']:continue
 argv=c['argv'];opts=[x for x in argv if x.startswith('-D') and not x.startswith(('-Dtest_dir=','-Dreport_dir=','-DCP_file_path='))]
 expectedseed=byindex[c['index']]['seed'];actualseed=int(argv[argv.index('-seed')+1])
 match=sorted(opts)==sorted(profile) and actualseed==expectedseed and c['timeout_seconds']==240
 profiles.append({'index':c['index'],'phase':c['phase'],'record_path':c['record_path'],'profile_seed_cap_match':match,'seed':actualseed,'generation_cap':c['timeout_seconds']})
 assert match,c['record_path']
 if c['attempt_kind']=='PREDECLARED_TECHNICAL_SANITIZED_CLASSPATH_RETRY':technical.append({'index':c['index'],'phase':c['phase'],'marker':c['technical_retry_marker'],'path':c['record_path']})
candidate_rows=[]
for r in rows:
 cs=byclass[r['index']];gen=[c for c in cs if c['stage']=='GENERATION_NEW_SEARCH' and c['started']]
 r['all_command_records']=len(cs);r['prior_nonexecution_status_record']=any(int(x['index'])==r['index'] for x in placeholders)
 r['measurement_started_at_least_once']=any(c['started'] and c['stage']=='MEASUREMENT_EXISTING_SUITE' for c in cs)
 # Remove broad ByteBuddy classpath mentions from error evidence; retain genuine stack/error messages.
 r['evidence']=[e for e in r['evidence'] if not (e['kind']=='BYTECODE_INSTRUMENTATION' and re.match(r'\s*-\s+[A-Za-z]:',e['excerpt']))]
 selected=[c for c in gen if c['folder_is_final_selected']];last=(selected or gen)[-1] if gen else None
 r['generator_reported_candidate_count']=None;r['internal_compile_failure']=False
 if r['generation']=='UNSUCCESSFUL' and last:
  candidates=evidence(last,r'\* Generated \d+ tests with total length','GENERATOR_CANDIDATES_BEFORE_EXPORT')
  compiler=evidence(last,r'ServiceConfigurationError|JUnitAnalyzer\.compileTests|compileAndCheckTests|removeTestsThatDoNotCompile','GENERATOR_INTERNAL_COMPILER')
  if candidates:
   r['generator_reported_candidate_count']=int(re.search(r'Generated (\d+)',candidates[-1]['excerpt'])[1]);r['evidence']+=candidates
   candidate_rows.append({'index':r['index'],'class_key':r['class_key'],'count':r['generator_reported_candidate_count'],'evidence':candidates+compiler})
  if compiler:
   r['internal_compile_failure']=True;r['category']='GENERATOR_INTERNAL_COMPILE_PROVIDER_FAILURE';r['evidence']+=compiler
 r['last_generation_returncode']=last['returncode'] if last else None
 # Class key is casefolded; present actual FQCN from the selected measurement or original manifest.
 manifest=load(R/'manifest300.json')[r['index']-1]
 r['focal_class_name']=manifest.get('focal_class') or r['class_key'].split('/')[-1]
 r['source_commit']=manifest.get('source_candidate',{}).get('commit') or manifest.get('commit')
phase=[]
for name in sorted({c['phase'] for c in commands}):
 cs=[c for c in commands if c['phase']==name];times=sorted(c['start_utc'] for c in cs if c['start_utc'] and c['start_utc'].startswith('2026-'))
 phase.append({'phase':name,'classes':sorted({c['index'] for c in cs}),'class_count':len({c['index'] for c in cs}),'commands':len(cs),'started':sum(c['started'] for c in cs),'generation':sum(c['started'] and c['stage']=='GENERATION_NEW_SEARCH' for c in cs),'measurement':sum(c['started'] and c['stage']=='MEASUREMENT_EXISTING_SUITE' for c in cs),'first_utc':times[0] if times else None,'last_command_start_utc':times[-1] if times else None})
counters=dict(oldsummary['counts']);counters.update(command_records=len(commands),prior_nonexecution_status_records=40,command_and_status_records=len(commands)+40,final_categories=dict(Counter(r['category'] for r in rows)),classes_with_measurement_start=sum(r['measurement_started_at_least_once'] for r in rows),generation_internal_compile_failures=sum(r['internal_compile_failure'] for r in rows),failed_generation_with_candidate_message=len(candidate_rows),technical_retry_processes=len(technical),technical_retry_classes=sorted({x['index'] for x in technical}))
assert counters['actual_generation_processes']==len(profiles)==305
assert counters['generation_started_classes']==290 and len(technical)==15
counts_by_build={b:{'classes':len([r for r in rows if r['build_tool']==b]),'complete_suites':sum(r['has_complete_suite'] for r in rows if r['build_tool']==b),'observed_PIT':sum(r['has_observed_PIT'] for r in rows if r['build_tool']==b),'complete_suite_without_observed_PIT':sum(r['complete_suite_without_observed_PIT'] for r in rows if r['build_tool']==b),'gen_unsuccessful':sum(r['generation']=='UNSUCCESSFUL' for r in rows if r['build_tool']==b),'not_started':sum(r['generation']=='NOT_STARTED_ADAPTER_BLOCK' for r in rows if r['build_tool']==b)} for b in ['maven','gradle']}
out={'at_utc':datetime.now(timezone.utc).isoformat(),'status':'PASS_WITH_EXPLICIT_HISTORICAL_LIMITATIONS','counts':counters,'build_tool_counts':counts_by_build,'phase_counts':phase,'input_hash_issues':[],'native_source_hash_checks':oldsummary['native_source_hash_checks'],'verified_unique_files':oldsummary['verified_unique_files'],'audit_parser_correction':'40 historical Gradle NOT_ATTEMPTED status rows have blank record_path; they are not file records. V1 resolved blank to workspace and emitted40 false missing-file flags; V2 preserves all40 status rows separately, with no change to actual started-command or scientific counts.','new_experiments':0,'benchmark_rows_changed':0,'scope':oldsummary['scope']}
dump('summary.json',out);dump('classes300.json',rows);dump('command_attempts.json',commands);dump('GENERATION_PROFILE_CHECKS.json',profiles);dump('TECHNICAL_RETRIES.json',technical);dump('GENERATOR_CANDIDATES_WITHOUT_EXPORT.json',candidate_rows)
export('classes300.csv',[{k:v for k,v in r.items() if k!='evidence'} for r in rows]);export('generated_without_valid_measurement32.csv',[{k:v for k,v in r.items() if k!='evidence'} for r in rows if r['complete_suite_without_observed_PIT']]);export('generation_unsuccessful37.csv',[{k:v for k,v in r.items() if k!='evidence'} for r in rows if r['generation']=='UNSUCCESSFUL']);export('adapter_not_started10.csv',[{k:v for k,v in r.items() if k!='evidence'} for r in rows if r['generation']=='NOT_STARTED_ADAPTER_BLOCK']);export('command_attempts.csv',[{k:v for k,v in c.items() if k!='error_markers'} for c in commands]);export('phase_counts.csv',phase)
export('error_evidence.csv',[{'index':r['index'],'class_key':r['class_key'],'final_category':r['category'],**e} for r in rows for e in r['evidence']])
for name in ['verified_input_hashes.json','job_folders.json','job_folders.csv','RAW_PIT_RECHECK.json']:shutil.copy2(I/name,O/name)
audit.log('E1_EXECUTION_AUDIT_REFINED',path=str(O),summary_sha256=sha(O/'summary.json'),scope='read-only parser correction and error clarification',new_experiments=0)
print(json.dumps({'counts':counters,'build_tool_counts':counts_by_build,'candidate_messages_without_complete_suite':candidate_rows,'phase_counts':[{k:v for k,v in p.items() if k!='classes'} for p in phase]},ensure_ascii=False,indent=2))
