"""Verify and seal completed fixed49 artifacts only; never scan/register live caches."""
import json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));import audit
REV=BASE/'manuscript_revision_v1'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def dump(p,obj):
    with p.open('x',encoding='utf-8') as f:json.dump(obj,f,ensure_ascii=False,indent=2);f.write('\n')
def main():
    audit.verify()
    guard=BASE.parents[1]/'review_reports/minimal_camera_ready_20261023/guard_rq123_frozen.py'
    argv=[sys.executable,'-B','-X','utf8',str(guard)]
    audit.log('FINAL49_GPT_GUARD_START',argv=argv)
    r=subprocess.run(argv,cwd=BASE.parents[1],capture_output=True,text=True,encoding='utf-8',timeout=120)
    guardout=BASE/'validation/final49_frozen_GPT_guard.txt'
    with guardout.open('x',encoding='utf-8') as f:f.write(r.stdout);f.write(r.stderr)
    audit.log('FINAL49_GPT_GUARD_END',returncode=r.returncode,output_sha256=audit.sha(guardout))
    assert r.returncode==0,r.stdout+r.stderr
    lock=read(BASE/'e49_driver/readiness_lock.json')
    for rel,h in lock['code_and_input_hashes'].items():assert audit.sha(BASE/rel)==h,rel
    for p,h in lock['context_source_hashes'].items():assert audit.sha(p)==h,p
    for p,h in lock['tool_hashes'].items():assert audit.sha(p)==h,p
    summary=read(BASE/'e49_driver/archive_final_v4/summary.json');assert summary['all49_complete']
    nchecks=0;paths=[]
    for i in range(1,50):
        p=BASE/f'e49_driver/archive_final_v4/{i:02}/manifest.json';m=read(p);assert m['job_index']==i
        for row in m['files']:
            for field in ['source','copy']:
                assert audit.sha(BASE/row[field])==row['sha256'],row[field];nchecks+=1
        paths.append(p)
    latest=read(REV/'output/release_manifest.json')
    for field in ['PDF','ZIP']:assert audit.sha(latest[field]['path'])==latest[field]['sha256']
    validation=read(REV/'final_validation.json');assert all(validation['controls'].values())
    stats=read(BASE/'outputs/e49_final_v2/statistics.json')
    assert stats['n']==49 and stats['GPT_API_calls']==0
    report={
        'status':'PASS_FOR_REVIEW_DRAFT','timestamp_utc':datetime.now(timezone.utc).isoformat(),
        'original_backup_pairs':585,'original_backup_match':True,'GPT_guard':'PASS',
        'code_input_context_tool_lock':'PASS','raw_source_archive_SHA_checks':nchecks,
        'E1_completed_slots':49,'E1_complete_suite_report_evidence':41,
        'manuscript_controls':'PASS','PDF_ZIP_hashes':'PASS','submission_ready':False,
        'scope':'Completed static artifacts; caches and mutable global ledgers excluded from file registry',
    }
    out=BASE/'validation/final49_release_verification_v1.json';dump(out,report);paths.append(out);paths.append(guardout)
    for rel in ['src','outputs/e49_final_v2']:
        paths.extend(p for p in (BASE/rel).rglob('*') if p.is_file())
    for p in REV.rglob('*'):
        if p.is_file() and p.relative_to(REV).parts[0] not in ['tectonic_cache','build_01','build_02']:paths.append(p)
    for name in ['BAO_CAO_CHOT_49_VA_KE_HOACH_CAMERA_READY.md','REVIEWER_TASK_MATRIX_FINAL49.md','PROTOCOL_CHAN_DOAN_E1_COMPATIBILITY.md']:
        paths.append(BASE/name)
    for rel in ['e49_driver/archive_final_v4/summary.json','e49_driver/results49.json','e49_driver/results49.csv','e49_driver/readiness_lock.json','e49_driver/postrun_v2/admission.json','e49_driver/postrun_v2/events.jsonl']:
        paths.append(BASE/rel)
    prior={}
    for e in audit.events():
        if e['kind']=='NEW_FILE_REGISTERED':prior[e['path'].replace('\\','/')]=e['sha256']
        elif e['kind']=='FILE_REVISION':prior[e['path'].replace('\\','/')]=e['after_sha256']
    records=[];pending=[]
    for p in sorted(set(paths)):
        rel=p.relative_to(BASE).as_posix();h=audit.sha(p)
        if rel in prior:assert prior[rel]==h,'Unrecorded edit: '+rel
        else:pending.append(('NEW_FILE_REGISTERED',dict(path=rel,sha256=h,bytes=p.stat().st_size,change_type='closed fixed49 analytic/manuscript artifact; original files untouched')))
        records.append({'path':rel,'sha256':h,'bytes':p.stat().st_size})
    audit._append_many(pending)
    manifest=BASE/'audit/final49_static_registry_v1.json'
    dump(manifest,{'timestamp_utc':datetime.now(timezone.utc).isoformat(),'files':records,'cache_or_live_global_ledger_included':False})
    audit.log('FINAL49_STATIC_ARTIFACTS_SEALED',files=len(records),new_registry_entries=len(pending),manifest=str(manifest.relative_to(BASE)),manifest_sha256=audit.sha(manifest),validation_sha256=audit.sha(out),submission_ready=False)
    audit.verify_chain()
    print(json.dumps({**report,'static_files_sealed':len(records),'new_registry_entries':len(pending),'audit_chain':'PASS'},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
