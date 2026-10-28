"""Read-only bounded audit of critical measurement/runtime cache groups. No Java/Maven."""
import concurrent.futures
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
import audit
CACHE = BASE / 'e1_compatibility_diagnostic_v1/maven_cache'
MANIFEST = BASE / 'e1_compatibility_diagnostic_v1/cache_copy_manifest.json'
OUT = BASE / 'validation/critical_runtime_cache_final_v1'
GROUPS = ('org/pitest/', 'org/jacoco/', 'org/apache/maven/surefire/',
          'org/apache/maven/plugins/maven-surefire-plugin/', 'junit/junit/',
          'org/hamcrest/', 'org/evosuite/')


def digest(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def selected(relative):
    return relative.startswith(GROUPS) and Path(relative).suffix.lower() in ('.jar', '.pom')


def inventory():
    found = {}
    for prefix in GROUPS:
        root = CACHE / prefix
        if root.is_dir():
            for p in root.rglob('*'):
                if p.is_file() and p.suffix.lower() in ('.jar', '.pom'):
                    rel = p.relative_to(CACHE).as_posix()
                    assert rel not in found, rel
                    found[rel] = p
    return found


def check(item):
    rel, expected = item
    p = CACHE / rel
    row = dict(relative=rel, expected_sha256=expected['sha256'], expected_bytes=expected['bytes'])
    if not p.is_file():
        return dict(row, status='MISSING')
    pre = p.stat()
    actual_sha = digest(p)
    post = p.stat()
    stable = (pre.st_size, pre.st_mtime_ns) == (post.st_size, post.st_mtime_ns)
    matches = actual_sha == expected['sha256'] and post.st_size == expected['bytes']
    return dict(row, sha256=actual_sha, bytes=post.st_size, stable_during_read=stable,
                status='PASS' if stable and matches else 'DRIFT_OR_CONCURRENT_CHANGE')


def new_entry(item):
    rel, p = item
    pre = p.stat()
    actual_sha = digest(p)
    post = p.stat()
    return dict(relative=rel, sha256=actual_sha, bytes=post.st_size,
                stable_during_read=(pre.st_size, pre.st_mtime_ns) == (post.st_size, post.st_mtime_ns))


def write(name, value):
    p = OUT / name
    with p.open('x', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    audit.log('NEW_FILE_REGISTERED', path=p.relative_to(BASE).as_posix(), sha256=digest(p),
              bytes=p.stat().st_size, change_type='new read-only critical runtime cache audit')
    return p


def main():
    started = datetime.now(timezone.utc).isoformat()
    OUT.mkdir(exist_ok=False)
    audit.log('NEW_FILE_REGISTERED', path=Path(__file__).relative_to(BASE).as_posix(),
              sha256=digest(Path(__file__)), bytes=Path(__file__).stat().st_size,
              change_type='new isolated bounded audit script; no experiment/config edits')
    pinned_manifest_sha = digest(MANIFEST)
    entries = json.loads(MANIFEST.read_text(encoding='utf-8'))
    assert len(entries) == 116010, len(entries)
    expected = {r['relative']: r for r in entries if selected(r['relative'])}
    assert expected
    before = inventory()
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        checked = list(pool.map(check, sorted(expected.items())))
        additions = list(pool.map(new_entry, sorted((k, p) for k,p in before.items() if k not in expected)))
    after = inventory()
    manifest_still_same = digest(MANIFEST) == pinned_manifest_sha
    membership_stable = set(before) == set(after)
    bad = [r for r in checked if r['status'] != 'PASS']
    per_group = {}
    for prefix in GROUPS:
        rows = [r for r in checked if r['relative'].startswith(prefix)]
        per_group[prefix] = dict(initial_selected_files=len(rows), initial_bytes=sum(r['expected_bytes'] for r in rows),
                                 passed=sum(r['status']=='PASS' for r in rows),
                                 status='PASS' if all(r['status']=='PASS' for r in rows) else 'ISSUES',
                                 current_added_files=sum(r['relative'].startswith(prefix) for r in additions))
    report = dict(status='PASS' if not bad and not additions and manifest_still_same and membership_stable else 'ISSUES',
                  started_utc=started, finished_utc=datetime.now(timezone.utc).isoformat(),
                  scope='Only .jar and .pom in the seven listed critical groups, all present versions. Not a full cache verification.',
                  cache=str(CACHE), initial_manifest=str(MANIFEST), initial_manifest_sha256=pinned_manifest_sha,
                  initial_manifest_total_files=len(entries), groups=list(GROUPS),
                  selected_initial_files=len(expected), selected_initial_bytes=sum(r['bytes'] for r in expected.values()),
                  selected_current_files=len(after), counts=dict(Counter(r['status'] for r in checked)),
                  added_critical_files=len(additions), missing_or_drifted=bad,
                  membership_stable_during_audit=membership_stable,
                  initial_manifest_unchanged=manifest_still_same,
                  per_group=per_group, Java_calls=0, Maven_calls=0, network_calls=0,
                  experiment_or_config_changes=0)
    write('selected_files.json', checked)
    write('added_critical_files.json', additions)
    report_path = write('report.json', report)
    audit.log('CRITICAL_RUNTIME_CACHE_AUDIT_COMPLETE', status=report['status'],
              report=report_path.relative_to(BASE).as_posix(), report_sha256=digest(report_path),
              selected_files=len(expected), scope='seven critical groups; jar/pom only; not entire cache')
    print(json.dumps(dict(status=report['status'], selected_files=len(expected),
                         selected_bytes=report['selected_initial_bytes'],
                         added_critical_files=len(additions), failed_files=len(bad),
                         report=str(report_path), report_sha256=digest(report_path)), indent=2))
    if report['status'] != 'PASS':
        raise SystemExit(2)

if __name__ == '__main__':
    main()
