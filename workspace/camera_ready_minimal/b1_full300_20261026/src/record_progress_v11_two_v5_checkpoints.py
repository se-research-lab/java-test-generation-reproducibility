"""Verify two closed new jobs; no old full-audit repetition or live-job reads."""
import json, sys, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from maven_adapter_v1 import R, sha, dump
from completed_archive_guard_v3 import verify
from measurement_parser_v1 import parse
from run_maven_b1_v2 import guards

B=R.parent/'paired49_20261023'
sys.path.insert(0,str(B))
import audit

def load(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))

guards(load(R/'admission_maven_v5.json'))
checks={}
for i in [67,68]:
    folder=R/'jobs'/f'{i:03d}'
    assert not (folder/'interrupted.json').exists()
    job=load(folder/'job_admission.json')['job']
    result=load(folder/'result.json')
    assert result['terminal'] and result['sample_index_1based']==i and result['GPT_API_calls']==0
    assert result['source_guard']=='PASS' and result['production_bytecode_guard']=='PASS'
    checks[str(i)]={'archive':verify(folder),'result_sha256':sha(folder/'result.json')}
    parsed=parse(folder/'repo'/job['module'],job['focal_class'],job['package'],job['selected_test_fqcn'],result['legacy_process_build'])
    assert all(result.get(k)==v for k,v in parsed.items())
    checks[str(i)]['offline_reparse']='IDENTICAL_FOR_ALL_FIELDS'
    checks[str(i)]['legacy_process_gate']=result['legacy_process_build']
    checks[str(i)]['strict_percent']=result['legacy_strict_mutation_percent']
with urllib.request.urlopen('http://127.0.0.1:8766/status.json',timeout=5) as response:
    status=json.load(response)
assert status['new_API_calls']==0
assert status['runner_liveness'] in {'PRESENT_MATCHED_PID_AND_CREATE_TIME','INVOCATION_COMPLETION_RECORD_PRESENT'}
at=datetime.now(timezone.utc).isoformat()
record={'at_utc':at,'status':'PASS_TWO_CLOSED_V5_CHECKPOINTS','baseline_verified_new':42,
        'additional_verified_indices':[67,68],'verified_new_total':44,'reused_E49':49,'verified_total':93,
        'unscored_deferrals':[48,49],'new_closed_job_checks':checks,'runtime_observation':status,
        'live_job_archives_audited':False,'new_GPT_API_calls':0,'new_Gradle_processes':0,
        'paper_changed':False,'full300_complete':False}
dump(R/'audit/progress_v11.json',record)
text=f'''# B1 — điểm tiếp tục hiện tại

UTC: {at}. **93/300 class có kết quả đã kiểm:49 E1 tái sử dụng +44 Maven mới.** Đã kiểm đầy đủ checkpoint cũ42 class mới và thêm archive/reparse của067,068.048/049 vẫn chưa đo và không có điểm.40 Gradle chưa chạy benchmark. E1-full300 chưa hoàn tất; paper và dữ liệu GPT không đổi.

## Đợt đang chạy

V5 được khóa cho đúng10 class **067,068,069,071,072,074,076,077,078,079**, tuần tự, tối đa10 rồi ghi completion.067/068 đã qua kiểm archive, file census, parser, source/bytecode guards. Runtime đang báo `{status['phase']}`, active `{status.get('active_sample_index')}`, liveness `{status['runner_liveness']}`. Số runtime có thể thay đổi sau snapshot; báo cáo này không đọc hoặc nghiệm thu archive đang mở.

Chưa có completion thì không mở lại v5 hoặc khởi động đợt khác. Khi invocation kết thúc, đọc `runtime/remaining_maven167_v5_completion.json`, đối chiếu từng terminal/deferral và guard trước quyết định mới. Tên file167 chỉ số eligible trước đợt; giới hạn thực của invocation là10.

Giữ nguyên code generation/measurement, profile reviewer, seed, ngân sách và timeout. Ngưỡng đĩa12GB, STOP guard và mọi lỗi integrity giữ nguyên. Không tự retry class theo điểm số hoặc restart sau lỗi; không thêm skip-license, đổi provider hoặc nâng dependency production. Class chưa chạy/chưa chấm không bị gán0 và vẫn thuộc manifest300.

## Đã xử lý trong lần tiếp tục này

- V4/monitor cũ không còn; không có completion hoặc exit code. Nguyên nhân chưa xác định. Không tự khởi động lại chúng.
-066 đã lưu đủ lệnh kết thúc và terminal result, thiếu archive. Đã đối chiếu ledger/hashes/raw reports/source/native/bytecode/dependencies và đóng archive ngoài, không sửa raw folder hoặc chạy lại. Native suite pass, PIT coverage minion lỗi; legacy strict-policy0 được giữ, raw mutation percentage không có.
- Audit cũ đã kiểm gần96.000 file/~1,16GB và585 file gốc/backup/audit chain PASS. Admission v5 tái sử dụng full-audit receipt còn mới, kiểm lại anchors và tiếp tục vào thư mục job mới; không giả rằng bước kiểm anchors là một full rehash khác.
- Preview v3 hoạt động, kiểm PID/create-time/script thay vì chỉ đọc nhãn RUNNING cũ.6 pure checks và8 HTTP checks PASS; manifest300/7 public fields; source/audit404, POST501, foreignHost403. Chưa kiểm render qua browser vì quyền điều khiển bị tắt. Thời điểm kiểm liveness khác thời điểm guard dữ liệu.
- Chỉ chuẩn bị thêm điều kiện cho một fixture Gradle2.13 bằng suite tổng hợp đã lưu:13 guard checks PASS; **chưa admit/chạy queue, fixture hoặc Gradle40**. Queue Gradle cũ vẫn SKIPPED; queue audit v4 cũng chưa được chạy vì thiếu completion. Các source chuẩn bị được giữ để audit; không tự chạy các prototype này.

## Task còn lại

1. Khép và kiểm đợt10 v5; tiếp tục các Maven chưa thử theo thứ tự gốc bằng admission rõ ràng.
2. Giữ048/049 ở hàng chờ. Muốn giải quyết phải có review riêng và ưu tiên measurement-only từ suite đã lưu; không regenerate hoặc nâng JUnit compile scope.
3. Qualify native measurement/provider và generation cho Gradle40, từng wrapper, khi không có benchmark Java khác.4 launcher version-only và pure recipe PASS chưa đủ để admit40.
4. Chỉ chốt E1-full300 sau nghiệm thu đầy đủ. Giữ E0 lịch sử300; fixed49 và giao E1 mới là phân tích riêng, không đổi GPT61/45/300 hoặc mẫu RQ1–RQ3. Giữ5RQ, giới hạn single-run/repeated chưa hoàn chỉnh; không suy NI300 hoặc đánh R2.1/margin/equal budgets/hybrid fully resolved từ cohort chưa đủ.

## File và preview

- [Preview local](http://127.0.0.1:8766/?view=b1-v2).
- [Chi tiết admission, audit066 và ràng buộc v5](PROGRESS_B1_V10.md).
- `admission_maven_v5.json`, `launch_remaining_maven167_v5.json`, `audit/maven_v5_dispatch_only.diff`.
- `audit/absent_v4_runner_reconciliation_v1/result.json` và `job066_recovered_archive.json`.
- `audit/progress_v11.json`, `audit/progress_registry_v11.json`: checks và hashes của snapshot này.
- `runtime/maven_v5_process_launch_v1/` và audit ledger: launch/log. Manifest/hash source được giữ, stdout-stderr đang ghi không được coi là file bất biến.

GPT/API mới0; repeated subset vẫn dừng. Không có Gradle JVM mới trong bước này. Không sửa paper15 trang, công khai code, đặt artifact URL, upload, thanh toán, đăng ký hoặc ký license.
'''
with (R/'PROGRESS_B1_V11.md').open('x',encoding='utf-8') as f:
    f.write(text)
paths=[R/'PROGRESS_B1_V11.md',R/'audit/progress_v11.json',R/'audit/progress_registry_v10.json',
       R/'jobs/067/result.json',R/'jobs/067/artifact_manifest.json',
       R/'jobs/068/result.json',R/'jobs/068/artifact_manifest.json',
       R/'validation/gradle_fixture_after_v5_v1/result.json']
paths+=list((R/'src').glob('*.py'))
dump(R/'audit/progress_registry_v11.json',{'files':[{'path':p.relative_to(R).as_posix(),
     'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(set(paths))]})
audit.log('B1_PROGRESS_V11_TWO_V5_CHECKPOINTS_VERIFIED',registry_sha256=sha(R/'audit/progress_registry_v11.json'),
          verified_total=93,additional_indices=[67,68],new_GPT_API_calls=0,new_Gradle_processes=0)
print(json.dumps({'status':record['status'],'verified_total':93,'phase_observed':status['phase'],
                  'liveness':status['runner_liveness'],'GPT_API_calls':0},indent=2))
