"""Export the selected E1 lineage and linked diagnostics, without execution.

Historical G0/E0 are referenced as frozen observations, not reconstructed as
new attempts. Linked E49 generation, diagnostics, measurement replays and all
B1 command plans are explicit. No score-based filtering or experiment changes.
"""
import ast,csv,hashlib,json,os,sys
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path
from maven_adapter_v1 import R,sha,dump,generation_bindings
from run_maven_b1_v2 import guards
from run_maven_b1_v3 import selected_result,RECOVER
from classpath_transport_v1 import inflate,argv_sha256

B=R.parent/'paired49_20261023'
sys.path.insert(0,str(B))
import audit
OUT=R/'policy_attempt_history_v2'

def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def rel(p):
    p=Path(p).resolve()
    return p.relative_to(R.parents[1]).as_posix() if p.is_relative_to(R.parents[1]) else str(p)
def writecsv(name,rows):
    keys=list(dict.fromkeys(k for row in rows for k in row))
    with (OUT/name).open('x',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
def native_rows(folder):
    p=folder/'native_generated.json'
    return load(p)['files'] if p.exists() else []

assert not OUT.exists(),'No overwrite of audit history'
guards(load(R/'admission_maven_v6.json'))
OUT.mkdir(parents=True,exist_ok=False)
jobs=load(R/'manifest300.json');by_index={j['sample_index_1based']:j for j in jobs}
e49_inputs=load(B/'e49_driver/input_manifest49.json')
e49_by_old={j['job_index']:j for j in e49_inputs}
e49_to_sample={j['job_index']:next(x['sample_index_1based'] for x in jobs if x['class_key']==j['class_key']) for j in e49_inputs}
v6=set(load(R/'launch_remaining_maven153_v6.json')['sample_indices'])
attempts=[];changes=[];folder_meta={};checks=[];hash_evidence=[]
profile=load(R/'protocol.json')['generation_options']
allow_patterns=['junit','jupiter','hamcrest','mockito','byte-buddy','objenesis','opentest4j','apiguardian']
ledger=audit.events()

def change_record(index,phase,kind,details,evidence,known_outcomes):
    changes.append({'index':index,'class_key':by_index[index]['class_key'],'phase':phase,'change_kind':kind,
        'details_json':json.dumps(details,ensure_ascii=False),'decision_timing':known_outcomes,
        'evidence_path':rel(evidence),'evidence_sha256':sha(evidence)})

def phase_changes(folder,index,phase,known):
    p=folder/'policy_applied.json'
    if p.exists():
        policy=load(p)
        for change in policy['changes']:
            change_record(index,phase,change['kind'],change,p,known)
    p=folder/'native_junit_policy.json'
    if p.exists() and load(p)['changed']:
        change_record(index,phase,'ADD_MISSING_NATIVE_JUNIT4_TEST_SCOPE',load(p),p,known)
    for filename,kind in [('junit_patch.json','DIAGNOSTIC_JUNIT_TEST_VERSION'),('selector_patch.json','DIAGNOSTIC_EXACT_RELATIVE_INCLUDE')]:
        p=folder/filename
        if p.exists():change_record(index,phase,kind,load(p),p,known)

def old_commands(folder):
    return [(p,load(p)) for p in sorted(folder.glob('command_*.json'))]

def command_rows(folder,index,phase,role,selected,kind_format='new'):
    folder_meta[str(folder.resolve())]={'index':index,'phase':phase,'role':role}
    commands=old_commands(folder) if kind_format=='old' else [(p,load(p)) for p in sorted((folder/'commands').glob('*/plan.json'))]
    generation=[]
    for p,plan in commands:
        argv=plan['argv'];logical=list(argv)
        if kind_format=='new':
            started=(p.parent/'started.json').exists()
            finish=load(p.parent/'finished.json') if (p.parent/'finished.json').exists() else {}
            interrupted=load(p.parent/'interrupted.json') if (p.parent/'interrupted.json').exists() else {}
            begin=load(p.parent/'started.json') if started else {}
            ticket=folder/'command_admissions'/(p.parent.name+'.json')
            transport=load(ticket).get('transport_manifest') if ticket.exists() else None
            if transport:logical=inflate(argv,load(transport),folder)
            stdout=p.parent/'stdout.txt';stderr=p.parent/'stderr.txt'
            code=finish.get('returncode');timeout=plan['timeout_seconds']
            time_label=begin.get('started_utc',plan.get('planned_utc'))
            elapsed=finish.get('elapsed_seconds')
            reason=finish.get('reason') or interrupted.get('reason')
        else:
            started=True # Completed command record, not merely an intention.
            finish=plan;interrupted={};transport=None
            stdout=B/plan['stdout'];stderr=B/plan['stderr']
            code=plan.get('returncode');timeout=240 if '-jar' in argv else (300 if ('verify' in argv or 'test' in argv or any('maven-surefire-plugin:' in a and ':test' in a for a in argv)) else None)
            elapsed=plan.get('duration_seconds');reason='TIMEOUT' if plan.get('timeout') else None
            matches=[e for e in ledger if e['kind']=='EONLY_COMMAND_START' and str(e.get('job','')).replace('\\','/')==folder.relative_to(B).as_posix() and e.get('command_index')==plan.get('index')]
            time_label=matches[-1]['timestamp_utc'] if matches else 'not present in command record; use stage/ordinal'
            if matches:timeout=matches[-1].get('timeout',timeout)
        for file,key in [(stdout,'stdout_sha256'),(stderr,'stderr_sha256')]:
            if finish.get(key):assert file.exists() and sha(file)==finish[key],f'Log drift: {file}'
        is_gen='-jar' in logical
        is_measure='org.pitest:pitest-maven:mutationCoverage' in logical
        is_test='test' in logical or any('maven-surefire-plugin:' in a and ':test' in a for a in logical)
        stage='GENERATION_NEW_SEARCH' if is_gen else ('MEASUREMENT_EXISTING_SUITE' if is_measure else ('DIAGNOSTIC_TEST_EXISTING_SUITE' if is_test else 'COMPILE_OR_DEPENDENCY_AUDIT'))
        generation_number=len(generation)+1 if is_gen else None
        trigger=''
        if is_gen:
            options=[a for a in logical if a.startswith('-D') and not a.startswith(('-Dtest_dir=','-Dreport_dir='))]
            assert sorted(options)==sorted(profile),f'Unexpected generation flags: {p}'
            assert logical[-2:]==['-seed',str(by_index[index]['seed'])]
            if timeout is not None:assert timeout==240
            if generation:
                prior=generation[-1]
                out=prior['stdout']+'\n'+prior['stderr']
                markers=['displaynamegenerator','innerclasses attribute','mockmethodadvice','mockmethoddispatcher','bytebuddy','should be in target project, but could not be found','error while initializing target class: org/mockito']
                present=[m for m in markers if m in out.lower()]
                assert present,f'Retry without a declared technical marker: {p}'
                cp=prior['logical'][prior['logical'].index('-projectCP')+1].split(os.pathsep)
                sanitized=[s for s in cp if not (Path(s).is_file() and any(pat in Path(s).name.lower() for pat in allow_patterns))]
                assert sanitized!=cp and logical[logical.index('-projectCP')+1]==os.pathsep.join(sanitized)
                trigger=';'.join(present)
                kind='PREDECLARED_TECHNICAL_SANITIZED_CLASSPATH_RETRY'
            else:kind='PRIMARY_GENERATION' if started else 'GENERATION_LAUNCH_PLAN_NOT_STARTED'
            generation.append({'logical':logical,'stdout':stdout.read_text(encoding='utf-8',errors='replace') if stdout.exists() else '',
                               'stderr':stderr.read_text(encoding='utf-8',errors='replace') if stderr.exists() else '',
                               'started':started,'path':p,'returncode':code})
        elif phase.startswith('D') or phase.startswith('C003'):
            kind='POST_FAILURE_DIAGNOSTIC_NOT_PREDECLARED_RETRY'
        elif phase=='E49_COMPAT':kind='POST_REVIEW_MEASUREMENT_REPLAY_SAME_SUITE'
        else:kind='ONE_LOCKED_LIFECYCLE_OR_AUDIT'
        selectors=[a for a in logical if a.startswith('-Dtest=') or 'maven-surefire-plugin:' in a]
        row={'attempt_id':f'A{len(attempts)+1:04d}','index':index,'class_key':by_index[index]['class_key'],
             'phase':phase,'stage':stage,'attempt_kind':kind,'generation_ordinal_in_folder':generation_number,
             'process_started':started,'event_time_utc':time_label,'record_path':rel(p),'record_sha256':sha(p),
             'returncode':code,'termination_reason':reason,'elapsed_seconds':elapsed,'timeout_seconds':timeout,
             'seed':by_index[index]['seed'] if is_gen else None,'technical_retry_marker':trigger,
             'CP_file_transport':bool(transport),'selector':';'.join(selectors),
             'selection_role':selected,'reason':role,'logical_argv_sha256':argv_sha256(logical),
             'logical_argv_json':json.dumps(logical,ensure_ascii=False),'actual_argv_sha256':argv_sha256(argv),
             'stdout_path':rel(stdout) if stdout.exists() else None,'stderr_path':rel(stderr) if stderr.exists() else None}
        attempts.append(row)
    assert len(generation)<=2
    return generation

for old_index,j in sorted(e49_by_old.items()):
    i=e49_to_sample[old_index]
    old=B/'e49_driver/jobs'/f'{old_index:02d}'
    command_rows(old,i,'E49_ORIGINAL','new E1 generation under reviewer profile; baseline integration before later compatibility changes',
                 'generation retained; original measurement superseded by whole49 compatibility sensitivity','old')
    generated=load(old/'generated_manifest.json')
    for path,h in generated.items():
        f=old/Path(path);assert sha(f)==h
        hash_evidence.append({'index':i,'phase':'E49_ORIGINAL','path':rel(f),'generated_sha256':h,'current_sha256':sha(f),'status':'PASS'})
    diagnostic=B/'e1_compatibility_diagnostic_v1/jobs'/f'{old_index:02d}'
    if diagnostic.exists():
        command_rows(diagnostic,i,'D_E49_COMPAT','after inspecting E1 failures; dependency/selector/runtime diagnosis only',
                     'excluded from benchmark result selection','old')
        phase_changes(diagnostic,i,'D_E49_COMPAT','AFTER_ORIGINAL_FAILURES_KNOWN')
    selector=B/'e1_compatibility_diagnostic_v1/selector_correction_v1'/f'{old_index:02d}'
    if selector.exists():
        command_rows(selector,i,'D_E49_SELECTOR','post-failure exact-relative include diagnostic; no new generation/PIT',
                     'excluded diagnostic','old')
        phase_changes(selector,i,'D_E49_SELECTOR','AFTER_ORIGINAL_FAILURES_KNOWN')
    compatible=B/'e49_measurement_compat_v1/jobs'/f'{old_index:02d}'
    command_rows(compatible,i,'E49_COMPAT','one full inherited-lifecycle measurement of frozen native suite after compatibility protocol adoption',
                 'selected for reused49 as the full-cohort sensitivity; not choose-max','old')
    phase_changes(compatible,i,'E49_COMPAT','ADOPTED_AFTER_OLD_E1_AND_DIAGNOSTIC_OUTCOMES_KNOWN; before this whole49 replay')
    copied=load(compatible/'generated_manifest.json')
    for path,h in copied.items():
        f=compatible/Path(path);assert sha(f)==h and generated.get(path)==h
        hash_evidence.append({'index':i,'phase':'E49_COMPAT','path':rel(f),'generated_sha256':h,'current_sha256':sha(f),'status':'PASS'})

b1_folders=[]
for folder in sorted((R/'jobs').iterdir()):
    if not folder.is_dir():continue
    match=__import__('re').match(r'^(\d{3})(?:_|$)',folder.name)
    if not match:continue
    i=int(match.group(1));b1_folders.append((i,folder))
    if 'native_junit_diagnostic' in folder.name:
        phase='C003_'+folder.name.rsplit('_',1)[-1].upper()
        chosen=folder.name.endswith('_v3')
        role='post-failure missing-JUnit diagnostic; no new generation; outcome known before override adoption'
        selection='selected measurement-only override by mapv2 AFTER diagnostic result known' if chosen else 'not selected; preflight/guard abort preserved'
    elif '_cpfile_v3' in folder.name:
        phase='B1_CP_TRANSPORT_RECOVERY';role='after WinError206; original generation process never started; same profile/seed/CP bytes'
        selection='fixed result-mapv3 recovery selected irrespective of score'
    else:
        admission=load(folder/'job_admission.json') if (folder/'job_admission.json').exists() else {}
        h=admission.get('batch_admission_sha256')
        version=next((v for v in range(1,7) if (R/f'admission_maven_v{v}.json').exists() and sha(R/f'admission_maven_v{v}.json')==h),None)
        phase=f'B1_V{version}'
        role='locked E-only policy, conditional technical retry only; guards may stop unscored'
        selection='superseded measurement-only by mapv2; original result retained' if i==3 else ('superseded unstarted launch by fixed mapv3' if i in RECOVER else 'current result if terminal without integrity interruption; otherwise unscored')
    generations=command_rows(folder,i,phase,role,selection)
    phase_changes(folder,i,phase,'POST_FAILURE_DIAGNOSTIC' if phase.startswith('C003') else 'CONDITIONAL_RULE_FROZEN_IN_THIS_ADMISSION_BEFORE_CLASS_OUTCOME')
    native=folder/'native_generated.json'
    if native.exists():
        files=load(native)['files']
        actual_started=[g for g in generations if g['started']]
        for f in files:
            p=Path(f['path']);assert sha(p)==f['sha256']
            ordinal=len(generations)
            manifest=folder/'generation_attempts'/f'{ordinal:02d}'/'manifest.json'
            assert manifest.exists()
            entries=load(manifest);module=folder/'repo'/by_index[i]['module']
            key=p.relative_to(module).as_posix()
            archived=next(r for r in entries if r['path']==key)
            stored=manifest.parent/key
            assert archived['sha256']==f['sha256']==sha(stored)
            hash_evidence.append({'index':i,'phase':phase,'path':rel(p),'generated_sha256':f['sha256'],
                'current_sha256':sha(p),'generation_attempt_archive':rel(stored),'status':'PASS'})
    if phase.startswith('C003'):
        original=load(R/'jobs/003/native_generated.json')['files']
        for f in original:
            relative=Path(f['path']).relative_to(R/'jobs/003/repo')
            new=folder/'repo'/relative
            if new.exists():
                assert sha(new)==f['sha256']
                hash_evidence.append({'index':i,'phase':phase,'path':rel(new),'generated_sha256':f['sha256'],'current_sha256':sha(new),'status':'PASS'})
    if not generations and not list((folder/'commands').glob('*/plan.json')):
        evidence=folder/'preflight_failure.json' if (folder/'preflight_failure.json').exists() else folder/'interrupted.json'
        if evidence.exists():attempts.append({'attempt_id':f'A{len(attempts)+1:04d}','index':i,'class_key':by_index[i]['class_key'],
             'phase':phase,'stage':'PRE_EXECUTION_ABORT','attempt_kind':'NO_SEARCH_NO_MEASUREMENT',
             'process_started':False,'record_path':rel(evidence),'record_sha256':sha(evidence),
             'selection_role':'excluded/unscored','reason':json.dumps(load(evidence),ensure_ascii=False)})

# Add no-job frozen-input receipts and explicit historical references for all300.
for j in jobs:
    i=j['sample_index_1based'];p=R/'runtime/pom_input_deferrals_v1'/f'{i:03d}.json'
    if p.exists():
        change_record(i,'B1_V6_PREFLIGHT','FIXED_FROZEN_POM_UNSCORED_NO_REPAIR',load(p),p,'after072 input failure; before any generation of other9')
    if j['build_tool']=='gradle':attempts.append({'attempt_id':f'A{len(attempts)+1:04d}','index':i,'class_key':j['class_key'],
        'phase':'B1_GRADLE','stage':'NO_CORPUS_EXECUTION','attempt_kind':'NOT_ATTEMPTED','process_started':False,
        'selection_role':'unattempted; no score; synthetic fixture excluded','reason':'Gradle generation/measurement adapter not admitted'})

# Verify the immutable V6 admission and every actual generation/retry.
locked=load(R/'admission_maven_v6.json')
for p,h in locked['code_and_input_hashes'].items():assert sha(p)==h
v6_attempts=[a for a in attempts if a.get('phase')=='B1_V6']
v6_gens=[a for a in v6_attempts if a['stage']=='GENERATION_NEW_SEARCH']
v6_measures=[a for a in v6_attempts if a['stage']=='MEASUREMENT_EXISTING_SUITE']
for i in v6:
    folder=R/'jobs'/f'{i:03d}'
    assert load(folder/'job_admission.json')['batch_admission_sha256']==sha(R/'admission_maven_v6.json')
    measurement=[a for a in v6_measures if a['index']==i]
    assert len(measurement)<=1,'Repeated corpus measurement insideV6'
    generations=[a for a in v6_gens if a['index']==i and a['process_started']]
    assert len(generations)<=2
    result=folder/'result.json'
    if result.exists():assert load(result)['source_guard']==load(result)['production_bytecode_guard']=='PASS'
    policy_file=folder/'policy_applied.json'
    if policy_file.exists():
        policy=load(policy_file)
        module=folder/'repo'/by_index[i]['module']
        assert sha(module/'pom.xml')==policy['after_sha256']
        native_policy=load(folder/'native_junit_policy.json')
        before=load(folder/'before_dependency.json')
        if (folder/'after_dependency.json').exists():
            after=load(folder/'after_dependency.json')
            if native_policy['changed']:
                from native_junit_policy_candidate_v1 import compare
                compare(before,after)
            else:
                from maven_adapter_v1 import measurement_policy_bindings
                measurement_policy_bindings(lambda *a,**k:None)['compare_cp'](before,after,policy)
        else:
            assert not policy['changes'] and not native_policy['changed']

    checks.append({'index':i,'V6_admission_hash':'PASS','actual_generation_processes':len(generations),
          'measurement_lifecycles':len(measurement),'technical_retry':len(generations)==2,
          'native_source_hash_rows':sum(h['index']==i and h['phase']=='B1_V6' for h in hash_evidence),
          'new_manual_repair_or_result_selection_in_V6':'NO_EVIDENCE_IN_RECORDED_ARTIFACTS'})

perclass=[]
for j in jobs:
    i=j['sample_index_1based'];selected=None;initial=None;rule='';scope='';posthoc=False
    if j['reused_result']:
        selected=Path(j['reused_result']['result_path']);old=j['reused_result']['old_job_index']
        initial=B/'e49_driver/jobs'/f'{old:02d}'/'result.json'
        rule='whole49 compatibility replay selected, including failures; diagnostics excluded; not max of attempts'
        scope='E49_COMPAT';posthoc=True
    elif selected_result(i).exists() and not (selected_result(i).parent/'interrupted.json').exists():
        selected=selected_result(i);initial=R/'jobs'/f'{i:03d}'/'result.json'
        if i==3:rule='mapv2 measurement-only diagnostic override adopted AFTER its successful result was known; cannot claim prospectively outcome-blind selection';posthoc=True
        elif i in RECOVER:rule='mapv3 recovery fixed BEFORE these3 first actual searches; preserve recovery outcome irrespective of score';posthoc=True
        else:rule='one terminal result from locked admission; optional predeclared technical retry; no max-score selection'
        scope='B1_MAVEN'
    else:rule='unscored/unattempted; preserve fixed300 membership, no fallback-zero or E0 substitution';scope='UNSCORED_OR_UNATTEMPTED'
    aa=[a for a in attempts if a['index']==i]
    pp=[p for p in changes if p['index']==i]
    current=load(selected) if selected else {};before=load(initial) if initial and initial.exists() else {}
    perclass.append({'index':i,'class_key':j['class_key'],'focal_class':j['focal_class'],'build_tool':j['build_tool'],
       'G0_E0_reference':'historical frozen observations; no post-review rerun; historical attempt-level count not reconstructed here',
       'new_generation_processes_in_E1_lineage':sum(a['stage']=='GENERATION_NEW_SEARCH' and a['process_started'] for a in aa),
       'generation_plans_not_started':sum(a['stage']=='GENERATION_NEW_SEARCH' and not a['process_started'] for a in aa),
       'predeclared_technical_retries':sum(a.get('attempt_kind')=='PREDECLARED_TECHNICAL_SANITIZED_CLASSPATH_RETRY' for a in aa),
       'mutation_measurement_lifecycles':sum(a['stage']=='MEASUREMENT_EXISTING_SUITE' and a['process_started'] for a in aa),
       'diagnostic_test_only_lifecycles':sum(a['stage']=='DIAGNOSTIC_TEST_EXISTING_SUITE' and a['process_started'] for a in aa),
       'attempt_ids':';'.join(a['attempt_id'] for a in aa if a['stage'] not in ['COMPILE_OR_DEPENDENCY_AUDIT']),
       'dependency_selector_changes_json':json.dumps([{'phase':p['phase'],'kind':p['change_kind'],'details':p['details_json']} for p in pp],ensure_ascii=False),
       'selected_phase':scope,'selected_result_path':rel(selected) if selected else None,
       'selected_result_sha256':sha(selected) if selected else None,'initial_gate':before.get('legacy_process_build'),
       'selected_gate':current.get('legacy_process_build'),'initial_saved_strict_score':before.get('legacy_strict_mutation_percent'),
       'selected_saved_strict_score':current.get('legacy_strict_mutation_percent'),
       'selection_rule':rule,'posthoc_amendment_in_lineage':posthoc,
       'native_source_hash_checks':sum(h['index']==i for h in hash_evidence)})

counts={'classes':len(perclass),'command_or_preflight_records':len(attempts),
        'E49_generation_processes':sum(a['phase']=='E49_ORIGINAL' and a['stage']=='GENERATION_NEW_SEARCH' and a['process_started'] for a in attempts),
        'B1_generation_processes':sum(a['phase'].startswith('B1_') and a['stage']=='GENERATION_NEW_SEARCH' and a['process_started'] for a in attempts),
        'V6_generation_processes':len([a for a in v6_gens if a['process_started']]),
        'V6_subjects_with_technical_retry':sum(c['technical_retry'] for c in checks),
        'V6_measurement_lifecycles':len(v6_measures),'native_source_hash_checks':len(hash_evidence),
        'V6_native_source_files_checked':sum(h['phase']=='B1_V6' for h in hash_evidence),
        'V6_missing_JUnit_addition_indices':[p['index'] for p in changes if p['phase']=='B1_V6' and p['change_kind']=='ADD_MISSING_NATIVE_JUNIT4_TEST_SCOPE'],
        'V6_JUnit4_upgrade_indices':[p['index'] for p in changes if p['phase']=='B1_V6' and p['change_kind']=='test_JUnit_API'],
        'V6_selector_change_indices':[p['index'] for p in changes if p['phase']=='B1_V6' and p['change_kind']=='regular_exact_relative_include'],
        'E49_gate_changed_after_replay_indices':[r['index'] for r in perclass if r['selected_phase']=='E49_COMPAT' and r['initial_gate']!=r['selected_gate']],
        'E49_saved_score_changed_after_replay_indices':[r['index'] for r in perclass if r['selected_phase']=='E49_COMPAT' and r['initial_saved_strict_score']!=r['selected_saved_strict_score']]}
assert len(perclass)==300 and len(checks)==153
assert counts['E49_generation_processes']==49 and counts['B1_generation_processes']==216
verification={'status':'PASS_RECORDED_ARGV_RETRY_AND_NATIVE_SOURCE_HASH_AUDIT','at_utc':datetime.now(timezone.utc).isoformat(),
      'counts':counts,'V6_profile_seed_budget_argv_checks':'PASS_FOR_ALL_RECORDED_GENERATIONS',
      'V6_same_seed_exact_sanitized_CP_retry_checks':'PASS','V6_source_bytes_vs_attempt_archive':'PASS_FOR_GENERATED_FILES',
      'V6_effective_POM_matches_recorded_policy_and_CP_delta_rules':'PASS; conditional changes exist, not an unchanged effective environment','V6_one_measurement_lifecycle_per_class':'PASS','V6_scoring_input_used_for_retry':'NO; markers and exact CP sanitizer only',
      'all_E1_configuration_invariant_from_beginning':'FALSE; explicit post-outcome amendments and suite-only replays exist',
      'manual_edits_invisible_between_archives_can_be_ruled_out_absolutely':False,
      'scope_limit':'Observed saved argv, code pins, end-to-end native-source hashes and linked diagnostics; not a reconstruction of every abandoned draft/G0/E0 historical attempt',
      'new_experiment_calls':0,'GPT_API_calls':0,'raw_evidence_or_selected_maps_changed':False}
dump(OUT/'verification.json',verification)
dump(OUT/'native_source_hash_evidence.json',hash_evidence)
dump(OUT/'V6_per_class_checks.json',checks)
writecsv('class_policy_history300.csv',perclass)
writecsv('command_history_all.csv',attempts)
writecsv('generation_measurement_diagnostic_attempts.csv',[a for a in attempts if a['stage']!='COMPILE_OR_DEPENDENCY_AUDIT'])
writecsv('dependency_selector_changes.csv',changes)
dump(OUT/'selection_current.json',perclass)
table='\n'.join('|'+ '|'.join(str(x) for x in [r['index'],r['focal_class'],r['new_generation_processes_in_E1_lineage'],r['predeclared_technical_retries'],r['mutation_measurement_lifecycles'],r['diagnostic_test_only_lifecycles'],r['selected_phase'],','.join(p['change_kind'] for p in changes if p['index']==r['index']) or 'none'])+'|' for r in perclass)
with (OUT/'CLASS_HISTORY300.md').open('x',encoding='utf-8') as f:
    f.write('# Lịch sử theo300 class\n\nSố là actual processes/lifecycles đã ghi, không là số lần độc lập thống kê. Các bước compile/dependency audit nằm trong command_history_all.csv. G0/E0 được giữ như historical references, không suy đoán attempt count thiếu log.\n\n|Index|Class|Generation mới|Retry kỹ thuật|Mutation measurement|Diagnostic test-only|Kết quả chọn|Dependency/selector changes|\n|---|---|---:|---:|---:|---:|---|---|\n'+table+'\n')
audit.log('B1_POLICY_ATTEMPT_HISTORY_EXPORTED',verification_sha256=sha(OUT/'verification.json'),counts=counts,
          classes=300,new_experiment_calls=0,GPT_API_calls=0,raw_evidence_changes=0)
print(json.dumps(verification,indent=2))
