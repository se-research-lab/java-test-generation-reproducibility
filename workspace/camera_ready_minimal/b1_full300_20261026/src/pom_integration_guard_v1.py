"""Guard the E49 POM integration separately from its conditional compatibility patch."""
import copy
from xml.etree import ElementTree as ET
from pathlib import Path
from maven_adapter_v1 import JDK,WORKSPACE,GuardAbort
N={'m':'http://maven.apache.org/POM/4.0.0'}
def local(tag):return tag.rsplit('}',1)[-1]
def canonical(e):
 return (local(e.tag),tuple(sorted(e.attrib.items())),(e.text or '').strip(),tuple(canonical(c) for c in e))
def children(e,name):return [x for x in e if local(x.tag)==name]
def field(e,name):return next(((x.text or '').strip() for x in e if local(x.tag)==name),'')
def allowed_plugin(p):
 g=field(p,'groupId');a=field(p,'artifactId')
 return (g,a) in {('org.apache.maven.plugins','maven-surefire-plugin'),('org.pitest','pitest-maven'),('org.jacoco','jacoco-maven-plugin')} or g=='org.evosuite.plugins'
def stripped(root):
 e=copy.deepcopy(root)
 for build in children(e,'build'):
  for plugins in children(build,'plugins'):
   for p in list(plugins):
    if local(p.tag)=='plugin' and allowed_plugin(p):plugins.remove(p)
   if not list(plugins) and not plugins.attrib and not (plugins.text or '').strip():build.remove(plugins)
  if not list(build) and not build.attrib and not (build.text or '').strip():e.remove(build)
 for deps in children(e,'dependencies'):
  if not list(deps) and not deps.attrib and not (deps.text or '').strip():e.remove(deps)
 return e
def verify(before_text,after_text):
 before=ET.fromstring(before_text);after=ET.fromstring(after_text)
 bd=children(before,'dependencies');ad=children(after,'dependencies')
 if len(bd)>1 or len(ad)!=1:raise GuardAbort('Unqualified dependencies structure')
 old=list(bd[0]) if bd else [];new=list(ad[0])
 if len(new)!=len(old)+2 or [canonical(d) for d in new[:len(old)]]!=[canonical(d) for d in old]:raise GuardAbort('Existing dependency changed or undeclared addition')
 expected=[{'groupId':'org.evosuite','artifactId':'evosuite-standalone-runtime','version':'1.2.0','scope':'system','systemPath':str(WORKSPACE/'scripts_v2/evosuite-standalone-runtime-1.2.0.jar').replace('\\','/')},{'groupId':'com.sun','artifactId':'tools','version':'1.8.0','scope':'system','systemPath':str(JDK/'lib/tools.jar').replace('\\','/')}]
 for actual,want in zip(new[-2:],expected):
  got={local(x.tag):(x.text or '').strip() for x in actual}
  if got!=want or len(actual)!=len(want) or actual.attrib:raise GuardAbort('Runtime/tool dependency differs from E49')
 for d in new[-2:]:ad[0].remove(d)
 if canonical(stripped(before))!=canonical(stripped(after)):raise GuardAbort('POM changes outside E49 test integration allowlist')
 return {'original_dependency_entries_preserved':True,'added_system_dependencies':expected,'scope_note':'whole compile classpath equality is not claimed across runtime integration; policy-patch compile closure checked separately','other_changes_limited_to_E49_test_plugins':True}
