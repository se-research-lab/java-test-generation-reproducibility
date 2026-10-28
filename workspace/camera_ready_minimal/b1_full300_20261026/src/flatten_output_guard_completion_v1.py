"""Exact Vaadin derived Maven output exception; every business source stays hashed."""
import json
from pathlib import Path
from xml.etree import ElementTree as ET
from maven_controller_v2 import source_hashes as base_hashes
from maven_adapter_v1 import dump,sha,GuardAbort
REL='server/.flattened-pom.xml'
def source_hashes(root):
 rows=base_hashes(root)
 p=Path(root)/REL
 if p.exists():
  ET.parse(p) # Never ignore malformed or arbitrary files under a broad pattern.
  rows.pop(REL,None)
 return rows
def capture(out,label):
 out=Path(out);p=out/'repo'/REL
 root=out/'repo/pom.xml';t=root.read_text(encoding='utf-8')
 if '<artifactId>flatten-maven-plugin</artifactId>' not in t or '<phase>process-resources</phase>' not in t or '<updatePomFile>true</updatePomFile>' not in t:raise GuardAbort('Expected pre-existing derived-output plugin configuration missing')
 folder=out/'derived_pom_evidence';folder.mkdir(exist_ok=True)
 dest=folder/(label+'.xml')
 if p.exists():
  ET.parse(p)
  with dest.open('xb') as f:f.write(p.read_bytes())
 dump(folder/(label+'.json'),{'exact_derived_path':REL,'present':p.exists(),'sha256':sha(p) if p.exists() else None,'plugin_source':str(root),'plugin_source_sha256':sha(root),'business_source_ignore_patterns':[],'reason':'pre-existing flatten-maven-plugin output at process-resources; all other source files hashed'})
