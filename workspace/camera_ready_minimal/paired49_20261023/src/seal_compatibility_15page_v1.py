"""Seal completed diagnostics and the 15-page review draft; no experiment edits."""
import json,shutil,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));import audit
STAGE=BASE/'e1_compatibility_diagnostic_v1';REV=BASE/'manuscript_revision_v2_15pages'
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def dump(p,x):
    with p.open('x',encoding='utf-8') as f:json.dump(x,f,ensure_ascii=False,indent=2);f.write('\n')
def main():
    report=BASE/'BAO_CAO_CHAN_DOAN_COMPATIBILITY_E1.md';text=report.read_text(encoding='utf-8')
    assert text.count('-51 Maven')==1
    backup=BASE/'backup/report_list_spacing02'/report.name;backup.parent.mkdir(parents=True,exist_ok=False);before=audit.sha(report);shutil.copy2(report,backup)
    report.write_text(text.replace('-51 Maven','- 51 Maven'),encoding='utf-8')
    audit.log('FILE_REVISION',path=report.name,before_sha256=before,after_sha256=audit.sha(report),backup=backup.relative_to(BASE).as_posix(),reason='Correct Markdown bullet spacing; no result changes')
    audit.verify()
    guard=BASE.parents[1]/'review_reports/minimal_camera_ready_20261023/guard_rq123_frozen.py'
    r=subprocess.run([sys.executable,'-B','-X','utf8',str(guard)],cwd=BASE.parents[1],capture_output=True,text=True,encoding='utf-8',timeout=120)
    out=BASE/'validation/final_compatibility_GPT_guard.txt'
    with out.open('x',encoding='utf-8') as f:f.write(r.stdout+r.stderr)
    audit.log('FINAL_COMPATIBILITY_GPT_GUARD',returncode=r.returncode,output_sha256=audit.sha(out));assert r.returncode==0
    old=load(BASE/'audit/final49_static_registry_v1.json')
    for row in old['files']:assert audit.sha(BASE/row['path'])==row['sha256'],row['path']
    assert audit.sha(BASE/'e49_driver/results49.json')=='5a7873ed3600b60fb4dc27fccb65468c8f0a39f1c38a763cea8dd467f24c0dd9'
    guards=[]
    for p in sorted((STAGE/'original_guards').glob('*/result.json')):
        g=load(p);assert g['source_E1_job_file_bytes_and_membership_unchanged'] and not g['issues']
        assert load(p.parent/'before.json')==load(p.parent/'after.json')
        guards.append(p)
    assert len(guards)==16
    summary=load(STAGE/'diagnostic_summary.json');assert summary['Maven_commands']==51 and not summary['E1_or_GPT_scores_replaced']
    assert summary['GPT_API_calls']==summary['generation_calls']==summary['PIT_measurement_calls']==0
    for job,n in [('09',26),('12',17),('13',11),('14',15),('15',6),('18',2),('19',12)]:
        if job in ['18','19']:p=STAGE/'selector_correction_v1'/job/'result.json';row=load(p);assert row['strict_suite_pass']
        else:p=STAGE/'jobs'/job/'diagnostic_result.json';row=load(p);assert load(p.parent/'strict_acceptance.json')['XML_suite_and_case_checks_pass']
        assert len(row['testcases'])==n and len({x['name'] for x in row['testcases']})==n
        assert all(x['errors']+x['failures']+x['skipped']==0 for x in row['testcases'])
        assert not row['source_issues'] and not row['production_class_mismatches']
    runtime=load(STAGE/'jobs/48/runtime_full_result.json');assert sum(s['errors'] for s in runtime['XML_suites'])==4 and not runtime['selected_suite_all_methods_pass']
    for m in ['test0','test1','test2']:
        row=load(STAGE/'jobs/48'/('runtime_'+m+'_result.json'));assert row['selected_method_XML_pass'] and len(row['testcases'])==1
    release=load(REV/'output/release_manifest.json');assert audit.sha(release['PDF']['path'])==release['PDF']['sha256'] and release['PDF']['pages']==15
    assert audit.sha(release['ZIP']['path'])==release['ZIP']['sha256']
    final=load(REV/'final_validation.json');assert all(final['controls'].values())
    for rel,h in final['compiled_source_hashes'].items():assert audit.sha(REV/'source'/rel)==h
    verification={'status':'PASS','timestamp_utc':datetime.now(timezone.utc).isoformat(),'original_backup_pairs':585,'old_static_artifacts_unchanged':len(old['files']),'GPT_frozen_guard':'PASS','E1_results_hash_unchanged':True,'original_E1_guard_pairs':16,'guard_full_membership_byte_dictionaries_equal':True,'diagnostic_suite_pass':7,'fullsuite_runtime48_pass':False,'Maven_commands':51,'GPT_API_calls':0,'generation_calls':0,'PIT_measurement_calls':0,'PDF_total_pages':15,'authors':6,'corresponding_authors':2,'funding_COI_user_confirmed':True,'artifact_URL':'pending','new_full49_measurement_executed':False,'repeated_subset_executed':False,'submission_ready':False}
    vpath=BASE/'validation/final_compatibility_and_15page_verification.json';dump(vpath,verification)
    paths=[vpath,out,BASE/'src/seal_compatibility_15page_v1.py']
    for p in (BASE/'src').glob('*.py'):paths.append(p)
    for p in REV.rglob('*'):
        if p.is_file() and p.relative_to(REV).parts[0] not in ['tectonic_cache','build_01','build_02']:paths.append(p)
    for p in STAGE.rglob('*'):
        if not p.is_file():continue
        parts=p.relative_to(STAGE).parts
        if parts[0]=='maven_cache' or any(x in ['repo','temp'] for x in parts):continue
        paths.append(p)
    for name in ['BAO_CAO_CHAN_DOAN_COMPATIBILITY_E1.md','TRANG_THAI_MOI_NHAT_15TRANG_VA_RUNTIME.md','PROTOCOL_REPEATED_SUBSET_DE_XUAT.md','repeated_subset_selection_v1.json','PLAN_DO_LAI_49_SAU_COMPATIBILITY.md','KE_HOACH_DO_LAI_49_SUITE.md','validation/readable_diagnostic_report_text.md']:
        paths.append(BASE/name)
    prior={}
    for e in audit.events():
        if e['kind']=='NEW_FILE_REGISTERED':prior[e['path'].replace('\\','/')]=e['sha256']
        elif e['kind']=='FILE_REVISION':prior[e['path'].replace('\\','/')]=e['after_sha256']
    records=[];pending=[]
    for p in sorted(set(paths)):
        rel=p.relative_to(BASE).as_posix();h=audit.sha(p)
        if rel in prior:assert prior[rel]==h,'Unrecorded edit: '+rel
        else:pending.append(('NEW_FILE_REGISTERED',dict(path=rel,sha256=h,bytes=p.stat().st_size,change_type='closed compatibility diagnostic or15page review draft; no original edited')))
        records.append({'path':rel,'sha256':h,'bytes':p.stat().st_size})
    audit._append_many(pending)
    manifest=BASE/'audit/compatibility_15page_static_registry_v1.json'
    dump(manifest,{'files':records,'cache_or_working_repo_bytes_included':False,'note':'working repo content bound by input manifests, POMdiffs, locked bytecode comparisons, original job guards and independent audit; large caches excluded'})
    audit.log('COMPATIBILITY_AND_15PAGE_ARTIFACTS_SEALED',files=len(records),new_registry_entries=len(pending),manifest_sha256=audit.sha(manifest),verification_sha256=audit.sha(vpath),original_E1_GPT_unchanged=True,submission_ready=False)
    audit.verify_chain();print(json.dumps({**verification,'static_files_sealed':len(records),'new_registry_entries':len(pending),'audit_chain':'PASS'},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
