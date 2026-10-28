"""Freeze exact49 supplementary inputs without running benchmark code."""
import csv,json,re,sys
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));import audit
STAGE=BASE/'e49_driver'
def rows(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
pairs=rows(BASE/'outputs/paired49.csv');assert len(pairs)==49 and all(p['build_tool']=='Maven' for p in pairs)
inv={r['class_key']:r for r in rows(BASE/'evo_patch/reports/raw49/inventory.csv')}
sampling=rows(audit.ROOT/'scripts_v2/data_new/class_sampling_manifest_final_seed42.csv')
samples={r['class_key']:(i+1,r) for i,r in enumerate(sampling)}
ignore={'.git','.gradle','.evosuite','target','build','evosuite-tests','evosuite-report'}
jobs=[]
for i,p in enumerate(pairs,1):
    sandbox=Path(inv[p['class_key']]['sandbox']);repo=sandbox/'compiledrepos'/p['repo_id']
    cs=rows(sandbox/'output/classes.csv');assert len(cs)==1 and cs[0]['Focal_Class']==p['focal_class']
    info=json.loads((sandbox/'output/project_info.json').read_text(encoding='utf-8'))
    key=p['repo_id']+'_'+p['module'] if p['module'] else p['repo_id'];framework=info[key]
    index,sample=samples[p['class_key']];assert sample['effective_java_runtime']=='8'
    focal=repo/p['focal_path'];globalfocal=audit.ROOT/'compiledrepos'/p['repo_id']/p['focal_path']
    text=focal.read_text(encoding='utf-8-sig',errors='replace');m=re.search(r'^\s*package\s+([\w.$]+)\s*;',text,re.M);package=m.group(1) if m else ''
    selected=(package+'.' if package else '')+p['focal_class']+'_ESTest'
    source_files=[]
    for path in sorted(repo.rglob('*')):
        if not path.is_file():continue
        rel=path.relative_to(repo)
        if any(part in ignore for part in rel.parts):continue
        assert not path.is_symlink()
        source_files.append({'relative':rel.as_posix(),'sha256':audit.sha(path),'bytes':path.stat().st_size})
    assert any(r['relative']==p['focal_path'] for r in source_files)
    oldtest=cs[0]['Test_Path'].replace('repos/'+p['repo_id']+'/','',1)
    assert not oldtest.startswith(('repos/','/')) and '..' not in Path(oldtest).parts
    jobs.append({'job_index':i,'sample_index':index,'class_key':p['class_key'],'repo_id':p['repo_id'],
        'focal_class':p['focal_class'],'focal_path':p['focal_path'],'package':package,'module':p['module'],
        'expected_commit_sha_from_sampling_manifest':sample['commit_sha'],
        'source_repo':str(repo),'source_snapshot_note':'remaining historical sandbox; complete source/POM hashes frozen now; historical execution revision not byte-certified',
        'focal_sha256':audit.sha(focal),'matches_current_compiledrepos_focal':globalfocal.exists() and audit.sha(globalfocal)==audit.sha(focal),
        'junit_version':framework.get('junit_version'),'testng_version':framework.get('testng_version'),
        'old_synthesized_test_relative':oldtest,'selected_test_fqcn':selected,
        'seed':20261023+index,'gpt_archived_mutation_percent':p['gpt_mutation_coverage'],
        'e0_archived_mutation_percent':p['evosuite_mutation_coverage'],'source_files':source_files})
assert len({j['class_key'] for j in jobs})==49
protocol={'status':'INPUTS_FROZEN_NOT_EXECUTION_AUTHORIZATION','scope':'fixed49 supplementary E configuration sensitivity; not full300 replacement',
    'outcomes_historical_known':True,'E1_benchmark_outcomes_inspected_before_freeze':False,
    'cohort_rule':'exact49 historical G0/E0 compilation=1 keys in paired49.csv; retain failures and original order',
    'seed_rule':'20261023 + original sampling manifest 1-based row index','search_budget_seconds':60,
    'generation_timeout_per_attempt_seconds':240,'maximum_generation_attempts_per_class':2,
    'retry_policy':'unchanged conditional sanitized-classpath retry from copied function; same seed; no manual repair or per-class config changes',
    'maven_timeout_per_command_seconds':300,'workers':1,'GPT_API_calls':0,
    'profile':'reviewer_assertions','assertions':True,'test_scaffolding':True,'no_runtime_dependency':False,
    'assertion_strategy':'MUTATION','criterion':'BRANCH','test_archive':False,'use_separate_classloader':False,
    'runtime_scope':'child environment only, exact JDK8 and existing tools.jar; workspace cache; no shared evaluator modification',
    'measurement_definition':'legacy SourceFile+package grouping including nested classes; KILLED/all focal-group CSV rows, rounded2; unchanged BUILD SUCCESS gate and strict zero-fill',
    'evidence_columns':'raw report presence, selected test, suite pass, mutant counts and measurement validity; not new P/C scales',
    'reporting':'descriptive fixed49 G0 vs E1 supplement; historical G0 score clearly labelled; missing measurements/failures enumerated; no new confirmatory NI test',
    'new_success_intersection':'optional labelled diagnostic only; cannot replace fixed49 or RQ1-RQ3',
    'limits':['conditional on historical build success, all Maven15 repos','one E seed per class is not variance estimation','G0 reused, no new GPT generation','source execution provenance and raw two-arm comparability still require checks'],
    'measurement_readiness_gate':'actual driver fixture with fresh generation, exact E-only Surefire/PIT selection, intact test/scaffold, JaCoCo/PIT evidence; source/tool/code/cache locks must verify before any benchmark job',
    'generation_job_count':49,'source_excluded_directory_names':sorted(ignore)}
for name,obj in [('input_manifest49.json',jobs),('protocol49.json',protocol)]:
    path=STAGE/name
    with path.open('x',encoding='utf-8') as f:json.dump(obj,f,ensure_ascii=False,indent=2);f.write('\n')
report={'n':49,'repositories':len({j['repo_id'] for j in jobs}),
    'input_files_hashed':sum(len(j['source_files']) for j in jobs),
    'focal_matches_compiledrepos':sum(j['matches_current_compiledrepos_focal'] for j in jobs),
    'manifest_sha256':audit.sha(STAGE/'input_manifest49.json'),'protocol_sha256':audit.sha(STAGE/'protocol49.json'),
    'no_benchmark_generation':True}
audit.log('E49_INPUT_PROTOCOL_FROZEN',**report);print(json.dumps(report,indent=2))
