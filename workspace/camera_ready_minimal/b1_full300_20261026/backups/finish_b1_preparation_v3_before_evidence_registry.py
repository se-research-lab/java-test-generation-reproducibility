"""Seal preparation evidence after snapshot/cache completion; never admits benchmark."""
import ast,json,sys,shutil
from pathlib import Path
from datetime import datetime,timezone
R=Path(__file__).resolve().parents[1];B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def dump(p,x):
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x',encoding='utf-8') as f:json.dump(x,f,ensure_ascii=False,indent=2)
def now():return datetime.now(timezone.utc).isoformat()
snap=load(R/'inputs/snapshot_v3/complete.json');cache=load(R/'cache_preparation_v1/complete.json')
assert snap['status']==cache['status']=='PASS' and snap['snapshots']==251
checks={}
for name in ['snapshot_store_v1','snapshot_reader_v2','snapshot_reader_v3','maven_adapter_v1','measurement_parser_v1','process_supervisor_v1','pom_integration_guard_v1','prepare_sandbox_v1']:
 p=R/'validation'/name/'result.json';x=load(p);assert x['status']=='PASS';checks[name]={'status':x['status'],'sha256':audit.sha(p),'path':p.relative_to(R).as_posix()}
fixture=R/'validation/maven_runtime_fixture_v1';runtime=load(fixture/'result.json') if (fixture/'result.json').exists() else ({'status':'FAILED',**load(fixture/'failure.json')} if (fixture/'failure.json').exists() else {'status':'NOT_RUN'})
for x in load(R/'audit/input_lock.json'):assert audit.sha(x['path'])==x['sha256'],x['path']
for registry in ['preparation_registry_v2.json','handoff_registry_v1.json']:
 data=load(R/'audit'/registry)
 for x in data.get('files',data.get('extras',[])):assert audit.sha(R/x['path'])==x['sha256'],x['path']
audit.verify()
import importlib.util
gpath=R.parents[1]/'review_reports/minimal_camera_ready_20261023/guard_rq123_frozen.py';spec=importlib.util.spec_from_file_location('b1finalguard',gpath);g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
assert g.collect()==load(g.LOCK),'GPT frozen data drift'
for p in (R/'src').glob('*.py'):ast.parse(p.read_text(encoding='utf-8'),filename=str(p))
summary={'created_utc':now(),'source_snapshots':snap,'private_cache':cache,'checks':checks,'runtime_fixture':runtime,'GPT_guard':'PASS','originals_guard':'PASS_585','benchmark_admitted':False,'new_benchmark_classes':0,'reused_E49':49,'new_GPT_API_calls':0,'pending_maven_classes':211,'pending_gradle_classes':40,'remaining':['production controller/command admission integration','runtime policy/classpath/bytecode guards for real Maven jobs','Gradle-specific wrapper/JDK/gate/timeout mapping and qualification','full300 final evidence audit after actual execution']}
dump(R/'audit/preparation_stage_v3.json',summary)
before=R/'status.json';backup=R/'backups/status_before_stage_v3.json'
with before.open('rb') as f,backup.open('xb') as t:shutil.copyfileobj(f,t)
s=load(before);s.update(updated_utc=now(),phase='SOURCE + CACHE READY / RUNNER QUALIFICATION',source_snapshot_roots_completed=251,private_cache_status='PASS',GPT_guard='PASS',GPT_guard_checked_utc=now(),runtime_fixture_status=runtime['status'],fixture_EvoSuite_calls=runtime.get('generation_calls',0),disk_free_GB=round(shutil.disk_usage(R).free/1e9,2))
s['new_EvoSuite_calls']=runtime.get('generation_calls',0)
s['tasks'][2]['name']='Source/cache đã khóa; adapter Maven đang qualify';s['tasks'][4]['name']='Pure guards PASS; runtime và controller cần nghiệm thu';s['tasks'][4]['status']='IN_PROGRESS'
s['blockers']=['Hoàn thiện controller Maven và admission cho benchmark','Kiểm đủ guards classpath/bytecode và policy trên job thực','Qualify Gradle theo wrapper/JDK/gate/timeout riêng; chưa chạy40class']
tmp=R/'status.stage_v3.tmp';dump(tmp,s);tmp.replace(before)
lines=['# B1 — source/cache và adapter preparation v3','',f"Snapshot source: **251/251 PASS**; {snap['source_files']:,} file logic, {snap['unique_blobs']:,} blob duy nhất. Mỗi blob đã đọc lại và kiểm SHA-256.",f"Cache Maven riêng: **{cache['files']:,} file / {cache['bytes']:,} byte**, sao chép độc lập và kiểm hash; không hardlink.",'','## Kiểm tra đã hoàn tất','']
for name in checks:lines.append('- '+name+': PASS.')
lines+=['',f"Java runtime fixture: **{runtime['status']}**; số generation calls tổng hợp ghi trong audit, không tính là class benchmark mới.",'','GPT guard PASS;585 originals/backup vẫn nguyên vẹn. E49 raw parser khớp cả49 kết quả và evidence flags.','', '**Chưa admit benchmark251.** Còn controller thực thi và guards trên job thực; Gradle40 có khác biệt wrapper/JDK/framework/gate/timeout cần xử lý riêng. Không sửa paper hoặc dữ liệu RQ1–RQ3.','','Đọc thêm MAVEN_COMPATIBILITY_ADDENDUM_V1.md và audit/gradle_scope_review_v1/REPORT.md. Không tự dùng E0 để lấp E1 thiếu, không tự resume repeated subset.']
(R/'PREPARATION_STATUS_V3.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
paths=list((R/'src').glob('*.py'))+list((R/'adapters').glob('*.py'))+[R/'PREPARATION_STATUS_V3.md',R/'MAVEN_COMPATIBILITY_ADDENDUM_V1.md',R/'audit/preparation_stage_v3.json']
paths+=list((R/'validation').rglob('result.json'))+[R/'inputs/context251_v1/manifest.json',R/'inputs/context251_v1/summary.json',R/'audit/gradle_scope_review_v1/report.json',R/'audit/gradle_scope_review_v1/REPORT.md']
dump(R/'audit/code_and_validation_registry_v3.json',{'created_utc':now(),'files':[{'path':p.relative_to(R).as_posix(),'sha256':audit.sha(p),'bytes':p.stat().st_size} for p in sorted(set(paths))]})
audit.log('B1_PREPARATION_STAGE_V3_COMPLETE',registry_sha256=audit.sha(R/'audit/code_and_validation_registry_v3.json'),snapshot_sha256=audit.sha(R/'inputs/snapshot_v3/complete.json'),cache_sha256=audit.sha(R/'cache_preparation_v1/complete.json'),runtime_fixture=runtime['status'],GPT_guard='PASS',benchmark_admitted=False)
print(json.dumps({k:v for k,v in summary.items() if k not in {'source_snapshots','private_cache','checks'}},indent=2))
