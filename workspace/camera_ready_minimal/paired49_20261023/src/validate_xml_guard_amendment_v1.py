import ast,copy,json,re,sys
from pathlib import Path
from xml.etree import ElementTree as ET
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));import audit
src=BASE/'src/run_e1compat_junit_v2.py';tree=ast.parse(src.read_text(encoding='utf-8'))
node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='xml_without_formatting');ns={'copy':copy};exec(compile(ast.Module(body=[node],type_ignores=[]),str(src),'exec'),ns)
canon=lambda text:ET.tostring(ns['xml_without_formatting'](ET.fromstring(text)))
a='<project><dependency>\n<groupId>junit</groupId>\n<artifactId>junit</artifactId>\n<scope>test</scope>\n</dependency><plugin><version>2.17</version></plugin></project>'
assert canon(a)==canon(a.replace('\n','  '))
assert canon(a)!=canon(a.replace('<scope>test</scope>','<scope>compile</scope>'))
assert canon(a)!=canon(a.replace('2.17','3.0.0'))
assert canon(a)!=canon(a.replace('</project>','<extra/></project>'))
checks=[]
for job in ['09','12','13','14','15']:
    out=BASE/'e1_compatibility_diagnostic_v1/jobs'/job;info=json.loads((out/'input.json').read_text(encoding='utf-8'));p=out/'repo'/info['module_relative']/'pom.xml'
    assert not (out/'junit_patch.json').exists()
    before=p.read_text(encoding='utf-8');matches=[m for m in re.finditer(r'<dependency\b[^>]*>.*?</dependency>',before,re.S) if re.search(r'<groupId>\s*junit\s*</groupId>',m.group()) and re.search(r'<artifactId>\s*junit\s*</artifactId>',m.group())]
    assert len(matches)==1;m=matches[0];chunk=m.group();old=re.search('<version>(.*?)</version>',chunk,re.S)
    patched=re.sub('<version>.*?</version>','<version>4.13.2</version>',chunk,count=1,flags=re.S) if old else chunk.replace('</artifactId>','</artifactId><version>4.13.2</version>',1)
    after=before[:m.start()]+patched+before[m.end():]
    root=ET.fromstring(after);nsx={'m':'http://maven.apache.org/POM/4.0.0'}
    dep=next(d for d in root.findall('m:dependencies/m:dependency',nsx) if d.findtext('m:groupId',namespaces=nsx)=='junit' and d.findtext('m:artifactId',namespaces=nsx)=='junit')
    v=dep.find('m:version',nsx)
    if old:v.text=old.group(1)
    else:dep.remove(v)
    assert canon(before)==ET.tostring(ns['xml_without_formatting'](root))
    checks.append({'job':job,'read_only_exact_version_reversal_pass':True,'source_POM_unchanged':True})
audit.log('E1_COMPATIBILITY_XML_GUARD_VALIDATED',wrapper_sha256=audit.sha(src),whitespace_only_accepted=True,scope_plugin_and_extra_node_rejected=True,real_POM_reversals=checks,experiment_code_or_scores_changed=False)
print(json.dumps({'status':'PASS','real_POMs':len(checks),'negative_scope_plugin_extra_checks':'PASS','POM_writes':0},indent=2))
