"""Final delivery seal after PDF, clean-source, evidence and guard validation."""
import hashlib,json,re,shutil,sys,zipfile
from pathlib import Path
from datetime import datetime,timezone
import psutil
R=Path(__file__).resolve().parents[1];O=R/'camera_ready_checkpoint300_v1';D=O/'delivery';B=R.parent/'paired49_20261023';F=R/'completion_amendment_v1/final300_offline_v1'
sys.path.insert(0,str(B));import audit
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,data):
 with p.open('x',encoding='utf-8') as f:json.dump(data,f,indent=2,ensure_ascii=False);f.write('\n')
assert not (D/'SHA256SUMS.txt').exists()
assert load(D/'VALIDATION.json')['status']=='PASS'
receipt=load(O/'private_artifact_receipt.json');assert sha(receipt['path'])==receipt['sha256'] and receipt['secret_signature_findings']==0
shutil.copy2(O/'private_artifact_receipt.json',D/'PRIVATE_ARTIFACT_RECEIPT.json')
for name,label in [('PROTECTED_GUARD.json','camera_ready_final_protected_guard'),('GPT_FROZEN_GUARD.json','camera_ready_final_gpt_guard')]:
 raw=(B/'audit'/f'{label}.stdout.txt').read_text(encoding='utf-8');data=json.loads(raw);write(D/name,data)
assert load(D/'GPT_FROZEN_GUARD.json')['status']=='PASS'
assert load(D/'PROTECTED_GUARD.json')['changed_or_missing']==[]
# Recheck the immutable analysis pack used to author the manuscript.
for line in (F/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
 expected,rel=line.split('  ',1);assert sha(F/rel)==expected,rel
workers=[]
for p in psutil.process_iter(['pid','name','cmdline']):
 name=(p.info['name'] or '').lower();args=p.info['cmdline'] or []
 if name in ['java.exe','javaw.exe']:workers.append({'pid':p.pid,'name':name})
 if name in ['python.exe','pythonw.exe'] and any(('dispatcher' in x.lower() or 'worker' in x.lower()) and x.lower().endswith('.py') for x in args):workers.append({'pid':p.pid,'name':name})
assert not workers,workers
write(D/'NO_EXPERIMENT_WORKERS.json',{'at_utc':datetime.now(timezone.utc).isoformat(),'workers':workers,'new_experiments_in_revision':0})
# Keep a snapshot of all new source authoring/build/validation commands.
scripts=['author_camera_ready_checkpoint300_v1.py','build_camera_ready_checkpoint300_v1.py','refine_camera_ready_checkpoint300_v1.py','package_camera_ready_checkpoint300_v1.py','package_private_checkpoint300_artifact_v1.py','package_private_checkpoint300_artifact_v2.py','validate_camera_ready_checkpoint300_v1.py','seal_camera_ready_checkpoint300_v1.py']
write(D/'REVISION_CODE_MANIFEST.json',[{'path':str(R/'src'/s),'sha256':sha(R/'src'/s)} for s in scripts])
files=[{'path':p.relative_to(D).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(D.iterdir()) if p.is_file()]
write(D/'DELIVERY_MANIFEST.json',{'at_utc':datetime.now(timezone.utc).isoformat(),'files':files,'state':'TECHNICAL_CAMERA_READY_COMPLETE_AUTHOR_APPROVAL_AND_SUBMISSION_PENDING','pdf_pages_including_references':15,'full300_E1_complete':False,'source_zip_clean_build_verified':True,'public_artifact_url':None,'uploaded':False,'registration_confirmed':False,'license_signed':False,'experimental_data_unchanged':True})
with (D/'SHA256SUMS.txt').open('x',encoding='utf-8') as f:
 for p in sorted(D.iterdir()):
  if p.is_file() and p.name!='SHA256SUMS.txt':f.write(sha(p)+'  '+p.name+'\n')
audit.log('CAMERA_READY_CHECKPOINT300_DELIVERY_SEALED',path=str(D),manifest_sha256=sha(D/'DELIVERY_MANIFEST.json'),hash_list_sha256=sha(D/'SHA256SUMS.txt'),pdf_sha256=sha(D/'FISAT2026_camera_ready.pdf'),pages=15,new_experiments=0)
print(json.dumps({'status':'SEALED','delivery':str(D),'pdf_pages':15,'files':len(files)+2,'private_artifact_size':receipt['zip_bytes'],'experiment_workers':workers,'author_actions_pending':True},indent=2))
