"""Render every draft PDF page and make contact sheets for visual QA; no PDF edits."""
import json,sys
from pathlib import Path
import fitz
from PIL import Image,ImageDraw,ImageFont
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));import audit
rev=BASE/'manuscript_revision_v3_compat49';tag=sys.argv[1];build=rev/('build_'+tag);pdf=build/'main.pdf';out=build/'rendered';out.mkdir(exist_ok=False)
doc=fitz.open(pdf);images=[];details=[]
for i,page in enumerate(doc):
    pix=page.get_pixmap(matrix=fitz.Matrix(1.8,1.8),alpha=False)
    path=out/('page_%02d.png'%(i+1));pix.save(path);images.append(path)
    text=page.get_text();details.append({'page':i+1,'chars':len(text),'width':page.rect.width,'height':page.rect.height,'has_replacement_character':'\ufffd' in text,'has_undefined_reference':'??' in text})
font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',20)
for start in range(0,len(images),6):
    sheet=Image.new('RGB',(1260,1820),'#d9d9d9');draw=ImageDraw.Draw(sheet)
    for off,path in enumerate(images[start:start+6]):
        im=Image.open(path).convert('RGB');im.thumbnail((400,850));x=20+(off%3)*420;y=45+(off//3)*900
        sheet.paste(im,(x,y));draw.text((x,y-28),'Page '+str(start+off+1),fill='black',font=font)
    sheet.save(out/('contact_%02d_%02d.png'%(start+1,min(start+6,len(images)))))
report={'PDF_sha256':audit.sha(pdf),'pages':details,'rendered_PNGs':{p.name:audit.sha(p) for p in sorted(out.glob('*.png'))},'visual_review_required':True,'renderer':'PyMuPDF; Poppler not installed on PATH'}
with (out/'render_manifest.json').open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
audit.log('MANUSCRIPT_ALL_PAGES_RENDERED',tag=tag,pages=len(doc),PDF_sha256=audit.sha(pdf),manifest_sha256=audit.sha(out/'render_manifest.json'))
print(json.dumps({'pages':len(doc),'out':str(out),'visual_review_still_required':True}))
