"""POM-only preparation correction. No generation algorithm or flag changes."""
import difflib,copy,re
from pathlib import Path
from xml.etree import ElementTree as ET
from maven_adapter_v1 import generation_bindings as original_bindings,R,dump,sha,GuardAbort
from pom_integration_guard_v1 import canonical
HTTP='http://maven.apache.org/POM/4.0.0';HTTPS='https://maven.apache.org/POM/4.0.0'
def ensure(v,m):
 if not v:raise GuardAbort(m)
def safe_write(tree,path):
 root=tree.getroot()
 ET.register_namespace('',HTTP)
 # Retain attributes and their URI. Never strip namespace declarations with regex.
 for node in root.iter():
  if not node.tag.startswith('{'):node.tag='{'+HTTP+'}'+node.tag
 tree.write(path,encoding='utf-8',xml_declaration=True)
 ET.parse(path)
def normalize_model(text):
 root=ET.fromstring(text);before=canonical(root)
 ensure(root.tag in {'{'+HTTPS+'}project','{'+HTTP+'}project'},'Unknown POM namespace')
 for node in root.iter():
  if node.tag.startswith('{'+HTTPS+'}'):node.tag='{'+HTTP+'}'+node.tag.split('}',1)[1]
 ensure(canonical(root)==before,'POM model content changed beyond namespace representation')
 ET.register_namespace('',HTTP)
 return ET.tostring(root,encoding='unicode')+'\n'
def generation_bindings(commands,out,event):
 ns=original_bindings(commands,out,event)
 ns['write_pom_tree']=safe_write
 original_edit=ns['edit_pom_file']
 def edit(path,df,junit,testng):
  pom=Path(path)/'pom.xml';old=pom.read_text(encoding='utf-8');new=normalize_model(old)
  dump(Path(out)/'pom_namespace_adapter.json',{'before_sha256':sha(pom),'change':'https POM model namespace -> http for fixed namespace helper; all model content preserved','production_dependencies_changed':False,'post_outcome':True})
  (Path(out)/'pom_namespace.diff').write_text(''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='restored_commit_pom',tofile='adapter_model_pom')),encoding='utf-8')
  pom.write_text(new,encoding='utf-8');return original_edit(path,df,junit,testng)
 ns['edit_pom_file']=edit
 return ns

def restore_pom(index,out):
 folder=R/'completion_amendment_v1/input_audit/pom_provenance'/f'{index:03d}'
 import json
 jobs=json.loads((R/'manifest300.json').read_text());j=jobs[index-1];pom=Path(out)/'repo'/j['module']/'pom.xml'
 frozen=folder/'frozen_input_pom.xml';commit=folder/'commit_pom.xml'
 ensure(pom.read_bytes()==frozen.read_bytes(),'Snapshot malformed input differs from provenance')
 # A repaired in-memory prefix must recover exactly the original model.
 old=frozen.read_text();repaired=old.replace('<project ','<project xmlns:ns1="https://www.w3.org/2001/XMLSchema-instance" ',1)
 ensure(canonical(ET.fromstring(repaired))==canonical(ET.fromstring(commit.read_bytes())),'POM restoration changes semantic model beyond serialization loss')
 (Path(out)/'pom_malformed_backup.xml').write_bytes(pom.read_bytes());pom.write_bytes(commit.read_bytes())
 dump(Path(out)/'pom_restoration.json',{'sampled_commit':j['commit_sha'],'source':str(commit),'source_sha256':sha(commit),'before_sha256':sha(frozen),'after_sha256':sha(pom),'semantic_model_same_after_in_memory_prefix_recovery':True,'business_source_changed':False})
