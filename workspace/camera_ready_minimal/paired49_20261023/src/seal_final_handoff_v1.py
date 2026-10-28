"""Seal local handoff after review. Only offline analytics and TeX compilation."""
import hashlib,json,os,re,shutil,subprocess,sys,zipfile
from pathlib import Path
from datetime import datetime,timezone
from dotenv import dotenv_values
import fitz
B=Path(__file__).resolve().parents[1];sys.path.insert(0,str(B));import audit
H=B/'final_handoff_20261024';A=H/'artifact';S=H/'manuscript';V=H/'validation'
def dump(p,obj):
 with p.open('x',encoding='utf-8') as f:json.dump(obj,f,ensure_ascii=False,indent=2)
def run(name,args,cwd,env=None):
 r=subprocess.run(list(map(str,args)),cwd=cwd,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=300)
 (V/(name+'.stdout.txt')).write_text(r.stdout,encoding='utf-8');(V/(name+'.stderr.txt')).write_text(r.stderr,encoding='utf-8');assert r.returncode==0,(name,r.stderr);return r
def archive(folder,dest):
 paths=sorted(p for p in folder.rglob('*') if p.is_file())
 with zipfile.ZipFile(dest,'x',zipfile.ZIP_DEFLATED) as z:
  for p in paths:z.write(p,p.relative_to(folder).as_posix())
 with zipfile.ZipFile(dest) as z:
  assert z.testzip() is None and len(z.namelist())==len(paths)
  for p in paths:assert hashlib.sha256(z.read(p.relative_to(folder).as_posix())).hexdigest()==audit.sha(p)
 return len(paths)
accepted=json.loads((V/'artifact_analytics_check.json').read_text());assert accepted['status']=='PASS'
# Verify official conference-linked template, not an inferred replacement template.
official=V/'official_Springer_Latex_Template.zip'
with zipfile.ZipFile(official) as z:
 template={}
 for name in ['llncs.cls','splncs04.bst']:
  matches=[n for n in z.namelist() if n.rsplit('/',1)[-1]==name];assert len(matches)==1
  h=hashlib.sha256(z.read(matches[0])).hexdigest();assert h==audit.sha(S/name),name;template[name]=h
dump(V/'official_template_check.json',{'status':'PASS','download_url':'https://help.eai-conferences.org/wp-content/uploads/sites/88/2021/04/Springer_Latex_Template.zip','archive_sha256':audit.sha(official),'matching_files':template})
pdf=H/'FISAT2026_camera_ready_final.pdf';assert audit.sha(pdf)==audit.sha(S/'main.pdf')
doc=fitz.open(pdf);assert len(doc)==15
alltext=' '.join(p.get_text() for p in doc);assert 'Corresponding author: Le Thi Quynh Chi' in alltext
assert all(name in alltext for name in ['Truong Dan Huy','Vuong Quoc Khanh','Tran Minh Quy','Le Tran Anh Khoa','Tran Bich Tram','Le Thi Quynh Chi'])
assert 'No complete repeated' in alltext and 'prespecified n' not in alltext
assert '45 GPT and 134 E0' in alltext and '61 and 158' in alltext
source_intro=S/'sections/01_introduction.tex';assert audit.sha(source_intro)==audit.sha(B/'manuscript_revision_v5_disclosure/source/sections/01_introduction.tex')
dump(V/'visual_QA.json',{'status':'PASS','pages':15,'review':'All15 v6 rendered pages reviewed; pages1/9/10/11/13 inspected at full image size; final clean-build page11 re-inspected, other14 final PNG hashes equal reviewed v6','no_observed_clipping_overlap_missing_glyphs':True,'PDF_sha256':audit.sha(pdf),'references_pages':[14,15],'tables_editable_text':True})
sourcehashes={p.relative_to(S).as_posix():audit.sha(p) for p in sorted(S.rglob('*')) if p.is_file()}
dump(S/'SOURCE_MANIFEST.json',{'files':sourcehashes,'PDF':'main.pdf','PDF_sha256':audit.sha(pdf),'pages':15})
sz=H/'FISAT2026_manuscript_source.zip';sn=archive(S,sz)
extract=V/'extracted_manuscript';extract.mkdir()
with zipfile.ZipFile(sz) as z:z.extractall(extract)
for n,h in sourcehashes.items():assert audit.sha(extract/n)==h
# Rebuild the actual extracted archive, fresh output, existing dependency cache only.
D=V/'extracted_clean_build';D.mkdir();env=dict(os.environ);env['TECTONIC_CACHE_DIR']=str(B/'manuscript_revision_v6_final/tectonic_cache')
tool=B/'tools/tectonic-0.17.0-x86_64-pc-windows-msvc/tectonic.exe'
run('extracted_source_build',[tool,'--only-cached','--untrusted','--keep-logs','--outdir',D,extract/'main.tex'],extract,env)
rebuilt=fitz.open(D/'main.pdf');assert len(rebuilt)==15
render_equal=[]
for i,p in enumerate(rebuilt):
 pix=p.get_pixmap(matrix=fitz.Matrix(1.8,1.8),alpha=False)
 original=doc[i].get_pixmap(matrix=fitz.Matrix(1.8,1.8),alpha=False)
 assert pix.samples==original.samples,i+1;render_equal.append(i+1)
dump(V/'extracted_source_build_check.json',{'status':'PASS','pages':15,'archive_member_PDF_matches_delivered':True,'source_hashes_match':True,'all_page_pixels_match':render_equal,'rebuilt_PDF_byte_identical':audit.sha(D/'main.pdf')==audit.sha(pdf),'output_directory_started_empty':True})
# Recheck secrets after the final offline checker revision; do not record values.
secrets=[str(v).encode() for k,v in dotenv_values(audit.ROOT/'scripts_v2/.env').items() if v and len(str(v))>=12 and re.search(r'KEY|TOKEN|SECRET|PASSWORD',k,re.I)]
patterns=[rb'sk-(?:proj-)?[A-Za-z0-9_-]{24,}',rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',rb'gh[pousr]_[A-Za-z0-9]{30,}',rb'AKIA[0-9A-Z]{16}',rb'(?i)Authorization\s*[:=]\s*[\"\x27]?Bearer\s+[A-Za-z0-9._-]{20,}']
findings=[]
for folder in [A,S]:
 for p in folder.rglob('*'):
  if not p.is_file():continue
  data=p.read_bytes()
  if p.name=='.env' or any(v in data for v in secrets) or any(re.search(pat,data) for pat in patterns):findings.append(p.relative_to(H).as_posix())
assert not findings,findings
dump(V/'final_secret_scan.json',{'status':'PASS','known_secret_values_checked':len(secrets),'pattern_classes':len(patterns),'findings':[],'scope':'final artifact and manuscript including manifests','limit':'Known values and selected signatures; not universal secret detection'})
az=H/'FISAT2026_experiment_artifact.zip';an=archive(A,az)
# Test the analysis command from the exact extracted deliverable, not only staging.
ae=V/'extracted_artifact';ae.mkdir()
with zipfile.ZipFile(az) as z:z.extractall(ae)
run('extracted_artifact_analytics',[sys.executable,'-B','-X','utf8',ae/'reproduce_analytics.py','--out',V/'extracted_artifact_check.json'],ae)
assert json.loads((V/'extracted_artifact_check.json').read_text())['status']=='PASS'
guard=audit.ROOT/'review_reports/minimal_camera_ready_20261023/guard_rq123_frozen.py'
g=run('GPT_frozen_guard',[sys.executable,'-B','-X','utf8',guard],B);assert json.loads(g.stdout)['status']=='PASS'
audit.verify()
for reg in ['measurement49_camera_ready_registry_v1.json','camera_ready_response_registry_v1.json','disclosure_only_registry_v1.json']:
 for x in json.loads((B/'audit'/reg).read_text())['files']:assert audit.sha(B/x['path'])==x['sha256'],x['path']
stop=json.loads((B/'repeated_subset_v1/STOP_DO_NOT_RESUME.json').read_text());snapshot=json.loads((B/'repeated_subset_v1/stop_snapshot_manifest_v1.json').read_text())
for x in snapshot['files']:assert audit.sha(B/'repeated_subset_v1'/x['path'])==x['sha256'],x['path']
dump(V/'stopped_repeat_preservation_check.json',{'status':'PASS','snapshot_files_unchanged':len(snapshot['files']),'successful_API_responses_preserved':stop['successful_responses'],'estimated_usage_cost_USD':stop['estimated_usage_cost_USD'],'repeated_results_used':False,'resume_authorized':False})
files=[pdf,sz,az,H/'RESPONSE_TO_REVIEWERS.md',H/'CHECKLIST_CONFY.md',H/'QUYET_DINH_PHAM_VI_E49.md',H/'REVIEWER_STATUS.json']
release={'status':'VERIFIED_LOCAL_HANDOFF_AUTHOR_ACTIONS_PENDING','created_utc':datetime.now(timezone.utc).isoformat(),'pages_including_references':15,'corresponding_author':'Le Thi Quynh Chi','authors':6,'RQ_count':5,'GPT_cohorts':[61,45,300],'E0_full_sample':300,'E1_supplement':49,'repeated_evaluation_complete':False,'repeated_results_in_manuscript_or_artifact':False,'new_experimental_API_Java_jobs_in_finalization':0,'manuscript_zip_members':sn,'artifact_zip_members':an,'files':[{'path':p.relative_to(H).as_posix(),'bytes':p.stat().st_size,'sha256':audit.sha(p)} for p in files],'validation':{p.name:audit.sha(p) for p in V.glob('*.json')},'author_actions_pending':['artifact public URL/DOI and license','author approval and actual AI-policy disclosure decision','track/deadline confirmation','registration/payment confirmation','license-to-publish signature','Confy+ upload and receipt'],'uploaded':False,'registration_confirmed':False,'license_signed_by_agent':False}
dump(H/'RELEASE_MANIFEST.json',release)
(H/'SHA256SUMS.txt').write_text(''.join(x['sha256']+'  '+x['path']+'\n' for x in release['files'])+audit.sha(H/'RELEASE_MANIFEST.json')+'  RELEASE_MANIFEST.json\n')
audit.log('FINAL_LOCAL_HANDOFF_SEALED',release_sha256=audit.sha(H/'RELEASE_MANIFEST.json'),PDF_sha256=audit.sha(pdf),manuscript_zip_sha256=audit.sha(sz),artifact_zip_sha256=audit.sha(az),author_actions_pending=True)
print(json.dumps({'status':release['status'],'pages':15,'manuscript_zip_members':sn,'artifact_zip_members':an,'PDF_sha256':audit.sha(pdf),'zip_sizes_MB':[sz.stat().st_size/1e6,az.stat().st_size/1e6]},indent=2))
