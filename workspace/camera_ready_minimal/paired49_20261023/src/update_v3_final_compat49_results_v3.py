"""Gate and minimally update isolated v3 after completed49 plus independent raw PASS.

No experiment, API, PDF build or patch occurs with --self-test/--check. --apply
backs up every changed source byte before one permitted manuscript transaction.
Public text uses E1 for the final supplementary configuration; internal E2 fields
are provenance labels only and never create a scoring scale or public treatment.
"""
import argparse
import csv
import difflib
import hashlib
import json
import re
import statistics
import sys
from decimal import Decimal
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
import audit
REV = BASE / 'manuscript_revision_v3_compat49'
SOURCE = REV / 'source'
STAGE = BASE / 'e49_measurement_compat_v1'
OFFICIAL = BASE / 'outputs/e49_measurement_compat_v1'
INDEPENDENT = BASE / 'validation/independent_compat49_raw_v1'
ANALYZER = 'src/analyze_measurement_compat49_v3.py'
AUDITOR = 'src/independent_measurement49_raw_audit_v2.py'
AMENDMENT_SHA256 = '47d1a6ab4b211ea14c19e82ae798e666055fd043e3497a872395a6840923ddf2'
CODE_PINS = {
    "src/analyze_measurement_compat49_v3.py": "28a986cf56f33d1df04f9eae654d619aee35574f1e2e15db2afe1191b7c56084",
    "src/independent_measurement49_raw_audit_v2.py": "c54a2f4d8078186112dee183ec06d56bb1583d01b126766b4e093e39db008985"
}
SOURCE_PINS = {
    "figures/_source_checks/agonetest2025_page_10.png": "10dd1cf10225bb5bc7cedf688b94350a85da186a528f3a77ea309015a57856a9",
    "figures/_source_checks/agonetest2025_page_8.png": "7179ce6e11a41e892d3e8c941180661630bedaacea3c847ef9223d5cd9057b95",
    "figures/_source_checks/agonetest2025_page_9.png": "ec2f032cd9b093bc69b69ca0b59b3c055819af86295f82fe661ac778fee75807",
    "llncs.cls": "f1be281bc631f07c4405566d64b294ec8df018e75e6d6c6c643cbdd5806677a5",
    "main.tex": "27254461f1259e34c9650daa32c011baaf5a98f414f93d3294ab9fa87fc584b1",
    "references.bib": "2b0f8cdaa85e11d0e8e6c685b48d4af4cf75bae9b6d57232d21ac21ab642ffa4",
    "references.tex": "98e20358f75b62f5cc351ceb0524615eb60603186228faf6da68270d96048f65",
    "sections/00_abstract.tex": "2ba8698e64a1d9b53e7ab5089760cfa9f260e7fb47721730d74c1a9921f987e1",
    "sections/01_introduction.tex": "502330c888df1b52696eb29d2fdbbdeab1099b4e8a76f043bb859040427a9f80",
    "sections/02_related_work.tex": "e73184cb160fe2736d51bb63d0c24d6fc9f941b36a0c46d3cba0118821e1c4be",
    "sections/03_method.tex": "e2c8cbb93bc2cab3a2df405e9ef6074c766ff7314c5cf03662f0409f1f065ec3",
    "sections/04a_supplement.tex": "dc221e5a96f15c04c4f635508152becea246d87e26547778889982f6cda3e3fd",
    "sections/04_results.tex": "e736cb72735ce81beceb7a084c54feab93d2ba2a7d60819ec39fae377eace57c",
    "sections/05_discussion.tex": "4cffdc6b4dd31f705427907e242f6e44623d25073fb2e4797ee4874a912b833d",
    "sections/06_threats.tex": "8f07d221d148daa211c2d67ba28d78086f84d2cfae1d59927f408447ca9aae4a",
    "sections/07_conclusion.tex": "821ec78b00fa4b36cd8b6b5d0ae902d10a8a9d7828c22a66b1a62ce5a3980b7b",
    "sections/08_disclosure.tex": "672fb436ec85fa86127980a0c1b382088278315204334ee01f86847f5c50f8ae",
    "splncs04.bst": "a370ad563909f7264038e3388d59036306c3ecd53c6de26279ba921f3a9979df"
}
ALLOWED = {'sections/00_abstract.tex', 'sections/03_method.tex',
           'sections/04a_supplement.tex', 'sections/05_discussion.tex',
           'sections/06_threats.tex', 'sections/07_conclusion.tex'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def rows(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))


def inside(root, relative):
    p = Path(relative)
    assert not p.is_absolute(), 'Expected relative manifest path'
    result = (root / p).resolve()
    assert result.is_relative_to(root.resolve()), 'Manifest path escapes its root'
    return result


def verify_manifest(folder, required):
    manifest_path = folder / 'output_manifest.json'
    manifest = read(manifest_path)
    for key in ['inputs', 'outputs']:
        assert isinstance(manifest.get(key), dict) and manifest[key], 'Missing manifest map: ' + key
    assert required <= set(manifest['outputs']), 'Required outputs absent from manifest'
    for group in ['source', 'inputs']:
        for relative, value in manifest.get(group, {}).items():
            assert sha(inside(BASE, relative)) == value, 'Manifest input changed: ' + relative
    for relative, value in manifest['outputs'].items():
        assert sha(inside(folder, relative)) == value, 'Manifest output changed: ' + relative
    return {'path': manifest_path.relative_to(BASE).as_posix(), 'sha256': sha(manifest_path),
            'inputs_verified': len(manifest['inputs']), 'outputs_verified': len(manifest['outputs'])}


def assert_source_pins():
    actual = {p.relative_to(SOURCE).as_posix(): sha(p) for p in SOURCE.rglob('*') if p.is_file()}
    assert actual == SOURCE_PINS, 'Manuscript changed since patch preparation; refuse to overwrite'
    for relative, value in CODE_PINS.items():
        assert sha(BASE / relative) == value, 'Pinned audit/analyzer source changed'
    return actual


def validate_completed_evidence():
    catalog_path=STAGE/'analysis_catalog_correction_v1.json'
    assert sha(catalog_path)=='159a7cea30e45fedc08fba5d5bf65586f75257bad72f0d32fc3b88da5240433a'
    catalog=read(catalog_path)
    assert catalog['changes']=='analysis_catalog_only' and catalog['score_gate_config_unchanged'] is True
    for rel,digest_value in catalog['code_input_hashes'].items():assert sha(inside(BASE,rel))==digest_value
    amendment_path = STAGE / 'inspection_amendment_v1.json'
    assert sha(amendment_path) == AMENDMENT_SHA256, 'Inspection-only amendment changed'
    amendment = read(amendment_path)
    assert amendment['changes'] == 'inspection_only'
    assert amendment['generation_unchanged'] and amendment['measurement_unchanged'] and amendment['scoring_unchanged']
    assert amendment['same_readiness_lock_sha256'] == sha(STAGE / 'readiness_lock.json')
    assert amendment['same_protocol_sha256'] == sha(STAGE / 'protocol.json')
    for relative, expected in amendment['code_input_hashes'].items():
        assert sha(inside(BASE, relative)) == expected, 'Amended inspection source/input changed'
    complete = read(STAGE / 'complete.json')
    assert complete['status'] == 'COMPLETE' and complete['n'] == 49
    assert complete['generation_calls'] == complete['GPT_API_calls'] == 0
    assert complete['results49_sha256'] == sha(STAGE / 'results49.json')
    result = read(STAGE / 'results49.json')
    jobs = read(STAGE / 'input_manifest49.json')
    assert len(result) == len(jobs) == 49
    assert [r['job_index'] for r in result] == list(range(1, 50))
    assert [r['class_key'] for r in result] == [j['class_key'] for j in jobs]
    assert len({j['class_key'] for j in jobs}) == 49 and len({j['repo_id'] for j in jobs}) == 15
    assert all(read(STAGE / ('job_result_%02d.json' % r['job_index'])) == r for r in result)
    official_manifest = verify_manifest(OFFICIAL, {'statistics.json', 'fixed49.csv',
        'raw_diagnostics49.json', 'repository_summary.csv', 'cluster_bootstrap_draws.csv'})
    independent_manifest = verify_manifest(INDEPENDENT, {'audit.json', 'raw_reconstructed49.json'})
    independent = read(INDEPENDENT / 'audit.json')
    assert independent['status'] == 'PASS' and independent['n'] == 49 and independent['repositories'] == 15
    assert independent['G0_all49_unchanged'] and independent['original_E1_guards'] == 'PASS'
    assert independent['raw_artifact_manifests'] == 'PASS'
    assert independent['exactly_one_measurement_per_job'] and independent['measurement_calls'] == 49
    assert independent['generation_calls'] == independent['GPT_API_calls'] == 0
    comparison = independent['official_comparison']
    assert comparison['status'] == 'PASS' and comparison['all20000_draws_match'] and comparison['fixed49_rows_match']
    assert comparison['official_statistics'] == sha(OFFICIAL / 'statistics.json')
    # Verify current archived bytes, rather than relying only on past PASS labels.
    artifact_count = 0
    for job, row in zip(jobs, result):
        work = STAGE / 'jobs' / ('%02d' % job['job_index'])
        manifest = read(work / 'artifact_manifest.json')
        for item in manifest:
            p = inside(BASE, item['path'])
            assert p.is_file() and sha(p) == item['sha256'] and p.stat().st_size == item['bytes']
            artifact_count += 1
        assert row['generation_calls'] == row['GPT_API_calls'] == row['generation_attempts'] == 0
        assert row['reused_E1_generated_tests']
    original = read(BASE / 'e49_driver/results49.json')
    assert len(original) == 49 and all(r['generation_attempts'] == 1 and r['generation_success'] for r in original)
    stats = read(OFFICIAL / 'statistics.json')
    fixed = rows(OFFICIAL / 'fixed49.csv')
    raw = read(OFFICIAL / 'raw_diagnostics49.json')
    independent_rows = read(INDEPENDENT / 'raw_reconstructed49.json')
    assert len(fixed) == len(raw) == len(independent_rows) == 49 and stats['n'] == 49
    assert [r['class_key'] for r in fixed] == [j['class_key'] for j in jobs]
    assert [r['class_key'] for r in independent_rows] == [j['class_key'] for j in jobs]
    assert stats['GPT_API_calls'] == stats['new_generation_calls'] == 0
    assert stats['historical_GPT_remeasured'] is False and stats['RQ123_membership_or_scores_updated'] is False
    assert stats['no_behavior_placeholder_classes'] == stats['no_behavior_placeholder_methods'] == 1
    assert stats['placeholder_changes_score_or_denominator'] is False
    placeholder = independent['statistics']['placeholder_diagnostic']
    assert placeholder['classes'] == placeholder['methods'] == 1 and placeholder['job_indices'] == [11]
    assert placeholder['changes_score_or_denominator'] is False
    assert placeholder['strict_evidence_is_execution_not_behavior_quality']
    assert independent['placeholder_diagnostic_changes_scores_or_membership'] is False
    placeholder_rows = [r for r in independent_rows if r['no_behavior_placeholder']]
    assert len(placeholder_rows) == 1
    entry = placeholder_rows[0]
    assert entry['job_index'] == 11 and entry['expected_methods'] == 1
    assert entry['no_behavior_placeholder_count'] == 1
    assert entry['no_behavior_placeholder_methods'] == ['notGeneratedAnyTest']
    assert Decimal(entry['E2']) == Decimal(entry['E1_archived']) == 0 and entry['focal_mutants'] == 6
    fixed_placeholder = [r for r in fixed if r['no_behavior_placeholder'] == 'True']
    assert len(fixed_placeholder) == 1 and int(fixed_placeholder[0]['job_index']) == 11
    assert stats['configuration_labels_not_scoring_scales'] and stats['no_E1_row_splicing']
    assert stats['E1_archived_not_overwritten']
    assert stats['bootstrap']['replicates'] == 20000 and stats['bootstrap']['seed'] == 20261023
    strict = sum(r['strict_measurement_evidence'] for r in independent_rows)
    assert strict == independent['statistics']['counts']['strict_measurement_evidence']
    # Manuscript reports the stricter exact-suite/report flag, not legacy suite_pass.
    mutants = [int(r['focal_mutants']) for r in fixed if int(r['focal_mutants']) > 0]
    observed = stats['observed_focal_mutants']
    assert observed['classes_with_nonempty_reports'] == len(mutants)
    assert observed['missing_or_empty'] == 49 - len(mutants)
    if mutants:
        assert [observed['min'], observed['median'], observed['max'], observed['mean']] == [min(mutants), statistics.median(mutants), max(mutants), statistics.mean(mutants)]
    frozen_guard = BASE.parents[1] / 'review_reports/minimal_camera_ready_20261023/guard_rq123_frozen.py'
    import importlib.util
    spec = importlib.util.spec_from_file_location('final_patch_gpt_guard', frozen_guard)
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    assert guard.collect() == read(guard.LOCK), 'GPT primary observations/artifacts changed'
    evidence = {'status': 'PASS', 'n': 49, 'official_manifest': official_manifest,
                'independent_manifest': independent_manifest, 'artifact_files_verified': artifact_count,
                'complete_sha256': sha(STAGE / 'complete.json'),
                'results_sha256': sha(STAGE / 'results49.json'),
                'independent_audit_sha256': sha(INDEPENDENT / 'audit.json'),
                'strict_measurement_evidence': strict, 'G0_primary_guard': 'PASS',
                'inspection_amendment_sha256': sha(amendment_path),
                'empty_placeholder_job11_retained_score0_focal_mutants6': True}
    return stats, fixed, raw, independent_rows, evidence


def f(value):
    return format(Decimal(str(value)), '.2f')


def once(text, old, new):
    assert text.count(old) == 1, 'Ambiguous or stale manuscript anchor: ' + old[:100]
    return text.replace(old, new, 1)


def interpretation(low, high):
    assert low <= high
    if low > 0:
        return ('The exploratory interval lies above zero, supporting a higher GPT pipeline mean within this cohort; integration differences and single runs preclude a general generator ranking.',
                'its exploratory interval favours GPT within this cohort',
                'supporting a higher GPT pipeline mean within this cohort, without establishing a general generator ranking')
    if high < 0:
        return ('The exploratory interval lies below zero, supporting a higher E1 pipeline mean within this cohort; integration differences and single runs preclude a general generator ranking.',
                'its exploratory interval favours E1 within this cohort',
                'supporting a higher E1 pipeline mean within this cohort, without establishing a general generator ranking')
    return ('The interval includes zero and does not establish a stable mean ordering within this cohort.',
            'its interval leaves the mean ordering uncertain',
            'leaving the mean ordering uncertain within this cohort')


def render(stats, fixed, raw, independent_rows, before):
    mean = f(stats['E2_legacy_strict_mean'])
    median = f(stats['E2_legacy_strict_median'])
    diff = stats['G0_minus_E2']
    gap, paired_median = f(diff['mean_pp']), f(diff['median_pp'])
    low, high = stats['repository_cluster_percentile_95CI_G0_minus_E2_mean_pp']
    lo, hi = f(low), f(high)
    conclusion, discussion, closing = interpretation(low, high)
    counts = stats['E2_counts']
    gate = counts['legacy_process_build']
    evidence = sum(r['strict_measurement_evidence'] for r in independent_rows)
    incomplete = [r['job_index'] for r in independent_rows if not r['strict_measurement_evidence']]
    difference_E0 = f(Decimal(str(stats['E2_legacy_strict_mean'])) - Decimal(str(stats['E0_mean'])))
    difference_word = 'increases' if Decimal(difference_E0) >= 0 else 'decreases'
    difference_magnitude = f(abs(Decimal(difference_E0)))
    direction = f"GPT is higher on {diff['G_higher']} classes, E1 on {diff['E_higher']}, with {diff['ties']} ties."
    observed = stats['observed_focal_mutants']
    if observed['classes_with_nonempty_reports']:
        mutant_text = f"Focal PIT reports are nonempty on {observed['classes_with_nonempty_reports']}/49 classes, with {observed['min']}--{observed['max']} mutants per source unit (median {f(observed['median'])}, mean {f(observed['mean'])})."
    else:
        mutant_text = 'No focal PIT report is nonempty; pipeline zero-fill does not establish oracle quality.'
    errors = json.dumps(next((r.get('XML', {}) for r in raw if r['job_index'] == 48), {}))
    if incomplete == [48] and 'sandbox' in errors.casefold() and 'TooManyResourcesException' in errors:
        runtime = 'One selected suite has sandbox/resource-limit errors and lacks complete execution evidence; this is an integration/runtime outcome, not automatically evidence of weak oracles.'
        threat = 'One E1 suite has sandbox/resource-limit errors, limiting runtime interpretation despite the recorded process gate.'
    elif incomplete:
        runtime = f'{49-evidence} selected suites lack complete execution/report evidence; these integration/execution outcomes do not automatically establish weak oracles.'
        threat = f'{49-evidence} E1 suites lack complete execution/report evidence, limiting interpretation of process-build successes.'
    else:
        runtime = 'All selected suites have exact-method, failure-free, non-skipped execution and focal PIT/JaCoCo evidence; the legacy process gate remains a distinct measure.'
        threat = 'Complete E1 suite/report evidence does not retrospectively certify historical GPT or E0 runtimes.'
    after = dict(before)
    abstract_old = r'An assertion-enabled configuration with scaffolding/runtime (E1) reaches 50.41\%, narrowing the GPT--E1 mean difference to 8.03 points (repository-bootstrap 95\% interval [-4.80, 26.99]); 41/49 E1 suites have complete execution evidence.'
    abstract_new = f'An assertion-enabled configuration with scaffolding/runtime (E1) reaches {mean}\\%, with a GPT--E1 mean difference of {gap} points (repository-bootstrap 95\\% interval [{lo}, {hi}]); {evidence}/49 E1 suites have complete execution/report evidence.'
    after['sections/00_abstract.tex'] = once(before['sections/00_abstract.tex'], abstract_old, abstract_new)
    supplement = r'''\subsection{Supplementary Assertion-enabled EvoSuite on Fixed49}
All 49 E1 keys are retained without new GPT calls or replacement classes. Table~\ref{tab:e1} compares the same fixed keys under the original process-gate/PIT scoring convention. The E1 mean __DIFF_WORD__ by __DIFF_E0__ points relative to E0; GPT's archived values remain unchanged. The GPT--E1 paired mean difference is __GAP__ points (whole-repository 95\% bootstrap interval [__LO__, __HI__]); the paired median difference is __PAIRED_MEDIAN__. __DIRECTION__ __INTERPRETATION__

\begin{table}[htbp]
\caption{Mutation pipeline scores on the same 49 historical common-build classes. E0 disables assertions; E1 enables assertions, scaffolding and runtime. Evidence flags do not change the scoring rule.}
\label{tab:e1}\centering\small
\begin{tabularx}{\linewidth}{@{}Yrrr@{}}\toprule
Statistic & GPT G0 & EvoSuite E0 & EvoSuite E1\\\midrule
Mean mutation (\%) & __GMEAN__ & __E0MEAN__ & __EMEAN__\\
Median mutation (\%) & __GMEDIAN__ & __E0MEDIAN__ & __EMEDIAN__\\
Recorded process-build & 49/49 & 49/49 & __GATE__/49\\
Suite/report evidence & not certified & not certified & __EVIDENCE__/49\\\bottomrule
\end{tabularx}\end{table}

__MUTANTS__ Each class uses one generation attempt with its scheduled seed; native test/scaffold bytes are preserved for measurement. __EVIDENCE__/49 selected suites have exact-method execution without failures/errors/skips and focal PIT/JaCoCo evidence. One E1 suite contains only an empty placeholder; execution evidence does not establish behavioral test quality. __RUNTIME__ Scores retain the original process gate and zero-fill convention; evidence flags do not independently replace scores.

The __GATE__/49 process-build count is conditional on historical common builds and a gate that can ignore test errors; it is not full-sample buildability. Assertion generation, runtime/scaffolding, seed and native integration differ from E0, so this sensitivity neither isolates an assertion effect nor demonstrates equivalence or NI on 300 classes. RQ1--RQ3 retain their original observations and memberships, and full300 comparisons remain conditional on E0.
'''
    substitutions = {'__DIFF_WORD__': difference_word, '__DIFF_E0__': difference_magnitude,
        '__GAP__': gap, '__LO__': lo, '__HI__': hi, '__PAIRED_MEDIAN__': paired_median,
        '__DIRECTION__': direction, '__INTERPRETATION__': conclusion,
        '__GMEAN__': f(stats['G0_mean']), '__E0MEAN__': f(stats['E0_mean']), '__EMEAN__': mean,
        '__GMEDIAN__': f(stats['G0_median']), '__E0MEDIAN__': f(stats['E0_median']), '__EMEDIAN__': median,
        '__GATE__': str(gate), '__EVIDENCE__': str(evidence), '__MUTANTS__': mutant_text, '__RUNTIME__': runtime}
    for token, value in substitutions.items():
        assert token in supplement
        supplement = supplement.replace(token, value)
    assert '__' not in supplement
    after['sections/04a_supplement.tex'] = supplement
    discussion_old = r'\textbf{Configuration bounds mutation conclusions.} Fixed49 pairing removes unmatched survivor populations, but E0 disables the main EvoSuite oracle mechanism. E1 preserves that cohort and failures, narrowing the mean gap without establishing stable GPT superiority. Runtime/scaffolding, explicit seeds and native integration also change, preventing an assertion-only causal claim. Neither survivor cohort replaces the full300 baseline.'
    discussion_new = r'\textbf{Configuration bounds mutation conclusions.} Fixed49 pairing removes unmatched survivor populations, but E0 disables the main EvoSuite oracle mechanism. E1 retains that cohort and failures; ' + discussion + '. Runtime/scaffolding, explicit seeds and native integration also change, preventing an assertion-only causal claim. Neither survivor cohort replaces the full300 baseline.'
    after['sections/05_discussion.tex'] = once(before['sections/05_discussion.tex'], discussion_old, discussion_new)
    threat1_old = "E1 separately records generated bytes, selected suites, failures/skips, reports and focal bytecode without changing GPT's primary scores."
    threat1_new = "E1 separately verifies generated bytes, selected methods, failures/skips, reports, production bytecode and permitted dependency/selector changes without changing GPT's primary scores."
    threat2_old = 'Incomplete E1 runtime evidence constrains process-build successes.'
    after['sections/06_threats.tex'] = once(once(before['sections/06_threats.tex'], threat1_old, threat1_new), threat2_old, threat)
    closing_old = r'Assertion-enabled E1 reaches mean 50.41\% on fixed49; the GPT--E1 gap is 8.03 points with interval [-4.80, 26.99], providing no stable GPT advantage. These supplements retain GPT RQ1--RQ3 and the full300 baseline. Broader claims require compatible runtime evidence and repeated runs.'
    closing_new = f'Assertion-enabled E1 reaches mean {mean}\\% on fixed49; the GPT--E1 gap is {gap} points with interval [{lo}, {hi}], {closing}. These supplements retain GPT RQ1--RQ3 and the full300 baseline. Broader claims require compatible runtime evidence and repeated runs.'
    after['sections/07_conclusion.tex'] = once(before['sections/07_conclusion.tex'], closing_old, closing_new)
    method = once(before['sections/03_method.tex'], 'only for inherited multiple executions with leading-slash patterns.', 'only for inherited Surefire 2.17 multiple executions with leading-slash patterns.')
    method = once(method, 'Production and available selected-test bytecode, ordered classpaths and semantic POM changes are checked.', 'Production and available selected-test bytecode and semantic POM changes are checked; the ordered production classpath is unchanged and the test-classpath delta is limited to JUnit/Hamcrest.')
    after['sections/03_method.tex'] = method
    changed = {name: value for name, value in after.items() if value != before[name]}
    assert set(changed) == ALLOWED
    for name, value in changed.items():
        assert not re.search(r'\bE2\b|E1\s*(?:->|→)\s*E2|debug|trial|previous attempt|rerun history', value, re.I)
        assert value.count(r'\begin{table}') == before[name].count(r'\begin{table}')
        assert value.count(r'\end{table}') == before[name].count(r'\end{table}')
        assert value.count(r'\section{') == before[name].count(r'\section{')
        assert value.count('{') == value.count('}'), 'Unbalanced braces in ' + name
    assert after['sections/04_results.tex'] == before['sections/04_results.tex']
    assert after['sections/01_introduction.tex'] == before['sections/01_introduction.tex']
    unchanged = {name: SOURCE_PINS[name] for name in SOURCE_PINS if name not in ALLOWED}
    return changed, {'E1_mean': mean, 'E1_median': median, 'G0_minus_E1_mean_pp': gap,
        'repository95CI': [lo, hi], 'paired_counts_G_E_ties': [diff['G_higher'], diff['E_higher'], diff['ties']],
        'strict_evidence': evidence, 'incomplete_evidence_job_indices': incomplete,
        'historical_results_and_RQ_intro_byte_identical': True, 'unchanged_source_pins': unchanged,
        'public_configuration_label': 'E1', 'GPT_primary_memberships': [61, 45, 300],
        'public_trial_history_added': False, 'new_tables': 0, 'new_RQs': 0,
        'one_empty_placeholder_explicitly_reported': True, 'execution_evidence_is_behavioral_quality': False}


def register_own_creation():
    relative = Path(__file__).relative_to(BASE).as_posix()
    records = [e for e in audit.events() if e['kind'] == 'NEW_FILE_REGISTERED' and e.get('path') == relative]
    if records:
        assert records[-1]['sha256'] == sha(__file__), 'Prepared script changed after registration'
    else:
        audit.log('NEW_FILE_REGISTERED', path=relative, sha256=sha(__file__),
                  bytes=Path(__file__).stat().st_size,
                  change_type='New isolated final manuscript patcher; gated on full49 and independent raw PASS; no execution or source edit at creation')


def apply(changed, before, source_hashes, evidence, interpretation_summary):
    backup = REV / 'backups/final_compat49_results_v3'
    backup.mkdir(parents=True, exist_ok=False)
    records = []
    # Back up and hash all affected files before any mutation.
    for relative, value in changed.items():
        original = SOURCE / relative
        saved = backup / relative
        saved.parent.mkdir(parents=True, exist_ok=True)
        raw = original.read_bytes()
        assert digest(raw) == source_hashes[relative]
        with saved.open('xb') as handle:
            handle.write(raw)
        assert sha(saved) == source_hashes[relative]
        after = value.encode('utf-8')
        diff_path = backup / (relative + '.diff')
        diff = ''.join(difflib.unified_diff(before[relative].splitlines(True), value.splitlines(True),
                    fromfile='before/' + relative, tofile='after/' + relative))
        with diff_path.open('x', encoding='utf-8', newline='') as handle:
            handle.write(diff)
        records.append({'path': original.relative_to(BASE).as_posix(), 'before_sha256': digest(raw),
                        'after_sha256': digest(after), 'backup': saved.relative_to(BASE).as_posix(),
                        'backup_sha256': sha(saved), 'diff': diff_path.relative_to(BASE).as_posix(),
                        'diff_sha256': sha(diff_path), 'old_words': len(before[relative].split()),
                        'new_words': len(value.split()), 'new_bytes': after,
                        'reason': 'Minimal final fixed49 evidence update after official and independent full49 PASS; historical RQ/results/GPT untouched',
                        'script_sha256': sha(__file__)})
    audit.log('MANUSCRIPT_PATCH_ADMISSION', script_sha256=sha(__file__), evidence=evidence,
              source_pins=source_hashes, changed_files=len(records), all_backups_verified=True,
              no_experiment_or_PDF_build_calls=True)
    for record in records:
        target = BASE / record['path']
        assert sha(target) == record['before_sha256'], 'Concurrent source change detected'
        data = record.pop('new_bytes')
        target.write_bytes(data)
        assert sha(target) == record['after_sha256']
        audit.log('FILE_REVISION', **record)
    assert {p.relative_to(SOURCE).as_posix() for p in SOURCE.rglob('*') if p.is_file()} == set(SOURCE_PINS)
    for relative, expected in source_hashes.items():
        record = next((r for r in records if r['path'] == (SOURCE / relative).relative_to(BASE).as_posix()), None)
        assert sha(SOURCE / relative) == (record['after_sha256'] if record else expected)
    summary = {'status': 'PATCHED_PENDING_BUILD_AND_VISUAL_QA', 'script_sha256': sha(__file__),
               'evidence': evidence, 'interpretation': interpretation_summary,
               'files': records, 'historical_results_preserved': True,
               'total_word_delta': sum(r['new_words'] - r['old_words'] for r in records),
               'PDF_pages_verified': False, 'target_total_pages_including_references': 15,
               'publication_ready': False, 'artifact_URL_pending': True}
    path = backup / 'revision.json'
    with path.open('x', encoding='utf-8') as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
        handle.write('\n')
    audit.log('MANUSCRIPT_PATCH_COMPLETE', path=path.relative_to(BASE).as_posix(), sha256=sha(path),
              files=len(records), historical_results_preserved=True, requires_build_visual_QA=True)
    return summary


def self_test():
    assert f('8.0304081632653') == '8.03'
    assert f('-0.004') == '-0.00'
    assert 'above zero' in interpretation(0.1, 2)[0]
    assert 'below zero' in interpretation(-2, -0.1)[0]
    assert 'includes zero' in interpretation(-1, 2)[0]
    assert 'includes zero' in interpretation(0, 2)[0]
    refused = 0
    for anchor in ['', 'old old']:
        try:
            once(anchor, 'old', 'new')
        except AssertionError:
            refused += 1
    assert refused == 2
    # Partial cohorts and missing completion evidence are never accepted by main.
    assert len(ALLOWED) == 6 and 'sections/04_results.tex' not in ALLOWED
    value = {'status': 'PASS', 'formatting_and_interval_branches': True,
             'missing_duplicate_anchors_refused': refused, 'allowed_scope_files': len(ALLOWED),
             'actual_manuscript_patch_calls': 0, 'Java_Maven_API_build_calls': 0}
    audit.log('STATIC_VALIDATION', script=Path(__file__).relative_to(BASE).as_posix(), **value)
    print(json.dumps(value))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--apply', action='store_true', help='Apply only after every full49/hash/audit/source gate passes')
    group.add_argument('--check', action='store_true', help='Validate and preview minimal changes without writing manuscript')
    group.add_argument('--self-test', action='store_true', help='Synthetic formatter/guard checks; no experiment or manuscript write')
    args = parser.parse_args()
    register_own_creation()
    if args.self_test:
        self_test()
        return
    source_hashes = assert_source_pins()
    stats, fixed, raw, reconstructed, evidence = validate_completed_evidence()
    before = {relative: (SOURCE / relative).read_text(encoding='utf-8') for relative in SOURCE_PINS if relative.endswith('.tex')}
    changed, summary = render(stats, fixed, raw, reconstructed, before)
    if args.apply:
        print(json.dumps(apply(changed, before, source_hashes, evidence, summary), ensure_ascii=False, indent=2))
    else:
        print(json.dumps({'status': 'READY_FOR_PATCH', 'changed_files': list(changed),
                          'word_delta': sum(len(v.split()) - len(before[k].split()) for k, v in changed.items()),
                          'interpretation': summary, 'evidence': evidence, 'manuscript_modified': False,
                          'build_or_experiment_calls': 0}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
