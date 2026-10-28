"""E-only supplement driver. Loads audited function ASTs; never imports GPT modules.

Every invocation requires a fresh output directory. No benchmark execution without lock.
"""
import argparse,ast,csv,hashlib,json,os,re,shutil,subprocess,sys,time,types,zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
import pandas as pd
BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE));import audit
STAGE=BASE/'e49_driver'
JDK=Path('C:/Program Files/Java/jdk1.8.0_172')
MVN=Path('C:/Program Files/Apache/maven/bin/mvn.cmd')
SOURCE=BASE/'evo_patch/working/AgoneTest/mavenLib.py'
sys.path.insert(0,str(SOURCE.parent));import evosuite_profile
FUNCTIONS=['command_output_tail','timeout_output_tail','evosuite_classpath_entries',
 'sanitize_evosuite_generation_classpath','should_retry_evosuite_with_sanitized_classpath',
 'common_maven_skip_args','write_pom_tree','edit_pom_file','add_evosuite_pom',
 'run_evosuite_generation_maven','run_maven_test_command']

def write_json(p,obj):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f:json.dump(obj,f,ensure_ascii=False,indent=2);f.write('\n')

def read_csv(p):
    with Path(p).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def isolated_env(out):
    env={k:v for k,v in os.environ.items() if not any(x in k.upper() for x in ['API_KEY','API_TOKEN','OPENAI','ANTHROPIC'])}
    for key in ['JAVA_TOOL_OPTIONS','_JAVA_OPTIONS','JDK_JAVA_OPTIONS']:
        assert not env.get(key),'Unexpected inherited JVM options: '+key
    env['JAVA_HOME']=str(JDK);env['PATH']=str(JDK/'bin')+os.pathsep+env.get('PATH','')
    env['JAVA_TOOL_OPTIONS']='-Xbootclasspath/a:"'+str(JDK/'lib/tools.jar')+'"'
    tmp=out/'temp';tmp.mkdir();env['TMP']=env['TEMP']=str(tmp)
    return env

class Commands:
    def __init__(self,out,env,repo,seed):
        self.out=out;self.env=env;self.repo=Path(repo).resolve();self.seed=seed;self.records=[]
    TimeoutExpired=subprocess.TimeoutExpired
    def run(self,argv,**kw):
        argv=list(map(str,argv));cwd=Path(kw.get('cwd',self.out)).resolve()
        assert cwd.is_relative_to(self.out.resolve()),'Command cwd outside new job'
        exe=Path(argv[0]).name.lower()
        if exe in ['mvn','mvn.cmd']:
            argv[0]=str(MVN)
            argv[1:1]=['-o','-Dmaven.repo.local='+str(self.repo)]
        elif exe in ['java','java.exe']:
            argv[0]=str(JDK/'bin/java.exe')
            if '-jar' in argv:
                assert Path(argv[argv.index('-jar')+1]).resolve()==(audit.ROOT/'scripts_v2/evosuite-1.2.0.jar').resolve()
                argv+=['-seed',str(self.seed)]
                expected=evosuite_profile.maven_generation_options(evosuite_profile.REVIEWER)
                assert all(flag in argv for flag in expected),'Reviewer profile missing on actual argv'
                assert '-Dassertions=false' not in argv and '-Dtest_scaffolding=false' not in argv
        else:raise AssertionError('Executable not allowed: '+exe)
        number=len(self.records)+1;prefix=self.out/('command_%02d'%number)
        kw.update(cwd=cwd,env=self.env,capture_output=True,text=True,errors='replace')
        kw.pop('stdout',None);kw.pop('stderr',None)
        audit.log('EONLY_COMMAND_START',job=str(self.out.relative_to(BASE)),command_index=number,argv=argv,cwd=str(cwd),timeout=kw.get('timeout'))
        started=time.monotonic();timedout=False
        try:r=subprocess.run(argv,**kw);rc=r.returncode;stdout=r.stdout;stderr=r.stderr
        except subprocess.TimeoutExpired as ex:
            timedout=True;rc=-999;stdout=ex.stdout or '';stderr=ex.stderr or ''
            if isinstance(stdout,bytes):stdout=stdout.decode('utf-8',errors='replace')
            if isinstance(stderr,bytes):stderr=stderr.decode('utf-8',errors='replace')
        a=prefix.with_suffix('.stdout.txt');b=prefix.with_suffix('.stderr.txt')
        a.write_text(stdout or '',encoding='utf-8');b.write_text(stderr or '',encoding='utf-8')
        rec={'index':number,'argv':argv,'cwd':str(cwd),'returncode':rc,'timeout':timedout,
             'duration_seconds':time.monotonic()-started,'stdout':str(a.relative_to(BASE)),
             'stderr':str(b.relative_to(BASE)),'stdout_sha256':audit.sha(a),'stderr_sha256':audit.sha(b)}
        if '-jar' in argv:
            artifact_dir=self.out/('generation_attempt_%02d'%number);artifact_dir.mkdir()
            archived=[]
            for root_name in ['src/test/java','evosuite-report']:
                search=cwd/root_name
                if search.is_dir():
                    for source in sorted(search.rglob('*')):
                        if source.is_file():
                            rel=source.relative_to(cwd);dest=artifact_dir/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)
                            archived.append({'relative':rel.as_posix(),'sha256':audit.sha(source)})
            write_json(artifact_dir/'manifest.json',archived)
            rec['generation_artifact_snapshot']=str(artifact_dir.relative_to(BASE))
        self.records.append(rec);write_json(prefix.with_suffix('.json'),rec)
        audit.log('EONLY_COMMAND_END',**rec)
        if timedout:raise subprocess.TimeoutExpired(argv,kw.get('timeout'),stdout,stderr)
        return subprocess.CompletedProcess(argv,rc,stdout,stderr)
    def check_call(self,argv,**kw):
        kw.setdefault('cwd',self.out)
        r=self.run(argv,**kw)
        if r.returncode:raise subprocess.CalledProcessError(r.returncode,r.args)
        return 0

def load_functions(commands,out):
    text=SOURCE.read_text(encoding='utf-8-sig');tree=ast.parse(text)
    nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in FUNCTIONS]
    assert {n.name for n in nodes}==set(FUNCTIONS)
    phases=[]
    def phase(*args,**kw):
        rec={'phase':str(args[0]),**{k:str(v) for k,v in kw.items()}};phases.append(rec)
        audit.log('EONLY_PHASE',job=str(out.relative_to(BASE)),**rec)
    def write_text(path,content):
        path=Path(path).resolve();assert path.is_relative_to(out.resolve());path.parent.mkdir(parents=True,exist_ok=True);path.write_text(content,encoding='utf-8')
    utils=types.SimpleNamespace(append_phase_log=phase,write_text_file=write_text)
    ns={'os':os,'time':time,'Path':Path,'zipfile':zipfile,'re':re,'ET':ET,
        'subprocess':commands,'utils':utils,'evosuite_profile':evosuite_profile,
        'toolchains':types.SimpleNamespace(evosuite_jar=lambda:str(audit.ROOT/'scripts_v2/evosuite-1.2.0.jar'),
            evosuite_runtime_jar=lambda:str(audit.ROOT/'scripts_v2/evosuite-standalone-runtime-1.2.0.jar')),
        'errorCorrection':types.SimpleNamespace(extract_errors=lambda stdout,stderr:(stdout+'\n'+stderr)[-2500:]),
        'MAVEN_TIMEOUT_SECONDS':300,'EVOSUITE_TIMEOUT_SECONDS':240,
        'EVOSUITE_TEST_FRAMEWORK_JAR_PATTERNS':['junit','jupiter','hamcrest','mockito','byte-buddy','objenesis','opentest4j','apiguardian'],
        'java_command':lambda system:str(JDK/'bin/java.exe'),'maven_command':lambda system:str(MVN),
        'maven_settings_args':lambda:['-s',str(out/'settings.xml')] if (out/'settings.xml').is_file() else [], 'jdk_tools_jar':lambda:str(JDK/'lib/tools.jar')}
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(SOURCE),'exec'),ns)
    return ns,phases

def raw_metrics(module,test_fqcn,focal_class,package,gate):
    result={'legacy_process_build':int(gate),'selected_test_fqcn':test_fqcn}
    xmls=sorted((module/'target/surefire-reports').glob('TEST-*.xml'))
    xml=[]
    for p in xmls:
        r=ET.parse(p).getroot();xml.append({'name':r.get('name'),**{k:int(r.get(k,'0')) for k in ['tests','failures','errors','skipped']}})
    result['surefire_suites']=xml
    result['only_selected_suite_executed']=bool(xml) and all(r['name']==test_fqcn for r in xml)
    result['suite_pass']=bool(xml) and result['only_selected_suite_executed'] and sum(r['tests'] for r in xml)>0 and all(r['failures']+r['errors']==0 for r in xml)
    pit=module/'target/pit-reports/mutations.csv';rows=[]
    if pit.exists():
        with pit.open(encoding='utf-8-sig',newline='') as f:rows=list(csv.reader(f))
    assert all(len(r)==7 for r in rows)
    focal=[r for r in rows if r[0].replace('.java','')==focal_class and (r[1].rsplit('.',1)[0] if '.' in r[1] else '')==package]
    result.update(pit_report_present=pit.exists(),module_mutants=len(rows),focal_mutants=len(focal),
        killed_mutants=sum(r[5]=='KILLED' for r in focal),
        focal_mutant_qualified_classes=sorted({r[1] for r in focal}),
        mutation_score_percent=round(100*sum(r[5]=='KILLED' for r in focal)/len(focal),2) if focal else None,
        # Same missing-report/zero-fill convention, with explicit raw evidence status.
        legacy_strict_mutation_percent=(round(100*sum(r[5]=='KILLED' for r in focal)/len(focal),2) if focal else 0.0) if gate else 0.0)
    jac=module/'target/site/jacoco/jacoco.csv';coverage=[]
    if jac.exists():
        coverage=[r for r in read_csv(jac) if r.get('CLASS')==focal_class and r.get('PACKAGE','').replace('/','.')==package]
    result['jacoco_focal_rows']=coverage
    result['measurement_evidence_complete']=result['suite_pass'] and bool(focal) and bool(coverage)
    return result

def execute_job(out,repo,seed,module,focal,info,fixture=False):
    env=isolated_env(out);commands=Commands(out,env,repo,seed);ns,phases=load_functions(commands,out)
    source=focal.read_text(encoding='utf-8-sig',errors='replace')
    m=re.search(r'^\s*package\s+([\w.$]+)\s*;',source,re.M);package=m.group(1) if m else ''
    test_class=focal.stem+'_ESTest';test_fqcn=(package+'.' if package else '')+test_class
    test_path=module/'src/test/java'/Path(*package.split('.'))/(test_class+'.java')
    df=pd.DataFrame([{'Project':info.get('repo_id','fixture'),'Module':info.get('module',''),
        'Focal_Class':focal.stem,'Test_Class':test_class,'Focal_Path':str(focal),'Test_Path':test_path.as_posix()}])
    # Functions are the original POM builders; only this copied E job is passed to them.
    poms=sorted(module.parent.rglob('pom.xml')) if fixture else sorted((out/'repo').rglob('pom.xml'))
    for p in poms:
        rel=p.relative_to(out);dest=out/'backup_poms'/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
    before={str(p.relative_to(out)):audit.sha(p) for p in poms}
    write_json(out/'pom_before_manifest.json',before)
    assert ns['edit_pom_file'](str(module),df,info.get('junit_version') or '4',info.get('testng_version')) is not None
    assert ns['add_evosuite_pom'](str(module)) is not None
    after={str(p.relative_to(out)):audit.sha(p) for p in poms}
    write_json(out/'pom_after_manifest.json',after);audit.log('EONLY_COPIED_POM_EDIT',job=str(out.relative_to(BASE)),before=before,after=after)
    generated=ns['run_evosuite_generation_maven'](str(module),str(focal),'Windows',generation_profile=evosuite_profile.REVIEWER)
    files=sorted((module/'src/test/java').rglob('*ESTest*.java'))
    gh={str(p.relative_to(out)):audit.sha(p) for p in files}
    write_json(out/'generated_manifest.json',gh)
    scaffold=test_path.with_name(test_class+'_scaffolding.java')
    gate=False
    if generated and test_path.exists() and scaffold.exists():
        # Generated files retain original names and bytes; target selectors use the same names.
        gate=ns['run_maven_test_command'](str(module),df,'Windows')[0]
    result={'generation_success':generated,'scaffold_present':scaffold.exists(),'seed':seed,
        **raw_metrics(module,test_fqcn,focal.stem,package,gate),
        'generated_bytes_unchanged':gh=={str(p.relative_to(out)):audit.sha(p) for p in files},
        'generation_attempts':sum('-jar' in r['argv'] for r in commands.records),
        'selected_test_manifest':[test_fqcn],'GPT_API_calls':0,'benchmark':not fixture}
    write_json(out/'result.json',result);write_json(out/'phase_records.json',phases)
    audit.log('EONLY_JOB_COMPLETE',job=str(out.relative_to(BASE)),result_sha256=audit.sha(out/'result.json'),generation_success=generated,legacy_process_build=result['legacy_process_build'])
    return result

def validate_safety():
    tree=ast.parse(Path(__file__).read_text(encoding='utf-8'))
    imports=[ast.unparse(x) for x in ast.walk(tree) if isinstance(x,(ast.Import,ast.ImportFrom))]
    assert not any(re.search(r'\b(openai|utils|agone_test|rbl4_v2_runner|errorCorrection)\b',x) for x in imports)
    assert 'LEGACY' not in ast.unparse(next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='execute_job'))
    return {'imports':imports,'function_AST_source_sha256':audit.sha(SOURCE),'function_whitelist':FUNCTIONS,'GPT_modules_imported':False}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['inspect','fixture']);parser.add_argument('--local-repository',type=Path);a=parser.parse_args()
    STAGE.mkdir(exist_ok=True)
    if a.mode=='inspect':
        report=validate_safety();write_json(STAGE/('static_validation_'+audit.sha(__file__)[:12]+'.json'),report);print(json.dumps(report,indent=2));return
    assert a.local_repository and a.local_repository.is_dir()
    assert a.local_repository.resolve().is_relative_to(audit.ROOT),'Use a workspace-owned cache'
    out=STAGE/'fixture_actual_driver_01';out.mkdir(exist_ok=False)
    prior=BASE/'evo_patch/fixtures/maven_runtime_10'
    module=out/'repo';module.mkdir()
    shutil.copytree(prior/'src/main',module/'src/main')
    # Input POM is the preserved pre-integration fixture POM; old target/tests are not copied.
    shutil.copy2(prior/'pom.xml',module/'pom.xml')
    result=execute_job(out,a.local_repository,20261023,module,module/'src/main/java/fixture/BranchFixture.java',{'junit_version':'4.13.2'},fixture=True)
    print(json.dumps(result,indent=2));assert result['measurement_evidence_complete'] and result['generated_bytes_unchanged']

if __name__=='__main__':main()
