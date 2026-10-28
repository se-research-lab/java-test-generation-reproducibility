"""Prepare isolated POM controller plus meaningful XML/model checks; no experiment."""
import ast,difflib,json,sys,tempfile
from pathlib import Path
import pandas as pd
from maven_adapter_v1 import R,sha,dump
from pom_namespace_completion_v1 import generation_bindings,normalize_model,safe_write
from pom_integration_guard_v1 import verify,canonical
from xml.etree import ElementTree as ET
A=R/'completion_amendment_v1'
def main():
 out=A/'pom_preparation';out.mkdir(exist_ok=False)
 old=R/'src/maven_controller_v2.py';new=R/'src/pom_completion_controller_v1.py'
 text=old.read_text().replace('from pom_integration_guard_v1 import verify as integration_guard','from pom_namespace_completion_v1 import generation_bindings\nfrom pom_integration_guard_v1 import verify as integration_guard')
 ast.parse(text)
 with new.open('x',encoding='utf-8') as f:f.write(text)
 (out/'controller.diff').write_text(''.join(difflib.unified_diff(old.read_text().splitlines(True),text.splitlines(True),fromfile=old.name,tofile=new.name)),encoding='utf-8')
 fixture=R/'validation/pom_namespace_adapter_v1';fixture.mkdir(exist_ok=False);checks=[]
 for i in [72,112,119,163,173,211,220,269,275,294]:
  saved=A/'input_audit/pom_provenance'/f'{i:03d}';original=(saved/'commit_pom.xml').read_text();bad=(saved/'frozen_input_pom.xml').read_text()
  fixed=bad.replace('<project ','<project xmlns:ns1="https://www.w3.org/2001/XMLSchema-instance" ',1)
  assert canonical(ET.fromstring(fixed))==canonical(ET.fromstring(original))
  f=fixture/f'{i:03d}';f.mkdir();p=f/'pom.xml';p.write_text(original,encoding='utf-8')
  ns=generation_bindings(None,f,lambda *a,**k:None)
  df=pd.DataFrame([{'Project':'synthetic','Module':'','Focal_Class':'BranchFixture','Test_Class':'BranchFixture_ESTest','Focal_Path':str(f/'src/main/java/fixture/BranchFixture.java'),'Test_Path':(f/'src/test/java/fixture/BranchFixture_ESTest.java').as_posix()}])
  assert ns['edit_pom_file'](str(f),df,'4',None) is not None
  assert ns['add_evosuite_pom'](str(f)) is not None
  guard=verify(original,p.read_text());checks.append({'index':i,'parseable':True,'model_restoration_equivalent':True,'integration_guard':guard})
 dump(out/'static_validation.json',{'status':'PASS_STATIC_MODEL_AND_POM_INTEGRATION','checks':checks,'runtime_qualified':False,'new_experiment_calls':0})
 print('PASS 10 POM model restoration and scoped integration; runtime qualification still required')
if __name__=='__main__':main()
