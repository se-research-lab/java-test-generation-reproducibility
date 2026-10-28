"""Seal remaining parseable Maven inputs after frozen-POM review.
Only dispatch/membership-of-unscored-queue changes. Experiment code unchanged.
"""
import ast, copy, difflib, json, sys
from pathlib import Path
from datetime import datetime, timezone
from maven_adapter_v1 import R, sha, dump
from run_maven_b1_v2 import guards
from run_maven_b1_v3 import selected_result
from pom_input_deferral_policy_v1 import register_fixed_set, verify_fixed_set, DIRECTORY, EXPECTED

B=R.parent/'paired49_20261023'
sys.path.insert(0,str(B))
import audit

def load(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))

def main():
    previous=R/'admission_maven_v5.json'
    old=load(previous)
    guards(old)
    completion=load(R/'runtime/remaining_maven167_v5_completion.json')
    assert completion['exit_code']==1 and completion['new_policy_accepted']==46
    assert completion['jobs_finished_this_invocation']==4
    report=load(R/'audit/pom_input_deferrals_v2/result.json')
    assert report['status']=='PASS_READONLY_FROZEN_POM_REVIEW'
    assert report['v5_completion_sha256']==sha(R/'runtime/remaining_maven167_v5_completion.json')
    assert load(R/'runtime/gradle_native_after_v5_v1/state.json')['state']=='SKIPPED_BOUNDED10_NOT_CLEANLY_COMPLETE'
    source=R/'src/run_remaining_maven167_v5.py'
    target=R/'src/run_remaining_maven153_v6.py'
    assert not target.exists() and not (R/'admission_maven_v6.json').exists()
    original=source.read_text(encoding='utf-8')
    text=original.replace('remaining_maven167_v5','remaining_maven153_v6').replace('admission_maven_v5.json','admission_maven_v6.json')
    text=text.replace('from completed_archive_guard_v3 import verify, reuse_verified_checkpoint, reuse_verified_deferral',
                      'from completed_archive_guard_v3 import verify\nfrom pom_input_deferral_policy_v1 import DIRECTORY as POM_QUARANTINE, verify_fixed_set')
    text=text.replace("elif (REGISTRY / f'{i:03d}.json').exists():", "elif (REGISTRY / f'{i:03d}.json').exists() or (POM_QUARANTINE / f'{i:03d}.json').exists():")
    text=text.replace("'E-only Maven continuation v5; saved066 externally reconciled; unchanged v3 measurement'",
                      "'E-only Maven continuation v6; fixed invalid-input quarantine; unchanged v3 measurement'")
    text=text.replace('len(remaining) == 167','len(remaining) == 153').replace("lock['invocation_max_new_jobs']==10","lock['invocation_max_new_jobs']==153")
    start=text.index('        for i in lock[\'existing_terminal_indices\']:')
    end=text.index('        plan = ',start)
    text=text[:start]+'''        # Full old archives have already been sealed and audited. The new
        # admission pins all old manifests/results and the audit receipts.
        # This is anchor revalidation, not another full byte census.
        ensure(verify_fixed_set()==lock['fixed_POM_unscored_indices'],'Frozen POM queue changed')
        for index in [48,49]:
            ensure(load(REGISTRY/f'{index:03d}.json')==lock['fixed_native_JUnit_deferral_receipts'][str(index)], 'Saved JUnit deferral changed')
''' +text[end:]
    text=text.replace("'sample_indices':remaining[:10], 'eligible_remaining_indices':remaining, 'max_new_jobs':10, 'workers':1,",
                      "'sample_indices':remaining, 'max_new_jobs':153, 'workers':1,")
    text=text.replace("'prior_scored_classes':42, 'prior_unscored_deferrals':[48,49]",
                      "'prior_scored_classes':46, 'prior_unscored_deferrals':lock['existing_unscored_deferrals']")
    text=text.replace('max_new_jobs=10','max_new_jobs=153').replace('EXPLICIT_CONTINUATION_10_OF_167','EXPLICIT_CONTINUATION_153_PARSEABLE_INPUTS')
    text=text.replace('MAVEN V5 / ','MAVEN V6 / ').replace('Maven v5:','Maven v6:')
    text=text.replace('maven_v5_','maven_v6_').replace('B1_V5_','B1_V6_').replace('B1_MAVEN_V5_','B1_MAVEN_V6_')
    text=text.replace("'Gradle40 chưa admit benchmark; queue fixture cũ đã SKIPPED và không tự khởi động lại',",
                      "'12 class đầu vào/provider chưa chấm; không sửa POM/JUnit, không giảm mẫu300',\n                 'Gradle40 chưa admit benchmark; queue fixture cũ đã SKIPPED và không tự khởi động lại',")
    ast.parse(text)
    with target.open('x',encoding='utf-8') as f:
        f.write(text)
    diff=R/'audit/maven_v6_dispatch_only.diff'
    with diff.open('x',encoding='utf-8') as f:
        f.write(''.join(difflib.unified_diff(original.splitlines(True),text.splitlines(True),fromfile=source.name,tofile=target.name)))
    before,after=ast.parse(original),ast.parse(text)
    for name in ['can_quarantine','boundary_guards']:
        a=next(n for n in before.body if isinstance(n,ast.FunctionDef) and n.name==name)
        b=next(n for n in after.body if isinstance(n,ast.FunctionDef) and n.name==name)
        assert ast.dump(a,include_attributes=False)==ast.dump(b,include_attributes=False)
    for name in ['execute','MavenCommands','prepare','receipt','reseal']:
        def nodes(tree):
            return [ast.dump(n,include_attributes=False) for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id==name]
        assert nodes(before)==nodes(after),'Experiment/deferral call changed: '+name
    register_fixed_set()
    assert verify_fixed_set()==EXPECTED
    jobs=load(R/'manifest300.json')
    completed=[]
    for j in jobs:
        if j['reused_result'] or j['build_tool']!='maven':
            continue
        selected=selected_result(j['sample_index_1based'])
        if selected.exists() and not (selected.parent/'interrupted.json').exists():
            completed.append(j['sample_index_1based'])
    assert len(completed)==46
    unscored=sorted([48,49]+EXPECTED)
    remaining=[i for i in old['admitted_sample_indices'] if i not in completed+unscored]
    assert len(remaining)==153 and all(not (R/'jobs'/f'{i:03d}').exists() for i in remaining)
    assert 49+len(completed)+len(unscored)+len(remaining)+40==300
    assert remaining==sorted(set(remaining)) and min(remaining)==74
    locked_sources=['maven_controller_v2.py','b1_maven_commands_v3.py','native_junit_policy_candidate_v1.py',
                    'process_supervisor_v1.py','classpath_transport_v1.py','measurement_parser_v1.py']
    for name in locked_sources:
        p=R/'src'/name
        assert old['code_and_input_hashes'][str(p)]==sha(p)
    validation=R/'validation/maven_v6_dispatch_preparation_v1/result.json'
    dump(validation,{'status':'PASS_FIXED_INPUT_DEFERRALS_DISPATCH_ONLY','source_sha256':sha(target),
         'original_source_sha256':sha(source),'diff_sha256':sha(diff),'unchanged_experiment_calls':True,
         'unchanged_experiment_source_hashes':{name:sha(R/'src'/name) for name in locked_sources},
         'verified_prior_new_results':46,'fixed_unscored_indices':unscored,'remaining_indices':remaining,
         'fixed300_count':300,'new_JVM_processes':0,'GPT_API_calls':0,'original_source_or_POM_edits':0})
    lock=copy.deepcopy(old)
    lock.update(created_utc=datetime.now(timezone.utc).isoformat(),
                scope='E-only Maven continuation v6; fixed invalid-input quarantine; unchanged v3 measurement',
                prior_admission_sha256=sha(previous),continuation_indices=remaining,existing_terminal_indices=completed,
                existing_unscored_deferrals=unscored,fixed_POM_unscored_indices=EXPECTED,
                fixed_native_JUnit_deferral_receipts={str(i):load(R/'runtime/non_junit4_deferrals_v1'/f'{i:03d}.json') for i in [48,49]},
                first_invocation_max_jobs=153,invocation_max_new_jobs=153,automatic_resume=False,
                retry_interrupted_jobs=False,scientific_measurement_changes=0,
                existing_archive_verification='reuse documented complete old audits; recheck pinned manifests/results/receipts at each boundary; full byte census remains required for new completed job archives')
    paths=[target,Path(__file__),R/'src/pom_input_deferral_policy_v1.py',diff,validation,
           R/'audit/pom_input_deferrals_v2/result.json',R/'audit/pom_input_deferrals_v2/manifest.json',
           R/'audit/pom_input_deferrals_v2/inspected_poms.json',R/'audit/pom_input_deferrals_v2/REPORT.md',
           R/'runtime/remaining_maven167_v5_completion.json',R/'runtime/gradle_native_after_v5_v1/state.json',
           R/'jobs/072/artifact_manifest.json',R/'jobs/072/interrupted.json']
    paths+=list(DIRECTORY.glob('*.json'))
    for i in completed:
        p=selected_result(i)
        paths.append(p)
        if (p.parent/'artifact_manifest.json').exists():
            paths.append(p.parent/'artifact_manifest.json')
    lock['code_and_input_hashes'].update({str(p.resolve()):sha(p) for p in paths})
    dump(R/'admission_maven_v6.json',lock)
    guards(lock)
    audit.log('B1_MAVEN_V6_FIXED_INPUT_QUARANTINE_ADMITTED',admission_sha256=sha(R/'admission_maven_v6.json'),
              verified_prior_new=46,unscored_indices=unscored,max_new_jobs=153,
              measurement_code_changed=False,original_POM_edits=0,GPT_API_calls=0)
    print(json.dumps({'status':'PASS_DISPATCH_ONLY_ADMISSION','prior_verified_total':95,
                      'unscored':unscored,'remaining_Maven_admitted':153,'Gradle_not_admitted':40,
                      'new_JVM_processes':0,'GPT_API_calls':0},indent=2))

if __name__=='__main__':
    main()
