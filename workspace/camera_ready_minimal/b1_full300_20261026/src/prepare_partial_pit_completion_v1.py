"""Offline parser amendment and continuation of eight untouched inputs; no score retry."""
import ast,difflib,json
from pathlib import Path
from maven_adapter_v1 import R,sha,dump
A=R/'completion_amendment_v1'
def main():
 out=A/'partial_pit_preparation_v1';out.mkdir(exist_ok=False);variants=[]
 old=R/'src/measurement_parser_v1.py';text=old.read_text()
 text=text.replace("assert all(len(r)==7 for r in rows),'Malformed PIT CSV'","report_shape_valid=all(len(r)==7 for r in rows)\n observed_row_widths={str(n):sum(len(r)==n for r in rows) for n in sorted({len(r) for r in rows})}\n complete_rows_before_rejection=sum(len(r)==7 for r in rows)\n report_complete=bool(pit.exists() and report_shape_valid and process_gate)\n if not report_complete:rows=[] # Keep the raw file; never score any prefix of an interrupted report.")
 text=text.replace("return {'legacy_process_build':int(process_gate)","return {'PIT_report_complete':report_complete,'PIT_report_shape_valid':report_shape_valid,'raw_row_widths':observed_row_widths,'complete_rows_before_rejection':complete_rows_before_rejection,'observed_focal_mutant_count':len(focal) if report_complete else None,'report_acceptance_rule':'complete successful process and well-formed report; partial prefix never scored','legacy_process_build':int(process_gate)")
 variants.append((old,R/'src/measurement_parser_completion_v2.py',text))
 old=R/'src/pom_completion_controller_v2.py';text=old.read_text().replace('from measurement_parser_v1 import parse','from measurement_parser_completion_v2 import parse')
 variants.append((old,R/'src/pom_completion_controller_v3.py',text))
 old=R/'src/complete_maven_groups_v3.py';text=old.read_text().replace('pom_completion_controller_v2','pom_completion_controller_v3').replace("f'admission_maven_{group}_v2.json'","f'admission_maven_{group}_v3.json'").replace("f'maven_{group}_run_v2'","f'maven_{group}_run_v3'").replace("f'{i:03d}_completion_{group}_v2'","f'{i:03d}_completion_{group}_v3'")
 variants.append((old,R/'src/complete_maven_groups_v4.py',text))
 for old,new,text in variants:
  ast.parse(text)
  with new.open('x',encoding='utf-8') as f:f.write(text)
  (out/(new.stem+'.diff')).write_text(''.join(difflib.unified_diff(old.read_text().splitlines(True),text.splitlines(True),fromfile=old.name,tofile=new.name)),encoding='utf-8')
 # Pure report parsing qualification: complete saved72 vs timed-out112.
 import sys;sys.path.insert(0,str(R/'src'))
 from measurement_parser_completion_v2 import parse
 jobs=json.loads((R/'manifest300.json').read_text());checks=[]
 for i,gate in [(72,True),(112,False)]:
  job=jobs[i-1];folder=R/'jobs'/f'{i:03d}_completion_pom_v2';module=folder/'repo'/job['module'];test=('/'+job['focal_path']).split('/src/main/java/')[1].removesuffix('.java').replace('/','.')+'_ESTest';package=test.removesuffix('_ESTest').rpartition('.')[0]
  report=module/'target/pit-reports/mutations.csv';h=sha(report);data=parse(module,job['focal_class'],package,test,gate);assert sha(report)==h
  if i==72:assert data['mutation_score_percent']==json.loads((folder/'result.json').read_text())['mutation_score_percent'] and data['PIT_report_complete']
  else:assert data['mutation_score_percent'] is None and not data['PIT_report_complete'] and data['strict_suite_evidence'] and data['legacy_strict_mutation_percent']==0
  checks.append({'index':i,'raw_report_sha256':h,'observed_mutation_percent':data['mutation_score_percent'],'PIT_report_complete':data['PIT_report_complete'],'native_suite_pass':data['strict_suite_evidence'],'raw_row_widths':data['raw_row_widths']})
 dump(out/'qualification.json',{'status':'PASS_OFFLINE_PARSER_NO_EXECUTION','checks':checks,'profile_seed_budget_target_mutators_changed':False,'new_generation_calls':0,'new_measurement_calls':0,'original_parser_unchanged':True})
 print('PASS parser amendment; no raw report edits; no rerun112')
if __name__=='__main__':main()
