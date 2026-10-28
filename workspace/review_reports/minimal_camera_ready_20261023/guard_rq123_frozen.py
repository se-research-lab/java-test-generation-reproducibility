"""Read-only integrity guard for submitted GPT observations; never runs experiments."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
LOCK = HERE / 'rq123_frozen_manifest.json'
RUN = 'scripts_v2/results/runs/full300_merged_20260724_paper/'
WIDE = RUN + 'metrics_wide.csv'
LONG = RUN + 'metrics_long.csv'
AVAIL = 'review_reports/reuse_audit_v1_20261021T112500/evidence/G0_AVAILABILITY_300.csv'
EXPECTED = {
    WIDE: '92ba89c3000be4b28ffc361ea19630764582d262c1e8817477dc54ac0fd4e724',
    LONG: 'dd09724477bbe43dfef6e5f7d5248fa236c9973d7260fe2fe72d4393d64ea53d',
    AVAIL: '9a86b404d297b43751211e22bec1b6585967be7ded81a818cc72e3c632ab3ac7',
}
# Identity/context columns before the arm-specific measurements in submitted schema.
IDENTITY = [
    'sample_index', 'class_key', 'project', 'repo_id', 'focal_class', 'focal_path',
    'module', 'scope_key', 'build_tool', 'java_version', 'complexity_half', 'nloc',
    'token_count', 'method_count', 'public_method_count', 'max_method_cc',
    'sum_method_cc', 'avg_method_cc', 'selection_rank_in_repo',
    'original_manifest_index', 'split_name',
]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_rows(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []
        require(len(fields) == len(set(fields)), 'Duplicate column names')
        rows = list(reader)
    keys = [r['class_key'] for r in rows]
    require(len(keys) == len(set(keys)), 'Duplicate class keys')
    return fields, sorted(rows, key=lambda r: r['class_key'])


def project(rows, fields):
    return [{k: r[k] for k in fields} for r in rows]


def observed(row, metric):
    value = row['gpt_' + metric]
    return row['gpt_compilation'] == '1' and value != '' and math.isfinite(float(value))


def collect():
    for name, expected in EXPECTED.items():
        require(sha(ROOT / name) == expected, f'Submitted source hash changed: {name}')
    fields, rows = read_rows(ROOT / WIDE)
    require(len(rows) == 300, 'Submitted cohort is not 300')
    protected = IDENTITY + [f for f in fields if f.startswith('gpt_')]
    cohorts = {
        'rq1': [r['class_key'] for r in rows if observed(r, 'mutation_coverage')],
        'rq2': [r['class_key'] for r in rows if observed(r, 'branch_coverage')],
        'rq3': [r['class_key'] for r in rows],
    }
    require([len(v) for v in cohorts.values()] == [61, 45, 300], 'RQ membership count mismatch')
    require(sum(r['gpt_compilation'] == '1' for r in rows) == 61, 'GPT success count mismatch')
    _, availability = read_rows(ROOT / AVAIL)
    require([r['class_key'] for r in availability] == cohorts['rq3'], 'Availability keys mismatch')
    artifacts = []
    for r in availability:
        if r['G0_available'].lower() == 'true':
            p = Path(r['G0_path'])
            require(p.is_file(), f'Missing GPT artifact: {r["class_key"]}')
            require(sha(p) == r['G0_sha256'], f'GPT artifact changed: {r["class_key"]}')
            artifacts.append({'class_key': r['class_key'], 'path': str(p), 'sha256': r['G0_sha256']})
    require(len(artifacts) == 298, 'Expected 298 archived GPT artifacts')
    return {
        'schema_version': 1, 'source_hashes': EXPECTED, 'protected_columns': protected,
        'cohort_keys': cohorts, 'gpt_rows': project(rows, protected), 'artifacts': artifacts,
        'no_output_keys': [r['class_key'] for r in availability if r['G0_available'].lower() != 'true'],
        'scope': 'data integrity only; no scientific-validity or runtime-isolation certification',
    }


def compare_candidate(path, lock, cohort='rq3'):
    fields, rows = read_rows(path)
    require(all(f in fields for f in lock['protected_columns']), 'Missing protected columns')
    keys = lock['cohort_keys'][cohort]
    require([r['class_key'] for r in rows] == keys,
            f'Candidate membership differs from frozen {cohort} (intersection substitution forbidden)')
    expected = [r for r in lock['gpt_rows'] if r['class_key'] in set(keys)]
    require(project(rows, lock['protected_columns']) == expected,
            'Candidate changed GPT observations or identity/context fields')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--init', action='store_true', help='Create lock once; refuses overwrite')
    parser.add_argument('--candidate-wide', type=Path)
    parser.add_argument('--rq1-wide', type=Path, help='Check the exact pre-aggregation RQ1 input')
    parser.add_argument('--rq2-wide', type=Path, help='Check the exact pre-aggregation RQ2 input')
    parser.add_argument('--rq3-wide', type=Path, help='Check the exact pre-aggregation RQ3 input')
    args = parser.parse_args()
    candidates = [(args.candidate_wide, 'rq3'), (args.rq1_wide, 'rq1'),
                  (args.rq2_wide, 'rq2'), (args.rq3_wide, 'rq3')]
    require(not (args.init and any(p for p, _ in candidates)), 'Init and candidate checking are separate')
    current = collect()
    if args.init:
        with LOCK.open('x', encoding='utf-8') as f:
            json.dump(current, f, ensure_ascii=False, indent=2)
            f.write('\n')
        status = 'INITIALIZED_ONCE'
    else:
        lock = json.loads(LOCK.read_text(encoding='utf-8'))
        require(current == lock, 'Frozen manifest differs; automatic re-baselining forbidden')
        for path, cohort in candidates:
            if path:
                compare_candidate(path, lock, cohort)
        status = 'PASS'
    print(json.dumps({'status': status, 'cohorts': {'rq1': 61, 'rq2': 45, 'rq3': 300},
                      'gpt_artifact_hashes_verified': 298, 'no_output_records': 2,
                      'candidates_checked': sum(p is not None for p, _ in candidates),
                      'experiment_executed': False}, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError) as e:
        print(json.dumps({'status': 'FAIL', 'reason': str(e)}))
        raise SystemExit(1)
