"""Isolated publisher-format update only; closed v3 and experimental code stay untouched."""
import difflib,hashlib,json,os,re,shutil,subprocess,sys
from pathlib import Path
B=Path(__file__).resolve().parents[1];sys.path.insert(0,str(B));import audit
OLD=B/'manuscript_revision_v3_compat49';NEW=B/'manuscript_revision_v4_submission';S=NEW/'source'
sha=audit.sha

def dump(p,x):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f:json.dump(x,f,ensure_ascii=False,indent=2);f.write('\n')

def main():
    assert not NEW.exists()
    audit.log('NEW_FILE_REGISTERED',path=Path(__file__).relative_to(B).as_posix(),sha256=sha(__file__),bytes=Path(__file__).stat().st_size,change_type='new publisher-only manuscript copy/build script')
    closed=json.loads((B/'audit/measurement49_camera_ready_registry_v1.json').read_text(encoding='utf-8'))
    for row in closed['files']:assert sha(B/row['path'])==row['sha256'],row['path']
    manifest=json.loads((OLD/'output/source_manifest.json').read_text(encoding='utf-8'))['files']
    assert len(manifest)==15
    S.mkdir(parents=True)
    for name,h in manifest.items():
        old=OLD/'source'/name;dest=S/name;dest.parent.mkdir(parents=True,exist_ok=True)
        assert sha(old)==h;shutil.copy2(old,dest);assert sha(old)==h==sha(dest)
    dump(NEW/'source_copy_manifest.json',{'from':str(OLD/'source'),'files':manifest,'excluded':'three unused SLR page images; not manuscript build inputs','original_modified':False})
    before={n:sha(S/n) for n in manifest}
    allowed=['sections/03_method.tex','sections/08_disclosure.tex']
    patch=[]
    for n in allowed:
        p=S/n;old=p.read_text(encoding='utf-8');backup=NEW/'backups/publisher_update_v1'/n
        backup.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,backup);assert sha(backup)==before[n]
        if '03_method' in n:
            new=old.replace('Holm sensitivity over RQ1','Holm sensitivity~\\cite{ref6} over RQ1').replace('whole-repository percentile-bootstrap intervals for the class-weighted mean','whole-repository percentile-bootstrap intervals~\\cite{ref4} for the class-weighted mean')
            assert new!=old and new.count('\\cite{ref4}')==new.count('\\cite{ref6}')==1
            assert re.sub(r'~\\cite\{ref[46]\}','',new)==old
        else:
            needle='The authors declare no external funding and no conflicts of interest.'
            assert old.count(needle)==1
            credits='''\\begingroup\\small
\\noindent\\textbf{Acknowledgements.} An AI assistant (OpenAI Codex) supported post-review code auditing, supplementary analysis and manuscript drafting. This assistance is separate from the GPT-4o-mini generation treatment. The authors remain responsible for verifying the analyses, references and final text. This study received no external funding.\\par
\\noindent\\textbf{Disclosure of Interests.} The authors have no conflicts of interest to declare.\\par
\\endgroup'''
            new=old.replace(needle,'').rstrip()+'\n\n'+credits+'\n'
        with p.open('w',encoding='utf-8',newline='\n') as f:f.write(new)
        diff=''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='v3/'+n,tofile='v4/'+n))
        df=NEW/'backups/publisher_update_v1'/(Path(n).name+'.diff');df.write_text(diff,encoding='utf-8')
        audit.log('FILE_REVISION',path=p.relative_to(B).as_posix(),before_sha256=before[n],after_sha256=sha(p),backup=backup.relative_to(B).as_posix(),backup_sha256=sha(backup),reason='Springer/FISAT publisher guidance: cite existing bootstrap/Holm references; acknowledge substantive AI support and separate conflict statement; no scientific score/config changes')
        patch.append({'path':n,'before':before[n],'after':sha(p),'backup_sha256':sha(backup),'diff_sha256':sha(df)})
    after={n:sha(S/n) for n in manifest}
    assert sorted(n for n in before if before[n]!=after[n])==sorted(allowed)
    dump(NEW/'publisher_update_manifest.json',{'allowed_files':allowed,'changes':patch,'all_other_13_sources_byte_identical':True,'historical_results_and_supplement_byte_identical':True,'corresponding_author_metadata_retained_as_instructed_by_user':2,'single_corresponding_publisher_rule_requires_author_resolution_or_organizer_exception':True,'experiment_or_API_calls':0})
    # Use an isolated byte-copy of the already functioning cached LaTeX runtime.
    cache=NEW/'tectonic_cache';cache.mkdir();cache_rows=[]
    for p in sorted((OLD/'tectonic_cache').rglob('*')):
        if not p.is_file():continue
        rel=p.relative_to(OLD/'tectonic_cache');dest=cache/rel;dest.parent.mkdir(parents=True,exist_ok=True)
        h=sha(p);shutil.copy2(p,dest);assert sha(dest)==h==sha(p)
        cache_rows.append({'relative':rel.as_posix(),'sha256':h,'bytes':p.stat().st_size})
    dump(NEW/'tectonic_cache_copy_manifest.json',cache_rows)
    tool=B/'tools/tectonic-0.17.0-x86_64-pc-windows-msvc/tectonic.exe'
    assert sha(tool)=='99ffcfdbf1ebf8bdda9e791942e3d06aedb12463fddc33f07de6f5211c8bf08d'
    build=NEW/'build_01';build.mkdir();env=dict(os.environ);env['TECTONIC_CACHE_DIR']=str(cache)
    argv=[str(tool),'--only-cached','--untrusted','--keep-logs','--keep-intermediates','--outdir',str(build),str(S/'main.tex')]
    audit.log('MANUSCRIPT_BUILD_START',revision='v4_submission',argv=argv,cwd=str(S),input_hashes=after,tool_sha256=sha(tool))
    r=subprocess.run(argv,cwd=S,env=env,capture_output=True,text=True,errors='replace',timeout=300)
    (build/'tectonic.stdout.txt').write_text(r.stdout,encoding='utf-8');(build/'tectonic.stderr.txt').write_text(r.stderr,encoding='utf-8')
    assert r.returncode==0,(r.stdout,r.stderr)
    import fitz
    doc=fitz.open(build/'main.pdf');assert len(doc)==15,len(doc)
    log=(build/'main.log').read_text(encoding='utf-8',errors='replace')
    severe=[l for l in log.splitlines() if re.search(r'Overfull|Missing character|LaTeX Warning:.*(?:undefined|multiply defined)|^!',l)]
    assert not severe,severe
    texts=[p.get_text() for p in doc]
    assert not any('\ufffd' in t or '??' in t for t in texts)
    olddoc=fitz.open(OLD/'build_04/main.pdf')
    # Numeric tokens in all scientific sections remain identical; only the citation
    # identifiers for already-listed sources can be newly inserted in Methods.
    cite_set=set();bib_set=set()
    alltext='\n'.join(p.read_text(encoding='utf-8') for p in S.rglob('*.tex'))
    for m in re.finditer(r'\\cite(?:\[[^\]]*\])?\{([^}]+)\}',alltext):cite_set.update(m[1].split(','))
    bib_set=set(re.findall(r'\\bibitem\{([^}]+)\}',alltext));assert cite_set==bib_set
    page_map=[]
    for i,t in enumerate(texts):
        headings=[l for l in t.splitlines() if re.match(r'^(?:[1-7](?:\.[1-9])?\s|References$|Acknowledgements\.|Disclosure of Interests\.|Table [1-5]\.)',l)]
        page_map.append({'page':i+1,'headings':headings,'chars':len(t)})
    result={'returncode':r.returncode,'pages':len(doc),'PDF_sha256':sha(build/'main.pdf'),'input_hashes':after,'tool_sha256':sha(tool),'cite_keys':sorted(cite_set),'bib_keys':sorted(bib_set),'citation_keys_complete':True,'severe_latex_errors':severe,'underfull_entries':[l for l in log.splitlines() if 'Underfull' in l],'page_map':page_map,'draft_not_submission_ready':True,'experiment_or_API_calls':0,'v3_closed_registry_unchanged':True}
    dump(build/'build_summary.json',result)
    render=NEW/'build_01/rendered';render.mkdir();pngs={};changed=[]
    for i,p in enumerate(doc):
        target=render/f'page_{i+1:02d}.png';p.get_pixmap(matrix=fitz.Matrix(1.8,1.8),alpha=False).save(target);pngs[target.name]=sha(target)
        if sha(target)!=sha(OLD/f'build_04/rendered/page_{i+1:02d}.png'):changed.append(i+1)
    dump(render/'render_manifest.json',{'PDF_sha256':sha(build/'main.pdf'),'PNG_hashes':pngs,'pages_changed_vs_verified_v3':changed,'unchanged_pages_reuse_prior_fullsize_QA':True,'changed_pages_visual_review_required':True,'renderer':'PyMuPDF fallback; Poppler unavailable'})
    audit.log('MANUSCRIPT_BUILD_END',revision='v4_submission',PDF_sha256=sha(build/'main.pdf'),pages=len(doc),changed_rendered_pages=changed,summary_sha256=sha(build/'build_summary.json'))
    print(json.dumps({'status':'BUILT_PENDING_VISUAL_QA','pages':len(doc),'changed_pages':changed,'PDF_sha256':sha(build/'main.pdf'),'page_map':page_map},indent=2))
if __name__=='__main__':main()
