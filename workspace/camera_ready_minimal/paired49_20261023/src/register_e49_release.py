"""Register only completed/static stage artifacts while benchmark outputs keep growing."""
import json,sys
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));import audit
lock=json.loads((BASE/'e49_driver/readiness_lock.json').read_text(encoding='utf-8'))
for rel,h in lock['code_and_input_hashes'].items():assert audit.sha(BASE/rel)==h,rel
for path,h in lock['tool_hashes'].items():assert audit.sha(path)==h,path
for path,h in lock['context_source_hashes'].items():assert audit.sha(path)==h,path
audit.verify()
files=[BASE/'audit.py',BASE/'STATUS_DRIVER_E49_DANG_CHAY.md']
for root in [BASE/'src',BASE/'outputs/maven260_sensitivity',BASE/'outputs/cluster300_sensitivity',BASE/'validation']:
    files.extend(p for p in root.rglob('*') if p.is_file())
for p in (BASE/'e49_driver').rglob('*'):
    if not p.is_file():continue
    rel=p.relative_to(BASE/'e49_driver')
    if rel.parts[0] in ['jobs','artifact_archive'] or p.name in ['controller_events.jsonl','release_manifest.json']:continue
    if p.name.startswith('job_result_') or p.name.startswith('results49'):continue
    files.append(p)
entries=[{'path':p.relative_to(BASE).as_posix(),'sha256':audit.sha(p),'bytes':p.stat().st_size} for p in sorted(set(files))]
manifest=BASE/'e49_driver/release_manifest.json'
with manifest.open('x',encoding='utf-8') as f:json.dump(entries,f,indent=2)
audit.log('E49_STATIC_RELEASE_REGISTERED',files=len(entries),manifest_sha256=audit.sha(manifest),
 live_outputs_excluded=['jobs','artifact_archive','controller_events.jsonl','results49 and job_result_*'],
 scope='Static release snapshot only; per-job manifests and observer archive register live results separately')
report={'status':'PASS','static_files_registered':len(entries),'code_tool_context_lock':'PASS','protected585':'PASS',
 'GPT_RQ123':'guard verified before admission and before/after every job','benchmark_status':'running; no aggregate efficacy claim',
 'audit_ledger':'serialized v2; original730 records losslessly retained','no_manuscript_edits':True}
out=BASE/'validation/e49_release_verification.json'
with out.open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
print(json.dumps(report,indent=2))
