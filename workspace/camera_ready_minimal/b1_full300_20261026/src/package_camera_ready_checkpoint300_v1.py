"""Prepare manuscript-only submission archive, with backups and validation gates."""
import json,re,shutil,sys,zipfile,difflib
from pathlib import Path
R=Path(__file__).resolve().parents[1];O=R/'camera_ready_checkpoint300_v1';B=R.parent/'paired49_20261023'
sys.path.insert(0,str(B));import audit
mode=sys.argv[1]
if mode=='refine':
 backup=O/'backup/refinement02';backup.mkdir()
 p=O/'manuscript/sections/04a_supplement.tex';shutil.copy2(p,backup/p.name)
 t=p.read_text(encoding='utf-8').replace('Indicator & Pass/available & Fail/unsuccessful & Other/unknown','Indicator & Pass/present & Fail & Other/unknown')
 p.write_text(t,encoding='utf-8')
 p=O/'RESPONSE_TO_REVIEWERS.md';shutil.copy2(p,backup/p.name);t=p.read_text(encoding='utf-8')
 t=re.sub(r'\b([REG]) ([0-9])',r'\1\2',t);t=re.sub(r'\bA 12\b','A12',t);t=re.sub(r'\bRQ ([0-9])',r'RQ\1',t)
 t=t.replace('CI[','CI [').replace('Table5','Table 5').replace('Table6','Table 6').replace('15-page','15-page')
 t=re.sub(r'Sections(?=\d)','Sections ',t);t=re.sub(r'Section(?=\d)','Section ',t);t=re.sub(r'pp\.(?=\d)','pp. ',t)
 p.write_text(t,encoding='utf-8');audit.log('CAMERA_READY_TABLE_RESPONSE_POLISH',backup=str(backup),experiment_calls=0)
elif mode=='package':
 build=O/'build_03';summary=json.loads((build/'build_summary.json').read_text());assert summary['pages']==15 and summary['returncode']==0
 log=(build/'main.log').read_text(encoding='utf-8',errors='replace');assert 'Overfull' not in log and 'undefined' not in log
 D=O/'delivery';D.mkdir();pdf=D/'FISAT2026_camera_ready.pdf';shutil.copy2(build/'main.pdf',pdf)
 stage=O/'submission_package';stage.mkdir();shutil.copytree(O/'manuscript',stage/'source');shutil.copy2(pdf,stage/pdf.name)
 readme='''# Camera-ready manuscript source

Contents: FISAT2026_camera_ready.pdf and source/ (main.tex, all sections, references.tex/references.bib, llncs.cls, splncs04.bst).
This archive contains manuscript material only, not experimental code, credentials or caches.

Build from source/ using a TeX distribution with the packages in main.tex:

    pdflatex -interaction=nonstopmode -halt-on-error main.tex
    pdflatex -interaction=nonstopmode -halt-on-error main.tex

The supplied references.tex is the active bibliography; BibTeX is not required.
Validated builder: Tectonic 0.17.0 with a prepopulated TeX cache:

    tectonic --only-cached --untrusted main.tex

Without an existing cache, Tectonic normally downloads its TeX support bundle; this is typesetting only, not an experimental run. For exact offline rendering, use the private retained cache and tool manifest. Do not run any experimental batch to build the manuscript.

The PDF has15pages including references. The reference source is frozen from the preceding manuscript. The use of a different TeX distribution can affect line breaks; check the page count and layout after rebuilding.
Six authors are listed; Le Thi Quynh Chi is the sole corresponding author. Authors remain responsible for final scholarly approval, metadata, applicable disclosures, registration, license and submission.
'''
 (stage/'README.md').write_text(readme,encoding='utf-8')
 entries=[{'path':str(p.relative_to(stage)).replace('\\','/'),'sha256':audit.sha(p),'bytes':p.stat().st_size} for p in sorted(stage.rglob('*')) if p.is_file()]
 (stage/'SOURCE_MANIFEST.json').write_text(json.dumps(entries,indent=2),encoding='utf-8')
 z=D/'FISAT2026_camera_ready_source.zip'
 with zipfile.ZipFile(z,'x',zipfile.ZIP_DEFLATED) as f:
  for p in sorted(stage.rglob('*')):
   if p.is_file():f.write(p,p.relative_to(stage).as_posix())
 clean=O/'clean_extract';clean.mkdir()
 with zipfile.ZipFile(z) as f:
  assert f.testzip() is None
  for name in f.namelist():assert not Path(name).is_absolute() and '..' not in Path(name).parts
  f.extractall(clean)
 for x in entries:assert audit.sha(clean/x['path'])==x['sha256']
 for name in ['RESPONSE_TO_REVIEWERS.md','REVIEWER_STATUS.json']:shutil.copy2(O/name,D/name)
 diffs=[];changes=[]
 for p in sorted((O/'manuscript').rglob('*')):
  if not p.is_file():continue
  rel=p.relative_to(O/'manuscript');old=O/'backup/manuscript'/rel
  changes.append({'path':rel.as_posix(),'before':audit.sha(old),'after':audit.sha(p)})
  if audit.sha(old)!=audit.sha(p):diffs.extend(difflib.unified_diff(old.read_text(encoding='utf-8').splitlines(True),p.read_text(encoding='utf-8').splitlines(True),fromfile='baseline/'+rel.as_posix(),tofile='camera_ready/'+rel.as_posix()))
 (D/'MANUSCRIPT_CHANGES.diff').write_text(''.join(diffs),encoding='utf-8');(D/'source_change_manifest.json').write_text(json.dumps(changes,indent=2),encoding='utf-8')
 audit.log('CAMERA_READY_SOURCE_ZIP_PREPARED',zip=str(z),zip_sha256=audit.sha(z),pdf_sha256=audit.sha(pdf),source_files=len(entries)-2,new_experiments=0)
 print(json.dumps({'delivery':str(D),'clean_source':str(clean/'source'),'pdf_sha256':audit.sha(pdf),'zip_members':len(entries)+1}))
else:raise ValueError(mode)
