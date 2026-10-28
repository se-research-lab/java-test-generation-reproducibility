"""Wait for full49 official analysis then run independent raw/statistical audit."""
import json,sys,time
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));import audit
STAGE=BASE/'e49_measurement_compat_v1';SOURCE=BASE/'src/independent_measurement49_raw_audit_v1.py';EXPECTED='74f02c729f3d72d9a43c150366e5254f368ffc0eb42eab2f1182351f82545b28'
def main():
    p=STAGE/'independent_followup_admission.json';assert not p.exists();assert audit.sha(SOURCE)==EXPECTED
    doc={'created_utc':audit.datetime.now(audit.timezone.utc).isoformat(),'controller_sha256':audit.sha(__file__),'auditor_sha256':EXPECTED,'scope':'raw audit after COMPLETE49+official output, no experiment/API','partial_results_refused':True};p.write_text(json.dumps(doc,indent=2)+'\n',encoding='utf-8');audit.log('COMPAT49_INDEPENDENT_FOLLOWUP',path=str(p),sha256=audit.sha(p),admission=doc)
    end=time.monotonic()+6*3600;official=BASE/'outputs/e49_measurement_compat_v1/output_manifest.json'
    while not official.exists():
        ev=[json.loads(x) for x in (STAGE/'events.jsonl').read_text(encoding='utf-8').splitlines() if x.strip()];assert not any(x['kind']=='ABORT' for x in ev),'Batch aborted; no partial audit'
        failures=[x for x in audit.events() if x['kind']=='COMMAND_END' and x.get('name')=='compat49_analysis_v1' and x.get('returncode')!=0];assert not failures,'Official analysis failed; stop independent follow-up'
        assert time.monotonic()<end,'Follow-up deadline reached';time.sleep(10)
    assert json.loads((STAGE/'complete.json').read_text(encoding='utf-8'))['n']==49 and audit.sha(SOURCE)==EXPECTED
    audit.run('compat49_independent_raw_v1',[sys.executable,'-B','-X','utf8',str(SOURCE)])
if __name__=='__main__':main()
