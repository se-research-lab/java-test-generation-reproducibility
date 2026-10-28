"""Post-completion read-only verification; no experiment launch or result recoding."""
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import psutil

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / 'src'))
from maven_adapter_v1 import sha, dump
from parallel_pin_verify_v1 import verify_pins
sys.path.insert(0, str(R.parent / 'paired49_20261023'))
import audit

def read(p):
    return json.loads(p.read_text(encoding='utf-8'))

out = R / 'audit/gradle_full40_completion_check_v1'
assert not out.exists(), 'Do not replace a previous audit'
out.mkdir()
owner = read(R / 'runtime/gradle_full40_v1/owner.json')
completion = read(R / 'runtime/gradle_full40_v1/complete.json')
admission = read(R / 'admission_gradle_full40_v1.json')
assert sha(R / 'admission_gradle_full40_v1.json') == owner['admission_sha256'] == completion['admission_sha256']
assert not (R / 'runtime/gradle_full40_v1/interrupted.json').exists()
try:
    p = psutil.Process(owner['pid'])
    assert abs(p.create_time() - owner['create_time']) >= .01, 'Original runner still alive'
except psutil.NoSuchProcess:
    pass
verify_pins(admission['code_and_input_hashes'])
audit.verify()
audit.verify_chain()
cache_rows = read(R / 'cache_preparation_gradle_v1/recovery_v2/manifest.json')
verify_pins({str(Path('C:/Users/admin/.gradle') / x['relative']): x['sha256'] for x in cache_rows})
rows, archive_files, native_files = [], 0, 0
for i in admission['admitted_sample_indices']:
    folder = R / 'jobs' / f'{i:03d}_gradle_v1'
    entries = read(folder / 'artifact_manifest.json')
    verify_pins({str(folder / x['relative']): x['sha256'] for x in entries})
    archive_files += len(entries)
    result_path = folder / 'result.json'
    deferred_path = folder / 'deferred.json'
    assert result_path.exists() != deferred_path.exists()
    d = read(result_path if result_path.exists() else deferred_path)
    commands = []
    for path in sorted((folder / 'commands').glob('*/plan.json')):
        plan = read(path)
        finished = read(path.parent / 'finished.json')
        commands.append({'command': path.parent.name, 'generation': '-jar' in plan['argv'],
            'started': (path.parent / 'started.json').exists(), 'returncode': finished['returncode'],
            'reason': finished.get('reason'), 'plan_sha256': sha(path)})
    calls = sum(c['generation'] and c['started'] for c in commands)
    assert calls <= 1, 'Unexpected retry; inspect without changing evidence'
    native_path = folder / 'native_generated.json'
    native_complete = False
    if native_path.exists():
        native = read(native_path)
        native_complete = native['complete']
        verify_pins({x['path']: x['sha256'] for x in native['files']})
        native_files += len(native['files'])
    evidence = []
    for path in sorted((folder / 'commands').glob('*/stderr.txt')):
        text = path.read_text(encoding='utf-8', errors='replace')
        for marker, label in [("Task 'b1WriteClasspaths' not found", 'HARNESS_TASK_MISSING'),
                              ('Unsupported class file major version 65', 'UNSUPPORTED_BYTECODE'),
                              ('ClassNotFoundException', 'CLASS_LOADING'),
                              ('because no repositories are defined', 'PIT_REPOSITORY_UNAVAILABLE')]:
            if marker in text:
                evidence.append({'label': label, 'path': str(path), 'sha256': sha(path)})
    labels = {e['label'] for e in evidence}
    if deferred_path.exists():
        assert 'PIT_REPOSITORY_UNAVAILABLE' in labels
        category = 'GENERATED_UNMEASURED_PIT_DEPENDENCY'
    elif d['legacy_process_build']:
        assert d['strict_suite_evidence'] and d['strict_measurement_evidence']
        category = 'BUILD_TEST_MEASUREMENT_PASS'
    elif d['generation_success']:
        assert i == 175
        stdout = folder / 'commands/004/stdout.txt'
        assert 'test0 FAILED' in stdout.read_text(encoding='utf-8')
        evidence.append({'label': 'TEST_EXECUTION_FAILURE_NPE', 'path': str(stdout), 'sha256': sha(stdout)})
        category = 'GENERATED_TEST_EXECUTION_FAILURE'
    elif calls == 0:
        assert 'HARNESS_TASK_MISSING' in labels
        category = 'NO_GENERATION_HARNESS_TASK_MISSING'
    elif 'UNSUPPORTED_BYTECODE' in labels:
        category = 'GENERATION_UNSUPPORTED_BYTECODE'
    elif 'CLASS_LOADING' in labels:
        category = 'GENERATION_CLASS_LOADING'
    else:
        assert any(c['generation'] and c['reason'] == 'TIMEOUT' for c in commands)
        category = 'GENERATION_TIMEOUT'
    rows.append({'index': i, 'class_key': d['class_key'], 'category': category,
        'generation_calls': calls, 'native_complete': native_complete,
        'raw_record_sha256': sha(result_path if result_path.exists() else deferred_path),
        'raw_process_gate': d.get('legacy_process_build'),
        'raw_strict_mutation_percent': d.get('legacy_strict_mutation_percent'),
        'raw_record_modified': False, 'commands': commands, 'evidence': evidence})
assert len(rows) == 40
counts = dict(Counter(r['category'] for r in rows))
summary = {'checked_utc': datetime.now(timezone.utc).isoformat(), 'completion': completion,
    'admission_sha256': owner['admission_sha256'], 'admission_pin_count': len(admission['code_and_input_hashes']),
    'original_cache_files_verified': len(cache_rows), 'archive_entries_verified': archive_files,
    'native_files_verified': native_files, 'original_and_backup_files_verified': 585,
    'generation_calls': sum(r['generation_calls'] for r in rows), 'retries': 0,
    'native_complete_classes': sum(r['native_complete'] for r in rows),
    'category_counts': counts, 'rows': rows, 'GPT_API_calls': 0,
    'new_experiment_calls_by_this_audit': 0, 'experiment_configuration_changed': False,
    'full300_scientific_acceptance': False, 'raw_results_recoded': False}
dump(out / 'verification.json', summary)
names = {
 'BUILD_TEST_MEASUREMENT_PASS': 'Qua build/test và đo',
 'GENERATED_TEST_EXECUTION_FAILURE': 'Đã sinh test, compile được nhưng chạy test lỗi',
 'GENERATED_UNMEASURED_PIT_DEPENDENCY': 'Đã sinh test, chưa đo được vì dependency PIT',
 'NO_GENERATION_HARNESS_TASK_MISSING': 'Chưa gọi EvoSuite vì thiếu task tích hợp',
 'GENERATION_UNSUPPORTED_BYTECODE': 'Không sinh suite hoàn chỉnh: bytecode không được hỗ trợ',
 'GENERATION_CLASS_LOADING': 'Không sinh suite hoàn chỉnh: lỗi nạp class',
 'GENERATION_TIMEOUT': 'Sinh test hết thời gian ngoài đã khóa',
}
lines = ['# Kiểm tra kết thúc Gradle40', '',
 'Batch kết thúc lúc 05:28:26 ngày 27/10/2026 (UTC+7). Đã xử lý cả 40 class; runner gốc đã thoát. Không khởi động lại.', '',
 '| Nhóm | Số class | Chỉ số class gốc |', '|---|---:|---|']
for key, title in names.items():
    ids = [str(x['index']) for x in rows if x['category'] == key]
    lines.append(f"| {title} | {len(ids)} | {', '.join(ids)} |")
lines += ['', '## Đọc số liệu đúng phạm vi', '',
 'Có 20 class tạo đủ native suite: 9 qua đo, 1 test execution fail (#175, NullPointerException ở test0), 10 bị chặn trước đo. Trong Gradle40, số class sinh test rồi fail gate là 1; không có lỗi compile test được quan sát. Không cộng 10 chưa đo vào số test build thất bại.', '',
 '30 raw terminal records + 10 deferred/unscored không đồng nghĩa 40 kết quả nghiệm thu. Toàn E1 hiện có 270 raw terminal records (49 E49 + 191 Maven + 30 Gradle), 30 deferred (20 Maven + 10 Gradle). 10 lỗi task tích hợp vẫn đang mang gate=0 trong raw; giữ nguyên bằng chứng nhưng cần rà tính hợp lệ trước tổng hợp khoa học. 9 lỗi nạp class/bytecode cũng cần rà môi trường/provenance; không tự recode, bỏ mẫu hoặc thay denominator.', '',
 'Batch là một lượt theo cấu hình khóa, không phải repeated-run evaluation. 30 lệnh sinh EvoSuite thực sự, không có retry; 10 class dừng trước sinh. Timeout #165 dừng trong giai đoạn assertions theo log, không chạy lại theo coverage hoặc mutation score.', '',
 '## Kiểm chứng', '',
 f"- Admission SHA-256: `{owner['admission_sha256']}`.",
 f"- {len(admission['code_and_input_hashes'])} mục code/input đã khóa: PASS.",
 f'- {archive_files} mục archive của 40 class và {native_files} file native test/scaffolding: PASS.',
 f'- {len(cache_rows)} file cache gốc: PASS; 585 file gốc/backup và audit chain: PASS.',
 '- Không sửa raw score/test/scaffolding/config; không gọi GPT/API hoặc chạy thêm thí nghiệm trong kiểm tra này.',
 '- Paper và G0/RQ1–RQ3 không được cập nhật từ các kết quả chưa nghiệm thu.', '',
 'Chi tiết attempts, phân loại và hashes trong verification.json. Đây là phân tích log sau chạy, không phải thay đổi policy thực nghiệm.']
(out / 'REPORT.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
dump(out / 'manifest.json', {p.name: sha(p) for p in [out / 'verification.json', out / 'REPORT.md']})
audit.log('B1_GRADLE_FULL40_POSTCOMPLETION_VERIFIED', folder=str(out), verification_sha256=sha(out / 'verification.json'), report_sha256=sha(out / 'REPORT.md'), experiment_calls=0, raw_results_modified=False)
print(json.dumps({k:v for k,v in summary.items() if k not in ('rows','completion')}, ensure_ascii=False, indent=2))
print(str(out / 'REPORT.md'))
