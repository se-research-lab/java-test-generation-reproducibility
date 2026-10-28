"""Read frozen POM bytes; quarantine invalid input without repair or a score.
No Maven/Java/EvoSuite, new source materialization or API call is allowed here.
"""
import hashlib, json, msvcrt, sqlite3, sys
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET
from maven_adapter_v1 import R, sha, dump
from run_maven_b1_v2 import guards
from run_maven_b1_v3 import selected_result
from completed_archive_guard_v3 import verify
from maven_controller_v2 import source_hashes

B=R.parent/'paired49_20261023'
sys.path.insert(0,str(B))
import audit
OUT=R/'audit/pom_input_deferrals_v2'

def load(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))

def signature(text):
    try:
        root=ET.fromstring(text)
    except ET.ParseError as ex:
        return {'parseable':False,'error':str(ex),'code':ex.code,'position':list(ex.position)}
    return {'parseable':True,'root_namespace':root.tag.split('}')[0].removeprefix('{') if '}' in root.tag else None}

def main():
    assert not OUT.exists(), 'Keep existing input review'
    with (R/'runtime/dispatcher.lock').open('r+b') as mutex:
        mutex.seek(0)
        msvcrt.locking(mutex.fileno(),msvcrt.LK_NBLCK,1)
        try:
            guards(load(R/'admission_maven_v5.json'))
            completion=load(R/'runtime/remaining_maven167_v5_completion.json')
            assert completion['exit_code']==1 and completion['error']['detail']=='E49 POM preparation failed'
            assert completion['new_policy_accepted']==46
            OUT.mkdir(parents=True,exist_ok=False)
            jobs=load(R/'manifest300.json')
            snapshot=R/'inputs/snapshot_v3'
            index=load(snapshot/'index.json')
            assert sha(snapshot/'index.json')==load(snapshot/'complete.json')['index_sha256']
            candidates=[j for j in jobs if j['build_tool']=='maven' and not j['reused_result']
                        and (j['sample_index_1based']==72 or not (R/'jobs'/f"{j['sample_index_1based']:03d}").exists())]
            assert len(candidates)==163
            inspected=[]
            with sqlite3.connect((snapshot/'content.sqlite3').as_uri()+'?mode=ro',uri=True) as conn:
                for j in candidates:
                    i=j['sample_index_1based']
                    mapping=next(m for m in index if i in m['class_indices'])
                    manifest=R/mapping['manifest']
                    assert sha(manifest)==mapping['sha256']
                    data=load(manifest)
                    relative=(Path(j['module'])/'pom.xml').as_posix()
                    row=next(r for r in data['files'] if r['relative']==relative)
                    nbytes,blob=conn.execute('SELECT nbytes,data FROM blobs WHERE sha256=?',(row['sha256'],)).fetchone()
                    assert nbytes==row['bytes']==len(blob) and hashlib.sha256(blob).hexdigest()==row['sha256']
                    proof=signature(blob)
                    inspected.append({'sample_index_1based':i,'class_key':j['class_key'],'module':j['module'],
                         'snapshot_manifest':mapping['manifest'],'snapshot_manifest_sha256':sha(manifest),
                         'pom_relative':relative,'pom_sha256':row['sha256'],'pom_bytes':len(blob),
                         'generation_already_attempted':False,**proof})
            invalid=[r for r in inspected if not r['parseable']]
            assert next(r for r in invalid if r['sample_index_1based']==72)['error']=='unbound prefix: line 2, column 0'
            # Only establish the audited, already observed failure signature.
            # Another malformed input remains a blocker, not an automatic skip.
            assert all(r['error']=='unbound prefix: line 2, column 0' and r['code']==27 for r in invalid)
            job=R/'jobs/072'
            check72=verify(job)
            interruption=load(job/'interrupted.json')
            assert interruption['detail']=='E49 POM preparation failed' and interruption['score_accepted'] is False
            assert not list((job/'commands').iterdir())
            assert not (job/'result.json').exists() and not (job/'native_generated.json').exists()
            expected=load(job/'controller_source_before.json')
            assert source_hashes(job/'repo')==expected, 'Source mutated before POM parse failure'
            frozen=next(r for r in invalid if r['sample_index_1based']==72)
            assert sha(job/'repo'/frozen['pom_relative'])==frozen['pom_sha256']
            original_bytes=(job/'repo'/frozen['pom_relative']).read_bytes()
            backup_bytes=(job/'pom_before_integration.xml').read_bytes()
            assert original_bytes.replace(b'\r\n',b'\n')==backup_bytes.replace(b'\r\n',b'\n'), 'Text backup content differs beyond CRLF'
            backup_receipt={'original_raw_sha256':sha(job/'repo'/frozen['pom_relative']),
                            'text_backup_sha256':sha(job/'pom_before_integration.xml'),
                            'raw_byte_identity':original_bytes==backup_bytes,
                            'content_equal_after_CRLF_normalization':True,
                            'reason':'controller read_text/write_text normalized LF to CRLF in its backup; copied POM input itself remains byte-identical to snapshot'}
            assert not list((job/'repo').rglob('target'))
            new_checks={}
            for i in [67,68,69,71]:
                folder=R/'jobs'/f'{i:03d}'
                result=load(folder/'result.json')
                new_checks[str(i)]={'archive':verify(folder),'result_sha256':sha(folder/'result.json'),
                                   'legacy_process_gate':result['legacy_process_build'],
                                   'strict_percent':result['legacy_strict_mutation_percent']}
            deferrals=[]
            for row in invalid:
                deferrals.append({**row,'status':'FROZEN_INPUT_XML_UNPARSEABLE_UNSCORED','score':None,
                     'new_generation_calls':0,'new_measurement_calls':0,'GPT_API_calls':0,
                     'retained_in_fixed300_manifest':True,'zero_fill_allowed':False,'input_repair_allowed':False,
                     'original_job_archive_sha256':sha(job/'artifact_manifest.json') if row['sample_index_1based']==72 else None})
            report={'status':'PASS_READONLY_FROZEN_POM_REVIEW','at_utc':datetime.now(timezone.utc).isoformat(),
                    'backup_comparison':backup_receipt,'Maven_input_POMs_inspected':len(inspected),'parseable_POMs':len(inspected)-len(invalid),
                    'unparseable_indices':[r['sample_index_1based'] for r in invalid],
                    'deferrals':deferrals,'job072_archive_check':check72,'new_terminal_archive_checks':new_checks,
                    'v5_completion_sha256':sha(R/'runtime/remaining_maven167_v5_completion.json'),
                    'new_generation_calls':0,'new_measurement_calls':0,'new_Java_processes':0,'GPT_API_calls':0,
                    'raw_source_modified':False,'paper_modified':False,'full300_complete':False}
            dump(OUT/'result.json',report)
            dump(OUT/'inspected_poms.json',inspected)
            table='\n'.join(f"|{r['sample_index_1based']}|{r['module']}|{r['error']}|chưa chấm|" for r in invalid)
            text=f'''# B1 — POM đầu vào không parse được

Kiểm tra UTC:{report['at_utc']}. Class072 dừng trước Java/generation/measurement do `unbound prefix: line 2, column 0`. POM trong job khớp SHA256 blob snapshot. Backup do controller ghi ở text mode khác CRLF, nhưng nội dung XML giống sau chuẩn hóa newline; receipt ghi riêng cả hai hash, không khẳng định byte identity của backup. Source hashes khớp trước/sau; không có target, native suite hoặc command được chạy. Lỗi có sẵn trong prepared-input snapshot, không phải do bật assertions ở lần chạy mới.

Đã đọc POM focal module của{len(inspected)} Maven chưa có kết quả, từ SQLite chỉ đọc và manifest đã khóa; phát hiện{len(invalid)} POM lỗi cùng signature. Không restore hay sửa repo để làm census này. Đây không chứng minh pristine upstream commit có lỗi; snapshot lấy từ các workspace đã chuẩn bị của protocol hiện có. Chưa xác định thao tác lịch sử nào tạo prefix bị thiếu khai báo.

|Index cố định|Module|Lỗi XML trong frozen input|Quyết định|
|---|---|---|---|
{table}

Giữ những class này trong manifest300 nhưng chưa chấm. Chưa chạy generation/measurement, vì vậy không có strict-policy0 hoặc observed score để điền vào. Không sửa namespace, dependency, provider, business source hoặc lấy dữ liệu E0/G0 thay thế. Đầu vào và artifact evidence được giữ nguyên; trước khi xử lý phải có amendment compatibility riêng, kiểm semantic POM/source/compile closure và sandbox mới.

Đối với các class chưa restore, receipt dựa trên frozen blob/manifest đã kiểm, không giả làm một job đã thực thi.072 có archive xác minh riêng của lần dừng. Các deferral này chỉ là quyết định scheduling cho môi trường chưa hỗ trợ, không phải sửa thang đo, đổi mẫu hoặc giải quyết R2.1. Không giảm denominator, không gọi E1-full300 hoàn tất khi còn class chưa chấm.

Bốn terminal mới067/068/069/071 đã được kiểm archive. V5 kết thúc có receipt thật exit1; không tự restart. Queue Gradle phụ thuộc bounded10 đã SKIPPED; không chạy JVM Gradle từ queue. GPT/API0, dữ liệu RQ1–RQ3/E0/E49/paper giữ nguyên.
'''
            with (OUT/'REPORT.md').open('x',encoding='utf-8') as f:
                f.write(text)
            dump(OUT/'manifest.json',{'files':[{'path':p.relative_to(R).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size}
                                            for p in sorted(OUT.iterdir()) if p.is_file()]})
            audit.log('B1_FROZEN_POM_INPUT_REVIEW_FINISHED',result_sha256=sha(OUT/'result.json'),
                      inspected=len(inspected),unparseable_indices=report['unparseable_indices'],
                      new_generation_calls=0,new_measurement_calls=0,GPT_API_calls=0)
            print(json.dumps({k:report[k] for k in ['status','Maven_input_POMs_inspected','parseable_POMs','unparseable_indices','GPT_API_calls']},indent=2))
        finally:
            mutex.seek(0)
            msvcrt.locking(mutex.fileno(),msvcrt.LK_UNLCK,1)

if __name__=='__main__':
    main()
