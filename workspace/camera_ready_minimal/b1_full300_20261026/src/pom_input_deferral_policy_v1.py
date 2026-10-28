"""Fixed frozen-input quarantine; no POM repair, score or experiment launch."""
import json, hashlib, sqlite3
from pathlib import Path
from maven_adapter_v1 import R, GuardAbort, sha, dump

REVIEW=R/'audit/pom_input_deferrals_v2/result.json'
DIRECTORY=R/'runtime/pom_input_deferrals_v1'
EXPECTED=[72,112,119,163,173,211,220,269,275,294]

def load(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))

def ensure(ok,why):
    if not ok:
        raise GuardAbort(why)

def decisions():
    report=load(REVIEW)
    ensure(report['status']=='PASS_READONLY_FROZEN_POM_REVIEW' and report['unparseable_indices']==EXPECTED,
           'POM quarantine requires the exact reviewed frozen-input set')
    ensure(report['new_generation_calls']==report['new_measurement_calls']==report['GPT_API_calls']==0,
           'Frozen-input review must have no experiment calls')
    return report['deferrals']

def verify_decision(row):
    i=row['sample_index_1based']
    ensure(i in EXPECTED and row['status']=='FROZEN_INPUT_XML_UNPARSEABLE_UNSCORED', 'Unknown POM quarantine')
    ensure(row['score'] is None and row['zero_fill_allowed'] is False and row['input_repair_allowed'] is False,
           'POM quarantine cannot invent score or permit input repair')
    manifest=R/row['snapshot_manifest']
    ensure(sha(manifest)==row['snapshot_manifest_sha256'],'Frozen source manifest drift')
    entry=next(r for r in load(manifest)['files'] if r['relative']==row['pom_relative'])
    ensure(entry['sha256']==row['pom_sha256'] and entry['bytes']==row['pom_bytes'],'Frozen POM identity drift')
    with sqlite3.connect((R/'inputs/snapshot_v3/content.sqlite3').as_uri()+'?mode=ro',uri=True) as conn:
        nbytes,data=conn.execute('SELECT nbytes,data FROM blobs WHERE sha256=?',(row['pom_sha256'],)).fetchone()
    ensure(nbytes==len(data)==row['pom_bytes'] and hashlib.sha256(data).hexdigest()==row['pom_sha256'], 'Frozen POM blob drift')
    from xml.etree import ElementTree as ET
    try:
        ET.fromstring(data)
    except ET.ParseError as ex:
        ensure(str(ex)==row['error'] and ex.code==27,'POM parse error differs from reviewed signature')
    else:
        raise GuardAbort('Reviewed POM unexpectedly parses')
    base=R/'jobs'/f'{i:03d}'
    if i==72:
        ensure(sha(base/'artifact_manifest.json')==row['original_job_archive_sha256'],'Original072 archive drift')
        ensure(not (base/'result.json').exists() and not list((base/'commands').iterdir()),'072 acquired an unreviewed result/process')
    else:
        ensure(not base.exists(),'Never-attempted quarantined POM acquired a job folder')
    return row

def register_fixed_set():
    for row in decisions():
        verify_decision(row)
        path=DIRECTORY/f"{row['sample_index_1based']:03d}.json"
        ensure(not path.exists(),'POM receipt already exists; no overwrite')
        dump(path,row)

def verify_fixed_set():
    result=[]
    for row in decisions():
        ensure(load(DIRECTORY/f"{row['sample_index_1based']:03d}.json")==row,'POM quarantine receipt drift')
        verify_decision(row)
        result.append(row['sample_index_1based'])
    return result
