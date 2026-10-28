"""Package the reviewed private-availability revision without experimental artifacts."""
import hashlib,json,shutil,sys,zipfile
from pathlib import Path
B=Path(__file__).resolve().parents[1];sys.path.insert(0,str(B));import audit
R=B/'final_handoff_20261025_private';OLD=B/'final_handoff_20261024';S=R/'manuscript';V=R/'validation'
def dump(p,x):
 with p.open('x',encoding='utf-8') as f:json.dump(x,f,ensure_ascii=False,indent=2)
report=json.loads((V/'build_report.json').read_text());assert report['pages']==15 and report['changed_render_pages']==[14,15]
pdf=R/'FISAT2026_camera_ready_private.pdf';assert audit.sha(pdf)==audit.sha(S/'main.pdf')==report['PDF_sha256']
dump(V/'visual_QA.json',{'status':'PASS','pages':15,'full_size_visual_review':[14,15],'other13_rendered_pages_byte_identical_to_previously_reviewed_final':True,'no_observed_clipping_overlap_or_missing_glyphs':True,'PDF_sha256':audit.sha(pdf)})
check=R/'CHECKLIST_CONFY.md';before=check.read_text(encoding='utf-8');backup=R/'backup/CHECKLIST_before_filename_update.md';shutil.copy2(check,backup)
check.write_text(before.replace('FISAT2026_camera_ready_final.pdf','FISAT2026_camera_ready_private.pdf'),encoding='utf-8')
audit.log('FILE_REVISION',path=check.relative_to(B).as_posix(),before_sha256=audit.sha(backup),after_sha256=audit.sha(check),backup=backup.relative_to(B).as_posix(),reason='Match final private-availability PDF filename')
shutil.copy2(OLD/'REVIEWER_STATUS.json',R/'REVIEWER_STATUS.json')
manifest={'files':{p.relative_to(S).as_posix():audit.sha(p) for p in sorted(S.rglob('*')) if p.is_file()},'PDF_member':'main.pdf','PDF_sha256':audit.sha(pdf),'pages':15,'contains_experimental_code':False}
dump(S/'SOURCE_MANIFEST.json',manifest)
zpath=R/'FISAT2026_manuscript_source.zip';members=sorted(p for p in S.rglob('*') if p.is_file());assert len(members)==18
assert all(p.suffix in ['.pdf','.tex','.bib','.cls','.bst','.md','.json'] for p in members)
with zipfile.ZipFile(zpath,'x',zipfile.ZIP_DEFLATED) as z:
 for p in members:z.write(p,p.relative_to(S).as_posix())
with zipfile.ZipFile(zpath) as z:
 assert z.testzip() is None and len(z.namelist())==18
 for p in members:assert hashlib.sha256(z.read(p.relative_to(S).as_posix())).hexdigest()==audit.sha(p)
 assert hashlib.sha256(z.read('main.pdf')).hexdigest()==audit.sha(pdf)
for row in json.loads((OLD/'RELEASE_MANIFEST.json').read_text())['files']:assert audit.sha(OLD/row['path'])==row['sha256'],row['path']
audit.verify()
outputs=[pdf,zpath,R/'RESPONSE_TO_REVIEWERS.md',check,R/'REVIEWER_STATUS.json']
release={'status':'VERIFIED_PRIVATE_AVAILABILITY_REVISION','supersedes_manuscript_in':'../final_handoff_20261024','pages':15,'only_changed_manuscript_source':'sections/08_disclosure.tex','other14_manuscript_sources_unchanged':True,'original_availability_phrase':'replication package withheld for double-blind review; submitted as supplementary material','public_code_release_authorized':False,'experimental_artifact_included':False,'existing_experimental_artifacts_preserved_locally':True,'new_API_or_experimental_jobs':0,'uploaded':False,'actual_supplementary_receipt_independently_verified':False,'visual_QA':'PASS','ZIP_members':18,'PDF_inside_ZIP_identical_to_delivered_PDF':True,'files':[{'path':p.relative_to(R).as_posix(),'sha256':audit.sha(p),'bytes':p.stat().st_size} for p in outputs]}
dump(R/'RELEASE_MANIFEST.json',release)
(R/'SHA256SUMS.txt').write_text(''.join(x['sha256']+'  '+x['path']+'\n' for x in release['files'])+audit.sha(R/'RELEASE_MANIFEST.json')+'  RELEASE_MANIFEST.json\n')
audit.log('PRIVATE_AVAILABILITY_RELEASE',manifest_sha256=audit.sha(R/'RELEASE_MANIFEST.json'),PDF_sha256=audit.sha(pdf),ZIP_sha256=audit.sha(zpath),public_code_release_authorized=False)
print(json.dumps({'status':release['status'],'pages':15,'ZIP_members':18,'PDF_sha256':audit.sha(pdf),'experimental_code_included':False},indent=2))
