"""Check a new deferred record and write an observed, scoped B1 handoff.
No process/experiment/measurement is started, stopped or modified here.
"""
import json,sys,urllib.request
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from maven_adapter_v1 import R,sha,dump
from run_maven_b1_v2 import guards

B=R.parent/'paired49_20261023'
sys.path.insert(0,str(B))
import audit

def load(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))

guards(load(R/'admission_maven_v6.json'))
row=load(R/'runtime/non_junit4_deferrals_v1/128.json')
folder=R/'jobs/128'
job=load(folder/'job_admission.json')['job']
assert row['sample_index_1based']==128 and row['class_key']==job['class_key']
assert row['seed']==job['seed']==20261151
assert row['score'] is None and row['measurement_attempted'] is False
assert row['retained_in_fixed300_manifest'] is True and row['denominator_may_be_reduced'] is False
assert row['rerun_generation_allowed'] is False
assert sha(folder/'artifact_manifest.json')==row['archive_sha256']
assert sha(folder/'interrupted.json')==row['interruption_sha256']
assert sha(folder/'before_dependency.json')==row['dependency_evidence_sha256']
assert not (folder/'result.json').exists()
dependency=load(folder/'before_dependency.json')
selected=[r for r in dependency['classpath'] if r['path'].startswith('junit/junit/')]
assert len(selected)==1 and selected[0]['path']=='junit/junit/3.8.1/junit-3.8.1.jar'
compilecp={r['path']:r['sha256'] for r in dependency['compile_classpath']}
assert compilecp[selected[0]['path']]==selected[0]['sha256']==sha(selected[0]['absolute_path'])
for native in row['native_suite']:
    assert sha(native['path'])==native['sha256']
commands=[]
starts=0
for p in sorted((folder/'commands').glob('*/plan.json')):
    plan=load(p)
    finished=load(p.parent/'finished.json')
    assert (p.parent/'started.json').exists() and finished['returncode']==0
    assert 'org.pitest:pitest-maven:mutationCoverage' not in plan['argv']
    assert 'verify' not in plan['argv']
    starts+=int('-jar' in plan['argv'])
    assert sha(p.parent/'stdout.txt')==finished['stdout_sha256']
    assert sha(p.parent/'stderr.txt')==finished['stderr_sha256']
    commands.append({'command':p.parent.name,'returncode':finished['returncode'],'plan_sha256':sha(p)})
assert starts==row['actual_generation_starts']==1
logged=[e for e in audit.events() if e['kind']=='B1_V6_UNSCORED_COMPATIBILITY_DEFERRAL' and e.get('sample_index')==128]
assert len(logged)==1 and logged[0]['evidence']==row
assert logged[0]['receipt_sha256']==sha(R/'runtime/non_junit4_deferrals_v1/128.json')

with urllib.request.urlopen('http://127.0.0.1:8766/status.json',timeout=5) as response:
    status=json.load(response)
assert status['runner_invocation_version']=='v6'
assert status['runner_liveness'] in {'PRESENT_MATCHED_PID_AND_CREATE_TIME','INVOCATION_COMPLETION_RECORD_PRESENT'}
assert status['new_API_calls']==0 and 128 in status['deferred_sample_indices']
sample=load(R/'audit/runtime_stability_v2/result.json')
assert sample['assessment']=='RUNNING_NO_HANG_EVIDENCE_IN_OBSERVATION'
capacity=sample['capacity']
assert capacity['sufficient_even_for_source_only'] is True
at=datetime.now(timezone.utc)
record={'status':'PASS_V6_CONTINUATION_ANCHORS_AND_RESOURCE_OBSERVATION','at_utc':at.isoformat(),
        'new128_deferral_checks':{'receipt_sha256':sha(R/'runtime/non_junit4_deferrals_v1/128.json'),
             'archive_manifest_anchor':'PASS','dependency_JUnit3_compile_scope':'PASS','native_suite_hashes':'PASS',
             'command_evidence':commands,'serialized_ledger_receipt_match':'PASS',
             'full128_repo_byte_census_repeated_here':False},
        'runtime_observation':status,'runtime_terminal_records_including_reuse49':49+status['new_completed'],
        'unscored_indices':status['deferred_sample_indices'],
        'resource_diagnostic_sha256':sha(R/'audit/runtime_stability_v2/result.json'),
        'storage_intervention_by_this_agent':False,'reason_for_external_free_space_increase':'NOT_ESTABLISHED',
        'preview_label_correction_sha256':sha(R/'audit/preview_deferral_label_v1.json'),
        'config_changes':0,'new_GPT_API_calls':0,'new_EvoSuite_calls_by_this_diagnostic':0,
        'new_Gradle_jobs':0,'paper_changed':False,'full300_complete':False}
dump(R/'audit/progress_v14.json',record)
local=at.astimezone(ZoneInfo('Asia/Bangkok')).strftime('%d/%m/%Y %H:%M:%S')
text=f'''# B1 — batch vẫn tiến triển, dung lượng đã thay đổi

Cập nhật **{local} (UTC+7)**. Runtime hiện có **{49+status['new_completed']}/300 terminal records**, gồm49 E1 tái sử dụng và{status['new_completed']} Maven mới. Active snapshot:`{status.get('active_sample_index')}`; phase:`{status['phase']}`; owner:`{status['runner_liveness']}`. Đây là số runtime và các checkpoint runner đã đóng; chưa phải audit toàn cohort cuối hoặc E1-full300 hoàn chỉnh.

## Vận hành hiện tại

Chẩn đoán v2 lấy hai mẫu cách nhau{sample['samples_seconds_apart']:.1f}s, kiểm owner PID/create-time/script, command intervals và resource metadata. Không có lệnh quá timeout+grace hoặc dispatcher command chồng nhau trong lịch sử quan sát. V6 đã đóng{sample['v6_closed_terminal_records_seen']} terminal records lúc chẩn đoán, tốc độ quan sát{sample['throughput_classes_per_hour_observed']:.1f} class/giờ; không phải ETA hoặc bảo đảm ổn định về sau. Chi tiết [runtime stability v2](audit/runtime_stability_v2/REPORT.md).

Runtime failure của subject được giữ theo policy, không tự rerun. `Unsupported class file major version65` tiếp tục xuất hiện ở một số class thuộc dependency analysis của AWS SDK; không nâng JDK/EvoSuite hoặc lọc thêm dependency để cải thiện outcome. Các lỗi này không tự đồng nghĩa runner bị treo. Không dùng tỷ lệ pass/fail hiện tại để thay kết luận paper.

## Dung lượng: cảnh báo cũ cần được cập nhật

Đĩa trống khi lấy mẫu mới:{capacity['free_bytes']/1e9:.2f}GB. Giữ reserve12GB thì còn dùng được{capacity['usable_before_guard_bytes']/1e9:.2f}GB; source tối thiểu chưa materialize:{capacity['remaining_source_bytes_lower_bound']/1e9:.2f}GB cho{capacity['pending_not_materialized']} class. Sau source-only còn{capacity['minimum_headroom_after_source_only_bytes']/1e9:.2f}GB cho build/report/cache/log.

Vì thế đánh giá cũ “chưa đủ ngay cả source trước reserve” **không còn đúng tại mẫu mới**. Build/report/log chưa được tính nên vẫn chưa bảo đảm đủ cho tất cả phần còn lại. Ngưỡng12GB giữ nguyên. Tôi chưa xóa, di chuyển, nén hoặc deduplicate evidence/cache; nguyên nhân dung lượng tăng từ khoảng15,65GB lên21,10GB chưa được xác định từ dữ liệu hiện có. Không quy việc tăng dung lượng cho một thao tác dọn của agent.

Không cần can thiệp lưu trữ để tiếp tục ở thời điểm này. Nếu disk guard chạm ngưỡng, dừng có kiểm soát và audit trước mọi quyết định; không tự hạ reserve hoặc xóa bằng chứng.

## Thêm class128 chưa chấm

128 (`AgentServerVersionsChecker`, repo44308560) có đúng JUnit3.8.1 trong production compile closure. Đã generation một lần, lưu native suite,5 lệnh trước measurement kết thúc thành công; guard dừng trước nâng JUnit/measurement. Không có score/result measurement. Receipt khớp global serialized ledger; archive-manifest, interruption, dependency JAR, native suite và command-log hashes khớp trong lần kiểm này.

Đây là kiểm anchors và receipt của full check mà runner đã thực hiện lúc quarantine; **không giả làm một full byte census của repo128 khác**. Không chạy lại generation/measurement hoặc thay dependency/provider.

Tổng hiện có **{status['maven_deferred_unscored']} class chưa chấm**: JUnit3 compile scope048/049/128; POM lỗi trong snapshot072/112/119/163/173/211/220/269/275/294. Mọi class vẫn thuộc manifest300, không gán0 hoặc giảm denominator. Future deferrals phải tiếp tục qua guard hẹp đã khóa; không có catch-all tự bỏ qua lỗi.

Nhãn blocker trên preview từng ghi cố định12 trong khi counter đã là13. Đã sửa **riêng hiển thị** để lấy số nguyên thực từ status. Backup HTML/hash trước-sau và HTTP receipt được lưu ở `audit/preview_deferral_label_v1.json`. Không sửa raw status, runner, metric hoặc denominator, không restart process. Browser render chưa kiểm vì quyền điều khiển browser bị tắt.

## Bước tiếp theo theo phạm vi đã khóa

1. Để invocation v6 đi tiếp các Maven chưa thử theo original order, worker1, cùng config/seed/budget. Không mở lại class đã chạy, tự retry hoặc tự restart khi guard fail. Đọc completion thật trước mọi continuation khác.
2. Giữ13 class chưa chấm trong hàng chờ review compatibility riêng. Không sửa namespace POM/JUnit compile scope hoặc lấy E0/G0 lấp chỗ trống. Ưu tiên dùng native suite đã lưu nếu về sau được admit measurement-only; chưa mở bước đó.
3. Gradle40 chưa admit; không chạy fixture/benchmark Java đồng thời Maven. Queue Gradle cũ đã SKIPPED; không tự kích hoạt lại. Chỉ qualifier mới sau khi Maven idle và audit scope đầy đủ.
4. Chỉ chốt analytic/paper sau nghiệm thu đủ phạm vi. Giữ E0 lịch sử300, fixed49 và giao E1 mới tách rõ, giữ GPT61/45/300 và5RQ. Không NI300 hoặc fully-resolved R2.1/margin/equalized budgets/hybrid từ cohort đang dở. Single-run/repeated evaluation chưa hoàn chỉnh vẫn nêu trung thực.

585 file gốc/backup, audit chain, code/input pins, GPT/E49 guards PASS trong lần kiểm hiện tại. GPT/API mới0; repeated subset và paper15 trang không đổi. Không công khai code, đặt artifact URL giả, upload, đăng ký, thanh toán hoặc ký license.

## File và preview

- [Preview local](http://127.0.0.1:8766/?view=b1-v2): chỉ đọc, không có endpoint khởi chạy experiment.
- `admission_maven_v6.json`, `launch_remaining_maven153_v6.json`: scope153 và owner; `runtime/remaining_maven153_v6_completion.json` sẽ có khi kết thúc.
- `audit/runtime_stability_v2/`: hai mẫu, command history, capacity lower bound, spot-check một closed archive nhỏ; chẩn đoán v1 được giữ như snapshot cũ.
- `audit/progress_v14.json`, `audit/progress_registry_v14.json`: kiểm128, trạng thái quan sát và hashes bàn giao.
- `PROGRESS_B1_V12.md`, `PROGRESS_B1_V13.md`: các quyết định và checkpoint trước, không phải trạng thái live.
'''
with (R/'PROGRESS_B1_V14.md').open('x',encoding='utf-8') as f:
    f.write(text)
paths=[Path(__file__),R/'PROGRESS_B1_V14.md',R/'audit/progress_v14.json',R/'audit/runtime_stability_v2/manifest.json',
       R/'audit/runtime_stability_v2/result.json',R/'audit/runtime_stability_v2/REPORT.md',
       R/'audit/preview_deferral_label_v1.json',R/'monitor/dist_v2/index.html',
       R/'backups/monitor_index_before_dynamic_deferral_label_v1.html',
       R/'runtime/non_junit4_deferrals_v1/128.json',folder/'artifact_manifest.json',folder/'interrupted.json',
       R/'admission_maven_v6.json',R/'launch_remaining_maven153_v6.json',
       R/'src/prepare_runtime_stability_v2.py',R/'src/assess_runtime_stability_v2.py',
       R/'src/correct_preview_deferral_label_v1.py']
dump(R/'audit/progress_registry_v14.json',{'files':[{'path':p.relative_to(R).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size}
                                              for p in sorted(set(paths))]})
audit.log('B1_PROGRESS_V14_RUNNING_DEFERRAL128_ANCHORS_CHECKED',registry_sha256=sha(R/'audit/progress_registry_v14.json'),
          runtime_total=49+status['new_completed'],unscored_count=status['maven_deferred_unscored'],
          agent_storage_intervention=False,experiment_changes=0,new_GPT_API_calls=0)
print(json.dumps({'status':record['status'],'runtime_total':49+status['new_completed'],
                  'active':status.get('active_sample_index'),'unscored':status['maven_deferred_unscored'],
                  'free_GB_at_sample':capacity['free_bytes']/1e9,'headroom_after_source_GB':capacity['minimum_headroom_after_source_only_bytes']/1e9,
                  'GPT_API_calls':0},indent=2))
