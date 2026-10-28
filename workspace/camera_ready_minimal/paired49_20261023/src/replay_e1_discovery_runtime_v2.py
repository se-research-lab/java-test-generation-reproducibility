"""Hazelcast effective execution and unmodified runtime replay; diagnostic only."""
import importlib.util,json,re,shutil,sys
from pathlib import Path
from xml.etree import ElementTree as ET
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));import audit
SOURCE=BASE/'src/diagnose_e1_compatibility_v4.py'
assert audit.sha(SOURCE)=='82ad00778ff7cb423f16051ede46d316238dbf45b354e90d9216ca20a9517ed9'
spec=importlib.util.spec_from_file_location('compatibility_locked_v4',SOURCE);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
NS=mod.NS

def snapshot_reports(module,dest):
    dest.mkdir(exist_ok=False);rows=[]
    root=module/'target/surefire-reports'
    if root.exists():
        for source in sorted(root.rglob('*')):
            if not source.is_file():continue
            rel=source.relative_to(root);p=dest/rel;p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,p)
            assert audit.sha(source)==audit.sha(p)
            rows.append({'relative':rel.as_posix(),'sha256':audit.sha(p)})
    mod.dump(dest/'snapshot_manifest.json',rows)

def postchecks(out,info,module):
    report=mod.verify_job(out,info,module)
    original=next(row['sha256'] for row in mod.load(out/'input_source_manifest.json') if Path(row['relative'])==Path(info['module_relative'])/'pom.xml')
    assert audit.sha(module/'pom.xml')==original,'Unmodified diagnostic POM drift'
    assert not report['source_issues'] and not report['production_class_mismatches'],report
    return report

def preserve_prior_reports(module,attempt):
    source=module/'target/surefire-reports';dest=attempt/'prior_reports'
    assert source.resolve().is_relative_to(mod.STAGE.resolve()) and dest.resolve().is_relative_to(mod.STAGE.resolve())
    if source.exists():
        assert not dest.exists()
        before={p.relative_to(source).as_posix():audit.sha(p) for p in source.rglob('*') if p.is_file()}
        shutil.move(str(source),str(dest))
        assert before=={p.relative_to(dest).as_posix():audit.sha(p) for p in dest.rglob('*') if p.is_file()}
        mod.dump(attempt/'prior_reports_manifest.json',before)
        audit.log('E1_COMPATIBILITY_PRIOR_REPORTS_PRESERVED',source=str(source),destination=str(dest),manifest_sha256=audit.sha(attempt/'prior_reports_manifest.json'))

def collect_hazel(job):
    assert job in ['18','19']
    out,info,module,commands,args,attempt=mod.context(job)
    assert not (out/'hazel_collect_result.json').exists()
    effective=attempt/'effective_pom.xml';profiles=attempt/'active_profiles.txt'
    r=commands.run([*args,'org.apache.maven.plugins:maven-help-plugin:3.2.0:effective-pom','-Doutput='+str(effective)],cwd=module,timeout=180)
    assert r.returncode==0 and effective.exists()
    p=commands.run([*args,'org.apache.maven.plugins:maven-help-plugin:3.2.0:active-profiles','-Doutput='+str(profiles)],cwd=module,timeout=180)
    root=ET.parse(effective).getroot()
    plugins=[e for e in root.findall('m:build/m:plugins/m:plugin',NS) if e.findtext('m:artifactId',namespaces=NS)=='maven-surefire-plugin']
    assert len(plugins)==1;plugin=plugins[0]
    parsed={'version':plugin.findtext('m:version',namespaces=NS),'base_configuration':ET.tostring(plugin.find('m:configuration',NS),encoding='unicode'),'executions':[{'id':e.findtext('m:id',namespaces=NS),'xml':ET.tostring(e,encoding='unicode')} for e in plugin.findall('m:executions/m:execution',NS)]}
    assert parsed['version']=='2.17'
    mod.dump(out/'effective_surefire.json',parsed)
    deps=mod.dependency(commands,args,module,attempt,'unchanged');assert deps['returncode']==0 and deps['compile_returncode']==0
    r=commands.run([*args,'test-compile'],cwd=module,timeout=300)
    report={'job':job,'phase':'collect effective config and compile only','compile_returncode':r.returncode,'active_profiles_returncode':p.returncode,'effective_POM_sha256':audit.sha(effective),**postchecks(out,info,module),'no_POM_patch':True,'no_generation':True,'GPT_API_calls':0}
    mod.dump(out/'hazel_collect_result.json',report)
    audit.log('E1_COMPATIBILITY_C02_EFFECTIVE_COLLECTED',job=job,effective_POM_sha256=audit.sha(effective),report_sha256=audit.sha(out/'hazel_collect_result.json'))
    print(json.dumps({'job':job,'phase':'effective collected','compile_returncode':r.returncode,'Surefire_version':parsed['version'],'executions':[e['id'] for e in parsed['executions']],'production_classes':report['production_class_count']},indent=2))

def hazel_direct(job):
    assert job in ['18','19']
    out,info,module,commands,args,attempt=mod.context(job)
    assert not (out/'hazel_direct_result.json').exists()
    prior=mod.load(out/'hazel_collect_result.json');assert prior['compile_returncode']==0
    parsed=mod.load(out/'effective_surefire.json')
    regular=next(e for e in parsed['executions'] if e['id']=='regular-tests')
    assert 'skip' in parsed['base_configuration'] and '<' in regular['xml']
    # This is a selector diagnostic: a single inherited regular execution, no serial execution first.
    overrides=['-Dmaven.test.skip=false','-DskipTests=false','-DfailIfNoTests=true','-DfailIfNoSpecifiedTests=true']
    plan={'job':job,'effective_surefire_sha256':audit.sha(out/'effective_surefire.json'),'execution':'regular-tests','overrides':overrides,'source_POM_patch':False,'generation_calls':0,'no_new_mutation_score':True}
    mod.dump(attempt/'execution_plan.json',plan);audit.log('E1_COMPATIBILITY_C02_EXECUTION_PLAN',job=job,sha256=audit.sha(attempt/'execution_plan.json'))
    preserve_prior_reports(module,attempt)
    r=commands.run([*args,'-X',*overrides,'org.jacoco:jacoco-maven-plugin:0.8.7:prepare-agent','org.apache.maven.plugins:maven-surefire-plugin:2.17:test@regular-tests'],cwd=module,timeout=300)
    report={'job':job,'kind':'single-execution discovery diagnosis only','command_returncode':r.returncode,**postchecks(out,info,module),'GPT_API_calls':0,'generation_calls':0}
    snapshot_reports(module,attempt/'surefire_archive');mod.dump(out/'hazel_direct_result.json',report)
    audit.log('E1_COMPATIBILITY_C02_DIRECT_COMPLETE',job=job,report_sha256=audit.sha(out/'hazel_direct_result.json'),suite_pass=report['selected_suite_all_methods_pass'])
    print(json.dumps({'job':job,'command_returncode':r.returncode,'selected_suite_all_methods_pass':report['selected_suite_all_methods_pass'],'expected_methods':len(report['expected_test_methods']),'XML_suites':report['XML_suites'],'foreign_cases':report['foreign_cases']},indent=2))

def runtime48(method=None):
    job='48';out,info,module,commands,args,attempt=mod.context(job)
    dest=out/('runtime_'+(method or 'full')+'_result.json')
    assert not dest.exists()
    if method:
        assert method in ['test0','test1','test2']
        assert (out/'runtime_full_result.json').exists()
        args=[('-Dtest='+info['selected_test_fqcn']+'#'+method) if v.startswith('-Dtest=') else v for v in args]
        goals=['org.jacoco:jacoco-maven-plugin:0.8.7:prepare-agent','org.apache.maven.plugins:maven-surefire-plugin:2.17:test']
    else:goals=['clean','test']
    plan={'job':job,'method':method,'kind':'fresh Maven invocation/fork, same unmodified suite bytes','goals':goals,'POM_patch':False,'no_new_score':True,'no_sandbox_or_resource_limit_override':True}
    mod.dump(attempt/'runtime_plan.json',plan);audit.log('E1_COMPATIBILITY_C03_PLAN',sha256=audit.sha(attempt/'runtime_plan.json'),method=method)
    preserve_prior_reports(module,attempt)
    r=commands.run([*args,*goals],cwd=module,timeout=300)
    report={'job':job,'method':method,'command_returncode':r.returncode,**postchecks(out,info,module),'GPT_API_calls':0,'generation_calls':0}
    snapshot_reports(module,attempt/'surefire_archive')
    if method:
        actual={r['name'] for r in report['testcases']}
        assert actual=={method},'Expected exactly the selected method: '+str(actual)
        assert all(r['class']==info['selected_test_fqcn'] and r['skipped']==0 for r in report['testcases'])
        report['selected_method_XML_pass']=all(r['errors']+r['failures']==0 for r in report['testcases'])
        report['method_replay_is_not_fullsuite_pass']=True
    mod.dump(dest,report)
    audit.log('E1_COMPATIBILITY_C03_REPLAY_COMPLETE',method=method,report_sha256=audit.sha(dest))
    print(json.dumps({'job':job,'method':method,'command_returncode':r.returncode,'XML_suites':report['XML_suites'],'testcases':report['testcases'],'production_class_count':report['production_class_count']},indent=2))

if __name__=='__main__':
    mode=sys.argv[1]
    if mode=='collect':collect_hazel(sys.argv[2])
    elif mode=='hazel_direct':hazel_direct(sys.argv[2])
    elif mode=='runtime48':runtime48(sys.argv[2] if len(sys.argv)>2 else None)
    else:raise ValueError(mode)
