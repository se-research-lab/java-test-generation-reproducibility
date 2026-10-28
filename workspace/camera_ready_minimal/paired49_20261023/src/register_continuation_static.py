"""Register only completed static continuation artifacts; exclude live jobs/ledgers."""
import json,sys
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));import audit
paths=[BASE/n for n in ['src/register_continuation_static.py','src/status_e49_readonly.py','GIAI_THICH_MEAN_RANK_A12_RQ4.md','TIEP_TUC_ANALYTICS_VA_TRANG_THAI_E49_20261023.md','validation/e49_raw_prefix17.json']]
for rel in ['outputs/budget_accounting','outputs/pilot_chronology','validation/junit_rule_probe_v1']:
    paths.extend(p for p in (BASE/rel).rglob('*') if p.is_file())
prior={e['path']:e['sha256'] for e in audit.events() if e['kind']=='NEW_FILE_REGISTERED'}
prior.update({e['path']:e['after_sha256'] for e in audit.events() if e['kind']=='FILE_REVISION'})
records=[];pending=[]
for p in sorted(set(paths)):
    rel=p.relative_to(BASE).as_posix();h=audit.sha(p)
    if rel in prior:assert prior[rel]==h,'Unrecorded static edit: '+rel
    else:pending.append(('NEW_FILE_REGISTERED',dict(path=rel,sha256=h,bytes=p.stat().st_size,change_type='completed isolated continuation artifact')))
    records.append({'path':rel,'sha256':h,'bytes':p.stat().st_size})
audit._append_many(pending)
out=BASE/'audit/static_continuation_registry.json'
with out.open('x',encoding='utf-8') as f:json.dump({'files':records,'live_job_or_ledger_files_frozen':False},f,indent=2)
audit.log('STATIC_CONTINUATION_REGISTRY_COMPLETE',files=len(records),new_records=len(pending),manifest_sha256=audit.sha(out))
print(json.dumps({'status':'PASS','files_verified':len(records),'new_files_registered':len(pending),'live_jobs_unmodified':True}))
