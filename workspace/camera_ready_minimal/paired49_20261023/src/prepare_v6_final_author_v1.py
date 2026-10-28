"""New manuscript only; no experiment launch/import."""
import json,sys,shutil,difflib,subprocess,os,re
from pathlib import Path
import fitz
B=Path(__file__).resolve().parents[1];sys.path.insert(0,str(B));import audit
OLD=B/'manuscript_revision_v5_disclosure';R=B/'manuscript_revision_v6_final';S=R/'source'
assert not R.exists(); assert (B/'repeated_subset_v1/STOP_DO_NOT_RESUME.json').exists()
for reg in ['measurement49_camera_ready_registry_v1.json','camera_ready_response_registry_v1.json','disclosure_only_registry_v1.json']:
 for x in json.loads((B/'audit'/reg).read_text())['files']:assert audit.sha(B/x['path'])==x['sha256'],x['path']
shutil.copytree(OLD/'source',S);shutil.copytree(OLD/'source',R/'backups/v5_source')
changes=[]
def edit(n,old,new):
 p=S/n;t=p.read_text(encoding='utf-8');assert t.count(old)==1,(n,old[:70]);p.write_text(t.replace(old,new),encoding='utf-8')
edit('sections/03_method.tex',r'above the prespecified n \ensuremath{\geq}60 gate.',r'above the recorded n \ensuremath{\geq}60 rule; its pre-pilot timing is unverified.')
edit('sections/04_results.tex',r'\end{tabularx}\end{table}'+'\n\n'+r'\textbf{Complexity.}',r'\end{tabularx}'+'\n'+r'\par\smallskip\parbox{\linewidth}{\scriptsize Denominators: compiled-only branch uses 45 GPT and 134 E0 observations; line, method and mutation use 61 and 158. Strict scores use 300 per arm, zero-filling failures and unavailable metrics.}'+'\n'+r'\end{table}'+'\n\n'+r'\textbf{Complexity.}')
edit('sections/06_threats.tex','Single runs/configuration sensitivity do not estimate within-arm variance.','No complete repeated-run evaluation is available; single-run configuration sensitivity does not quantify within-arm variance.')
edit('sections/08_disclosure.tex','Access information will accompany the final camera-ready submission.','Public artifact access has not yet been finalized.')
for p in S.rglob('*'):
 if not p.is_file():continue
 n=p.relative_to(S);old=OLD/'source'/n
 if audit.sha(p)!=audit.sha(old):
  diff=R/'backups'/Path(str(n)+'.diff');diff.parent.mkdir(parents=True,exist_ok=True)
  diff.write_text(''.join(difflib.unified_diff(old.read_text().splitlines(True),p.read_text().splitlines(True),fromfile='v5/'+n.as_posix(),tofile='v6/'+n.as_posix())),encoding='utf-8')
  changes.append({'path':n.as_posix(),'before':audit.sha(old),'after':audit.sha(p),'backup':(R/'backups/v5_source'/n).relative_to(B).as_posix()})
  audit.log('FILE_REVISION',path=p.relative_to(B).as_posix(),before_sha256=audit.sha(old),after_sha256=audit.sha(p),backup=changes[-1]['backup'],reason='Author finalization: no repeated results; threshold chronology and Table3 denominators clarified')
(R/'change_manifest.json').write_text(json.dumps(changes,indent=2),encoding='utf-8')
shutil.copytree(OLD/'tectonic_cache',R/'tectonic_cache')
D=R/'build_01';D.mkdir();env=dict(os.environ);env['TECTONIC_CACHE_DIR']=str(R/'tectonic_cache')
tool=B/'tools/tectonic-0.17.0-x86_64-pc-windows-msvc/tectonic.exe';assert audit.sha(tool)=='99ffcfdbf1ebf8bdda9e791942e3d06aedb12463fddc33f07de6f5211c8bf08d'
argv=[str(tool),'--only-cached','--untrusted','--keep-logs','--keep-intermediates','--outdir',str(D),str(S/'main.tex')]
a=subprocess.run(argv,cwd=S,env=env,capture_output=True,text=True,errors='replace',timeout=300)
(D/'stdout.txt').write_text(a.stdout);(D/'stderr.txt').write_text(a.stderr);assert a.returncode==0,a.stderr
doc=fitz.open(D/'main.pdf');text='\n'.join(p.get_text() for p in doc);assert len(doc)==15,len(doc)
assert 'Corresponding author: Le Thi Quynh Chi' in text and '??' not in text
log=(D/'main.log').read_text(errors='replace');bad=[l for l in log.splitlines() if re.search(r'Overfull|Missing character|LaTeX Warning:.*(?:undefined|multiply defined)|^!',l)];assert not bad,bad
render=D/'rendered';render.mkdir()
for i,p in enumerate(doc):p.get_pixmap(matrix=fitz.Matrix(1.8,1.8),alpha=False).save(render/f'page_{i+1:02}.png')
(D/'text.txt').write_text(text,encoding='utf-8')
summary={'pages':len(doc),'PDF_sha256':audit.sha(D/'main.pdf'),'changes':changes,'no_new_experiments':True,'no_repeated_results':True,'severe_latex_errors':bad,'visual_QA':'PENDING','source_hashes':{p.relative_to(S).as_posix():audit.sha(p) for p in S.rglob('*') if p.is_file()},'template_llncs_matches_local_official':audit.sha(S/'llncs.cls')==audit.sha(audit.ROOT/'tutorial/Springer_Latex_Template/llncs.cls')}
(D/'summary.json').write_text(json.dumps(summary,indent=2));audit.log('V6_MANUSCRIPT_BUILD',summary=summary)
print(json.dumps({'pages':len(doc),'changes':[x['path'] for x in changes],'PDF_sha256':summary['PDF_sha256'],'visual_QA':'PENDING'}))
