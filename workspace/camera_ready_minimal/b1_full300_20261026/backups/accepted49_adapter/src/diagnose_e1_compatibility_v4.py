"""Isolated E1 compatibility diagnostics. No generation/API and no E1 score replacement."""
import argparse,concurrent.futures,difflib,json,os,re,shutil,sys,time,zipfile
from datetime import datetime,timezone
from pathlib import Path
from xml.etree import ElementTree as ET
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));sys.path.insert(0,str(BASE/'src'))
import audit
from e49_driver import Commands,isolated_env
STAGE=BASE/'e1_compatibility_diagnostic_v1'
ORIG=BASE/'e49_driver';CACHE=BASE.parent/'maven_cache_20261023'
JOB_IDS=['09','12','13','14','15','18','19','48']
NS={'m':'http://maven.apache.org/POM/4.0.0'}
def dump(p,obj):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f:json.dump(obj,f,ensure_ascii=False,indent=2);f.write('\n')
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def walk(root,exclude=()):
    for folder,dirs,names in os.walk(root):
        dirs[:]=sorted(d for d in dirs if d not in exclude)
        for name in sorted(names):
            p=Path(folder)/name
            assert not p.is_symlink(),str(p)
            yield p

def verify_locked():
    lock=load(ORIG/'readiness_lock.json')
    for rel,h in lock['code_and_input_hashes'].items():assert audit.sha(BASE/rel)==h,rel
    for p,h in lock['tool_hashes'].items():assert audit.sha(p)==h,p
    registry=load(BASE/'audit/final49_static_registry_v1.json')
    for r in registry['files']:assert audit.sha(BASE/r['path'])==r['sha256'],r['path']
    return {'E1_results':audit.sha(ORIG/'results49.json'),'final49_registry':audit.sha(BASE/'audit/final49_static_registry_v1.json')}

def prepare():
    assert not STAGE.exists(),'Never overwrite diagnostics'
    locked=verify_locked();audit.verify()
    STAGE.mkdir()
    protocol={
        'created_utc':datetime.now(timezone.utc).isoformat(),'kind':'post-review compatibility diagnosis only; known outcomes',
        'jobs':JOB_IDS,'reviewer':['R2.1 runtime/scaffolding','R3.4 harness'],
        'no_generation':True,'GPT_API_calls':0,'no_replacement_of_E1_scores':True,
        'source_protocol_sha256':audit.sha(BASE/'PROTOCOL_CHAN_DOAN_E1_COMPATIBILITY.md'),
        'script_sha256':audit.sha(__file__),'frozen_E1':locked,
        'cache':'Separate full byte-verified copy; offline only; no install/deploy',
        'C01_patch':'Only direct test-scope junit:junit module dependency version4.13.2 for09,12-15',
        'C02_first':'Effective POM on unchanged newcopy before any execution-specific patch',
        'C03':'Unmodified fullsuite, thenmethod selection in fresh fork; no sandbox/limit/source changes',
        'timeout_seconds':{'dependency':180,'test':300,'effective_pom':180},
        'acceptance':'Report errors, skips, foreign tests, source/classpath/classbyte hashes separately; exit0 not pass',
        'stop':'Unexpected POM/source/production dependency/bytecode drift; no automatic additional fixes',
        'not_new_baseline_or_repeated_run_study':True,
    }
    dump(STAGE/'protocol.json',protocol)
    audit.log('E1_COMPATIBILITY_DIAGNOSTIC_PROTOCOL',path=str((STAGE/'protocol.json').relative_to(BASE)),sha256=audit.sha(STAGE/'protocol.json'),**locked)
    cacheout=STAGE/'maven_cache';cacheout.mkdir()
    files=list(walk(CACHE));records=[]
    audit.log('E1_COMPATIBILITY_CACHE_COPY_START',source=str(CACHE),destination=str(cacheout),files=len(files))
    def copyfile(p):
        rel=p.relative_to(CACHE);dest=cacheout/rel;dest.parent.mkdir(parents=True,exist_ok=True)
        before=audit.sha(p);shutil.copy2(p,dest)
        assert audit.sha(dest)==before==audit.sha(p),str(p)
        return {'relative':rel.as_posix(),'sha256':before,'bytes':p.stat().st_size}
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:records=list(pool.map(copyfile,files))
    dump(STAGE/'cache_copy_manifest.json',records)
    audit.log('E1_COMPATIBILITY_CACHE_COPY_COMPLETE',files=len(records),bytes=sum(r['bytes'] for r in records),manifest_sha256=audit.sha(STAGE/'cache_copy_manifest.json'))
    inputs=[]
    for job in JOB_IDS:
        old=ORIG/'jobs'/job;out=STAGE/'jobs'/job;out.mkdir(parents=True)
        cmd=load(old/'command_04.json');module_rel=Path(cmd['cwd']).relative_to(old/'repo')
        sourcefiles=list(walk(old/'repo',exclude={'.git','target','node_modules','evosuite-report','.gradle'}));rows=[]
        for source in sourcefiles:
            rel=source.relative_to(old/'repo');dest=out/'repo'/rel;dest.parent.mkdir(parents=True,exist_ok=True)
            h=audit.sha(source);shutil.copy2(source,dest);assert h==audit.sha(dest)==audit.sha(source)
            rows.append({'relative':rel.as_posix(),'sha256':h,'bytes':source.stat().st_size})
        shutil.copy2(old/'settings.xml',out/'settings.xml')
        generated=load(old/'generated_manifest.json')
        for rel,h in generated.items():
            assert audit.sha(old/rel)==h==audit.sha(out/rel),rel
        oldmodule=old/'repo'/module_rel
        classes={p.relative_to(oldmodule/'target/classes').as_posix():audit.sha(p) for p in (oldmodule/'target/classes').rglob('*.class')}
        assert classes
        dump(out/'input_source_manifest.json',rows);dump(out/'production_class_baseline.json',classes)
        info={'job':job,'module_relative':module_rel.as_posix(),'selected_test_fqcn':load(old/'result.json')['selected_test_fqcn'],
              'locked_generated':generated,'source_manifest_sha256':audit.sha(out/'input_source_manifest.json'),
              'production_class_manifest_sha256':audit.sha(out/'production_class_baseline.json'),
              'settings_sha256':audit.sha(out/'settings.xml'),'original_command_sha256':audit.sha(old/'command_04.json')}
        dump(out/'input.json',info);inputs.append({'job':job,'input_sha256':audit.sha(out/'input.json')})
        audit.log('E1_COMPATIBILITY_NEW_COPY_READY',job=job,files=len(rows),input_sha256=audit.sha(out/'input.json'),source_modified=False)
    dump(STAGE/'input_lock.json',{'jobs':inputs,'script_sha256':audit.sha(__file__),'protocol_sha256':audit.sha(STAGE/'protocol.json')})
    print(json.dumps({'status':'PREPARED','jobs':JOB_IDS,'cache_files':len(records),'cache_bytes':sum(r['bytes'] for r in records)},indent=2))

class DiagnosticCommands(Commands):
    def run(self,argv,**kw):
        existing=[int(m.group(1)) for p in self.out.glob('command_*') if (m:=re.match(r'command_(\d+)\.',p.name))]
        self.records=[None]*(max(existing,default=0))
        prefix=self.out/('command_%02d'%(len(self.records)+1))
        assert not any(prefix.with_suffix(ext).exists() for ext in ['.json','.stdout.txt','.stderr.txt'])
        return super().run(argv,**kw)

def context(job):
    assert job in JOB_IDS
    lock=load(STAGE/'input_lock.json');assert lock['script_sha256']==audit.sha(__file__)
    assert lock['protocol_sha256']==audit.sha(STAGE/'protocol.json')
    out=STAGE/'jobs'/job
    expected=next(r for r in lock['jobs'] if r['job']==job)
    assert audit.sha(out/'input.json')==expected['input_sha256']
    info=load(out/'input.json');module=out/'repo'/info['module_relative']
    assert audit.sha(out/'input_source_manifest.json')==info['source_manifest_sha256']
    assert audit.sha(out/'production_class_baseline.json')==info['production_class_manifest_sha256']
    assert audit.sha(out/'settings.xml')==info['settings_sha256']
    source_rows=load(out/'input_source_manifest.json')
    expected_paths={row['relative'] for row in source_rows}
    current_paths={p.relative_to(out/'repo').as_posix() for p in walk(out/'repo',exclude={'.git','target','node_modules','evosuite-report','.gradle'})}
    assert expected_paths==current_paths,'Source file membership drift'
    for row in source_rows:
        source=out/'repo'/row['relative']
        expected_hash=row['sha256']
        patch=out/'junit_patch.json'
        if patch.exists() and source==module/'pom.xml':expected_hash=load(patch)['after_sha256']
        assert audit.sha(source)==expected_hash,row['relative']
    for rel,h in info['locked_generated'].items():assert audit.sha(out/rel)==h,rel
    verify_locked()
    env=isolated_env(out) if not (out/'temp').exists() else None
    if env is None:
        env={k:v for k,v in os.environ.items() if not any(x in k.upper() for x in ['API_KEY','API_TOKEN','OPENAI','ANTHROPIC'])}
        env['JAVA_HOME']='C:/Program Files/Java/jdk1.8.0_172';env['PATH']=env['JAVA_HOME']+'/bin'+os.pathsep+env.get('PATH','')
        for k in ['_JAVA_OPTIONS','JDK_JAVA_OPTIONS']:assert not env.get(k)
        env['JAVA_TOOL_OPTIONS']='-Xbootclasspath/a:"'+env['JAVA_HOME']+'/lib/tools.jar"'
        env['TMP']=env['TEMP']=str(out/'temp')
    attempt=out/('attempt_'+str(len(list(out.glob('attempt_*')))+1).zfill(2));attempt.mkdir()
    env['TMP']=env['TEMP']=str(attempt/'temp');(attempt/'temp').mkdir()
    commands=DiagnosticCommands(attempt,env,STAGE/'maven_cache',0)
    # Commands checks cwd within its output; use the job as containment and attempt-owned record prefix.
    commands.out=out
    dump(attempt/'environment_allowlist.json',{k:env.get(k) for k in ['JAVA_HOME','JAVA_TOOL_OPTIONS','TMP','TEMP']})
    baseargv=load(ORIG/'jobs'/job/'command_04.json')['argv']
    start=baseargv.index('-Dtest='+info['selected_test_fqcn'])
    flags=baseargv[start:baseargv.index('clean')]
    args=['mvn','-s',str(out/'settings.xml'),*flags]
    # Store each invocation in a unique job command number; Commands never overwrites previous attempts.
    commands.records=[None]*len(list(out.glob('command_*.json')))
    return out,info,module,commands,args,attempt

def dependency(commands,args,module,attempt,name):
    tree=attempt/(name+'_tree.txt');cp=attempt/(name+'_test_classpath.txt')
    argv=[*args,'org.apache.maven.plugins:maven-dependency-plugin:3.7.0:tree',
          'org.apache.maven.plugins:maven-dependency-plugin:3.7.0:build-classpath',
          '-DoutputFile='+str(tree),'-Dmdep.outputFile='+str(cp),'-DincludeScope=test']
    r=commands.run(argv,cwd=module,timeout=180)
    entries=[]
    if cp.exists():
        for value in cp.read_text(encoding='utf-8').strip().split(os.pathsep):
            p=Path(value);assert p.is_file(),value
            if p.is_relative_to(STAGE/'maven_cache'):key=p.relative_to(STAGE/'maven_cache').as_posix()
            else:key=str(p)
            entries.append({'path':key,'sha256':audit.sha(p),'bytes':p.stat().st_size})
    cache_manifest={r['relative']:r['sha256'] for r in load(STAGE/'cache_copy_manifest.json')}
    for row in entries:
        if not Path(row['path']).is_absolute():assert cache_manifest[row['path']]==row['sha256'],row['path']
    compile_cp=attempt/(name+'_compile_classpath.txt')
    compile_result=commands.run([*args,'org.apache.maven.plugins:maven-dependency-plugin:3.7.0:build-classpath','-Dmdep.outputFile='+str(compile_cp),'-DincludeScope=compile'],cwd=module,timeout=180)
    compile_entries=[]
    if compile_cp.exists():
        for value in compile_cp.read_text(encoding='utf-8').strip().split(os.pathsep):
            p=Path(value);assert p.is_file(),value
            key=p.relative_to(STAGE/'maven_cache').as_posix() if p.is_relative_to(STAGE/'maven_cache') else str(p)
            h=audit.sha(p)
            if not p.is_absolute() or p.is_relative_to(STAGE/'maven_cache'):assert cache_manifest[key]==h,key
            compile_entries.append({'path':key,'sha256':h})
    report={'returncode':r.returncode,'compile_returncode':compile_result.returncode,'compile_classpath':compile_entries,'classpath':entries,'tree':str(tree),'tree_sha256':audit.sha(tree) if tree.exists() else None}
    dump(attempt/(name+'_dependency.json'),report);return report

def patch_junit(module,out):
    p=module/'pom.xml';before=p.read_text(encoding='utf-8');root=ET.fromstring(before)
    deps=root.findall('m:dependencies/m:dependency',NS)
    dep=[d for d in deps if d.findtext('m:groupId',namespaces=NS)=='junit' and d.findtext('m:artifactId',namespaces=NS)=='junit']
    assert len(dep)==1 and dep[0].findtext('m:scope',namespaces=NS)=='test'
    old=dep[0].findtext('m:version',namespaces=NS)
    assert old in [None,'4.8','4.8.2'],old
    matches=list(re.finditer(r'<dependency\b[^>]*>.*?</dependency>',before,re.S))
    candidates=[m for m in matches if re.search(r'<groupId>\s*junit\s*</groupId>',m.group()) and re.search(r'<artifactId>\s*junit\s*</artifactId>',m.group())]
    assert len(candidates)==1
    match=candidates[0];chunk=match.group()
    if old:patched=re.sub(r'<version>.*?</version>','<version>4.13.2</version>',chunk,count=1,flags=re.S)
    else:patched=chunk.replace('</artifactId>','</artifactId><version>4.13.2</version>',1)
    after=before[:match.start()]+patched+before[match.end():]
    # Semantic whitelist: removing changed version gives an identical XML tree.
    a=ET.fromstring(before);b=ET.fromstring(after)
    bd=[d for d in b.findall('m:dependencies/m:dependency',NS) if d.findtext('m:groupId',namespaces=NS)=='junit' and d.findtext('m:artifactId',namespaces=NS)=='junit'][0]
    if old:bd.find('m:version',NS).text=old
    else:bd.remove(bd.find('m:version',NS))
    assert ET.tostring(a)==ET.tostring(b)
    backup=out/'backup_before_junit_patch/pom.xml';backup.parent.mkdir();shutil.copy2(p,backup)
    p.write_text(after,encoding='utf-8')
    diff=out/'junit_patch.diff';diff.write_text(''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='before/pom.xml',tofile='after/pom.xml')),encoding='utf-8')
    report={'before_sha256':audit.sha(backup),'after_sha256':audit.sha(p),'old_version':old or 'inherited','new_version':'4.13.2','scope':'test','semantic_change_only_junit_version':True,'diff_sha256':audit.sha(diff)}
    dump(out/'junit_patch.json',report);audit.log('E1_COMPATIBILITY_COPIED_POM_PATCH',job=out.name,**report)

def verify_job(out,info,module):
    for rel,h in info['locked_generated'].items():assert audit.sha(out/rel)==h,rel
    baseline=load(out/'production_class_baseline.json')
    current={p.relative_to(module/'target/classes').as_posix():audit.sha(p) for p in (module/'target/classes').rglob('*.class')}
    mismatch=sorted(k for k in set(baseline)|set(current) if baseline.get(k)!=current.get(k))
    sourceissues=[]
    expected_paths={row['relative'] for row in load(out/'input_source_manifest.json')}
    current_paths={p.relative_to(out/'repo').as_posix() for p in walk(out/'repo',exclude={'.git','target','node_modules','evosuite-report','.gradle'})}
    sourceissues.extend(sorted(expected_paths^current_paths))
    allowed=(Path('repo')/info['module_relative']/'pom.xml').as_posix()
    for row in load(out/'input_source_manifest.json'):
        p=out/'repo'/row['relative']
        if p.relative_to(out).as_posix()!=allowed and audit.sha(p)!=row['sha256']:sourceissues.append(row['relative'])
    xml=[];fqcn=info['selected_test_fqcn']
    java=module/'src/test/java'/Path(*fqcn.split('.')).with_suffix('.java')
    methods=sorted(set(re.findall(r'public\s+void\s+(test\w*)\s*\(',java.read_text(encoding='utf-8'))))
    cases=[]
    for p in sorted((module/'target/surefire-reports').glob('TEST-*.xml')):
        root=ET.parse(p).getroot();xml.append({'name':root.get('name'),'sha256':audit.sha(p),'tests':int(root.get('tests','0')),'errors':int(root.get('errors','0')),'failures':int(root.get('failures','0')),'skipped':int(root.get('skipped','0'))})
        for t in root.findall('testcase'):cases.append({'class':t.get('classname'),'name':t.get('name'),'errors':len(t.findall('error')),'failures':len(t.findall('failure')),'skipped':len(t.findall('skipped'))})
    foreign=[r for r in cases if r['class']!=fqcn or r['name'] not in methods]
    passflag=bool(cases) and not foreign and all(r['errors']+r['failures']+r['skipped']==0 for r in cases) and sorted(set(r['name'] for r in cases))==methods
    return {'source_issues':sourceissues,'production_class_count':len(current),'production_class_mismatches':mismatch,'locked_generated_unchanged':True,'expected_test_methods':methods,'XML_suites':xml,'testcases':cases,'foreign_cases':foreign,'selected_suite_all_methods_pass':passflag}

def junit(job):
    assert job in ['09','12','13','14','15']
    out,info,module,commands,args,attempt=context(job)
    before=dependency(commands,args,module,attempt,'before');assert before['returncode']==0 and before['compile_returncode']==0 and before['classpath'] and before['compile_classpath']
    jars=[r for r in before['classpath'] if r['path'].startswith('junit/junit/')]
    assert len(jars)==1
    with zipfile.ZipFile(STAGE/'maven_cache'/jars[0]['path']) as z:assert 'org/junit/rules/TestRule.class' not in z.namelist()
    patch_junit(module,out)
    after=dependency(commands,args,module,attempt,'after');assert after['returncode']==0 and after['compile_returncode']==0 and after['classpath'] and after['compile_classpath']
    selected_junit=[r for r in after['classpath'] if r['path'].startswith('junit/junit/')]
    assert len(selected_junit)==1 and selected_junit[0]['path']=='junit/junit/4.13.2/junit-4.13.2.jar',selected_junit
    assert sorted((r['path'],r['sha256']) for r in before['compile_classpath'])==sorted((r['path'],r['sha256']) for r in after['compile_classpath']),'Compile-scope production closure drift'
    def allow(r):return r['path'].startswith(('junit/junit/','org/hamcrest/'))
    production_before=sorted((r['path'],r['sha256']) for r in before['classpath'] if not allow(r))
    production_after=sorted((r['path'],r['sha256']) for r in after['classpath'] if not allow(r))
    assert production_before==production_after,'Non JUnit/Hamcrest dependency drift'
    with zipfile.ZipFile(STAGE/'maven_cache/junit/junit/4.13.2/junit-4.13.2.jar') as z:assert 'org/junit/rules/TestRule.class' in z.namelist()
    result=commands.run([*args,'clean','test'],cwd=module,timeout=300)
    report={'job':job,'kind':'C01 diagnostic only; not new E1 score','command_returncode':result.returncode,'non_junit_hamcrest_dependency_hashes_unchanged':True,'compile_scope_dependency_hashes_unchanged':True,'selected_JUnit_version':'4.13.2',**verify_job(out,info,module),'GPT_API_calls':0,'generation_calls':0}
    dump(out/'diagnostic_result.json',report)
    audit.log('E1_COMPATIBILITY_C01_COMPLETE',job=job,report_sha256=audit.sha(out/'diagnostic_result.json'),suite_pass=report['selected_suite_all_methods_pass'],production_class_mismatches=report['production_class_mismatches'])
    print(json.dumps(report,ensure_ascii=False,indent=2))
    assert not report['source_issues'] and not report['production_class_mismatches'],'Unexpected original input/bytecode drift'

def effective(job):
    assert job in ['18','19']
    out,info,module,commands,args,attempt=context(job)
    dest=attempt/'effective_pom.xml'
    r=commands.run([*args,'org.apache.maven.plugins:maven-help-plugin:3.2.0:effective-pom','-Doutput='+str(dest)],cwd=module,timeout=180)
    report={'job':job,'returncode':r.returncode,'effective_pom':str(dest),'sha256':audit.sha(dest) if dest.exists() else None,'POM_modified':False}
    dump(attempt/'effective_result.json',report);print(json.dumps(report))

def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','junit','effective']);p.add_argument('--job');a=p.parse_args()
    if a.mode=='prepare':prepare()
    elif a.mode=='junit':junit(a.job)
    else:effective(a.job)
if __name__=='__main__':main()
