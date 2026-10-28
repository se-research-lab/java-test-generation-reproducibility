"""Synthetic Maven/Surefire/JaCoCo/PIT integration; no study project or original POM edits."""
import csv,json,os,shutil,subprocess,sys,time
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));import audit

def main():
    stage=BASE/'evo_patch';prior=stage/'fixtures/scoped_runtime_08';out=stage/'fixtures/maven_runtime_10'
    out.mkdir(exist_ok=False)
    jdk=Path('C:/Program Files/Java/jdk1.8.0_172')
    runtime=audit.ROOT/'scripts_v2/evosuite-standalone-runtime-1.2.0.jar'
    jars={'runtime':runtime,'junit':Path('C:/Users/admin/.m2/repository/junit/junit/4.13.2/junit-4.13.2.jar'),
          'hamcrest':Path('C:/Users/admin/.m2/repository/org/hamcrest/hamcrest-core/1.3/hamcrest-core-1.3.jar'),
          'tools':jdk/'lib/tools.jar'}
    copies=[]
    for src,dest in [(prior/'src/fixture/BranchFixture.java',out/'src/main/java/fixture/BranchFixture.java'),
        *[(p,out/'src/test/java/fixture'/p.name) for p in sorted((prior/'generated/fixture').glob('*.java'))]]:
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dest);assert audit.sha(src)==audit.sha(dest)
        copies.append({'source':str(src),'copy':str(dest),'sha256':audit.sha(src)})
    def add(parent,tag,text=None):
        x=ET.SubElement(parent,tag)
        if text is not None:x.text=str(text)
        return x
    p=ET.Element('project',xmlns='http://maven.apache.org/POM/4.0.0')
    for k,v in [('modelVersion','4.0.0'),('groupId','local.audit'),('artifactId','synthetic-evo-fixture'),('version','1.0')]:add(p,k,v)
    props=add(p,'properties')
    for k,v in [('maven.compiler.source','1.8'),('maven.compiler.target','1.8'),('project.build.sourceEncoding','UTF-8')]:add(props,k,v)
    deps=add(p,'dependencies')
    for name,g,a,v in [('runtime','org.evosuite','evosuite-standalone-runtime','1.2.0'),('junit','junit','junit','4.13.2'),
                       ('hamcrest','org.hamcrest','hamcrest-core','1.3'),('tools','com.sun','tools','1.8.0')]:
        d=add(deps,'dependency')
        for k,val in [('groupId',g),('artifactId',a),('version',v),('scope','system'),('systemPath',jars[name].as_posix())]:add(d,k,val)
    plugins=add(add(p,'build'),'plugins')
    def plugin(g,a,v):
        pl=add(plugins,'plugin')
        for k,val in [('groupId',g),('artifactId',a),('version',v)]:add(pl,k,val)
        return pl
    plugin('org.apache.maven.plugins','maven-compiler-plugin','3.1')
    sure=add(plugin('org.apache.maven.plugins','maven-surefire-plugin','2.17'),'configuration')
    for k,v in [('argLine','${surefireArgLine} -Djdk.attach.allowAttachSelf=true'),('testFailureIgnore','true'),('forkCount','2'),('reuseForks','false')]:add(sure,k,v)
    jac=plugin('org.jacoco','jacoco-maven-plugin','0.8.7');jc=add(jac,'configuration')
    for k,v in [('propertyName','surefireArgLine'),('skip','false'),('dataFile','${project.build.directory}/jacoco.exec'),('output','file')]:add(jc,k,v)
    add(add(jc,'formats'),'format','CSV')
    executions=add(jac,'executions')
    for ident,goal,phase in [('jacoco-initialize','prepare-agent',None),('jacoco-site','report','test')]:
        ex=add(executions,'execution');add(ex,'id',ident)
        if phase:add(ex,'phase',phase)
        add(add(ex,'goals'),'goal',goal)
    pit=add(plugin('org.pitest','pitest-maven','1.16.0'),'configuration')
    for k,v in [('skip','false'),('exportLineCoverage','true'),('timestampedReports','false')]:add(pit,k,v)
    add(add(pit,'outputFormats'),'outputFormat','CSV')
    feat=add(pit,'features');add(feat,'feature','+CLASSLIMIT(limit[42])');add(feat,'feature','+auto_threads')
    add(add(pit,'targetTests'),'param','fixture.BranchFixture_ESTest')
    ET.indent(p);ET.ElementTree(p).write(out/'pom.xml',encoding='utf-8',xml_declaration=True)
    parent=dict(os.environ)
    assert not any(parent.get(k) for k in ['JAVA_TOOL_OPTIONS','_JAVA_OPTIONS','JDK_JAVA_OPTIONS'])
    env={k:v for k,v in parent.items() if not any(x in k.upper() for x in ['API_KEY','API_TOKEN','OPENAI','ANTHROPIC'])}
    env['JAVA_HOME']=str(jdk);env['PATH']=str(jdk/'bin')+os.pathsep+env.get('PATH','')
    env['JAVA_TOOL_OPTIONS']='-Xbootclasspath/a:"'+str(jdk/'lib/tools.jar')+'"'
    protocol={'scope':'synthetic integration only; 0 study classes, 0 API calls',
        'source_copies':copies,'pom_sha256':audit.sha(out/'pom.xml'),
        'configuration':'mirrors E-specific Surefire2.17, JaCoCo0.8.7, PIT1.16.0; compiler3.1 fixture only',
        'legacy_gate_preserved_in_fixture':True,'validation':'additionally inspect raw Surefire/PIT/JaCoCo; does not change primary scoring',
        'env_delta':{'JAVA_HOME':env['JAVA_HOME'],'JAVA_TOOL_OPTIONS':env['JAVA_TOOL_OPTIONS']},
        'network':'Maven offline; existing dependency cache only','original_POM_edits':0}
    (out/'protocol.json').write_text(json.dumps(protocol,indent=2)+'\n',encoding='utf-8')
    audit.log('MAVEN_FIXTURE_PROTOCOL',path=str((out/'protocol.json').relative_to(BASE)),sha256=audit.sha(out/'protocol.json'))
    argv=['C:/Program Files/Apache/maven/bin/mvn.cmd','-o','-B','clean','verify','jacoco:prepare-agent','jacoco:report','org.pitest:pitest-maven:1.16.0:mutationCoverage']
    audit.log('MAVEN_FIXTURE_START',argv=argv,cwd=str(out),timeout=180)
    start=time.monotonic()
    try:
        r=subprocess.run(argv,cwd=out,env=env,capture_output=True,text=True,errors='replace',timeout=180)
        rc=r.returncode;stdout=r.stdout;stderr=r.stderr
    except subprocess.TimeoutExpired as ex:
        rc=-999;stdout=ex.stdout or '';stderr=ex.stderr or ''
        if isinstance(stdout,bytes):stdout=stdout.decode('utf-8',errors='replace')
        if isinstance(stderr,bytes):stderr=stderr.decode('utf-8',errors='replace')
    for label,value in [('stdout',stdout),('stderr',stderr)]: (out/(label+'.txt')).write_text(value,encoding='utf-8')
    command={'argv':argv,'returncode':rc,'seconds':time.monotonic()-start,'stdout_sha256':audit.sha(out/'stdout.txt'),'stderr_sha256':audit.sha(out/'stderr.txt')}
    (out/'command.json').write_text(json.dumps(command,indent=2)+'\n',encoding='utf-8');audit.log('MAVEN_FIXTURE_END',**command)
    assert dict(os.environ)==parent
    assert all(audit.sha(x['copy'])==x['sha256']==audit.sha(x['source']) for x in copies)
    raw=[]
    for path in (out/'target/surefire-reports').glob('TEST-*.xml'):
        root=ET.parse(path).getroot();raw.append({'path':str(path),'sha256':audit.sha(path),**{k:int(root.get(k,'0')) for k in ['tests','failures','errors','skipped']}})
    pitfile=out/'target/pit-reports/mutations.csv';mutants=[]
    if pitfile.exists():
        with pitfile.open(newline='',encoding='utf-8') as f:mutants=list(csv.reader(f))
    jacfile=out/'target/site/jacoco/jacoco.csv';coverage=[]
    if jacfile.exists():
        with jacfile.open(newline='',encoding='utf-8') as f:coverage=list(csv.DictReader(f))
    passed=rc==0 and bool(raw) and sum(x['tests'] for x in raw)>0 and all(x['failures']+x['errors']==0 for x in raw) and bool(mutants) and bool(coverage)
    report={'status':'PASS' if passed else 'FAIL','returncode':rc,'surefire':raw,
        'mutant_rows':len(mutants),'mutant_statuses':dict(Counter(x[5] for x in mutants)),'jacoco':coverage,
        'raw_artifact_hashes':{str(x.relative_to(out)):audit.sha(x) for x in [pitfile,jacfile] if x.is_file()},
        'generated_bytes_unchanged':True,'parent_environment_unchanged':True,
        'study_projects_executed':0,'original_code_modified':False,
        'limitation':'Mirrored synthetic POM; actual copied pipeline, renaming/scaffold handling and benchmark repos still require validation'}
    rp=stage/'reports/maven_fixture_result.json';rp.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    audit.log('MAVEN_FIXTURE_VALIDATED',status=report['status'],path=str(rp.relative_to(BASE)),sha256=audit.sha(rp))
    print(json.dumps(report,indent=2))
    assert passed,'Maven fixture did not pass all raw checks; inspect preserved stdout/stderr'

if __name__=='__main__':main()
