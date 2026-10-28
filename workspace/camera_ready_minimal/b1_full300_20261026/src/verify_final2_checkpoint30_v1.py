"""Audit terminal continuation receipts and export the thirty-class checkpoint."""
import csv
import importlib.util
import json
import msvcrt
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import shutil
import sys
from xml.etree import ElementTree as ET
import psutil
from maven_adapter_v1 import R, dump, sha
from parallel_pin_verify_v1 import verify_pins
from projection_io_v1 import publish_json
from check_resume_after173_status_v2 import inventory, processes

A = R / 'completion_amendment_v1'
P = A / 'resume_final2_v1'
O = A / 'checkpoint30_v1'
B = R.parent / 'paired49_20261023'
sys.path.insert(0, str(B))
import audit


def load(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))


def main():
    assert not O.exists(), 'New audit version required; preserve earlier evidence'
    O.mkdir(exist_ok=False)
    before = processes()
    dump(O / 'processes_before.json', before)
    assert not before['experiment_or_dispatch_processes'] and not before['inaccessible_pids']
    with (R / 'runtime/dispatcher.lock').open('r+b') as f:
        f.seek(0)
        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        f.seek(0)
        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
    admission = load(P / 'admission.json')
    pin_counts = {name: verify_pins(pins) for name, pins in [
        ('retained28_and_partial275', load(P / 'retained_evidence_pins.json')),
        ('code_and_inputs', admission['code_and_input_hashes']), ('tools', admission['tool_hashes'])]}
    assert sha(P / 'admission.json') == load(P / 'invocation/authorization.json')['admission_sha256']
    end = load(P / 'invocation/complete.json')
    assert end['returncode'] == 0 and end['follow_on_queues_started'] is False and end['automatic_retry'] is False
    for name in ['stdout', 'stderr']:
        assert sha(P / 'invocation' / ('runner_' + name + '.txt')) == end[name + '_sha256']
    group_end = load(A / 'maven_pom_resume_final2_v1/complete.json')
    assert group_end['status'] == 'GROUP_ONE_PASS_FINISHED' and group_end['indices'] == [275, 294]
    new_verified = []
    for i, name in [(275, 'MetadataWriter'), (294, 'ServerRpcHandler')]:
        job = R / 'jobs' / f'{i:03d}_completion_pom_resume_final2_v1'
        data = load(job / 'result.json')
        assert data['source_guard'] == data['production_bytecode_guard'] == 'PASS'
        assert data['seed'] == 20261023 + i and data['generation_calls'] == 1
        assert data['PIT_report_complete'] and data['PIT_report_shape_valid']
        assert data['strict_suite_evidence'] and data['strict_measurement_evidence']
        rows = inventory(job)
        actual = {x['relative']: x for x in rows}
        archive = load(job / 'artifact_manifest.json')
        for old in archive:
            found = actual[old['relative']]
            assert found['sha256'] == old['sha256'] and found['bytes'] == old['bytes']
        old_names = {x['relative'] for x in archive}
        extras = [x for x in actual if x not in old_names and x != 'artifact_manifest.json']
        assert {x for x in extras if 'temp' not in Path(x).parts} == {
            'derived_pom_evidence/after_generation_and_measurement.json',
            'derived_pom_evidence/after_generation_and_measurement.xml'}
        dump(O / f'{i:03d}_complete_archive.json', rows)
        suite = load(job / 'native_generated.json')
        for x in suite['files']:
            assert sha(x['path']) == x['sha256'], 'Generated Java/scaffolding changed'
        plans = [p for p in (job / 'commands').glob('*/plan.json') if (p.parent / 'started.json').exists()]
        assert len(plans) == 7 and sum('-jar' in load(p)['argv'] for p in plans) == 1
        assert all(load(p.parent / 'finished.json')['returncode'] == 0 for p in plans)
        report = job / 'repo/server/target/pit-reports/mutations.csv'
        with report.open(encoding='utf-8', newline='') as f:
            raw = list(csv.reader(f))
        assert raw and all(len(x) == 7 for x in raw)
        fqcn = 'com.vaadin.server.communication.' + name
        focal = [x for x in raw if x[1] == fqcn or x[1].startswith(fqcn + '$')]
        assert focal and all(x[0] == name + '.java' for x in focal)
        status = dict(Counter(x[5] for x in focal))
        killed = status.get('KILLED', 0)
        assert all(x[6] == fqcn + '_ESTest' for x in focal if x[5] == 'KILLED')
        assert len(focal) == data['focal_mutants'] and killed == data['killed_mutants']
        assert round(100 * killed / len(focal), 2) == data['mutation_score_percent']
        xml = job / 'repo/server/target/surefire-reports' / ('TEST-' + fqcn + '_ESTest.xml')
        tree = ET.parse(xml).getroot()
        assert int(tree.attrib['tests']) == (3 if i == 275 else 8)
        assert all(int(tree.attrib[k]) == 0 for k in ['failures', 'errors', 'skipped'])
        new_verified.append({'index': i, 'mutation_percent': data['mutation_score_percent'],
                             'killed_mutants': killed, 'focal_mutants': len(focal),
                             'focal_status_counts': status, 'raw_report_sha256': sha(report),
                             'native_xml_sha256': sha(xml), 'result_sha256': sha(job / 'result.json'),
                             'archive_entries_rehashed': len(archive),
                             'extra_or_temp_files_preserved': extras})
        print('NEW_RESULT_VERIFIED', i, flush=True)
    paths = {x['index']: Path(x['selected_result']) for x in load(A / 'pause_20261027_after173_v1/accepted25.json')}
    paths.update({i: R / 'jobs' / f'{i:03d}_completion_pom_resume_after173_v1/result.json' for i in [211, 220, 269]})
    paths.update({i: R / 'jobs' / f'{i:03d}_completion_pom_resume_final2_v1/result.json' for i in [275, 294]})
    manifest = {x['sample_index_1based']: x for x in load(R / 'manifest300.json')}
    assert len(paths) == 30
    rows = []
    for i, p in sorted(paths.items()):
        d = load(p)
        assert d['class_key'] == manifest[i]['class_key'] and d['seed'] == manifest[i]['seed']
        junit3 = i in [48, 49, 128, 138, 145, 148, 198, 202, 224, 239]
        partial = i in [112, 269]
        expected_calls = 0 if junit3 or i in [4, 40, 45, 129, 135, 156, 169, 170, 184, 197] else 1
        # 72 reuses its exact suite from the first completion generation attempt.
        if i == 72:
            expected_calls = 0
        assert d['generation_calls'] == expected_calls
        score = d.get('mutation_score_percent')
        if junit3:
            assert score is None
            measurement = 'UNRESOLVED_PIT_PROVIDER_TEST_ONLY'
        elif partial:
            assert score is None and not d['PIT_report_complete']
            measurement = 'PIT_PROCESS_TIMEOUT_PARTIAL_REPORT_REJECTED'
        else:
            assert score is not None and d['strict_measurement_evidence']
            measurement = 'VALID_OBSERVED_PIT_REPORT'
        suites = d.get('surefire_suites', [])
        rows.append({'index': i, 'class_key': d['class_key'], 'repo_id': d['repo_id'], 'seed': d['seed'],
                     'selected_result': str(p), 'result_sha256': sha(p),
                     'configuration': d['configuration'], 'generation_calls_in_selected_stage': d['generation_calls'],
                     'observed_mutation_percent': score, 'measurement_status': measurement,
                     'tests': sum(x['tests'] for x in suites), 'skipped': sum(x['skipped'] for x in suites),
                     'failures': sum(x['failures'] for x in suites), 'errors': sum(x['errors'] for x in suites),
                     'strict_suite_evidence': d['strict_suite_evidence'],
                     'historical_verify_plus_PIT_gate': None if junit3 else d['legacy_process_build'],
                     'legacy_raw_process_gate_retained': d['legacy_process_build'],
                     'conventional_E2E_zero_if_applicable': 0 if partial else None,
                     'must_not_rerun': True})
    assert len({x['class_key'] for x in rows}) == 30
    counts = dict(Counter(x['measurement_status'] for x in rows))
    assert sorted(counts.values()) == [2, 10, 18]
    dump(O / 'selected30.json', rows)
    with (O / 'selected30.csv').open('x', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    spec = importlib.util.spec_from_file_location('checkpoint30_gpt_guard', R.parents[1] / 'review_reports/minimal_camera_ready_20261023/guard_rq123_frozen.py')
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    assert guard.collect() == load(guard.LOCK)
    audit.verify()
    after = processes()
    assert not after['experiment_or_dispatch_processes'] and not after['inaccessible_pids']
    dump(O / 'processes_after.json', after)
    summary = {'at_utc': datetime.now(timezone.utc).isoformat(), 'status': 'CHECKPOINT30_STAGE_RECEIPTS_VERIFIED',
               'selected_class_count': 30, 'unique_class_keys': 30, 'new_results_verified': new_verified,
               'measurement_status_counts': counts, 'retained28_unchanged': True,
               'pin_counts_verified': pin_counts, 'GPT_RQ123_guard': 'PASS',
               'worker_count': 0, 'automatic_retry': False, 'follow_on_queues_started': False,
               'disk_free_bytes': shutil.disk_usage(R).free, 'GPT_API_calls': 0,
               'policy_seed_config_budget_changed': False, 'full300_complete': False,
               'notes': ['18 observed PIT scores; 10 JUnit3 test-only with unresolved PIT provider; 112/269 process timeout with partial reports rejected.',
                         '294 has a valid observed 0/44 under the unchanged KILLED/all denominator; 38 NO_COVERAGE and 6 TIMED_OUT mutant outcomes.',
                         'Stage-completion for30 does not resolve missing evidence elsewhere in the300 cohort.',
                         'No scientific reruns, new GPT calls, paper edits, full300 statistics or packaging queues were launched by this verification.']}
    dump(O / 'summary.json', summary)
    md = '''# Checkpoint bổ sung 30 class — 27/10/2026

Batch 275–294 kết thúc bình thường lúc 14:56 giờ Việt Nam/Thái Lan; return code 0. Không còn worker thực nghiệm hoặc queue nối tiếp. Đã kiểm tra raw reports, Java/scaffolding, command receipts, archive và hashes; 28 hồ sơ trước giữ nguyên. GPT/RQ1–RQ3, policy, seed, config và budget không thay đổi.

| Class mới | Test execution | PIT quan sát |
|---|---|---|
| 275 MetadataWriter | 3/3 pass | 1/20 KILLED = 5,00%; 10 NO_COVERAGE, 9 SURVIVED |
| 294 ServerRpcHandler | 8/8 pass | 0/44 KILLED = 0,00%; 38 NO_COVERAGE, 6 TIMED_OUT |

0,00% của 294 là kết quả từ báo cáo PIT hoàn chỉnh, process thành công và denominator đã khóa; phải giữ chú thích có 6 mutant TIMED_OUT. Điều này khác timeout của toàn phép đo tại112/269: hai ca đó không có mutation score quan sát hợp lệ, không được gọi là mutation 0% đo được hoặc compile fail chỉ vì PIT lỗi.

30 class đã có hồ sơ giai đoạn: **18 báo cáo PIT hợp lệ, 10 JUnit3 mới hoàn tất compile/test và còn unresolved PIT, 2 process timeout** (112/269). Không ép thành 30 mutation score. Class239 còn một test skipped, phải giữ flag strict-suite tương ứng. Điểm end-to-end quy ước0 cho112/269 được lưu riêng với nhãn rõ ràng; gate test-only của JUnit3 không thay cho gate verify+PIT.

Chưa gọi E1-full300 hoàn chỉnh. 16 gate-pass thiếu measurement evidence và 10 Gradle thiếu task trong270 hồ sơ trước vẫn cần đối chiếu khi ghép full300; chưa có thống kê full300, paper mới hoặc kết luận NI mới trong checkpoint này.

Các tệp: selected30.csv/json (30 class_key duy nhất, kết quả và seed/provenance), summary.json, archive đầy đủ cho275/294, process checks và SHA256SUMS.txt. Bằng chứng gốc không bị ghi đè; không có GPT/API hoặc repeated-run evaluation mới.
'''
    (O / 'CHECKPOINT30.md').write_text(md, encoding='utf-8')
    projection = {'phase': 'CHECKPOINT30_STAGE_RECEIPTS_VERIFIED', 'active_index': None,
                  'finished_indices': [275, 294], 'remaining_indices': [],
                  'completed30_subset_count': 30, 'observed_PIT_scores_in30': 18,
                  'unresolved_PIT_provider_in30': 10, 'rejected_partial_PIT_reports_in30': 2,
                  'updated_utc': summary['at_utc'], 'full300_complete': False, 'GPT_API_calls': 0,
                  'automatic_retry': False, 'follow_on_queues_enabled': False,
                  'verified_checkpoint': str(O / 'summary.json')}
    ui = publish_json(R / 'runtime/completion_progress.json', projection, label='verified_checkpoint30')
    assert ui['published']
    dump(O / 'UI_publication.json', ui)
    files = sorted(p for p in O.iterdir() if p.is_file())
    (O / 'SHA256SUMS.txt').write_text(''.join(sha(p) + '  ' + p.name + '\n' for p in files), encoding='utf-8')
    audit.log('CHECKPOINT30_STAGE_RECEIPTS_VERIFIED', path=str(O), summary_sha256=sha(O / 'summary.json'),
              selected_classes=30, observed_PIT_scores=18, unresolved_PIT_provider=10,
              partial_timeout_reports_rejected=2, new_experiment_launches=0, GPT_API_calls=0)
    print(json.dumps({'status': summary['status'], 'path': str(O), 'counts': counts}, indent=2))


if __name__ == '__main__':
    main()
