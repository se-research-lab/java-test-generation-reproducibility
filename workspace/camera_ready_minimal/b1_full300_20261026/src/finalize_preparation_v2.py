"""Recover metadata-only backup, check locked inputs, and record real preflight state."""
import ast,hashlib,json,shutil,sys,subprocess,urllib.request,urllib.error
from pathlib import Path
from datetime import datetime,timezone
R=Path(__file__).resolve().parents[1];B=R.parent/'paired49_20261023'
sys.path.insert(0,str(B));import audit
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def dump(p,x):
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x',encoding='utf-8') as f:json.dump(x,f,ensure_ascii=False,indent=2)
def now():return datetime.now(timezone.utc).isoformat()
backups=[]
rels=['src/e49_driver.py','src/run_e49_supplement.py','src/replay_fixed49_measurement_v5.py','src/diagnose_e1_compatibility_v4.py','src/analyze_e49_final_v2.py','src/junit_method_inventory_v1.py','evo_patch/working/AgoneTest/mavenLib.py','evo_patch/working/AgoneTest/evosuite_profile.py']
for rel in rels:
 src=B/rel;dst=R/'backups/accepted49_adapter'/rel;assert src.is_file(),src
 existed=dst.exists()
 if not existed:
  dst.parent.mkdir(parents=True,exist_ok=True)
  with src.open('rb') as f,dst.open('xb') as out:shutil.copyfileobj(f,out)
 assert audit.sha(src)==audit.sha(dst),str(src)
 backups.append({'original':str(src),'backup':str(dst),'sha256':audit.sha(src),'preexisting_partial_backup':existed})
dump(R/'audit/adapter_backup_manifest_v2.json',backups)
census=load(R/'audit/source_census_v1.json');jobs=load(R/'manifest300.json')
summary={'timestamp_utc':now(),'class_count':sum(len(x['class_indices']) for x in census),'unique_candidate_roots':len(census),'candidate_files':sum(x['file_count'] for x in census),'candidate_bytes':sum(x['bytes'] for x in census),'candidate_GB':round(sum(x['bytes'] for x in census)/1e9,3),'backup_adapter_files':len(backups),'disk_free_GB':round(shutil.disk_usage(R).free/1e9,2),'scope':'metadata census, descriptor hashes and adapter backup; no complete source snapshot or execution adapter yet','new_experiment_calls':0,'recovery':'v1 metadata census completed, adapter backup stopped at wrong helper basename. v2 verified existing copies and backed up correct junit_method_inventory_v1.py; v1 script/error retained.'}
assert summary['class_count']==251
dump(R/'audit/source_census_summary_v2.json',summary)
gradle={}
for j in jobs:
 if j['build_tool']!='gradle':continue
 root=j['source_candidate']['source_repo'];entry=next(x for x in census if x['source_repo']==root)
 g=gradle.setdefault(j['repo_id'],{'class_indices':[],'descriptor_evidence':{},'status':'NOT_QUALIFIED'})
 g['class_indices'].append(j['sample_index_1based'])
 for d in entry['build_descriptors']:
  g['descriptor_evidence'].setdefault(d['path']+'#'+d['sha256'],d)
dump(R/'audit/gradle_readiness_inventory_v1.json',gradle)
for x in load(R/'audit/input_lock.json'):assert audit.sha(x['path'])==x['sha256'],x['path']
audit.verify()
guard=R.parents[1]/'review_reports/minimal_camera_ready_20261023/guard_rq123_frozen.py'
p=subprocess.run([sys.executable,'-B','-X','utf8',str(guard)],capture_output=True,encoding='utf-8');assert p.returncode==0,p.stderr
g= json.loads(p.stdout);assert g['status']=='PASS';dump(R/'audit/GPT_guard_after_preparation_v2.json',g)
for p in list((R/'src').glob('*.py'))+[R/'monitor/serve.py']:ast.parse(p.read_text(encoding='utf-8'),filename=str(p))
qa={}
for path,expected in [('/',200),('/status.json',200),('/manifest.json',200),('/src/source_census_v1.py',404),('/audit/input_lock.json',404),('/../Reviewer.txt',404)]:
 try:
  with urllib.request.urlopen('http://127.0.0.1:8766'+path) as response:code=response.status
 except urllib.error.HTTPError as error:code=error.code
 assert code==expected,(path,code);qa[path]=code
req=urllib.request.Request('http://127.0.0.1:8766/',headers={'Host':'untrusted.invalid'})
try:urllib.request.urlopen(req);raise AssertionError('Host guard did not reject')
except urllib.error.HTTPError as error:assert error.code==403;qa['foreign_host']=403
req=urllib.request.Request('http://127.0.0.1:8766/',data=b'',method='POST')
try:urllib.request.urlopen(req);raise AssertionError('POST unexpectedly accepted')
except urllib.error.HTTPError as error:assert error.code==501;qa['POST']=501
dump(R/'audit/monitor_http_checks_v1.json',{'checked_utc':now(),'results':qa,'browser_check':'Verified rendered counters, Gradle filter40, page26-40, reset300 using browser UI; experiment-control routes absent'})
old=R/'status.json';backup=R/'backups/status_before_preparation_v2.json'
with old.open('rb') as f,backup.open('xb') as out:shutil.copyfileobj(f,out)
s=load(old);s['updated_utc']=now();s['phase']='PREFLIGHT / ADAPTER PREPARATION';s['source_census']=summary;s['GPT_guard_checked_utc']=now();s['disk_free_GB']=summary['disk_free_GB']
s['blockers']=['Hoàn tất snapshot source và adapter E-only mới','Qualify adapter Maven tương thích E49 trên fixture tổng hợp','Qualify Gradle: classpath, runtime/scaffold và JUnit/TestNG discovery','Pass negative guards, stop/recovery và kiểm tra dung lượng']
names=['Khóa 300 keys và phạm vi E-only','Xác minh E49 và GPT guard','Inventory + backup xong; snapshot/adapter Maven còn chờ','Qualify Gradle 40 class, chỉ trong sandbox E','Fixture, negative guards và admission','Chạy 251 class mới, tuần tự, giữ failures','Audit 300 và phân tích RQ4/RQ5 riêng']
for i,t in enumerate(s['tasks']):t['name']=names[i]
s['tasks'][2]['status']='IN_PROGRESS'
temp=R/'status.preparation_v2.tmp';dump(temp,s);temp.replace(old)
event={'timestamp_utc':now(),'kind':'B1_PREPARATION_V2_COMPLETE','data':summary,'benchmark_admitted':False}
with (R/'events.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(event,ensure_ascii=False)+'\n')
files=[]
for p in sorted(R.rglob('*')):
 if p.is_file() and p.name not in {'status.json','events.jsonl'} and 'monitor_http_access' not in p.name:
  files.append({'path':p.relative_to(R).as_posix(),'sha256':audit.sha(p),'bytes':p.stat().st_size})
dump(R/'audit/preparation_registry_v2.json',{'created_utc':now(),'files':files,'mutable_projections':['status.json','events.jsonl'],'benchmark_admitted':False})
audit.log('B1_PREPARATION_V2',stage=str(R),summary=summary,GPT_guard=g,registry_sha256=audit.sha(R/'audit/preparation_registry_v2.json'),benchmark_admitted=False)
print(json.dumps(summary,ensure_ascii=False,indent=2))
