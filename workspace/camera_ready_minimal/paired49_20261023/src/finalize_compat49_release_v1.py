"""Read-only release verification and packaging of the existing final PDF; no experiments."""
import hashlib,json,re,subprocess,sys,zipfile
from pathlib import Path
from datetime import datetime,timezone
import fitz
B=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(B))
import audit
R=B/'manuscript_revision_v3_compat49'
S=R/'source'
D=R/'build_04'
O=R/'output'
V=B/'validation/camera_ready_compat49_release_v1'

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def relative(p): return Path(p).relative_to(B).as_posix()
def save(p,obj):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8',newline='\n') as f:
        json.dump(obj,f,ensure_ascii=False,indent=2);f.write('\n')
    audit.log('NEW_FILE_REGISTERED',path=relative(p),sha256=sha(p),bytes=p.stat().st_size,change_type='new isolated release evidence; original files untouched')
def save_text(p,text):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8',newline='\n') as f:f.write(text)
    audit.log('NEW_FILE_REGISTERED',path=relative(p),sha256=sha(p),bytes=p.stat().st_size,change_type='new isolated release document')

assert not V.exists() and not O.exists(), 'Refuse to overwrite any release output'
audit.log('NEW_FILE_REGISTERED',path=relative(__file__),sha256=sha(__file__),bytes=Path(__file__).stat().st_size,change_type='new isolated release verifier; no experiment code edits')
audit.verify()
guard=B.parents[1]/'review_reports/minimal_camera_ready_20261023/guard_rq123_frozen.py'
g=subprocess.run([sys.executable,'-B','-X','utf8',str(guard)],capture_output=True,text=True,encoding='utf-8',cwd=B)
assert g.returncode==0,(g.stdout,g.stderr)
gj=json.loads(g.stdout);assert gj['status']=='PASS'
V.mkdir()
save_text(V/'GPT_frozen_guard.txt',g.stdout)

# Validate immutable older registries and all raw artifacts from the final measurement.
old_counts={}
for name in ['final49_static_registry_v1.json','compatibility_15page_static_registry_v1.json']:
    obj=read(B/'audit'/name); rows=obj['files']
    for row in rows: assert sha(B/row['path'])==row['sha256'],row['path']
    old_counts[name]=len(rows)
man=read(B/'outputs/e49_measurement_compat_v1/output_manifest.json')
for p,h in man['inputs'].items(): assert sha(B/p)==h,p
for p,h in man['outputs'].items(): assert sha(B/'outputs/e49_measurement_compat_v1'/p)==h,p
rawfiles=0
for i in range(1,50):
    for row in read(B/f'e49_measurement_compat_v1/jobs/{i:02d}/artifact_manifest.json'):
        assert sha(B/row['path'])==row['sha256'],row['path'];rawfiles+=1
complete=read(B/'e49_measurement_compat_v1/complete.json')
assert complete['status']=='COMPLETE' and complete['n']==49
assert complete['GPT_API_calls']==complete['generation_calls']==0
assert sha(B/'e49_measurement_compat_v1/results49.json')==complete['results49_sha256']
ind=read(B/'validation/independent_compat49_raw_v1/audit.json')
late=read(B/'validation/independent_compat49_late_comparison_v1/report.json')
assert ind['status']=='PASS' and ind['exactly_one_measurement_per_job'] and ind['measurement_calls']==49
assert ind['G0_all49_unchanged'] and late['status']=='PASS'
assert late['comparison']['all20000_draws_match'] and late['comparison']['fixed49_rows_match']
for p,h in late['input_hashes'].items(): assert sha(B/p)==h,p
cache=read(B/'validation/critical_runtime_cache_final_v1/report.json')
assert cache['status']=='PASS' and cache['selected_current_files']==725 and not cache['missing_or_drifted']
st=read(B/'outputs/e49_measurement_compat_v1/statistics.json')
assert st['n']==49 and st['repositories']==15 and st['G0_minus_E2']['mean_pp']<0
assert st['G0_minus_E2']['G_higher']==14 and st['G0_minus_E2']['E_higher']==26 and st['G0_minus_E2']['ties']==9

# Bind the current source to its final build. Exactly six sections differ from closed v2.
summary=read(D/'build_summary.json')
source_hashes={p.relative_to(S).as_posix():sha(p) for p in sorted(S.rglob('*')) if p.is_file()}
normalized_inputs={k.replace('\\','/').replace('//','/'):v for k,v in summary['input_hashes'].items()}
assert normalized_inputs==source_hashes
initial=read(R/'source_copy_manifest.json')
changed=[]
for row in initial['files']:
    assert sha(B/'manuscript_revision_v2_15pages/source'/row['relative'])==row['sha256']
    if source_hashes[row['relative']]!=row['sha256']:changed.append(row['relative'])
allowed=['sections/00_abstract.tex','sections/03_method.tex','sections/04a_supplement.tex','sections/05_discussion.tex','sections/06_threats.tex','sections/07_conclusion.tex']
assert sorted(changed)==sorted(allowed),changed
assert sha(D/'main.pdf')=='b96c26add85f236a5c904d59a1211a3296e96e87be6d232d38b778d872501ecc'
log=(D/'main.log').read_text(encoding='utf-8',errors='replace')
severe=[l for l in log.splitlines() if re.search(r'Overfull|Missing character|LaTeX Warning:.*(?:undefined|multiply defined)|^!',l)]
assert not severe,severe
underfull=[l for l in log.splitlines() if 'Underfull' in l]
doc=fitz.open(D/'main.pdf');assert len(doc)==15
texts=[p.get_text() for p in doc];text='\n'.join(texts)
assert not any('\ufffd' in t or '??' in t for t in texts)
refpages=[i+1 for i,t in enumerate(texts) if re.search(r'^References$',t,re.M)]
assert refpages==[14],refpages
assert all(x in text for x in ['59.16','58.44','71.43','65.79','48/49','Corresponding authors: Truong Dan Huy and Le Thi Quynh Chi'])
assert re.search(r'[-\u2212]0\.72',text) and '-7.50' in text and '8.38' in text
main=(S/'main.tex').read_text(encoding='utf-8')
for name in ['Truong Dan Huy','Vuong Quoc Khanh','Tran Minh Quy','Le Tran Anh Khoa','Tran Bich Tram','Le Thi Quynh Chi']:assert name in main
assert 'no external funding and no conflicts of interest' in (S/'sections/08_disclosure.tex').read_text(encoding='utf-8')
assert not re.search(r'\bE2\b|compatibility_v\d|ABORT|parser amendment',text,re.I)

# Human full-size visual inspection was completed for build02 all pages, build03
# revised pages 1/11/13, and build04 revised page11. Check every unchanged PNG byte.
page_proof=[]
for i in range(1,16):
    name=f'page_{i:02d}.png'
    h2=sha(R/'build_02/rendered'/name);h3=sha(R/'build_03/rendered'/name);h4=sha(D/'rendered'/name)
    if i not in [1,11,13]:assert h2==h3
    if i!=11:assert h3==h4
    page_proof.append({'page':i,'final_PNG_sha256':h4,'visually_reviewed_build':'build_04' if i==11 else 'build_03' if i in [1,13] else 'build_02','byte_identical_to_reviewed_page':True})
qa={'status':'PASS','PDF_sha256':sha(D/'main.pdf'),'pages':15,'references_start_page':14,'references_end_page':15,'reviewer':'root agent, full-size rendered PNG inspection','renderer':'PyMuPDF fallback; Poppler unavailable on PATH','clipping_overlap_missing_glyphs_or_unreadable_tables':False,'page_proof':page_proof,'underfull_log_entries':underfull,'underfull_visual_disposition':'Reviewed; no visible defect. No overfull/missing-character/undefined-reference error found.'}
save(V/'visual_QA_final.json',qa)
validation={'status':'PASS','timestamp_utc':datetime.now(timezone.utc).isoformat(),'scope':'Verified fixed49 supplement and 15-page manuscript draft; not certification that every reviewer concern is closed','measurement_n':49,'measurement_calls':49,'new_generation_calls_in_final_measurement':0,'GPT_API_calls':0,'G0_all49_unchanged':True,'GPT_frozen_guard':gj,'protected_original_and_backup_pairs':585,'old_static_registries_verified':old_counts,'official_input_hashes_checked':len(man['inputs']),'official_output_hashes_checked':len(man['outputs']),'raw_artifact_files_rehashed':rawfiles,'independent_raw_audit':'PASS','independent_late_comparison_all20000_draws':'PASS','critical_cache_scope':'725 JAR/POM files in seven critical groups; prior final hash audit PASS, not whole-cache verification','allowed_changed_sections_vs_closed_v2':changed,'other_source_files_vs_closed_v2_unchanged':len(initial['files'])-len(changed),'RQ_definitions_and_historical_results_section_unchanged_vs_closed_v2':True,'source_hashes':source_hashes,'PDF_sha256':sha(D/'main.pdf'),'pages':15,'references_pages':[14,15],'visual_QA':'PASS','unresolved':['Artifact access URL not finalized','Repeated-run subset not executed','Practical validation of 5pp margin and pre-pilot analysis lock not established','Assertion-enabled measurement restricted to historical common-build49, not a new full300 baseline'],'no_new_Java_Maven_or_API_calls_by_this_verifier':True}
save(V/'final_validation.json',validation)

pdfout=O/'pdf/FISAT2026_revision_fixed49_15pages_draft.pdf'
pdfout.parent.mkdir(parents=True)
with pdfout.open('xb') as f:f.write((D/'main.pdf').read_bytes())
assert sha(pdfout)==qa['PDF_sha256']
audit.log('NEW_FILE_REGISTERED',path=relative(pdfout),sha256=sha(pdfout),bytes=pdfout.stat().st_size,change_type='byte-identical copy of visually verified PDF')
readme='''# FISAT2026 fixed49 revision - review draft\n\nThis source package contains the revised 15-page manuscript, including references on pages 14-15. It preserves the five research questions and archived GPT observations. E0 denotes the submitted structural EvoSuite configuration; E1 denotes the supplementary assertion-enabled configuration on the same fixed49 historical common-build keys. These are configurations under the original scoring convention.\n\nBuild from this directory with Tectonic 0.17.0:\n\n    tectonic --untrusted --keep-logs main.tex\n\nA populated Tectonic cache permits adding --only-cached. The supplied llncs.cls and splncs04.bst are retained. No font or page-margin reduction was introduced to meet the 15-page limit. The verified PDF is distributed separately.\n\nBefore submission, finalize the replication artifact access information. Repeated-run variance is not estimated by fixed49 measurement or repository bootstrap. The paper records the limits of the 5pp margin rationale, pilot-lock evidence, and the restricted supplementary cohort. This is a review draft, not a declaration that all reviewer concerns are fully resolved.\n\nAuthors: Truong Dan Huy; Vuong Quoc Khanh; Tran Minh Quy; Le Tran Anh Khoa; Tran Bich Tram; Le Thi Quynh Chi. All FPT University. Corresponding authors: Truong Dan Huy and Le Thi Quynh Chi. No external funding or conflicts of interest.\n\nThe package intentionally includes only manuscript build inputs and this README/source manifest. Experiment logs and replication materials are maintained separately.\n'''
save_text(O/'README.md',readme)
packaged={p:h for p,h in source_hashes.items() if not p.startswith('figures/_source_checks/')}
assert len(packaged)==15 and not re.search(r'\\includegraphics', ''.join(p.read_text(encoding='utf-8') for p in S.rglob('*.tex')))
save(O/'source_manifest.json',{'files':packaged,'PDF_sha256':qa['PDF_sha256'],'pages':15})
zpath=O/'FISAT2026_revision_fixed49_sources.zip'
with zipfile.ZipFile(zpath,'x',zipfile.ZIP_DEFLATED) as z:
    for p in sorted(packaged):z.write(S/p,p)
    z.write(O/'README.md','README.md');z.write(O/'source_manifest.json','source_manifest.json')
with zipfile.ZipFile(zpath) as z:
    assert len(z.namelist())==17 and z.testzip() is None
    for p,h in packaged.items():assert hashlib.sha256(z.read(p)).hexdigest()==h
    for p in ['README.md','source_manifest.json']:assert z.read(p)==(O/p).read_bytes()
audit.log('NEW_FILE_REGISTERED',path=relative(zpath),sha256=sha(zpath),bytes=zpath.stat().st_size,change_type='new manuscript source ZIP; verified members; no raw experiments or caches')
save(O/'release_manifest.json',{'status':'VERIFIED_REVIEW_DRAFT','created_utc':datetime.now(timezone.utc).isoformat(),'PDF':{'path':relative(pdfout),'sha256':sha(pdfout),'pages':15},'source_zip':{'path':relative(zpath),'sha256':sha(zpath),'members':17,'verified':True},'source_files':packaged,'validation':{relative(p):sha(p) for p in [V/'final_validation.json',V/'visual_QA_final.json',V/'GPT_frozen_guard.txt']},'artifact_URL_pending':True,'public_submission_performed':False})
print(json.dumps({'status':'PASS','pages':15,'raw_files_verified':rawfiles,'PDF':str(pdfout),'source_zip':str(zpath)},ensure_ascii=False,indent=2))
