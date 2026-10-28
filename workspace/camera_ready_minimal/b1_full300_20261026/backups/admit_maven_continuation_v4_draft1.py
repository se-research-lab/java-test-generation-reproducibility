"""Read existing evidence, test quarantine boundaries and seal one new dispatcher.
No Java, Maven, Gradle, EvoSuite or API execution is performed here.
"""
import ast, copy, json, msvcrt, sys, zipfile
from pathlib import Path
from datetime import datetime, timezone
from maven_adapter_v1 import R, GuardAbort, sha, dump
from run_maven_b1_v2 import guards
from run_maven_b1_v3 import selected_result, counters
from checkpoint_archive_guard_v2 import verify
from non_junit4_deferral_v1 import eligible_dependency, inspect, receipt, REGISTRY, DETAIL
from run_remaining_maven183_v4 import can_quarantine, counts

B = R.parent/'paired49_20261023'
sys.path.insert(0, str(B))
import audit

def load(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))

def main():
    destination = R/'admission_maven_v4.json'
    assert not destination.exists(), 'Admission already sealed; do not overwrite'
    old = load(R/'admission_maven_v3.json')
    guards(old)
    with (R/'runtime/dispatcher.lock').open('r+b') as mutex:
        mutex.seek(0)
        msvcrt.locking(mutex.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            jobs = load(R/'manifest300.json')
            indices = old['admitted_sample_indices']
            assert len(indices)==211
            archives = {}
            done = []
            for i in indices:
                p = selected_result(i)
                if p.exists():
                    assert not (p.parent/'interrupted.json').exists()
                    archives[str(i)] = verify(R/'jobs'/f'{i:03d}')
                    if p.parent != R/'jobs'/f'{i:03d}':
                        archives[p.parent.name] = verify(p.parent)
                    done.append(i)
            assert len(done)==27 and max(done)==47
            review = inspect(R/'jobs/048')
            dep = load(R/'jobs/048/before_dependency.json')
            junit = next(x for x in dep['classpath'] if x['path'].startswith('junit/junit/'))
            assert junit['path']=='junit/junit/3.8.1/junit-3.8.1.jar'
            with zipfile.ZipFile(junit['absolute_path']) as z:
                assert 'junit/framework/TestCase.class' in z.namelist()
                assert 'org/junit/Test.class' not in z.namelist()
            assert sha(junit['absolute_path'])==junit['sha256']
            assert load(R/'runtime/remaining_maven198_v1_completion.json')['exit_code']==1
            assert load(R/'runtime/gradle_native_after_maven_v1/state.json')['status']=='SKIPPED_MAVEN_NOT_SUCCESSFULLY_COMPLETE'

            checks = ['known048 saved archive/source/native/bytecode/finished-command preconditions pass',
                      'JUnit3 JAR lacks JUnit4 API and is on compile closure',
                      'previous invocation stopped and dependent Gradle queue skipped']
            base = {'classpath':[{'path':'junit/junit/3.8.1/junit-3.8.1.jar','sha256':'a'}],
                    'compile_classpath':[{'path':'junit/junit/3.8.1/junit-3.8.1.jar','sha256':'a'}]}
            assert eligible_dependency(base)
            bad = []
            x=copy.deepcopy(base);x['compile_classpath']=[];bad.append(('test-only JUnit3 requires different review',x))
            x=copy.deepcopy(base);x['compile_classpath'][0]['sha256']='b';bad.append(('compile/test JAR mismatch',x))
            x=copy.deepcopy(base);x['classpath']=[];bad.append(('no resolved JUnit',x))
            for version in ['4.13.2','5.0','30.0']:
                p=f'junit/junit/{version}/junit-{version}.jar'
                bad.append(('reject major version'+version,{'classpath':[{'path':p,'sha256':'a'}], 'compile_classpath':[{'path':p,'sha256':'a'}]}))
            x=copy.deepcopy(base);x['classpath']*=2;bad.append(('ambiguous multiple JUnit dependencies',x))
            for label,value in bad:
                assert not eligible_dependency(value)
                checks.append(label)
            assert can_quarantine(GuardAbort(DETAIL))
            class DifferentGuard(GuardAbort):
                pass
            for ex in [GuardAbort('Production bytecode changed'), GuardAbort(DETAIL+'!'),
                       RuntimeError(DETAIL), DifferentGuard(DETAIL), KeyboardInterrupt()]:
                assert not can_quarantine(ex)
            checks.append('only exact GuardAbort/message; reject integrity, other exceptions, subclasses and interruption')
            receipt(R/'jobs/048')
            terminal, deferred, remaining = counts(jobs)
            assert terminal==done and deferred==[48] and len(remaining)==183
            assert remaining==sorted(set(indices)-set(done)-{48})
            assert len(done)+len(deferred)+len(remaining)==211
            assert len([j for j in jobs if j['reused_result']])==49
            assert len([j for j in jobs if j['build_tool']=='gradle'])==40
            assert 49+27+1+183+40==300
            assert not (R/'jobs/048/result.json').exists()
            checks.append('complete fixed300 census; no missing-class zero or denominator reduction')
            source=R/'src/run_remaining_maven183_v4.py'
            ast.parse(source.read_text(encoding='utf-8'))
            for p in [R/'src/maven_controller_v2.py',R/'src/b1_maven_commands_v3.py',
                      R/'src/native_junit_policy_candidate_v1.py',R/'adapters/e49_measurement_policy.py']:
                assert old['code_and_input_hashes'][str(p)]==sha(p)
            checks.append('measurement/command/nativeJUnit/E49-policy hashes unchanged from v3')
            validation={'status':'PASS_PURE_DISPATCH_ADMISSION_GUARDS','at_utc':datetime.now(timezone.utc).isoformat(),
                        'checks':checks,'existing_scored_classes':done,'deferred_unscored':[48],
                        'new_continuation_indices':remaining,'new_JVM_processes':0,'GPT_API_calls':0,
                        'archive_checks':archives,'known048_review':review}
            report=R/'validation/maven_dispatch_v4/result.json'
            dump(report,validation)
            paths=[Path(__file__),source,R/'src/non_junit4_deferral_v1.py',
                   R/'backups/non_junit4_deferral_v1_draft1.py',R/'NON_JUNIT4_DEFERRAL_V1.md',
                   report,REGISTRY/'048.json',R/'jobs/048/artifact_manifest.json',
                   R/'jobs/048/interrupted.json',R/'runtime/remaining_maven198_v1_completion.json',
                   R/'runtime/gradle_native_after_maven_v1/state.json']
            for i in done:
                p=selected_result(i)
                paths.extend([p,p.parent/'artifact_manifest.json'])
            lock=copy.deepcopy(old)
            lock.update(created_utc=datetime.now(timezone.utc).isoformat(),
                        scope='E-only Maven continuation v4; scheduling deferral only; unchanged v3 measurement',
                        prior_admission_sha256=sha(R/'admission_maven_v3.json'),
                        continuation_indices=remaining,existing_terminal_indices=done,
                        existing_unscored_deferrals=[48],first_invocation_max_jobs=183,
                        retry_interrupted_jobs=False,automatic_resume=False,
                        deferral_rule='exact compile-scope JUnit3 guard with complete archived evidence; no score assigned',
                        scientific_measurement_changes=0)
            lock['code_and_input_hashes'].update({str(p.resolve()):sha(p) for p in paths})
            dump(destination,lock)
            guards(lock)
            audit.log('B1_V4_DISPATCH_ADMITTED_UNCHANGED_MEASUREMENT',admission_sha256=sha(destination),
                      validation_sha256=sha(report),prior_scored=27,deferred_unscored=[48],
                      new_jobs=183,workers=1,GPT_API_calls=0)
            print(json.dumps({'status':validation['status'],'checks':len(checks),'prior_scored':27,
                              'deferred_unscored':[48],'unattempted_Maven':183,'Gradle_not_admitted':40,
                              'new_JVM_processes':0,'GPT_API_calls':0},indent=2))
        finally:
            mutex.seek(0)
            msvcrt.locking(mutex.fileno(),msvcrt.LK_UNLCK,1)

if __name__=='__main__':
    main()
