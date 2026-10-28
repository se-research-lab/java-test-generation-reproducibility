"""Read-only fixed49 measurement replay analysis; never generates tests or calls GPT.

E2 names the measurement-compatibility configuration, not a new scoring scale.
The original G0/E0/E1 observations and analyzers remain immutable.
"""
import argparse, ast, csv, hashlib, importlib.util, json, re, statistics, sys
from collections import Counter
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree as ET
import numpy as np
from junit_method_inventory_v1 import inventory_java_tests, normalize_case

BASE = Path(__file__).resolve().parents[1]
ORIGINAL = BASE / 'e49_driver'
DEFAULT_STAGE = BASE / 'e49_measurement_compat_v1'
OLD_ANALYZER = BASE / 'src/analyze_e49_final_v2.py'
OLD_ANALYZER_SHA256 = '802133f6313ff3f2fa42d09d85dd7718cbb3a9d0015db4c0a5455931313c73ed'


def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def dec(x):
    return Decimal(str(x))


def csvread(p):
    with Path(p).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def rawcsv(p):
    if not p.is_file():
        return []
    with p.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.reader(f))


def write_json(p, value):
    with p.open('x', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write('\n')


def write_csv(p, rows):
    assert rows
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with p.open('x', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def pure_original_functions():
    # Extract only pure analysis functions; no experiment module or API imports.
    assert sha(OLD_ANALYZER) == OLD_ANALYZER_SHA256, 'Original analyzer changed'
    wanted = {'focal', 'counter_hash', 'class_hashes', 'summarize'}
    tree = ast.parse(OLD_ANALYZER.read_text(encoding='utf-8'))
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in wanted]
    assert {n.name for n in nodes} == wanted
    ns = {'hashlib': hashlib, 'json': json, 'Path': Path, 'sha': sha,
          'dec': dec, 'statistics': statistics, 'np': np}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(OLD_ANALYZER), 'exec'), ns)
    return ns


def resolve_base(relative):
    p = Path(relative)
    assert not p.is_absolute(), 'Expected BASE-relative archive/input path'
    resolved = (BASE / p).resolve()
    assert resolved.is_relative_to(BASE.resolve()), 'Path escapes isolated workspace'
    return resolved


def validate_cohort(jobs, frozen, results):
    assert len(jobs) == len(frozen) == len(results) == 49, 'Incomplete fixed49 cohort'
    keys = [j['class_key'] for j in jobs]
    assert len(set(keys)) == 49
    assert keys == [g['class_key'] for g in frozen] == [r['class_key'] for r in results]
    assert [j['job_index'] for j in jobs] == list(range(1, 50))
    assert [r['job_index'] for r in results] == list(range(1, 50))
    assert len({j['repo_id'] for j in jobs}) == 15
    assert [j['repo_id'] for j in jobs] == [g['repo_id'] for g in frozen]
    assert [j['repo_id'] for j in jobs] == [r['repo_id'] for r in results]


def frozen_gpt_guard():
    guard = BASE.parents[1] / 'review_reports/minimal_camera_ready_20261023/guard_rq123_frozen.py'
    spec = importlib.util.spec_from_file_location('read_only_gpt_frozen_guard', guard)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.collect() == read(module.LOCK), 'Frozen GPT observations/artifacts changed'


def validate_inspection_amendment(stage, lock):
    """Add inspection code provenance while retaining every old locked digest."""
    amendment_path = stage / 'inspection_amendment_v1.json'
    amendment = read(amendment_path)
    assert amendment['same_readiness_lock_sha256'] == sha(stage / 'readiness_lock.json')
    assert amendment['same_protocol_sha256'] == sha(stage / 'protocol.json')
    assert amendment['original_admission_sha256'] == sha(stage / 'admission.json')
    assert amendment['changes'] == 'inspection_only'
    for key in ['generation_unchanged', 'measurement_unchanged', 'scoring_unchanged']:
        assert amendment[key] is True, 'Amendment exceeds inspection scope'
    extension = amendment['code_input_hashes']
    assert extension and not (set(extension) & set(lock['code_input_hashes'])), 'Amendment must not replace old lock entries'
    correction_path=stage/'analysis_catalog_correction_v1.json'
    correction=read(correction_path)
    assert correction['changes']=='analysis_catalog_only' and correction['score_gate_config_unchanged'] is True
    assert correction['same_readiness_lock_sha256']==sha(stage/'readiness_lock.json')
    assert correction['same_inspection_amendment_sha256']==sha(amendment_path)
    catalog_extension=correction['code_input_hashes']
    assert not (set(catalog_extension)&(set(extension)|set(lock['code_input_hashes'])))
    assert catalog_extension.get(Path(__file__).relative_to(BASE).as_posix())==sha(__file__),'Catalog-corrected analyzer is unpinned'
    for relative,digest in catalog_extension.items():assert sha(resolve_base(relative))==digest,'Catalog correction source changed: '+relative
    helper = BASE / 'src/junit_method_inventory_v1.py'
    assert extension.get(helper.relative_to(BASE).as_posix()) == sha(helper), 'Annotation parser is unpinned'
    for relative, digest in extension.items():
        assert sha(resolve_base(relative)) == digest, 'Inspection extension source changed: ' + relative
    return amendment


def validate_inputs(stage):
    assert stage.resolve().is_relative_to(BASE.resolve())
    jobs = read(stage / 'input_manifest49.json')
    frozen = csvread(BASE / 'outputs/paired49.csv')
    paths = [stage / ('job_result_%02d.json' % i) for i in range(1, 50)]
    missing = [p.name for p in paths if not p.is_file()]
    assert not missing, 'Incomplete49: missing ' + ','.join(missing)
    assert (stage / 'results49.json').is_file(), 'No final49 batch; partial cohort refused'
    results = [read(p) for p in paths]
    validate_cohort(jobs, frozen, results)
    assert read(stage / 'results49.json') == results, 'Batch/per-job results differ'
    complete = read(stage / 'complete.json')
    assert complete['status'] == 'COMPLETE' and complete['n'] == 49
    assert complete['results49_sha256'] == sha(stage / 'results49.json')
    assert complete['GPT_API_calls'] == complete['generation_calls'] == 0
    original_jobs = read(ORIGINAL / 'input_manifest49.json')
    original_results = read(ORIGINAL / 'results49.json')
    validate_cohort(original_jobs, frozen, original_results)
    for j, old in zip(jobs, original_jobs):
        assert all(j.get(k) == v for k, v in old.items() if k != 'source_files'), 'Original E1 core input changed'
        # The copied-source manifest replaces the obsolete historical source_files list.
        assert 'input_source_manifest_sha256' in j
    lock = read(stage / 'readiness_lock.json')
    code_hashes = lock.get('code_input_hashes', lock.get('code_and_input_hashes', {}))
    assert code_hashes and lock.get('tool_hashes'), 'Missing locked code/input/tool provenance'
    for relative, digest in code_hashes.items():
        assert sha(resolve_base(relative)) == digest, 'Locked code/input changed: ' + relative
    for filename, digest in lock['tool_hashes'].items():
        tool = Path(filename) if Path(filename).is_absolute() else resolve_base(filename)
        assert sha(tool) == digest, 'Locked tool changed: ' + filename
    for filename, digest in lock.get('context_source_hashes', {}).items():
        assert sha(Path(filename)) == digest, 'Locked context source changed: ' + filename
    validate_inspection_amendment(stage, lock)
    frozen_gpt_guard()
    return jobs, frozen, results, original_results


def normalize_testcase_name(name, fqcn, expected):
    method = normalize_case(name, fqcn)
    return method if method in expected else None


def inspect_xml(module, fqcn):
    java = module / 'src/test/java' / Path(*fqcn.split('.')).with_suffix('.java')
    method_inventory = inventory_java_tests(java.read_text(encoding='utf-8'))
    expected = method_inventory['methods']
    suites, cases, errors = [], [], []
    for p in sorted((module / 'target/surefire-reports').glob('TEST-*.xml')):
        root = ET.parse(p).getroot()
        suite = {'name': root.get('name'), **{k: int(root.get(k, '0')) for k in ['tests', 'failures', 'errors', 'skipped']}}
        assert suite['name'] == fqcn, 'Foreign canonical Surefire suite'
        suites.append(suite)
        for case in root.findall('testcase'):
            assert case.get('classname') == fqcn, 'Foreign testcase classname'
            method = normalize_testcase_name(case.get('name'), fqcn, expected)
            entries = []
            for kind in ['failure', 'error']:
                for item in case.findall(kind):
                    entry = {'kind': kind, 'type': item.get('type'), 'message': item.get('message')}
                    entries.append(entry)
                    errors.append(entry)
            cases.append({'raw_name': case.get('name'), 'class': fqcn, 'method': method,
                          'failures': len(case.findall('failure')), 'errors': len(case.findall('error')),
                          'skipped': len(case.findall('skipped')), 'error_details': entries})
    legacy_pass = bool(suites) and sum(s['tests'] for s in suites) > 0 and all(s['failures'] + s['errors'] == 0 for s in suites)
    counts = Counter(c['method'] for c in cases)
    strict = (bool(expected) and bool(cases) and counts == Counter(expected)
              and all(c['errors'] + c['failures'] + c['skipped'] == 0 for c in cases)
              and all(s['errors'] + s['failures'] + s['skipped'] == 0 for s in suites))
    return {'suites': suites, 'cases': cases, 'errors': errors, 'expected': expected,
            'method_entry_counts': dict(counts), 'legacy_suite_pass': legacy_pass,
            'method_inventory': method_inventory,
            'no_behavior_placeholder_methods': method_inventory['no_behavior_placeholder_methods'],
            'no_behavior_placeholder_count': method_inventory['no_behavior_placeholder_count'],
            'strict_evidence_meaning': 'Exact annotated methods executed once without XML errors; not behavioral quality',
            'complete_suite_evidence': strict,
            'skipped': sum(s['skipped'] for s in suites),
            'non_skipped_cases': sum(s['tests'] - s['skipped'] for s in suites)}


def verify_artifact_manifest(work):
    rows = read(work / 'artifact_manifest.json')
    assert isinstance(rows, list) and rows, 'Empty raw artifact manifest'
    names = [r['path'] for r in rows]
    assert len(names) == len(set(names)), 'Duplicate artifact manifest paths'
    assert all(resolve_base(r['path']).is_relative_to(work.resolve()) for r in rows)
    for r in rows:
        p = resolve_base(r['path'])
        assert sha(p) == r['sha256'], 'Raw artifact changed: ' + r['path']
        if 'bytes' in r:
            assert p.stat().st_size == r['bytes']
    return set(names)


def selected_test_bytecode(module, fqcn):
    root = module / 'target/test-classes'
    prefixes = [fqcn.replace('.', '/'), fqcn.replace('.', '/') + '_scaffolding']
    result = {}
    for p in root.rglob('*.class'):
        relative = p.relative_to(root).as_posix()
        stem = relative[:-6]
        if any(stem == prefix or stem.startswith(prefix + '$') for prefix in prefixes):
            result[relative] = {'sha256': sha(p), 'bytes': p.stat().st_size}
    return result


def validate_test_bytecode(work, job, module, gate, measurement):
    baseline_path = work / 'generated_test_bytecode_baseline.json'
    assert sha(baseline_path) == job['generated_test_bytecode_baseline_sha256']
    baseline = read(baseline_path)
    old_module = ORIGINAL / 'jobs' / ('%02d' % job['job_index']) / 'repo' / job['module']
    original = selected_test_bytecode(old_module, job['selected_test_fqcn'])
    assert baseline['classes'] == original
    available = bool(original)
    assert baseline['available'] == available == job['generated_test_bytecode_baseline_available']
    assert baseline['count'] == len(original) == job['generated_test_bytecode_baseline_count']
    current = selected_test_bytecode(module, job['selected_test_fqcn'])
    changed = sorted(name for name in set(original) & set(current) if original[name] != current[name])
    added = sorted(set(current) - set(original)) if available else []
    missing = sorted(set(original) - set(current))
    if available:
        assert not changed and not added, 'Generated-test bytecode changed or added'
        if gate:
            assert not missing, 'BUILD SUCCESS with missing original generated-test bytecode'
    after = read(work / 'generated_test_bytecode_after.json')
    assert after['selected_test_fqcn'] == job['selected_test_fqcn']
    assert after['classes'] == current and after['count'] == len(current)
    diagnostic = measurement['generated_test_bytecode']
    assert after['guard'] == diagnostic
    expected = {'baseline_available': available, 'baseline_count': len(original),
                'observed_count': len(current), 'changed': changed, 'added': added, 'missing': missing,
                'matches_original_E1': (not missing) if available else None,
                'newly_pinned_without_E1_baseline': not available,
                'unchanged_claim_available': available and not missing}
    assert all(diagnostic.get(key) == value for key, value in expected.items())
    return expected


def inspect_job(stage, job, gpt, row, original_row, pure):
    index = job['job_index']
    work = stage / 'jobs' / ('%02d' % index)
    module = work / 'repo' / job['module']
    fqcn = job['selected_test_fqcn']
    assert read(work / 'result.json') == row, 'Copied per-job result differs'
    assert row['GPT_API_calls'] == row['generation_calls'] == row['generation_attempts'] == 0
    assert row['seed'] == job['seed'] == original_row['seed']
    assert bool(row['archived_E1_generation_success']) == bool(original_row['generation_success']) == bool(job['archived_E1_generation_success']), 'Archived E1 generation provenance differs'
    assert dec(row['G0_archived_mutation_percent']) == dec(gpt['gpt_mutation_coverage']) == dec(job['gpt_archived_mutation_percent'])
    assert dec(row['E0_archived_mutation_percent']) == dec(gpt['evosuite_mutation_coverage']) == dec(job['e0_archived_mutation_percent'])
    assert dec(row['E1_archived_mutation_percent']) == dec(original_row['legacy_strict_mutation_percent'])
    assert sha(work / 'repo' / job['focal_path']) == job['focal_sha256']
    artifacts = verify_artifact_manifest(work)
    original_job = ORIGINAL / 'jobs' / ('%02d' % index)
    before_guard = read(work / 'original_E1_guard_before.json')
    after_guard = read(work / 'original_E1_guard_after.json')
    assert before_guard == after_guard and before_guard, 'Original E1 job guard differs'
    actual_old_paths = {p.relative_to(original_job).as_posix() for p in original_job.rglob('*') if p.is_file()}
    assert actual_old_paths == set(before_guard), 'Original E1 file membership changed'
    for relative, value in before_guard.items():
        source = original_job / relative
        assert sha(source) == value['sha256'] and source.stat().st_size == value['bytes'], 'Original E1 bytes changed'
    assert sha(work / 'input_source_manifest.json') == job['input_source_manifest_sha256']
    copied = read(work / 'input_source_manifest.json')
    expected_sources = {r['relative']: r['sha256'] for r in copied}
    policy = read(work / 'policy_applied.json')
    assert policy['only_allowlisted_semantic_changes']
    expected_sources[(Path(job['module']) / 'pom.xml').as_posix()] = policy['after_sha256']
    excluded = {'.git', 'target', 'node_modules', 'evosuite-report', '.gradle'}
    actual_sources = {p.relative_to(work / 'repo').as_posix(): sha(p) for p in (work / 'repo').rglob('*')
                      if p.is_file() and not (set(p.relative_to(work / 'repo').parts) & excluded)}
    assert actual_sources == expected_sources, 'Copied source closure changed outside allowed module POM'
    generated = read(work / 'generated_manifest.json')
    for relative, digest in generated.items():
        assert sha(work / relative) == digest, 'Reused generated bytes changed'
    selected_path = Path('repo') / job['module'] / 'src/test/java' / Path(*fqcn.split('.')).with_suffix('.java')
    for relative in [selected_path, selected_path.with_name(selected_path.stem + '_scaffolding.java')]:
        assert sha(work / relative) == sha(original_job / relative), 'Original E1 native test/scaffold mismatch'
        assert (work / relative).relative_to(BASE).as_posix() in artifacts, 'Native test missing from raw manifest'
    required_raw = [module / 'pom.xml']
    required_raw.extend(p for p in (module / 'target').rglob('*') if p.is_file() and
                        (p.suffix == '.class' and p.is_relative_to(module / 'target/classes')
                         or 'surefire-reports' in p.parts or 'pit-reports' in p.parts
                         or p.is_relative_to(module / 'target/site/jacoco')))
    testclassroot = module / 'target/test-classes'
    required_raw.extend(testclassroot / relative for relative in selected_test_bytecode(module, fqcn))
    assert all(p.relative_to(BASE).as_posix() in artifacts for p in required_raw), 'Key raw report/bytecode missing from manifest'
    commands = [read(p) for p in sorted(work.glob('command_*.json'))]
    assert commands, 'No measurement invocation evidence'
    for command in commands:
        argv = command['argv']
        assert '-jar' not in argv, 'Generation command in measurement replay'
        assert not any('openai' in str(a).lower() for a in argv), 'Unexpected API command'
        assert Path(command['cwd']).resolve().is_relative_to(work.resolve())
        selectors = [a for a in argv if a.startswith('-Dtest=')]
        assert not selectors or selectors == ['-Dtest=' + fqcn], 'Foreign/method-only selected test'
        for key in ['stdout', 'stderr']:
            assert sha(resolve_base(command[key])) == command[key + '_sha256']
    measurement = read(work / 'measurement_audit.json')
    assert measurement['source_unchanged'] and measurement['generated_unchanged']
    assert measurement['production_class_mismatches'] == []
    assert measurement['compile_classpath_unchanged'] and measurement['test_classpath_delta_allowed']
    baseline = read(work / 'production_class_baseline.json')
    actual = {p.relative_to(module / 'target/classes').as_posix(): sha(p) for p in (module / 'target/classes').rglob('*.class')}
    expected_classes = {name: value['sha256'] if isinstance(value, dict) else value for name, value in baseline.items()}
    changed = sorted(name for name in actual if name not in expected_classes or actual[name] != expected_classes[name])
    missing = sorted(set(expected_classes) - set(actual))
    assert not changed, 'Production bytecode changed or added'
    assert measurement['production_class_mismatches'] == []
    assert measurement['missing_production_classes'] == missing
    if int(row['legacy_process_build']):
        assert not missing, 'BUILD SUCCESS with missing production bytecode'
    testbytecode = validate_test_bytecode(work, job, module, int(row['legacy_process_build']), measurement)
    xml = inspect_xml(module, fqcn)
    assert bool(measurement['complete_suite_evidence']) == xml['complete_suite_evidence']
    assert row['surefire_suites'] == xml['suites'] and bool(row['suite_pass']) == xml['legacy_suite_pass']
    assert measurement['expected_methods'] == xml['expected']
    for key in ['no_behavior_placeholder_methods', 'no_behavior_placeholder_count']:
        if key in measurement:
            assert measurement[key] == xml[key], 'Stored placeholder diagnostic differs from frozen source'
    pit = module / 'target/pit-reports/mutations.csv'
    mutants = rawcsv(pit)
    assert all(len(r) == 7 for r in mutants)
    focal = pure['focal'](mutants, job)
    killed = sum(r[5] == 'KILLED' for r in focal)
    assert not [r for r in mutants if r[5] == 'KILLED' and fqcn not in r[6]], 'Foreign PIT killing suite'
    original_module = ORIGINAL / 'jobs' / ('%02d' % index) / 'repo' / job['module']
    old_focal = pure['focal'](rawcsv(original_module / 'target/pit-reports/mutations.csv'), job)
    multiset_same = bool(focal and old_focal) and pure['counter_hash'](focal) == pure['counter_hash'](old_focal)
    assert bool(measurement['focal_mutant_multiset_matches_E1']) == multiset_same
    # Availability may be false for an honest measurement failure; no invented report.
    if focal:
        assert multiset_same, 'Nonempty measured focal mutant inventory incomplete or different; required guard evidence unavailable, not proof of source mutation'
    jacoco = module / 'target/site/jacoco/jacoco.csv'
    coverage = [r for r in csvread(jacoco) if r.get('CLASS') == job['focal_class'] and r.get('PACKAGE', '').replace('/', '.') == job['package']] if jacoco.is_file() else []
    gate = int(row['legacy_process_build'])
    assert gate in [0, 1]
    score = round(100 * killed / len(focal), 2) if focal else None
    strict_score = score if gate and score is not None else 0.0
    assert len(focal) == row['focal_mutants'] and killed == row['killed_mutants']
    assert dec(row['legacy_strict_mutation_percent']) == dec(strict_score), 'Legacy score formula changed'
    assert bool(row['measurement_evidence_complete']) == bool(xml['legacy_suite_pass'] and focal and coverage)
    if score is not None:
        assert dec(row['mutation_score_percent']) == dec(score)
    else:
        assert row['mutation_score_percent'] is None
    measured = [c for c in commands if any('mutationCoverage' in str(a) for a in c['argv'])]
    assert len(measured) == 1, 'Expected exactly one measurement pipeline invocation'
    command = measured[0]
    actual_gate = int(not command.get('timeout', False) and command.get('returncode') != -999
                      and 'BUILD SUCCESS' in resolve_base(command['stdout']).read_text(encoding='utf-8', errors='replace'))
    assert gate == actual_gate, 'Legacy process gate differs from actual measurement marker/timeout'
    record = {'job_index': index, 'class_key': job['class_key'], 'repo_id': job['repo_id'], 'focal_class': job['focal_class'],
              'G0_archived_mutation_percent': str(dec(gpt['gpt_mutation_coverage'])),
              'E0_archived_mutation_percent': str(dec(gpt['evosuite_mutation_coverage'])),
              'E1_archived_mutation_percent': str(dec(original_row['legacy_strict_mutation_percent'])),
              'E2_legacy_strict_mutation_percent': str(dec(strict_score)),
              'G0_minus_E2_pp': str(dec(gpt['gpt_mutation_coverage']) - dec(strict_score)),
              'E2_minus_E1_pp': str(dec(strict_score) - dec(original_row['legacy_strict_mutation_percent'])),
              'legacy_process_build': gate, 'suite_pass': xml['legacy_suite_pass'],
              'complete_suite_evidence': xml['complete_suite_evidence'],
              'no_behavior_placeholder': bool(xml['no_behavior_placeholder_count']),
              'no_behavior_placeholder_count': xml['no_behavior_placeholder_count'],
              'no_behavior_placeholder_methods': ';'.join(xml['no_behavior_placeholder_methods']),
              'measurement_evidence_complete': row['measurement_evidence_complete'],
              'skipped_tests': xml['skipped'], 'non_skipped_surefire_cases': xml['non_skipped_cases'],
              'archived_E1_generation_success': row['archived_E1_generation_success'], 'generation_attempts': 0,
              'focal_mutants': len(focal), 'killed_mutants': killed,
              'PIT_report_present': pit.is_file(), 'JaCoCo_focal_present': bool(coverage),
              'TestRule_missing': any('TestRule' in str(e.get('message', '')) for e in xml['errors']),
              'seed': job['seed'], 'GPT_API_calls': 0, 'generation_calls': 0,
              'generated_test_bytecode_baseline_available': testbytecode['baseline_available'],
              'generated_test_bytecode_unchanged_claim_available': testbytecode['unchanged_claim_available'],
              'generated_test_bytecode_observed_count': testbytecode['observed_count'],
              'error_type': row.get('error_type', ''), 'technical_error': row.get('error', '')}
    diagnostic = {'job_index': index, 'class_key': job['class_key'], 'XML': xml,
                  'focal_mutant_multiset_matches_E1': multiset_same,
                  'focal_mutant_multiset_sha256': pure['counter_hash'](focal) if focal else None,
                  'artifact_files_verified': len(artifacts), 'commands_verified': len(commands),
                  'measurement_audit': measurement,
                  'PIT_focal_status_counts': dict(Counter(r[5] for r in focal)),
                  'no_foreign_killing_suite': True,
                  'mutant_identity_limit': 'CSV cols0-4 multiset retains duplicates but lacks full PIT mutation index'}
    return record, diagnostic


def summarize_replay(rows, pure):
    assert len(rows) == 49
    # Only rename the treatment field at the pure-function boundary. The original
    # arithmetic, repository order and draw algorithm are unchanged.
    adapted = [{**r, 'E1_legacy_strict_mutation_percent': r['E2_legacy_strict_mutation_percent'],
                'generation_success': r['archived_E1_generation_success']} for r in rows]
    stats, repos, draws = pure['summarize'](adapted)
    stats = {key.replace('E1', 'E2'): value for key, value in stats.items()}
    stats['E2_counts']['archived_E1_generation_success'] = stats['E2_counts'].pop('generation_success')
    repos = [{key.replace('E1', 'E2'): value for key, value in row.items()} for row in repos]
    old = [dec(r['E1_archived_mutation_percent']) for r in rows]
    current = [dec(r['E2_legacy_strict_mutation_percent']) for r in rows]
    differences = [a - b for a, b in zip(current, old)]
    stats['E1_archived_mean'] = float(sum(old) / 49)
    stats['E1_archived_median'] = float(statistics.median(old))
    stats['E2_minus_E1'] = {'mean_pp': float(sum(differences) / 49), 'median_pp': float(statistics.median(differences)),
                           'E2_higher': sum(d > 0 for d in differences), 'E1_higher': sum(d < 0 for d in differences), 'ties': sum(d == 0 for d in differences)}
    stats['E2_complete_suite_evidence'] = sum(r['complete_suite_evidence'] for r in rows)
    stats['measurement_replay_of_locked_E1_tests'] = True
    stats['new_generation_calls'] = 0
    stats['generated_test_bytecode_baseline_available_classes'] = sum(r['generated_test_bytecode_baseline_available'] for r in rows)
    stats['generated_test_bytecode_unchanged_claim_classes'] = sum(r['generated_test_bytecode_unchanged_claim_available'] for r in rows)
    stats['no_behavior_placeholder_classes'] = sum(r['no_behavior_placeholder'] for r in rows)
    stats['no_behavior_placeholder_methods'] = sum(r['no_behavior_placeholder_count'] for r in rows)
    stats['strict_suite_evidence_meaning'] = 'Execution of exactly the frozen annotated methods, including any placeholder; not behavioral adequacy'
    stats['placeholder_changes_score_or_denominator'] = False
    stats['configuration_labels_not_scoring_scales'] = True
    stats['no_E1_row_splicing'] = True
    stats['E1_archived_not_overwritten'] = True
    return stats, repos, draws


def self_test():
    # These negative tests do not touch experiment files or require a complete run.
    jobs = [{'job_index': i + 1, 'class_key': str(i), 'repo_id': str(i % 15)} for i in range(49)]
    frozen = [{'class_key': j['class_key'], 'repo_id': j['repo_id']} for j in jobs]
    results = [dict(j) for j in jobs]
    validate_cohort(jobs, frozen, results)
    refused = 0
    for candidate in [results[:-1], results + [results[-1]], [results[1], results[0]] + results[2:]]:
        try:
            validate_cohort(jobs, frozen, candidate)
        except AssertionError:
            refused += 1
    assert refused == 3
    fqcn = 'example.Selected_ESTest'
    assert normalize_testcase_name('test4 on test4(' + fqcn + ')', fqcn, ['test4']) == 'test4'
    for name in ['test4 on test5(' + fqcn + ')', 'test4 on test4(example.Foreign_ESTest)', 'initializationError']:
        assert normalize_testcase_name(name, fqcn, ['test4']) is None
    source = '''class Sample {
      // @Test public void fake() {}
      String ignored = "@Test public void falsePositive() {}";
      @org.junit.Test(timeout=1000) public void notGeneratedAnyTest() { /* no behavior */ ; }
      @Test public void meaningfulName_$2() throws Throwable { assertTrue(true); }
    }'''
    inventory = inventory_java_tests(source)
    assert inventory['methods'] == ['meaningfulName_$2', 'notGeneratedAnyTest']
    assert inventory['no_behavior_placeholder_methods'] == ['notGeneratedAnyTest']
    assert normalize_testcase_name('notGeneratedAnyTest', fqcn, inventory['methods']) == 'notGeneratedAnyTest'
    assert normalize_testcase_name('meaningfulName_$2 on meaningfulName_$2(' + fqcn + ')', fqcn, inventory['methods']) == 'meaningfulName_$2'
    assert normalize_testcase_name('meaningfulName_$2 on other(' + fqcn + ')', fqcn, inventory['methods']) is None
    # Repeated failure entries cannot become strict suite evidence by set-dedupe.
    assert Counter(['test0', 'test0', 'test1']) != Counter(['test0', 'test1'])
    print(json.dumps({'status': 'PASS', 'partial_extra_reordered_cohort_refused': 3,
                      'TestNG_exact_normalization': True, 'duplicate_entries_preserved': True,
                      'annotated_nonprefix_methods': True, 'placeholder_is_diagnostic_only': True,
                      'Java_Maven_API_calls': 0}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage', type=Path, default=DEFAULT_STAGE)
    parser.add_argument('--out', type=Path, default=BASE / 'outputs/e49_measurement_compat_v1')
    parser.add_argument('--validate-only', action='store_true')
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    pure = pure_original_functions()
    jobs, frozen, results, original_results = validate_inputs(args.stage)
    rows, diagnostics = [], []
    for job, gpt, result, original in zip(jobs, frozen, results, original_results):
        row, diagnostic = inspect_job(args.stage, job, gpt, result, original, pure)
        rows.append(row)
        diagnostics.append(diagnostic)
    stats, repos, draws = summarize_replay(rows, pure)
    print(json.dumps({'status': 'PASS', 'n': 49, 'GPT_guard': 'PASS', 'generation_calls': 0, 'GPT_API_calls': 0}))
    if args.validate_only:
        return
    assert args.out.resolve().is_relative_to(BASE.resolve())
    args.out.mkdir(exist_ok=False)
    write_csv(args.out / 'fixed49.csv', rows)
    write_json(args.out / 'statistics.json', stats)
    write_json(args.out / 'raw_diagnostics49.json', diagnostics)
    write_csv(args.out / 'repository_summary.csv', repos)
    write_csv(args.out / 'cluster_bootstrap_draws.csv', draws)
    difference = stats['G0_minus_E2']
    ci = stats['repository_cluster_percentile_95CI_G0_minus_E2_mean_pp']
    report = f'''# Fixed49 measurement-compatibility replay

E2 is a configuration label, not a new scoring scale. All49 locked E1 generated-test/scaffold pairs were measured in new E-only workspaces; no GPT API call or test generation occurred. Archived G0/E0/E1 remain unchanged. RQ1–RQ3 retain their original61/45/300 observations.

|Same49 classes|G0 archived|E0 archived|E1 archived|E2 replay|
|---|---:|---:|---:|---:|
|Mean mutation (%)|{stats['G0_mean']:.2f}|{stats['E0_mean']:.2f}|{stats['E1_archived_mean']:.2f}|{stats['E2_legacy_strict_mean']:.2f}|
|Median mutation (%)|{stats['G0_median']:.2f}|{stats['E0_median']:.2f}|{stats['E1_archived_median']:.2f}|{stats['E2_legacy_strict_median']:.2f}|

G0−E2 paired mean={difference['mean_pp']:.2f}pp; paired median={difference['median_pp']:.2f}pp; G0 higher/E2 higher/ties={difference['G_higher']}/{difference['E_higher']}/{difference['ties']}. Exploratory whole-repository percentile95% CI mean=[{ci[0]:.2f},{ci[1]:.2f}]pp,20,000 draws, seed20261023. Strict suite evidence={stats['E2_complete_suite_evidence']}/49. Original legacy score gates and raw suite/evidence flags remain separate. Strict evidence confirms that the frozen annotated methods executed; it does not certify behavioral quality. No-behavior placeholder classes={stats['no_behavior_placeholder_classes']}/49, retained with their original score formula and cohort membership.

This is a fixed-test measurement sensitivity on a historical Maven-only common-build cohort, not a generation rerun, a new49-class NI test, repeated-run variance estimate, or full300 baseline replacement. No old/new E1 rows are spliced; failures remain in the49 denominator. TestNG wrapper reports are archived but canonical TEST-*.xml supplies testcase counts, preserving error/duplicate entries. E1→E2 changes are integration-policy effects; they do not establish an assertion-only causal effect. CSV mutant fingerprints retain duplicates but lack full PIT mutation indexes.
'''
    with (args.out / 'BAO_CAO_MEASUREMENT_REPLAY49.md').open('x', encoding='utf-8') as f:
        f.write(report)
    inputs = [args.stage / x for x in ['input_manifest49.json', 'readiness_lock.json', 'inspection_amendment_v1.json', 'results49.json', 'complete.json']]
    for work in sorted((args.stage / 'jobs').iterdir()):
        inputs.extend(work / name for name in ['original_E1_guard_before.json', 'original_E1_guard_after.json', 'artifact_manifest.json'])
    inputs += [BASE / 'outputs/paired49.csv', ORIGINAL / 'results49.json', OLD_ANALYZER, Path(__file__), args.stage/'analysis_catalog_correction_v1.json', BASE/'validation/packaged_class_index_correction_v1/packaged_duplicate_checks.json']
    write_json(args.out / 'output_manifest.json', {'inputs': {p.relative_to(BASE).as_posix(): sha(p) for p in inputs},
               'outputs': {p.name: sha(p) for p in sorted(args.out.iterdir()) if p.is_file()},
               'original_files_modified': False, 'GPT_API_calls': 0, 'generation_calls': 0})


if __name__ == '__main__':
    main()
