"""Audited analytics follow-up; wait for COMPLETE49, never analyze partial results."""
import json,sys,time
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));import audit
STAGE=BASE/'e49_measurement_compat_v1'
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def main():
    out=STAGE/'analytics_followup_admission.json';assert not out.exists(),'Single analytics admission'
    lock=load(STAGE/'readiness_lock.json');source=BASE/'src/analyze_measurement_compat49_v1.py';expected=lock['code_input_hashes'][source.relative_to(BASE).as_posix()]
    assert audit.sha(source)==expected
    doc={'kind':'full49 analytics follow-up only','created_utc':audit.datetime.now(audit.timezone.utc).isoformat(),'controller_sha256':audit.sha(__file__),'readiness_sha256':audit.sha(STAGE/'readiness_lock.json'),'protocol_sha256':audit.sha(STAGE/'protocol.json'),'analyzer_sha256':expected,'generation_calls':0,'GPT_API_calls':0,'partial_analysis_forbidden':True}
    out.write_text(json.dumps(doc,indent=2)+'\n',encoding='utf-8');audit.log('COMPAT49_ANALYTICS_FOLLOWUP_ADMITTED',path=str(out),sha256=audit.sha(out),**doc)
    deadline=time.monotonic()+6*3600
    while not (STAGE/'complete.json').exists():
        ev=[json.loads(x) for x in (STAGE/'events.jsonl').read_text(encoding='utf-8').splitlines() if x.strip()]
        assert not any(x['kind']=='ABORT' for x in ev),'Batch guard abort; no partial analytics'
        assert time.monotonic()<deadline,'No COMPLETE49 before follow-up deadline'
        time.sleep(10)
    complete=load(STAGE/'complete.json');assert complete['status']=='COMPLETE' and complete['n']==49
    assert complete['results49_sha256']==audit.sha(STAGE/'results49.json') and audit.sha(source)==expected
    audit.run('compat49_analysis_v1',[sys.executable,'-B','-X','utf8',str(source)])
if __name__=='__main__':main()
