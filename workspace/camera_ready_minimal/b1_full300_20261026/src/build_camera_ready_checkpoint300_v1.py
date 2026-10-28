"""Offline TeX build and PDF inspection; no experimental workloads."""
import json,os,re,subprocess,sys
from pathlib import Path
import fitz
R=Path(__file__).resolve().parents[1];O=R/'camera_ready_checkpoint300_v1';B=R.parent/'paired49_20261023'
sys.path.insert(0,str(B));import audit
tag=sys.argv[1];assert re.fullmatch(r'\d\d',tag)
S=Path(sys.argv[2]) if len(sys.argv)>2 else O/'manuscript'
out=O/('build_'+tag);out.mkdir(exist_ok=False)
tool=B/'tools/tectonic-0.17.0-x86_64-pc-windows-msvc/tectonic.exe'
env=dict(os.environ);env['TECTONIC_CACHE_DIR']=str(R/'analysis_camera_ready_rq45_v1/tectonic_cache')
argv=[str(tool),'--only-cached','--untrusted','--keep-logs','--keep-intermediates','--outdir',str(out),str(S/'main.tex')]
inputs={str(p.relative_to(S)):audit.sha(p) for p in S.rglob('*') if p.is_file()}
proc=subprocess.run(argv,cwd=S,env=env,capture_output=True,text=True,errors='replace',timeout=300)
(out/'stdout.txt').write_text(proc.stdout,encoding='utf-8');(out/'stderr.txt').write_text(proc.stderr,encoding='utf-8')
report={'returncode':proc.returncode,'source_hashes':inputs,'command':argv,'tool_sha256':audit.sha(tool),'experiment_calls':0}
if (out/'main.pdf').is_file():
 doc=fitz.open(out/'main.pdf');report.update(pages=len(doc),pdf_sha256=audit.sha(out/'main.pdf'))
 (out/'page_text.txt').write_text('\n\n'.join(f'PAGE {i+1}\n'+p.get_text() for i,p in enumerate(doc)),encoding='utf-8')
 report['page_starts']=[p.get_text()[:140] for p in doc]
 report['references_pages']=[i+1 for i,p in enumerate(doc) if 'References' in p.get_text()]
(out/'build_summary.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
audit.log('CAMERA_READY_CHECKPOINT300_BUILD',path=str(out),summary_sha256=audit.sha(out/'build_summary.json'),returncode=proc.returncode)
print(json.dumps(report,indent=2));assert proc.returncode==0
