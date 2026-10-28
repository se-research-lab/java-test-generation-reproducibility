"""Append JUnit4 API only to test compiler/runtime and PIT. Keep production graph intact."""
import copy,difflib,os,json
from xml.etree import ElementTree as ET
from pathlib import Path
from maven_adapter_v1 import R,NS,sha,dump,GuardAbort
from native_junit_policy_candidate_v1 import norm
URI=NS['m']
def ensure(v,m):
 if not v:raise GuardAbort(m)
def child(p,n,t=None):
 x=ET.SubElement(p,'{'+URI+'}'+n)
 if t is not None:x.text=t
 return x
def get(p,n):
 x=p.find('m:'+n,NS)
 return x if x is not None else child(p,n)
def patch(module,out,before):
 pom=module/'pom.xml';text=pom.read_text();root=ET.fromstring(text)
 junit=[r for r in before['classpath'] if r['path'].startswith('junit/junit/')]
 ensure(len(junit)==1 and junit[0]['path']=='junit/junit/3.8.1/junit-3.8.1.jar','Exact JUnit3 precondition')
 jars=[R/'cache_preparation_v1/maven_cache'/rel for rel in ['junit/junit/4.13.2/junit-4.13.2.jar','org/hamcrest/hamcrest-core/1.3/hamcrest-core-1.3.jar']]
 manifest={r['relative']:r['sha256'] for r in json.loads((R.parent/'paired49_20261023/e1_compatibility_diagnostic_v1/cache_copy_manifest.json').read_text())}
 for p in jars:ensure(sha(p)==manifest[p.relative_to(R/'cache_preparation_v1/maven_cache').as_posix()],'Support JAR hash drift')
 plugins=root.find('m:build/m:plugins',NS);ensure(plugins is not None,'No explicit plugin model')
 def plugin(name):
  found=[p for p in plugins if p.findtext('m:artifactId',namespaces=NS)==name]
  ensure(len(found)<=1,'Ambiguous plugin')
  if found:return found[0]
  p=child(plugins,'plugin');child(p,'groupId','org.apache.maven.plugins');child(p,'artifactId',name);return p
 compiler=plugin('maven-compiler-plugin');cfg=get(compiler,'configuration')
 ensure(cfg.find('m:testCompilerArguments',NS) is None,'Existing custom test arguments require review')
 cp=[str(module/'target/test-classes'),str(module/'target/classes')]+[r['absolute_path'] for r in before['classpath']]
 cp += [str(p) for p in jars if str(p) not in cp]
 args=child(cfg,'testCompilerArguments');child(args,'classpath',os.pathsep.join(cp))
 sure=plugin('maven-surefire-plugin');scfg=get(sure,'configuration')
 ensure(scfg.find('m:additionalClasspathElements',NS) is None,'Existing extra test CP requires review')
 additional=child(scfg,'additionalClasspathElements')
 for p in jars:child(additional,'additionalClasspathElement',str(p))
 deps=get(sure,'dependencies');ensure(len(deps)==0,'Existing explicit Surefire provider requires review')
 d=child(deps,'dependency')
 for k,v in [('groupId','org.apache.maven.surefire'),('artifactId','surefire-junit4'),('version','2.17')]:child(d,k,v)
 pit=plugin('pitest-maven');pcfg=get(pit,'configuration');ensure(pcfg.find('m:additionalClasspathElements',NS) is None,'Existing PIT extra CP requires review')
 additional=child(pcfg,'additionalClasspathElements')
 for p in jars:child(additional,'param',str(p))
 # Root dependencies and properties must remain byte-model-identical.
 old=ET.fromstring(text)
 for name in ['dependencies','dependencyManagement','properties','parent']:
  a=old.find('m:'+name,NS);b=root.find('m:'+name,NS);ensure((norm(a) if a is not None else None)==(norm(b) if b is not None else None),'Production model modified')
 ET.register_namespace('',URI);new=ET.tostring(root,encoding='unicode')+'\n'
 (out/'pom_before_junit3_test_support.xml').write_bytes(pom.read_bytes());pom.write_text(new,encoding='utf-8')
 (out/'junit3_test_support.diff').write_text(''.join(difflib.unified_diff(text.splitlines(True),new.splitlines(True),fromfile='before',tofile='test_tool_support')),encoding='utf-8')
 dump(out/'junit3_test_support.json',{'post_outcome':True,'production_dependency_entries_changed':False,'production_JUnit3_preserved':True,'test_classpath_order':'old entries first; pinned JUnit4 and Hamcrest appended','provider':'explicit surefire-junit4:2.17 tooling only','PIT_version_mutators_targets_changed':False,'suite_edited':False,'support_jars':[{'path':str(p),'sha256':sha(p)} for p in jars]})
