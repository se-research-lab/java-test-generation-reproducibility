"""Verify ordinary archives or the explicitly reconciled saved terminal066.
No generic fallback, archive creation, source rewrite, process or measurement.
"""
import json
from pathlib import Path
from maven_adapter_v1 import R, sha, GuardAbort
from checkpoint_archive_guard_v2 import verify as ordinary_verify

REVIEW=R/'audit/absent_v4_runner_reconciliation_v1'

def ensure(ok,why):
    if not ok:
        raise GuardAbort(why)

def verify(folder):
    folder=Path(folder).resolve()
    if (folder/'artifact_manifest.json').exists():
        return ordinary_verify(folder)
    ensure(folder==(R/'jobs/066').resolve(),'Missing archive requires separate explicit review')
    record=json.loads((REVIEW/'result.json').read_text(encoding='utf-8'))
    ensure(record['status']=='PASS_SAVED_TERMINAL_RECOVERED_NO_RERUN' and record['sample_index_1based']==66,
           'Saved checkpoint066 reconciliation not accepted')
    ensure(record['raw_job_modified'] is False and record['new_generation_calls']==record['new_measurement_calls']==record['GPT_API_calls']==0,
           'Reconciliation must be read-only with no experiment calls')
    manifest=(R/record['external_archive_path']).resolve()
    ensure(manifest==REVIEW/'job066_recovered_archive.json' and sha(manifest)==record['external_archive_sha256'],
           'External checkpoint066 archive drift')
    ensure(sha(folder/'result.json')==record['original_result_sha256'],'Saved terminal066 result drift')
    rows=json.loads(manifest.read_text(encoding='utf-8'))
    expected={r['relative'] for r in rows}
    actual={p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file() and 'temp' not in p.relative_to(folder).parts}
    ensure(expected==actual,'External checkpoint066 file census differs')
    for row in rows:
        path=(folder/row['relative']).resolve()
        ensure(path.is_relative_to(folder) and path.is_file() and sha(path)==row['sha256'],
               'External checkpoint066 archived file changed: '+row['relative'])
    return {'status':'PASS','files_verified':len(rows),'manifest_sha256':sha(manifest),
            'manifest_location':manifest.relative_to(R).as_posix(),'file_census':'PASS',
            'reconciled_saved_terminal':66,'new_generation_or_measurement_calls':0}
