"""Record verified frozen-input decisions and a read-only runtime observation."""
import json,sys,urllib.request,urllib.error
from pathlib import Path
from datetime import datetime,timezone
from maven_adapter_v1 import R,sha,dump
from run_maven_b1_v2 import guards
from pom_input_deferral_policy_v1 import verify_fixed_set, EXPECTED

B=R.parent/'paired49_20261023'
sys.path.insert(0,str(B))
import audit

def load(p):
    return json.loads(Path(p).read_text(encoding='utf-8-sig'))

lock=load(R/'admission_maven_v6.json')
guards(lock)
assert verify_fixed_set()==EXPECTED
plan=load(R/'launch_remaining_maven153_v6.json')
assert plan['admission_sha256']==sha(R/'admission_maven_v6.json')
assert plan['max_new_jobs']==153 and len(plan['sample_indices'])==153
assert plan['sample_indices']==sorted(set(plan['sample_indices']))==lock['continuation_indices']
assert set(plan['sample_indices']).isdisjoint(lock['existing_unscored_deferrals'])
assert 49+46+12+153+40==300
review=load(R/'audit/pom_input_deferrals_v2/result.json')
assert review['status']=='PASS_READONLY_FROZEN_POM_REVIEW'
assert review['unparseable_indices']==EXPECTED and len(review['new_terminal_archive_checks'])==4
assert load(R/'runtime/gradle_native_after_v5_v1/state.json')['state']=='SKIPPED_BOUNDED10_NOT_CLEANLY_COMPLETE'
http=[]
status=None
for route,expected in [('/',200),('/status.json',200),('/manifest.json',200),
                        ('/jobs/072/pom_before_integration.xml',404),('/audit/',404),('/src/',404)]:
    try:
        with urllib.request.urlopen('http://127.0.0.1:8766'+route,timeout=5) as response:
            code=response.status
            body=response.read()
    except urllib.error.HTTPError as ex:
        code=ex.code
        body=ex.read()
    assert code==expected
    http.append({'route':route,'status':code})
    if route=='/status.json':
        status=json.loads(body)
    if route=='/manifest.json':
        rows=json.loads(body)
        assert len(rows)==300 and all(set(r)=={'sample_index_1based','class_key','repo_id','focal_class','build_tool','seed','status'} for r in rows)
        assert all(next(r for r in rows if r['sample_index_1based']==i)['status']=='INTERRUPTED_REVIEW_REQUIRED' for i in lock['existing_unscored_deferrals'])
for label,request,expected in [
    ('POST disabled',urllib.request.Request('http://127.0.0.1:8766/',data=b'',method='POST'),501),
    ('foreign Host denied',urllib.request.Request('http://127.0.0.1:8766/',headers={'Host':'untrusted.invalid'}),403)]:
    try:
        with urllib.request.urlopen(request,timeout=5) as response:
            code=response.status
    except urllib.error.HTTPError as ex:
        code=ex.code
    assert code==expected
    http.append({'check':label,'status':code})
assert status['new_API_calls']==0 and status['runner_invocation_version']=='v6'
assert status['runner_liveness'] in {'PRESENT_MATCHED_PID_AND_CREATE_TIME','INVOCATION_COMPLETION_RECORD_PRESENT'}
at=datetime.now(timezone.utc).isoformat()
record={'status':'PASS_V6_ADMISSION_FIXED300_AND_HTTP','at_utc':at,'verified_reused_E49':49,
        'verified_new_at_admission':46,'verified_total_at_admission':95,
        'unscored_indices':lock['existing_unscored_deferrals'],'unscored_JUnit_compile_scope':[48,49],
        'unscored_frozen_POM_XML':EXPECTED,'new_invocation_indices':plan['sample_indices'],'new_invocation_max_jobs':153,
        'Gradle_unattempted':40,'runtime_observation':status,'http_checks':http,
        'raw_live_job_archives_not_read':True,'render_QA_performed':False,
        'new_GPT_API_calls':0,'paper_changed':False,'full300_complete':False,
        'staged_Gradle_component_queue':'Executed once; SKIPPED because bounded10 parent ended exit1 before10; no Gradle JVM started'}
dump(R/'audit/progress_v12.json',record)
text=f'''# B1 — tiếp tục153 Maven độc lập, giữ12 class chưa chấm

Snapshot UTC: {at}. **95/300 class có kết quả đã nghiệm thu:49 E1 tái sử dụng +46 Maven mới.** Có12 class chưa chấm,153 Maven chưa thử trước invocation mới và40 Gradle chưa admit benchmark. Tổng danh mục vẫn300. **E1-full300 chưa hoàn tất; chưa sửa paper hoặc kết luận RQ từ dữ liệu đang dở.**

## V5 dừng ở đâu và đã nghiệm thu gì

V5 có completion receipt thật `exit_code:1`, bốn class terminal067/068/069/071, dừng ở072 trước Java do POM không parse được. Bốn terminal archives đã qua kiểm file census/hash; mọi failure được giữ.069 lỗi generation với thông báo bytecode major65 trong dependency analysis; không đổi JDK, nâng EvoSuite hoặc lọc thêm classpath để tìm kết quả tốt hơn. Điểm policy0 của lần đã thực thi không phải một mutation percentage đã quan sát được.

Queue Gradle2.13 mới được mở đúng một lần để chờ bounded10 sạch; đã `SKIPPED_BOUNDED10_NOT_CLEANLY_COMPLETE` vì V5 dừng sau4 class. **Không có Gradle fixture/JVM hoặc generation mới từ queue này.** Không restart queue cũ hoặc dùng việc mở queue làm bằng chứng đã qualify Gradle.

## Mười POM lỗi trong frozen input

Đã đọc POM focal module của163 Maven chưa có kết quả từ content-addressed SQLite chỉ đọc, kiểm manifest/blob hashes; phát hiện đúng10 class Vaadin bị `unbound prefix: line 2, column 0`: **072,112,119,163,173,211,220,269,275,294**.153 POM còn lại parse được. Census không materialize repo mới hoặc chạy Java.

POM072 trong job khớp byte/SHA256 snapshot; source toàn repo khớp baseline trước integration; không có commands/target/native generation/measurement. Backup do controller ghi bằng text mode khác newline LF→CRLF nhưng nội dung XML giống; ghi riêng hash và không khẳng định backup byte-identical. Audit v1 đã dừng vì kiểm nhầm raw-byte equality của backup; source/log/folder đó được giữ. Audit v2 sửa phép đối chiếu newline, PASS; không sửa input hoặc thực nghiệm.

Lỗi hiện diện trong **prepared-input snapshot**, không phải bằng chứng upstream/pristine commit bị lỗi và chưa xác định thao tác lịch sử tạo ra nó. Việc bật assertions không tạo lỗi POM này. Không phục hồi POM từ một workspace khác, sửa namespace, dependency hoặc business source trong bước hiện tại.

Receipt từng class đặt ở `runtime/pom_input_deferrals_v1/`.072 có archive lần dừng; chín class còn lại chỉ có bằng chứng preflight frozen input, **không giả làm job đã chạy**. Tất cả chưa có score, giữ trong manifest300 và không giảm denominator. Chi tiết ở [POM input review](audit/pom_input_deferrals_v2/REPORT.md).

## Hai class JUnit3

048/049 giữ nguyên suite đã sinh và archive, chưa measurement, không có điểm. JUnit3 nằm trong production compile closure, bên cạnh Jupiter test dependencies. Không nâng JUnit compile scope hoặc đổi provider. Policy missing-JUnit/E49 JUnit4-test-scope không bao trùm hai trường hợp này; cần review compatibility riêng. Không regenerate test.

## Invocation v6 hiện tại

- Một invocation **tối đa153** class Maven chưa thử có POM parse được, thứ tự original manifest, worker1, bắt đầu074. Code generation/measurement v2/bridge v3, tools, parser và native-JUnit policy giữ nguyên hash; reviewer assertions/scaffolding/runtime, search60s, generation timeout240s, Maven measurement300s, dependency audit180s, seed gốc và conditional retry giữ nguyên.
- V6 chỉ thay điều phối: nhận receipt fixed-input chưa chấm, giữ đủ300 khi đếm, pin manifests/results/receipts đã nghiệm thu và tạo thư mục job mới. Không mô tả việc kiểm anchors là một full byte rehash khác. New job archives vẫn được kiểm toàn bộ trước checkpoint.
- Không chạy lại V5,072,066 hoặc class có score cũ. Không tự resume invocation sau lỗi hoặc ngưỡng đĩa12GB. Các lỗi integrity/guard khác tiếp tục dừng; không tự sửa dependency/source để vượt gate. Không sinh GPT, chạy lại repeated subset hoặc chạy Gradle đồng thời.

Runtime lúc `{status['updated_utc']}`: `{status['phase']}`, active `{status.get('active_sample_index')}`, liveness `{status['runner_liveness']}`. Preview báo{status['new_completed']} kết quả mới,{status['maven_deferred_unscored']} chưa chấm,{status['maven_unattempted']} Maven chưa thử. Các số này là quan sát runtime, có thể đổi sau snapshot; báo cáo không nghiệm thu raw archive đang ghi.

## Ràng buộc với reviewer và RQ

|Hạng mục|Việc đang làm/đã có|Giới hạn cần giữ|
|---|---|---|
|R1.2/R2.3: paired49|Giữ E49 đã xác minh và phân tích theo fixed49|Giao E1 mới không thay mẫu GPT gốc|
|R2.1: bật assertions/runtime/scaffolding|Mở rộng E-only vào phần Maven độc lập|Chưa fully resolved toàn300; còn12 class chưa chấm +40 Gradle và nhiều class đang chạy|
|R2.2: Gradle|Metadata/cache/launcher đã qualify; native fixture còn chờ|Không gọi version-only PASS là benchmark qualification; giữ Maven260 sensitivity riêng|
|RQ1–RQ3|GPT từng class và mẫu61/45/300,298 artifacts+2 no-API rows giữ khóa|Không chạy thêm API hoặc remeasure GPT; không dùng giao mới thay mẫu|
|RQ4/RQ5|Chưa kết luận từ E1 chưa đủ; giữ failures thật theo policy gốc|Không gán0 cho unattempted/unscored; không NI300 từ49 hoặc loại12 class|
|R1.7/R2.5|Repeated subset vẫn dừng|Chưa có repeated evaluation hoàn chỉnh; giữ single-run và variance chưa định lượng|
|Margin/budgets/hybrid|Giữ giới hạn bằng chứng hiện có|Không đổi protocol để bảo toàn thứ hạng cũ; không đánh fully resolved khi thiếu chứng cứ|

Reviewer muốn bổ sung cấu hình EvoSuite và phân tích công bằng; điều này không đòi đổi dữ liệu GPT hoặc cả nămRQ. Kết quả E1 có thể thay đổi thực sự; không chỉnh harness theo chiều giữ kết luận. Không quy mọi E0→E1 khác biệt chỉ cho assertions vì integration/configuration cũng khác. Bài hiện tại và response chỉ cập nhật khi có bộ kết quả được nghiệm thu và phạm vi rõ ràng.

## Task và mức ảnh hưởng

|Ưu tiên|Task tiếp theo|Chạy gì|Rủi ro/cổng|
|---|---|---|---|
|P0|Hoàn tất hoặc đóng an toàn invocation v6|153 Maven E-only chưa thử|Guard/hash/archive từng class; STOP/disk reserve; không retry theo điểm|
|P0|Review12 môi trường chưa hỗ trợ|Analytic trước; chưa có job repair mới|Không POM/JUnit repair hoặc score0 mặc định; amendment riêng nếu cần|
|P1|Qualify Gradle native provider/JaCoCo/PIT và generation|Fixture tổng hợp sau khi Maven nhả khóa, rồi admission riêng cho40|Không chạm G0/shared cache; kiểm runtime/compile closure, seeds/budgets/target|
|P2|Audit và sensitivity cuối|Analytic trên raw accepted data|E0 toàn300/E1/fixed49/giao mới tách rõ; giữ denominator|
|P3|Chốt paper/response15 trang|Chỉ biên tập sau nghiệm thu|Giữ5RQ; metadata6 tác giả/Chi sole corresponding; chưa upload hoặc công khai code|

## Preview và file tiếp tục

[Preview local](http://127.0.0.1:8766/?view=b1-v2) dùng server v4, chỉ đọc; xác minh owner v5/v6 bằng PID/create-time/script và plan/admission hashes.6 pure-owner checks và8 HTTP checks PASS; manifest300 dòng/7 fields; source/audit404, POST501, foreignHost403. Chưa kiểm browser render vì quyền điều khiển browser bị tắt. Giờ liveness khác giờ guard dữ liệu; không gọi guard là giám sát hash liên tục.

- `admission_maven_v6.json`, `launch_remaining_maven153_v6.json`: scope,153 indices, owner và hashes.
- `runtime/remaining_maven153_v6_completion.json` chỉ xuất hiện khi invocation kết thúc; không tự chạy lại script nếu file chưa có, phải kiểm owner và log.
- `audit/maven_v6_dispatch_only.diff`, `validation/maven_v6_dispatch_preparation_v1/result.json`.
- `audit/pom_input_deferrals_v2/`: census163,10 lỗi và kiểm archive mới; `runtime/pom_input_deferrals_v1/`: receipt chưa chấm.
- `audit/progress_v12.json`, `audit/progress_registry_v12.json`: checkpoint và hashes. Các bản trước giữ nguyên, không phải trạng thái live.
- `runtime/maven_v6_process_launch_v1/`, từng `jobs/<index>/commands/` và ledger serialized: log/argv/returncode/hash; không công khai qua web.

585 file gốc/backup, audit chain, GPT/E49 guards PASS. GPT/API mới0. Bản paper15 trang không đổi; không công khai code, bịa artifact URL, upload, đăng ký, thanh toán hoặc ký license.
'''
with (R/'PROGRESS_B1_V12.md').open('x',encoding='utf-8') as f:
    f.write(text)
paths=[R/'PROGRESS_B1_V12.md',R/'audit/progress_v12.json',R/'admission_maven_v6.json',
       R/'launch_remaining_maven153_v6.json',R/'validation/maven_v6_dispatch_preparation_v1/result.json',
       R/'audit/maven_v6_dispatch_only.diff',R/'audit/pom_input_deferrals_v2/result.json',
       R/'audit/pom_input_deferrals_v2/REPORT.md',R/'audit/pom_input_deferrals_v2/manifest.json',
       R/'runtime/remaining_maven167_v5_completion.json',R/'runtime/gradle_native_after_v5_v1/state.json',
       R/'validation/monitor_v4_preparation_v1/result.json',R/'monitor/serve_v4.py',
       R/'runtime/monitor_v4_launch_v1/plan.json',R/'runtime/monitor_v4_launch_v1/started.json',
       R/'runtime/maven_v6_process_launch_v1/plan.json',R/'runtime/maven_v6_process_launch_v1/started.json']
paths+=list((R/'src').glob('*.py'))+list((R/'runtime/pom_input_deferrals_v1').glob('*.json'))
dump(R/'audit/progress_registry_v12.json',{'files':[{'path':p.relative_to(R).as_posix(),
     'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(set(paths))]})
audit.log('B1_PROGRESS_V12_V6_FIXED300_AND_HTTP_VERIFIED',registry_sha256=sha(R/'audit/progress_registry_v12.json'),
          verified_total_at_admission=95,fixed_unscored=12,max_new_jobs=153,HTTP_checks=len(http),
          new_GPT_API_calls=0,paper_changed=False)
print(json.dumps({'status':record['status'],'verified_at_admission':95,'unscored':12,
                  'max_new_Maven_jobs':153,'observed_active':status.get('active_sample_index'),
                  'liveness':status['runner_liveness'],'HTTP_checks':len(http),'GPT_API_calls':0},indent=2))
