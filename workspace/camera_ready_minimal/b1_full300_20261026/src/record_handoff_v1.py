"""Record extra handoff artifacts; read-only verification of closed preparation registry."""
import sys,json
from pathlib import Path
R=Path(__file__).resolve().parents[1];B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
registry=json.loads((R/'audit/preparation_registry_v2.json').read_text(encoding='utf-8'))
for item in registry['files']:assert audit.sha(R/item['path'])==item['sha256'],item['path']
extras=[]
for name in ['HANDOFF_20261026.md','audit/dashboard_preview_v1.png','audit/dashboard_overview_v1.png','src/record_handoff_v1.py']:
 p=R/name;extras.append({'path':name,'sha256':audit.sha(p),'bytes':p.stat().st_size})
result={'registry_check':'PASS','registered_files':len(registry['files']),'extras':extras,'benchmark_started':False,'monitor_url':'http://127.0.0.1:8766/','monitor_only':True,'automatic_batch_start':False}
with (R/'audit/handoff_registry_v1.json').open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
audit.log('B1_PLAN_AND_PREFLIGHT_HANDOFF',stage=str(R),registry_sha256=audit.sha(R/'audit/handoff_registry_v1.json'),benchmark_started=False,monitor_url=result['monitor_url'])
print(json.dumps(result,ensure_ascii=False,indent=2))
