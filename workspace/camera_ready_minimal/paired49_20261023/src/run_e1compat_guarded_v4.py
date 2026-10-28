"""Guard all byte content and file membership of source E1 job during diagnostic replay."""
import json,runpy,sys
from datetime import datetime,timezone
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));sys.path.insert(0,str(BASE/'src'));import audit
import diagnose_e1_compatibility_v4 as mod
name=sys.argv[1];args=sys.argv[2:]
allowed={'run_e1compat_junit_v2.py':'054933cbf7546d48ffc525116e1728aea76fd9c88e606f1828fe94b80e16f5fa','replay_e1_discovery_runtime_v2.py':'a8a80c71c4042cb34e3fef27ed6abc283715ccd48bf208f8b10544599c12b386'}
allowed['replay_hazel_selector_v1.py']='f6f57c5418dfa44fb0c2986649697a8ddf7ac8ba0f98244ddc53c08a1aa66bc0'
assert name in allowed and audit.sha(BASE/'src'/name)==allowed[name]
job=args[0] if name.startswith('run_e1compat') else ('48' if args[0]=='runtime48' else args[1])
assert job in mod.JOB_IDS
old=mod.ORIG/'jobs'/job
runid=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')+'_'+job
out=mod.STAGE/'original_guards'/runid;out.mkdir(parents=True)
def snapshot():return {p.relative_to(old).as_posix():{'sha256':audit.sha(p),'bytes':p.stat().st_size} for p in mod.walk(old)}
mod.verify_locked();before=snapshot();mod.dump(out/'before.json',before)
properties=[]
for rel,h in mod.load(old/'generated_manifest.json').items():
    p=old/rel
    if p.name.endswith('_ESTest.java'):assert 'useVFS = true' in p.read_text(encoding='utf-8') and 'useVNET = true' in p.read_text(encoding='utf-8')
    if p.name.endswith('_scaffolding.java'):properties=[s.strip() for s in p.read_text(encoding='utf-8').splitlines() if 'System.setProperty' in s]
mod.dump(out/'recorded_properties.json',{'preserved_scaffold_properties':properties,'VFS_and_VNET_enabled':True,'rewritten_scaffold':False})
audit.log('E1_COMPATIBILITY_ORIGINAL_JOB_GUARD_START',job=job,files=len(before),manifest_sha256=audit.sha(out/'before.json'),script_sha256=allowed[name],argv=args,recorded_absolute_properties_preserved=True)
try:
    sys.argv=[str(BASE/'src'/name),*args]
    runpy.run_path(str(BASE/'src'/name),run_name='__main__')
finally:
    after=snapshot();mod.dump(out/'after.json',after)
    issues=[p for p in sorted(set(before)|set(after)) if before.get(p)!=after.get(p)]
    mod.dump(out/'result.json',{'job':job,'source_E1_job_file_bytes_and_membership_unchanged':not issues,'issues':issues,'before_files':len(before),'after_files':len(after),'scaffold_recorded_properties_preserved':True})
    audit.log('E1_COMPATIBILITY_ORIGINAL_JOB_GUARD_END',job=job,unchanged=not issues,issues=issues,report_sha256=audit.sha(out/'result.json'))
    assert not issues,'Source E1 job changed during replay: '+str(issues)
    mod.verify_locked()
