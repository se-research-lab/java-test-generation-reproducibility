"""Reconcile an absent runner using saved evidence only; never rerun a tool.
Original invocation, result and raw files are not modified. Its missing exit
receipt is not fabricated. A separately sealed archive can close checkpoint066.
"""
import json, msvcrt, os, sys
from datetime import datetime, timezone
from pathlib import Path
import psutil
from maven_adapter_v1 import R, sha, dump
from run_maven_b1_v2 import guards
from run_maven_b1_v3 import selected_result, counters, PUBLIC
from checkpoint_archive_guard_v2 import verify
from measurement_parser_v1 import parse
from maven_controller_v2 import source_hashes, bytecode
from pom_integration_guard_v1 import verify as verify_integration
from non_junit4_deferral_v1 import inspect, REGISTRY
from audit_maven_v4_postbatch_v1 import generation_checks
from projection_io_v1 import publish_json

B=R.parent/'paired49_20261023'
sys.path.insert(0,str(B))
import audit
OUT=R/'audit/absent_v4_runner_reconciliation_v1'

def load(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))

def now():
    return datetime.now(timezone.utc).isoformat()

def process_observation():
    matches=[]
    java=[]
    denied=[]
    targets={'run_remaining_maven183_v4.py','run_maven_b1_v3.py','serve_v2.py'}
    for p in psutil.process_iter(['pid','name']):
        name=(p.info['name'] or '').lower()
        if name in {'java.exe','javaw.exe'}:
            java.append(p.info)
        if name not in {'python.exe','pythonw.exe'} or p.pid==os.getpid():
            continue
        try:
            arguments=p.cmdline()
        except (psutil.NoSuchProcess,psutil.AccessDenied):
            denied.append(p.pid)
            continue
        scripts=[Path(s).name for s in arguments if Path(s).name in targets]
        if scripts:
            matches.append({'pid':p.pid,'scripts':scripts,'create_time':p.create_time()})
    return {'at_utc':now(),'matching_B1_runner_or_monitor':matches,'Java_processes':java,
            'Python_processes_with_unavailable_argv':denied}

def census(folder):
    rows=[]
    for p in sorted(folder.rglob('*')):
        if not p.is_file() or 'temp' in p.relative_to(folder).parts:
            continue
        assert not p.is_symlink()
        rows.append({'relative':p.relative_to(folder).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size})
    return rows

def main():
    assert not OUT.exists(), 'Preserve prior reconciliation; no overwrite'
    assert not (R/'runtime/remaining_maven183_v4_completion.json').exists(), 'Use the actual completion if present'
    observation=process_observation()
    assert not observation['matching_B1_runner_or_monitor'] and not observation['Java_processes'], 'Runner/monitor or Java still active; no reconciliation'
    assert not observation['Python_processes_with_unavailable_argv'], 'Cannot establish absent runner'
    with (R/'runtime/dispatcher.lock').open('r+b') as mutex:
        mutex.seek(0)
        msvcrt.locking(mutex.fileno(),msvcrt.LK_NBLCK,1)
        try:
            lock=load(R/'admission_maven_v4.json')
            guards(lock)
            jobs=load(R/'manifest300.json')
            ctx={j['sample_index_1based']:j for j in load(R/'inputs/context251_v1/manifest.json')}
            folder=R/'jobs/066'
            assert not (folder/'artifact_manifest.json').exists() and not (folder/'interrupted.json').exists()
            before=census(folder)
            OUT.mkdir(parents=True,exist_ok=False)
            dump(OUT/'observation.json',{'process_observation':observation,'dispatcher_lock_acquired':True,
                 'v4_completion_receipt_present':False,'v4_process_exit_code':None,
                 'cause_of_process_absence':'UNKNOWN_FROM_AVAILABLE_EVIDENCE',
                 'new_JVM_processes':0,'new_EvoSuite_calls':0,'GPT_API_calls':0,
                 'scope':'recover saved terminal evidence only; no generation, measurement or raw job modification'})
            dump(OUT/'job066_census_before.json',before)
            j=next(j for j in jobs if j['sample_index_1based']==66)
            metadata=load(folder/'job_admission.json')
            job=metadata['job']
            assert job['class_key']==j['class_key'] and job['seed']==j['seed']==20261089
            assert metadata['batch_admission_sha256']==sha(R/'admission_maven_v4.json')
            result=load(folder/'result.json')
            assert result['terminal'] and result['sample_index_1based']==66 and result['class_key']==j['class_key']
            assert result['source_guard']=='PASS' and result['production_bytecode_guard']=='PASS'
            module=folder/'repo'/j['module']
            c=ctx[66]
            parsed=parse(module,j['focal_class'],c['package'],c['selected_test_fqcn'],result['legacy_process_build'])
            assert all(result.get(k)==v for k,v in parsed.items()), 'Raw parser reconstruction mismatch'
            assert result['legacy_process_build']==0 and result['legacy_strict_mutation_percent']==0
            assert result['mutation_score_percent'] is None and result['strict_suite_evidence'] is True
            assert result['strict_measurement_evidence'] is False and result['measurement_attempted'] is True
            events=[json.loads(s) for s in (folder/'events.jsonl').read_text(encoding='utf-8').splitlines()]
            assert events[-1]['kind']=='JOB_TERMINAL' and events[-1]['result_sha256']==sha(folder/'result.json')
            ledger=audit.events()
            global_terminal=[e for e in ledger if e['kind']=='B1_MAVEN_V4_JOB_TERMINAL' and e.get('sample_index')==66]
            assert len(global_terminal)==1 and global_terminal[0]['result_sha256']==sha(folder/'result.json')
            command_checks=[]
            for p in sorted((folder/'commands').glob('*/plan.json')):
                plan=load(p)
                finish=load(p.parent/'finished.json')
                assert (p.parent/'started.json').exists()
                local=[e for e in events if e['kind']=='COMMAND_PLAN' and Path(e['path'])==p.parent]
                anchored=[e for e in ledger if e['kind']=='B1_MAVEN_V4_COMMAND_PLAN' and e.get('sample_index')==66 and Path(e['path'])==p.parent]
                assert len(local)==len(anchored)==1 and local[0]['plan_sha256']==anchored[0]['plan_sha256']==sha(p)
                assert finish['stdout_sha256']==sha(p.parent/'stdout.txt') and finish['stderr_sha256']==sha(p.parent/'stderr.txt')
                for value,h in plan.get('input_hashes',{}).items():
                    assert sha(value)==h
                command_checks.append({'command':p.parent.name,'returncode':finish['returncode'],
                     'stdout_sha256':finish['stdout_sha256'],'stderr_sha256':finish['stderr_sha256']})
            assert len(command_checks)==7
            assert [x['returncode'] for x in command_checks]==[0,0,0,0,0,0,1]
            last_stdout=(folder/'commands/007/stdout.txt').read_text(encoding='utf-8')
            last_stderr=(folder/'commands/007/stderr.txt').read_text(encoding='utf-8')
            assert 'Coverage generator Minion exited abnormally due to UNKNOWN_ERROR' in last_stdout+last_stderr
            generation=generation_checks(folder,job)
            assert len(generation)==1 and generation[0]['started']
            native=load(folder/'native_generated.json')
            assert native['complete'] and len(native['files'])==2
            expected=load(folder/'controller_source_before.json')
            pom=module/'pom.xml'
            policy=load(folder/'policy_applied.json')
            native_policy=load(folder/'native_junit_policy.json')
            assert not native_policy['changed'] and policy['changes']==[]
            assert sha(pom)==policy['after_sha256']==policy['before_sha256']==native_policy['original_sha256']
            assert sha(folder/'backup_before_policy/pom.xml')==sha(pom)
            assert verify_integration((folder/'pom_before_integration.xml').read_text(encoding='utf-8'),pom.read_text(encoding='utf-8'))==load(folder/'integration_guard.json')
            expected[pom.relative_to(folder/'repo').as_posix()]=sha(pom)
            for row in native['files']:
                p=Path(row['path'])
                assert sha(p)==row['sha256']
                expected[p.relative_to(folder/'repo').as_posix()]=row['sha256']
            assert source_hashes(folder/'repo')==expected
            assert bytecode(module)==load(folder/'production_generation_baseline.json')
            for row in load(folder/'before_dependency.json')['classpath']+load(folder/'before_dependency.json')['compile_classpath']:
                assert sha(row['absolute_path'])==row['sha256']
            old_checks={}
            terminal=[]
            for candidate in jobs:
                i=candidate['sample_index_1based']
                if candidate['reused_result'] or candidate['build_tool']!='maven' or i==66:
                    continue
                selected=selected_result(i)
                if not selected.exists():
                    continue
                base=R/'jobs'/f'{i:03d}'
                old_checks[str(i)]={'base':verify(base)}
                if selected.parent!=base:
                    old_checks[str(i)]['selected']=verify(selected.parent)
                r=load(selected)
                cc=ctx[i]
                rebuilt=parse(selected.parent/'repo'/candidate['module'],candidate['focal_class'],cc['package'],cc['selected_test_fqcn'],r['legacy_process_build'])
                assert all(r.get(k)==v for k,v in rebuilt.items())
                terminal.append(i)
            assert len(terminal)==41
            deferrals={str(i):inspect(R/'jobs'/f'{i:03d}') for i in [48,49]}
            assert all(deferrals[str(i)]==load(REGISTRY/f'{i:03d}.json') for i in [48,49])
            assert census(folder)==before, 'Job066 changed during read-only reconciliation'
            archive=OUT/'job066_recovered_archive.json'
            dump(archive,before)
            record={'status':'PASS_SAVED_TERMINAL_RECOVERED_NO_RERUN','at_utc':now(),
                    'sample_index_1based':66,'class_key':j['class_key'],'seed':j['seed'],
                    'original_job':'jobs/066','original_result_sha256':sha(folder/'result.json'),
                    'external_archive_path':archive.relative_to(R).as_posix(),'external_archive_sha256':sha(archive),
                    'raw_job_modified':False,'new_generation_calls':0,'new_measurement_calls':0,'GPT_API_calls':0,
                    'process_exit_receipt_reconstructed':False,'process_absence_cause':'UNKNOWN_FROM_AVAILABLE_EVIDENCE',
                    'policy_result':'retain actual terminal pipeline failure; strict policy0; raw mutation percentage unavailable',
                    'legacy_process_build':0,'legacy_strict_mutation_percent':0.0,'mutation_score_percent':None,
                    'verified_new_terminal_indices':sorted(terminal+[66]),'verified_new_terminal_count':42,
                    'reused_E49':49,'deferred_unscored_indices':[48,49],'Maven_unattempted':167,
                    'Gradle_unattempted':40,'full300_complete':False,'command_checks':command_checks,
                    'generation_checks':generation,'original_archive_checks':old_checks,'deferral_checks':deferrals}
            dump(OUT/'result.json',record)
            for x in jobs:
                if x['sample_index_1based'] in terminal+[66]:
                    rr=load(selected_result(x['sample_index_1based']))
                    x['status']='COMPLETED_E1_MAVEN' if rr['legacy_process_build'] else 'TERMINAL_PIPELINE_FAILURE'
                elif x['sample_index_1based'] in [48,49]:
                    x['status']='INTERRUPTED_REVIEW_REQUIRED'
            planned,started,fixtures=counters()
            s=load(R/'status.json')
            s.update(phase='V4_RUNNER_ABSENT_RECONCILED_IDLE_NO_AUTO_RESUME',updated_utc=now(),running=0,
                     active_sample_index=None,benchmark_admitted=False,new_completed=42,new_policy_accepted=42,
                     maven_pending=169,maven_policy_pending=169,maven_unattempted=167,
                     maven_deferred_unscored=2,deferred_sample_indices=[48,49],new_API_calls=0,
                     benchmark_EvoSuite_commands_planned=planned,benchmark_EvoSuite_calls=started,
                     fixture_EvoSuite_calls=fixtures,new_EvoSuite_calls=started+fixtures,
                     full300_complete=False,automatic_resume=False,GPT_guard='PASS',reuse49_guard='PASS')
            s['blockers']=['Runner v4/monitor không còn; không có completion/exit receipt; nguyên nhân chưa xác định',
                           'Đã khôi phục terminal066 bằng raw log/hash/source/native/bytecode; không chạy lại generation/measurement',
                           '42 Maven mới +49 tái sử dụng;048/049 chưa chấm;167 Maven chưa thử;40 Gradle chưa admit',
                           'Không tự restart v4; mọi continuation mới cần admission riêng; GPT/repeated/paper giữ nguyên']
            mr=publish_json(R/'runtime/manifest_live300.json',[{k:x[k] for k in PUBLIC} for x in jobs],label='absent_v4_reconciliation_manifest')
            sr=publish_json(R/'status.json',s,label='absent_v4_reconciliation_status') if mr['published'] else {'published':False}
            dump(OUT/'ui_publication.json',{'manifest':mr,'status':sr})
            audit.log('B1_V4_ABSENT_RUNNER_CHECKPOINT_RECONCILED',result_sha256=sha(OUT/'result.json'),
                      recovered_archive_sha256=sha(archive),verified_new_terminal=42,
                      new_generation_calls=0,new_measurement_calls=0,GPT_API_calls=0,raw_job_modified=False)
            print(json.dumps({k:record[k] for k in ['status','verified_new_terminal_count','Maven_unattempted','deferred_unscored_indices','GPT_API_calls']},indent=2))
        finally:
            mutex.seek(0)
            msvcrt.locking(mutex.fileno(),msvcrt.LK_UNLCK,1)

if __name__=='__main__':
    main()
