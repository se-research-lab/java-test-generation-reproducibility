"""Read-only exact-model access probe; no generation, no secret output."""
import json,os,sys,urllib.request,urllib.error
from datetime import datetime,timezone
from pathlib import Path
from dotenv import dotenv_values
B=Path(__file__).resolve().parents[1];sys.path.insert(0,str(B));import audit
key=dotenv_values(B.parents[1]/'scripts_v2/.env').get('OPENAI_API_KEY') or os.environ.get('OPENAI_API_KEY');assert key
report={'started_utc':datetime.now(timezone.utc).isoformat(),'requested_model':'gpt-4o-mini-2024-07-18','generation_POST_requests':0,'readonly_model_GET_requests':1,'secret_values_logged':False}
req=urllib.request.Request('https://api.openai.com/v1/models/gpt-4o-mini-2024-07-18',headers={'Authorization':'Bearer '+key})
try:
    with urllib.request.urlopen(req,timeout=30) as r:
        obj=json.loads(r.read());report['access']={'status':'PASS','http_status':r.status,'id':obj.get('id')}
except urllib.error.HTTPError as e:
    try:error=json.loads(e.read()).get('error',{})
    except Exception:error={}
    report['access']={'status':'HTTP_ERROR','http_status':e.code,'error_type':error.get('type'),'error_code':error.get('code')}
except urllib.error.URLError as e:
    reason=e.reason;report['access']={'status':'NETWORK_ERROR','exception_class':type(reason).__name__,'errno':getattr(reason,'errno',None),'winerror':getattr(reason,'winerror',None),'certificate_verification':getattr(reason,'verify_code',None)}
report['finished_utc']=datetime.now(timezone.utc).isoformat();p=B/'repeated_subset_v1/preflight_probe_access_v2.json'
with p.open('x',encoding='utf-8') as f:json.dump(report,f,indent=2);f.write('\n')
audit.log('NEW_FILE_REGISTERED',path=Path(__file__).relative_to(B).as_posix(),sha256=audit.sha(__file__),bytes=Path(__file__).stat().st_size,change_type='read-only exact-model connection probe')
audit.log('REPEAT_SUBSET_MODEL_ACCESS',report_sha256=audit.sha(p),**report)
print(json.dumps(report,indent=2))
