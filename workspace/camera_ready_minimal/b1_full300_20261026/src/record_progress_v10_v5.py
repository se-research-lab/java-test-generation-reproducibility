"""Lightweight live handoff after a complete offline checkpoint audit.
No hashing of growing job trees, experiment, API or manuscript modification.
"""
import json, sys, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from maven_adapter_v1 import R, sha, dump

B=R.parent/'paired49_20261023'
sys.path.insert(0,str(B))
import audit

def load(p):
    return json.loads(Path(p).read_text(encoding='utf-8-sig'))

review=load(R/'audit/absent_v4_runner_reconciliation_v1/result.json')
assert review['status']=='PASS_SAVED_TERMINAL_RECOVERED_NO_RERUN'
admission=load(R/'admission_maven_v5.json')
plan=load(R/'launch_remaining_maven167_v5.json')
assert plan['admission_sha256']==sha(R/'admission_maven_v5.json')
assert plan['max_new_jobs']==admission['invocation_max_new_jobs']==10
assert plan['sample_indices']==[67,68,69,71,72,74,76,77,78,79]
assert plan['prior_scored_classes']==42 and plan['prior_unscored_deferrals']==[48,49]
assert admission['scientific_measurement_changes']==0
old=load(R/'admission_maven_v4.json')
source_names=['maven_controller_v2.py','b1_maven_commands_v3.py','native_junit_policy_candidate_v1.py',
              'process_supervisor_v1.py','classpath_transport_v1.py','measurement_parser_v1.py']
for name in source_names:
    path=R/'src'/name
    assert old['code_and_input_hashes'][str(path)]==admission['code_and_input_hashes'][str(path)]==sha(path)
with urllib.request.urlopen('http://127.0.0.1:8766/status.json',timeout=5) as response:
    observed=json.load(response)
assert observed['new_API_calls']==0
assert observed['runner_liveness'] in {'PRESENT_MATCHED_PID_AND_CREATE_TIME','INVOCATION_COMPLETION_RECORD_PRESENT'}
at=datetime.now(timezone.utc).isoformat()
record={'at_utc':at,'verified_new_terminal_at_admission':42,'verified_reused_E49':49,'verified_total_at_admission':91,
        'saved066_reconciliation_sha256':sha(R/'audit/absent_v4_runner_reconciliation_v1/result.json'),
        'v5_admission_sha256':sha(R/'admission_maven_v5.json'),'v5_launch_plan_sha256':sha(R/'launch_remaining_maven167_v5.json'),
        'v5_max_jobs':10,'v5_indices':plan['sample_indices'],'v5_runner_identity':plan['runner_identity'],
        'runtime_observation':observed,'new_running_archives_verified_here':False,
        'experiment_sources_unchanged':source_names,'new_GPT_API_calls':0,'paper_changed':False,
        'staged_v4_postbatch_audit_queue':'NOT_ADMITTED_NOT_EXECUTED; original v4 completion receipt is absent',
        'full300_complete':False}
dump(R/'audit/progress_v10.json',record)
text=f'''# B1 — checkpoint v5: tiếp tục từ dữ liệu đã đối chiếu

Cập nhật UTC: {at}. **91/300 class có kết quả đã kiểm:49 E1 tái sử dụng +42 Maven mới.** Class048 và049 chưa có điểm; trước đợt này còn167 Maven chưa thử và40 Gradle chưa admit benchmark. E1-full300 chưa hoàn tất. GPT, E0, E49, nămRQ và bản paper15 trang hiện có giữ nguyên.

## Điểm dừng v4 và kết quả audit

Runner v4 và monitor cũ không còn hoạt động; execution session không còn truy cập được, không có completion/exit receipt. Nguyên nhân tiến trình biến mất **chưa xác định từ bằng chứng hiện có**. Không dựng lại exit code hoặc giả rằng v4 đã kết thúc bình thường; không khởi động lại v4.

Class066 đã lưu7 lệnh kết thúc, raw result và terminal event, nhưng thiếu archive cuối. Audit riêng đã đối chiếu global ledger/command hashes/stdout-stderr, profile/seed/timeout/CP, native suite, source, POM integration, dependency JAR và production bytecode, rồi reparse suite/PIT/JaCoCo; đồng thời kiểm41 archive đã hoàn tất và048/049.585 file gốc/backup và audit chain PASS. Audit đọc gần96.000 file/~1,16GB archive, không chạy JVM/API.

066 có native suite pass nhưng PIT coverage minion lỗi `UNKNOWN_ERROR`. Giữ đúng legacy process gate0/strict-policy0 của lần đã thực thi; raw mutation percentage không có. Đây không phải mutation percentage quan sát được0%. Không sửa flags, provider, nguồn test hoặc tăng timeout để lấy điểm khác; không chạy lại generation/measurement.

Archive066 được đóng riêng tại `audit/absent_v4_runner_reconciliation_v1/job066_recovered_archive.json`; raw folder066 và result cũ không đổi. Guard mới chỉ nhận trường hợp066 đã đối chiếu này khi archive gốc thiếu; mọi class khác thiếu archive vẫn dừng để review. Receipt và archive ngoài được pin trong admission v5.

## Đợt Maven hiện tại

- Danh sách cố định: **067,068,069,071,072,074,076,077,078,079**, là10 class đầu trong167 class chưa thử theo original order. Worker1, tối đa10 class rồi ghi completion; không tự mở đợt sau hoặc tự restart sau lỗi.
- Controller measurement v2, bridge v3, native-JUnit policy, process supervisor, CP-file transport và parser giữ đúng hash đã khóa. Reviewer profile, seed `20261023 + index`, search60s, generation timeout240s, Maven measurement300s, dependency audit180s và một conditional technical retry tối đa giữ nguyên. Thay đổi chỉ ở điều phối/checkpoint/preview.
- Full byte audit vừa hoàn tất được tái sử dụng qua receipt mới không quá15 phút khi admit/start, cùng kiểm lại manifest/result/event/native anchors. Bước này không được mô tả như rehash toàn bộ archive thêm lần nữa. New jobs và mọi deferral mới vẫn qua kiểm đầy đủ trước checkpoint. Không ghi vào old job folders.
- Guard JUnit3 compile scope chỉ giữ lại chưa chấm khi đủ điều kiện đã khóa; class vẫn thuộc300. Không gán0 cho class chưa đo, không hạ denominator hoặc dùng E0 lấp E1 còn thiếu.048/049 không được regenerate hoặc nâng dependency production.

Runtime quan sát lúc `{observed['updated_utc']}`: `{observed['phase']}`, active `{observed.get('active_sample_index')}`; liveness `{observed['runner_liveness']}`. Runtime báo{observed['new_completed']} kết quả mới, còn{observed.get('maven_unattempted','?')} Maven chưa thử. Đây là snapshot đang chạy, chưa nghiệm thu thêm raw archives trong báo cáo này.

## Preview và log

[Preview local](http://127.0.0.1:8766/?view=b1-v2) đã mở lại bằng server v3. Backend kiểm đúng PID/create-time/script của runner v5; khi không xác minh được tiến trình thì đánh dấu cần review thay cho lấy trạng thái RUNNING từ file cũ. Liveness không phải kiểm hash dữ liệu liên tục; thời điểm guard input phản ánh guard thật ở boundary, khác thời điểm đọc preview.

6 kiểm tra liveness thuần và8 kiểm tra HTTP PASS. Manifest300 dòng/7 public fields; source/audit404, POST501, foreignHost403. Chưa kiểm render bằng browser vì quyền điều khiển browser bị tắt. Monitor chỉ đọc; không có endpoint khởi chạy experiment.

File chính:

- `admission_maven_v5.json`, `validation/maven_v5_dispatch_preparation_v1/result.json`, `audit/maven_v5_dispatch_only.diff`.
- `launch_remaining_maven167_v5.json`: actual runner PID/create-time/script và10 indices đã khóa; tên file167 là số class eligible trước đợt, **không phải167 job được mở trong đợt10 này**.
- `runtime/remaining_maven167_v5_completion.json` sẽ có khi invocation kết thúc; phải đọc file này và audit trước khi quyết định continuation mới.
- `runtime/maven_v5_process_launch_v1/`: plan/started/stdout-stderr của wrapper; chi tiết generation/measurement trong từng `jobs/<index>/commands/` và audit ledger.
- `audit/absent_v4_runner_reconciliation_v1/result.json`, `job066_recovered_archive.json`: bằng chứng thu nhận066 không rerun.
- `audit/progress_v10.json`, `audit/progress_registry_v10.json`: snapshot và hashes bàn giao. Các bản trước được giữ nguyên, không phải trạng thái live.

## Task còn lại và giới hạn

|Mức|Việc|Điều kiện|
|---|---|---|
|P0|Khép đợt10 bằng completion, giữ mọi failure và audit log|Không tự retry/restart; guard/STOP/disk reserve12GB giữ nguyên|
|P0|Giải quyết048/049 bằng quyết định riêng|Ưu tiên dùng native suite đã lưu; không nâng compile dependency hoặc đổi provider khi chưa đủ căn cứ|
|P1|Tiếp tục các Maven chưa thử theo original order|Giữ nguyên cấu hình đo, không chọn class/score thuận lợi|
|P1|Qualify native measurement và generation cho Gradle40|4 launcher chỉ PASS version-only; recipe v4/fixture mới ở preparation. Không chạy Java fixture đồng thời benchmark|
|P2|Audit E1-full300, phân tích fixed49/toàn bộ/giao mới riêng|Giữ E0 toàn300; GPT61/45/300 không bị thay bởi giao mới; không suy NI300 từ49 hoặc cohort chưa đủ|
|P3|Cập nhật paper/response trong15 trang|Chưa dùng kết quả dang dở; giữ5RQ/single-run, chưa có repeated variance đầy đủ; R2.1/margin/equal budgets/hybrid không đánh fully resolved khi thiếu bằng chứng|

Queue Gradle cũ đã SKIPPED và không được restart. Source queue audit v4 mới chuẩn bị trong bước kiểm tra ban đầu **chưa được admit hoặc chạy**, vì v4 không có completion receipt; giữ source để audit, không tự chạy nó. Không có Gradle benchmark/fixture mới trong bước này.

GPT/API mới0, repeated subset vẫn dừng. Không công khai code, đặt artifact URL giả, upload, đăng ký, thanh toán hoặc ký license. Không dùng log vận hành dang dở để đổi paper/RQ hoặc lựa chọn kết quả.
'''
with (R/'PROGRESS_B1_V10.md').open('x',encoding='utf-8') as f:
    f.write(text)
paths=[R/'PROGRESS_B1_V10.md',R/'audit/progress_v10.json',R/'admission_maven_v5.json',
       R/'launch_remaining_maven167_v5.json',R/'validation/maven_v5_dispatch_preparation_v1/result.json',
       R/'audit/maven_v5_dispatch_only.diff',R/'audit/absent_v4_runner_reconciliation_v1/result.json',
       R/'audit/absent_v4_runner_reconciliation_v1/job066_recovered_archive.json',
       R/'validation/monitor_v3_preparation_v1/result.json',R/'validation/monitor_v3_http_v1/result.json',
       R/'runtime/monitor_v3_launch_v1/plan.json',R/'runtime/monitor_v3_launch_v1/started.json',
       R/'runtime/maven_v5_process_launch_v1/plan.json',R/'runtime/maven_v5_process_launch_v1/started.json',
       R/'monitor/serve_v3.py']
paths+=list((R/'src').glob('*.py'))+list((R/'backups').glob('*draft*.py'))
dump(R/'audit/progress_registry_v10.json',{'files':[{'path':p.relative_to(R).as_posix(),
     'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(set(paths))]})
audit.log('B1_PROGRESS_V10_V5_HANDOFF_RECORDED',registry_sha256=sha(R/'audit/progress_registry_v10.json'),
          verified_at_admission=91,max_new_jobs=10,runner_identity=plan['runner_identity'],GPT_API_calls=0)
print(json.dumps({'status':'PASS_V5_ADMISSION_AND_LIVE_OWNER_HANDOFF','verified_at_admission':91,
                  'max_jobs':10,'observed_active_index':observed.get('active_sample_index'),
                  'liveness':observed['runner_liveness'],'GPT_API_calls':0},indent=2))
