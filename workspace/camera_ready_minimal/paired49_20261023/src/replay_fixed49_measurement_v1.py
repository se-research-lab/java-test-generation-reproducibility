"""Frozen-suite fixed49 EvoSuite compatibility remeasurement, isolated and audited.
No generation/API. Original E1/G0 and shared experiment code remain read-only.
"""
import argparse,ast,concurrent.futures,copy,csv,difflib,hashlib,importlib.util,json,os,re,shutil,sys,time,zipfile
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from xml.etree import ElementTree as ET
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));sys.path.insert(0,str(BASE/'src'))
import audit,e49_driver as legacy,diagnose_e1_compatibility_v4 as compat,run_e49_supplement as frozen
import analyze_e49_final_v2 as pure
STAGE=BASE/'e49_measurement_compat_v1';E1=BASE/'e49_driver'
CACHE=BASE/'e1_compatibility_diagnostic_v1/maven_cache';NS=compat.NS
EXCLUDE={'.git','target','node_modules','evosuite-report','.gradle'}
ORDER=[18,19]+[i for i in range(1,50) if i not in [18,19]]
CACHE_HASHES=None

def now():return datetime.now(timezone.utc).isoformat()
def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def dump(p,x):legacy.write_json(p,x)
def event(kind,**kw):
    row={'timestamp_utc':now(),'kind':kind,**kw}
    with (STAGE/'events.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n');f.flush();os.fsync(f.fileno())
    audit.log('COMPAT49_'+kind,**kw)
def hashes(root,exclude=(),classes_only=False):
    return {p.relative_to(root).as_posix():{'sha256':audit.sha(p),'bytes':p.stat().st_size} for p in compat.walk(root,exclude) if not classes_only or p.suffix=='.class'}
def normalize(root):
    root=copy.deepcopy(root)
    for e in root.iter():
        if e.text is not None and not e.text.strip():e.text=None
        if e.tail is not None and not e.tail.strip():e.tail=None
    return ET.tostring(root)
def verify_base():
    for manifest in ['final49_static_registry_v1.json','compatibility_15page_static_registry_v1.json']:
        for r in load(BASE/'audit'/manifest)['files']:assert audit.sha(BASE/r['path'])==r['sha256'],r['path']
    old=load(E1/'readiness_lock.json')
    for rel,h in old['code_and_input_hashes'].items():assert audit.sha(BASE/rel)==h,rel
    for p,h in old['tool_hashes'].items():assert audit.sha(p)==h,p
    frozen.check_gpt()
    assert audit.sha(E1/'results49.json')=='5a7873ed3600b60fb4dc27fccb65468c8f0a39f1c38a763cea8dd467f24c0dd9'
    return old

def prepare():
    assert not STAGE.exists(),'New stage only; no overwrite'
    oldlock=verify_base();audit.verify();STAGE.mkdir()
    protocol={'created_utc':now(),'status':'PREPARING_INPUTS','kind':'post-review evaluation compatibility sensitivity on already generated E1 suites',
        'cohort':'exact fixed49 historical G0/E0 common-build keys; preserve all failures and G0 observations',
        'generation_calls':0,'GPT_API_calls':0,'workers':1,'measurement_order':ORDER,
        'goals':['clean','verify','jacoco:prepare-agent','jacoco:report','org.pitest:pitest-maven:mutationCoverage'],
        'measurement_timeout_seconds':300,'dependency_timeout_seconds':180,'technical_retry':False,
        'JUnit_rule':'if actual selected JUnit jar lacks TestRule and direct module junit:junit dependency scope=test, override version4.13.2; other test delta only Hamcrest-core1.3 required by JUnit',
        'selector_rule':'if effective Surefire2.17 has multiple execution IDs including regular-tests whose includes contain leading slash, replace only regular-tests/includes with exact relative native test.java combine.self=override',
        'lifecycle':'Retain original command04 full inherited lifecycle; do not disable serial/default executions or add skip/group/fork flags',
        'gate':'legacy literal BUILD SUCCESS in measurement stdout; suite evidence does not change score',
        'score':'KILLED/all focal SourceFile+package rows incl nested classes; round2; legacy gate/unavailable zero-fill',
        'pilot_gate':'18 and19 counted once in49 first; require exact2/12 unique passing canonical methods, fresh XML after clean, unchanged class/CP/mutant data before remaining47',
        'no_new_measure':'not a new generation baseline, not repeated-run robustness, not full300 NI/buildability',
        'scope':'E-only copied module test dependency/regular includes; no common runner/Gradle/GPT/production/PIT/JaCoCo changes',
        'errors':'measurement/tool failure may remain slot0 under legacy; guard/source/dependency/bytecode mutations stop batch and cannot be recoded as ordinary failure',
        'supersedes_plan_sentence':'The earlier proposal to invoke one execution is superseded; full original lifecycle is retained here before any new measurement',
        'cache':str(CACHE),'E1_results_sha256':audit.sha(E1/'results49.json'),
        'outcomes_known':'E1/diagnostic outcomes inspected; protocol is not pre-study preregistration',
        'source_original_manifest':'complete old E1 job files before preparation, checked after each new measurement because scaffold properties retain old absolute paths',
    }
    dump(STAGE/'protocol.json',protocol);event('PROTOCOL_RECORDED',sha256=audit.sha(STAGE/'protocol.json'))
    original=load(E1/'input_manifest49.json');paired=legacy.read_csv(BASE/'outputs/paired49.csv')
    assert [j['class_key'] for j in original]==[j['class_key'] for j in paired] and len(original)==49
    def prep(j):
        i=j['job_index'];old=E1/'jobs'/f'{i:02}';out=STAGE/'jobs'/f'{i:02}';out.mkdir(parents=True)
        before=hashes(old);dump(out/'original_E1_guard_before.json',before)
        rows=[]
        for p in compat.walk(old/'repo',EXCLUDE):
            rel=p.relative_to(old/'repo');h=audit.sha(p);dest=out/'repo'/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest);assert h==audit.sha(dest)==audit.sha(p)
            rows.append({'relative':rel.as_posix(),'sha256':h,'bytes':p.stat().st_size})
        dump(out/'input_source_manifest.json',rows)
        shutil.copy2(old/'settings.xml',out/'settings.xml');assert audit.sha(old/'settings.xml')==audit.sha(out/'settings.xml')
        generated=load(old/'generated_manifest.json')
        for rel,h in generated.items():assert audit.sha(old/rel)==h==audit.sha(out/rel)
        dump(out/'generated_manifest.json',generated)
        baseline=hashes(old/'repo'/j['module']/'target/classes',classes_only=True);assert baseline
        dump(out/'production_class_baseline.json',baseline)
        oldpit=pure.rawcsv(old/'repo'/j['module']/'target/pit-reports/mutations.csv');oldf=pure.focal(oldpit,j);assert oldf
        dump(out/'focal_mutant_baseline.json',{'multiset_sha256':pure.counter_hash(oldf),'n':len(oldf),'PIT_CSV_sha256':audit.sha(old/'repo'/j['module']/'target/pit-reports/mutations.csv'),'ID_limit':'CSVcols0-4 multiset retains duplicates, lacks bytecode index'})
        row={k:v for k,v in j.items() if k!='source_files'}
        row.update(E1_archived_mutation_percent=str(load(old/'result.json')['legacy_strict_mutation_percent']),E1_generated_manifest_sha256=audit.sha(old/'generated_manifest.json'),E1_result_sha256=audit.sha(old/'result.json'),input_source_manifest_sha256=audit.sha(out/'input_source_manifest.json'),generated_manifest_sha256=audit.sha(out/'generated_manifest.json'),production_class_baseline_sha256=audit.sha(out/'production_class_baseline.json'),focal_mutant_baseline_sha256=audit.sha(out/'focal_mutant_baseline.json'),original_guard_sha256=audit.sha(out/'original_E1_guard_before.json'),settings_sha256=audit.sha(out/'settings.xml'))
        event('INPUT_COPY_READY',job_index=i,source_files=len(rows),generated_manifest_sha256=row['generated_manifest_sha256']);return row
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:jobs=list(pool.map(prep,original))
    assert [j['job_index'] for j in jobs]==list(range(1,50))
    dump(STAGE/'input_manifest49.json',jobs)
    tracked=[Path(__file__),BASE/'src/e49_driver.py',BASE/'src/diagnose_e1_compatibility_v4.py',BASE/'src/run_e49_supplement.py',BASE/'src/analyze_e49_final_v2.py',STAGE/'protocol.json',STAGE/'input_manifest49.json',BASE/'outputs/paired49.csv',BASE/'e1_compatibility_diagnostic_v1/cache_copy_manifest.json']
    for out in sorted((STAGE/'jobs').iterdir()):tracked.extend(p for p in out.glob('*.json'))
    lock={'code_input_hashes':{p.relative_to(BASE).as_posix():audit.sha(p) for p in tracked},'tool_hashes':oldlock['tool_hashes'],'cache':str(CACHE),'measurement_order':ORDER,'new_generation_authorized':False,'GPT_API_calls':0}
    dump(STAGE/'readiness_lock.json',lock);event('INPUTS_LOCKED',jobs=49,readiness_lock_sha256=audit.sha(STAGE/'readiness_lock.json'))
    print(json.dumps({'status':'READY','jobs':49,'generation_calls':0,'GPT_API_calls':0,'order':ORDER},indent=2),flush=True)

def verify_lock():
    lock=load(STAGE/'readiness_lock.json')
    for rel,h in lock['code_input_hashes'].items():assert audit.sha(BASE/rel)==h,rel
    for p,h in lock['tool_hashes'].items():assert audit.sha(p)==h,p
    frozen.check_gpt();return lock

def cp_entries(file):
    global CACHE_HASHES
    if CACHE_HASHES is None:CACHE_HASHES={r['relative']:r['sha256'] for r in load(BASE/'e1_compatibility_diagnostic_v1/cache_copy_manifest.json')}
    assert file.is_file(),'Missing classpath output'
    rows=[]
    for value in file.read_text(encoding='utf-8').strip().split(os.pathsep):
        p=Path(value);assert p.is_file(),value;h=audit.sha(p)
        if p.is_relative_to(CACHE):key=p.relative_to(CACHE).as_posix();assert CACHE_HASHES.get(key)==h,'Cache jar drift: '+key
        else:key=str(p)
        rows.append({'path':key,'absolute_path':str(p),'sha256':h,'bytes':p.stat().st_size})
    return rows

def dependency(commands,args,module,out,label):
    testcp=out/(label+'_test_classpath.txt');compilecp=out/(label+'_compile_classpath.txt');tree=out/(label+'_tree.txt')
    r=commands.run([*args,'org.apache.maven.plugins:maven-dependency-plugin:3.7.0:tree','org.apache.maven.plugins:maven-dependency-plugin:3.7.0:build-classpath','-DoutputFile='+str(tree),'-Dmdep.outputFile='+str(testcp),'-DincludeScope=test'],cwd=module,timeout=180)
    assert r.returncode==0,'Premeasurement dependency resolution failed; no policy admission'
    c=commands.run([*args,'org.apache.maven.plugins:maven-dependency-plugin:3.7.0:build-classpath','-Dmdep.outputFile='+str(compilecp),'-DincludeScope=compile'],cwd=module,timeout=180)
    assert c.returncode==0,'Compile dependency guard unavailable'
    data={'classpath':cp_entries(testcp),'compile_classpath':cp_entries(compilecp),'tree_sha256':audit.sha(tree)};dump(out/(label+'_dependency.json'),data);return data

def effective(commands,args,module,out,label):
    dest=out/(label+'_effective_pom.xml')
    r=commands.run([*args,'org.apache.maven.plugins:maven-help-plugin:3.2.0:effective-pom','-Doutput='+str(dest)],cwd=module,timeout=180)
    assert r.returncode==0 and dest.is_file(),'Effective POM unavailable; no policy admission'
    root=ET.parse(dest).getroot();plugins=[p for p in root.findall('m:build/m:plugins/m:plugin',NS) if p.findtext('m:artifactId',namespaces=NS)=='maven-surefire-plugin'];assert len(plugins)==1
    return plugins[0]

def patch_pom(j,module,out,before_dep,surefire):
    path=module/'pom.xml';before=path.read_text(encoding='utf-8');text=before;changes=[]
    root=ET.fromstring(text)
    selected=[r for r in before_dep['classpath'] if r['path'].startswith('junit/junit/')]
    assert len(selected)<=1
    lacks=False
    if selected:
        with zipfile.ZipFile(selected[0]['absolute_path']) as z:lacks='org/junit/rules/TestRule.class' not in z.namelist()
    if lacks:
        ds=[d for d in root.findall('m:dependencies/m:dependency',NS) if d.findtext('m:groupId',namespaces=NS)=='junit' and d.findtext('m:artifactId',namespaces=NS)=='junit']
        assert len(ds)==1 and ds[0].findtext('m:scope',namespaces=NS)=='test','Unsafe JUnit dependency scope'
        candidates=[m for m in re.finditer(r'<dependency\b[^>]*>.*?</dependency>',text,re.S) if re.search(r'<groupId>\s*junit\s*</groupId>',m.group()) and re.search(r'<artifactId>\s*junit\s*</artifactId>',m.group())]
        assert len(candidates)==1;m=candidates[0];chunk=m.group();old=ds[0].findtext('m:version',namespaces=NS)
        if old:chunk2=re.sub(r'<version>.*?</version>','<version>4.13.2</version>',chunk,count=1,flags=re.S)
        else:chunk2=chunk.replace('</artifactId>','</artifactId><version>4.13.2</version>',1)
        text=text[:m.start()]+chunk2+text[m.end():];changes.append({'kind':'test_JUnit_API','old_version':old,'new_version':'4.13.2'})
    executions=surefire.findall('m:executions/m:execution',NS)
    regular=[e for e in executions if e.findtext('m:id',namespaces=NS)=='regular-tests']
    inc=[i.text for e in regular for i in e.findall('m:configuration/m:includes/m:include',NS)]
    selector=bool(len(executions)>1 and regular and any(v and v.startswith('/') for v in inc))
    if selector:
        assert surefire.findtext('m:version',namespaces=NS)=='2.17' and len(regular)==1
        selected_path=j['selected_test_fqcn'].replace('.','/')+'.java'
        blocks=[m for m in re.finditer(r'<plugin\b[^>]*>.*?</plugin>',text,re.S) if '<artifactId>maven-surefire-plugin</artifactId>' in m.group()]
        assert len(blocks)==1;m=blocks[0];chunk=m.group();p=ET.fromstring('<root xmlns="'+NS['m']+'">'+chunk+'</root>')[0]
        assert p.find('m:executions',NS) is None,'Unproven module execution shape; stop'
        addition='<executions><execution><id>regular-tests</id><configuration><includes combine.self="override"><include>'+selected_path+'</include></includes></configuration></execution></executions>'
        text=text[:m.start()]+chunk.replace('</plugin>',addition+'</plugin>',1)+text[m.end():]
        changes.append({'kind':'regular_exact_relative_include','old_effective_includes':inc,'new_include':selected_path})
    # Reverse only the declared changes; everything significant must match original XML.
    reverted=ET.fromstring(text)
    for change in changes:
        if change['kind']=='test_JUnit_API':
            d=next(d for d in reverted.findall('m:dependencies/m:dependency',NS) if d.findtext('m:groupId',namespaces=NS)=='junit' and d.findtext('m:artifactId',namespaces=NS)=='junit');v=d.find('m:version',NS)
            if change['old_version'] is None:d.remove(v)
            else:v.text=change['old_version']
        else:
            p=next(p for p in reverted.findall('m:build/m:plugins/m:plugin',NS) if p.findtext('m:artifactId',namespaces=NS)=='maven-surefire-plugin');p.remove(p.find('m:executions',NS))
    assert normalize(reverted)==normalize(ET.fromstring(before)),'POM semantic diff outside allowlist'
    backup=out/'backup_before_policy/pom.xml';backup.parent.mkdir();shutil.copy2(path,backup)
    if text!=before:path.write_text(text,encoding='utf-8')
    diff=out/'policy_patch.diff';diff.write_text(''.join(difflib.unified_diff(before.splitlines(True),text.splitlines(True),fromfile='before/pom.xml',tofile='after/pom.xml')),encoding='utf-8')
    policy={'JUnit_rule_applied':lacks,'selector_rule_applied':selector,'direct_JUnit_present':bool(selected),'TestRule_missing_before':lacks,'changes':changes,'before_sha256':audit.sha(backup),'after_sha256':audit.sha(path),'diff_sha256':audit.sha(diff),'only_allowlisted_semantic_changes':True}
    dump(out/'policy_applied.json',policy);event('COPIED_POLICY_RECORDED',job_index=j['job_index'],policy=policy)
    return policy

def compare_cp(a,b,policy):
    sig=lambda rows:sorted((r['path'],r['sha256']) for r in rows)
    assert sig(a['compile_classpath'])==sig(b['compile_classpath']),'Production compile closure drift'
    allowed=lambda r:r['path'].startswith('junit/junit/') or r['path']=='org/hamcrest/hamcrest-core/1.3/hamcrest-core-1.3.jar'
    if policy['JUnit_rule_applied']:
        assert sig([r for r in a['classpath'] if not allowed(r)])==sig([r for r in b['classpath'] if not allowed(r)]),'Non JUnit/Hamcrest test closure drift'
        selected=[r for r in b['classpath'] if r['path'].startswith('junit/junit/')];assert len(selected)==1 and selected[0]['path']=='junit/junit/4.13.2/junit-4.13.2.jar'
        with zipfile.ZipFile(selected[0]['absolute_path']) as z:assert 'org/junit/rules/TestRule.class' in z.namelist()
    else:assert sig(a['classpath'])==sig(b['classpath']),'Unpatched test closure drift'

def normalize_case(name,test):
    if re.fullmatch(r'test\w*',name or ''):return name
    m=re.fullmatch(r'(test\w*) on \1\('+re.escape(test)+r'\)',name or '')
    return m.group(1) if m else None

def inspect(out,j,module,gate,measurement):
    raw=legacy.raw_metrics(module,j['selected_test_fqcn'],j['focal_class'],j['package'],gate)
    sourceissues=[];rows=load(out/'input_source_manifest.json');expected={r['relative']:r['sha256'] for r in rows};patch=load(out/'policy_applied.json')
    expected[(Path(j['module'])/'pom.xml').as_posix()]=patch['after_sha256']
    actual={p.relative_to(out/'repo').as_posix():audit.sha(p) for p in compat.walk(out/'repo',EXCLUDE)}
    sourceissues=[p for p in sorted(set(expected)|set(actual)) if expected.get(p)!=actual.get(p)];assert not sourceissues,sourceissues
    for rel,h in load(out/'generated_manifest.json').items():assert audit.sha(out/rel)==h,rel
    baseline=load(out/'production_class_baseline.json');current=hashes(module/'target/classes',classes_only=True)
    mismatches=[p for p in set(baseline)&set(current) if baseline[p]['sha256']!=current[p]['sha256']]
    added=sorted(set(current)-set(baseline));assert not mismatches and not added,{'changed':mismatches,'added':added}
    missing=sorted(set(baseline)-set(current))
    if gate:assert not missing,'BUILD SUCCESS with missing production bytecode'
    test=j['selected_test_fqcn'];testjava=module/'src/test/java'/Path(*test.split('.')).with_suffix('.java')
    methods=sorted(set(re.findall(r'public\s+void\s+(test\w*)\s*\(',testjava.read_text(encoding='utf-8'))));assert methods
    cases=[]
    for p in sorted((module/'target/surefire-reports').glob('TEST-*.xml')):
        root=ET.parse(p).getroot();assert root.get('name')==test,'Foreign canonical suite'
        for c in root.findall('testcase'):
            assert c.get('classname')==test,'Foreign testcase class'
            cases.append({'class':c.get('classname'),'name':c.get('name'),'method':normalize_case(c.get('name'),test),'errors':len(c.findall('error')),'failures':len(c.findall('failure')),'skipped':len(c.findall('skipped'))})
    suite_ok=bool(cases) and Counter(c['method'] for c in cases)==Counter(methods) and all(c['errors']+c['failures']+c['skipped']==0 for c in cases)
    if cases and all(c['errors']+c['failures']==0 for c in cases):assert len(cases)==len({c['method'] for c in cases}),'Repeated canonical selected methods'
    csvrows=pure.rawcsv(module/'target/pit-reports/mutations.csv');foc=pure.focal(csvrows,j)
    assert not [r for r in csvrows if r[5]=='KILLED' and test not in r[6]],'PIT foreign killing tests'
    expected_mutants=load(out/'focal_mutant_baseline.json');match=bool(foc) and pure.counter_hash(foc)==expected_mutants['multiset_sha256']
    if foc:assert match,'Present focal mutation candidate multiset drift'
    strict_evidence=bool(suite_ok and foc and raw['jacoco_focal_rows'])
    repeated_runs=len(re.findall(r'^\s*Running '+re.escape(test)+r'\s*$',measurement.stdout,re.M))
    assert repeated_runs<=1,'Multiple Surefire selected suite invocations in full lifecycle'
    diagnostic={'source_issues':sourceissues,'source_unchanged':True,'generated_unchanged':True,'production_class_mismatches':mismatches,'missing_production_classes':missing,'production_class_count':len(current),'focal_mutant_multiset_matches_E1':match,'compile_classpath_unchanged':True,'test_classpath_delta_allowed':True,'expected_methods':methods,'canonical_cases':cases,'complete_suite_evidence':suite_ok,'complete_measurement_evidence':strict_evidence,'selected_suite_running_lines':repeated_runs,'mutation_ID_limit':'CSVcols0-4 duplicate-preserving multiset lacks PIT bytecode index'}
    dump(out/'measurement_audit.json',diagnostic)
    return raw,diagnostic

def archive_job(out):
    paths=[]
    for p in out.rglob('*'):
        if not p.is_file():continue
        rel=p.relative_to(out);parts=rel.parts
        if 'temp' in parts or p.name=='artifact_manifest.json':continue
        if parts[0]=='repo':
            if p.suffix=='.class' and '/target/classes/' in p.as_posix():pass
            elif any(v in p.as_posix() for v in ['/surefire-reports/','/pit-reports/','/target/site/jacoco/']):pass
            elif p.name=='pom.xml' or p.name.endswith(('_ESTest.java','_ESTest_scaffolding.java')):pass
            else:continue
        paths.append(p)
    dump(out/'artifact_manifest.json',[{'path':p.relative_to(BASE).as_posix(),'sha256':audit.sha(p),'bytes':p.stat().st_size} for p in sorted(paths)])

def execute(j):
    i=j['job_index'];out=STAGE/'jobs'/f'{i:02}';old=E1/'jobs'/f'{i:02}';module=out/'repo'/j['module']
    assert not (out/'result.json').exists() and not list(out.glob('command_*.json')),'Do not rerun a measured job'
    for key,file in [('input_source_manifest_sha256','input_source_manifest.json'),('generated_manifest_sha256','generated_manifest.json'),('production_class_baseline_sha256','production_class_baseline.json'),('focal_mutant_baseline_sha256','focal_mutant_baseline.json'),('original_guard_sha256','original_E1_guard_before.json')]:assert audit.sha(out/file)==j[key],file
    assert hashes(old)==load(out/'original_E1_guard_before.json'),'Original E1 job drift before replay'
    env=legacy.isolated_env(out);commands=compat.DiagnosticCommands(out,env,CACHE,0)
    dump(out/'environment_allowlist.json',{k:env.get(k) for k in ['JAVA_HOME','JAVA_TOOL_OPTIONS','TMP','TEMP']})
    oldargv=load(old/'command_04.json')['argv'];test=j['selected_test_fqcn'];start=oldargv.index('-Dtest='+test);flags=oldargv[start:oldargv.index('clean')]
    args=['mvn','-s',str(out/'settings.xml'),*flags]
    try:
        before_dep=dependency(commands,args,module,out,'before')
        before_eff=effective(commands,args,module,out,'before');policy=patch_pom(j,module,out,before_dep,before_eff)
        if policy['changes']:
            after_dep=dependency(commands,args,module,out,'after');after_eff=effective(commands,args,module,out,'after')
            compare_cp(before_dep,after_dep,policy)
            a=copy.deepcopy(before_eff);b=copy.deepcopy(after_eff)
            if policy['selector_rule_applied']:
                for plugin in [a,b]:
                    reg=next(e for e in plugin.findall('m:executions/m:execution',NS) if e.findtext('m:id',namespaces=NS)=='regular-tests');c=reg.find('m:configuration',NS);c.remove(c.find('m:includes',NS))
                actual=next(e for e in after_eff.findall('m:executions/m:execution',NS) if e.findtext('m:id',namespaces=NS)=='regular-tests')
                assert [v.text for v in actual.findall('m:configuration/m:includes/m:include',NS)]==[test.replace('.','/')+'.java']
            assert normalize(a)==normalize(b),'Effective Surefire drift outside includes'
        else:after_dep=before_dep
        commands.run([str(legacy.JDK/'bin/java.exe'),'-version'],cwd=out,timeout=15)
        goals=load(STAGE/'protocol.json')['goals']
        expected=oldargv[oldargv.index('clean'):];assert goals==expected,'Measurement goals changed'
        try:measurement=commands.run([*args,*goals],cwd=module,timeout=300);gate='BUILD SUCCESS' in measurement.stdout
        except commands.TimeoutExpired:
            record=commands.records[-1];measurement=type('TimedOut',(),{'stdout':(BASE/record['stdout']).read_text(encoding='utf-8'),'stderr':(BASE/record['stderr']).read_text(encoding='utf-8'),'returncode':-999})();gate=False
        raw,diag=inspect(out,j,module,gate,measurement)
        for r in after_dep['classpath']:assert audit.sha(r['absolute_path'])==r['sha256'],'Dependency jar mutated during measurement'
        row={'job_index':i,'class_key':j['class_key'],'repo_id':j['repo_id'],'G0_archived_mutation_percent':j['gpt_archived_mutation_percent'],'E0_archived_mutation_percent':j['e0_archived_mutation_percent'],'E1_archived_mutation_percent':j['E1_archived_mutation_percent'],'seed':j['seed'],'generation_success':True,'generation_attempts':0,'generation_calls':0,'reused_E1_generated_tests':True,'generated_bytes_unchanged':True,'GPT_API_calls':0,'configuration':'frozen_E1_suite_compatibility_measurement','command_returncode':measurement.returncode,**raw}
        if i in [18,19]:assert diag['complete_suite_evidence'] and not diag['missing_production_classes'] and len(diag['canonical_cases'])=={18:2,19:12}[i],'Full lifecycle Hazelcast gate failed; stop before47 remaining'
        dump(out/'result.json',row)
    finally:
        after=hashes(old);dump(out/'original_E1_guard_after.json',after);same=after==load(out/'original_E1_guard_before.json');event('ORIGINAL_E1_GUARD',job_index=i,unchanged=same);assert same,'Original E1 job bytes or membership changed'
        frozen.check_gpt()
    archive_job(out);dump(STAGE/f'job_result_{i:02}.json',row);event('JOB_COMPLETE',job_index=i,result_sha256=audit.sha(out/'result.json'),artifact_manifest_sha256=audit.sha(out/'artifact_manifest.json'),gate=raw['legacy_process_build'],suite_pass=diag['complete_suite_evidence'])
    return row

def run():
    verify_lock();assert not (STAGE/'admission.json').exists(),'No second admission'
    dump(STAGE/'admission.json',{'timestamp_utc':now(),'readiness_sha256':audit.sha(STAGE/'readiness_lock.json'),'protocol_sha256':audit.sha(STAGE/'protocol.json'),'order':ORDER,'generation_calls':0,'GPT_API_calls':0})
    event('RUN_START',admission_sha256=audit.sha(STAGE/'admission.json'),workers=1)
    jobs={j['job_index']:j for j in load(STAGE/'input_manifest49.json')};results={}
    try:
        for i in ORDER:
            frozen.check_gpt();results[i]=execute(jobs[i]);print(json.dumps({'completed':len(results),'n':49,'job_index':i,'gate':results[i]['legacy_process_build'],'raw_score':results[i]['legacy_strict_mutation_percent'],'new_generation':False},ensure_ascii=False),flush=True)
        rows=[results[i] for i in range(1,50)];dump(STAGE/'results49.json',rows)
        fields=list(dict.fromkeys(k for r in rows for k in r if not isinstance(r[k],(dict,list))))
        with (STAGE/'results49.csv').open('x',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
        frozen.check_gpt();audit.verify();dump(STAGE/'complete.json',{'status':'COMPLETE','n':49,'results49_sha256':audit.sha(STAGE/'results49.json'),'GPT_API_calls':0,'generation_calls':0});event('COMPLETE',n=49,results49_sha256=audit.sha(STAGE/'results49.json'))
    except BaseException as ex:
        event('ABORT',completed=len(results),error_type=type(ex).__name__,error=str(ex));raise

def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','run']);a=p.parse_args()
    if a.mode=='prepare':prepare()
    else:run()
if __name__=='__main__':main()
