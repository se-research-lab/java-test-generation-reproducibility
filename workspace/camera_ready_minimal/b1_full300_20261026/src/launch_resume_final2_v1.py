"""Validate and launch one hidden finite worker after explicit human resume."""
import argparse
import json
import msvcrt
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
import psutil
from maven_adapter_v1 import R, sha, dump
from parallel_pin_verify_v1 import verify_pins
from projection_io_v1 import publish_json

A = R / 'completion_amendment_v1'
P = A / 'resume_final2_v1'
B = R.parent / 'paired49_20261023'
sys.path.insert(0, str(B))
import audit


def load(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))


def now():
    return datetime.now(timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--explicit-user-resume', action='store_true', required=True)
    parser.parse_args()
    assert not (P / 'invocation').exists() and not (A / 'maven_pom_resume_final2_v1').exists()
    assert not (R / 'STOP_REQUESTED.json').exists()
    lock = load(P / 'admission.json')
    assert lock['admitted_sample_indices'] == lock['generation_allowed_indices'] == [275, 294]
    assert not lock['GPT_generation_authorized'] and not lock['automatic_resume']
    verify_pins(lock['code_and_input_hashes'])
    verify_pins(lock['tool_hashes'])
    verify_pins(load(P / 'retained_evidence_pins.json'))
    assert shutil.disk_usage(R).free >= lock['minimum_free_bytes']
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        name = (proc.info['name'] or '').lower()
        argv = proc.info['cmdline'] or []
        if name in ('java.exe', 'javaw.exe'):
            assert str(R).lower() not in ' '.join(argv).lower(), 'Existing E1 Java process'
        scripts = [Path(x).name for x in argv if x.endswith('.py')]
        forbidden = ('run_remaining', 'complete_maven_groups', 'complete_gradle_pit_group',
                     'finalize_completion_when_ready', 'watch_resume_final2', 'resume_user_paused_e1')
        assert not any(any(t in s for t in forbidden) for s in scripts), 'Existing scoped dispatcher/queue'
    with (R / 'runtime/dispatcher.lock').open('r+b') as f:
        f.seek(0)
        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        f.seek(0)
        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
    for i in [275, 294]:
        assert not (R / 'jobs' / f'{i:03d}_completion_pom_resume_final2_v1').exists()
    run = P / 'invocation'
    run.mkdir(exist_ok=False)
    dump(run / 'authorization.json', {'at_utc': now(), 'explicit_user_resume': True,
                                      'user_request': 'bắt đầu chạy lại, đã giải phóng ổ d bây giờ trống hơn 15gb',
                                      'admitted_indices': [275, 294], 'retained28_not_rerun': True,
                                      'admission_sha256': sha(P / 'admission.json'),
                                      'free_bytes_at_launch': shutil.disk_usage(R).free,
                                      'policy_seed_config_budget_changed': False,
                                      'automatic_retry': False, 'follow_on_queues_enabled': False})
    publish_json(R / 'runtime/completion_progress.json', {
        'phase': 'USER_RESUMED_FINAL2_PREPARING275', 'active_index': 275,
        'finished_indices': [], 'remaining_indices': [275, 294],
        'previous28_retained': True, 'updated_utc': now(), 'GPT_API_calls': 0,
        'policy_seed_config_changed': False, 'full300_complete': False,
        'automatic_retry': False, 'follow_on_queues_enabled': False}, label='explicit_resume_final2')
    argv = [sys.executable, '-B', '-X', 'utf8', str(R / 'src/watch_resume_final2_v1.py'), '--explicit-user-resume']
    dump(run / 'watcher_plan.json', {'argv': argv, 'hidden_window': True,
                                    'finite_scope': [275, 294], 'automatic_retry': False})
    with (run / 'watcher_stdout.txt').open('xb') as so, (run / 'watcher_stderr.txt').open('xb') as se:
        child = subprocess.Popen(argv, stdout=so, stderr=se, stdin=subprocess.DEVNULL,
                                 cwd=R, creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP)
        dump(run / 'launch_owner.json', {'pid': child.pid, 'create_time': psutil.Process(child.pid).create_time(),
                                         'at_utc': now()})
    audit.log('USER_AUTHORIZED_FINAL2_LAUNCH', indices=[275, 294], admission_sha256=sha(P / 'admission.json'),
              watcher_pid=child.pid, source_profile_seed_budget_unchanged=True, GPT_API_calls=0,
              follow_on_queues_enabled=False)
    print(json.dumps({'status': 'LAUNCHED_FINAL2', 'watcher_pid': child.pid,
                      'indices': [275, 294], 'free_GB': shutil.disk_usage(R).free / 1e9,
                      'invocation': str(run)}, indent=2))


if __name__ == '__main__':
    main()
