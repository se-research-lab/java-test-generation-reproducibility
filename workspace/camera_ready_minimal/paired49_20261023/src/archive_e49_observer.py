"""Read-only observer of completed jobs; archive raw evidence without altering execution."""
import json,os,shutil,sys,time
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));import audit
STAGE=BASE/'e49_driver';out=STAGE/'artifact_archive';out.mkdir(exist_ok=False)
jobs=json.loads((STAGE/'input_manifest49.json').read_text(encoding='utf-8'));done=set();deadline=time.monotonic()+25*3600
while len(done)<49:
    for job in jobs:
        index=job['job_index'];summary=STAGE/('job_result_%02d.json'%index)
        if index in done or not summary.exists():continue
        # Master writes this small JSON in one closed write; retry if observed mid-write.
        try:result=json.loads(summary.read_text(encoding='utf-8'))
        except json.JSONDecodeError:continue
        work=STAGE/'jobs'/('%02d'%index);module=work/'repo'/job['module'];dest=out/('%02d'%index);dest.mkdir()
        files=[]
        sources=[]
        for rel in ['target/surefire-reports','target/site/jacoco','target/pit-reports']:
            root=module/rel
            if root.is_dir():sources.extend(p for p in root.rglob('*') if p.is_file())
        cp=module/'target/evosuite-classpath.txt'
        if cp.exists():sources.append(cp)
        for path in [work/'generated_manifest.json',work/'pom_before_manifest.json',work/'pom_after_manifest.json',summary]:
            if path.exists():sources.append(path)
        classroot=module/'target/classes'/Path(*job['package'].split('.'))
        if classroot.is_dir():
            sources.extend(p for p in classroot.glob(job['focal_class']+'*.class') if p.stem==job['focal_class'] or p.stem.startswith(job['focal_class']+'$'))
        for p in sorted(set(sources)):
            rel=p.relative_to(STAGE);target=dest/rel;target.parent.mkdir(parents=True,exist_ok=True)
            h=audit.sha(p);shutil.copy2(p,target);assert h==audit.sha(p)==audit.sha(target)
            files.append({'source':str(p.relative_to(BASE)),'copy':str(target.relative_to(BASE)),'sha256':h,'bytes':p.stat().st_size})
        deps=[]
        if cp.exists():
            for raw in cp.read_text(encoding='utf-8-sig').strip().split(os.pathsep):
                p=Path(raw)
                if p.is_file() and p.suffix.lower()=='.jar':deps.append({'path':str(p),'sha256':audit.sha(p),'bytes':p.stat().st_size})
        manifest={'class_key':job['class_key'],'job_index':index,'result_sha256':audit.sha(summary),
          'raw_artifact_copies':files,'resolved_dependency_jars':deps,'source_jobs_modified':False,
          'scope':'post-completion read-only evidence archive; no measurement or result changes'}
        path=dest/'manifest.json'
        with path.open('x',encoding='utf-8') as f:json.dump(manifest,f,indent=2)
        audit.log('E49_COMPLETED_JOB_EVIDENCE_ARCHIVED',class_key=job['class_key'],job_index=index,files=len(files),dependency_jars=len(deps),manifest_sha256=audit.sha(path))
        done.add(index);print(json.dumps({'archived_jobs':len(done),'job_index':index,'raw_files':len(files)}),flush=True)
    if time.monotonic()>deadline:raise TimeoutError('Observer deadline; completed-job copies retained')
    if len(done)<49:
        events=(STAGE/'controller_events.jsonl').read_text(encoding='utf-8').splitlines()
        if events and json.loads(events[-1])['kind']=='PIPELINE_STOPPED':break
        time.sleep(2)
report={'completed_jobs_archived':len(done),'expected49':49,'original_job_files_modified':False,'all49_complete':len(done)==49}
with (out/'summary.json').open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
audit.log('E49_EVIDENCE_OBSERVER_END',**report)
