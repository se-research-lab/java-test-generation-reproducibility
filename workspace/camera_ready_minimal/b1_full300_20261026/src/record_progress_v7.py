"""Verified idle handoff for B1v3; never launches a benchmark or API."""
import json,msvcrt,sys,shutil,urllib.request,urllib.error
from pathlib import Path
from datetime import datetime,timezone
from maven_adapter_v1 import R,sha,dump
from run_maven_b1_v3 import guards,project,counters,RECOVER,selected_result
from checkpoint_archive_guard_v2 import verify
B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
with (R/'runtime/dispatcher.lock').open('r+b') as mutex:
 mutex.seek(0);msvcrt.locking(mutex.fileno(),msvcrt.LK_NBLCK,1)
 try:
  guards(load(R/'admission_maven_v3.json'));rows=[];archive_checks={};pending=[]
  jobs=load(R/'manifest300.json')
  for j in jobs:
   i=j['sample_index_1based'];base=R/'jobs'/f'{i:03d}'
   if not (base/'result.json').exists():continue
   archive_checks[str(i)]=verify(base);chosen=selected_result(i);out=chosen.parent
   unresolved=i in RECOVER and (not (R/RECOVER[i]/'result.json').exists() or (R/RECOVER[i]/'interrupted.json').exists())
   if unresolved:pending.append(i)
   if chosen!=base/'result.json':archive_checks[chosen.parent.name]=verify(chosen.parent)
   result=load(chosen)
   rows.append({'index':i,'class_key':j['class_key'],'selected_result':chosen.relative_to(R).as_posix(),'selected_sha256':sha(chosen),'transport_recovery_pending':unresolved,'build_gate':result['legacy_process_build'],'strict_percent':result['legacy_strict_mutation_percent'],'killed':result['killed_mutants'],'focal_mutants':result['focal_mutants'],'suite_evidence':result['strict_suite_evidence'],'measurement_evidence':result['strict_measurement_evidence']})
  assert project('VERIFIED_CHECKPOINT_V7')
  planned,started,fixtures=counters();at=datetime.now(timezone.utc).isoformat();free=shutil.disk_usage(R).free
  http=[]
  for route,expected in [('/',200),('/status.json',200),('/manifest.json',200),('/jobs/012/result.json',404),('/audit/',404)]:
   try:
    with urllib.request.urlopen('http://127.0.0.1:8766'+route,timeout=5) as response:status=response.status;body=response.read()
   except urllib.error.HTTPError as error:status=error.code;body=error.read()
   assert status==expected
   if route=='/manifest.json':
    public=json.loads(body);assert len(public)==300 and all(set(x)=={'sample_index_1based','class_key','repo_id','focal_class','build_tool','seed','status'} for x in public)
   http.append({'path':route,'status':status})
  state={'at_utc':at,'terminal_new_classes':len(rows),'accepted49':49,'pending_transport_recovery':pending,'new_classes_accepted_under_v3':len(rows)-len(pending),'Maven_unattempted':211-len(rows),'Gradle_unattempted':40,'generation_commands_planned':planned,'actual_benchmark_EvoSuite_starts':started,'actual_fixture_EvoSuite_starts':fixtures,'new_GPT_API_calls':0,'original585_GPT_E49_guards':'PASS','disk_free_bytes':free,'class_results':rows,'archive_checks':archive_checks,'http_checks':http,'visual_QA':'not repeated: browser control disabled','Gradle_launcher_check':load(R/'validation/gradle_versions_qualification_v1/complete.json')['status'],'Gradle_recipe_v3':load(R/'validation/gradle_native_recipe_v3/result.json')['recipe_status'],'full300_complete':False,'paper_modified':False}
  dump(R/'audit/progress_v7.json',state)
  table='\n'.join('|'+ '|'.join(map(str,[x['index'],x['build_gate'],x['strict_percent'],f"{x['killed']}/{x['focal_mutants']}",x['measurement_evidence'],'chờ recovery' if x['transport_recovery_pending'] else 'terminal']))+'|' for x in rows)
  text=f'''# B1 — checkpoint v3 đã xác minh

Cập nhật UTC: {at}. Đã có **49 class E1 tái sử dụng + {len(rows)} class mới có terminal record**. Trong số class mới, {len(rows)-len(pending)} đã có kết quả theo policy v3; recovery còn chờ: {pending}. Còn {211-len(rows)} Maven chưa thử và40 Gradle chưa chạy benchmark. **E1-full300 chưa hoàn tất; paper hiện tại chưa sửa.**

## Những phần đã triển khai và kiểm

- Maven v3 đã khóa ở `admission_maven_v3.json`: giữ profile/seed/budgets E49, native JUnit amendment có điều kiện và classpath-file khi lệnh vượt giới hạn Windows.
- Fixture classpath dài PASS:33.133 xuống745 UTF-16 units,1 generation tổng hợp,6/6 focal mutants killed; source, native suite, bytecode và input hashes đều PASS. Fixture không thuộc300 class hoặc repeated evaluation.
- Lệnh fixture tiếp tục chạy sau lần ngắt giao diện và được thu nhận từ log đã có; không khởi động lại fixture đó.
- Bốn launcher Gradle2.13/5.2.1/6.9.4/8.14.4 PASS trên JDK8u172, offline/cache riêng. Đây chỉ là kiểm launcher; chưa đủ native provider, JaCoCo/PIT hoặc generation Gradle.
- Recipe Gradle v3 mới qua kiểm thuần Python: ràng buộc sandbox, giữ thứ tự classpath và legacy exact-focal target, kế thừa tài nguyên/process gate của task gốc, cho hai lệnh đo dùng lại đúng sealed configuration. Receipt chỉ nói cấu hình, không giả làm bằng chứng thực thi. Chưa runtime-qualified.
- Snapshot251 và cache riêng được giữ. GPT,585file gốc/backup, E49 và audit chain PASS. Không thay code/paper cũ; mọi phiên bản cũ và log lỗi còn nguyên.

## Kết quả từng class đã có record

|Index gốc|Build gate|Strict%|Killed/all focal|Đủ measurement evidence|Trạng thái|
|---|---:|---:|---:|---|---|
{table}

Strict0 khi thiếu report/focal mutant không phải một mutation percentage quan sát được0%. Build gate và suite/measurement evidence được giữ riêng theo policy đã khóa; không tạo thangP/C hoặc loại class thất bại.

## Ba lỗi launch Windows và cách xử lý

012,016,023 có lệnh quá dài và không có Java process start ở lần ban đầu. Có14 generation plans nhưng11 process starts trước recovery; một class có hai technical attempts theo policy E49. Không cộng ba launch failure thành ba lần search đã thực hiện.

Quy tắc recovery được chốt trong `measurement_result_map_v3.json` trước khi biết generation outcome của ba class: giữ source/bytecode giống lần lỗi, giữ ordered CP và mọi dependency hash ngoài đường dẫn sandbox mới, cùng seed/options/budgets; chỉ đổi transport sang `CP_file_path`. Kết quả recovery được dùng bất kể score, không lấy max hoặc tự chạy lại class đã search chỉ vì điểm thấp. Initial result và archive vẫn giữ.

012 và023 đã khởi động được EvoSuite và sinh native suite, nhưng measurement bị license-header check của dự án chặn.016 timeout generation240s và được dừng theo owned process tree, không đổi timeout. Ba kết quả strict0 được giữ; không sửa header của native test hoặc tự thêm skip-license. Đây là failure của pipeline; không quy thành năng lực oracle hoặc model.

Tại checkpoint này có{planned} generation commands được lập và{started} benchmark EvoSuite process starts; fixture tổng hợp:{fixtures}. **GPT/API mới:0.** Các counter là số tiến trình thực và kế hoạch, không phải số class độc lập hoặc repeated-run sample size.

## Preview và audit

V2 hoàn tất10 class trong invocation nhưng lỗi ở lần replace file snapshot cuối do Windows sharing. Đã kiểm đủ13 archive, backup và giữ nguyên file.tmp/log cũ. V3 dùng temp độc quyền, backup/hash, bounded retry và log lỗi UI riêng; lỗi I/O preview không tự chuyển thành failure của generation. Manifest runtime chỉ chứa7 trường public; source và audit route trả404. HTTP checks PASS, chưa kiểm lại render vì browser control bị tắt.

Preview: http://127.0.0.1:8766/?view=b1-v2 . `status.json` là trạng thái runtime; báo cáo này là snapshot và không tự cập nhật. Đĩa trống:{free/1e9:.2f}GB; runner giữ ngưỡng12GB và không xóa evidence.

## Task tiếp theo và giới hạn phạm vi

1. **P0:** hoàn tất recovery cố định và tiếp tục Maven theo original order; giữ mọi failure, không thay flags để cải thiện score. Integrity mismatch dừng unscored và không tự resume.
2. **P1 Gradle:** audit lịch sử xác nhận10 GPT build thành công và10 PIT CSV;6 report có killing-test xác nhận owner,4 report zero có mutant nhưng chưa thể xác nhận owner chỉ bằng killing-test. CSV không cho biết engine version. Báo cáo tại `audit/gradle_g0_measurement_v1/REPORT.md`. Giữ đúng target FQCN của Gradle gốc, không tự thêm nested targets; đối chiếu miền mutant quan sát được độc lập với trạng thái killed trước quality claim. Tiếp tục fixture build/native provider/PIT/JaCoCo từng wrapper; khóa engine/agent thực tế và gate/timeout900. Audit resource/ignoreFailures/enabled của native task so với original test; giữ hooks locale, generated sources và dependencies nghiệp vụ. Prototype và launcher PASS chưa cấp admission40.
3. **P2 analytic:** chỉ sau300 terminal+audit mới phân tích E1 toàn300, Maven260, fixed49 và giao E1 mới riêng. GPT giữ nguyên từng class và các mẫu61/45/300; giao mới không thay mẫu RQ1–RQ3. Không dùng E0 lấp E1 chưa chạy, không suy NI300 từ49.
4. **P3 paper/response:** giữ5RQ, E0 lịch sử300 và E1 bổ sung rõ ràng. Các sửa harness làm E0→E1 có thêm yếu tố integration; không khẳng định chỉ assertions gây ra chênh lệch. Giữ giới hạn single-run/chưa có variance hoàn chỉnh; R1.7/R2.5 chưa được repeated evaluation giải quyết. Margin5pp, equalized budgets, hybrid và R2.1 toàn300 không đánh fully resolved khi thiếu bằng chứng.

Bản camera-ready15 trang và package hiện có vẫn giữ nguyên. Chưa công khai code, chưa đặt artifact URL, chưa upload/ký/đăng ký hoặc thanh toán.
'''
  with (R/'PROGRESS_B1_V7.md').open('x',encoding='utf-8') as f:f.write(text)
  with (R/'README_CURRENT.md').open('x',encoding='utf-8') as f:f.write('# Điểm tiếp tục B1\n\nBáo cáo mới nhất: [PROGRESS_B1_V7.md](PROGRESS_B1_V7.md). Đây là checkpoint; trạng thái đang chạy xem [preview local](http://127.0.0.1:8766/?view=b1-v2).\n\nDùng admission/dispatcher Maven v3. V1/v2 và các báo cáo cũ được giữ để audit; không tự chạy lại các preparation, fixture hoặc batch cũ. Measurement map v3 kế thừa map v2 cho003 và chỉ recovery12/16/23 theo quy tắc đã khóa. Repeated subset và GPT vẫn dừng. Gradle40 chưa được admit benchmark; recipe mới nhất là gradle_native_recipe_v3.py, còn cần runtime fixture.\n')
  paths=[R/'PROGRESS_B1_V7.md',R/'README_CURRENT.md',R/'NEXT_STEPS_B1_V2.md',R/'WINDOWS_CP_TRANSPORT_AMENDMENT_V3.md',R/'audit/gradle_g0_measurement_v1/REPORT.md',R/'audit/gradle_g0_measurement_v1/result.json',R/'audit/progress_v7.json',R/'admission_maven_v3.json',R/'measurement_result_map_v3.json']
  paths+=list((R/'src').glob('*.py'))
  paths+=[R/'validation/long_classpath_fixture_v1/validation_result.json',R/'validation/gradle_versions_qualification_v1/complete.json',R/'validation/gradle_native_recipe_v3/result.json',R/'cache_preparation_gradle_v1/recovery_v2/complete.json',R/'audit/projection_reconciliation_v2/result.json']
  dump(R/'audit/progress_registry_v7.json',{'files':[{'path':p.relative_to(R).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(set(paths))]})
  audit.log('B1_PROGRESS_V7_VERIFIED',registry_sha256=sha(R/'audit/progress_registry_v7.json'),new_terminal=len(rows),pending_recovery=pending,actual_benchmark_starts=started,fixture_starts=fixtures,GPT_API_calls=0)
  print(json.dumps({k:v for k,v in state.items() if k not in ['class_results','archive_checks','http_checks']},ensure_ascii=False,indent=2))
 finally:mutex.seek(0);msvcrt.locking(mutex.fileno(),msvcrt.LK_UNLCK,1)
