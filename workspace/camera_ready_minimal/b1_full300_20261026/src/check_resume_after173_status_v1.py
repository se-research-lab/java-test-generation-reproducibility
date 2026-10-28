"""Observe and checkpoint an exited resume attempt; never launch experiments."""
import concurrent.futures
import json
import msvcrt
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import sys
from datetime import datetime, timezone

import psutil

from maven_adapter_v1 import R, dump, sha
from parallel_pin_verify_v1 import verify_pins
from projection_io_v1 import publish_json

A = R / 'completion_amendment_v1'
O = A / 'pause_20261027_after173_v1'
B = R.parent / 'paired49_20261023'
sys.path.insert(0, str(B))
import audit


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def inventory(folder):
    paths = []
    for root, dirs, names in os.walk(folder, followlinks=False):
        for name in dirs + names:
            p = Path(root) / name
            s = p.lstat()
            assert not p.is_symlink()
            assert not getattr(s, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400)
        paths.extend(Path(root) / name for name in names)

    def record(p):
        return {'relative': p.relative_to(folder).as_posix(), 'bytes': p.stat().st_size, 'sha256': sha(p)}

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        return sorted(pool.map(record, paths), key=lambda x: x['relative'])


def processes():
    rows = []
    inaccessible = []
    tokens = ('run_remaining', 'complete_maven_groups', 'complete_gradle_pit_group',
              'finalize_completion_when_ready', 'resume_user_paused_e1')
    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
        try:
            name = (proc.info['name'] or '').lower()
            argv = proc.info['cmdline'] or []
            scripts = [x for x in argv if x.lower().endswith('.py')]
            is_java = name in ('java.exe', 'javaw.exe')
            worker = name in ('python.exe', 'pythonw.exe') and any(
                any(token in Path(x).name for token in tokens) for x in scripts)
            if is_java or worker:
                rows.append({'pid': proc.pid, 'name': name,
                             'create_time': proc.info['create_time'],
                             'scripts': scripts,
                             'scoped_to_E1': str(R).lower() in ' '.join(argv).lower()})
        except psutil.NoSuchProcess:
            continue
        except psutil.AccessDenied:
            inaccessible.append(proc.pid)
    return {'at_utc': timestamp(), 'experiment_or_dispatch_processes': rows,
            'inaccessible_pids': inaccessible}


def main():
    out = A / ('resume_status_check_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '_v1')
    out.mkdir(exist_ok=False)
    dump(out / 'scope.json', {'at_utc': timestamp(), 'purpose': 'read-only evidence check and UI projection only',
                              'experiment_launches': 0, 'GPT_API_calls': 0,
                              'source_script_sha256': sha(__file__)})
    process = processes()
    dump(out / 'processes_before.json', process)
    assert not process['experiment_or_dispatch_processes'], 'A worker is still alive; inspection must not claim quiescence'
    assert not process['inaccessible_pids'], 'Cannot certify complete process inventory'
    with (R / 'runtime/dispatcher.lock').open('r+b') as f:
        f.seek(0)
        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        f.seek(0)
        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
    admission = load(O / 'resume_admission_v1.json')
    counts = {}
    for name, pins in [('accepted25_checkpoint', load(O / 'checkpoint_pins.json')),
                       ('resume_code_and_inputs', admission['code_and_input_hashes']),
                       ('tools', admission['tool_hashes'])]:
        counts[name] = verify_pins(pins)
        print('VERIFIED', name, counts[name], flush=True)
    checkpoint = load(O / 'checkpoint.json')
    assert sha(A / 'admission_maven_pom_v3.json') == checkpoint['admission_sha256']
    assert sha(O / 'checkpoint.json') == admission['resume_checkpoint_sha256']
    import importlib.util
    spec = importlib.util.spec_from_file_location('status_gpt_guard', R.parents[1] / 'review_reports/minimal_camera_ready_20261023/guard_rq123_frozen.py')
    g = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(g)
    assert g.collect() == load(g.LOCK), 'GPT/RQ1-3 frozen input drift'
    dump(out / 'GPT_RQ123_guard.json', {'status': 'PASS', 'gpt_artifact_hashes_verified': 298,
                                      'no_output_records': 2, 'cohort_sizes': [61, 45, 300],
                                      'new_experiments': 0})
    audit.verify()
    rows = []
    for i in [211, 220, 269]:
        job = R / 'jobs' / f'{i:03d}_completion_pom_resume_after173_v1'
        result = load(job / 'result.json')
        actual = inventory(job)
        by_name = {x['relative']: x for x in actual}
        old = load(job / 'artifact_manifest.json')
        for row in old:
            rel = PurePosixPath(row['relative'])
            assert not rel.is_absolute() and '..' not in rel.parts and ':' not in str(rel)
            found = by_name[str(rel)]
            assert found['sha256'] == row['sha256'] and found['bytes'] == row['bytes']
        old_names = {row['relative'] for row in old}
        extras = [x['relative'] for x in actual if x['relative'] not in old_names and x['relative'] != 'artifact_manifest.json']
        assert set(extras) == {'derived_pom_evidence/after_generation_and_measurement.json',
                               'derived_pom_evidence/after_generation_and_measurement.xml'}, extras
        dump(out / f'{i:03d}_complete_archive.json', actual)
        plans = [p for p in (job / 'commands').glob('*/plan.json') if (p.parent / 'started.json').exists()]
        generation_count = sum('-jar' in load(p)['argv'] for p in plans)
        assert generation_count == result['generation_calls'] == 1
        measurement = load(job / 'commands/007/finished.json')
        assert result['seed'] == 20261023 + i
        assert result['source_guard'] == result['production_bytecode_guard'] == 'PASS'
        if i in [211, 220]:
            assert measurement['returncode'] == 0
            assert result['PIT_report_complete'] and result['strict_measurement_evidence']
            assert result['mutation_score_percent'] == round(100 * result['killed_mutants'] / result['focal_mutants'], 2)
        else:
            assert measurement['reason'] == 'TIMEOUT' and measurement['elapsed_seconds'] >= 300
            assert result['strict_suite_evidence'] and not result['PIT_report_complete']
            assert result['mutation_score_percent'] is None
        rows.append({'index': i, 'result_sha256': sha(job / 'result.json'),
                     'suite_pass': result['strict_suite_evidence'],
                     'test_count': sum(x['tests'] for x in result['surefire_suites']),
                     'PIT_report_complete': result['PIT_report_complete'],
                     'observed_mutation_percent': result['mutation_score_percent'],
                     'measurement_end_reason': measurement['reason'],
                     'legacy_end_to_end_gate': result['legacy_process_build'],
                     'generation_calls': generation_count, 'seed': result['seed'],
                     'archived_entries_verified': len(old), 'post_archive_extra_receipts_verified': extras,
                     'complete_archive_sha256': sha(out / f'{i:03d}_complete_archive.json')})
        print('VERIFIED_NEW_RESULT', i, flush=True)
    partial = R / 'jobs/275_completion_pom_resume_after173_v1'
    assert not (partial / 'commands').exists() and not (partial / 'generation_attempts').exists()
    assert set(p.name for p in partial.iterdir()) == {'repo'}
    partial_rows = inventory(partial)
    dump(out / '275_partial_source_restore_archive.json', partial_rows)
    assert not (R / 'jobs/294_completion_pom_resume_after173_v1').exists()
    complete_receipts = [A / 'maven_pom_resume_after173_v1/complete.json',
                         A / 'maven_pom_resume_after173_v1/interrupted.json',
                         O / 'resume_invocation/complete.json']
    assert not any(p.exists() for p in complete_receipts)
    disk = shutil.disk_usage(R).free
    final_process = processes()
    assert not final_process['experiment_or_dispatch_processes'] and not final_process['inaccessible_pids']
    dump(out / 'processes_after.json', final_process)
    report = {'at_utc': timestamp(), 'status': 'NO_WORKER_OBSERVED_INCOMPLETE_DISPATCH',
              'accepted25_unchanged': True, 'pin_counts_verified': counts,
              'additional_terminal_results': rows, 'completed30_subset_count': 28,
              'remaining_indices': [275, 294],
              'partial275': {'source_restore_only': True, 'files': len(partial_rows),
                             'bytes': sum(x['bytes'] for x in partial_rows),
                             'generation_calls': 0, 'measurement_calls': 0},
              'missing_dispatch_exit_receipts': [str(p) for p in complete_receipts],
              'dispatcher_exit_cause': 'UNKNOWN: no complete/interrupted or parent exit receipt; do not infer from low current disk',
              'disk_free_bytes': disk, 'disk_free_GiB': disk / 1024**3,
              'minimum_free_bytes': admission['minimum_free_bytes'],
              'disk_reserve_satisfied': disk >= admission['minimum_free_bytes'],
              'policy_seed_config_changed': False, 'experiment_workers_alive': 0,
              'GPT_API_calls': 0, 'automatic_restart': False, 'full300_complete': False}
    dump(out / 'status.json', report)
    ui = {'phase': 'POM / INCOMPLETE_NO_LIVE_WORKER', 'active_index': None,
          'finished_indices': [211, 220, 269], 'completed30_subset_count': 28,
          'remaining_indices': [275, 294], 'updated_utc': timestamp(),
          'event': 'OBSERVED_WORKER_EXIT_WITHOUT_COMPLETION_RECEIPT',
          'dispatch_exit_cause': 'UNKNOWN', 'disk_reserve_satisfied': report['disk_reserve_satisfied'],
          'status_receipt': str(out / 'status.json'), 'full300_complete': False, 'GPT_API_calls': 0}
    receipt = publish_json(R / 'runtime/completion_progress.json', ui, label='checked_exited_resume_status')
    dump(out / 'UI_publication.json', receipt)
    assert receipt['published']
    md = f'''# Kiểm tra batch tiếp tục — 27/10/2026\n\n- Không còn worker thực nghiệm/dispatcher; mutex đã kiểm tra rảnh. Không khởi động lại.\n- 25 checkpoint cũ: {counts['accepted25_checkpoint']} hashes khớp; code/input {counts['resume_code_and_inputs']} và tools {counts['tools']} hashes khớp; GPT/RQ1–RQ3 và backup paper gốc kiểm tra PASS.\n- 211: 8 test pass, PIT hợp lệ 13/32 = 40,62%.\n- 220: 3 test pass, PIT hợp lệ 10/23 = 43,48%.\n- 269: 25 test pass; phép đo đạt timeout 300 giây, CSV cắt dở. Mutation quan sát chưa xác định; không gọi mutation 0% đo được, không gọi compile/build test fail. Không retry.\n- Tổng 28/30 class có kết quả giai đoạn, không đồng nghĩa 28 mutation score hợp lệ.\n- 275 mới khôi phục một phần source ({len(partial_rows)} file); chưa chạy lệnh experiment, chưa sinh test. 294 chưa chuẩn bị.\n- Worker thoát khi khôi phục input 275; không có receipt kết thúc/ngoại lệ. Chưa xác định nguyên nhân thoát.\n- Dung lượng hiện tại {disk / 1024**3:.2f} GiB; ngưỡng khóa {admission['minimum_free_bytes'] / 1024**3:.2f} GiB. Dung lượng thấp là chặn chạy tiếp hiện tại, không phải nguyên nhân thoát đã được chứng minh.\n- Log, report, suite và thư mục dở được giữ nguyên. Chỉ UI projection có backup và receipt được cập nhật; không thay policy/seed/config.\n- Chưa cập nhật paper, chưa gọi E1-full300 hoàn chỉnh.\n\nChi tiết: status.json, complete archives cho 211/220/269, partial-source archive cho 275 và hashes SHA256SUMS.txt cùng thư mục.\n'''
    (out / 'CHECK_STATUS.md').write_text(md, encoding='utf-8')
    manifest = [{'path': p.name, 'sha256': sha(p), 'bytes': p.stat().st_size}
                for p in sorted(out.iterdir()) if p.is_file()]
    dump(out / 'MANIFEST.json', manifest)
    files = sorted(p for p in out.iterdir() if p.is_file())
    (out / 'SHA256SUMS.txt').write_text(''.join(sha(p) + '  ' + p.name + '\n' for p in files), encoding='utf-8')
    audit.log('RESUME_AFTER173_CHECKPOINT_OBSERVATION', path=str(out),
              status_sha256=sha(out / 'status.json'), accepted25_unchanged=True,
              new_terminal_indices=[211, 220, 269], remaining_indices=[275, 294],
              experiment_launches=0, GPT_API_calls=0, worker_exit_cause='UNKNOWN')
    print(json.dumps({'status': report['status'], 'output': str(out),
                      'disk_free_GiB': report['disk_free_GiB'],
                      'additional_terminal': [211, 220, 269], 'remaining': [275, 294]}, indent=2))


if __name__ == '__main__':
    main()
