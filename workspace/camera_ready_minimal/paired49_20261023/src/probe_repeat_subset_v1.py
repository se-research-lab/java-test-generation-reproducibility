"""Read-only admission probe: exact historical model and local runtime; no generation."""
import importlib.metadata,json,os,shutil,sys,time
from datetime import datetime,timezone
from pathlib import Path
B=Path(__file__).resolve().parents[1];sys.path.insert(0,str(B));import audit
ST=B/'repeated_subset_v1';assert not ST.exists();ST.mkdir()
audit.log('NEW_FILE_REGISTERED',path=Path(__file__).relative_to(B).as_posix(),sha256=audit.sha(__file__),bytes=Path(__file__).stat().st_size,change_type='new read-only model/runtime admission probe')
report={'started_utc':datetime.now(timezone.utc).isoformat(),'model_requested':'gpt-4o-mini-2024-07-18','generation_POST_requests':0,'readonly_model_GET_requests':0,'key_values_logged':False,'disk_free_bytes':shutil.disk_usage(B).free,'packages':{}}
for name in ['openai','httpx','pandas','scipy','numpy','psutil','python-dotenv','tiktoken']:
    try:report['packages'][name]=importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:report['packages'][name]=None
from dotenv import dotenv_values
values=dotenv_values(B.parents[1]/'scripts_v2/.env');key=values.get('OPENAI_API_KEY') or os.environ.get('OPENAI_API_KEY')
report['credential_present']=bool(key)
if key:
    import urllib.request,urllib.error
    req=urllib.request.Request('https://api.openai.com/v1/models/gpt-4o-mini-2024-07-18',headers={'Authorization':'Bearer '+key})
    report['readonly_model_GET_requests']=1;start=time.monotonic()
    try:
        with urllib.request.urlopen(req,timeout=30) as r:
            obj=json.loads(r.read());report['model_access']={'status':'PASS','http_status':r.status,'id':obj.get('id'),'object':obj.get('object')}
    except urllib.error.HTTPError as e:
        body=json.loads(e.read());error=body.get('error',{})
        report['model_access']={'status':'FAIL','http_status':e.code,'error_type':error.get('type'),'error_code':error.get('code')}
    except Exception as e:report['model_access']={'status':'NETWORK_ERROR','exception_class':type(e).__name__}
    report['readonly_probe_seconds']=time.monotonic()-start
else:report['model_access']={'status':'NO_CREDENTIAL'}
report['finished_utc']=datetime.now(timezone.utc).isoformat()
p=ST/'preflight_probe.json'
with p.open('x',encoding='utf-8') as f:json.dump(report,f,ensure_ascii=False,indent=2);f.write('\n')
audit.log('REPEAT_SUBSET_READONLY_ADMISSION_PROBE',path=str(p.relative_to(B)),sha256=audit.sha(p),model_access=report['model_access'],generation_POST_requests=0,readonly_model_GET_requests=report['readonly_model_GET_requests'])
print(json.dumps(report,indent=2))
