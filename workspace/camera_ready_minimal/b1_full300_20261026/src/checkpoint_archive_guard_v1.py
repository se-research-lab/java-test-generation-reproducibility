"""Verify archived bytes plus precisely one post-archive terminal log append."""
import hashlib,json
from maven_adapter_v1 import sha,GuardAbort
def ensure(ok,message):
 if not ok:raise GuardAbort(message)
def verify(folder):
 manifest=folder/'artifact_manifest.json';rows=json.loads(manifest.read_text(encoding='utf-8'));append=None
 for row in rows:
  p=folder/row['relative'];ensure(p.is_file(),'Missing archived file: '+row['relative'])
  if sha(p)==row['sha256']:continue
  ensure(row['relative']=='events.jsonl','Changed archived evidence: '+row['relative'])
  data=p.read_bytes();prefix=data[:row['bytes']];suffix=data[row['bytes']:]
  ensure(hashlib.sha256(prefix).hexdigest()==row['sha256'],'Archived event prefix changed')
  lines=suffix.decode('utf-8').splitlines();ensure(len(lines)==1,'Unexpected post-archive log changes')
  event=json.loads(lines[0]);ensure(event['kind']=='JOB_TERMINAL','Unexpected post-archive event')
  ensure(event['artifact_manifest_sha256']==sha(manifest),'Terminal event archive hash differs')
  ensure(event['result_sha256']==sha(folder/'result.json'),'Terminal result hash differs')
  ensure(event['class_key']==json.loads((folder/'result.json').read_text(encoding='utf-8'))['class_key'],'Terminal class mismatch')
  append={'relative':row['relative'],'prefix_bytes':row['bytes'],'prefix_sha256':row['sha256'],'appended_bytes':len(suffix),'appended_sha256':hashlib.sha256(suffix).hexdigest(),'current_sha256':sha(p),'verified_terminal_event':event}
 return {'status':'PASS','files_verified':len(rows),'manifest_sha256':sha(manifest),'post_archive_append':append}
