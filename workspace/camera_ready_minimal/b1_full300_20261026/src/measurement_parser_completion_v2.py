"""Read existing native Maven evidence only. Score policy matches accepted E49."""
import csv,hashlib,importlib.util,json
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET
R=Path(__file__).resolve().parents[1]
def inventory_module():
 p=R/'backups/accepted49_adapter/src/junit_method_inventory_v1.py'
 lock=json.loads((R/'audit/adapter_backup_manifest_v2.json').read_text(encoding='utf-8'))
 row=next(x for x in lock if Path(x['backup'])==p)
 assert hashlib.sha256(p.read_bytes()).hexdigest()==row['sha256'],'JUnit inventory helper drift'
 spec=importlib.util.spec_from_file_location('b1_frozen_junit_inventory',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def parse(module,focal_class,package,test_fqcn,process_gate):
 module=Path(module);pit=module/'target/pit-reports/mutations.csv';rows=[]
 if pit.exists():
  with pit.open(encoding='utf-8-sig',newline='') as f:rows=list(csv.reader(f))
 report_shape_valid=all(len(r)==7 for r in rows)
 observed_row_widths={str(n):sum(len(r)==n for r in rows) for n in sorted({len(r) for r in rows})}
 complete_rows_before_rejection=sum(len(r)==7 for r in rows)
 report_complete=bool(pit.exists() and report_shape_valid and process_gate)
 if not report_complete:rows=[] # Keep the raw file; never score any prefix of an interrupted report.
 focal=[r for r in rows if r[0].replace('.java','')==focal_class and (r[1].rsplit('.',1)[0] if '.' in r[1] else '')==package]
 killed=sum(r[5]=='KILLED' for r in focal)
 raw_score=round(100*killed/len(focal),2) if focal else None
 strict=raw_score if process_gate and raw_score is not None else 0.0
 inventory=inventory_module();source=module/'src/test/java'/Path(*test_fqcn.split('.')).with_suffix('.java')
 info=inventory.inventory_java_tests(source.read_text(encoding='utf-8')) if source.is_file() else None
 methods=info['methods'] if info else [];cases=[];suites=[]
 for p in sorted((module/'target/surefire-reports').glob('TEST-*.xml')):
  root=ET.parse(p).getroot();suites.append({'name':root.get('name'),**{k:int(root.get(k,'0')) for k in ['tests','failures','errors','skipped']}})
  assert root.get('name')==test_fqcn,'Unexpected test suite in canonical evidence'
  for case in root.findall('testcase'):
   assert case.get('classname')==test_fqcn,'Unexpected testcase class'
   cases.append({'name':case.get('name'),'method':inventory.normalize_case(case.get('name'),test_fqcn),'errors':len(case.findall('error')),'failures':len(case.findall('failure')),'skipped':len(case.findall('skipped'))})
 suite=bool(cases) and Counter(c['method'] for c in cases)==Counter(methods) and all(c['errors']+c['failures']+c['skipped']==0 for c in cases)
 if cases and all(c['errors']+c['failures']==0 for c in cases):assert len(cases)==len({c['method'] for c in cases}),'Duplicate method execution'
 jac=module/'target/site/jacoco/jacoco.csv';coverage=[]
 if jac.is_file():
  with jac.open(encoding='utf-8-sig',newline='') as f:coverage=[r for r in csv.DictReader(f) if r.get('CLASS')==focal_class and r.get('PACKAGE','').replace('/','.')==package]
 assert not [r for r in rows if r[5]=='KILLED' and test_fqcn not in r[6]],'Foreign killing tests'
 return {'PIT_report_complete':report_complete,'PIT_report_shape_valid':report_shape_valid,'raw_row_widths':observed_row_widths,'complete_rows_before_rejection':complete_rows_before_rejection,'observed_focal_mutant_count':len(focal) if report_complete else None,'report_acceptance_rule':'complete successful process and well-formed report; partial prefix never scored','legacy_process_build':int(process_gate),'legacy_strict_mutation_percent':strict,'mutation_score_percent':raw_score,'focal_mutants':len(focal),'killed_mutants':killed,'focal_mutant_qualified_classes':sorted({r[1] for r in focal}),'pit_report_present':pit.exists(),'strict_suite_evidence':suite,'strict_measurement_evidence':bool(suite and focal and coverage),'inventory':info,'cases':cases,'surefire_suites':suites,'jacoco_focal_rows':coverage,'metric_policy':'original process gate, KILLED/all focal mutants incl nested, round2; evidence flags do not replace score'}
