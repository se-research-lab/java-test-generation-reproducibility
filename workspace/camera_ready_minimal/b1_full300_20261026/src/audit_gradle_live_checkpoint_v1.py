"""Read-only experiment checkpoint. Writes a separate timestamped audit report."""
import hashlib
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

def read(p):
    return json.loads(p.read_text(encoding='utf-8'))

started = datetime.now(timezone.utc)
out = R / 'audit' / ('gradle_live_checkpoint_' + started.strftime('%Y%m%dT%H%M%S%fZ'))
out.mkdir(exist_ok=False)
admission_path = R / 'admission_gradle_full40_v1.json'
admission = read(admission_path)
owner = read(R / 'runtime/gradle_full40_v1/owner.json')
assert sha(admission_path) == owner['admission_sha256']
verified_code = {}
for name, expected in admission['code_and_input_hashes'].items():
    p = Path(name)
    if p.parent == R / 'src' or p.name == 'GRADLE40_FROZEN_PROTOCOL_V1.md':
        actual = sha(p)
        assert actual == expected, str(p)
        verified_code[name] = actual
audit.verify()
audit.verify_chain()
rows = []
for folder in sorted((R / 'jobs').glob('*_gradle_v1')):
    row = {'index': int(folder.name.split('_')[0]), 'folder': str(folder)}
    result_path, deferred_path = folder / 'result.json', folder / 'deferred.json'
    row['state'] = 'IN_PROGRESS'
    if result_path.exists():
        d = read(result_path)
        row.update(state='TERMINAL', result_sha256=sha(result_path))
        for k in ('generation_success', 'generation_calls', 'legacy_process_build',
                  'strict_suite_evidence', 'strict_measurement_evidence',
                  'mutation_score_percent', 'source_guard', 'production_bytecode_guard'):
            row[k] = d.get(k)
    elif deferred_path.exists():
        d = read(deferred_path)
        row.update(state='DEFERRED_UNSCORED', reason=d['reason'], score=None,
                   deferred_sha256=sha(deferred_path))
    if row['state'] != 'IN_PROGRESS':
        native_path = folder / 'native_generated.json'
        if native_path.exists():
            native = read(native_path)
            for item in native['files']:
                assert sha(item['path']) == item['sha256'], item['path']
            row['native_source_hash_check'] = 'PASS'
            row['native_file_count'] = len(native['files'])
        manifest_path = folder / 'artifact_manifest.json'
        if manifest_path.exists():
            entries = read(manifest_path)
            # Check only small control evidence here; the dispatcher checks the full archive.
            for item in entries:
                if item['relative'] in ('result.json', 'deferred.json', 'native_generated.json'):
                    assert sha(folder / item['relative']) == item['sha256']
            row['archive_manifest_sha256'] = sha(manifest_path)
    row['commands'] = []
    for p in sorted((folder / 'commands').glob('*/plan.json')):
        plan = read(p)
        finish = p.parent / 'finished.json'
        finished = read(finish) if finish.exists() else {}
        row['commands'].append({'number': p.parent.name, 'plan_sha256': sha(p),
            'is_generation': '-jar' in plan['argv'], 'started': (p.parent / 'started.json').exists(),
            'finished': finish.exists(), 'returncode': finished.get('returncode')})
    rows.append(row)
with urllib.request.urlopen('http://127.0.0.1:8766/status.json', timeout=10) as response:
    status = json.load(response)
dump(out / 'status_observed.json', status)
report = {'started_utc': started.isoformat(), 'finished_utc': datetime.now(timezone.utc).isoformat(),
    'scope': 'read-only rolling checkpoint; class records and live status can advance during observation',
    'admission_sha256': sha(admission_path), 'control_code_pins_verified': verified_code,
    'original_protected_files': 'PASS via audit.verify', 'audit_chain': 'PASS',
    'full_cache_rehashed_here': False, 'rows': rows, 'new_experiment_calls_by_this_check': 0,
    'full300_complete': False, 'configuration_or_generated_test_edits': False}
dump(out / 'checkpoint.json', report)
lines = ['# Kiểm tra Gradle40 đang chạy', '', f"Thời điểm: {report['finished_utc']} (UTC).",
    '', 'Đây là snapshot trong lúc batch tiếp tục; không phải kết quả cuối hoặc xác nhận E1 đủ 300.',
    '', f"- Cấu hình admission giữ nguyên SHA-256: `{report['admission_sha256']}`.",
    f"- Đã kiểm lại {len(verified_code)} file code/protocol đã khóa; PASS.",
    '- Dữ liệu gốc thuộc danh sách bảo vệ và chuỗi audit: PASS.',
    '- Kiểm tra này không gọi GPT/EvoSuite/Gradle, không sửa cấu hình hoặc test.',
    '- Snapshot không kiểm lại toàn bộ cache; dispatcher thực hiện kiểm theo protocol.',
    '', '| Class gốc | Trạng thái quan sát | Sinh mới thực tế | Gate đo | Ghi chú |',
    '|---|---|---:|---|---|']
for row in rows:
    calls = sum(c['is_generation'] and c['started'] for c in row['commands'])
    note = row.get('reason', '')
    if row['state'] == 'TERMINAL':
        note = 'Native hash ' + row.get('native_source_hash_check', 'not available') + '; mutation=' + str(row.get('mutation_score_percent')) + '%'
    lines.append(f"| {row['index']} | {row['state']} | {calls} | {row.get('legacy_process_build', 'chưa chấm')} | {note} |")
if any(r['index'] == 4 and r['state'] == 'DEFERRED_UNSCORED' for r in rows):
    error = R / 'jobs/004_gradle_v1/commands/003/stderr.txt'
    text = error.read_text(encoding='utf-8')
    if 'because no repositories are defined' in text and 'org.pitest:pitest-command-line:1.3.1' in text:
        lines.extend(['', 'Class #4 đã sinh native suite nhưng bị chặn trước đo: cấu hình PIT không resolve được `org.pitest:pitest-command-line:1.3.1` vì không có repository được khai báo trong configuration tương ứng. Đây là lỗi môi trường tích hợp/đo; chưa có bằng chứng test sinh ra không compile hoặc fail khi chạy. Giữ unscored, không đổi thành 0, không thêm repository hay chạy lại sau lỗi.', '', f'Bằng chứng: `{error}`; SHA-256 `{sha(error)}`.'])
lines.extend(['', '20 class Maven bị chặn tiếp tục giữ nguyên. Mọi bổ sung Gradle được báo cáo riêng; không thay G0 hoặc mẫu RQ1–RQ3. Quy tắc chạy được khóa tại GRADLE40_FROZEN_PROTOCOL_V1.md.', '', 'Dashboard đã sửa nhãn admission và bộ lọc Gradle. Chỉ xác nhận HTTP trả đúng HTML; chưa kiểm render bằng trình duyệt.'])
(out / 'REPORT.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
audit.log('B1_GRADLE_READONLY_LIVE_CHECKPOINT', checkpoint_sha256=sha(out / 'checkpoint.json'), report_sha256=sha(out / 'REPORT.md'), folder=str(out), experiment_calls=0)
print(json.dumps({'folder': str(out), 'checked_code_files': len(verified_code), 'rows': [{k: v for k, v in r.items() if k in ('index', 'state', 'legacy_process_build', 'reason')} for r in rows], 'runner_liveness': status.get('runner_liveness'), 'active_sample_index': status.get('active_sample_index')}, ensure_ascii=False, indent=2))
