"""Complete file census plus hash verification; preserve v1 log-append rule."""
from checkpoint_archive_guard_v1 import verify as verify_hashes,ensure
def verify(folder):
 import json
 rows=json.loads((folder/'artifact_manifest.json').read_text(encoding='utf-8'))
 expected={x['relative'] for x in rows}
 actual={p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file() and 'temp' not in p.relative_to(folder).parts and p.name!='artifact_manifest.json'}
 ensure(expected==actual,'Archive file census differs: missing='+str(sorted(expected-actual))+'; extra='+str(sorted(actual-expected)))
 result=verify_hashes(folder);result['file_census']='PASS';return result
