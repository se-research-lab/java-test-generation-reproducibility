"""Independent, read-only completed49 raw audit. Never launches experiment/API tools.

All score/statistical computations are implemented here without importing the
measurement driver or either official analyzer. New output is exclusive-create.
"""
import argparse
import csv
import hashlib
import importlib.util
import json
import re
import statistics
from collections import Counter
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree as ET

import numpy as np
from junit_method_inventory_v1 import inventory_java_tests, normalize_case

BASE = Path(__file__).resolve().parents[1]
STAGE = BASE / 'e49_measurement_compat_v1'
OLD = BASE / 'e49_driver'
OUT = BASE / 'validation/independent_compat49_raw_v1'
EXCLUDED = {'.git', 'target', 'node_modules', 'evosuite-report', '.gradle'}
GOALS = ['clean', 'verify', 'jacoco:prepare-agent', 'jacoco:report',
         'org.pitest:pitest-maven:mutationCoverage']


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def D(value):
    return Decimal(str(value))


def csv_rows(path, header=True):
    path = Path(path)
    if not path.is_file():
        return []
    with path.open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle) if header else csv.reader(handle))


def resolved(relative):
    relative = Path(relative)
    assert not relative.is_absolute(), 'Archive path must be relative'
    path = (BASE / relative).resolve()
    assert path.is_relative_to(BASE.resolve()), 'Path outside isolated workspace'
    return path


def inventory(root):
    return {p.relative_to(root).as_posix(): {'sha256': sha(p), 'bytes': p.stat().st_size}
            for p in root.rglob('*') if p.is_file()}


def bytecode(root):
    return {p.relative_to(root).as_posix(): {'sha256': sha(p), 'bytes': p.stat().st_size}
            for p in root.rglob('*.class') if p.is_file()}


def selected_bytecode(module, fqcn):
    prefix = fqcn.replace('.', '/')
    return {name: value for name, value in bytecode(module / 'target/test-classes').items()
            if any(name[:-6] == p or name[:-6].startswith(p + '$')
                   for p in [prefix, prefix + '_scaffolding'])}


def fingerprint(mutants):
    # Duplicate retention is essential: no set(), and no assertion of full PIT ID.
    serial = json.dumps(sorted([list(r[:5]) for r in mutants]),
                        ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(serial).hexdigest()


def focal_rows(mutants, job):
    return [r for r in mutants
            if r[0].removesuffix('.java') == job['focal_class']
            and r[1].rpartition('.')[0] == job['package']]


def normalize(name, fqcn, methods):
    method = normalize_case(name, fqcn)
    return method if method in methods else None


def xml_evidence(module, fqcn):
    java = module / 'src/test/java' / Path(*fqcn.split('.')).with_suffix('.java')
    source_inventory = inventory_java_tests(java.read_text(encoding='utf-8'))
    methods = source_inventory['methods']
    suites, cases = [], []
    for path in sorted((module / 'target/surefire-reports').glob('TEST-*.xml')):
        root = ET.parse(path).getroot()
        assert root.get('name') == fqcn, 'Foreign canonical Surefire suite'
        suite = {'name': fqcn, **{k: int(root.get(k, '0'))
                 for k in ['tests', 'failures', 'errors', 'skipped']}}
        suites.append(suite)
        for case in root.findall('testcase'):
            assert case.get('classname') == fqcn, 'Foreign canonical testcase'
            cases.append({'class': fqcn, 'name': case.get('name'),
                          'method': normalize(case.get('name'), fqcn, methods),
                          **{k: len(case.findall(k[:-1] if k != 'skipped' else 'skipped'))
                             for k in ['errors', 'failures', 'skipped']}})
    legacy = bool(suites) and sum(s['tests'] for s in suites) > 0 and all(
        s['errors'] + s['failures'] == 0 for s in suites)
    strict = (bool(methods) and bool(cases)
              and Counter(c['method'] for c in cases) == Counter(methods)
              and all(c['errors'] + c['failures'] + c['skipped'] == 0 for c in cases)
              and all(s['errors'] + s['failures'] + s['skipped'] == 0 for s in suites))
    return {'suites': suites, 'cases': cases, 'expected_methods': methods,
            'source_inventory': source_inventory,
            'no_behavior_placeholder_methods': source_inventory['no_behavior_placeholder_methods'],
            'no_behavior_placeholder_count': source_inventory['no_behavior_placeholder_count'],
            'legacy_pass': legacy, 'strict_pass': strict,
            'skipped': sum(s['skipped'] for s in suites),
            'non_skipped': sum(s['tests'] - s['skipped'] for s in suites)}


def assert_complete(stage):
    assert (stage / 'complete.json').is_file(), 'Partial49 refused: no completion certificate'
    complete = read(stage / 'complete.json')
    assert complete['status'] == 'COMPLETE' and complete['n'] == 49
    assert complete['generation_calls'] == complete['GPT_API_calls'] == 0
    assert sha(stage / 'results49.json') == complete['results49_sha256']
    paths = [stage / ('job_result_%02d.json' % n) for n in range(1, 50)]
    assert all(p.is_file() for p in paths), 'Partial49 refused: missing slot'
    results = [read(p) for p in paths]
    assert results == read(stage / 'results49.json')
    assert sorted(p.name for p in stage.glob('job_result_*.json')) == sorted(p.name for p in paths)
    jobs = read(stage / 'input_manifest49.json')
    gpt = csv_rows(BASE / 'outputs/paired49.csv')
    original = read(OLD / 'results49.json')
    assert len(jobs) == len(gpt) == len(results) == len(original) == 49
    assert [j['job_index'] for j in jobs] == [r['job_index'] for r in results] == list(range(1, 50))
    keys = [j['class_key'] for j in jobs]
    assert len(set(keys)) == 49
    assert keys == [r['class_key'] for r in gpt] == [r['class_key'] for r in results] == [r['class_key'] for r in original]
    repos = [j['repo_id'] for j in jobs]
    assert len(set(repos)) == 15
    assert repos == [g['repo_id'] for g in gpt] == [r['repo_id'] for r in results]
    return jobs, gpt, results, original


def check_inspection_amendment(stage, lock):
    amendment = read(stage / 'inspection_amendment_v1.json')
    assert amendment['same_readiness_lock_sha256'] == sha(stage / 'readiness_lock.json')
    assert amendment['same_protocol_sha256'] == sha(stage / 'protocol.json')
    assert amendment['original_admission_sha256'] == sha(stage / 'admission.json')
    assert amendment['changes'] == 'inspection_only'
    assert all(amendment[key] is True for key in
               ['generation_unchanged', 'measurement_unchanged', 'scoring_unchanged'])
    extension = amendment['code_input_hashes']
    assert extension and not (set(extension) & set(lock['code_input_hashes']))
    fix_path=stage/'independent_audit_correction_v1.json'
    fix=read(fix_path)
    assert fix['changes']=='audit_metadata_only' and fix['score_gate_config_unchanged'] is True
    assert fix['same_readiness_lock_sha256']==sha(stage/'readiness_lock.json')
    assert fix['same_inspection_amendment_sha256']==sha(stage/'inspection_amendment_v1.json')
    extra=fix['code_input_hashes'];assert not(set(extra)&(set(extension)|set(lock['code_input_hashes'])))
    assert extra.get(Path(__file__).relative_to(BASE).as_posix())==sha(__file__)
    for relative,digest in extra.items():assert sha(resolved(relative))==digest,'Audit metadata correction changed'
    helper = BASE / 'src/junit_method_inventory_v1.py'
    assert extension.get(helper.relative_to(BASE).as_posix()) == sha(helper)
    for relative, digest in extension.items():
        assert sha(resolved(relative)) == digest, 'Inspection extension changed'
    return amendment


def check_lock_recovery(stage):
    lock = read(stage / 'readiness_lock.json')
    for path, digest in lock['code_input_hashes'].items():
        assert sha(resolved(path)) == digest, 'Locked code/input changed'
    for name in ['tool_hashes', 'context_source_hashes']:
        for path, digest in lock.get(name, {}).items():
            p = Path(path) if Path(path).is_absolute() else resolved(path)
            assert sha(p) == digest, 'Locked tool/context changed'
    admission = read(stage / 'admission.json')
    assert admission['readiness_sha256'] == sha(stage / 'readiness_lock.json')
    assert admission['protocol_sha256'] == sha(stage / 'protocol.json')
    assert admission['order'] == lock['measurement_order']
    assert admission['generation_calls'] == admission['GPT_API_calls'] == 0
    recovery = stage / 'resume_guard01'
    cert = read(recovery / 'admission.json')
    assert cert['same_readiness_lock_sha256'] == sha(stage / 'readiness_lock.json')
    assert cert['same_protocol_sha256'] == sha(stage / 'protocol.json')
    assert cert['original_admission_sha256'] == sha(stage / 'admission.json')
    assert cert['retained_measurement_calls'] == 1 and cert['new_measurement_calls_for18'] == 0
    assert cert['same_driver_sha256'] in lock['code_input_hashes'].values()
    assert cert['controller_sha256'] == sha(BASE / 'src/resume_fixed49_measurement_after_interruption_v2.py')
    prefix_path = recovery / 'retained_slot18_files.json'
    assert cert['retained_slot18_files_sha256'] == sha(prefix_path)
    prefix = read(prefix_path)
    assert prefix
    for relative, item in prefix.items():
        path = stage / 'jobs/18' / relative
        assert path.resolve().is_relative_to((stage / 'jobs/18').resolve())
        assert sha(path) == item['sha256'] and path.stat().st_size == item['bytes']
    assert cert['remaining_order'] == [i for i in admission['order'] if i != 18]
    amendment = check_inspection_amendment(stage, lock)
    recovery02 = stage / 'resume_guard02'
    cert02 = read(recovery02 / 'admission.json')
    assert cert02['same_driver_v4_sha256'] == cert['same_driver_sha256']
    assert cert02['amended_driver_sha256'] in amendment['code_input_hashes'].values()
    assert cert02['controller_sha256'] in amendment['code_input_hashes'].values()
    assert cert02['same_readiness_lock_sha256'] == sha(stage / 'readiness_lock.json')
    assert cert02['same_protocol_sha256'] == sha(stage / 'protocol.json')
    assert cert02['original_admission_sha256'] == sha(stage / 'admission.json')
    assert cert02['inspection_amendment_sha256'] == sha(stage / 'inspection_amendment_v1.json')
    assert cert02['completed_order'] == [18, 19] + list(range(1, 11))
    assert cert02['retained_measurement_job11'] == 1 and cert02['new_measurement_calls_for11'] == 0
    assert cert02['remaining_order'] == admission['order'][13:]
    prefix02_path = recovery02 / 'retained_completed_prefix_files.json'
    assert cert02['retained_completed_prefix_sha256'] == sha(prefix02_path)
    prefix02 = read(prefix02_path)
    assert prefix02
    for relative, item in prefix02.items():
        path = resolved(relative)
        assert path.is_relative_to(stage.resolve())
        assert sha(path) == item['sha256'] and path.stat().st_size == item['bytes'], 'Completed prefix changed after parser amendment'
    for index in cert02['completed_order']:
        for path in [stage / ('job_result_%02d.json' % index),
                     stage / 'jobs' / ('%02d' % index) / 'result.json',
                     stage / 'jobs' / ('%02d' % index) / 'artifact_manifest.json']:
            assert path.relative_to(BASE).as_posix() in prefix02, 'Completed prefix certificate omits result/archive'
    slot11_path = recovery02 / 'retained_slot11_files.json'
    assert cert02['retained_slot11_files_sha256'] == sha(slot11_path)
    slot11 = read(slot11_path)
    assert slot11
    slot11_root = stage / 'jobs/11'
    for relative, item in slot11.items():
        path = (slot11_root / relative).resolve()
        assert not Path(relative).is_absolute() and path.is_relative_to(slot11_root.resolve())
        assert sha(path) == item['sha256'] and path.stat().st_size == item['bytes'], 'Retained job11 evidence changed'
    events = [json.loads(line) for line in (stage / 'events.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
    resume_positions = [i for i, event in enumerate(events) if event['kind'] == 'RESUME_AFTER_INSPECTION_AMENDMENT']
    assert len(resume_positions) == 1, 'Missing or duplicate parser-amendment recovery marker'
    assert not any(event['kind'] == 'ABORT' for event in events[resume_positions[0] + 1:]), 'Later batch abort invalidates completion'

    done = [e for e in events if e['kind'] == 'JOB_COMPLETE']
    assert [e['job_index'] for e in done] == admission['order'], 'Missing/duplicate/reordered completion'
    for event in done:
        i = event['job_index']
        assert event['result_sha256'] == sha(stage / ('job_result_%02d.json' % i))
        assert event['artifact_manifest_sha256'] == sha(stage / 'jobs' / ('%02d' % i) / 'artifact_manifest.json')
    return {'recovery18_prefix_files': len(prefix), 'measurement_repeated_for18': False,
            'inspection_amendment_sha256': sha(stage / 'inspection_amendment_v1.json'),
            'completed_prefix_files': len(prefix02), 'retained_job11_files': len(slot11),
            'measurement_repeated_for11': False, 'original_ABORT_events_retained': sum(e['kind'] == 'ABORT' for e in events),
            'no_abort_after_inspection_resume': True,
            'completion_event_count': len(done), 'locked_inputs': len(lock['code_input_hashes']),
            'additional_inspection_sources': len(amendment['code_input_hashes'])}


def gpt_guard():
    path = BASE.parents[1] / 'review_reports/minimal_camera_ready_20261023/guard_rq123_frozen.py'
    spec = importlib.util.spec_from_file_location('independent_read_only_gpt_guard', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.collect() == read(module.LOCK), 'Original GPT guard failed'


def validate_policy(work, module, oldmodule, fqcn, policy):
    ns = {'m': 'http://maven.apache.org/POM/4.0.0'}
    def text(element, path):
        return element.findtext(path, namespaces=ns)
    def normalized(element):
        content = element.text.strip() if element.text and element.text.strip() else None
        tail = element.tail.strip() if element.tail and element.tail.strip() else None
        return (element.tag, tuple(sorted(element.attrib.items())), content, tail,
                tuple(normalized(child) for child in element))
    before = work / 'backup_before_policy/pom.xml'
    assert sha(before) == policy['before_sha256'] == sha(oldmodule / 'pom.xml')
    assert sha(work / 'policy_patch.diff') == policy['diff_sha256']
    original, changed = ET.parse(before).getroot(), ET.parse(module / 'pom.xml').getroot()
    kinds = [c['kind'] for c in policy['changes']]
    assert kinds.count('test_JUnit_API') == int(policy['JUnit_rule_applied'])
    assert kinds.count('regular_exact_relative_include') == int(policy['selector_rule_applied'])
    assert len(kinds) == int(policy['JUnit_rule_applied']) + int(policy['selector_rule_applied'])
    for change in policy['changes']:
        if change['kind'] == 'test_JUnit_API':
            dependencies = [d for d in changed.findall('m:dependencies/m:dependency', ns)
                            if text(d, 'm:groupId') == 'junit' and text(d, 'm:artifactId') == 'junit']
            assert len(dependencies) == 1
            dependency = dependencies[0]
            assert text(dependency, 'm:scope') == 'test'
            version = dependency.find('m:version', ns)
            assert version is not None and version.text == '4.13.2' == change['new_version']
            if change['old_version'] is None:
                dependency.remove(version)
            else:
                version.text = change['old_version']
        elif change['kind'] == 'regular_exact_relative_include':
            plugins = [p for p in changed.findall('m:build/m:plugins/m:plugin', ns)
                       if text(p, 'm:artifactId') == 'maven-surefire-plugin']
            assert len(plugins) == 1
            plugin = plugins[0]
            executions = plugin.find('m:executions', ns)
            assert executions is not None and len(executions) == 1
            execution = executions[0]
            assert text(execution, 'm:id') == 'regular-tests'
            includes = execution.find('m:configuration/m:includes', ns)
            assert includes is not None and includes.attrib == {'combine.self': 'override'}
            assert len(includes) == 1 and includes[0].text == fqcn.replace('.', '/') + '.java' == change['new_include']
            plugin.remove(executions)
        else:
            raise AssertionError('Unexpected policy mutation')
    assert normalized(original) == normalized(changed), 'Semantic POM delta outside policy'
    if not policy['changes']:
        assert sha(before) == sha(module / 'pom.xml'), 'Unpatched POM bytes changed'


def inspect(stage, job, frozen, row, oldrow):
    index = job['job_index']
    work = stage / 'jobs' / ('%02d' % index)
    repo, module = work / 'repo', work / 'repo' / job['module']
    oldwork = OLD / 'jobs' / ('%02d' % index)
    oldmodule = oldwork / 'repo' / job['module']
    fqcn = job['selected_test_fqcn']
    assert read(work / 'result.json') == row
    assert row['GPT_API_calls'] == row['generation_calls'] == row['generation_attempts'] == 0
    assert row['reused_E1_generated_tests'] and row['generated_bytes_unchanged']
    assert row['seed'] == oldrow['seed'] == job['seed']
    assert bool(row['archived_E1_generation_success']) == bool(oldrow['generation_success'])
    for key, source in [('G0_archived_mutation_percent', 'gpt_mutation_coverage'),
                        ('E0_archived_mutation_percent', 'evosuite_mutation_coverage')]:
        assert D(row[key]) == D(frozen[source]), 'Archived class score changed'
    assert D(row['G0_archived_mutation_percent']) == D(job['gpt_archived_mutation_percent'])
    assert D(row['E1_archived_mutation_percent']) == D(oldrow['legacy_strict_mutation_percent'])
    assert sha(oldwork / 'result.json') == job['E1_result_sha256']
    before = read(work / 'original_E1_guard_before.json')
    assert before == read(work / 'original_E1_guard_after.json') == inventory(oldwork), 'Original E1 bytes/membership changed'
    manifests = read(work / 'artifact_manifest.json')
    names = [item['path'] for item in manifests]
    assert len(names) == len(set(names)) and names
    for item in manifests:
        path = resolved(item['path'])
        assert path.is_relative_to(work.resolve())
        assert sha(path) == item['sha256'] and path.stat().st_size == item['bytes']
    artifacts = set(names)
    def archived(path):
        assert path.relative_to(BASE).as_posix() in artifacts, 'Key raw evidence absent from archive'
    policy = read(work / 'policy_applied.json')
    assert policy['only_allowlisted_semantic_changes']
    assert isinstance(policy['JUnit_rule_applied'], bool) and isinstance(policy['selector_rule_applied'], bool)
    assert not (policy['JUnit_rule_applied'] and policy['selector_rule_applied']), 'Unexpected combined policy stratum'
    assert sha(module / 'pom.xml') == policy['after_sha256']
    validate_policy(work, module, oldmodule, fqcn, policy)
    original_sources = read(work / 'input_source_manifest.json')
    assert sha(work / 'input_source_manifest.json') == job['input_source_manifest_sha256']
    expected = {r['relative']: r['sha256'] for r in original_sources}
    expected[(Path(job['module']) / 'pom.xml').as_posix()] = policy['after_sha256']
    actual = {p.relative_to(repo).as_posix(): sha(p) for p in repo.rglob('*')
              if p.is_file() and not (set(p.relative_to(repo).parts) & EXCLUDED)}
    assert actual == expected, 'Source closure changed outside allowed module POM'
    assert sha(repo / job['focal_path']) == job['focal_sha256']
    for relative, digest in read(work / 'generated_manifest.json').items():
        assert sha(work / relative) == digest == sha(oldwork / relative), 'Reused generated bytes changed'
    assert sha(work / 'generated_manifest.json') == job['generated_manifest_sha256']
    commands = [read(p) for p in sorted(work.glob('command_*.json'))]
    measurement_commands = []
    for c in commands:
        args = c['argv']
        assert '-jar' not in args and not any('openai' in str(a).lower() for a in args)
        java_metadata=Path(args[0]).name.lower() in ['java','java.exe'] and args[1:]==['-version']
        expected_cwd=work if java_metadata else module
        assert Path(c['cwd']).resolve()==expected_cwd.resolve(),'Unexpected cwd outside declared Java metadata or Maven module'
        selectors = [a for a in args if a.startswith('-Dtest=')]
        assert not selectors or selectors == ['-Dtest=' + fqcn]
        for stream in ['stdout', 'stderr']:
            path = resolved(c[stream])
            assert sha(path) == c[stream + '_sha256']
            archived(path)
        if any('mutationCoverage' in a for a in args):
            measurement_commands.append(c)
            assert args[-5:] == GOALS, 'Measurement lifecycle changed'
    assert len(measurement_commands) == 1, 'Measurement duplicated or missing'
    command = measurement_commands[0]
    output = resolved(command['stdout']).read_text(encoding='utf-8', errors='replace')
    gate = int(not command.get('timeout', False) and command.get('returncode') != -999
               and 'BUILD SUCCESS' in output)
    assert gate == row['legacy_process_build']
    assert row['command_returncode'] == command['returncode']
    measurement = read(work / 'measurement_audit.json')
    baseline = read(work / 'production_class_baseline.json')
    classes = bytecode(module / 'target/classes')
    assert all(name in baseline and value == baseline[name] for name, value in classes.items()), 'Production bytecode differs'
    missing = sorted(set(baseline) - set(classes))
    assert measurement['missing_production_classes'] == missing
    assert not gate or not missing, 'Successful gate without original production bytecode'
    testbaseline = read(work / 'generated_test_bytecode_baseline.json')
    oldtests = selected_bytecode(oldmodule, fqcn)
    assert testbaseline['classes'] == oldtests
    newtests = selected_bytecode(module, fqcn)
    available = bool(oldtests)
    if available:
        assert all(name in oldtests and value == oldtests[name] for name, value in newtests.items())
        assert not gate or newtests == oldtests
    aftertests = read(work / 'generated_test_bytecode_after.json')
    assert aftertests['classes'] == newtests and aftertests['count'] == len(newtests)
    for root in [module / 'target/classes', module / 'target/test-classes']:
        for relative in (classes if root.name == 'classes' else newtests):
            archived(root / relative)
    xml = xml_evidence(module, fqcn)
    assert xml['suites'] == row['surefire_suites']
    assert bool(row['suite_pass']) == xml['legacy_pass']
    assert bool(row['strict_suite_evidence']) == xml['strict_pass']
    assert xml['expected_methods'] == measurement['expected_methods']
    assert xml['cases'] == measurement['canonical_cases']
    assert xml['strict_pass'] == measurement['complete_suite_evidence']
    for key in ['no_behavior_placeholder_methods', 'no_behavior_placeholder_count']:
        if key in measurement:
            assert measurement[key] == xml[key], 'Placeholder diagnostic differs from frozen annotated source'
    for path in (module / 'target/surefire-reports').glob('TEST-*.xml'):
        archived(path)
    pit_path = module / 'target/pit-reports/mutations.csv'
    mutants = csv_rows(pit_path, False)
    assert all(len(r) == 7 for r in mutants), 'Unexpected PIT CSV schema'
    assert not any(r[5] == 'KILLED' and fqcn not in r[6] for r in mutants), 'Foreign PIT killing test'
    focal = focal_rows(mutants, job)
    killed = sum(r[5] == 'KILLED' for r in focal)
    old_pit = oldmodule / 'target/pit-reports/mutations.csv'
    old_focal = focal_rows(csv_rows(old_pit, False), job)
    mutant_baseline = read(work / 'focal_mutant_baseline.json')
    assert mutant_baseline['n'] == len(old_focal)
    assert mutant_baseline['multiset_sha256'] == (fingerprint(old_focal) if old_focal else None)
    if old_pit.is_file():
        assert mutant_baseline['PIT_CSV_sha256'] == sha(old_pit)
    same = bool(focal and old_focal) and fingerprint(focal) == fingerprint(old_focal)
    assert same == measurement['focal_mutant_multiset_matches_E1']
    assert not focal or same, 'Focal mutant inventory changed'
    rawscore = round(100 * killed / len(focal), 2) if focal else None
    score = rawscore if gate and rawscore is not None else 0.0
    assert len(focal) == row['focal_mutants'] and killed == row['killed_mutants']
    assert D(score) == D(row['legacy_strict_mutation_percent'])
    assert rawscore == row['mutation_score_percent']
    assert len(mutants) == row['module_mutants'] and pit_path.is_file() == row['pit_report_present']
    if pit_path.is_file():
        archived(pit_path)
    jacoco = module / 'target/site/jacoco/jacoco.csv'
    focal_coverage = [r for r in csv_rows(jacoco)
                      if r.get('CLASS') == job['focal_class']
                      and r.get('PACKAGE', '').replace('/', '.') == job['package']]
    assert focal_coverage == row['jacoco_focal_rows']
    if jacoco.is_file():
        archived(jacoco)
    legacy_evidence = bool(xml['legacy_pass'] and focal and focal_coverage)
    strict_evidence = bool(xml['strict_pass'] and focal and focal_coverage)
    assert legacy_evidence == bool(row['measurement_evidence_complete'])
    assert strict_evidence == bool(row['strict_measurement_evidence']) == bool(measurement['complete_measurement_evidence'])
    stratum = 'JUnit-applied' if policy['JUnit_rule_applied'] else 'selector-applied' if policy['selector_rule_applied'] else 'neither'
    return {'job_index': index, 'class_key': job['class_key'], 'repo_id': job['repo_id'],
            'G0': str(D(frozen['gpt_mutation_coverage'])), 'E0': str(D(frozen['evosuite_mutation_coverage'])),
            'E1_archived': str(D(oldrow['legacy_strict_mutation_percent'])), 'E2': str(D(score)),
            'E2_minus_E1_pp': str(D(score) - D(oldrow['legacy_strict_mutation_percent'])),
            'policy_stratum': stratum, 'G0_unchanged': True, 'gate': gate,
            'legacy_suite_pass': xml['legacy_pass'], 'strict_suite_evidence': xml['strict_pass'],
            'no_behavior_placeholder': bool(xml['no_behavior_placeholder_count']),
            'no_behavior_placeholder_count': xml['no_behavior_placeholder_count'],
            'no_behavior_placeholder_methods': xml['no_behavior_placeholder_methods'],
            'legacy_measurement_evidence': legacy_evidence, 'strict_measurement_evidence': strict_evidence,
            'focal_mutants': len(focal), 'killed_mutants': killed,
            'multiset_matches_E1': same, 'multiset_sha256': fingerprint(focal) if focal else None,
            'JaCoCo_focal_present': bool(focal_coverage), 'PIT_report_present': pit_path.is_file(),
            'canonical_XML_cases': len(xml['cases']), 'expected_methods': len(xml['expected_methods']),
            'skipped': xml['skipped'], 'non_skipped': xml['non_skipped'],
            'production_classes': len(classes), 'missing_production_classes': len(missing),
            'original_E1_guard_files': len(before), 'raw_artifact_files': len(artifacts),
            'measurement_calls': 1, 'generation_calls': 0, 'GPT_API_calls': 0,
            'generated_test_bytecode_baseline_available': available,
            'generated_test_bytecode_unchanged_claim_available': available and newtests == oldtests}


def summaries(rows):
    def describe(values):
        return {'mean': str(sum(values) / D(len(values))), 'median': str(statistics.median(values))}
    def delta(a, b):
        values = [D(r[a]) - D(r[b]) for r in rows]
        return {**describe(values), 'first_higher': sum(v > 0 for v in values),
                'second_higher': sum(v < 0 for v in values), 'ties': sum(v == 0 for v in values)}
    result = {'n': 49, 'repositories': 15,
              'arms': {k: describe([D(r[k]) for r in rows]) for k in ['G0', 'E0', 'E1_archived', 'E2']},
              'G0_minus_E2': delta('G0', 'E2'), 'G0_minus_E0': delta('G0', 'E0'),
              'E2_minus_E1': delta('E2', 'E1_archived'), 'E2_minus_E0': delta('E2', 'E0')}
    repos = sorted({r['repo_id'] for r in rows})
    sums, counts = [], []
    for repo in repos:
        selected = [r for r in rows if r['repo_id'] == repo]
        sums.append(float(sum(D(r['G0']) - D(r['E2']) for r in selected)))
        counts.append(len(selected))
    indices = np.random.default_rng(20261023).integers(0, len(repos), size=(20000, len(repos)))
    draws = np.array(sums)[indices].sum(axis=1) / np.array(counts)[indices].sum(axis=1)
    result['bootstrap'] = {'replicates': 20000, 'seed': 20261023, 'repo_order': repos,
                           'ratio_of_sums_class_weighted': True,
                           'percentile95CI': np.quantile(draws, [.025, .975]).tolist()}
    policies = {}
    for group in ['JUnit-applied', 'selector-applied', 'neither']:
        selected = [r for r in rows if r['policy_stratum'] == group]
        changes = [D(r['E2']) - D(r['E1_archived']) for r in selected]
        policies[group] = {'n': len(selected), 'job_indices': [r['job_index'] for r in selected],
                           'G0_all_unchanged': all(r['G0_unchanged'] for r in selected),
                           'E2_minus_E1': describe(changes) if changes else None,
                           'new_higher': sum(v > 0 for v in changes), 'old_higher': sum(v < 0 for v in changes),
                           'ties': sum(v == 0 for v in changes),
                           'changed_rows': [{'job_index': r['job_index'], 'class_key': r['class_key'],
                                             'E1_archived': r['E1_archived'], 'E2': r['E2'],
                                             'difference_pp': r['E2_minus_E1_pp']} for r in selected if D(r['E2_minus_E1_pp']) != 0]}
    result['policy_stratification'] = policies
    result['placeholder_diagnostic'] = {'classes': sum(r['no_behavior_placeholder'] for r in rows),
                                        'methods': sum(r['no_behavior_placeholder_count'] for r in rows),
                                        'job_indices': [r['job_index'] for r in rows if r['no_behavior_placeholder']],
                                        'changes_score_or_denominator': False,
                                        'strict_evidence_is_execution_not_behavior_quality': True}
    result['counts'] = {key: sum(bool(r[key]) for r in rows) for key in
                        ['gate', 'legacy_suite_pass', 'strict_suite_evidence', 'legacy_measurement_evidence',
                         'strict_measurement_evidence', 'JaCoCo_focal_present', 'PIT_report_present',
                         'generated_test_bytecode_baseline_available', 'generated_test_bytecode_unchanged_claim_available']}
    return result, indices, draws


def compare_official(folder, rows, stats, indices, values):
    if not folder.exists():
        return {'status': 'NOT_YET_PRESENT', 'path': str(folder)}
    official = read(folder / 'statistics.json')
    pairs = {'G0': 'G0', 'E0': 'E0', 'E2': 'E2_legacy_strict', 'E1_archived': 'E1_archived'}
    for key, target in pairs.items():
        for metric in ['mean', 'median']:
            assert abs(float(stats['arms'][key][metric]) - official[target + '_' + metric]) < 1e-12
    diff = stats['G0_minus_E2']
    target = official['G0_minus_E2']
    assert abs(float(diff['mean']) - target['mean_pp']) < 1e-12
    assert abs(float(diff['median']) - target['median_pp']) < 1e-12
    assert [diff['first_higher'], diff['second_higher'], diff['ties']] == [target['G_higher'], target['E_higher'], target['ties']]
    assert np.allclose(stats['bootstrap']['percentile95CI'], official['repository_cluster_percentile_95CI_G0_minus_E2_mean_pp'], atol=1e-12, rtol=0)
    assert stats['bootstrap']['repo_order'] == official['bootstrap']['repo_order']
    assert official['E2_complete_suite_evidence'] == stats['counts']['strict_suite_evidence']
    assert official['generated_test_bytecode_baseline_available_classes'] == stats['counts']['generated_test_bytecode_baseline_available']
    assert official['generated_test_bytecode_unchanged_claim_classes'] == stats['counts']['generated_test_bytecode_unchanged_claim_available']
    assert official['no_behavior_placeholder_classes'] == stats['placeholder_diagnostic']['classes']
    assert official['no_behavior_placeholder_methods'] == stats['placeholder_diagnostic']['methods']
    assert official['placeholder_changes_score_or_denominator'] is False
    fixed = csv_rows(folder / 'fixed49.csv')
    assert len(fixed) == 49
    for actual, expected in zip(fixed, rows):
        assert actual['class_key'] == expected['class_key'] and actual['repo_id'] == expected['repo_id']
        assert D(actual['E2_legacy_strict_mutation_percent']) == D(expected['E2'])
        assert D(actual['G0_archived_mutation_percent']) == D(expected['G0'])
    drawrows = csv_rows(folder / 'cluster_bootstrap_draws.csv')
    assert len(drawrows) == 20000
    for i, (row, draws, value) in enumerate(zip(drawrows, indices, values), 1):
        assert int(row['replicate']) == i
        assert row['repo_indices'] == ';'.join(map(str, draws))
        assert abs(float(row['mean_difference_pp']) - float(value)) < 1e-12
    return {'status': 'PASS', 'official_statistics': sha(folder / 'statistics.json'),
            'all20000_draws_match': True, 'fixed49_rows_match': True}


def self_test():
    fqcn = 'example.Selected_ESTest'
    assert normalize('test4 on test4(' + fqcn + ')', fqcn, ['test4']) == 'test4'
    assert normalize('test4 on test5(' + fqcn + ')', fqcn, ['test4']) is None
    assert normalize('test4 on test4(example.Foreign)', fqcn, ['test4']) is None
    source = '''class Sample {
      // @Test public void fake() {}
      String ignored = "@Test public void falsePositive() {}";
      @org.junit.Test(timeout=1000) public void notGeneratedAnyTest() { /* no behavior */ ; }
      @Test public void meaningfulName_$2() throws Throwable { assertTrue(true); }
    }'''
    annotation_inventory = inventory_java_tests(source)
    assert annotation_inventory['methods'] == ['meaningfulName_$2', 'notGeneratedAnyTest']
    assert annotation_inventory['no_behavior_placeholder_methods'] == ['notGeneratedAnyTest']
    assert normalize('notGeneratedAnyTest', fqcn, annotation_inventory['methods']) == 'notGeneratedAnyTest'
    assert normalize('meaningfulName_$2 on meaningfulName_$2(' + fqcn + ')', fqcn, annotation_inventory['methods']) == 'meaningfulName_$2'
    assert normalize('initializationError', fqcn, annotation_inventory['methods']) is None
    a = ['A.java', 'x.A', 'M', 'f', '1', 'KILLED', 't']
    assert fingerprint([a]) != fingerprint([a, a]), 'Duplicate identity lost'
    assert fingerprint([a, a]) == fingerprint([a, a][::-1])
    # Incomplete cohort refusal is verified without reading real experiment files.
    import tempfile
    with tempfile.TemporaryDirectory() as dirname:
        try:
            assert_complete(Path(dirname))
            raise RuntimeError('Partial cohort unexpectedly accepted')
        except AssertionError as error:
            assert 'Partial49 refused' in str(error)
    print(json.dumps({'status': 'PASS', 'partial49_refused': True,
                      'exact_TestNG_normalization': True, 'PIT_duplicates_preserved': True,
                      'annotated_nonprefix_methods': True, 'placeholder_is_diagnostic_only': True,
                      'real_experiment_files_read': False, 'Java_Maven_API_calls': 0}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage', type=Path, default=STAGE)
    parser.add_argument('--out', type=Path, default=OUT)
    parser.add_argument('--official', type=Path, default=BASE / 'outputs/e49_measurement_compat_v1')
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    assert args.stage.resolve().is_relative_to(BASE.resolve())
    assert args.out.resolve().is_relative_to((BASE / 'validation').resolve())
    jobs, gpt, results, old = assert_complete(args.stage)
    recovery = check_lock_recovery(args.stage)
    gpt_guard()
    rows = [inspect(args.stage, j, g, r, o) for j, g, r, o in zip(jobs, gpt, results, old)]
    stats, indices, draws = summaries(rows)
    comparison = compare_official(args.official, rows, stats, indices, draws)
    # All input checks precede creation: no outputs for partial/failed audit.
    args.out.mkdir(exist_ok=False)
    result = {'status': 'PASS', 'n': 49, 'repositories': 15, 'G0_all49_unchanged': True,
              'original_E1_guards': 'PASS', 'raw_artifact_manifests': 'PASS',
              'exactly_one_measurement_per_job': True, 'measurement_calls': 49,
              'generation_calls': 0, 'GPT_API_calls': 0,
              'independent_math_no_official_analyzer_import': True,
              'shared_pure_annotation_parser_only': 'junit_method_inventory_v1.py',
              'placeholder_diagnostic_changes_scores_or_membership': False,
              'PIT_identity_limit': 'Duplicate-preserving cols0-4 multiset; not full mutation ID',
              'recovery': recovery, 'official_comparison': comparison, 'statistics': stats}
    with (args.out / 'audit.json').open('x', encoding='utf-8') as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write('\n')
    with (args.out / 'raw_reconstructed49.json').open('x', encoding='utf-8') as handle:
        json.dump(rows, handle, ensure_ascii=False, indent=2)
        handle.write('\n')
    lines = ['# Kiểm tra raw độc lập cho measurement49', '',
             'Đủ 49 class / 15 repository. Mọi điểm G0 từng class được giữ nguyên; không sinh test hoặc gọi GPT. '
             'Mỗi class có đúng một lệnh đo clean → verify → JaCoCo → PIT. '
             'PIT, canonical XML, JaCoCo, gate và strict flags đều dựng lại từ raw; không nhập analyzer chính.', '',
             '| Nhóm policy | n | Điểm E mới cao hơn / thấp hơn / bằng E1 lưu trữ | Mean thay đổi (pp) |',
             '|---|---:|---:|---:|']
    for name, group in stats['policy_stratification'].items():
        lines.append(f"| {name} | {group['n']} | {group['new_higher']} / {group['old_higher']} / {group['ties']} | "
                     + (group['E2_minus_E1']['mean'] if group['E2_minus_E1'] else 'N/A') + ' |')
    lines += ['', 'Các dòng không vá cấu hình nhưng đổi điểm được liệt kê đầy đủ trong `audit.json` '
              '(`policy_stratification.neither.changed_rows`); không giả định 42 dòng không vá sẽ bất biến. '
              'G0 không tái đo. Chênh lệch E1→E mới là mô tả độ nhạy tích hợp/thực thi, không phải hiệu ứng nhân quả riêng assertions, '
              'không tạo RQ hoặc thang đo mới. Không lọc class theo thành công, không ghép điểm cũ và mới.', '',
              'Strict suite evidence chỉ xác nhận các phương thức @Test đóng băng được thực thi đúng một lần; '
              'không khẳng định chất lượng hành vi. Phương thức placeholder không có hành vi được đánh dấu riêng '
              'trong JSON, giữ nguyên điểm và mẫu phân tích.', '',
              'Raw mutant fingerprint giữ duplicate trong cột 0–4 của PIT CSV nhưng thiếu bytecode mutation index; '
              'không chứng nhận định danh hoàn chỉnh mọi mutant. Repository bootstrap là exploratory, không ước lượng biến thiên nhiều lần chạy.', '']
    with (args.out / 'BAO_CAO_AUDIT_RAW49.md').open('x', encoding='utf-8') as handle:
        handle.write('\n'.join(lines))
    with (args.out / 'output_manifest.json').open('x', encoding='utf-8') as handle:
        json.dump({'source': {Path(__file__).relative_to(BASE).as_posix(): sha(__file__)},
                   'inputs': {p.relative_to(BASE).as_posix(): sha(p) for p in
                              [args.stage / 'complete.json', args.stage / 'results49.json',
                               args.stage / 'readiness_lock.json', args.stage / 'inspection_amendment_v1.json',
                               args.stage / 'resume_guard02/admission.json', BASE / 'outputs/paired49.csv']},
                   'outputs': {p.name: sha(p) for p in args.out.iterdir() if p.is_file()}},
                  handle, ensure_ascii=False, indent=2)
        handle.write('\n')
    print(json.dumps({'status': 'PASS', 'n': 49, 'output': str(args.out),
                      'official_comparison': comparison['status'], 'generation_calls': 0, 'GPT_API_calls': 0}))


if __name__ == '__main__':
    main()
