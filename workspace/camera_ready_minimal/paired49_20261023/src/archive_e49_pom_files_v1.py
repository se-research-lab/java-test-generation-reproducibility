"""Read-only archive of completed E49 POM files; never computes Maven effective POM."""
import json,shutil,sys,time
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));import audit
STAGE=BASE/'e49_driver'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def main():
    out=STAGE/'pom_file_archive_v1';out.mkdir(exist_ok=False)
    jobs=read(STAGE/'input_manifest49.json');done=set();deadline=time.monotonic()+25*3600
    while len(done)<49:
        for job in jobs:
            idx=job['job_index'];summary=STAGE/('job_result_%02d.json'%idx)
            if idx in done or not summary.exists():continue
            try:row=read(summary)
            except json.JSONDecodeError:continue
            assert row['class_key']==job['class_key']
            work=STAGE/'jobs'/('%02d'%idx);dest=out/('%02d'%idx);dest.mkdir()
            before=read(work/'pom_before_manifest.json') if (work/'pom_before_manifest.json').exists() else {}
            after=read(work/'pom_after_manifest.json') if (work/'pom_after_manifest.json').exists() else {}
            records=[]
            for rel in sorted(set(before)|set(after)):
                path=Path(rel);assert not path.is_absolute() and '..' not in path.parts
                for source,expected,kind in [(work/path,after.get(rel),'post_integration_POM'),(work/'backup_poms'/path,before.get(rel),'pre_integration_backup')]:
                    assert source.resolve().is_relative_to(work.resolve())
                    rec={'source':str(source.relative_to(BASE)),'kind':kind,'expected_sha256':expected,'present':source.is_file()}
                    if source.is_file():
                        h=audit.sha(source);target=dest/source.relative_to(STAGE);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
                        assert h==audit.sha(source)==audit.sha(target)
                        rec.update(copy=str(target.relative_to(BASE)),sha256=h,bytes=source.stat().st_size,matches_declared_hash=None if expected is None else h==expected)
                    records.append(rec)
            report={'job_index':idx,'class_key':job['class_key'],'result_sha256':audit.sha(summary),'files':records,'source_modified':False,
                'limit':'actual saved POM files, not resolved Maven effective-POM/dependency model',
                'mismatches_or_missing':[r['source'] for r in records if not r['present'] or r.get('matches_declared_hash') is False]}
            p=dest/'manifest.json'
            with p.open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
            audit.log('E49_COMPLETED_POM_FILES_ARCHIVED',job_index=idx,files=len(records),issues=report['mismatches_or_missing'],manifest_sha256=audit.sha(p))
            done.add(idx);print(json.dumps({'archived':len(done),'job_index':idx,'POM_files':len(records),'issues':len(report['mismatches_or_missing'])}),flush=True)
        if time.monotonic()>deadline:raise TimeoutError('POM observer deadline; existing evidence preserved')
        if len(done)<49:
            path=STAGE/'resume_guard01/events.jsonl';lines=path.read_text(encoding='utf-8').splitlines() if path.exists() else []
            if lines and json.loads(lines[-1])['kind']=='STOPPED':break
            time.sleep(2)
    summary={'completed_jobs':len(done),'expected':49,'all49_complete':len(done)==49,'source_modified':False}
    with (out/'summary.json').open('x',encoding='utf-8') as f:json.dump(summary,f,indent=2)
    audit.log('E49_POM_FILES_OBSERVER_END',**summary)
if __name__=='__main__':main()
