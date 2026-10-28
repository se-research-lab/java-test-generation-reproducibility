"""Quarantine a narrow unsupported environment without manufacturing a score.

This is a scheduling decision, not an amendment of measurement or dependencies.
The archived generation is retained; a future reconciliation must reuse it.
"""
import json
from pathlib import Path
from maven_adapter_v1 import R, GuardAbort, sha, dump
from maven_controller_v2 import source_hashes, bytecode, ensure
from checkpoint_archive_guard_v2 import verify
from pom_integration_guard_v1 import verify as verify_integration

DETAIL = 'Existing non-JUnit4 requires separate review'
REGISTRY = R / 'runtime/non_junit4_deferrals_v1'

def load(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))

def eligible_dependency(dep):
    test = [x for x in dep.get('classpath', []) if x['path'].startswith('junit/junit/')]
    compile_rows = {x['path']: x['sha256'] for x in dep.get('compile_classpath', [])}
    return (len(test) == 1 and test[0]['path'].split('/')[2].startswith('3.')
            and compile_rows.get(test[0]['path']) == test[0]['sha256'])

def inspect(out):
    out = Path(out).resolve()
    ensure(out.parent == (R / 'jobs').resolve() and out.name.isdigit(), 'Deferral outside original job folder')
    verify(out)
    interruption = load(out / 'interrupted.json')
    ensure(interruption['error_type'] == 'GuardAbort' and interruption['detail'] == DETAIL,
           'Only the reviewed non-JUnit4 pre-measurement guard is deferrable')
    ensure(interruption['auto_resume'] is False and interruption['score_accepted'] is False,
           'Interruption must be unscored and non-resumable')
    ensure(not (out / 'result.json').exists(), 'Never defer a scored result')
    job = load(out / 'job_admission.json')['job']
    ensure(job['sample_index_1based'] == int(out.name) and job['build_tool'] == 'maven'
           and not job['reused_result'], 'Deferral job identity mismatch')
    dep = load(out / 'before_dependency.json')
    ensure(eligible_dependency(dep), 'Deferral requires exactly one JUnit3 dependency also on production compile classpath')
    native = load(out / 'native_generated.json')
    ensure(native['complete'] is True and len(native['files']) == 2, 'Saved native suite incomplete')
    repo = out / 'repo'
    expected = load(out / 'controller_source_before.json')
    pom = repo / job['module'] / 'pom.xml'
    ensure(verify_integration((out / 'pom_before_integration.xml').read_text(encoding='utf-8'),
                              pom.read_text(encoding='utf-8')) == load(out / 'integration_guard.json'),
           'POM integration differs from archived allowed transformation')
    expected[(Path(job['module']) / 'pom.xml').as_posix()] = sha(pom)
    for row in native['files']:
        p = Path(row['path']).resolve()
        ensure(p.is_relative_to(repo) and sha(p) == row['sha256'], 'Native suite drift')
        expected[p.relative_to(repo).as_posix()] = row['sha256']
    ensure(source_hashes(repo) == expected, 'Unexpected source change before deferral')
    ensure(bytecode(repo / job['module']) == load(out / 'production_generation_baseline.json'),
           'Production bytecode drift before deferral')
    ensure(not (out / 'native_junit_policy.json').exists() and not (out / 'after_dependency.json').exists(),
           'Deferral must precede any JUnit patch or measurement')
    starts = 0
    for p in sorted((out / 'commands').glob('*/plan.json')):
        plan = load(p)
        ensure((p.parent / 'started.json').exists() and (p.parent / 'finished.json').exists(),
               'Unfinished command is not deferrable')
        ensure(load(p.parent / 'finished.json')['returncode'] == 0, 'Failed prior command needs separate review')
        argv = plan['argv']
        ensure('org.pitest:pitest-maven:mutationCoverage' not in argv and 'verify' not in argv,
               'Measurement already attempted')
        starts += int('-jar' in argv)
    ensure(1 <= starts <= 2, 'Expected saved native generation, not a new generation request')
    return {'sample_index_1based': job['sample_index_1based'], 'class_key': job['class_key'],
            'seed': job['seed'], 'reason': DETAIL, 'JUnit3_on_production_compile_classpath': True,
            'archive_sha256': sha(out / 'artifact_manifest.json'),
            'interruption_sha256': sha(out / 'interrupted.json'),
            'dependency_evidence_sha256': sha(out / 'before_dependency.json'),
            'native_suite': native['files'], 'actual_generation_starts': starts,
            'score': None, 'scored_terminal': False, 'measurement_attempted': False,
            'rerun_generation_allowed': False, 'automatic_resume': False,
            'retained_in_fixed300_manifest': True, 'denominator_may_be_reduced': False,
            'full300_claim_allowed': False, 'status': 'DEFERRED_UNSCORED_COMPATIBILITY_REVIEW'}

def receipt(out):
    record = inspect(out)
    path = REGISTRY / f"{record['sample_index_1based']:03d}.json"
    if path.exists():
        ensure(load(path) == record, 'Deferral evidence/decision changed')
    else:
        dump(path, record)
    return record
