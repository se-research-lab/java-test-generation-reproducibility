"""Freeze a verified idle checkpoint; no benchmark or API generation."""
import json,sys,shutil,msvcrt,urllib.request,urllib.error
from datetime import datetime,timezone
from pathlib import Path
from maven_adapter_v1 import R,dump,sha
from checkpoint_archive_guard_v2 import verify
from run_maven_b1_v2 import guards,project
B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
def load(p):return json.loads(p.read_text(encoding='utf-8'))
checks={};rows=[]
with (R/'runtime/dispatcher.lock').open('r+b') as mutex:
 msvcrt.locking(mutex.fileno(),msvcrt.LK_NBLCK,1)
 try:
  guards(load(R/'admission_maven_v2.json'))
  for out in sorted((R/'jobs').glob('[0-9][0-9][0-9]')):
   assert (out/'result.json').exists(),'Incomplete checkpoint'
   checks[out.name]=verify(out);r=load(out/'result.json')
   if out.name=='003':r=load(R/'jobs/003_native_junit_diagnostic_v3/diagnostic_result.json')
   rows.append({'index':int(out.name),'class_key':load(out/'result.json')['class_key'],'gate':r['legacy_process_build'],'strict_percent':r['legacy_strict_mutation_percent'],'focal_mutants':r['focal_mutants'],'killed_mutants':r['killed_mutants'],'suite_evidence':r['strict_suite_evidence'],'measurement_evidence':r['strict_measurement_evidence'],'generation_calls':load(out/'result.json')['generation_calls'],'measurement_result':str((R/'jobs/003_native_junit_diagnostic_v3/diagnostic_result.json' if out.name=='003' else out/'result.json').relative_to(R))})
  checks['003_native_junit_diagnostic_v3']=verify(R/'jobs/003_native_junit_diagnostic_v3')
  project('CHECKPOINT_VERIFIED_AMENDMENT_V2')
  http=[]
  for path,status,host,method in [('/',200,None,'GET'),('/status.json',200,None,'GET'),('/manifest.json',200,None,'GET'),('/audit/',404,None,'GET'),('/jobs/003/result.json',404,None,'GET'),('/../protocol.json',404,None,'GET'),('/',403,'example.com','GET'),('/',501,None,'POST')]:
   request=urllib.request.Request('http://127.0.0.1:8766'+path,method=method,headers={'Host':host} if host else {})
   try:
    with urllib.request.urlopen(request,timeout=5) as response:observed=response.status;body=response.read()
   except urllib.error.HTTPError as error:observed=error.code;body=error.read()
   assert observed==status,(path,observed,status)
   if path=='/manifest.json':
    manifest=json.loads(body);assert len(manifest)==300;assert all(set(x)=={'sample_index_1based','class_key','repo_id','focal_class','build_tool','seed','status'} for x in manifest)
   http.append({'path':path,'host':host,'method':method,'status':observed})
  stamp=datetime.now(timezone.utc).isoformat();free=shutil.disk_usage(R).free
  report={'at_utc':stamp,'scope':'verified checkpoint; full300 incomplete','new_terminal_classes':len(rows),'accepted49':49,'Maven_remaining':211-len(rows),'Gradle_unattempted':40,'new_generation_benchmark':sum(x['generation_calls'] for x in rows),'generation_synthetic_fixtures':2,'GPT_API_calls':0,'original585_guard':'PASS','GPT_guard':'PASS','accepted49_guard':'PASS','disk_free_bytes':free,'rows':rows,'archives':checks,'monitor_HTTP_checks':http,'monitor_visual_check':'Unavailable this turn: local browser use disabled in Work settings','Gradle_metadata_status':load(R/'inputs/gradle40_context_v2/summary.json')['status']}
  dump(R/'audit/progress_v5.json',report)
  table='\n'.join('|'+ '|'.join(map(str,[x['index'],x['gate'],x['strict_percent'],str(x['killed_mutants'])+'/'+str(x['focal_mutants']),x['suite_evidence'],x['measurement_evidence']]))+'|' for x in rows)
  text=f'''# B1 — checkpoint đã xác minh, 26/10/2026

Đã có49class E1 được tái sử dụng và{len(rows)}class mới terminal. Còn{211-len(rows)}Maven và40Gradle chưa hoàn tất. **Chưa có E1-full300 hoặc kết luận mới cho paper.**

## Kết quả checkpoint

|Index gốc|Build gate|Strict mutation%|Killed/all focal mutants|Suite evidence|Measurement evidence|
|---|---:|---:|---:|---|---|
{table}

Điểm strict0 khi không có focal mutant/report là quy tắc zero-fill đã khóa; không được diễn giải thành mutation strength quan sát được0% hoặc tự loại class khỏi mẫu. Không báo compiled-only median/NI300 từ checkpoint này.

003 dùng lại nguyên suite và seed, bổ sung JUnit4 test scope sau generation; initial measurement failure vẫn giữ tại `jobs/003/result.json`. Map thay thế measurement được khóa ở `measurement_result_map_v2.json`; diagnostic không tính thêm class hoặc generation. Quyết định amendment được lập sau khi biết kết quả003 và ghi rõ thời điểm, không mô tả như prespecified. Xem `MAVEN_NATIVE_JUNIT_AMENDMENT_V2.md`.

Hai class mới tiếp theo chạy bằng controller v2, đúng thứ tự gốc, không chọn lại outcome. Mọi original source/dependency nghiệp vụ, native bytes và production bytecode đều qua guard; failure thật vẫn được giữ. Archive có census đầy đủ và hash; lỗi thứ tự log/archive của v1 được giải trình bằng kiểm prefix+đúng một terminal append, v2 ghi terminal trước archive.

## Ràng buộc đã kiểm

- GPT giữ61/45/300,298artifacts+2preprocessing rows;0API request mới. Repeated subset vẫn dừng.
-585file gốc/backup, audit chain, E49 và registry paper PASS. Không sửa paper/PDF/ZIP hiện tại hoặc code thực nghiệm gốc.
- Số generation benchmark:{sum(x['generation_calls'] for x in rows)}; fixture tổng hợp:2. Các diagnostic chỉ đo suite đã có, không phải repeated-run evaluation.
- Cache Maven riêng và source snapshot251 đã hash; E49 không bị ghi lại. Disk trống tại checkpoint:{free/1e9:.2f}GB; runner dừng khi dưới12GB.
- PreviewHTTP và giới hạn route/Host/method PASS. Browser control bị tắt trong Work settings nên chưa kiểm lại render phiên bản này; không gọi HTTP test là visualQA.

## Gradle40 và công việc tiếp

Đã xác minh40mapping từ frozenmetadata/snapshot, gồm wrapper2.13 trong module41627638; supplement ở `inputs/gradle40_context_v2/`. Không nâng version từ suy đoán. Có4wrapper2.13/5.2.1/6.9.4/8.14.4, Java metadata1.8. Còn phải chuẩn bị cache riêng theo diskbudget, supervisor riêng, generationCP đầy đủ, nativeJUnit/TestNG discovery và gate/timeout900 theo legacy. Chưa chạy Gradle hoặc gán0 cho40class này.

Tiếp tục Maven trong invocation có giới hạn và giữ originalorder; dừng unscored nếu integrity/coverage audit thiếu. MetadataJUnit5 chưa chứng minh provider runtime; đọc suite/PIT/JaCoCo từngclass. Chỉ sau full300 terminal và finalaudit mới phân tích fixed49, Maven260, toàn300 và tập giao E1 mới riêng. GPT mẫu gốc và5RQ giữ khóa.

ReviewerR2.1 chưa fullyresolved cho full300; repeatedvariance, margin justification, equalizedbudgets và hybrid chưa có thêm bằng chứng. Bổ sung Gradle/harness có thể ảnh hưởng E1, không quy toàn bộ chênh E0→E1 cho assertions.

Snapshot này:{stamp}. Trạng thái đang chạy về sau xem `status.json` và dashboard; báo cáo này không tự cập nhật.
'''
  with (R/'PROGRESS_B1_V5.md').open('x',encoding='utf-8') as f:f.write(text)
  paths=[R/'PROGRESS_B1_V5.md',R/'audit/progress_v5.json',Path(__file__),R/'audit/gradle40_independent_review_v1.md',R/'inputs/gradle40_context_v2/manifest.json',R/'inputs/gradle40_context_v2/summary.json',R/'src/prepare_gradle_metadata_v2.py',R/'audit/maven_amendment_v2_independent_review.md',R/'admission_maven_v2.json',R/'measurement_result_map_v2.json',R/'MAVEN_NATIVE_JUNIT_AMENDMENT_V2.md']
  paths+=list((R/'src').glob('*native_junit*.py'))+[R/'src/checkpoint_archive_guard_v1.py',R/'src/checkpoint_archive_guard_v2.py',R/'src/maven_controller_v2.py',R/'src/run_maven_b1_v2.py',R/'src/admit_maven_b1_v2.py']
  dump(R/'audit/progress_registry_v5.json',{'files':[{'path':p.relative_to(R).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(set(paths))]})
  audit.log('B1_PROGRESS_CHECKPOINT_V5',registry_sha256=sha(R/'audit/progress_registry_v5.json'),new_terminal=len(rows),GPT_API_calls=0,remaining_Maven=211-len(rows),remaining_Gradle=40)
  print(json.dumps({k:v for k,v in report.items() if k not in ['rows','archives','monitor_HTTP_checks']},indent=2))
 finally:mutex.seek(0);msvcrt.locking(mutex.fileno(),msvcrt.LK_UNLCK,1)
