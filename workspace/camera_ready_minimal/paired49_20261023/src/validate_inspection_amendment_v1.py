"""No-execution controls for annotation-only inspection amendment."""
import ast,json,re,sys
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));sys.path.insert(0,str(BASE/'src'))
import audit,junit_method_inventory_v1 as helper
STAGE=BASE/'e49_measurement_compat_v1'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def functions(p):return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(p.read_text(encoding='utf-8')).body if isinstance(n,ast.FunctionDef)}
def main():
    a=functions(BASE/'src/replay_fixed49_measurement_v4.py');b=functions(BASE/'src/replay_fixed49_measurement_v5.py');assert set(a)==set(b)
    changed=sorted(k for k in a if a[k]!=b[k]);assert changed==['inspect','normalize_case','verify_lock'],changed
    jobs=read(STAGE/'input_manifest49.json');completed=[18,19]+list(range(1,11));checks=[];deltas=[];placeholders=[]
    for j in jobs:
        idx=j['job_index'];old=BASE/'e49_driver/jobs'/f'{idx:02}'/'repo'/j['module'];java=old/'src/test/java'/Path(*j['selected_test_fqcn'].split('.')).with_suffix('.java');text=java.read_text(encoding='utf-8');inventory=helper.inventory_java_tests(text)
        prior=sorted(set(re.findall(r'public\s+void\s+(test\w*)\s*\(',text)))
        if prior!=inventory['methods']:deltas.append(idx)
        if inventory['no_behavior_placeholder_count']:placeholders.append(idx)
        if idx in completed:
            work=STAGE/'jobs'/f'{idx:02}';mod=work/'repo'/j['module'];diagnostic=read(work/'measurement_audit.json');cases=[]
            for xml in sorted((mod/'target/surefire-reports').glob('TEST-*.xml')):
                root=ET.parse(xml).getroot();assert root.get('name')==j['selected_test_fqcn']
                for c in root.findall('testcase'):
                    assert c.get('classname')==j['selected_test_fqcn'];name=helper.normalize_case(c.get('name'),j['selected_test_fqcn']);cases.append((name,len(c.findall('error'))+len(c.findall('failure'))+len(c.findall('skipped'))))
            strict=bool(cases) and Counter(x[0] for x in cases)==Counter(inventory['methods']) and all(x[1]==0 for x in cases)
            assert strict==diagnostic['complete_suite_evidence'] and inventory['methods']==diagnostic['expected_methods'];checks.append(idx)
    assert deltas==[11] and placeholders==[11] and len(checks)==12
    report={'status':'PASS','changed_driver_functions':changed,'measurement_execute_dependency_POM_gate_code_AST_unchanged':True,'only_source_method_inventory_delta_jobs':deltas,'empty_placeholder_jobs':placeholders,'completed12_strict_evidence_unchanged':checks,'Java_Maven_API_calls':0,'driver_v5_sha256':audit.sha(BASE/'src/replay_fixed49_measurement_v5.py'),'helper_sha256':audit.sha(BASE/'src/junit_method_inventory_v1.py')}
    out=BASE/'validation/inspection_amendment_v1';out.mkdir(exist_ok=False);p=out/'controls.json';p.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');audit.log('INSPECTION_AMENDMENT_CONTROLS',path=str(p),sha256=audit.sha(p),status='PASS');print(json.dumps(report))
if __name__=='__main__':main()
