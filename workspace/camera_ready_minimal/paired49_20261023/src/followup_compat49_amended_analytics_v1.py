"""Only after completed amended49: official analytics then independent raw/statistical audit."""
import json,sys,time
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));import audit
STAGE=BASE/'e49_measurement_compat_v1';AMEND=STAGE/'inspection_amendment_v1.json';EXPECTED='47d1a6ab4b211ea14c19e82ae798e666055fd043e3497a872395a6840923ddf2'
def main():
    assert audit.sha(AMEND)==EXPECTED;am=json.loads(AMEND.read_text(encoding='utf-8'));ad=STAGE/'amended_analytics_followup_admission.json';assert not ad.exists()
    doc={'created_utc':audit.datetime.now(audit.timezone.utc).isoformat(),'controller_sha256':audit.sha(__file__),'inspection_amendment_sha256':EXPECTED,'generation_calls':0,'GPT_API_calls':0,'partial_analysis_forbidden':True};ad.write_text(json.dumps(doc,indent=2)+'\n',encoding='utf-8');audit.log('AMENDED_ANALYTICS_FOLLOWUP_ADMITTED',path=str(ad),sha256=audit.sha(ad),admission=doc)
    deadline=time.monotonic()+6*3600
    while not (STAGE/'complete.json').exists():
        try:ev=[json.loads(x) for x in (STAGE/'events.jsonl').read_text(encoding='utf-8').splitlines() if x.strip()]
        except json.JSONDecodeError:time.sleep(1);continue
        assert not any(x['kind']=='ABORT' and x['timestamp_utc']>am['created_utc'] for x in ev),'Amended batch aborted; no partial analytics'
        assert time.monotonic()<deadline,'Deadline awaiting COMPLETE49';time.sleep(10)
    complete=json.loads((STAGE/'complete.json').read_text(encoding='utf-8'));assert complete['status']=='COMPLETE' and complete['n']==49 and complete['inspection_amendment_sha256']==EXPECTED
    assert complete['results49_sha256']==audit.sha(STAGE/'results49.json')
    for name,path in [('compat49_analysis_v2','src/analyze_measurement_compat49_v2.py'),('compat49_independent_raw_v2','src/independent_measurement49_raw_audit_v2.py')]:
        assert audit.sha(AMEND)==EXPECTED and audit.sha(BASE/path)==am['code_input_hashes'][path]
        audit.run(name,[sys.executable,'-B','-X','utf8',str(BASE/path)])
if __name__=='__main__':main()
