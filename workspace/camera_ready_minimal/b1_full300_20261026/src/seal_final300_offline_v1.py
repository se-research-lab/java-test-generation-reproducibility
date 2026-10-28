"""Seal private offline analysis deliverables; never starts an experiment."""
import csv,hashlib,json,sys,shutil
from pathlib import Path
from datetime import datetime,timezone
import psutil

R=Path(__file__).resolve().parents[1];A=R/'completion_amendment_v1';OUT=A/'final300_offline_v1';B=R.parent/'paired49_20261023'
sys.path.insert(0,str(B));import audit
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,data):
    with p.open('x',encoding='utf-8') as f:json.dump(data,f,ensure_ascii=False,indent=2);f.write('\n')

def main():
    assert not (OUT/'SHA256SUMS.txt').exists()
    rows=load(OUT/'class_results300.json');stats=load(OUT/'statistics.json')
    refs={}
    def scan(obj):
        if isinstance(obj,dict):
            if isinstance(obj.get('path'),str) and isinstance(obj.get('sha256'),str):
                key=obj['path'];assert key not in refs or refs[key]==obj['sha256'];refs[key]=obj['sha256']
            for v in obj.values():scan(v)
        elif isinstance(obj,list):
            for v in obj:scan(v)
    scan(rows);scan(load(OUT/'FORMULA_AUDIT.json'))
    for filename in ['manifest300.json','completion_amendment_v1/checkpoint30_v1/selected30.json','completion_amendment_v1/input_audit/class_census300.json','completion_amendment_v1/analysis300_checkpoint_v2/protocol.json']:
        p=R/filename;refs[str(p)]=sha(p)
    for name in ['POLICY.md','MAVEN_POLICY_ANNEX.md','PARTIAL_PIT_POLICY_V3.md','STAGE_POLICY_ANNEX_V2.md']:
        refs[str(A/name)]=sha(A/name)
    for name in ['reconcile300_checkpoint_v3.py','offline_evidence_reader_v1.py','compute_checkpoint300_statistics_v1.py','verify_final300_offline_v1.py','seal_final300_offline_v1.py']:
        refs[str(R/'src'/name)]=sha(R/'src'/name)
    for p,h in refs.items():assert sha(p)==h,p
    write(OUT/'EXTERNAL_EVIDENCE_MANIFEST.json',{'verified_at_utc':datetime.now(timezone.utc).isoformat(),'files':[{'path':p,'sha256':h} for p,h in sorted(refs.items())]})
    fields=['index','class_key','repo_id','build_tool','seed','fixed49','amendment30','generation','compile_production_evidence','compile_test_evidence','test_execution','PIT','process_gate','focal_mutants','killed_mutants','E1_TIMED_OUT_mutants','observed_mutation_percent','end_to_end_score_percent','score_basis','G0_strict','E0_strict','G0_build','E0_build','amendment30_measurement_unresolved','end_to_end_unresolved','nonpassing_suite_with_valid_PIT']
    with (OUT/'class_summary300.csv').open('x',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows({k:r[k] for k in fields} for r in rows)
    workers=[];inspect_errors=[]
    for p in psutil.process_iter(['pid','name','cmdline','create_time']):
        if p.pid==psutil.Process().pid:continue
        try:
            name=(p.info['name'] or '').lower();args=p.info['cmdline'] or [];cmd=' '.join(args).lower()
            java=name in ['java.exe','javaw.exe']
            candidate=name in ['python.exe','pythonw.exe','cmd.exe','powershell.exe'] and any('b1_full300_20261026' in x.lower() or 'repeated_subset' in x.lower() for x in args)
            dispatcher=candidate and any(('dispatcher' in x.lower() or 'worker' in x.lower() or 'run_completion_' in x.lower()) and x.lower().endswith(('.py','.ps1','.cmd')) for x in args)
            if java or dispatcher:workers.append({'pid':p.pid,'name':name,'kind':'java_process' if java else 'experiment_dispatcher_candidate'})
        except (psutil.AccessDenied,psutil.NoSuchProcess):inspect_errors.append(p.pid)
    write(OUT/'PROCESS_SNAPSHOT.json',{'at_utc':datetime.now(timezone.utc).isoformat(),'experiment_worker_candidates':workers,'inspection_errors':inspect_errors,'commands_not_executed':True})
    assert not workers,workers
    for label in ['final300_original_and_backup_guard','final300_rq123_frozen_guard']:
        for ext in ['stdout.txt','stderr.txt']:
            p=B/'audit'/f'{label}.{ext}';dest=OUT/p.name;assert not dest.exists();shutil.copy2(p,dest)
    files=[{'path':p.relative_to(OUT).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(OUT.rglob('*')) if p.is_file()]
    write(OUT/'MANIFEST.json',{'at_utc':datetime.now(timezone.utc).isoformat(),'state':'SEALED_OFFLINE_TABLE_300_NOT_COMPLETE_E1_FULL300','files':files,'external_evidence_files':len(refs),'new_experiments':0,'original_files_overwritten':0})
    paths=sorted(p for p in OUT.rglob('*') if p.is_file())
    with (OUT/'SHA256SUMS.txt').open('x',encoding='utf-8') as f:
        for p in paths:f.write(sha(p)+'  '+p.relative_to(OUT).as_posix()+'\n')
    audit.log('FINAL300_OFFLINE_SEALED',path=str(OUT),manifest_sha256=sha(OUT/'MANIFEST.json'),hash_list_sha256=sha(OUT/'SHA256SUMS.txt'),external_files=len(refs),new_experiments=0,worker_candidates=workers)
    print(json.dumps({'status':'SEALED','directory':str(OUT),'files':len(paths),'external_hashes_verified':len(refs),'workers':workers,'process_inspection_errors':inspect_errors,'full300_complete':False},indent=2))
if __name__=='__main__':main()
