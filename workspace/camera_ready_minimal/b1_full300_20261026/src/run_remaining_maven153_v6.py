"""One explicitly sealed E-only continuation. No retry, scheduler or API client.

Only the narrow, reviewed compile-scope JUnit3 guard can quarantine a job and
continue. Every other interruption stops this invocation without auto-resume.
The measurement controller and command bridge are unchanged from admission v3.
"""
import json, msvcrt, shutil, sys, traceback, os, psutil
from pathlib import Path
from datetime import datetime, timezone
from maven_adapter_v1 import R, GuardAbort, sha, dump
from run_maven_b1_v2 import guards
from run_maven_b1_v3 import counters, selected_result, RECOVER, reseal, PUBLIC
from b1_maven_commands_v3 import MavenCommands
from maven_controller_v2 import execute, ensure
from prepare_sandbox_v1 import prepare
from completed_archive_guard_v3 import verify
from pom_input_deferral_policy_v1 import DIRECTORY as POM_QUARANTINE, verify_fixed_set
from projection_io_v1 import publish_json
from non_junit4_deferral_v1 import DETAIL, REGISTRY, receipt

B = R.parent / 'paired49_20261023'
sys.path.insert(0, str(B))
import audit
ADMISSION = R / 'admission_maven_v6.json'
PLAN = R / 'launch_remaining_maven153_v6.json'
COMPLETE = R / 'runtime/remaining_maven153_v6_completion.json'

def load(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))

def now():
    return datetime.now(timezone.utc).isoformat()

def can_quarantine(ex):
    return type(ex) is GuardAbort and str(ex) == DETAIL

def counts(jobs):
    terminal, deferred, unattempted = [], [], []
    for j in jobs:
        i = j['sample_index_1based']
        if j['reused_result'] or j['build_tool'] != 'maven':
            continue
        chosen = selected_result(i)
        base = R / 'jobs' / f'{i:03d}'
        if chosen.exists() and not (chosen.parent / 'interrupted.json').exists():
            terminal.append(i)
        elif (REGISTRY / f'{i:03d}.json').exists() or (POM_QUARANTINE / f'{i:03d}.json').exists():
            deferred.append(i)
        elif not base.exists():
            unattempted.append(i)
    return terminal, deferred, unattempted

def project(state, active=None, admitted=True):
    try:
        jobs = load(R / 'manifest300.json')
        terminal, deferred, unattempted = counts(jobs)
        for j in jobs:
            i = j['sample_index_1based']
            if i in terminal:
                result = load(selected_result(i))
                j['status'] = 'COMPLETED_E1_MAVEN' if result['legacy_process_build'] else 'TERMINAL_PIPELINE_FAILURE'
            elif i in deferred or (R / 'jobs' / f'{i:03d}' / 'interrupted.json').exists():
                j['status'] = 'INTERRUPTED_REVIEW_REQUIRED'
            if i == active:
                j['status'] = 'RUNNING'
        planned, started, fixtures = counters()
        s = load(R / 'status.json')
        s.update(phase='MAVEN V6 / ' + state, updated_utc=now(), new_completed=len(terminal),
                 new_policy_accepted=len(terminal), maven_pending=211-len(terminal),
                 maven_policy_pending=211-len(terminal), maven_unattempted=len(unattempted),
                 maven_deferred_unscored=len(deferred), deferred_sample_indices=deferred,
                 running=int(active is not None), active_sample_index=active,
                 gradle_pending=40, benchmark_admitted=admitted, new_API_calls=0,
                 benchmark_EvoSuite_calls=started, benchmark_EvoSuite_commands_planned=planned,
                 benchmark_EvoSuite_commands_not_started=planned-started,
                 fixture_EvoSuite_calls=fixtures, new_EvoSuite_calls=started+fixtures,
                 GPT_guard='PASS', GPT_guard_checked_utc=LAST_INPUT_GUARD_UTC, reuse49_guard='PASS',
                 disk_free_GB=round(shutil.disk_usage(R).free/1e9, 2),
                 full300_complete=False, automatic_resume=False)
        s['tasks'][5].update(status='IN_PROGRESS', name='Maven v6: giữ nguyên cách đo; tách class chưa hỗ trợ, không gán điểm')
        s['blockers'] = [
            f'Maven chưa có kết quả: {211-len(terminal)}; chưa thử: {len(unattempted)}; giữ lại chưa chấm: {deferred}',
            'Class giữ lại vẫn thuộc mẫu300; không gán0, không giảm denominator hoặc tuyên bố E1-full300 hoàn tất',
            '12 class đầu vào/provider chưa chấm; không sửa POM/JUnit, không giảm mẫu300',
                 'Gradle40 chưa admit benchmark; queue fixture cũ đã SKIPPED và không tự khởi động lại',
            'GPT/API/repeated subset và paper giữ nguyên; STOP và ngưỡng đĩa12GB vẫn áp dụng']
        public = [{k:j[k] for k in PUBLIC} for j in jobs]
        mr = publish_json(R/'runtime/manifest_live300.json', public, label='maven_v6_manifest')
        sr = publish_json(R/'status.json', s, label='maven_v6_status') if mr['published'] else {'published':False}
        if not mr['published'] or not sr['published']:
            audit.log('B1_V6_UI_IO_FAILURE_EXPERIMENT_CONTINUES', manifest=mr, status=sr)
        return s
    except OSError as ex:
        audit.log('B1_V6_UI_IO_FAILURE_EXPERIMENT_CONTINUES', detail=str(ex))
        return None

LAST_INPUT_GUARD_UTC = None

def boundary_guards(lock):
    global LAST_INPUT_GUARD_UTC
    guards(lock)
    LAST_INPUT_GUARD_UTC=now()

def main():
    ensure(not PLAN.exists() and not COMPLETE.exists(), 'Existing invocation: no automatic restart')
    lock = load(ADMISSION)
    boundary_guards(lock)
    ensure(lock['scope'] == 'E-only Maven continuation v6; fixed invalid-input quarantine; unchanged v3 measurement', 'Wrong scope')
    jobs = load(R/'manifest300.json')
    contexts = {j['sample_index_1based']:j for j in load(R/'inputs/context251_v1/manifest.json')}
    remaining = lock['continuation_indices']
    ensure(len(remaining) == 153 and remaining == sorted(set(remaining)), 'Unexpected bounded continuation')
    ensure(lock['invocation_max_new_jobs']==153, 'Unexpected invocation bound')
    for i in remaining:
        ensure(not (R/'jobs'/f'{i:03d}').exists(), 'Already attempted class in continuation')
    mutex = (R/'runtime/dispatcher.lock').open('r+b')
    mutex.seek(0)
    msvcrt.locking(mutex.fileno(), msvcrt.LK_NBLCK, 1)
    completed = quarantined = attempted = 0
    error = None
    code = 0
    try:
        # Recheck all evidence after acquiring the single-worker dispatcher lock.
        boundary_guards(lock)
        # Full old archives have already been sealed and audited. The new
        # admission pins all old manifests/results and the audit receipts.
        # This is anchor revalidation, not another full byte census.
        ensure(verify_fixed_set()==lock['fixed_POM_unscored_indices'],'Frozen POM queue changed')
        for index in [48,49]:
            ensure(load(REGISTRY/f'{index:03d}.json')==lock['fixed_native_JUnit_deferral_receipts'][str(index)], 'Saved JUnit deferral changed')
        plan = {'runner_identity':{'pid':os.getpid(),'create_time':psutil.Process().create_time(),'script':str(Path(__file__).resolve())}, 'started_utc':now(), 'admission_sha256':sha(ADMISSION), 'launcher_sha256':sha(__file__),
                'sample_indices':remaining, 'max_new_jobs':153, 'workers':1,
                'prior_scored_classes':46, 'prior_unscored_deferrals':lock['existing_unscored_deferrals'],
                'measurement_controller':'maven_controller_v2.py', 'command_bridge':'b1_maven_commands_v3.py',
                'reruns_allowed':False, 'automatic_resume':False, 'GPT_API_calls_authorized':0,
                'Gradle_execution_authorized':False, 'paper_edits_authorized':False}
        dump(PLAN, plan)
        audit.log('B1_V6_BOUNDED_CONTINUATION_STARTED', plan_sha256=sha(PLAN), max_new_jobs=153)
        project('EXPLICIT_CONTINUATION_153_PARSEABLE_INPUTS')
        for j in jobs:
            i = j['sample_index_1based']
            if i not in remaining:
                continue
            ensure(i in lock['admitted_sample_indices'] and j['build_tool']=='maven' and not j['reused_result'], 'Job outside E-only admission')
            boundary_guards(lock)
            out = R/'jobs'/f'{i:03d}'
            ensure(not out.exists(), 'Existing job: no implicit retry')
            context = contexts[i]
            job = {**j, **{k:context[k] for k in ['junit_version','testng_version','package','selected_test_fqcn']}}
            def event(kind, **kw):
                with (out/'events.jsonl').open('a', encoding='utf-8') as f:
                    f.write(json.dumps({'at_utc':now(), 'kind':kind, **kw}, ensure_ascii=False)+'\n')
                audit.log('B1_MAVEN_V6_'+kind, sample_index=i, **kw)
                if kind == 'COMMAND_STARTED':
                    project('RUNNING', i)
            try:
                prepare(i, out, R/'inputs/snapshot_v3')
                dump(out/'job_admission.json', {'batch_admission_sha256':sha(ADMISSION), 'job':job, 'started_utc':now()})
                project('RUNNING', i)
                commands = MavenCommands(out, job, ADMISSION, event)
                result = execute(out, job, commands, event)
                verify(out)
                boundary_guards(lock)
                completed += 1
                print(json.dumps({'sample_index':i, 'state':'SCORED_TERMINAL', 'build_gate':result['legacy_process_build'],
                                  'strict_percent':result['legacy_strict_mutation_percent'], 'GPT_API_calls':0}), flush=True)
            except BaseException as ex:
                if out.exists():
                    dump(out/'interrupted.json', {'at_utc':now(), 'error_type':type(ex).__name__, 'detail':str(ex),
                                                  'auto_resume':False, 'score_accepted':False})
                    reseal(out)
                if not can_quarantine(ex):
                    raise
                record = receipt(out)  # Additional evidence predicates must pass; never catches other integrity failures.
                boundary_guards(lock)
                quarantined += 1
                audit.log('B1_V6_UNSCORED_COMPATIBILITY_DEFERRAL', sample_index=i,
                          receipt_sha256=sha(REGISTRY/f'{i:03d}.json'), evidence=record)
                print(json.dumps({'sample_index':i, 'state':'DEFERRED_UNSCORED', 'score':None, 'GPT_API_calls':0}), flush=True)
            attempted += 1
            project('CHECKPOINT')
            if attempted>=lock['invocation_max_new_jobs']:
                break
    except BaseException as ex:
        code = 1
        error = {'type':type(ex).__name__, 'detail':str(ex), 'traceback':traceback.format_exc()}
        audit.log('B1_V6_STOPPED_NO_AUTO_RESUME', error_type=type(ex).__name__, detail=str(ex))
        traceback.print_exc()
    finally:
        state = project('STOPPED_NO_AUTOMATIC_RESUME' if code else 'BOUNDED_INVOCATION_FINISHED', admitted=False)
        terminal, deferred, unattempted = counts(load(R/'manifest300.json'))
        record = {'finished_utc':now(), 'exit_code':code, 'new_scored_this_invocation':completed,
                  'new_deferred_this_invocation':quarantined, 'jobs_finished_this_invocation':attempted,
                  'new_policy_accepted':len(terminal), 'unscored_deferred_indices':deferred,
                  'Maven_unattempted':len(unattempted), 'Maven260_terminal':len(terminal)==211,
                  'full300_complete':False, 'Gradle_benchmark_admitted':False, 'GPT_API_calls':0,
                  'automatic_resume':False, 'error':error,
                  'launch_plan_sha256':sha(PLAN) if PLAN.exists() else None}
        dump(COMPLETE, record)
        audit.log('B1_V6_BOUNDED_INVOCATION_FINISHED', completion_sha256=sha(COMPLETE), evidence=record)
        mutex.seek(0)
        msvcrt.locking(mutex.fileno(), msvcrt.LK_UNLCK, 1)
        mutex.close()
    return code

if __name__ == '__main__':
    sys.exit(main())
