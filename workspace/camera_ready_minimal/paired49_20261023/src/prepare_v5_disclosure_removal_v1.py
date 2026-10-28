"""User-requested disclosure-only revision in a new manuscript copy; no experiment edits."""
import difflib,json,os,re,shutil,subprocess,sys
from pathlib import Path
import fitz
B=Path(__file__).resolve().parents[1];sys.path.insert(0,str(B));import audit
OLD=B/'manuscript_revision_v4_submission';NEW=B/'manuscript_revision_v5_disclosure';S=NEW/'source'
sha=audit.sha
def dump(p,obj):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f:json.dump(obj,f,ensure_ascii=False,indent=2);f.write('\n')
assert not NEW.exists()
audit.log('NEW_FILE_REGISTERED',path=Path(__file__).relative_to(B).as_posix(),sha256=sha(__file__),bytes=Path(__file__).stat().st_size,change_type='new user-requested disclosure-only copy/build script')
closed=json.loads((B/'audit/camera_ready_response_registry_v1.json').read_text(encoding='utf-8'))
for row in closed['files']:assert sha(B/row['path'])==row['sha256'],row['path']
source_manifest=json.loads((OLD/'output/source_manifest.json').read_text(encoding='utf-8'))['files'];assert len(source_manifest)==15
S.mkdir(parents=True)
for n,h in source_manifest.items():
    source=OLD/'source'/n;dest=S/n;dest.parent.mkdir(parents=True,exist_ok=True)
    assert sha(source)==h;shutil.copy2(source,dest);assert sha(dest)==h==sha(source)
dump(NEW/'source_copy_manifest.json',{'from':str(OLD/'source'),'files':source_manifest,'original_files_unchanged':True})
name='sections/08_disclosure.tex';p=S/name;backup=NEW/'backups/disclosure_removal_v1'/name;backup.parent.mkdir(parents=True);shutil.copy2(p,backup)
before=p.read_text(encoding='utf-8');h_before=sha(p)
needle='\\noindent\\textbf{Acknowledgements.} An AI assistant (OpenAI Codex) supported post-review code auditing, supplementary analysis and manuscript drafting. This assistance is separate from the GPT-4o-mini generation treatment. The authors remain responsible for verifying the analyses, references and final text. This study received no external funding.\\par'
assert before.count(needle)==1
after=before.replace(needle,'\\noindent\\textbf{Funding.} This study received no external funding.\\par')
with p.open('w',encoding='utf-8',newline='\n') as f:f.write(after)
assert 'OpenAI Codex' not in after and 'AI assistant' not in after and 'no external funding' in after and 'no conflicts of interest' in after
diff=NEW/'backups/disclosure_removal_v1/08_disclosure.tex.diff';diff.write_text(''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='v4/'+name,tofile='v5/'+name)),encoding='utf-8')
audit.log('FILE_REVISION',path=p.relative_to(B).as_posix(),before_sha256=h_before,after_sha256=sha(p),backup=backup.relative_to(B).as_posix(),backup_sha256=sha(backup),reason='Explicit user request to omit substantive-AI-use acknowledgement; retain funding/conflict facts; no claim of copy-editing-only use is substituted')
actual={n:sha(S/n) for n in source_manifest};changed=[n for n in actual if actual[n]!=source_manifest[n]];assert changed==[name]
dump(NEW/'change_manifest.json',{'changed_sources':changed,'before_sha256':h_before,'after_sha256':sha(p),'backup_sha256':sha(backup),'diff_sha256':sha(diff),'other14_source_files_byte_identical':True,'user_requested_omission':True,'funding_and_conflicts_retained':True,'only_copy_editing_claim_added':False,'publisher_AI_disclosure_compliance_not_certified':True,'experiment_API_calls':0})
cache=NEW/'tectonic_cache';cache.mkdir();rows=[]
for q in sorted((OLD/'tectonic_cache').rglob('*')):
    if not q.is_file():continue
    n=q.relative_to(OLD/'tectonic_cache');dest=cache/n;dest.parent.mkdir(parents=True,exist_ok=True);h=sha(q);shutil.copy2(q,dest);assert sha(q)==h==sha(dest)
    rows.append({'path':n.as_posix(),'sha256':h,'bytes':q.stat().st_size})
dump(NEW/'tectonic_cache_copy_manifest.json',rows)
tool=B/'tools/tectonic-0.17.0-x86_64-pc-windows-msvc/tectonic.exe';assert sha(tool)=='99ffcfdbf1ebf8bdda9e791942e3d06aedb12463fddc33f07de6f5211c8bf08d'
build=NEW/'build_01';build.mkdir();env=dict(os.environ);env['TECTONIC_CACHE_DIR']=str(cache)
argv=[str(tool),'--only-cached','--untrusted','--keep-logs','--keep-intermediates','--outdir',str(build),str(S/'main.tex')]
audit.log('MANUSCRIPT_BUILD_START',revision='v5_disclosure',argv=argv,cwd=str(S),input_hashes=actual,tool_sha256=sha(tool))
r=subprocess.run(argv,cwd=S,env=env,capture_output=True,text=True,errors='replace',timeout=300)
(build/'tectonic.stdout.txt').write_text(r.stdout,encoding='utf-8');(build/'tectonic.stderr.txt').write_text(r.stderr,encoding='utf-8');assert r.returncode==0,(r.stdout,r.stderr)
doc=fitz.open(build/'main.pdf');assert len(doc)==15,len(doc)
texts=[p.get_text() for p in doc];alltext='\n'.join(texts)
assert 'OpenAI Codex' not in alltext and 'AI assistant' not in alltext
assert 'Corresponding author: Le Thi Quynh Chi' in alltext
assert 'no external funding' in alltext and 'no conflicts of interest' in alltext
assert not any('\ufffd' in t or '??' in t for t in texts)
log=(build/'main.log').read_text(encoding='utf-8',errors='replace');errors=[l for l in log.splitlines() if re.search(r'Overfull|Missing character|LaTeX Warning:.*(?:undefined|multiply defined)|^!',l)];assert not errors,errors
render=build/'rendered';render.mkdir();pngs={};changed_pages=[]
for i,page in enumerate(doc):
    out=render/f'page_{i+1:02d}.png';page.get_pixmap(matrix=fitz.Matrix(1.8,1.8),alpha=False).save(out);pngs[out.name]=sha(out)
    if sha(out)!=sha(OLD/f'build_01/rendered/page_{i+1:02d}.png'):changed_pages.append(i+1)
dump(render/'render_manifest.json',{'PDF_sha256':sha(build/'main.pdf'),'PNG_hashes':pngs,'pages_changed_vs_verified_v4':changed_pages,'unchanged_pages_byte_identical_to_prior_QA':True,'changed_pages_visual_review_required':True,'renderer':'PyMuPDF fallback; Poppler unavailable'})
dump(build/'build_summary.json',{'returncode':0,'pages':len(doc),'PDF_sha256':sha(build/'main.pdf'),'input_hashes':actual,'changed_pages':changed_pages,'severe_latex_errors':errors,'underfull_entries':[l for l in log.splitlines() if 'Underfull' in l],'pending_visual_QA':True,'draft_not_submission_ready':True})
audit.log('MANUSCRIPT_BUILD_END',revision='v5_disclosure',pages=len(doc),PDF_sha256=sha(build/'main.pdf'),changed_pages=changed_pages,summary_sha256=sha(build/'build_summary.json'))
print(json.dumps({'status':'BUILT_PENDING_VISUAL_QA','pages':len(doc),'changed_pages':changed_pages,'PDF_sha256':sha(build/'main.pdf')},indent=2))
