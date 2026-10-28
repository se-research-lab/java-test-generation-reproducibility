"""Python-only negative controls for fixed49 replay guards. No Java/Maven/API.
AST-extracts only named pure helpers; never imports or runs the replay driver.
Creates tiny fixtures only under a new validation directory, never the real stage.
"""
import ast,copy,csv,difflib,hashlib,json,os,re,shutil,sys,types,zipfile
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET
BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE));import audit
OUT=BASE/'validation/replay_guard_controls_v1'
DRIVER=BASE/'src/replay_fixed49_measurement_v3.py'
CACHE=BASE/'e1_compatibility_diagnostic_v1/maven_cache'
NS={'m':'http://maven.apache.org/POM/4.0.0'}
EXCLUDE={'.git','target','node_modules','evosuite-report','.gradle'}
TEST='a.Focal_ESTest';RESULTS=[];EVENTS=[]

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,data):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f:json.dump(data,f,ensure_ascii=False,indent=2);f.write('\n')
def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def put(p,data):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('xb') as f:f.write(data.encode() if isinstance(data,str) else data)
    return p

def walk(root,exclude=()):
    for folder,dirs,files in os.walk(root):
        dirs[:]=sorted(d for d in dirs if d not in exclude)
        for name in sorted(files):
            p=Path(folder)/name;assert not p.is_symlink();yield p

class ForbiddenCommands:
    calls=0
    def run(self,*args,**kw):
        self.calls+=1;raise RuntimeError('External process forbidden in guard fixture validation')
    check_call=run


def extract(source,names,namespace):
    tree=ast.parse(source.read_text(encoding='utf-8'))
    all_defs=[n.name for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))]
    assert len(all_defs)==len(set(all_defs)),'Duplicate top-level driver function definitions'
    defs=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
    assert {n.name for n in defs}==set(names),'Missing guard helper: '+str(set(names)-{n.name for n in defs})
    assert all(not isinstance(n,(ast.Import,ast.ImportFrom)) for f in defs for n in ast.walk(f))
    exec(compile(ast.Module(body=defs,type_ignores=[]),str(source),'exec'),namespace)
    return tree

def check(name,fn,reject=False):
    try:
        value=fn()
        if reject:raise RuntimeError('Guard accepted forbidden fixture')
        RESULTS.append({'name':name,'PASS':True,'expected':'accept'})
    except AssertionError as ex:
        RESULTS.append({'name':name,'PASS':bool(reject),'expected':'reject' if reject else 'accept','observed_exception':'AssertionError','message':str(ex)})
    except Exception as ex:
        RESULTS.append({'name':name,'PASS':False,'expected':'reject' if reject else 'accept','observed_exception':type(ex).__name__,'message':str(ex)})

def require(value,message='Fixture assertion failed'):
    assert value,message

def pom(scope='test',version='4.8',executions=False):
    dependency='<dependency><groupId>junit</groupId><artifactId>junit</artifactId>'
    if version is not None:dependency+='<version>'+version+'</version>'
    if scope is not None:dependency+='<scope>'+scope+'</scope>'
    dependency+='</dependency>'
    execution='<executions><execution><id>custom</id></execution></executions>' if executions else ''
    return '<project xmlns="'+NS['m']+'"><modelVersion>4.0.0</modelVersion><groupId>a</groupId><artifactId>fixture</artifactId><version>1</version><dependencies>'+dependency+'</dependencies><build><plugins><plugin><artifactId>maven-surefire-plugin</artifactId><version>2.17</version>'+execution+'</plugin></plugins></build></project>'

def surefire(version='2.17',multiple=False,leading=True):
    includes=('/a/**.java' if leading else 'a/**.java')
    extra='<execution><id>default-test</id></execution>' if multiple else ''
    return ET.fromstring('<plugin xmlns="'+NS['m']+'"><version>'+version+'</version><executions>'+extra+'<execution><id>regular-tests</id><configuration><includes><include>'+includes+'</include></includes></configuration></execution></executions></plugin>')

def patch_fixture(name,jar,scope='test',version='4.8',multiple=False,leading=False,plugin_version='2.17',executions=False,duplicate=False):
    out=OUT/'fixtures'/name;module=out/'repo';put(module/'pom.xml',pom(scope,version,executions))
    selected=[] if jar is None else [jar]
    if duplicate:selected*=2
    data={'classpath':selected,'compile_classpath':[]}
    before=(module/'pom.xml').read_bytes()
    policy=G['patch_pom']({'job_index':999,'selected_test_fqcn':TEST},module,out,data,surefire(plugin_version,multiple,leading))
    return out,module,policy,before

def raw_metrics(module,test,focal,package,gate):
    rows=PURE['rawcsv'](module/'target/pit-reports/mutations.csv')
    foc=PURE['focal'](rows,{'focal_class':focal,'package':package})
    score=round(100*sum(r[5]=='KILLED' for r in foc)/len(foc),2) if foc else None
    return {'legacy_process_build':int(gate),'legacy_strict_mutation_percent':score if gate and score is not None else 0.0,'jacoco_focal_rows':[{'CLASS':'Focal'}] if (module/'target/site/jacoco/jacoco.csv').exists() else []}


def source_fixture(name,admission=False):
    out=OUT/'fixtures'/name;module=out/'repo'
    put(module/'pom.xml',pom(version='4.13.2'))
    java=put(module/'src/test/java/a/Focal_ESTest.java','public class Focal_ESTest { public void test0() {} public void test1() {} }')
    scaffold=put(module/'src/test/java/a/Focal_ESTest_scaffolding.java','public class Focal_ESTest_scaffolding {}')
    production=put(module/'src/main/java/a/Focal.java','class Focal {}')
    settings=put(out/'settings.xml','<settings/>')
    rows=[{'relative':p.relative_to(module).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size} for p in walk(module)]
    dump(out/'input_source_manifest.json',rows)
    generated={p.relative_to(out).as_posix():sha(p) for p in [java,scaffold]};dump(out/'generated_manifest.json',generated)
    j={'job_index':999,'module':'.','selected_test_fqcn':TEST,'focal_class':'Focal','package':'a','settings_sha256':sha(settings)}
    if admission:
        dump(out/'generated_test_bytecode_baseline.json',{'available':False,'count':0,'classes':{}})
        j.update(generated_test_bytecode_baseline_count=0,generated_test_bytecode_baseline_available=False)
    for key,file in [('input_source_manifest_sha256','input_source_manifest.json'),('generated_manifest_sha256','generated_manifest.json')]:j[key]=sha(out/file)
    return out,module,j,java,scaffold,production,settings


def evidence_fixture(name,gate=True,case_names=None,errors=None):
    out,module,j,java,scaffold,production,settings=source_fixture(name)
    put(module/'target/classes/a/Focal.class',b'production-bytecode')
    dump(out/'production_class_baseline.json',G['hashes'](module/'target/classes',classes_only=True))
    for rel in ['a/Focal_ESTest.class','a/Focal_ESTest$1.class','a/Focal_ESTest_scaffolding.class']:
        put(module/'target/test-classes'/rel,('bytecode:'+rel).encode())
    classes=G['generated_test_bytecode'](module,TEST)
    dump(out/'generated_test_bytecode_baseline.json',{'available':True,'count':len(classes),'classes':classes})
    dump(out/'policy_applied.json',{'after_sha256':sha(module/'pom.xml')})
    names=['test0','test1'] if case_names is None else case_names
    errors={} if errors is None else errors
    root=ET.Element('testsuite',{'name':TEST,'tests':str(len(names)),'errors':str(sum(errors.values())),'failures':'0','skipped':'0'})
    for name in names:
        c=ET.SubElement(root,'testcase',{'classname':TEST,'name':name})
        for _ in range(errors.get(name,0)):ET.SubElement(c,'error',{'type':'FixtureRuntimeError'})
    put(module/'target/surefire-reports/TEST-a.Focal_ESTest.xml',ET.tostring(root,encoding='utf-8'))
    rows=[['Focal.java','a.Focal','MUTATOR_A','method','11','KILLED',TEST+'.test0'],['Focal.java','a.Focal','MUTATOR_B','method','12','SURVIVED','none']]
    p=module/'target/pit-reports/mutations.csv';p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8',newline='') as f:csv.writer(f).writerows(rows)
    dump(out/'focal_mutant_baseline.json',{'multiset_sha256':PURE['counter_hash'](rows),'n':2})
    put(module/'target/site/jacoco/jacoco.csv','CLASS\nFocal\n')
    measurement=types.SimpleNamespace(stdout='Running '+TEST+'\nBUILD SUCCESS\n',returncode=0)
    return out,module,j,measurement


def main():
    global G,PURE
    assert not OUT.exists(),'Never overwrite validation results'
    assert DRIVER.is_file(),'Wait for final v3 driver before validation'
    OUT.mkdir(parents=True)
    audit.log('FIXED49_REPLAY_GUARD_VALIDATION_START',source_sha256=sha(__file__),driver_sha256=sha(DRIVER),output=str(OUT.relative_to(BASE)),external_processes_allowed=False)
    G={'Path':Path,'ET':ET,'NS':NS,'EXCLUDE':EXCLUDE,'copy':copy,'difflib':difflib,'shutil':shutil,'re':re,'os':os,'json':json,'zipfile':zipfile,'Counter':Counter,'audit':types.SimpleNamespace(sha=sha),'compat':types.SimpleNamespace(walk=walk),'load':load,'dump':dump,'event':lambda kind,**kw:EVENTS.append({'kind':kind,**kw}),'CACHE':CACHE,'CACHE_HASHES':None,'BASE':BASE,'commands':ForbiddenCommands()}
    names=['normalize','hashes','patch_pom','compare_cp','normalize_case','is_generated_test_bytecode','generated_test_bytecode','compare_generated_test_bytecode','assert_no_stale_targets','preflight_sources','cp_entries','inspect']
    tree=extract(DRIVER,names,G)
    PURE={'Path':Path,'csv':csv,'hashlib':hashlib,'json':json}
    extract(BASE/'src/analyze_e49_final_v2.py',['rawcsv','focal','counter_hash'],PURE)
    G['pure']=types.SimpleNamespace(**{n:PURE[n] for n in ['rawcsv','focal','counter_hash']})
    G['legacy']=types.SimpleNamespace(raw_metrics=raw_metrics)
    pinned={r['relative']:r['sha256'] for r in load(BASE/'e1_compatibility_diagnostic_v1/cache_copy_manifest.json')}
    def jar(rel):
        p=CACHE/rel;h=sha(p);assert pinned[rel]==h
        return {'path':rel,'absolute_path':str(p),'sha256':h,'bytes':p.stat().st_size}
    old=jar('junit/junit/4.8/junit-4.8.jar');new=jar('junit/junit/4.13.2/junit-4.13.2.jar');ham=jar('org/hamcrest/hamcrest-core/1.3/hamcrest-core-1.3.jar')
    fake3=put(OUT/'fixtures/junit3.jar',b'')
    fake3.unlink()
    with zipfile.ZipFile(fake3,'x') as z:z.writestr('junit/framework/Test.class',b'fixture')
    old3={'path':'junit/junit/3.8.1/junit-3.8.1.jar','absolute_path':str(fake3),'sha256':sha(fake3)}
    def api():
        with zipfile.ZipFile(old['absolute_path']) as z:require('org/junit/Test.class' in z.namelist() and 'org/junit/rules/TestRule.class' not in z.namelist())
        with zipfile.ZipFile(new['absolute_path']) as z:require('org/junit/Test.class' in z.namelist() and 'org/junit/rules/TestRule.class' in z.namelist())
    check('actual_pinned_JUnit_API_difference',api)
    def modern():
        o,m,p,b=patch_fixture('junit_modern',new,version='4.13.2');require(not p['changes'] and m.joinpath('pom.xml').read_bytes()==b)
    check('JUnit_TestRule_present_preserves_POM_bytes',modern)
    def eligible():
        o,m,p,b=patch_fixture('junit_eligible',old);require(p['JUnit_rule_applied'] and not p['selector_rule_applied']);require('<version>4.13.2</version>' in (m/'pom.xml').read_text());require(sha(o/'backup_before_policy/pom.xml')==p['before_sha256'])
    check('JUnit4_test_scope_minimal_version_patch',eligible)
    check('JUnit3_API_rejected',lambda:patch_fixture('junit3_reject',old3),True)
    check('JUnit_compile_scope_rejected',lambda:patch_fixture('junit_compile',old,scope='compile'),True)
    check('JUnit_default_scope_rejected',lambda:patch_fixture('junit_default',old,scope=None),True)
    check('duplicate_selected_JUnit_jars_rejected',lambda:patch_fixture('junit_duplicate',old,duplicate=True),True)
    def inherited():
        o,m,p,b=patch_fixture('junit_inherited',old,version=None);require(p['JUnit_rule_applied'] and '<version>4.13.2</version>' in (m/'pom.xml').read_text())
    check('JUnit_test_inherited_version_only_override',inherited)
    def exact():
        o,m,p,b=patch_fixture('selector_eligible',new,version='4.13.2',multiple=True,leading=True);require(p['selector_rule_applied'] and not p['JUnit_rule_applied']);require(p['changes'][0]['new_include']=='a/Focal_ESTest.java');require('combine.self="override"' in (m/'pom.xml').read_text())
    check('selector_multiple_inherited_leading_slash_only_include',exact)
    for key,multi,leading in [('relative',True,False),('single',False,True)]:
        def nopatch(key=key,multi=multi,leading=leading):
            o,m,p,b=patch_fixture('selector_'+key,new,version='4.13.2',multiple=multi,leading=leading);require(not p['changes'] and (m/'pom.xml').read_bytes()==b)
        check('selector_'+key+'_preserves_POM_bytes',nopatch)
    check('selector_wrong_Surefire_version_rejected',lambda:patch_fixture('selector_wrong_version',new,version='4.13.2',multiple=True,leading=True,plugin_version='2.22.2'),True)
    check('selector_existing_module_execution_rejected',lambda:patch_fixture('selector_existing_exec',new,version='4.13.2',multiple=True,leading=True,executions=True),True)
    prod={'path':'org/example/production/1/production-1.jar','sha256':'prodsha'}
    before={'compile_classpath':[prod],'classpath':[prod,old]};after={'compile_classpath':[prod],'classpath':[prod,new,ham]};applied={'JUnit_rule_applied':True}
    check('CP_expected_JUnit_Hamcrest_delta_accepted',lambda:G['compare_cp'](before,after,applied))
    b=copy.deepcopy(after);b['compile_classpath'][0]['sha256']='changed'
    check('CP_compile_closure_drift_rejected',lambda:G['compare_cp'](before,b,applied),True)
    b2=copy.deepcopy(after);b2['classpath'].append({'path':'org/example/extra/1/extra.jar','sha256':'other'})
    check('CP_non_JUnit_dependency_addition_rejected',lambda:G['compare_cp'](before,b2,applied),True)
    b3=copy.deepcopy(after);b3['classpath'][-1]['path']='org/hamcrest/hamcrest-core/1.1/hamcrest-core-1.1.jar'
    check('CP_wrong_Hamcrest_version_rejected',lambda:G['compare_cp'](before,b3,applied),True)
    b4=copy.deepcopy(after);b4['classpath']=b4['classpath'][:-1]
    check('CP_required_Hamcrest_missing_rejected',lambda:G['compare_cp'](before,b4,applied),True)
    check('CP_unpatched_closure_must_match',lambda:G['compare_cp'](before,after,{'JUnit_rule_applied':False}),True)
    cpfile=put(OUT/'fixtures/cache_classpath.txt',old['absolute_path']);G['CACHE_HASHES']={old['path']:'not_the_pinned_hash'}
    check('CP_cache_JAR_hash_tamper_detected',lambda:G['cp_entries'](cpfile),True);G['CACHE_HASHES']=None
    check('TestNG_name_normalized_exactly',lambda:require(G['normalize_case']('test1 on test1('+TEST+')',TEST)=='test1'))
    check('TestNG_mismatched_method_rejected',lambda:require(G['normalize_case']('test1 on test2('+TEST+')',TEST) is None))
    check('TestNG_foreign_FQCN_rejected',lambda:require(G['normalize_case']('test1 on test1(a.Other_ESTest)',TEST) is None))
    for label,mutation in [
        ('source_modified',lambda f:f[5].write_text('modified',encoding='utf-8')),
        ('scaffold_modified',lambda f:f[4].write_text('modified',encoding='utf-8')),
        ('settings_modified',lambda f:f[6].write_text('<modified/>',encoding='utf-8')),
        ('source_added',lambda f:put(f[1]/'src/main/java/a/Added.java','class Added {}')),
        ('source_removed',lambda f:f[5].unlink()),
        ('stale_target_XML',lambda f:put(f[1]/'nested/target/surefire-reports/TEST-stale.xml','<testsuite/>')),
    ]:
        def bad_source(label=label,mutation=mutation):
            f=source_fixture('preflight_'+label,True);mutation(f);G['preflight_sources'](f[0],f[2])
        check('preflight_'+label+'_rejected',bad_source,True)
    def clean_source():
        f=source_fixture('preflight_clean',True);G['preflight_sources'](f[0],f[2])
    check('preflight_clean_copied_fixture_accepted',clean_source)
    def hook():
        execute=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='execute')
        calls=[n for n in ast.walk(execute) if isinstance(n,ast.Call)]
        p=[n.lineno for n in calls if isinstance(n.func,ast.Name) and n.func.id=='preflight_sources']
        m=[n.lineno for n in calls if isinstance(n.func,ast.Name) and n.func.id=='dependency']
        require(len(p)==1 and m and p[0]<min(m),'Actual execute must call preflight before first Maven dependency helper')
    check('execute_admission_preflight_precedes_Maven',hook)
    family=['a/Focal_ESTest.class','a/Focal_ESTest$1.class','a/Focal_ESTest_scaffolding.class','a/Focal_ESTest_scaffolding$1.class']
    check('generated_bytecode_exact_family_nested_included',lambda:require(all(G['is_generated_test_bytecode'](Path(p),TEST) for p in family)))
    check('generated_bytecode_prefix_foreign_excluded',lambda:require(not any(G['is_generated_test_bytecode'](Path(p),TEST) for p in ['b/Focal_ESTest.class','a/Focal_ESTestOther.class','a/Focal_ESTest_scaffoldingOther.class','a/Focal_ESTest.java'])))
    oldclasses={p:{'sha256':'hash:'+p,'bytes':1} for p in family};baseline={'available':True,'count':len(oldclasses),'classes':oldclasses}
    check('generated_bytecode_identical_family_accepted',lambda:require(G['compare_generated_test_bytecode'](baseline,copy.deepcopy(oldclasses),True)['matches_original_E1'] is True))
    changed=copy.deepcopy(oldclasses);changed[family[0]]['sha256']='changed'
    check('generated_bytecode_changed_rejected',lambda:G['compare_generated_test_bytecode'](baseline,changed,False),True)
    added=copy.deepcopy(oldclasses);added['a/Focal_ESTest$2.class']={'sha256':'extra','bytes':1}
    check('generated_bytecode_added_nested_rejected',lambda:G['compare_generated_test_bytecode'](baseline,added,True),True)
    missing=copy.deepcopy(oldclasses);missing.pop(family[0])
    check('generated_bytecode_missing_BUILD_SUCCESS_rejected',lambda:G['compare_generated_test_bytecode'](baseline,missing,True),True)
    check('generated_bytecode_missing_failed_build_explicit',lambda:require(G['compare_generated_test_bytecode'](baseline,missing,False)['matches_original_E1'] is False))
    def unavailable():
        d=G['compare_generated_test_bytecode']({'available':False,'count':0,'classes':{}},oldclasses,True);require(d['matches_original_E1'] is None and d['newly_pinned_without_E1_baseline'])
    check('generated_bytecode_unavailable_baseline_no_equivalence_claim',unavailable)
    def inspect_case(name,mutate=None,gate=True,case_names=None,errors=None):
        f=evidence_fixture(name,gate,case_names,errors)
        if mutate:mutate(f)
        return G['inspect'](f[0],f[2],f[1],gate,f[3])
    check('raw_evidence_complete_exact_methods',lambda:require(inspect_case('evidence_complete')[1]['complete_measurement_evidence']))
    check('missing_method_strict_false_score_retained',lambda:require((lambda r:not r[1]['complete_suite_evidence'] and r[0]['legacy_strict_mutation_percent']==50.0)(inspect_case('evidence_missing_method',case_names=['test0']))))
    check('duplicate_passing_method_rejected',lambda:inspect_case('evidence_duplicate',case_names=['test0','test0','test1']),True)
    def foreign_xml(f):
        p=f[1]/'target/surefire-reports/TEST-a.Focal_ESTest.xml';r=ET.parse(p).getroot();r[0].set('classname','a.Foreign_ESTest');p.write_bytes(ET.tostring(r))
    check('foreign_testcase_rejected',lambda:inspect_case('evidence_foreign',foreign_xml),True)
    def skipped(f):
        p=f[1]/'target/surefire-reports/TEST-a.Focal_ESTest.xml';r=ET.parse(p).getroot();ET.SubElement(r[0],'skipped');p.write_bytes(ET.tostring(r))
    check('skipped_method_strict_false_score_retained',lambda:require((lambda r:not r[1]['complete_suite_evidence'] and r[0]['legacy_strict_mutation_percent']==50.0)(inspect_case('evidence_skipped',skipped))))
    check('runtime_errors_not_new_scale_or_score_rewrite',lambda:require((lambda r:not r[1]['complete_suite_evidence'] and r[0]['legacy_strict_mutation_percent']==50.0)(inspect_case('evidence_errors',case_names=['test0','test0','test1'],errors={'test0':2}))))
    def noxml(f):(f[1]/'target/surefire-reports/TEST-a.Focal_ESTest.xml').unlink()
    check('no_XML_positive_legacy_score_retained',lambda:require((lambda r:not r[1]['complete_suite_evidence'] and r[0]['legacy_strict_mutation_percent']==50.0)(inspect_case('evidence_no_XML',noxml))))
    def prod_changed(f):(f[1]/'target/classes/a/Focal.class').write_bytes(b'changed-production')
    check('production_bytecode_changed_hard_stop',lambda:inspect_case('evidence_prod_changed',prod_changed,gate=False),True)
    def prod_added(f):put(f[1]/'target/classes/a/Extra.class',b'extra')
    check('production_bytecode_added_hard_stop',lambda:inspect_case('evidence_prod_added',prod_added),True)
    def prod_missing(f):(f[1]/'target/classes/a/Focal.class').unlink()
    check('production_bytecode_missing_BUILD_SUCCESS_rejected',lambda:inspect_case('evidence_prod_missing_success',prod_missing),True)
    check('production_bytecode_missing_failed_build_retains_zero',lambda:require((lambda r:bool(r[1]['missing_production_classes']) and r[0]['legacy_strict_mutation_percent']==0.0)(inspect_case('evidence_prod_missing_failed',prod_missing,gate=False))))
    def foreignkill(f):
        p=f[1]/'target/pit-reports/mutations.csv';text=p.read_text();p.write_text(text.replace(TEST+'.test0','a.Foreign_ESTest.test0'))
    check('foreign_PIT_killing_test_rejected',lambda:inspect_case('evidence_foreign_kill',foreignkill),True)
    def mutant_changed(f):
        p=f[1]/'target/pit-reports/mutations.csv';p.write_text(p.read_text().replace('MUTATOR_A','MUTATOR_CHANGED'))
    check('mutant_candidate_multiset_drift_rejected',lambda:inspect_case('evidence_mutant_changed',mutant_changed),True)
    def repeated(f):f[3].stdout='Running '+TEST+'\nRunning '+TEST+'\nBUILD SUCCESS\n'
    check('multiple_full_lifecycle_suite_invocations_rejected',lambda:inspect_case('evidence_repeat',repeated),True)
    require(G['commands'].calls==0,'External command attempted')
    summary={'status':'PASS' if all(r['PASS'] for r in RESULTS) else 'FAIL','test_count':len(RESULTS),'passed':sum(r['PASS'] for r in RESULTS),'failed':sum(not r['PASS'] for r in RESULTS),'source_sha256':sha(__file__),'driver_sha256':sha(DRIVER),'driver_path':str(DRIVER.relative_to(BASE)),'AST_only_helpers':names,'generation_calls':0,'GPT_API_calls':0,'Java_Maven_calls':0,'real_stage_created':(BASE/'e49_measurement_compat_v1').exists(),'fixture_output':str(OUT.relative_to(BASE)),'pinned_JARs':[old,new,ham],'tests':RESULTS,'events':EVENTS}
    dump(OUT/'results.json',summary)
    dump(OUT/'fixture_manifest.json',[{'relative':p.relative_to(OUT).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(OUT.rglob('*')) if p.is_file() and p.name!='fixture_manifest.json'])
    audit.log('FIXED49_REPLAY_GUARD_VALIDATION_COMPLETE',status=summary['status'],tests=summary['test_count'],passed=summary['passed'],failed=summary['failed'],results_sha256=sha(OUT/'results.json'),manifest_sha256=sha(OUT/'fixture_manifest.json'),Java_Maven_calls=0,GPT_API_calls=0,generation_calls=0)
    print(json.dumps({k:summary[k] for k in ['status','test_count','passed','failed','source_sha256','driver_sha256','Java_Maven_calls','GPT_API_calls','generation_calls']},indent=2))
    if summary['failed']:sys.exit(1)
if __name__=='__main__':main()
