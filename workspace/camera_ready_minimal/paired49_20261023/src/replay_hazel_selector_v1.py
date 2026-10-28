"""New-copy Hazelcast include-selector diagnosis; no generation/PIT/source test changes."""
import difflib,json,re,shutil,sys
from pathlib import Path
from xml.etree import ElementTree as ET
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));sys.path.insert(0,str(BASE/'src'));import audit
import diagnose_e1_compatibility_v4 as mod
assert audit.sha(BASE/'src/diagnose_e1_compatibility_v4.py')=='82ad00778ff7cb423f16051ede46d316238dbf45b354e90d9216ca20a9517ed9'
NS=mod.NS

def normalized(root):
    for e in root.iter():
        if e.text is not None and not e.text.strip():e.text=None
        if e.tail is not None and not e.tail.strip():e.tail=None
    return ET.tostring(root)

def main(job):
    assert job in ['18','19'];mod.verify_locked()
    source=mod.STAGE/'jobs'/job;info=mod.load(source/'input.json')
    assert (source/'hazel_direct_result.json').exists()
    prior=mod.load(source/'hazel_direct_result.json');assert not prior['testcases']
    assert prior['command_returncode']!=0
    out=mod.STAGE/'selector_correction_v1'/job;out.mkdir(parents=True,exist_ok=False)
    protocol={'job':job,'reason':'Effective Surefire multiple inherited executions retains leading-slash include; compiled selected class not scanned','change':'Append same-id regular-tests execution with exact relative selected includes combine.self=override in new module POM','unchanged':['test/scaffold bytes','production dependencies/bytecode','JUnit4.13.1','Surefire2.17','PIT/JaCoCo versions','selected FQCN','sandbox/resource limits'],'no_generation':True,'GPT_API_calls':0,'PIT_calls':0,'E1_scores_replaced':False,'script_sha256':audit.sha(__file__),'source_input_sha256':audit.sha(source/'input.json'),'source_effective_surefire_sha256':audit.sha(source/'effective_surefire.json')}
    mod.dump(out/'protocol.json',protocol);audit.log('E1_COMPATIBILITY_SELECTOR_PROTOCOL',job=job,sha256=audit.sha(out/'protocol.json'))
    rows=mod.load(source/'input_source_manifest.json')
    for row in rows:
        p=source/'repo'/row['relative'];assert audit.sha(p)==row['sha256']
        dest=out/'repo'/row['relative'];dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest);assert audit.sha(dest)==row['sha256']
    module=out/'repo'/info['module_relative'];oldmodule=source/'repo'/info['module_relative']
    for directory in ['classes','test-classes']:
        sr=oldmodule/'target'/directory;assert sr.is_dir()
        for p in mod.walk(sr):
            rel=p.relative_to(sr);dest=module/'target'/directory/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest);assert audit.sha(dest)==audit.sha(p)
    for name in ['input_source_manifest.json','production_class_baseline.json','input.json','settings.xml']:
        shutil.copy2(source/name,out/name);assert audit.sha(source/name)==audit.sha(out/name)
    for rel,h in info['locked_generated'].items():assert audit.sha(out/rel)==h
    # Add only exact includes in one execution. Parent/configuration/plugin versions untouched.
    pom=module/'pom.xml';before=pom.read_text(encoding='utf-8');root=ET.fromstring(before)
    plugin=next(p for p in root.findall('m:build/m:plugins/m:plugin',NS) if p.findtext('m:artifactId',namespaces=NS)=='maven-surefire-plugin')
    assert plugin.find('m:executions',NS) is None
    fqcn=info['selected_test_fqcn'];include=fqcn.replace('.','/')+'.java'
    insert='<executions><execution><id>regular-tests</id><configuration><includes combine.self="override"><include>'+include+'</include></includes></configuration></execution></executions>'
    blocks=[m for m in re.finditer(r'<plugin\b[^>]*>.*?</plugin>',before,re.S) if '<artifactId>maven-surefire-plugin</artifactId>' in m.group()]
    assert len(blocks)==1;m=blocks[0];chunk=m.group();after=before[:m.start()]+chunk.replace('</plugin>',insert+'</plugin>',1)+before[m.end():]
    check=ET.fromstring(after);p=next(p for p in check.findall('m:build/m:plugins/m:plugin',NS) if p.findtext('m:artifactId',namespaces=NS)=='maven-surefire-plugin');p.remove(p.find('m:executions',NS))
    assert normalized(ET.fromstring(before))==normalized(check)
    backup=out/'backup_before_selector/pom.xml';backup.parent.mkdir();shutil.copy2(pom,backup);pom.write_text(after,encoding='utf-8')
    diff=out/'selector_patch.diff';diff.write_text(''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='before/pom.xml',tofile='after/pom.xml')),encoding='utf-8')
    patch={'before_sha256':audit.sha(backup),'after_sha256':audit.sha(pom),'include':include,'execution':'regular-tests','semantic_only_execution_include':True,'diff_sha256':audit.sha(diff)}
    mod.dump(out/'selector_patch.json',patch);audit.log('E1_COMPATIBILITY_SELECTOR_POM_PATCH',job=job,**patch)
    env=mod.isolated_env(out);commands=mod.DiagnosticCommands(out,env,mod.STAGE/'maven_cache',0)
    oldargv=mod.load(mod.ORIG/'jobs'/job/'command_04.json')['argv'];start=oldargv.index('-Dtest='+fqcn);flags=oldargv[start:oldargv.index('clean')]
    args=['mvn','-s',str(out/'settings.xml'),*flags]
    mod.dump(out/'environment_allowlist.json',{k:env.get(k) for k in ['JAVA_HOME','JAVA_TOOL_OPTIONS','TMP','TEMP']})
    effective=out/'effective_pom.xml'
    r=commands.run([*args,'org.apache.maven.plugins:maven-help-plugin:3.2.0:effective-pom','-Doutput='+str(effective)],cwd=module,timeout=180);assert r.returncode==0
    p=next(p for p in ET.parse(effective).getroot().findall('m:build/m:plugins/m:plugin',NS) if p.findtext('m:artifactId',namespaces=NS)=='maven-surefire-plugin');assert p.findtext('m:version',namespaces=NS)=='2.17'
    executions=p.findall('m:executions/m:execution',NS);assert [e.findtext('m:id',namespaces=NS) for e in executions]==['default-test','serial-tests','regular-tests']
    regular=next(e for e in executions if e.findtext('m:id',namespaces=NS)=='regular-tests');includes=regular.findall('m:configuration/m:includes/m:include',NS);assert [i.text for i in includes]==[include]
    dep=mod.dependency(commands,args,module,out,'patched');assert dep['returncode']==dep['compile_returncode']==0
    olddep=mod.load(next(source.glob('attempt_*/unchanged_dependency.json')))
    for key in ['classpath','compile_classpath']:
        assert sorted((r['path'],r['sha256']) for r in dep[key])==sorted((r['path'],r['sha256']) for r in olddep[key]),key
    r=commands.run([*args,'-X','-Dmaven.test.skip=false','-DskipTests=false','-DfailIfNoTests=true','org.jacoco:jacoco-maven-plugin:0.8.7:prepare-agent','org.apache.maven.plugins:maven-surefire-plugin:2.17:test@regular-tests'],cwd=module,timeout=300)
    result={'job':job,'diagnosis':'exact relative include selector','command_returncode':r.returncode,'test_and_compile_dependency_hashes_unchanged':True,**mod.verify_job(out,info,module),'POM_sha256_after':audit.sha(pom),'E1_scores_replaced':False,'GPT_API_calls':0,'generation_calls':0,'PIT_calls':0}
    assert audit.sha(pom)==patch['after_sha256']
    assert not result['source_issues'] and not result['production_class_mismatches']
    result['strict_suite_pass']=result['selected_suite_all_methods_pass'] and bool(result['XML_suites']) and all(s['name']==fqcn and s['tests']>0 and s['errors']+s['failures']+s['skipped']==0 for s in result['XML_suites'])
    mod.dump(out/'result.json',result);audit.log('E1_COMPATIBILITY_SELECTOR_COMPLETE',job=job,report_sha256=audit.sha(out/'result.json'),suite_pass=result['strict_suite_pass'],E1_scores_replaced=False)
    print(json.dumps({'job':job,'command_returncode':r.returncode,'strict_suite_pass':result['strict_suite_pass'],'testmethods':len(result['expected_test_methods']),'XML_suites':result['XML_suites'],'production_classes_unchanged':result['production_class_count'],'no_new_scores':True},indent=2))
if __name__=='__main__':assert sys.argv[1]=='selector';main(sys.argv[2])
