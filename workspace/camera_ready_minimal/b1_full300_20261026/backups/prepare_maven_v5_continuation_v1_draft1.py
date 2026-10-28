"""Prepare and seal one new bounded continuation after absent-v4 audit.
Generation, measurement and the narrow deferral policy stay byte-identical.
No experiment or process is launched here.
"""
import ast, copy, difflib, json, sys
from pathlib import Path
from datetime import datetime, timezone
from maven_adapter_v1 import R, sha, dump
from run_maven_b1_v2 import guards
from run_maven_b1_v3 import selected_result
from completed_archive_guard_v3 import verify, REVIEW

B=R.parent/'paired49_20261023'
sys.path.insert(0,str(B))
import audit

def load(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))

def main():
    old=load(R/'admission_maven_v4.json')
    guards(old)
    review=load(REVIEW/'result.json')
    assert review['status']=='PASS_SAVED_TERMINAL_RECOVERED_NO_RERUN'
    assert review['verified_new_terminal_count']==42 and review['Maven_unattempted']==167
    assert not (R/'runtime/remaining_maven183_v4_completion.json').exists()
    source=R/'src/run_remaining_maven183_v4.py'
    target=R/'src/run_remaining_maven167_v5.py'
    assert not target.exists() and not (R/'admission_maven_v5.json').exists()
    original=source.read_text(encoding='utf-8')
    text=original.replace('remaining_maven183_v4','remaining_maven167_v5').replace('admission_maven_v4.json','admission_maven_v5.json')
    text=text.replace('from checkpoint_archive_guard_v2 import verify','from completed_archive_guard_v3 import verify')
    text=text.replace('import json, msvcrt, shutil, sys, traceback','import json, msvcrt, shutil, sys, traceback, os, psutil')
    text=text.replace('E-only Maven continuation v4; scheduling deferral only; unchanged v3 measurement',
                      'E-only Maven continuation v5; saved066 externally reconciled; unchanged v3 measurement')
    text=text.replace('len(remaining) == 183','len(remaining) == 167')
    text=text.replace("'prior_scored_classes':27, 'prior_unscored_deferrals':[48]", "'prior_scored_classes':42, 'prior_unscored_deferrals':[48,49]")
    text=text.replace("plan = {'started_utc':now(),", "plan = {'runner_identity':{'pid':os.getpid(),'create_time':psutil.Process().create_time(),'script':str(Path(__file__).resolve())}, 'started_utc':now(),")
    text=text.replace("ensure(receipt(R/'jobs/048') == load(REGISTRY/'048.json'), 'Known048 deferral drift')",
                      "ensure(receipt(R/'jobs/048') == load(REGISTRY/'048.json'), 'Known048 deferral drift')\n        ensure(receipt(R/'jobs/049') == load(REGISTRY/'049.json'), 'Known049 deferral drift')")
    text=text.replace('EXPLICIT_CONTINUATION_183','EXPLICIT_CONTINUATION_167')
    text=text.replace('MAVEN V4 / ','MAVEN V5 / ').replace('Maven v4:','Maven v5:')
    text=text.replace('maven_v4_','maven_v5_').replace('B1_V4_','B1_V5_').replace('B1_MAVEN_V4_','B1_MAVEN_V5_')
    ast.parse(text)
    with target.open('x',encoding='utf-8') as f:
        f.write(text)
    difference=''.join(difflib.unified_diff(original.splitlines(True),text.splitlines(True),fromfile=source.name,tofile=target.name))
    diff=R/'audit/maven_v5_dispatch_only.diff'
    with diff.open('x',encoding='utf-8') as f:
        f.write(difference)
    # Pure AST comparison: the actual experiment call and quarantine rule are
    # unchanged; completed-archive verification/identity/limits are dispatch only.
    trees=[ast.parse(s) for s in [original,text]]
    for name in ['can_quarantine','counts']:
        nodes=[next(n for n in t.body if isinstance(n,ast.FunctionDef) and n.name==name) for t in trees]
        assert ast.dump(nodes[0],include_attributes=False)==ast.dump(nodes[1],include_attributes=False)
    def calls(tree,name):
        return [ast.dump(n,include_attributes=False) for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id==name]
    for name in ['execute','MavenCommands','prepare','receipt','reseal']:
        before=calls(trees[0],name)
        after=calls(trees[1],name)
        if name=='receipt':
            assert len(after)==len(before)+1
        else:
            assert before==after, 'Experiment/deferral call changed: '+name
    jobs=load(R/'manifest300.json')
    completed=review['verified_new_terminal_indices']
    remaining=[j['sample_index_1based'] for j in jobs if j['sample_index_1based'] in old['admitted_sample_indices']
               and j['sample_index_1based'] not in completed+[48,49]]
    assert len(remaining)==167 and remaining==sorted(set(remaining))
    assert all(not (R/'jobs'/f'{i:03d}').exists() for i in remaining)
    checks={}
    for i in completed:
        checks[str(i)]=verify(R/'jobs'/f'{i:03d}')
        selected=selected_result(i)
        if selected.parent!=R/'jobs'/f'{i:03d}':
            checks[selected.parent.name]=verify(selected.parent)
    immutable_experiment_sources=['maven_controller_v2.py','b1_maven_commands_v3.py','native_junit_policy_candidate_v1.py',
                                  'process_supervisor_v1.py','classpath_transport_v1.py','measurement_parser_v1.py']
    for name in immutable_experiment_sources:
        path=R/'src'/name
        assert old['code_and_input_hashes'][str(path)]==sha(path)
    validation=R/'validation/maven_v5_dispatch_preparation_v1/result.json'
    dump(validation,{'status':'PASS_DISPATCH_ONLY_CHANGE_AFTER_SAVED_CHECKPOINT_AUDIT',
         'source_sha256':sha(target),'original_source_sha256':sha(source),'diff_sha256':sha(diff),
         'unchanged_quarantine_and_count_AST':True,'unchanged_experiment_calls':True,
         'unchanged_experiment_sources':immutable_experiment_sources,'verified_archives':checks,
         'completed_new_indices':completed,'deferred_unscored':[48,49],'remaining_indices':remaining,
         'new_JVM_processes':0,'GPT_API_calls':0,'new_EvoSuite_calls':0})
    lock=copy.deepcopy(old)
    lock.update(created_utc=datetime.now(timezone.utc).isoformat(),
                scope='E-only Maven continuation v5; saved066 externally reconciled; unchanged v3 measurement',
                prior_admission_sha256=sha(R/'admission_maven_v4.json'),continuation_indices=remaining,
                existing_terminal_indices=completed,existing_unscored_deferrals=[48,49],
                first_invocation_max_jobs=167,automatic_resume=False,retry_interrupted_jobs=False,
                scientific_measurement_changes=0,prior_invocation_exit_code=None,
                prior_invocation_termination='runner absent; no completion receipt; cause unknown; saved066 terminal independently reconciled')
    paths=[target,Path(__file__),diff,validation,R/'src/completed_archive_guard_v3.py',
           R/'src/reconcile_absent_v4_runner_v1.py',R/'src/audit_maven_v4_postbatch_v1.py',
           REVIEW/'result.json',REVIEW/'job066_recovered_archive.json',REVIEW/'observation.json',
           REGISTRY_PATH(49)]
    for i in completed:
        selected=selected_result(i)
        paths.append(selected)
        if (selected.parent/'artifact_manifest.json').exists():
            paths.append(selected.parent/'artifact_manifest.json')
    lock['code_and_input_hashes'].update({str(p.resolve()):sha(p) for p in paths})
    dump(R/'admission_maven_v5.json',lock)
    guards(lock)
    audit.log('B1_MAVEN_V5_EXPLICIT_CONTINUATION_ADMITTED',admission_sha256=sha(R/'admission_maven_v5.json'),
              validation_sha256=sha(validation),remaining=167,reconciled_saved_terminal=66,
              no_rerun_of066=True,measurement_code_changed=False,GPT_API_calls=0)
    print('PASS: new167-class continuation sealed; no JVM/API started; actual066 pipeline failure retained without rerun')

def REGISTRY_PATH(i):
    return R/'runtime/non_junit4_deferrals_v1'/f'{i:03d}.json'

if __name__=='__main__':
    main()
