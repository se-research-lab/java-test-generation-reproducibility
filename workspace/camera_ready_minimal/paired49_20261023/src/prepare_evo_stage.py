"""Create isolated code checkout and pre-edit backup; never modify originals."""
import json
import shutil
import sys
from pathlib import Path

BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE))
import audit


def main():
    audit.verify()
    stage=BASE/'evo_patch'
    assert not stage.exists(), 'New stage only; do not reset evidence'
    for folder in ['backup','working/AgoneTest','reports','fixtures','artifacts','patches']:
        (stage/folder).mkdir(parents=True)
    names=['mavenLib.py','gradleLib.py','utils.py','agone_test.py','toolchains.py','errorCorrection.py']
    records=[]
    for name in names:
        src=BASE/'backup/original/scripts_v2/AgoneTest'/name
        assert audit.sha(src)==audit.sha(audit.ROOT/'scripts_v2/AgoneTest'/name)
        bak=stage/'backup'/name;work=stage/'working/AgoneTest'/name
        shutil.copy2(src,bak);shutil.copy2(src,work)
        records.append({'file':name,'original_sha256':audit.sha(src),'backup':str(bak.relative_to(BASE)),
                        'working':str(work.relative_to(BASE))})
    protocol={'stage':'EvoSuite generation profile only, plus raw-evidence inventory49',
              'reviewer_points':['R2.1','R1.3','R1.11','R3 assertions/runtime'],
              'scope':['copy before edits','Maven generation flags only','explicit legacy/assertions-enabled profile',
                       'no Gradle changes','no shared evaluator changes','synthetic fixture only'],
              'forbidden':['GPT API','changes to original scripts/paper','RQ123 data updates','benchmark generation'],
              'baseline_limit':'current audited source; exact historical execution source provenance not yet certified',
              'runtime_integration_status':'not complete; profile success is not end-to-end readiness',
              'benchmark_scope_not_frozen':True,
              'fixture_seed':20261023,'search_budget':60,'generation_outer_timeout':240,
              'fixture_not_in_primary_data':True}
    (stage/'protocol.json').write_text(json.dumps(protocol,indent=2)+'\n',encoding='utf-8')
    (stage/'pre_edit_manifest.json').write_text(json.dumps(records,indent=2)+'\n',encoding='utf-8')
    audit.log('STAGE_SCOPE_RECORDED',path='evo_patch/protocol.json',sha256=audit.sha(stage/'protocol.json'),
              note='extends analytics stage with separately scoped code preparation; benchmark not launched')
    audit.log('PRE_EDIT_BACKUP_COMPLETE',files=records,reviewer='R2.1',originals_unchanged=True)
    print(json.dumps({'status':'PRE_EDIT_BACKUP_COMPLETE','code_files':len(records),'stage':str(stage)}))


if __name__=='__main__':main()
