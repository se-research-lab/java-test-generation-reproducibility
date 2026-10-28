"""Seal a control-only continuation for two never-started classes; no launches."""
import ast
import difflib
import json
from pathlib import Path, PurePosixPath
from datetime import datetime, timezone
from maven_adapter_v1 import R, sha, dump
from parallel_pin_verify_v1 import verify_pins

A = R / 'completion_amendment_v1'
O = A / 'pause_20261027_after173_v1'
P = A / 'resume_final2_v1'
CHECK = A / 'resume_status_check_20261027T064934Z_v2'


def load(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))


def main():
    assert not P.exists(), 'Preserve earlier preparation; use a new version after inspection'
    old = R / 'src/run_remaining5_after173_v1.py'
    new = R / 'src/run_remaining2_final_v1.py'
    original = old.read_text(encoding='utf-8')
    text = original
    changes = {
        "admission=A/'pause_20261027_after173_v1/resume_admission_v1.json'":
            "admission=A/'resume_final2_v1/admission.json'",
        "run=A/'maven_pom_resume_after173_v1'":
            "run=A/'maven_pom_resume_final2_v1'",
        "f'{i:03d}_completion_{group}_resume_after173_v1'":
            "f'{i:03d}_completion_{group}_resume_final2_v1'",
    }
    for before, after in changes.items():
        assert text.count(before) == 1
        text = text.replace(before, after)
    ast.parse(text)
    assert not new.exists()
    with new.open('x', encoding='utf-8') as f:
        f.write(text)
    P.mkdir(exist_ok=False)
    (P / 'dispatcher_control_only.diff').write_text(''.join(difflib.unified_diff(
        original.splitlines(True), text.splitlines(True), fromfile=old.name, tofile=new.name)), encoding='utf-8')
    parent = O / 'resume_admission_v1.json'
    lock = load(parent)
    pins = dict(load(O / 'checkpoint_pins.json'))
    for i in [211, 220, 269]:
        job = R / 'jobs' / f'{i:03d}_completion_pom_resume_after173_v1'
        result = load(job / 'result.json')
        assert result['terminal'] and result['generation_calls'] == 1
        pins[str(job / 'result.json')] = sha(job / 'result.json')
        for row in load(CHECK / f'{i:03d}_complete_archive.json'):
            name = row['relative']
            parts = PurePosixPath(name).parts
            assert '..' not in parts and not PurePosixPath(name).is_absolute() and ':' not in name
            # The complete prior byte archive is reverified, not merely trusted by filename.
            pins[str(job / Path(*parts))] = row['sha256']
    partial = R / 'jobs/275_completion_pom_resume_after173_v1'
    assert set(p.name for p in partial.iterdir()) == {'repo'}
    for row in load(CHECK / '275_partial_source_restore_archive.json'):
        pins[str(partial / Path(*PurePosixPath(row['relative']).parts))] = row['sha256']
    assert not (R / 'jobs/294_completion_pom_resume_after173_v1').exists()
    for i in [275, 294]:
        assert not (R / 'jobs' / f'{i:03d}_completion_pom_resume_final2_v1').exists()
        assert not load(R / 'runtime/pom_input_deferrals_v1' / f'{i:03d}.json')['generation_already_attempted']
    verify_pins(pins)
    dump(P / 'retained_evidence_pins.json', pins)
    accepted = load(O / 'checkpoint.json')['accepted25_indices'] + [211, 220, 269]
    assert len(set(accepted)) == 28 and not set(accepted) & {275, 294}
    dump(P / 'continuation_scope.json', {
        'at_utc': datetime.now(timezone.utc).isoformat(),
        'reason': 'Human explicitly requested continuation after freeing drive D; prior dispatcher exited without an exit receipt.',
        'remaining_indices': [275, 294], 'must_not_rerun_indices': sorted(accepted),
        '275_prior_attempt': 'partial source restoration only; no command, generation, compile/test, or PIT start',
        'old_partial275_preserved': str(partial),
        'retained_evidence_hashes': len(pins),
        '269_final_selection': 'keep completed timeout attempt; observed mutation undefined; no retry',
        'scope_is_post_outcome_continuation': True,
        'experiment_profile_seed_budget_dependencies_targets_mutators_changed': False,
        'automatic_retry': False, 'follow_on_queues_enabled': False, 'GPT_API_calls': 0,
    })
    revised = json.loads(json.dumps(lock))
    revised.update(admitted_sample_indices=[275, 294], generation_allowed_indices=[275, 294],
                   scope='User-authorized continuation of only unstarted275/294; unchanged E1 scientific recipe',
                   parent_admission_sha256=sha(parent),
                   prepared_utc=datetime.now(timezone.utc).isoformat())
    inputs = [new, Path(__file__), R / 'src/watch_resume_final2_v1.py',
              R / 'src/launch_resume_final2_v1.py', P / 'dispatcher_control_only.diff',
              P / 'retained_evidence_pins.json', P / 'continuation_scope.json', parent]
    revised['code_and_input_hashes'].update({str(p.resolve()): sha(p) for p in inputs})
    permitted = {'admitted_sample_indices', 'generation_allowed_indices', 'scope',
                 'parent_admission_sha256', 'prepared_utc', 'code_and_input_hashes'}
    changed = {k for k in set(lock) | set(revised) if lock.get(k) != revised.get(k)}
    assert changed <= permitted
    assert all(revised['code_and_input_hashes'][k] == v for k, v in lock['code_and_input_hashes'].items())
    verify_pins(revised['code_and_input_hashes'])
    verify_pins(revised['tool_hashes'])
    dump(P / 'admission.json', revised)
    dump(P / 'preparation.json', {'prepared_only': True, 'control_fields_changed': sorted(changed),
                                  'admission_sha256': sha(P / 'admission.json'),
                                  'parent_admission_sha256': sha(parent),
                                  'retained_evidence_pins': len(pins),
                                  'scientific_core_unchanged': True, 'experiment_launches': 0})
    print('SEALED_FINAL2; not launched; evidence pins', len(pins), flush=True)


if __name__ == '__main__':
    main()
