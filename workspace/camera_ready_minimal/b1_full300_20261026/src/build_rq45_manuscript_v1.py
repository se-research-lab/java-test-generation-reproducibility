"""Build only the isolated LaTeX manuscript; no experimental Java commands."""
import json, os, shutil, subprocess, sys, re
from pathlib import Path
import fitz
R=Path(__file__).resolve().parents[1];B=R.parent/'paired49_20261023';O=R/'analysis_camera_ready_rq45_v1';S=O/'manuscript'
sys.path.insert(0,str(B));import audit
tag=sys.argv[1];assert re.fullmatch(r'\d\d',tag)
out=O/('build_'+tag);out.mkdir(exist_ok=False)
cache=O/'tectonic_cache'
if not cache.exists():
    old=B/'manuscript_revision_v5_disclosure/tectonic_cache'
    shutil.copytree(old,cache)
    entries={str(p.relative_to(old)):audit.sha(p) for p in old.rglob('*') if p.is_file()}
    for name,h in entries.items():assert audit.sha(cache/name)==h
    (O/'latex_cache_copy_hashes.json').write_text(json.dumps(entries,indent=2),encoding='utf-8')
tool=B/'tools/tectonic-0.17.0-x86_64-pc-windows-msvc/tectonic.exe'
env=dict(os.environ);env['TECTONIC_CACHE_DIR']=str(cache)
inputs={p.relative_to(S).as_posix():audit.sha(p) for p in S.rglob('*') if p.is_file()}
argv=[str(tool),'--only-cached','--untrusted','--keep-logs','--keep-intermediates','--outdir',str(out),str(S/'main.tex')]
audit.log('B1_RQ45_LATEX_BUILD_START',argv=argv,source_hashes=inputs,tool_sha256=audit.sha(tool))
proc=subprocess.run(argv,cwd=S,env=env,capture_output=True,text=True,errors='replace',timeout=300)
(out/'stdout.txt').write_text(proc.stdout,encoding='utf-8');(out/'stderr.txt').write_text(proc.stderr,encoding='utf-8')
summary={'returncode':proc.returncode,'source_hashes':inputs,'argv':argv,'experiment_calls':0}
if (out/'main.pdf').exists():
    doc=fitz.open(out/'main.pdf');summary.update(pages=len(doc),pdf_sha256=audit.sha(out/'main.pdf'))
    (out/'page_text.txt').write_text('\n\n'.join(f'PAGE {i+1}\n'+p.get_text() for i,p in enumerate(doc)),encoding='utf-8')
    summary['page_starts']=[p.get_text()[:180] for p in doc]
(out/'build_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
audit.log('B1_RQ45_LATEX_BUILD_END',summary_sha256=audit.sha(out/'build_summary.json'),returncode=proc.returncode)
print(json.dumps(summary,indent=2));assert proc.returncode==0
