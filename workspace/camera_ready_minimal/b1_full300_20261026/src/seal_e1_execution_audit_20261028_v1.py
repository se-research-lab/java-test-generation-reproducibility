"""Validate/seal new audit only. Never start experimental work."""
import json,csv,hashlib,re,sys
from pathlib import Path
from datetime import datetime,timezone
import psutil
R=Path(__file__).resolve().parents[1];O=R/'audit_e1_execution_20261028_v2';F=R/'completion_amendment_v1/final300_offline_v1';B=R.parent/'paired49_20261023';D=R/'camera_ready_checkpoint300_v1/delivery'
sys.path.insert(0,str(B));import audit
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(name,obj):
 with (O/name).open('x',encoding='utf-8') as f:json.dump(obj,f,ensure_ascii=False,indent=2);f.write('\n')
rows=load(O/'class_history300.json');frozen=load(F/'class_results300.json');commands=load(O/'command_attempts.json')
assert len(rows)==300 and len({r['class_key'] for r in rows})==300
for r,f in zip(rows,frozen):
 assert r['class_key']==f['class_key']
 for k in ['observed_mutation_percent','end_to_end_score_percent','process_gate','G0_build','G0_strict','E0_build','E0_strict']:assert r[k]==f[k],(r['index'],k)
 assert re.fullmatch('[0-9a-f]{40}',r['source_commit'])
 assert sha(r['selected_result']['path'])==r['selected_result']['sha256']
assert sum(r['actual_generation_processes'] for r in rows)==305
assert sum(r['measurement_processes'] for r in rows)==292
assert len(commands)==2195 and sum(c['started'] for c in commands)==2190
assert sum(r['has_complete_suite'] for r in rows)==253
assert sum(r['has_observed_PIT'] for r in rows)==221
assert sum(r['complete_suite_without_observed_PIT'] for r in rows)==32
assert sum(r['end_to_end_score_percent'] is None for r in rows)==21
assert sum(r['score_basis']=='CONVENTIONAL_PIPELINE_FAILURE_ZERO_NOT_OBSERVED' for r in rows)==58
assert len(load(O/'GENERATION_PROFILE_CHECKS.json'))==305 and all(r['profile_seed_cap_match'] for r in load(O/'GENERATION_PROFILE_CHECKS.json'))
protected=load(B/'audit/protected_manifest.json');bad=[r['source'] for r in protected if not Path(r['source']).is_file() or sha(r['source'])!=r['sha256'] or sha(r['backup'])!=r['sha256']];assert not bad,bad
gpt=load(B/'audit/e1_execution_audit_gpt_guard_20261028.stdout.txt');assert gpt['status']=='PASS'
sealed=[]
for base in [F,D]:
 for line in (base/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
  h,n=line.split('  ',1);assert sha(base/n)==h,str(base/n);sealed.append(str(base/n))
# Inspect process state. Capture names/script basenames only, never arbitrary argv or credentials.
workers=[];python_processes=[];inaccessible=[]
for proc in psutil.process_iter(['pid','name']):
 try:
  name=(proc.info['name'] or '').lower()
  if name in ['java.exe','javaw.exe','mvn.exe','gradle.exe']:workers.append({'pid':proc.pid,'name':name})
  if name in ['python.exe','pythonw.exe']:
   args=proc.cmdline();scripts=[Path(a).name for a in args if a.lower().endswith('.py')]
   python_processes.append({'pid':proc.pid,'scripts':scripts})
   if any(re.search(r'worker|dispatcher|run_.*(?:batch|queue|completion|evosuite|e49|b1)',x,re.I) for x in scripts):workers.append({'pid':proc.pid,'name':name,'scripts':scripts})
 except (psutil.NoSuchProcess,psutil.ZombieProcess):pass
 except psutil.AccessDenied:inaccessible.append({'pid':proc.pid,'name':proc.info['name']})
assert not workers,workers
report=(O/'BAO_CAO_TOAN_BO_E1.md').read_text(encoding='utf-8')+(O/'CLASS_HISTORY300.md').read_text(encoding='utf-8')
links=re.findall(r'\]\(<([^>]+)>\)',report);missing=[p for p in links if not Path(p).is_file()];assert not missing,missing
audit.verify_chain()
write('FINAL_INTEGRITY.json',{'at_utc':datetime.now(timezone.utc).isoformat(),'status':'PASS','rows':300,'unique_keys':300,'scientific_values_match_checkpoint':True,'original_and_backup_files_verified':len(protected),'changed_or_missing_protected':bad,'gpt_guard':gpt,'sealed_final_data_and_camera_ready_files_verified':len(sealed),'experimental_worker_candidates':workers,'python_process_scripts_at_snapshot':python_processes,'process_access_denied':inaccessible,'local_file_links_verified':len(links),'audit_chain':'PASS','new_experiments':0,'new_GPT_API_calls':0,'experimental_data_changes':0,'paper_changes':0})
scripts=['audit_e1_execution_20261028_v1.py','verify_e1_raw_reports_20261028_v1.py','refine_e1_execution_audit_20261028_v2.py','report_e1_execution_20261028_v1.py','seal_e1_execution_audit_20261028_v1.py']
write('AUDIT_CODE_MANIFEST.json',[{'path':str(R/'src'/n),'sha256':sha(R/'src'/n)} for n in scripts])
with (O/'README.md').open('x',encoding='utf-8') as f:f.write('''# E1 audit package — read-only analysis

Start with BAO_CAO_TOAN_BO_E1.md. CLASS_HISTORY300.md lists every class and command receipt; class_history300.csv/json are the complete handoff tables. Intermediate classes300.* are retained for audit but have an unfilled source_commit field; class_history300.* correctly joins commit_sha from manifest300.json.

No experiments ran during this audit. Existing reports and receipts remain at their original private workspace paths. This is an audit index, not a copy of all raw experimental files. Absolute paths resolve in the current workspace.

SHA256SUMS.txt covers this directory's deliverables. verified_input_hashes.json identifies the raw evidence checked; RAW_PIT_RECHECK.json independently recomputes 221 selected raw scores. FINAL_INTEGRITY.json records final data/authoring guards and a process snapshot. Audit code hashes are in AUDIT_CODE_MANIFEST.json; exact commands/stdout/stderr are in paired49_20261023/audit.

Reproduction is OFFLINE only. The five scripts in AUDIT_CODE_MANIFEST.json build derivatives sequentially: audit census -> raw PIT recheck -> refine -> report -> seal. They use exclusive-create outputs and deliberately refuse to overwrite prior audit evidence. To repeat, use a separate copied audit workspace/output version; do not delete the existing evidence, run archived experiment argv, or invoke a dispatcher. The generation/measurement commands in command_attempts.csv are historical records, not instructions to execute them.

Prior audit parser V1 treated40 non-execution placeholder rows as missing file paths; V2 corrects that classification and retains all40 rows separately. No benchmark results changed. This correction is unrelated to experimental generation retry or measurement policy.
''')
with (O/'SHA256SUMS.txt').open('x',encoding='utf-8') as f:
 for p in sorted(O.iterdir()):
  if p.is_file() and p.name!='SHA256SUMS.txt':f.write(sha(p)+'  '+p.name+'\n')
audit.log('E1_EXECUTION_AUDIT_SEALED',path=str(O),hash_manifest_sha256=sha(O/'SHA256SUMS.txt'),report_sha256=sha(O/'BAO_CAO_TOAN_BO_E1.md'),new_experiments=0,workers=workers)
print(json.dumps({'status':'SEALED','folder':str(O),'protected_files':len(protected),'workers':workers,'inaccessible_processes':inaccessible,'files':len(list(O.iterdir()))},ensure_ascii=False))
