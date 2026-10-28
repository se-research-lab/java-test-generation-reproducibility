"""Read Gradle native evidence; same strict zero-fill definition, no new scale."""
import csv
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET
from measurement_parser_v1 import inventory_module

def parse(module,evidence,job,gate):
 module=Path(module);evidence=Path(evidence);fqcn=job['selected_test_fqcn'];focal=job['focal_class'];package=job['package']
 reports=list((evidence/'pit-native').rglob('mutations.csv'))
 assert len(reports)<=1,'Ambiguous PIT report'
 rows=[]
 if reports:
  with reports[0].open(encoding='utf-8-sig',newline='') as f:rows=list(csv.reader(f))
 assert all(len(r)==7 for r in rows),'Malformed PIT CSV'
 mutants=[r for r in rows if r[0].removesuffix('.java')==focal and (r[1].rsplit('.',1)[0] if '.' in r[1] else '')==package]
 killed=sum(r[5]=='KILLED' for r in mutants);score=round(100*killed/len(mutants),2) if mutants else None
 assert not [r for r in rows if r[5]=='KILLED' and fqcn not in r[6]],'Foreign killing tests'
 inv=inventory_module();source=module/'src/test/java'/Path(*fqcn.split('.')).with_suffix('.java')
 info=inv.inventory_java_tests(source.read_text(encoding='utf-8')) if source.is_file() else None
 methods=info['methods'] if info else [];cases=[];suites=[]
 for p in sorted((evidence/'surefire-native').glob('TEST-*.xml')):
  root=ET.parse(p).getroot();assert root.get('name')==fqcn,'Foreign suite'
  suites.append({'name':root.get('name'),**{k:int(root.get(k,'0')) for k in ['tests','failures','errors','skipped']}})
  for c in root.findall('testcase'):
   assert c.get('classname')==fqcn,'Foreign testcase'
   cases.append({'name':c.get('name'),'method':inv.normalize_case(c.get('name'),fqcn),'errors':len(c.findall('error')),'failures':len(c.findall('failure')),'skipped':len(c.findall('skipped'))})
 suite=bool(cases) and Counter(c['method'] for c in cases)==Counter(methods) and all(c['errors']+c['failures']+c['skipped']==0 for c in cases)
 jac=evidence/'jacoco-native.csv';coverage=[]
 if jac.is_file():
  with jac.open(encoding='utf-8-sig',newline='') as f:coverage=[r for r in csv.DictReader(f) if r.get('CLASS')==focal and r.get('PACKAGE','').replace('/','.')==package]
 return {'legacy_process_build':int(gate),'legacy_strict_mutation_percent':score if gate and score is not None else 0.0,'mutation_score_percent':score,'focal_mutants':len(mutants),'killed_mutants':killed,'focal_mutant_qualified_classes':sorted({r[1] for r in mutants}),'pit_report_present':bool(reports),'strict_suite_evidence':suite,'strict_measurement_evidence':bool(suite and mutants and coverage),'inventory':info,'cases':cases,'surefire_suites':suites,'jacoco_focal_rows':coverage,'metric_policy':'legacy Gradle process gate; KILLED/all focal SourceFile+package mutants, round2; exact focal target retained; evidence flags do not replace score'}
