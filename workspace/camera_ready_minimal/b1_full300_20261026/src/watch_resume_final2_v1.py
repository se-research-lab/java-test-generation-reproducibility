"""One finite user-authorized two-class invocation; no restart or follow-on queue."""
import argparse
import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone
import psutil
from maven_adapter_v1 import R, sha, dump
from projection_io_v1 import publish_json

A = R / 'completion_amendment_v1'
P = A / 'resume_final2_v1'


def now():
    return datetime.now(timezone.utc).isoformat()


def load(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--explicit-user-resume', action='store_true', required=True)
    parser.parse_args()
    run = P / 'invocation'
    assert run.is_dir() and (run / 'authorization.json').exists()
    assert not (run / 'watcher_owner.json').exists() and not (run / 'complete.json').exists()
    me = psutil.Process()
    dump(run / 'watcher_owner.json', {'pid': me.pid, 'create_time': me.create_time(), 'started_utc': now()})
    argv = [sys.executable, '-B', '-X', 'utf8', str(R / 'src/run_remaining2_final_v1.py'), '--group', 'pom']
    dump(run / 'runner_plan.json', {'argv': argv, 'automatic_retry': False, 'follow_on_queues_enabled': False})
    rc = None
    try:
        with (run / 'runner_stdout.txt').open('xb') as so, (run / 'runner_stderr.txt').open('xb') as se:
            child = subprocess.Popen(argv, stdout=so, stderr=se, stdin=subprocess.DEVNULL,
                                     cwd=R, creationflags=subprocess.CREATE_NO_WINDOW)
            dump(run / 'runner_owner.json', {'pid': child.pid, 'create_time': psutil.Process(child.pid).create_time(),
                                             'started_utc': now()})
            rc = child.wait()
        dump(run / 'complete.json', {'at_utc': now(), 'returncode': rc, 'automatic_retry': False,
                                     'follow_on_queues_started': False,
                                     'stdout_sha256': sha(run / 'runner_stdout.txt'),
                                     'stderr_sha256': sha(run / 'runner_stderr.txt')})
        results = [i for i in [275, 294] if (R / 'jobs' / f'{i:03d}_completion_pom_resume_final2_v1/result.json').exists()]
        progress = {'phase': 'FINAL2_INVOCATION_ENDED', 'active_index': None, 'finished_indices': results,
                    'remaining_indices': [i for i in [275, 294] if i not in results],
                    'updated_utc': now(), 'returncode': rc, 'GPT_API_calls': 0,
                    'full300_complete': False, 'automatic_retry': False, 'follow_on_queues_enabled': False,
                    'note': 'Invocation ended; final evidence audit still required; unresolved remains separate.'}
        dump(run / 'UI_publication.json', publish_json(R / 'runtime/completion_progress.json', progress,
                                                       label='final2_invocation_end'))
    except BaseException as exc:
        dump(run / 'watcher_interrupted.json', {'at_utc': now(), 'type': type(exc).__name__,
                                               'error': str(exc), 'runner_returncode': rc,
                                               'automatic_retry': False, 'follow_on_queues_started': False})
        raise


if __name__ == '__main__':
    main()
