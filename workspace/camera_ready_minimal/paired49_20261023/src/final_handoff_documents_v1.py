"""Prepare reviewer response and clean manuscript build; no experimental execution."""
import sys,json,shutil,subprocess,os,re,difflib
from pathlib import Path
import fitz
B=Path(__file__).resolve().parents[1];sys.path.insert(0,str(B));import audit
H=B/'final_handoff_20261024';R=B/'manuscript_revision_v6_final';S=H/'manuscript';V=H/'validation'
assert not S.exists();V.mkdir(exist_ok=True);shutil.copytree(R/'source',S)
p=S/'sections/04a_supplement.tex';old=p.read_text();new=old.replace('Each class uses one generation attempt with its scheduled seed;','Each class contributes one scheduled generation run;');assert new!=old
backup=H/'internal_backups/04a_supplement_before_run_wording.tex';shutil.copy2(p,backup);p.write_text(new,encoding='utf-8')
audit.log('FILE_REVISION',path=p.relative_to(B).as_posix(),before_sha256=audit.sha(backup),after_sha256=audit.sha(p),backup=backup.relative_to(B).as_posix(),reason='One scheduled run permits the documented conditional same-seed technical retry; no repeated-run evaluation implied')
readme='''# Manuscript source

This directory contains the final 15-page manuscript, including references. main.pdf is the exact PDF supplied separately. Six authors are listed in the agreed order. Le Thi Quynh Chi is the sole corresponding author.

Build from this directory with Tectonic 0.17.0:

    tectonic --untrusted --keep-logs main.tex

Or, with a populated Tectonic cache:

    tectonic --only-cached --untrusted --keep-logs main.tex

All manuscript inputs are included: main.tex, sections/*.tex, references.tex (the bibliography actually used), references.bib, llncs.cls and splncs04.bst. No external image files are required. TeX packages/fonts are engine dependencies, not manuscript sources; a fresh Tectonic installation needs its normal bundle download or a populated cache. A clean-output offline build was validated during handoff. Check validation in the parent handoff for hashes and render evidence. Do not combine these sources with previous drafts.

Public artifact access is not yet finalized. The experiment artifact and response are separate files. No upload, registration, payment or license signature has been performed by this workflow.
'''
(S/'README.md').write_text(readme,encoding='utf-8')
tool=B/'tools/tectonic-0.17.0-x86_64-pc-windows-msvc/tectonic.exe';D=V/'clean_build';D.mkdir();env=dict(os.environ);env['TECTONIC_CACHE_DIR']=str(R/'tectonic_cache')
argv=[str(tool),'--only-cached','--untrusted','--keep-logs','--keep-intermediates','--outdir',str(D),str(S/'main.tex')]
r=subprocess.run(argv,cwd=S,env=env,capture_output=True,text=True,errors='replace',timeout=300)
(D/'stdout.txt').write_text(r.stdout);(D/'stderr.txt').write_text(r.stderr);assert r.returncode==0,r.stderr
doc=fitz.open(D/'main.pdf');assert len(doc)==15
texts=[p.get_text() for p in doc];whole='\n'.join(texts);assert '??' not in whole and 'Corresponding author: Le Thi Quynh Chi' in whole
log=(D/'main.log').read_text(errors='replace');bad=[l for l in log.splitlines() if re.search(r'Overfull|Missing character|LaTeX Warning:.*(?:undefined|multiply defined)|^!',l)];assert not bad,bad
render=D/'rendered';render.mkdir();changed=[]
for i,pdfpage in enumerate(doc):
 out=render/f'page_{i+1:02}.png';pdfpage.get_pixmap(matrix=fitz.Matrix(1.8,1.8),alpha=False).save(out)
 if audit.sha(out)!=audit.sha(R/'build_01/rendered'/out.name):changed.append(i+1)
shutil.copy2(D/'main.pdf',S/'main.pdf');shutil.copy2(D/'main.pdf',H/'FISAT2026_camera_ready_final.pdf')
summary={'status':'BUILD_PASS_RENDER_REVIEW_PENDING','pages':15,'changed_pages_vs_v6_reviewed':changed,'PDF_sha256':audit.sha(D/'main.pdf'),'source_hashes':{p.relative_to(S).as_posix():audit.sha(p) for p in sorted(S.rglob('*')) if p.is_file()},'tool_sha256':audit.sha(tool),'severe_latex_errors':bad,'clean_output_directory':True,'offline_cached_build':True}
(V/'clean_build_summary.json').write_text(json.dumps(summary,indent=2))
old_response=B/'reviewer_response_v1/RESPONSE_TO_REVIEWERS_DRAFT.md';response=old_response.read_text(encoding='utf-8')
response=response.replace('# Response to Reviewers - Author Review Draft','# Response to Reviewers - Final Local Handoff')
response=response.replace('This draft accompanies','This response accompanies')
response=response.replace('No repeated-run experiment or assertion-enabled full 300 comparison is claimed.','No completed repeated-run evaluation or assertion-enabled full 300 comparison is claimed. Only accepted single-run observations enter the manuscript.')
response=response.replace('This experiment remains unperformed.','No complete repeated-run evaluation is available for this revision. Incomplete exploratory observations are excluded from the manuscript and its reported statistics.')
response=response.replace('Each evaluated configuration has one scheduled generation run per class.','The reported evidence contains one scheduled generation run per class and configuration, allowing only the documented same-seed technical retry.')
response=response.replace('difference of-','difference of -').replace('gap is-','gap is -').replace('state the-','state the -')
response=response.replace('The minimum-valid-n 60 rule applies to RQ1/RQ2, not to the descriptive paired 49 supplement.','The minimum-valid-n 60 rule applies to RQ1/RQ2, not to the descriptive paired 49 supplement. We replaced the unsupported word "prespecified" for this rule with "recorded" and explicitly note that its pre-pilot timing is unverified.')
response=response.replace('Thank you. We retain these distinctions and make their denominators explicit.','Thank you. We retain these distinctions and make their denominators explicit. Table 3 now specifies that compiled-only branch uses 45 GPT and 134 E0 observations, while line/method/mutation use 61 and 158; every strict metric retains 300 per arm.')
statuses={
'R1.1':('Addressed with gate qualification','pp. 6-11; Table 3 note p. 10'),
'R1.2':('Addressed: fixed-cohort descriptive comparison','Sections 3.5, 4.4-4.5, pp. 7-8 and 11; Table 5 p. 11'),
'R1.3':('Partial: E1 on 49, not a new full-300 baseline','Abstract p. 1; Sections 3.3/3.5 pp. 5-8; 4.5 pp. 11-12'),
'R1.4':('Addressed by interpretation; historical NI remains conditional','Abstract p. 1; Table 2 p. 9; Discussion p. 12'),
'R1.5':('Open: no validated practical margin justification','Section 3.4 p. 7; Discussion/Threats pp. 12-13'),
'R1.6':('Partial: narrowed inference; source uncertainty unresolved','Section 2.1 pp. 2-3; Section 3.5 p. 8; Discussion p. 12'),
'R1.7':('Open: no completed repeated-run evaluation','Sections 4.5-6 pp. 11-13'),
'R1.8':('Addressed through Maven sensitivity and pipeline qualification','Section 4.3 p. 10; Discussion/Threats pp. 12-13'),
'R1.9':('Addressed: two no-API rows retained','Sections 3.3/4.1 pp. 5-6 and 8; Table 4 p. 10'),
'R1.10':('Partial: wording corrected; pre-pilot analytical lock unverified','Sections 3.1/3.2/3.4 pp. 4-7; Threats p. 13'),
'R1.11':('Partial: certified final E49 counts; no certified full300 raw inventory','Section 4.5 p. 11; definition Sections 3.4 pp. 6-7'),
'R1.12':('Addressed by paired supplement and narrower claims','Abstract p. 1; Sections 4.4-7 pp. 11-13'),
'R2.strengths':('Acknowledged; archived observations retained','Sections 3-4 pp. 4-12'),
'R2.1':('PARTIAL; blocking concern not claimed fully resolved','Section 3.5 pp. 7-8; Section 4.5 pp. 11-12; Table 5 p. 11; Conclusion p. 13'),
'R2.2':('Addressed via reviewer-offered Maven260 alternative; no Gradle repair','Section 4.3 p. 10'),
'R2.3':('Addressed: full300 and fixed49 remain separate','Sections 4.2-4.5 pp. 8-12; Tables 2-5 pp. 9-11'),
'R2.4':('Addressed','Abstract p. 1; Table 2 p. 9; Discussion p. 12'),
'R2.5':('Open: incomplete repeated data excluded','Discussion p. 12; Threats p. 13'),
'R2.6':('Addressed as exploratory cluster sensitivity','Section 3.5 pp. 7-8; Section 4.4 p. 11'),
'R2.7':('Addressed','Abstract p. 1; Results pp. 8-9; Conclusion p. 13'),
'R2.minor':('Addressed: full stage table in main text','Table 4 p. 10'),
'R2.path':('Partial overall; full300 E1 and repeated evaluation absent','Sections 4.3-7 pp. 10-13'),
'R3.1':('Addressed as additional E49 configuration; limited scope','Sections 3.5/4.5 pp. 7-8 and 11-12; Table 5 p. 11'),
'R3.2':('Open: budgets documented, not equalized','Section 3.5 pp. 7-8; Discussion/Threats pp. 12-13'),
'R3.3':('Addressed as sensitivity, not replacement of all original inference','Sections 3.5/4.4 pp. 7-8 and 11'),
'R3.4':('Partial: taxonomy/Maven sensitivity; no Gradle redesign','Section 4.3 p. 10; Section 4.5 pp. 11-12'),
'R3.5':('Not evaluated; retained as future work','Section 2.2 p. 3; Discussion p. 12')}
for key,(status,loc) in statuses.items():
 pattern=r'(### '+re.escape(key)+r' - [^\n]+\n)';assert re.search(pattern,response),key
 response=re.sub(pattern,lambda m:m.group(1)+'\n**Status:** '+status+'.  \n**Final manuscript location:** '+loc+'.\n',response,count=1)
(H/'RESPONSE_TO_REVIEWERS.md').write_text(response,encoding='utf-8')
(H/'REVIEWER_STATUS.json').write_text(json.dumps({k:{'status':s,'location':l} for k,(s,l) in statuses.items()},indent=2))
audit.log('FINAL_RESPONSE_PREPARED',items=len(statuses),prior_response_sha256=audit.sha(old_response),new_response_sha256=audit.sha(H/'RESPONSE_TO_REVIEWERS.md'),incomplete_repeated_results_excluded=True)
print(json.dumps({'pages':15,'changed_render_pages':changed,'reviewer_items':len(statuses),'PDF_sha256':summary['PDF_sha256']}))
