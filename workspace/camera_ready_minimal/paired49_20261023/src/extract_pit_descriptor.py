"""Version-pinned read-only metadata audit of PIT failing-test handling."""
import hashlib,json,sys,zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));import audit
out=BASE/'validation/pit116_descriptor';out.mkdir(exist_ok=False)
jar=audit.ROOT/'camera_ready_minimal/maven_cache_20261023/org/pitest/pitest-maven/1.16.0/pitest-maven-1.16.0.jar'
with zipfile.ZipFile(jar) as z:raw=z.read('META-INF/maven/plugin.xml')
(out/'plugin.xml').write_bytes(raw);root=ET.fromstring(raw)
mojo=next(m for m in root.findall('./mojos/mojo') if m.findtext('goal')=='mutationCoverage')
parameters={p.findtext('name'):p.findtext('description') for p in mojo.findall('./parameters/parameter')}
config={p.tag:{'default':p.attrib.get('default-value'),'property':p.text} for p in mojo.findall('./configuration/*')}
report={'source_jar':str(jar),'jar_sha256':audit.sha(jar),'plugin_xml_sha256':hashlib.sha256(raw).hexdigest(),
 'goal':'mutationCoverage','version':'1.16.0','parameters':{k:{'description':parameters[k],**config.get(k,{})} for k in ['parseSurefireConfig','skipFailingTests']},
 'interpretation':'Descriptor documents Surefire testFailureIgnore overriding skipFailingTests when parsing is enabled; consistent with partial passing-test mutation results despite Surefire failures. Historical invoked POM not certified.',
 'experiment_commands_executed':0,'GPT_data_modified':False}
assert report['parameters']['parseSurefireConfig']['default']=='true'
assert report['parameters']['skipFailingTests']['default']=='false'
assert 'testFailureIgnore' in report['parameters']['skipFailingTests']['description']
with (out/'summary.json').open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
audit.log('PIT116_DESCRIPTOR_READONLY_AUDIT',jar_sha256=audit.sha(jar),report_sha256=audit.sha(out/'summary.json'),experiment_commands=0)
print(json.dumps(report,indent=2))
