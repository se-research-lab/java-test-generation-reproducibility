"""Complete post-build PDF checks/render without rerunning LaTeX or any experiment."""
import json,re,sys,unicodedata
from pathlib import Path
import fitz
B=Path(__file__).resolve().parents[1];sys.path.insert(0,str(B));import audit
R=B/'manuscript_revision_v5_disclosure';OLD=B/'manuscript_revision_v4_submission';S=R/'source';D=R/'build_01';sha=audit.sha
manifest=json.loads((R/'source_copy_manifest.json').read_text(encoding='utf-8'))['files'];change=json.loads((R/'change_manifest.json').read_text(encoding='utf-8'))
actual={n:sha(S/n) for n in manifest};assert [n for n in actual if actual[n]!=manifest[n]]==['sections/08_disclosure.tex']
assert sha(S/'sections/08_disclosure.tex')==change['after_sha256']
pdfsha=sha(D/'main.pdf');doc=fitz.open(D/'main.pdf');assert len(doc)==15
texts=[p.get_text() for p in doc];alltext=unicodedata.normalize('NFKC',' '.join(texts));alltext=' '.join(alltext.split())
assert 'OpenAI Codex' not in alltext and 'AI assistant' not in alltext
assert 'no external funding' in alltext and 'no conflicts of interest' in alltext
assert 'Corresponding author: Le Thi Quynh Chi' in alltext
assert not any('\ufffd' in t or '??' in t for t in texts)
log=(D/'main.log').read_text(encoding='utf-8',errors='replace');errors=[l for l in log.splitlines() if re.search(r'Overfull|Missing character|LaTeX Warning:.*(?:undefined|multiply defined)|^!',l)];assert not errors,errors
out=D/'rendered';out.mkdir(exist_ok=False);pngs={};changed=[]
for i,page in enumerate(doc):
    p=out/f'page_{i+1:02d}.png';page.get_pixmap(matrix=fitz.Matrix(1.8,1.8),alpha=False).save(p);pngs[p.name]=sha(p)
    if sha(p)!=sha(OLD/f'build_01/rendered/page_{i+1:02d}.png'):changed.append(i+1)
assert sha(D/'main.pdf')==pdfsha
report={'returncode':0,'pages':15,'PDF_sha256':pdfsha,'input_hashes':actual,'changed_pages':changed,'severe_latex_errors':errors,'underfull_entries':[l for l in log.splitlines() if 'Underfull' in l],'pending_visual_QA':True,'draft_not_submission_ready':True,'postbuild_textcheck_correction':'NFKC normalization for PDF ligature confllicts/fl; collapse whitespace. No PDF/source edit or LaTeX rerun.'}
for p,obj in [(D/'build_summary.json',report),(out/'render_manifest.json',{'PDF_sha256':pdfsha,'PNG_hashes':pngs,'pages_changed_vs_verified_v4':changed,'unchanged_pages_byte_identical_to_prior_QA':True,'changed_pages_visual_review_required':True,'renderer':'PyMuPDF fallback; Poppler unavailable'})]:
    with p.open('x',encoding='utf-8') as f:json.dump(obj,f,indent=2);f.write('\n')
audit.log('NEW_FILE_REGISTERED',path=Path(__file__).relative_to(B).as_posix(),sha256=sha(__file__),bytes=Path(__file__).stat().st_size,change_type='postbuild check correction only; no source/PDF change or rebuild')
audit.log('MANUSCRIPT_BUILD_END',revision='v5_disclosure',pages=15,PDF_sha256=pdfsha,changed_pages=changed,summary_sha256=sha(D/'build_summary.json'),prior_postbuild_check_failed_due_to_PDF_ligature=True,PDF_rebuilt_for_recovery=False)
print(json.dumps({'status':'RENDERED_PENDING_VISUAL_QA','pages':15,'changed_pages':changed,'PDF_sha256':pdfsha},indent=2))
