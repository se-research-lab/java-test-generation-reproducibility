"""Build isolated manuscript draft with workspace-owned cache and per-attempt outputs."""
import argparse,json,os,re,shutil,subprocess,sys
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));import audit
REV=BASE/'manuscript_revision_v3_compat49';SOURCE=REV/'source'
def dump(p,obj):
    with p.open('x',encoding='utf-8') as f:json.dump(obj,f,indent=2)
def main():
    parser=argparse.ArgumentParser();parser.add_argument('tag');args=parser.parse_args();assert re.fullmatch('[a-zA-Z0-9_]+',args.tag)
    output=REV/('build_'+args.tag);output.mkdir(exist_ok=False)
    tool=BASE/'tools/tectonic-0.17.0-x86_64-pc-windows-msvc/tectonic.exe'
    cache=REV/'tectonic_cache'
    if not cache.exists():
        old=BASE/'manuscript_revision_v2_15pages/tectonic_cache';cache.mkdir();files=[]
        for p in sorted(old.rglob('*')):
            if not p.is_file():continue
            rel=p.relative_to(old);dest=cache/rel;dest.parent.mkdir(parents=True,exist_ok=True)
            h=audit.sha(p);shutil.copy2(p,dest);assert h==audit.sha(p)==audit.sha(dest)
            files.append({'relative':rel.as_posix(),'sha256':h,'bytes':p.stat().st_size})
        dump(REV/'tectonic_cache_copy_manifest.json',files)
        audit.log('MANUSCRIPT_LATEX_CACHE_COPIED',files=len(files),bytes=sum(r['bytes'] for r in files),manifest_sha256=audit.sha(REV/'tectonic_cache_copy_manifest.json'),original_cache_modified=False)
    env=dict(os.environ);env['TECTONIC_CACHE_DIR']=str(cache)
    inputs={str(p.relative_to(SOURCE)):audit.sha(p) for p in sorted(SOURCE.rglob('*')) if p.is_file()}
    argv=[str(tool),'--only-cached','--untrusted','--keep-logs','--keep-intermediates','--outdir',str(output),str(SOURCE/'main.tex')]
    audit.log('MANUSCRIPT_BUILD_START',tag=args.tag,argv=argv,cwd=str(SOURCE),tool_sha256=audit.sha(tool),input_hashes=inputs,cache=str(cache))
    r=subprocess.run(argv,cwd=SOURCE,env=env,capture_output=True,text=True,errors='replace',timeout=300)
    stdout=output/'tectonic.stdout.txt';stderr=output/'tectonic.stderr.txt';stdout.write_text(r.stdout,encoding='utf-8');stderr.write_text(r.stderr,encoding='utf-8')
    result={'returncode':r.returncode,'input_hashes':inputs,'argv':argv,'stdout_sha256':audit.sha(stdout),'stderr_sha256':audit.sha(stderr),'original_paper_modified':False,'draft_not_submission_ready':True}
    pdf=output/'main.pdf'
    if pdf.is_file():
        import fitz
        doc=fitz.open(pdf);result['PDF_sha256']=audit.sha(pdf);result['pages']=len(doc)
        result['page_text_characters']=[len(p.get_text()) for p in doc]
    dump(output/'build_summary.json',result);audit.log('MANUSCRIPT_BUILD_END',tag=args.tag,summary_sha256=audit.sha(output/'build_summary.json'),**{k:result[k] for k in ['returncode','original_paper_modified']})
    print(json.dumps(result))
    if r.returncode:raise SystemExit(r.returncode)
if __name__=='__main__':main()
