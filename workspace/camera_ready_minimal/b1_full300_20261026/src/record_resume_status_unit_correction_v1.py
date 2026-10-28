"""Correct an inspection narrative's disk units; preserve all prior receipts."""
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
from maven_adapter_v1 import R, dump, sha
from projection_io_v1 import publish_json

B = R.parent / 'paired49_20261023'
sys.path.insert(0, str(B))
import audit

A = R / 'completion_amendment_v1'
prior = A / 'resume_status_check_20261027T064934Z_v2'
for line in (prior / 'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
    expected, name = line.split('  ', 1)
    assert Path(name).name == name and sha(prior / name) == expected
state = json.loads((prior / 'status.json').read_text(encoding='utf-8'))
assert state['minimum_free_bytes'] == 12_000_000_000 and state['disk_reserve_satisfied']
out = A / 'resume_status_unit_correction_v1'
out.mkdir(exist_ok=False)
dump(out / 'correction.json', {
    'at_utc': datetime.now(timezone.utc).isoformat(),
    'supersedes_narrative': str(prior / 'CHECK_STATUS.md'),
    'prior_narrative_sha256': sha(prior / 'CHECK_STATUS.md'),
    'verified_status_receipt': str(prior / 'status.json'),
    'verified_status_sha256': sha(prior / 'status.json'),
    'minimum_free_bytes': state['minimum_free_bytes'],
    'minimum_free_GB_decimal': state['minimum_free_bytes'] / 1e9,
    'minimum_free_GiB_binary': state['minimum_free_bytes'] / 1024**3,
    'observed_free_GB_decimal': state['disk_free_bytes'] / 1e9,
    'observed_free_GiB_binary': state['disk_free_bytes'] / 1024**3,
    'disk_reserve_satisfied': True,
    'correction': 'The prior JSON disk check was correct. The inspection commentary and Markdown narrative incorrectly treated the policy as 12 GiB and described disk as blocking. The locked threshold is 12,000,000,000 bytes, and the observed free space exceeds it.',
    'worker_exit_cause': 'UNKNOWN',
    'experiment_launches': 0, 'GPT_API_calls': 0,
    'experiment_policy_or_result_changes': False
})
md = '''# Trạng thái đã kiểm chứng — 27/10/2026

Batch hiện không còn worker thực nghiệm hoặc dispatcher. Chưa khởi động lại trong lần kiểm tra này.

| Class | Bằng chứng test | Phép đo PIT |
|---|---|---|
| 211 CurrentInstance | 8/8 pass | Báo cáo hợp lệ: 13/32 = 40,62% |
| 220 LocaleService | 3/3 pass | Báo cáo hợp lệ: 10/23 = 43,48% |
| 269 DataCommunicator | 25/25 pass | Timeout 300 giây; CSV dở, không có mutation score quan sát hợp lệ |
| 275 MetadataWriter | Chưa chạy; mới khôi phục một phần source | Chưa chạy |
| 294 ServerRpcHandler | Chưa bắt đầu | Chưa chạy |

25 checkpoint trước được giữ nguyên; 339 hashes checkpoint, 12.317 hashes code/input và 5 hashes công cụ khớp. GPT/RQ1–RQ3 và 585 file gốc/backup kiểm tra PASS. Mỗi class 211/220/269 chỉ có một lượt generation; không chạy lại theo điểm. Tổng 28/30 class đã có kết quả giai đoạn, không đồng nghĩa 28 mutation score hợp lệ. Kết quả 269 không được gọi là mutation 0% đo được hoặc lỗi compile chỉ vì PIT timeout.

Worker thoát khi đang khôi phục source 275; chưa có receipt complete/interrupted của dispatcher hoặc parent. Nguyên nhân thoát chưa xác định. Không suy lỗi chương trình từ phần chuẩn bị input đang dở.

**Đính chính đơn vị dung lượng:** ngưỡng policy là 12.000.000.000 byte = 12 GB thập phân ≈ 11,18 GiB. Khi kiểm tra còn khoảng 12,49 GB = 11,63 GiB, nên vẫn đạt ngưỡng. JSON kiểm tra gốc đã ghi đúng `disk_reserve_satisfied=true`; nhận xét trước đó rằng dung lượng chặn chạy là sai. Không thay đổi hoặc hạ ngưỡng policy.

Log, suite, báo cáo, thư mục dở và mọi kết quả trước giữ nguyên. Các archive bổ sung và hashes đã xác minh nằm trong `../resume_status_check_20261027T064934Z_v2/`. Narrative tại đây thay thế CHECK_STATUS.md của lần kiểm tra đó; tất cả file cũ được giữ để audit. Chỉ UI projection có backup được cập nhật, không sửa code thực nghiệm. Chưa cập nhật paper hoặc gọi E1-full300 hoàn chỉnh.
'''
(out / 'CHECK_STATUS.md').write_text(md, encoding='utf-8')
progress = json.loads((R / 'runtime/completion_progress.json').read_text(encoding='utf-8'))
progress.update(status_narrative=str(out / 'CHECK_STATUS.md'),
                disk_reserve_satisfied=True,
                minimum_free_bytes=state['minimum_free_bytes'],
                disk_free_bytes_at_check=state['disk_free_bytes'])
receipt = publish_json(R / 'runtime/completion_progress.json', progress,
                       label='checked_resume_disk_units')
assert receipt['published']
dump(out / 'UI_publication.json', receipt)
paths = sorted(p for p in out.iterdir() if p.is_file())
(out / 'SHA256SUMS.txt').write_text(''.join(sha(p) + '  ' + p.name + '\n' for p in paths), encoding='utf-8')
audit.log('RESUME_STATUS_DISK_UNITS_CORRECTION', path=str(out),
          correction_sha256=sha(out / 'correction.json'),
          prior_receipts_preserved=True, disk_reserve_satisfied=True,
          worker_exit_cause='UNKNOWN', experiment_launches=0, GPT_API_calls=0)
print(out)
