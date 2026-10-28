"""Report completed compatibility diagnostics without changing the benchmark/manuscript."""
import json,sys
from datetime import datetime,timezone
from pathlib import Path
from xml.etree import ElementTree as ET
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));import audit
STAGE=BASE/'e1_compatibility_diagnostic_v1'
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def dump(p,x):
    with p.open('x',encoding='utf-8') as f:json.dump(x,f,ensure_ascii=False,indent=2);f.write('\n')
def xml_errors(p):
    rows=[]
    for xml in p.rglob('TEST-*.xml'):
        root=ET.parse(xml).getroot()
        for case in root.findall('testcase'):
            for tag in ['error','failure']:
                for err in case.findall(tag):rows.append({'suite':root.get('name'),'test':case.get('name'),'kind':tag,'type':err.get('type'),'message':(err.get('message') or '')[:250]})
    return rows

def main():
    complete=load(STAGE/'diagnostic_queue_v1/complete.json');assert complete['status']=='COMPLETE'
    records=[]
    for job in ['09','12','13','14','15']:
        out=STAGE/'jobs'/job;r=load(out/'diagnostic_result.json');a=load(out/'strict_acceptance.json')
        assert a['post_POM_hash']=='PASS' and a['source_and_production_bytecode_unchanged']
        records.append({'job':job,'group':'JUnit TestRule','diagnostic_suite_pass':a['XML_suite_and_case_checks_pass'],'expected_methods':len(r['expected_test_methods']),'XML_suites':r['XML_suites'],'errors':xml_errors(out/'repo'),'report_sha256':audit.sha(out/'diagnostic_result.json'),'production_class_count':r['production_class_count']})
    for job in ['18','19']:
        out=STAGE/'jobs'/job;r=load(out/'hazel_direct_result.json')
        records.append({'job':job,'group':'Hazelcast discovery','diagnostic_suite_pass':r['selected_suite_all_methods_pass'],'expected_methods':len(r['expected_test_methods']),'XML_suites':r['XML_suites'],'errors':xml_errors(out/'repo'),'report_sha256':audit.sha(out/'hazel_direct_result.json'),'production_class_count':r['production_class_count']})
    out=STAGE/'jobs/48';r=load(out/'runtime_full_result.json')
    records.append({'job':'48','group':'Runtime sandbox/resource','diagnostic_suite_pass':r['selected_suite_all_methods_pass'],'expected_methods':len(r['expected_test_methods']),'XML_suites':r['XML_suites'],'errors':xml_errors(out/'attempt_01/surefire_archive'),'report_sha256':audit.sha(out/'runtime_full_result.json'),'production_class_count':r['production_class_count']})
    methods=[load(out/('runtime_'+m+'_result.json')) for m in ['test0','test1','test2']]
    guards=[]
    for p in sorted((STAGE/'original_guards').glob('*/result.json')):
        g=load(p);assert g['source_E1_job_file_bytes_and_membership_unchanged'];guards.append({'path':str(p.relative_to(BASE)),'sha256':audit.sha(p),'job':g['job'],'files':g['before_files']})
    registry=load(BASE/'audit/final49_static_registry_v1.json')
    for row in registry['files']:assert audit.sha(BASE/row['path'])==row['sha256'],row['path']
    commands=[]
    for p in sorted((STAGE/'jobs').glob('*/command_*.json')):
        row=load(p);assert '-jar' not in row['argv'];assert Path(row['argv'][0]).name=='mvn.cmd';assert '-o' in row['argv']
        assert audit.sha(BASE/row['stdout'])==row['stdout_sha256'] and audit.sha(BASE/row['stderr'])==row['stderr_sha256']
        commands.append({'path':str(p.relative_to(BASE)),'sha256':audit.sha(p),'returncode':row['returncode']})
    stats=load(BASE/'outputs/e49_final_v2/statistics.json')
    report={'status':'DIAGNOSTIC_PHASE_COMPLETE','created_utc':datetime.now(timezone.utc).isoformat(),'jobs':records,'runtime48_methods':methods,'original_guards':guards,'commands':commands,'Maven_commands':len(commands),'GPT_API_calls':0,'generation_calls':0,'PIT_measurement_calls':0,'E1_or_GPT_scores_replaced':False,'frozen49_artifacts_unchanged':True,'E1_mean_unchanged':stats['E1_legacy_strict_mean'],'not_new_fairness_baseline':True,'repeated_subset_status':'PLANNED_NOT_EXECUTED'}
    dump(STAGE/'diagnostic_summary.json',report)
    lines=['# Chẩn đoán tám ca EvoSuite E1: kết quả và bước sửa tối thiểu','',
    'Báo cáo nội bộ sau replay trên bản sao riêng. Không sửa E1 đã đóng, không sinh test mới, không gọi GPT, không tính lại PIT và không ghép các ca chạy tốt hơn vào bảng49.','',
    '| Job | Nhóm | Số method khóa | Suite replay theo XML | Production class files giữ nguyên |',
    '|---|---|---:|---|---:|']
    for row in records:lines.append('| '+row['job']+' | '+row['group']+' | '+str(row['expected_methods'])+' | '+('PASS' if row['diagnostic_suite_pass'] else 'Còn lỗi/thiếu evidence')+' | '+str(row['production_class_count'])+' |')
    lines += ['', '## JUnit09,12–15', '',
    'Chỉ module-level dependency test junit:junit được đặt4.13.2 trong bản sao mới; parent POM và production dependencies không đổi. Compile-scope classpath/JAR hashes trước–sau khớp; test classpath chỉ được phép thay JUnit/Hamcrest. Generated Java/scaffold giữ nguyên byte, toàn bộ production .class được so SHA. Không đổi Surefire2.17, PIT1.16.0, JaCoCo0.8.7 hay oracle.', '',
    'Nếu các suite PASS, evidence ủng hộ TestRule API compatibility là lỗi thực thi của các case này. Không suy ra mọi project chỉ cần nâng JUnit, không sửa dependency GPT hoặc shared harness.', '',
    '## Hazelcast18–19', '',
    'Thu effective POM/active profiles trên bản sao chưa chỉnh, compile test rồi gọi riêng Surefire execution regular-tests với đúng FQCN, skipTests=false và maven.test.skip=false. Không chạy serial execution trước, không sửa POM/version. Dependency đã có JUnit4.13.1. Kết quả direct discovery nếu PASS chứng minh suite có thể được phát hiện trong execution đó; chưa tự cô lập nguyên nhân duy nhất giữa skip/category/execution kế thừa. Debug log được giữ để đối chiếu.', '',
    'Job19 PIT77,78% trong E1 gốc vẫn giữ nguyên dù Surefire XML lúc đó thiếu. Replay này không tính PIT nên không phát sinh mutation score mới.', '',
    '## Job48: fullsuite và từng method', '',
    'Giữ nguyên sandbox/resource limits, Log4j, source/scaffold và runtime. Trước mỗi replay lưu/move report cũ trong workspace mới, tránh đọc XML tồn dư. Mỗi method được chạy bằng một Maven invocation mới, đúng selected method; không cộng các method pass riêng thành suite pass.', '',
    '| Method trong JVM riêng | Testcase entries | Errors | Failures | XML method pass |',
    '|---|---:|---:|---:|---|']
    for row in methods:lines.append('| '+row['method']+' | '+str(len(row['testcases']))+' | '+str(sum(c['errors'] for c in row['testcases']))+' | '+str(sum(c['failures'] for c in row['testcases']))+' | '+str(row['selected_method_XML_pass'])+' |')
    lines += ['', 'Phân tích tĩnh đặt giả thuyết lỗi trong ClassResetter/Log4j cleanup có thể làm trạng thái sandbox còn lại giữa các method. Một XML pass không tự chứng nhận cleanup hoàn tất, vì runtime rule có xử lý riêng TooManyResourcesException. Chỉ đối chiếu replay/trace mới cho phép thu hẹp giả thuyết; chưa được gọi lỗi vòng lặp của focal class hoặc oracle sai.', '',
    '## Guard và audit', '',
    'Scaffold giữ các absolute properties user.dir/tmpdir đã ghi khi sinh test; không sửa chuỗi này để làm replay pass. VFS/VNET vẫn bật. Guard so cả byte và tập đường dẫn file của source E1 job trước/sau từng invocation, cùng211 static artifact hashes của bản49 đã niêm phong. Các guard đều PASS; không có thay đổi source E1 được ghi nhận.', '',
    'Tổng'+str(len(commands))+' Maven commands offline, stdout/stderr có SHA. Cache Maven dùng bản sao riêng gồm116.010 file; manifest giữ SHA từng file. Mọi POM patch có backup/diff; các source/helper phiên bản chuẩn bị được giữ, không ghi đè.', '',
    '## Ảnh hưởng paper và bước tiếp theo', '',
    '- G0 RQ1/2/3 vẫn61/45/300; E1 fixed49 mean vẫn50,41%, G0−E1mean8,03pp vàCI[−4,80;26,99]. Không tính điểm mới từ chẩn đoán này.',
    '- Không kết hợp41 case E1 cũ với case compatibility mới để gọi48/49 hoặc49/49 baseline pass. Cần measurement profile chung cho đủ49 nếu muốn bảng sensitivity được sửa runtime.',
    '- Bước hợp lý tiếp là khóa policy E-only: conditional test JUnit API compatibility, single selected Surefire execution có căn cứ; giữ mọi failure, source/test/scaffold và metric. Validate policy rồi đo lại đủ49 suite đã khóa, không generation mới. Nếu đổi classpath trước generation và muốn baseline generation mới, phải protocol riêng cho cả49.',
    '- Không tắt sandbox/nâng loop limit/xóa method để chữa48. Nếu chưa có fix tối thiểu có bằng chứng, giữ failure và giới hạn claim.',
    '- Repeated subset mới ở thiết kế:15class×5run×2arm; chưa gọi75GPTrequests. Không đánh dấu R1.7/R2.5 hoàn tất.',
    '- Practical5pp, pre-pilot analytical-lock evidence, metadata/artifact URL và page allowance vẫn mở như báo cáo trước.', '',
    '## File kiểm chứng', '',
    '- [Diagnostic summary](e1_compatibility_diagnostic_v1/diagnostic_summary.json)',
    '- [Protocol đã khóa](e1_compatibility_diagnostic_v1/protocol.json)',
    '- [Input lock](e1_compatibility_diagnostic_v1/input_lock.json)',
    '- [Queue completion](e1_compatibility_diagnostic_v1/diagnostic_queue_v1/complete.json)',
    '- [Original job guards](e1_compatibility_diagnostic_v1/original_guards)',
    '- [Repeated subset đề xuất](PROTOCOL_REPEATED_SUBSET_DE_XUAT.md)',
    '- [Báo cáo49 trước đó](BAO_CAO_CHOT_49_VA_KE_HOACH_CAMERA_READY.md)', '',
    'Manuscript không kể các diagnostic trials. Chỉ đưa cấu hình/kết quả được nghiệm thu cuối cùng và các giới hạn cần thiết vào paper.']
    dest=BASE/'BAO_CAO_CHAN_DOAN_COMPATIBILITY_E1.md'
    with dest.open('x',encoding='utf-8') as f:f.write('\n'.join(lines)+'\n')
    audit.log('E1_COMPATIBILITY_DIAGNOSTIC_REPORT_COMPLETE',report_sha256=audit.sha(dest),summary_sha256=audit.sha(STAGE/'diagnostic_summary.json'),jobs=8,GPT_API_calls=0,generation_calls=0,PIT_calls=0,E1_scores_replaced=False)
    print(json.dumps({'status':report['status'],'diagnostic_suite_pass_count':sum(r['diagnostic_suite_pass'] for r in records),'diagnostic_jobs':8,'Maven_commands':len(commands),'original_guard_invocations':len(guards),'E1_scores_replaced':False},indent=2))
if __name__=='__main__':main()
