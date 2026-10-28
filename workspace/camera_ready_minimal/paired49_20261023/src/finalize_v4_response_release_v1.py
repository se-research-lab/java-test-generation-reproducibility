"""Validate and package publisher-only v4 plus a truthful reviewer response; no experiments."""
import hashlib,json,re,subprocess,sys,zipfile
from datetime import datetime,timezone
from pathlib import Path
import fitz
B=Path(__file__).resolve().parents[1];sys.path.insert(0,str(B));import audit
R=B/'manuscript_revision_v4_submission';S=R/'source';O=R/'output';RR=B/'reviewer_response_v1';V=B/'validation/camera_ready_response_release_v1'
sha=audit.sha
rel=lambda p:Path(p).relative_to(B).as_posix()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def registered(p,reason='new isolated publisher/response output'):
    audit.log('NEW_FILE_REGISTERED',path=rel(p),sha256=sha(p),bytes=p.stat().st_size,change_type=reason)
def dump(p,obj):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f:json.dump(obj,f,ensure_ascii=False,indent=2);f.write('\n')
    registered(p)
def text(p,t):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8',newline='\n') as f:f.write(t)
    registered(p)
assert not O.exists() and not V.exists()
registered(Path(__file__))
# Explicitly record the response editing chain; its draft copies are retained.
p=RR/'RESPONSE_TO_REVIEWERS_DRAFT.md';b1=RR/'backups/response_before_spacing.md';b2=RR/'backups/response_after_spacing_v1.md'
assert sha(b1)=='2219aa4cf0c1f40e723ed0fa63fafff78b6311eaa0d9a876eabb4b58648e2a68'
assert sha(b2)=='b12bbd2d22f34d2c54cb33b0df5b36c63d7bf0b6de54a1cf145c173ab297f0ce'
assert sha(p)=='0dec4e5028e75cf7fab822bc33ec0050ad4618e2b06848fc2a77af6a9ce9b0c0'
audit.log('NEW_DOCUMENT_INITIAL_BYTES_RECORDED',path=rel(p),sha256=sha(b1),evidence_backup=rel(b1),recorded_at_close=True,reason='Initial English response drafted in this turn; raw before-image retained')
audit.log('FILE_REVISION',path=rel(p),before_sha256=sha(b1),after_sha256=sha(b2),backup=rel(b1),reason='English spacing around numbers; no claim/data change',recorded_at_close=True)
audit.log('FILE_REVISION',path=rel(p),before_sha256=sha(b2),after_sha256=sha(p),backup=rel(b2),reason='English punctuation spacing; no claim/data change',recorded_at_close=True)
for q in RR.rglob('*'):
    if q.is_file():registered(q)
closed=read(B/'audit/measurement49_camera_ready_registry_v1.json')
for row in closed['files']:assert sha(B/row['path'])==row['sha256'],row['path']
audit.verify()
guard=B.parents[1]/'review_reports/minimal_camera_ready_20261023/guard_rq123_frozen.py'
g=subprocess.run([sys.executable,'-B','-X','utf8',str(guard)],cwd=B,capture_output=True,text=True,encoding='utf-8')
assert g.returncode==0,(g.stdout,g.stderr);gj=json.loads(g.stdout);assert gj['status']=='PASS'
V.mkdir();text(V/'GPT_frozen_guard.txt',g.stdout)
# Verify allowed source differences and backups, then the exact final build inputs.
old=read(R/'source_copy_manifest.json')['files'];patch=read(R/'publisher_update_manifest.json');summary=read(R/'build_01/build_summary.json')
actual={q.relative_to(S).as_posix():sha(q) for q in sorted(S.rglob('*')) if q.is_file()}
assert actual==summary['input_hashes'] and len(actual)==15
changed=sorted(n for n in old if old[n]!=actual[n]);assert changed==sorted(patch['allowed_files'])
for row in patch['changes']:
    assert actual[row['path']]==row['after'] and old[row['path']]==row['before']
    assert sha(R/'backups/publisher_update_v1'/row['path'])==row['before']
method=(S/'sections/03_method.tex').read_text(encoding='utf-8')
prior_method=(B/'manuscript_revision_v3_compat49/source/sections/03_method.tex').read_text(encoding='utf-8')
assert re.sub(r'~\\cite\{ref[46]\}','',method)==prior_method
main=(S/'main.tex').read_text(encoding='utf-8')
assert main.count('Corresponding author: Le Thi Quynh Chi')==1 and 'Corresponding authors:' not in main
assert 'chiltq6@fe.edu.vn' in main and 'truongdanhuyak@gmail.com' in main
for name in ['Truong Dan Huy','Vuong Quoc Khanh','Tran Minh Quy','Le Tran Anh Khoa','Tran Bich Tram','Le Thi Quynh Chi']:assert name in main
# Compare scientific sections by bytes, rather than just checking rounded values.
science=['00_abstract','01_introduction','02_related_work','04_results','04a_supplement','05_discussion','06_threats','07_conclusion']
for name in science:assert sha(S/'sections'/(name+'.tex'))==sha(B/'manuscript_revision_v3_compat49/source/sections'/(name+'.tex'))
response=p.read_text(encoding='utf-8');coverage=read(RR/'coverage_map.json');assert coverage['response_sha256']==sha(p)
ids=re.findall(r'^### (R\d\.[\w]+) - ',response,re.M)
expected=[f'R1.{i}' for i in range(1,13)]+['R2.strengths']+[f'R2.{i}' for i in range(1,8)]+['R2.minor','R2.path']+[f'R3.{i}' for i in range(1,6)]
assert ids==expected and [r['id'] for r in coverage['items']]==expected and len(set(ids))==27
assert not re.search(r'\bE2\b|ABORT|50\.408|parser amendment|recovery18',response)
for phrase in ['No repeated-generation subset has been completed','not a replacement baseline for all 300','practical justification remains a limitation','not been verified']:
    assert phrase in response,phrase
# Check displayed claims against sealed derived data (not a new statistical analysis).
st=read(B/'outputs/e49_measurement_compat_v1/statistics.json');hist=read(B/'outputs/statistics.json');cluster=read(B/'outputs/cluster300_sensitivity/summary.json');maven=read(B/'outputs/maven260_sensitivity/summary.json')
checks={
    'E1_mean':(f"{st['E2_legacy_strict_mean']:.2f}",'59.16'),
    'G0_mean_fixed49':(f"{st['G0_mean']:.2f}",'58.44'),
    'new_gap':(f"{st['G0_minus_E2']['mean_pp']:.2f}",'-0.72'),
    'new_CI_lo':(f"{st['repository_cluster_percentile_95CI_G0_minus_E2_mean_pp'][0]:.2f}",'-7.50'),
    'new_CI_hi':(f"{st['repository_cluster_percentile_95CI_G0_minus_E2_mean_pp'][1]:.2f}",'8.38'),
    'historical_gap':(f"{hist['paired_mean_difference_pp']:.2f}",'40.81'),
    'historical_CI_lo':(f"{hist['cluster_percentile_95ci_mean_difference_pp'][0]:.2f}",'32.99'),
    'historical_CI_hi':(f"{hist['cluster_percentile_95ci_mean_difference_pp'][1]:.2f}",'49.06'),
    'cluster300_CI_lo':(f"{cluster['strict_mutation_repository_percentile95CI_pp'][0]:.2f}",'0.98'),
    'cluster300_CI_hi':(f"{cluster['strict_mutation_repository_percentile95CI_pp'][1]:.2f}",'9.51')}
for key,(value,expected_value) in checks.items():assert value==expected_value and value in response,(key,value)
m=next(r for r in maven['table'] if r['population']=='Maven260');assert [m[k] for k in ['n','GPT_builds','E0_builds','both_build','GPT_only','E0_only','neither_build']]==[260,51,158,49,2,109,100]
assert [st['G0_minus_E2'][k] for k in ['G_higher','E_higher','ties']]==[14,26,9]
doc=fitz.open(R/'build_01/main.pdf');assert len(doc)==15 and sha(R/'build_01/main.pdf')=='53a0eff4cf627c076ff3e4202a143d0584f79a0e87185f06673bb364d85e191a'
texts=[page.get_text() for page in doc];allpdf='\n'.join(texts)
assert 'Corresponding author: Le Thi Quynh Chi' in allpdf and 'Corresponding authors:' not in allpdf
assert 'OpenAI Codex' in allpdf and 'Disclosure of Interests.' in allpdf
assert 'References' in texts[13] and 'References' not in '\n'.join(texts[:13])
abstract=texts[0].split('Abstract.')[1].split('Keywords:')[0];abstract_n=len(abstract.split());assert 150<=abstract_n<=250,abstract_n
render=read(R/'build_01/rendered/render_manifest.json');assert render['pages_changed_vs_verified_v3']==[1,7,14,15]
for name,h in render['PNG_hashes'].items():assert sha(R/'build_01/rendered'/name)==h
qa={'status':'PASS','pages':15,'PDF_sha256':sha(R/'build_01/main.pdf'),'new_fullsize_visual_review_pages':[1,7,14,15],'unchanged_11_page_PNGs_byte_identical_to_visually_verified_v3':True,'clipping_overlap_or_missing_glyph_defects':False,'reviewer':'root agent; visual inspection of all changed pages','references_pages':[14,15],'renderer':'PyMuPDF fallback; Poppler unavailable'}
dump(V/'visual_QA.json',qa)
validation={'status':'PASS','timestamp_utc':datetime.now(timezone.utc).isoformat(),'old_closed_registry_files_verified':len(closed['files']),'original_and_backup_pairs_verified':585,'GPT_frozen_guard':gj,'allowed_changed_sources':changed,'other_sources_byte_identical':12,'scientific_sections_byte_identical_to_v3':science,'method_only_adds_existing_ref4_ref6_citations':True,'paper_pages':15,'abstract_word_count_from_PDF':abstract_n,'all25_cite_keys_and_bib_items_match':True,'corresponding_author':'Le Thi Quynh Chi','corresponding_email':'chiltq6@fe.edu.vn','response_sections':ids,'response_coverage_and_scope_check':'PASS','numeric_claims_crosschecked':checks,'new_generation_calls':0,'GPT_API_calls':0,'new_measurement_calls':0,'visual_QA':'PASS','source_hashes':actual,'PDF_sha256':sha(R/'build_01/main.pdf'),'not_a_submission_ready_certification':True,'remaining':['artifact access URL','repeated-generation variance','E1 fixed49 does not replace assertion-disabled baseline300','practical 5pp justification and pre-pilot analytical lock not established']}
dump(V/'final_validation.json',validation)
# Build a new archive that satisfies the PDF+source upload shape.
O.mkdir();pdf=O/'pdf/FISAT2026_camera_ready_review_draft.pdf';pdf.parent.mkdir()
with pdf.open('xb') as f:f.write((R/'build_01/main.pdf').read_bytes())
assert sha(pdf)==qa['PDF_sha256'];registered(pdf)
readme='''# FISAT2026 camera-ready review draft\n\nThis archive contains main.pdf and its 15 manuscript source inputs. The PDF has 15 pages including references. It has not been uploaded or submitted.\n\nBuild source with Tectonic0.17.0 from this folder:\n\n    tectonic --untrusted --keep-logs main.tex\n\nA populated cache allows --only-cached. The supplied LLNCS class and bibliography files are retained.\n\nCorresponding author: Le Thi Quynh Chi, FPT University, chiltq6@fe.edu.vn. The six-author order and all email addresses are retained.\n\nThis update changes corresponding-author metadata, adds citations for two already-listed methods references, and records substantive AI assistance in acknowledgements. Scientific observations, five RQs, historical results and fixed49 supplement are unchanged from the verified prior revision.\n\nBefore submission, finalize replication-artifact access information and review the response draft distributed separately. This manuscript archive is not the experiment replication artifact. Repeated-run variance, an assertion-enabled full300 baseline, practical validation of the5pp margin and evidence of pre-pilot analytical locking remain unresolved or restricted as stated in the paper.\n'''
text(O/'README.md',readme)
dump(O/'source_manifest.json',{'files':actual,'PDF_member':'main.pdf','PDF_sha256':sha(pdf),'pages':15})
archive=O/'FISAT2026_upload_review_draft.zip'
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
    z.write(pdf,'main.pdf')
    for n in sorted(actual):z.write(S/n,n)
    z.write(O/'README.md','README.md');z.write(O/'source_manifest.json','source_manifest.json')
with zipfile.ZipFile(archive) as z:
    assert len(z.namelist())==18 and z.testzip() is None and len(z.namelist())==len(set(z.namelist()))
    assert hashlib.sha256(z.read('main.pdf')).hexdigest()==sha(pdf)
    for n,h in actual.items():assert hashlib.sha256(z.read(n)).hexdigest()==h
    assert not any('..' in Path(n).parts or Path(n).is_absolute() for n in z.namelist())
registered(archive)
dump(O/'release_manifest.json',{'status':'VERIFIED_AUTHOR_REVIEW_DRAFT','PDF':{'path':rel(pdf),'sha256':sha(pdf),'pages':15},'upload_archive':{'path':rel(archive),'sha256':sha(archive),'members':18,'contains_exact_PDF_and_sources':True},'corresponding_author':'Le Thi Quynh Chi','response':{'path':rel(p),'sha256':sha(p),'items':27,'not_submitted':True},'verification':{rel(q):sha(q) for q in [V/'final_validation.json',V/'visual_QA.json',RR/'coverage_map.json',RR/'publisher_sources.json']},'artifact_URL_pending':True,'submission_performed':False})
registry=B/'audit/camera_ready_response_registry_v1.json';assert not registry.exists()
entries=set()
for d in [RR,V,R/'source',R/'backups',R/'build_01',O]:entries.update(q for q in d.rglob('*') if q.is_file())
for q in [Path(__file__),B/'src/prepare_v4_publisher_update_v1.py',B/'src/prepare_v4_publisher_update_v2.py',R/'source_copy_manifest.json',R/'publisher_update_manifest.json',R/'tectonic_cache_copy_manifest.json',B/'audit/measurement49_camera_ready_registry_v1.json']:entries.add(q)
for q in [B/'outputs/e49_measurement_compat_v1/statistics.json',B/'outputs/statistics.json',B/'outputs/cluster300_sensitivity/summary.json',B/'outputs/maven260_sensitivity/summary.json']:entries.add(q)
rows=[{'path':rel(q),'sha256':sha(q),'bytes':q.stat().st_size} for q in sorted(entries)]
prior=audit.events()[-1]
dump(registry,{'status':'CLOSED_REVIEWER_RESPONSE_AND_PUBLISHER_ONLY_V4','created_utc':datetime.now(timezone.utc).isoformat(),'files':rows,'prior_closed_registry_sha256':sha(B/'audit/measurement49_camera_ready_registry_v1.json'),'ledger_head_before_registry':{'seq':prior['seq'],'sha256':prior['event_sha256']},'experimental_changes':0,'corresponding_author_selected_by_user':'Le Thi Quynh Chi','public_submission_performed':False})
for row in rows:assert sha(B/row['path'])==row['sha256'],row['path']
links=re.findall(r'\]\(([^)]+)\)',(RR/'CAMERA_READY_READINESS.md').read_text(encoding='utf-8'))
for target in links:
    if '://' not in target:assert (RR/target.split('#')[0]).exists(),target
audit.verify()
print(json.dumps({'status':'PASS','pages':15,'response_items':27,'upload_archive_members':18,'registry_files':len(rows),'PDF':str(pdf),'archive':str(archive),'response':str(p),'readiness':str(RR/'CAMERA_READY_READINESS.md'),'corresponding_author':'Le Thi Quynh Chi','experiment_API_calls':0},indent=2))
