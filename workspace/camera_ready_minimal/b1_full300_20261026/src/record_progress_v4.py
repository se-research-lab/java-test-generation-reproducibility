"""Close this implementation stage with fresh immutable-data checks; no execution admission."""
import json,sys,shutil,importlib.util
from pathlib import Path
from datetime import datetime,timezone
R=Path(__file__).resolve().parents[1];B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def dump(p,x):
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x',encoding='utf-8') as f:json.dump(x,f,ensure_ascii=False,indent=2)
for row in load(R/'audit/code_and_validation_registry_v3.json')['files']:assert audit.sha(R/row['path'])==row['sha256'],row['path']
for row in load(R/'audit/input_lock.json'):assert audit.sha(row['path'])==row['sha256'],row['path']
audit.verify();p=R.parents[1]/'review_reports/minimal_camera_ready_20261023/guard_rq123_frozen.py';spec=importlib.util.spec_from_file_location('v4gptguard',p);g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g);assert g.collect()==load(g.LOCK)
runtime=load(R/'validation/maven_runtime_fixture_v1/result.json');assert runtime['status']=='PASS' and runtime['generation_calls']==1
assert not list((R/'jobs').glob('*/result.json')) if (R/'jobs').exists() else True
old=R/'status.json';backup=R/'backups/status_before_progress_v4.json'
with old.open('rb') as f,backup.open('xb') as t:shutil.copyfileobj(f,t)
s=load(old);s.update(updated_utc=datetime.now(timezone.utc).isoformat(),phase='INPUTS READY / SYNTHETIC MAVEN PASS / CONTROLLER PENDING',new_EvoSuite_calls=1,fixture_EvoSuite_calls=1,new_completed=0,running=0,benchmark_admitted=False,GPT_guard='PASS',GPT_guard_checked_utc=datetime.now(timezone.utc).isoformat())
s['tasks'][2]['name']='Snapshot/cache đủ251; adapter Maven + fixture PASS, controller còn chờ'
s['tasks'][4]['name']='Các guards và fixture Maven PASS; cần nghiệm thu controller thực'
s['blockers']=['Nối production controller với dependency/effective-POM/bytecode guards','Qualify controller thực; kiểm58class có runtime config và framework khác JUnit4','Gradle40: khóa wrapper/JDK/gate/timeout và test discovery riêng']
tmp=R/'status.progress_v4.tmp';dump(tmp,s);tmp.replace(old)
paths=[R/'PROGRESS_B1_V4.md',Path(__file__),R/'src/b1_maven_commands_v1.py',R/'src/validate_b1_maven_commands_v1.py',R/'src/review_frozen_inputs251_v1.py',R/'validation/b1_maven_commands_v1/result.json',R/'audit/frozen_inputs251_review_v1/rows.json',R/'audit/frozen_inputs251_review_v1/summary.json',backup]
registry={'created_utc':s['updated_utc'],'files':[{'path':p.relative_to(R).as_posix(),'sha256':audit.sha(p),'bytes':p.stat().st_size} for p in paths],'GPT_guard':'PASS','originals_585':'PASS','benchmark_admitted':False,'new_benchmark_class_count':0,'fixture_EvoSuite_calls':1,'GPT_API_calls':0}
dump(R/'audit/progress_registry_v4.json',registry);audit.log('B1_PROGRESS_V4',registry_sha256=audit.sha(R/'audit/progress_registry_v4.json'),GPT_guard='PASS',benchmark_admitted=False,fixture_EvoSuite_calls=1,new_benchmark_classes=0)
print(json.dumps({k:v for k,v in registry.items() if k!='files'},indent=2))
