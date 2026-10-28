"""Read-only syntax/import checks for new diagnostic helpers and selection evidence."""
import ast,hashlib,json,sys
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));import audit
names=['diagnose_e1_compatibility_v4.py','run_e1compat_junit_v1.py','replay_e1_discovery_runtime_v2.py','run_e1compat_guarded_v1.py','wait_and_run_e1compat_v1.py']
report=[]
for name in names:
    p=BASE/'src'/name;tree=ast.parse(p.read_text(encoding='utf-8'))
    imports=[ast.unparse(n) for n in ast.walk(tree) if isinstance(n,(ast.Import,ast.ImportFrom))]
    assert not any('openai' in x.lower() or 'rbl4_v2_runner' in x.lower() for x in imports)
    report.append({'path':name,'sha256':audit.sha(p),'syntax':'PASS','imports':imports})
selection=json.loads((BASE/'repeated_subset_selection_v1.json').read_text(encoding='utf-8'))
assert selection['candidate_count']==49 and selection['selected_count']==15
expected=[]
for repo in sorted({r['repo_id'] for r in selection['candidates']}):
    rows=[r for r in selection['candidates'] if r['repo_id']==repo]
    for r in rows:
        expected_digest=hashlib.sha256(('FISAT2026-repeat-v1|'+r['repo_id']+'|'+r['class_key']).encode()).hexdigest()
        assert r['selection_digest']==expected_digest
    expected.append(min(rows,key=lambda r:r['selection_digest']))
assert expected==selection['selected']
audit.log('E1_COMPATIBILITY_HELPERS_READONLY_VALIDATED',files=report,selection_sha256=audit.sha(BASE/'repeated_subset_selection_v1.json'),selection_algorithm_verified=True,selection_actual_generation_calls=0)
print(json.dumps({'syntax_import_checks':'PASS','helpers':len(report),'selection_algorithm':'PASS','selected_classes':15,'generation_calls':0},indent=2))
