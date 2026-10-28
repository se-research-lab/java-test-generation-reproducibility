"""Display-only correction, with original bytes and diff retained. No job calls."""
import difflib
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / 'src'))
from maven_adapter_v1 import sha, dump
sys.path.insert(0, str(R.parent / 'paired49_20261023'))
import audit

target = R / 'monitor/dist_v2/index.html'
out = R / 'audit/gradle_preview_labels_v1'
assert not out.exists(), 'One display edit only; preserve prior evidence'
for name in ('admission_gradle_full40_v1.json', 'admission_maven_v6.json'):
    serialized = (R / name).read_text(encoding='utf-8')
    for candidate in (str(target), target.as_posix()):
        assert json.dumps(candidate)[1:-1] not in serialized, 'Display file is sealed'

before = target.read_bytes()
original = before.decode('utf-8')
updated = original
changes = {
    "text('admitted',s.benchmark_admitted?'Maven được admit · Gradle chưa':'CHƯA');":
    "text('admitted',s.benchmark_admitted?(s.Gradle_benchmark_admitted?'Gradle · cấu hình đã khóa':'Maven được admit · Gradle chưa'):'DỪNG / CẦN KIỂM TRA');",
    "COMPLETED_E1_MAVEN:'Hoàn tất E1 Maven',":
    "COMPLETED_E1_MAVEN:'Hoàn tất E1 Maven',PENDING_GRADLE_LOCKED_V1:'Gradle chờ lượt · đã khóa',COMPLETED_E1_GRADLE:'Hoàn tất E1 Gradle',DEFERRED_GRADLE_UNSCORED:'Gradle bị chặn · chưa chấm',",
    '<option value="COMPLETED_E1_MAVEN">Hoàn tất E1 Maven</option>':
    '<option value="COMPLETED_E1_MAVEN">Hoàn tất E1 Maven</option><option value="PENDING_GRADLE_LOCKED_V1">Gradle chờ lượt · đã khóa</option><option value="COMPLETED_E1_GRADLE">Hoàn tất E1 Gradle</option><option value="DEFERRED_GRADLE_UNSCORED">Gradle bị chặn · chưa chấm</option>',
    '<small>Chưa chạy ≠ điểm 0</small>':
    '<small>Gồm đang chạy / bị chặn; chưa chấm ≠ điểm 0</small>',
    "text('running',`Đang chạy: ${s.running}`);":
    "text('running',`Đang chạy: ${s.running}${s.active_sample_index!=null?' · class #'+s.active_sample_index:''}`);",
    '● Kết nối local · đọc thành công ${new Date().toLocaleTimeString(\'vi-VN\')} · không tự suy diễn tiến độ':
    '● Kết nối local · đọc thành công ${new Date().toLocaleTimeString(\'vi-VN\')} · runner: ${s.runner_liveness||\'chưa xác minh\'}',
}
for old, new in changes.items():
    assert updated.count(old) == 1, ('Unexpected display source', old)
    updated = updated.replace(old, new)
out.mkdir()
(out / 'index.before.html').write_bytes(before)
(out / 'change.diff').write_text(''.join(difflib.unified_diff(original.splitlines(True), updated.splitlines(True), fromfile='index.before.html', tofile='index.after.html')), encoding='utf-8')
assert target.read_bytes() == before
target.write_bytes(updated.encode('utf-8'))
(out / 'index.after.html').write_bytes(target.read_bytes())
with urllib.request.urlopen('http://127.0.0.1:8766/', timeout=10) as response:
    served = response.read()
assert served == target.read_bytes(), 'HTTP did not serve corrected HTML'
receipt = {
    'at_utc': datetime.now(timezone.utc).isoformat(),
    'scope': 'display only; no experimental configuration or data edits',
    'target': str(target), 'before_sha256': sha(out / 'index.before.html'),
    'after_sha256': sha(target), 'diff_sha256': sha(out / 'change.diff'),
    'http_exact_bytes_verified': True, 'browser_render_checked': False,
    'experiment_calls': 0, 'admission_sha256': sha(R / 'admission_gradle_full40_v1.json'),
}
dump(out / 'receipt.json', receipt)
audit.log('B1_GRADLE_PREVIEW_LABELS_CORRECTED', receipt_sha256=sha(out / 'receipt.json'), experiment_calls=0)
print(json.dumps(receipt, ensure_ascii=False, indent=2))
