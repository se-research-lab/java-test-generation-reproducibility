"""Verify ordinary archives or the explicitly reconciled saved terminal066.
No generic fallback, archive creation, source rewrite, process or measurement.
"""
import json
from datetime import datetime, timezone
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

def reuse_verified_checkpoint(folder):
    """Reuse the just-completed full audit; verify its immutable anchors again.

    This is explicitly not another full byte census. The continuation can only
    create new167 job directories and must not write any certified old job.
    A fresh full audit is required if this receipt is older than15 minutes.
    """
    folder=Path(folder).resolve()
    record=json.loads((REVIEW/'result.json').read_text(encoding='utf-8'))
    ensure(record['status']=='PASS_SAVED_TERMINAL_RECOVERED_NO_RERUN','Fresh saved-checkpoint audit required')
    age=(datetime.now(timezone.utc)-datetime.fromisoformat(record['at_utc'])).total_seconds()
    ensure(-5<=age<=900,'Full checkpoint audit no longer fresh; no automatic continuation')
    if folder==(R/'jobs/066').resolve():
        return verify(folder)
    from run_maven_b1_v3 import selected_result
    certificate=None
    for index,checks in record['original_archive_checks'].items():
        if folder==(R/'jobs'/f'{int(index):03d}').resolve():
            certificate=checks['base']
        elif folder==selected_result(int(index)).parent.resolve() and 'selected' in checks:
            certificate=checks['selected']
    ensure(certificate is not None,'Folder outside the fresh full-audit certificate')
    manifest=folder/'artifact_manifest.json'
    ensure(sha(manifest)==certificate['manifest_sha256'],'Certified archive manifest changed')
    entries=json.loads(manifest.read_text(encoding='utf-8'))
    result_name='diagnostic_result.json' if (folder/'diagnostic_result.json').exists() else 'result.json'
    entry=next((x for x in entries if x['relative']==result_name),None)
    ensure(entry is not None and sha(folder/result_name)==entry['sha256'],'Certified result changed')
    event=next((x for x in entries if x['relative']=='events.jsonl'),None)
    if event:
        append=certificate.get('post_archive_append')
        expected=append['current_sha256'] if append else event['sha256']
        ensure(sha(folder/'events.jsonl')==expected,'Certified event log changed')
    return {'status':'PASS_FRESH_FULL_AUDIT_REUSED_ANCHORS_RECHECKED',
            'full_audit_at_utc':record['at_utc'],'full_audit_receipt_sha256':sha(REVIEW/'result.json'),
            'full_archive_bytes_rehashed_here':False,'manifest_sha256':sha(manifest)}
