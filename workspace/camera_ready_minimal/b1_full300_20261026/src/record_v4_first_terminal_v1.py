"""Verify both new scheduling paths using immutable completed evidence only."""
import json, sys, urllib.request
from pathlib import Path
from datetime import datetime, timezone
from maven_adapter_v1 import R, sha, dump
from run_maven_b1_v2 import guards
from checkpoint_archive_guard_v2 import verify
from non_junit4_deferral_v1 import inspect, REGISTRY

B=R.parent/'paired49_20261023'
sys.path.insert(0,str(B))
import audit

def load(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))

def main():
    guards(load(R/'admission_maven_v4.json'))
    result=load(R/'jobs/050/result.json')
    check50=verify(R/'jobs/050')
    assert result['sample_index_1based']==50 and result['terminal'] is True
    assert result['source_guard']=='PASS' and result['production_bytecode_guard']=='PASS'
    assert result['measurement_attempted'] and result['strict_suite_evidence'] and result['strict_measurement_evidence']
    assert result['legacy_process_build']==1 and result['focal_mutants']==5 and result['killed_mutants']==1
    assert result['legacy_strict_mutation_percent']==20 and result['GPT_API_calls']==0
    reviews={}
    for i in [48,49]:
        reviews[str(i)]=inspect(R/'jobs'/f'{i:03d}')
        assert reviews[str(i)]==load(REGISTRY/f'{i:03d}.json')
        assert not (R/'jobs'/f'{i:03d}'/'result.json').exists()
    with urllib.request.urlopen('http://127.0.0.1:8766/status.json',timeout=5) as response:
        status=json.load(response)
    assert status['new_API_calls']==0
    at=datetime.now(timezone.utc).isoformat()
    record={'status':'PASS_FIRST_V4_TERMINAL_AND_QUARANTINE_PATHS', 'at_utc':at,
            'previous_verified_new_results':27,'new_verified_terminal_index':50,
            'verified_new_results':28,'verified_reuse49':49,'verified_unscored_deferrals':[48,49],
            'class050_result_sha256':sha(R/'jobs/050/result.json'),'class050_archive_check':check50,
            'class050_result':result,'deferral_checks':reviews,'runtime_observation':status,
            'observation_is_transactional_with_other_files':False,
            'GPT_API_calls':0,'paper_modified':False,'full300_complete':False}
    dump(R/'audit/progress_v9.json',record)
    text=f'''# B1 — checkpoint sau khi đi qua cả hai nhánh v4

Xác minh UTC: {at}. **49 class E1 tái sử dụng +28 kết quả mới =77 class đã kiểm.** Class048 và049 giữ lại chưa chấm;40 Gradle chưa chạy benchmark. E1-full300 chưa hoàn tất; GPT, E0, E49 và paper hiện tại không thay đổi.

## Bằng chứng mới

- Class050 hoàn tất cùng controller/bridge/cách đo v3: build gate pass,2 native test pass, đủ JaCoCo/PIT,1/5 focal mutants killed, mutation20%. Source và production bytecode guards PASS; archive đã kiểm hash và file census. Kết quả này được giữ theo cùng policy, không chọn theo điểm số.
- Class049 gặp đúng môi trường JUnit3 compile scope như048. Đã kiểm lại archive, source, bytecode, hai file native và các lệnh đã kết thúc; receipt khớp. Không có measurement, không có score và không generation lại. Invocation đã đi tiếp class độc lập.
- Như vậy đã quan sát và kiểm cả nhánh terminal measurement và nhánh giữ lại chưa chấm của dispatcher mới.13 kiểm tra admission trước đó PASS; measurement controller, native-JUnit policy và bridge không thay đổi.

## Trạng thái đang chạy

Snapshot runtime UTC: `{status['updated_utc']}`. Phase: `{status['phase']}`; active class: `{status.get('active_sample_index')}`. Preview báo{status['new_completed']} kết quả mới,{status.get('maven_deferred_unscored',0)} class chưa chấm,{status.get('maven_unattempted','?')} Maven chưa thử. Đây là quan sát runtime, có thể thay đổi sau khi ghi file; báo cáo không nghiệm thu archive của class đang chạy.

Invocation đang đi qua danh sách183 class chưa thử được khóa trước khi chạy, worker1, cùng seed/profile/budgets của v3. Không tự retry/resume. Mọi guard khác ngoài trường hợp JUnit3 compile scope đã được khóa đều dừng invocation. Đĩa trống lúc quan sát:{status['disk_free_GB']}GB; giữ ngưỡng12GB và không xóa evidence.

`maven_pending` gồm mọi Maven chưa có kết quả đã chấm: chưa thử, đang chạy, hoặc đang giữ lại. Class chưa chấm vẫn thuộc manifest300; không gán0, không giảm denominator, không dùng E0 lấp vào hoặc tuyên bố NI300. Seed, log, native suite và receipt giữ nguyên để quyết định measurement-only sau này trong sandbox mới nếu đủ căn cứ.

## Ràng buộc và bước tiếp

1. Giữ invocation hiện tại chạy; không mở benchmark hay fixture Java/Gradle đồng thời. Xem completion `runtime/remaining_maven183_v4_completion.json` khi kết thúc; nếu dừng thì audit nguyên nhân trước mọi quyết định mới.
2. Audit cuối invocation: terminal archives, mọi class giữ lại, ordered CP/tools/source/bytecode và GPT/E49 guards. Chưa giải quyết JUnit3 bằng nâng dependency production hoặc đổi provider. Không sửa native suite để vượt license/test gate.
3. Gradle40 vẫn chưa admit.4 launcher chỉ PASS version-only; recipe v4 và native fixture mới qua preparation/pure checks. Queue Gradle cũ đã SKIPPED, không tự khởi động lại. Chỉ qualify fixture sau khi Maven đã nhả lock và không còn tiến trình benchmark.
4. Chỉ chốt phân tích E1-full300 sau nghiệm thu đủ dữ liệu. E0 lịch sử300, E1 bổ sung, fixed49 và giao mới tách rõ; GPT giữ nguyên61/45/300, mẫu RQ1–RQ3 và5RQ. Các thay đổi integration cần được nêu khi giải thích E0→E1; không quy toàn bộ chênh lệch cho assertions.
5. Chưa sửa paper từ dữ liệu đang dở. Giữ giới hạn single-run/repeated chưa hoàn chỉnh; chưa đánh R2.1 toàn300, margin justification, equalized budgets hoặc hybrid fully resolved khi thiếu bằng chứng. Không công khai code, bịa artifact URL hoặc upload/ký/đăng ký/thanh toán.

## File để theo dõi

- [Preview local](http://127.0.0.1:8766/?view=b1-v2): cập nhật runtime, không có nút khởi chạy experiment.5 route HTTP PASS ở checkpoint trước; manifest300/7 public fields, source/audit404. Chưa kiểm render qua browser vì quyền điều khiển browser bị tắt.
- `admission_maven_v4.json`, `launch_remaining_maven183_v4.json`: danh sách, hash và giới hạn invocation hiện tại.
- `NON_JUNIT4_DEFERRAL_V1.md`, `runtime/non_junit4_deferrals_v1/048.json`, `049.json`: phạm vi giữ lại chưa chấm.
- `audit/progress_v9.json`, `audit/progress_registry_v9.json`: dữ liệu/hash checkpoint này. `PROGRESS_B1_V8.md` và các bản trước là snapshot cũ được giữ để audit.

585 file gốc/backup và audit chain PASS; GPT/API mới0. Repeated subset vẫn dừng. Bản camera-ready15 trang hiện có giữ nguyên.
'''
    with (R/'PROGRESS_B1_V9.md').open('x',encoding='utf-8') as f:
        f.write(text)
    paths=[Path(__file__),R/'PROGRESS_B1_V9.md',R/'audit/progress_v9.json',
           R/'admission_maven_v4.json',R/'launch_remaining_maven183_v4.json',
           R/'jobs/050/result.json',R/'jobs/050/artifact_manifest.json',
           REGISTRY/'048.json',REGISTRY/'049.json',R/'NON_JUNIT4_DEFERRAL_V1.md',
           R/'validation/maven_dispatch_v4/result.json',R/'audit/progress_registry_v8.json']
    dump(R/'audit/progress_registry_v9.json',{'files':[{'path':p.relative_to(R).as_posix(),
          'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(set(paths))]})
    audit.log('B1_V4_FIRST_TERMINAL_AND_DEFERRAL_PATHS_VERIFIED',
              registry_sha256=sha(R/'audit/progress_registry_v9.json'),verified_new=28,
              verified_reuse49=49,deferred_unscored=[48,49],GPT_API_calls=0)
    print(json.dumps({'status':record['status'],'verified_total':77,'unscored':[48,49],
                      'runtime_phase':status['phase'],'active':status.get('active_sample_index'),
                      'GPT_API_calls':0},indent=2))

if __name__=='__main__':
    main()
