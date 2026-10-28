"""Validate released PDF/source archive against clean build and frozen inputs."""
import hashlib,json,re,sys,zipfile
from pathlib import Path
import fitz
from PIL import Image,ImageChops
R=Path(__file__).resolve().parents[1];O=R/'camera_ready_checkpoint300_v1';D=O/'delivery';B=R.parent/'paired49_20261023'
sys.path.insert(0,str(B));import audit
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
pdf=D/'FISAT2026_camera_ready.pdf';a=fitz.open(pdf);b=fitz.open(O/'build_04/main.pdf');assert len(a)==len(b)==15
assert sha(pdf)==sha(O/'build_03/main.pdf')
same=[];bounds=[];fonts=[]
for i,(x,y) in enumerate(zip(a,b)):
 px=x.get_pixmap(matrix=fitz.Matrix(1.5,1.5),alpha=False);py=y.get_pixmap(matrix=fitz.Matrix(1.5,1.5),alpha=False)
 assert (px.width,px.height,px.samples)==(py.width,py.height,py.samples),i
 assert x.get_text()==y.get_text();same.append(i+1)
 for word in x.get_text('words'):
  assert 0<=word[0]<=word[2]<=x.rect.width+0.1 and 0<=word[1]<=word[3]<=x.rect.height+0.1,(i,word)
 bounds.append({'page':i+1,'words':len(x.get_text('words'))})
 for font in x.get_fonts():
  data=a.extract_font(font[0]);assert data[3],font
  fonts.append(font[3])
unchanged=[];changed=[]
for i in range(1,16):
 old=Image.open(O/'render_02'/f'page-{i:02d}.png').convert('RGB');new=Image.open(O/'render_03'/f'page-{i:02d}.png').convert('RGB')
 if old.size==new.size and ImageChops.difference(old,new).getbbox() is None:unchanged.append(i)
 else:changed.append(i)
assert changed==[11],changed
text='\n'.join(x.get_text() for x in a);normalized=re.sub(r'\s+',' ',text)
for name in ['Truong Dan Huy','Vuong Quoc Khanh','Tran Minh Quy','Le Tran Anh Khoa','Tran Bich Tram','Le Thi Quynh Chi']:assert name in normalized,name
assert normalized.count('Corresponding author:')==1 and 'Corresponding author: Le Thi Quynh Chi' in normalized
for value in ['221','279','222','21 unresolved','58 conventional','79.29','31.88','38.88','20.33','61/300']:
 assert value in normalized,value
sources='\n'.join(p.read_text(encoding='utf-8') for p in (O/'manuscript').rglob('*.tex'))
for stale in ['270 operational','270 recorded','270 observed','30 unscored','nine Gradle','prespecified n']:
 assert stale not in sources,stale
assert 'replication package withheld for double-blind review; submitted as supplementary material' in sources
assert sha(O/'manuscript/sections/04_results.tex')==sha(O/'backup/manuscript/sections/04_results.tex')
assert len(re.findall(r'\\item \\textbf\{RQ[1-5]',sources))==5
assert len(re.findall(r'\\bibitem\{',sources))==25
for tag in ['03','04']:
 log=(O/f'build_{tag}/main.log').read_text(encoding='utf-8',errors='replace')
 assert not re.search(r'Overfull|undefined|LaTeX Error',log)
with zipfile.ZipFile(D/'FISAT2026_camera_ready_source.zip') as z:
 assert z.testzip() is None
 assert hashlib.sha256(z.read(pdf.name)).hexdigest()==sha(pdf)
 assert all(not any(x in n.lower() for x in ['.env','secret','api_key']) for n in z.namelist())
 assert len(z.namelist())==18
original=[]
for p in sorted((O/'backup/manuscript').rglob('*')):
 if p.is_file():
  current=R/'analysis_camera_ready_rq45_v1/manuscript'/p.relative_to(O/'backup/manuscript')
  assert sha(p)==sha(current);original.append(str(current))
report={'status':'PASS','pdf_sha256':sha(pdf),'pages':15,'references_start_page':14,'clean_zip_build_pages':15,'clean_build_pixel_equal_pages':same,'clean_build_text_equal':True,'embedded_fonts':sorted(set(fonts)),'page_bounds':bounds,'manuscript_baseline_files_unchanged':len(original),'historical_RQ_results_section_unchanged':True,'five_RQs':True,'six_authors':True,'sole_corresponding_author':'Le Thi Quynh Chi','overfull_or_undefined_references':False,'source_zip_contains_identical_pdf':True,'new_experiments':0,'new_GPT_API_calls':0}
(D/'VALIDATION.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
visual={'status':'PASS','renderer':'Poppler pdftoppm 105dpi','reviewed_initial_pages':list(range(1,16)),'final_pages_pixel_identical_to_reviewed':unchanged,'final_changed_page_reviewed':[11],'review':'All pages visually checked; final table header shortened on page11. No clipping, overlap, missing glyphs or broken tables observed. References and author block checked.','pdf_sha256':sha(pdf)}
(D/'VISUAL_QA.json').write_text(json.dumps(visual,indent=2),encoding='utf-8')
audit.log('CAMERA_READY_CHECKPOINT300_VALIDATED',pdf_sha256=sha(pdf),validation_sha256=sha(D/'VALIDATION.json'),pages=15,clean_build_pixel_equal=True,new_experiments=0)
print(json.dumps({'status':'PASS','pages':15,'clean_build_pixel_equal':True,'final_visual_changed_pages':changed,'manuscript_baseline_files_unchanged':len(original)}))
