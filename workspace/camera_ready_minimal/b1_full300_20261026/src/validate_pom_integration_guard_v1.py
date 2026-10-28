import json,subprocess
from pathlib import Path
import pandas as pd
from maven_adapter_v1 import generation_bindings,GuardAbort,dump,sha,R
from pom_integration_guard_v1 import verify
O=R/'validation/pom_integration_guard_v1';O.mkdir(parents=True,exist_ok=False);M=O/'repo';M.mkdir()
source='<project xmlns="http://maven.apache.org/POM/4.0.0"><modelVersion>4.0.0</modelVersion><groupId>synthetic</groupId><artifactId>fixture</artifactId><version>1</version><dependencies><dependency><groupId>business</groupId><artifactId>unchanged</artifactId><version>1</version></dependency></dependencies></project>'
(M/'pom.xml').write_text(source,encoding='utf-8')
class Commands:
 TimeoutExpired=subprocess.TimeoutExpired
 def run(self,*args,**kw):raise GuardAbort('No subprocess in POM fixture')
ns=generation_bindings(Commands(),O,lambda *args,**kw:None)
df=pd.DataFrame([{'Test_Path':str(M/'src/test/java/fixture/BranchFixture_ESTest.java').replace('\\','/')}])
assert ns['edit_pom_file'](str(M),df,'4',None) is not None
assert ns['add_evosuite_pom'](str(M)) is not None
after=(M/'pom.xml').read_text(encoding='utf-8');guard=verify(source,after);checks=['actual_E49_helpers_allowlisted_integration']
for name,modified in [('business_dependency_changed',after.replace('<artifactId>unchanged</artifactId>','<artifactId>changed</artifactId>')),('runtime_scope_changed',after.replace('<scope>system</scope>','<scope>test</scope>',1)),('project_version_changed',after.replace('<version>1</version>','<version>2</version>',1))]:
 try:verify(source,modified)
 except GuardAbort:checks.append(name)
 else:raise AssertionError(name)
result={'status':'PASS','checks':checks,'scope':guard,'Java_calls':0,'experiment_calls':0,'guard_sha256':sha(R/'src/pom_integration_guard_v1.py')};dump(O/'result.json',result);print(json.dumps(result,indent=2))
