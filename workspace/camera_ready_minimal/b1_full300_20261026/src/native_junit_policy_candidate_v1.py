"""Unadmitted candidate: supply missing native JUnit4 only after generation.
Never upgrades an existing dependency or changes providers, tests or compile scope.
"""
import copy,difflib
from xml.etree import ElementTree as ET
from maven_adapter_v1 import NS,GuardAbort,sha,dump

URI=NS['m']
def ensure(ok,message):
 if not ok:raise GuardAbort(message)
def norm(node):
 return (node.tag,tuple(sorted(node.attrib.items())),(node.text or '').strip(),tuple(norm(x) for x in node))
def candidate(text,dependency):
 existing=[x for x in dependency['classpath'] if x['path'].startswith('junit/junit/')]
 if existing:
  ensure(all(x['path'].split('/')[2].startswith('4.') for x in existing),'Existing non-JUnit4 requires separate review')
  return text,False
 root=ET.fromstring(text);before=norm(root)
 ensure(not root.findall(".//m:dependency[m:groupId='junit'][m:artifactId='junit']",NS),'Unresolved existing JUnit declaration; refuse override')
 deps=root.find('m:dependencies',NS);created=deps is None
 if created:deps=ET.SubElement(root,'{'+URI+'}dependencies')
 dep=ET.SubElement(deps,'{'+URI+'}dependency')
 for key,value in [('groupId','junit'),('artifactId','junit'),('version','4.13.2'),('scope','test')]:ET.SubElement(dep,'{'+URI+'}'+key).text=value
 undo=copy.deepcopy(root);d=undo.find('m:dependencies',NS);d.remove(d[-1])
 if created:undo.remove(d)
 ensure(norm(undo)==before,'Unexpected POM edit')
 ET.register_namespace('',URI)
 return ET.tostring(root,encoding='unicode')+'\n',True
def patch(pom,out,dependency):
 original=pom.read_text(encoding='utf-8');updated,changed=candidate(original,dependency)
 dump(out/'native_junit_policy.json',{'candidate_only':True,'condition':'no resolved junit:junit and no unresolved JUnit declaration','changed':changed,'addition':'junit:junit:4.13.2:test' if changed else None,'generation_already_complete':True,'provider_changes':False,'original_sha256':sha(pom)})
 if changed:
  with (out/'pom_before_native_junit.xml').open('xb') as f:f.write(pom.read_bytes())
  (out/'native_junit.diff').write_text(''.join(difflib.unified_diff(original.splitlines(True),updated.splitlines(True),fromfile='before',tofile='candidate')),encoding='utf-8')
  pom.write_text(updated,encoding='utf-8')
 return changed
def compare(before,after):
 def mapping(rows):return {x['path']:x['sha256'] for x in rows}
 ensure(mapping(before['compile_classpath'])==mapping(after['compile_classpath']),'Production compile closure changed')
 b=mapping(before['classpath']);a=mapping(after['classpath'])
 ensure(all(a.get(k)==v for k,v in b.items()),'Existing test dependency removed or changed')
 added=set(a)-set(b);allowed={'junit/junit/4.13.2/junit-4.13.2.jar','org/hamcrest/hamcrest-core/1.3/hamcrest-core-1.3.jar'}
 ensure(added<=allowed and 'junit/junit/4.13.2/junit-4.13.2.jar' in added,'Unexpected dependency delta')
 return {'production_compile_closure':'UNCHANGED','existing_test_dependencies':'UNCHANGED','added':sorted(added)}
