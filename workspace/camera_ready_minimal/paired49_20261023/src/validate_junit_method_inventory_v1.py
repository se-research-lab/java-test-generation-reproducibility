"""Parser-only controls and frozen49 source/XML inventory; no experiment calls."""
import hashlib,json,sys
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET
BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE));sys.path.insert(0,str(BASE/'src'))
import audit
from junit_method_inventory_v1 import inventory_java_tests,test_methods,normalize_case
OUT=BASE/'validation/junit_inventory_annotation_v1'

def check_fixture():
    simple='''// @Test public void fakeComment() {}
class Example {
String x = "@Test public void fakeString() {}";
@Test(timeout=4000) public void test0() throws Throwable { assertTrue(true); }
@org.junit.Test @SuppressWarnings("unused") public final void another$Name_42() { String y="}"; }
@Test public void notGeneratedAnyTest() { /* no behavior */ }
@Test public void kiểmTra() { ; }
}'''
    inv=inventory_java_tests(simple)
    assert inv['methods']==sorted(['test0','another$Name_42','notGeneratedAnyTest','kiểmTra'])
    assert inv['annotation_count']==4 and inv['no_behavior_placeholder_methods']==['notGeneratedAnyTest']
    assert test_methods('@Test public void notGeneratedAnyTest() { assertTrue(true); }')==['notGeneratedAnyTest']
    assert inventory_java_tests('@Test public void notGeneratedAnyTest() { assertTrue(true); }')['no_behavior_placeholder_count']==0
    rejected=[]
    for bad in ['@Test public void f(int x) {}','@Test private void f() {}','@Test public static void f() {}',
                '@Test public int f() { return 1; }','@Test public void f() {} @Test public void f() {}',
                '@Test public void f() {','/* unfinished']:
        try: inventory_java_tests(bad)
        except ValueError: rejected.append(bad)
        else: raise AssertionError('Did not reject '+bad)
    for method in ['test0','notGeneratedAnyTest','another$Name_42','kiểmTra']:
        assert normalize_case(method,'a.Example_ESTest')==method
        assert normalize_case(method+' on '+method+'(a.Example_ESTest)','a.Example_ESTest')==method
    for bad in ['test0 on test1(a.Example_ESTest)','notGeneratedAnyTest on test0(a.Example_ESTest)',
                'test0 on test0(a.Foreign_ESTest)','test0 on test0(a.Example_ESTest)junk',' test0','test0 ',
                'test0()','test0 on test0(a.Example_ESTest) on test0(a.Example_ESTest)','5test','test-0']:
        assert normalize_case(bad,'a.Example_ESTest') is None,bad
    return {'status':'PASS','fixtures':['annotation-not-name-prefix','comments-and-string-literals-excluded',
        'qualified-and-intervening-annotations','arbitrary-Java-identifiers','braced-body-balancing',
        'placeholder-distinct-from-behavior','unsupported-signatures-fail-closed','duplicate-names-rejected',
        'anchored-TestNG-normalization','foreign-or-mismatched-TestNG-token-rejected'],
        'negative_signature_fixtures':len(rejected),'negative_case_fixtures':10}

def xml_inventory(module,test,methods):
    paths=sorted((module/'target/surefire-reports').glob('TEST-*.xml')); cases=[]
    for p in paths:
        root=ET.parse(p).getroot()
        for c in root.findall('testcase'):
            cases.append({'suite':root.get('name'),'classname':c.get('classname'),'name':c.get('name'),
                          'method':normalize_case(c.get('name'),test),'errors':len(c.findall('error')),
                          'failures':len(c.findall('failure')),'skipped':len(c.findall('skipped'))})
    expected=Counter(methods);observed=Counter(c['method'] for c in cases)
    return {'xml_files':[{'path':str(p.relative_to(BASE)),'sha256':audit.sha(p)} for p in paths],
            'case_count':len(cases),'cases':cases,'expected_count':len(methods),
            'method_multiset_exact':bool(cases) and observed==expected,
            'all_selected_class':all(c['suite']==test and c['classname']==test for c in cases),
            'unknown_names':[c['name'] for c in cases if c['method'] not in methods],
            'missing_methods':list((expected-observed).elements()),
            'extra_methods':list((observed-expected).elements()),
            'errors':sum(c['errors'] for c in cases),'failures':sum(c['failures'] for c in cases),
            'skipped':sum(c['skipped'] for c in cases),
            'strict_suite_evidence':bool(cases) and observed==expected and
                all(c['suite']==test and c['classname']==test and c['errors']+c['failures']+c['skipped']==0 for c in cases)}

def main():
    assert not OUT.exists(),'New parser-only report only'
    fixture=check_fixture();jobs=json.loads((BASE/'e49_driver/input_manifest49.json').read_text(encoding='utf-8'))
    assert len(jobs)==49
    rows=[]
    for j in jobs:
        test=j['selected_test_fqcn'];old=BASE/'e49_driver/jobs'/f"{j['job_index']:02}"/'repo'/j['module']
        src=old/'src/test/java'/Path(*test.split('.')).with_suffix('.java')
        before=audit.sha(src);inv=inventory_java_tests(src.read_text(encoding='utf-8'));assert inv['methods']
        assert before==audit.sha(src),'Read-only source changed'
        row={'job_index':j['job_index'],'class_key':j['class_key'],'selected_test_fqcn':test,
             'source':src.relative_to(BASE).as_posix(),'source_sha256':before,**inv,
             'original_E1_XML':xml_inventory(old,test,inv['methods'])}
        new=BASE/'e49_measurement_compat_v1/jobs'/f"{j['job_index']:02}"/'repo'/j['module']
        if new.is_dir(): row['new_measurement_XML']=xml_inventory(new,test,inv['methods'])
        rows.append(row)
    summary={'status':'PASS','kind':'parser-only source/XML inventory; no experiments or original edits',
             'n':len(rows),'JUnit_Test_annotations':sum(r['annotation_count'] for r in rows),
             'no_behavior_placeholder_methods':sum(r['no_behavior_placeholder_count'] for r in rows),
             'placeholder_jobs':[r['job_index'] for r in rows if r['no_behavior_placeholder_count']],
             'original_E1_XML_strict_suite_evidence':sum(r['original_E1_XML']['strict_suite_evidence'] for r in rows),
             'original_E1_XML_missing_or_incomplete_jobs':[r['job_index'] for r in rows if not r['original_E1_XML']['strict_suite_evidence']],
             'unknown_original_XML_names':[{ 'job_index':r['job_index'],'names':r['original_E1_XML']['unknown_names']} for r in rows if r['original_E1_XML']['unknown_names']],
             'generation_calls':0,'GPT_API_calls':0,'Maven_commands':0,
             'helper_sha256':audit.sha(BASE/'src/junit_method_inventory_v1.py'),
             'script_sha256':audit.sha(__file__),
             'interpretation':'An empty generated @Test placeholder can prove selection/execution only; it supplies no behavior assertions. Keep it in execution evidence with an explicit placeholder flag; never alter legacy score, gate, samples, or RQs.'}
    OUT.mkdir()
    for name,data in [('fixtures.json',fixture),('inventory49.json',rows),('summary.json',summary)]:
        p=OUT/name;p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        audit.log('PARSER_ONLY_INVENTORY_CREATED',path=str(p.relative_to(BASE)),sha256=audit.sha(p))
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
