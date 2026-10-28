"""Wait for fixed49 closure then validate/analyse once; no experiment reconfiguration."""
import json,subprocess,sys,time
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));import audit
STAGE=BASE/'e49_driver';DEST=STAGE/'postrun_v2'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def event(kind,**data):
    from datetime import datetime,timezone
    row={'timestamp_utc':datetime.now(timezone.utc).isoformat(),'kind':kind,**data}
    with (DEST/'events.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(row)+'\n')
    audit.log('E49_POSTRUN_V2_'+kind,**data);print(json.dumps(row),flush=True)
def main():
    DEST.mkdir(exist_ok=False)
    analyzer=BASE/'src/analyze_e49_final_v2.py'
    with (DEST/'admission.json').open('x',encoding='utf-8') as f:json.dump({'analyzer_sha256':audit.sha(analyzer),'protocol49_sha256':audit.sha(STAGE/'protocol49.json'),'scope':'wait49 then readonlyrawvalidation and supplementaryanalytics; no generation/configchange','no_GPT':True},f,indent=2)
    lock=read(DEST/'admission.json');event('WAITING_COMPLETE49')
    deadline=time.monotonic()+25*3600
    while True:
        results=STAGE/'results49.json';archive=STAGE/'archive_final_v4/summary.json'
        lines=(STAGE/'resume_guard02/events.jsonl').read_text(encoding='utf-8').splitlines()
        try:last=json.loads(lines[-1])['kind'] if lines else None
        except json.JSONDecodeError:last=None
        if last=='STOPPED':raise RuntimeError('Benchmark stopped; no final analysis emitted')
        if last=='COMPLETE' and results.exists() and archive.exists():
            try:result_rows=read(results);archive_summary=read(archive)
            except json.JSONDecodeError:time.sleep(1);continue
            assert len(result_rows)==49 and archive_summary['all49_complete']
            break
        if time.monotonic()>deadline:raise TimeoutError('49 completion deadline; raw artifacts preserved')
        time.sleep(10)
    assert audit.sha(analyzer)==lock['analyzer_sha256'] and audit.sha(STAGE/'protocol49.json')==lock['protocol49_sha256']
    event('VALIDATING_AND_ANALYSING_FIXED49')
    cmd=[sys.executable,'-B','-X','utf8',str(BASE/'audit.py'),'run','analyze_e49_final_v2',sys.executable,'-B','-X','utf8',str(analyzer)]
    result=subprocess.run(cmd,cwd=BASE,timeout=1800)
    assert result.returncode==0,'Analyzer failed; no automatic correction/tuning'
    audit.verify();event('COMPLETE',n=49,report='outputs/e49_final_v2/BAO_CAO_E49.md',G0_updated=False)
if __name__=='__main__':
    try:main()
    except Exception as exc:
        if DEST.exists():event('STOPPED',error_type=type(exc).__name__,detail=str(exc))
        raise
