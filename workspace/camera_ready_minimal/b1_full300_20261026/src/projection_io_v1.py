"""Evidence-preserving UI snapshot publication; never launches experiments.

publish_json(target, data, *, label='projection') returns a JSON-safe receipt.
Only OSError is converted to an unsuccessful receipt. GuardAbort, invalid JSON,
and caller/programming errors propagate. Failed temporary files are retained.
"""
import hashlib,json,math,os,re,stat,time,uuid
from pathlib import Path
from maven_adapter_v1 import R,GuardAbort

IO_ROOT=R/'runtime/projection_io_v1'
REPARSE=getattr(stat,'FILE_ATTRIBUTE_REPARSE_POINT',0x400)

def ensure(ok,message):
 if not ok:raise GuardAbort(message)
def digest(data):return hashlib.sha256(data).hexdigest()
def validate_json(value):
 if isinstance(value,dict):
  if not all(isinstance(k,str) for k in value):raise TypeError('UI projection JSON object keys must be strings')
  for child in value.values():validate_json(child)
 elif isinstance(value,list):
  for child in value:validate_json(child)
 elif value is None or isinstance(value,(str,bool,int)):pass
 elif isinstance(value,float):
  if not math.isfinite(value):raise ValueError('UI projection JSON must contain finite numbers')
 else:raise TypeError('Unsupported UI projection JSON value: '+type(value).__name__)
def owned_target(target):
 p=Path(target)
 ensure(p.is_absolute(),'UI projection target must be absolute')
 p=Path(os.path.abspath(str(p)))
 ensure(p==R/'status.json' or (p.is_relative_to(R/'runtime') and p!=R/'runtime'),'UI publication outside runtime/status refused')
 ensure(p.suffix=='.json','UI snapshot target must be a JSON file')
 check_chain(p)
 return p
def check_chain(path):
 cursor=Path(path)
 while cursor.is_relative_to(R):
  if cursor.exists() or cursor.is_symlink():
   s=cursor.lstat();ensure(not cursor.is_symlink() and not getattr(s,'st_file_attributes',0)&REPARSE,'UI publication through reparse/link refused')
  if cursor==R:break
  cursor=cursor.parent
def exclusive_bytes(path,data):
 with path.open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
def persist_receipt(result,folder,identifier):
 # Receipt I/O must not turn a snapshot write problem into an experiment failure.
 try:
  check_chain(folder);folder.mkdir(parents=True,exist_ok=True);check_chain(folder);path=folder/(identifier+'.json')
  raw=(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf-8')
  exclusive_bytes(path,raw);result['receipt_path']=str(path);result['receipt_sha256']=digest(raw)
 except OSError as ex:result['receipt_write_error']={'type':type(ex).__name__,'detail':str(ex)}
 return result

def publish_json(target,data,*,label='projection',max_retry_seconds=1.5,retry_delay_seconds=.05,replace_fn=None):
 """Publish one owned JSON snapshot, retaining old bytes and every failed temp.

 PermissionError during replace is retried for at most1.5s. All other OSError
 failures return a receipt immediately. replace_fn is a test seam taking two
 Paths; production callers leave it unset. No cleanup/deletion occurs here.
 """
 ensure(isinstance(label,str) and re.fullmatch(r'[A-Za-z0-9_.-]{1,64}',label) is not None,'Invalid UI projection label')
 ensure(isinstance(max_retry_seconds,(int,float)) and not isinstance(max_retry_seconds,bool) and 0<max_retry_seconds<=1.5,'UI replace retry window must be positive and <=1.5s')
 ensure(isinstance(retry_delay_seconds,(int,float)) and not isinstance(retry_delay_seconds,bool) and 0<retry_delay_seconds<=.25,'Invalid UI retry delay')
 if not isinstance(data,(dict,list)):raise TypeError('UI snapshot must be a JSON object or array')
 validate_json(data)
 payload=(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf-8')
 identifier=label+'_'+str(os.getpid())+'_'+str(time.time_ns())+'_'+uuid.uuid4().hex
 result={'published':False,'identifier':identifier,'target':str(target),'intended_sha256':digest(payload),'intended_bytes':len(payload),'attempts':0,'replace_completed':False,'backup':None,'temporary_path':None,'temporary_preserved':False}
 stage='validate_owned_path';started=time.monotonic();temporary=None
 try:
  path=owned_target(target);result['target']=str(path)
  check_chain(IO_ROOT);IO_ROOT.mkdir(parents=True,exist_ok=True);check_chain(IO_ROOT)
  for name in ['backups','temporary','receipts','failures']:
   check_chain(IO_ROOT/name);(IO_ROOT/name).mkdir(exist_ok=True);check_chain(IO_ROOT/name)
  check_chain(path.parent);path.parent.mkdir(parents=True,exist_ok=True);check_chain(path.parent)
  if path.exists():
   ensure(path.is_file(),'Existing UI target must be a regular file');stage='backup_previous_bytes'
   old=path.read_bytes();backup=IO_ROOT/'backups'/(identifier+'_'+path.name+'.before')
   exclusive_bytes(backup,old);ensure(digest(backup.read_bytes())==digest(old),'UI previous-byte backup mismatch')
   result['backup']={'path':str(backup),'sha256':digest(old),'bytes':len(old)}
  stage='write_exclusive_temporary'
  temporary=IO_ROOT/'temporary'/(identifier+'_'+path.name+'.tmp');result['temporary_path']=str(temporary)
  exclusive_bytes(temporary,payload);ensure(digest(temporary.read_bytes())==result['intended_sha256'],'UI temp serialization hash mismatch')
  replace=replace_fn or os.replace;retry_started=time.monotonic();stage='replace_snapshot'
  while True:
   result['attempts']+=1
   try:replace(temporary,path);result['replace_completed']=True;break
   except PermissionError:
    remaining=max_retry_seconds-(time.monotonic()-retry_started)
    if remaining<=0:raise
    time.sleep(min(retry_delay_seconds,remaining))
  stage='verify_published_bytes';ensure(digest(path.read_bytes())==result['intended_sha256'],'UI published bytes mismatch after successful replace')
  result.update(published=True,published_sha256=result['intended_sha256'],elapsed_seconds=time.monotonic()-started,stage='complete',temporary_preserved=False)
  return persist_receipt(result,IO_ROOT/'receipts',identifier)
 except OSError as ex:
  result.update(error_type=type(ex).__name__,error=str(ex),errno=getattr(ex,'errno',None),winerror=getattr(ex,'winerror',None),stage=stage,elapsed_seconds=time.monotonic()-started)
  if temporary is not None:
   try:
    result['temporary_preserved']=temporary.is_file()
    if result['temporary_preserved']:result['temporary_actual_sha256']=digest(temporary.read_bytes())
   except OSError as inspect_error:result['temporary_inspection_error']=str(inspect_error)
  return persist_receipt(result,IO_ROOT/'failures',identifier)
