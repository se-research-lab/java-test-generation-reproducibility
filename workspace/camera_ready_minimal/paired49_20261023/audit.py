"""Audit/backup wrapper for an isolated, analytics-only camera-ready revision."""
import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[1]
RUN = ROOT / 'scripts_v2/results/runs/full300_merged_20260724_paper'
LEDGER = BASE / 'audit/events_serialized_v2.jsonl'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def canonical(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


def events():
    return [json.loads(s) for s in LEDGER.read_text(encoding='utf-8').splitlines()] if LEDGER.exists() else []


def _append_many(items):
    import msvcrt
    import time
    lockpath = BASE / 'audit/events.lock'
    with lockpath.open('a+b') as lock:
        lock.seek(0, 2)
        if lock.tell() == 0:
            lock.write(b'0'); lock.flush()
        deadline = time.monotonic() + 60
        while True:
            lock.seek(0)
            try:
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise TimeoutError('Audit ledger lock unavailable')
                time.sleep(0.02)
        try:
            prior = events()
            seq = prior[-1]['seq'] if prior else 0
            previous = prior[-1]['event_sha256'] if prior else None
            with LEDGER.open('a', encoding='utf-8') as f:
                for kind, data in items:
                    seq += 1
                    record = dict(seq=seq, timestamp_utc=datetime.now(timezone.utc).isoformat(),
                                  kind=kind, previous_sha256=previous, **data)
                    record['event_sha256'] = hashlib.sha256(canonical(record)).hexdigest()
                    f.write(json.dumps(record, ensure_ascii=False)+chr(10))
                    previous = record['event_sha256']
                f.flush(); os.fsync(f.fileno())
        finally:
            lock.seek(0); msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)


def log(kind, **data):
    _append_many([(kind, data)])

def verify_chain():
    previous = None
    for i, record in enumerate(events(), 1):
        digest = record.pop('event_sha256')
        assert record['seq'] == i and record['previous_sha256'] == previous
        assert hashlib.sha256(canonical(record)).hexdigest() == digest
        previous = digest


def protected_files():
    names = [ROOT/'Reviewer.txt', ROOT/'FISAT2026_Buildability_Mutation_Strength.pdf',
             ROOT/'RANG_BUOC_EVOSUITE_KHONG_TAC_DONG_RQ123.md',
             ROOT/'PLAN_CAMERA_READY_SPRINGER_GIU_PHAM_VI_NGHIEN_CUU.md',
             ROOT/'PLAN_TRIEN_KHAI_EVOSUITE_TRUOC_PHAN_TICH_49.md',
             ROOT/'review_reports/minimal_camera_ready_20261023/guard_rq123_frozen.py',
             ROOT/'review_reports/minimal_camera_ready_20261023/rq123_frozen_manifest.json',
             ROOT/'review_reports/reuse_audit_v1_20261021T112500/evidence/G0_AVAILABILITY_300.csv',
             ROOT/'scripts_v2/rbl4_v2_runner.py']
    names += list((ROOT/'paper').rglob('*'))
    names += list((ROOT/'scripts_v2/AgoneTest').glob('*.py'))
    names += list((RUN/'generated_tests').rglob('*'))
    names += [RUN/n for n in ['metrics_wide.csv','metrics_long.csv','manifest.json',
                             'generated_tests_manifest.csv','rq_decisions.csv','summary.csv']]
    return sorted({p for p in names if p.is_file()}, key=str)


def initialize():
    assert not LEDGER.exists(), 'Already initialized; do not overwrite audit/backup'
    for d in ['audit','backup/original','src','outputs','validation']:
        (BASE/d).mkdir(parents=True, exist_ok=True)
    log('INITIALIZE', scope='historical paired49 analytics only', original_edits_authorized=False,
        reviewer_points=['R1.2','R1.12 paired analysis','R2.3','R2.6 clustering'],
        bootstrap_note='audit.py was newly created before ledger initialization; no original file edited',
        audit_source_sha256=sha(__file__), python=sys.version, executable=sys.executable,
        platform=platform.platform())
    entries=[]
    for p in protected_files():
        rel=p.relative_to(ROOT)
        dest=BASE/'backup/original'/rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        assert not dest.exists()
        before=sha(p)
        shutil.copy2(p,dest)
        assert sha(dest)==before==sha(p)
        entries.append(dict(source=str(p),relative=rel.as_posix(),backup=str(dest),sha256=before,bytes=p.stat().st_size))
    manifest=BASE/'audit/protected_manifest.json'
    manifest.write_text(json.dumps(entries,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    log('BACKUP_COMPLETE', files=len(entries), manifest=str(manifest.relative_to(BASE)), sha256=sha(manifest))
    protocol={
        'scope':'post-review reanalysis of submitted G0/E0; not new generation or remeasurement',
        'outcomes_previously_seen':True,
        'selection':'all original class keys where gpt_compilation==1 and evosuite_compilation==1',
        'expected_n':49,'expected_repositories':15,'expected_build_tool':'Maven',
        'metrics':'archived per-class mutation percentages, same-class difference GPT minus E0 in pp',
        'primary_summaries':['arm mean/median','paired mean/median difference','win/loss/tie'],
        'uncertainty':'whole-repository percentile bootstrap; preserve pairs; class-weighted ratio of sums',
        'resamples':20000,'seed':20261023,'confidence':0.95,
        'secondary':['repository-equal mean difference','leave-one-repository-out mean difference',
                     'historical strict300 descriptive context and joint-failure ties'],
        'no_new_hypothesis_test':True,'no_new_NI_decision':True,
        'rq123':'frozen membership and every GPT observation; never fed from paired49',
        'validity_limit':'historical process/build gate; no new suite-pass or raw-mutant validity certification',
        'new_generation_calls':0,'new_java_measurement_jobs':0,
        'code_scope':'new standalone analytics/audit files only; original experiment and paper code read-only',
    }
    p=BASE/'protocol.json';p.write_text(json.dumps(protocol,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    log('PROTOCOL_RECORDED',path=p.name,sha256=sha(p),note='recorded before this execution; not preregistered before historical outcomes')
    print(json.dumps({'backup_files':len(entries),'workspace':str(BASE),'status':'INITIALIZED'}))


def verify():
    verify_chain()
    manifest=BASE/'audit/protected_manifest.json'
    backup_event=next(x for x in events() if x['kind']=='BACKUP_COMPLETE')
    assert sha(manifest)==backup_event['sha256'], 'Protected manifest changed'
    entries=json.loads(manifest.read_text(encoding='utf-8'))
    issues=[r['relative'] for r in entries if not Path(r['source']).is_file()
            or sha(r['source'])!=r['sha256'] or sha(r['backup'])!=r['sha256']]
    report={'protected_files':len(entries),'changed_or_missing':issues,'ledger_chain':'PASS',
            'original_and_backup_bytes_match':not issues}
    log('VERIFY_PROTECTED',**report)
    assert not issues, issues
    print(json.dumps(report,indent=2))


def run(name,argv):
    assert name.replace('_','').isalnum()
    stdout=BASE/f'audit/{name}.stdout.txt';stderr=BASE/f'audit/{name}.stderr.txt'
    assert not stdout.exists() and not stderr.exists(), 'Use a new attempt name; preserve old logs'
    log('COMMAND_START',name=name,argv=argv,cwd=str(BASE))
    start=datetime.now(timezone.utc)
    with stdout.open('w',encoding='utf-8') as out, stderr.open('w',encoding='utf-8') as err:
        result=subprocess.run(argv,cwd=BASE,stdout=out,stderr=err,
                              env={**os.environ,'PYTHONIOENCODING':'utf-8','PYTHONDONTWRITEBYTECODE':'1'})
    log('COMMAND_END',name=name,returncode=result.returncode,
        duration_seconds=(datetime.now(timezone.utc)-start).total_seconds(),
        stdout=str(stdout.relative_to(BASE)),stdout_sha256=sha(stdout),
        stderr=str(stderr.relative_to(BASE)),stderr_sha256=sha(stderr))
    print(stdout.read_text(encoding='utf-8'))
    if result.returncode:
        print(stderr.read_text(encoding='utf-8'))
        raise SystemExit(result.returncode)


def register():
    prior={e['path']:e['sha256'] for e in events() if e['kind']=='NEW_FILE_REGISTERED'}
    prior.update({e['path']:e['after_sha256'] for e in events() if e['kind']=='FILE_REVISION'})
    pending=[]
    for p in sorted(BASE.rglob('*')):
        if not p.is_file() or p.is_relative_to(BASE/'backup') or p.is_relative_to(BASE/'audit'):
            continue
        rel=p.relative_to(BASE).as_posix()
        if rel in prior:
            assert sha(p)==prior[rel], f'Unrecorded edit: {rel}; backup before editing'
        else:
            pending.append(('NEW_FILE_REGISTERED',dict(path=rel,sha256=sha(p),bytes=p.stat().st_size,
                change_type='new isolated file; no original overwritten')))
    _append_many(pending)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['init','verify','register','run'])
    parser.add_argument('args',nargs=argparse.REMAINDER);a=parser.parse_args()
    if a.action=='init':initialize()
    elif a.action=='verify':verify()
    elif a.action=='register':register()
    else:run(a.args[0],a.args[1:])
