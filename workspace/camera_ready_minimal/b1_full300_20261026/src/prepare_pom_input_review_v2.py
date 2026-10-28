"""Keep failed audit v1; distinguish raw bytes from its text-mode backup."""
import ast, sys
from maven_adapter_v1 import R,sha,dump
B=R.parent/'paired49_20261023'
sys.path.insert(0,str(B))
import audit
source=R/'src/audit_pom_input_deferrals_v1.py'
target=R/'src/audit_pom_input_deferrals_v2.py'
text=source.read_text(encoding='utf-8').replace('pom_input_deferrals_v1','pom_input_deferrals_v2')
old="assert sha(job/'repo'/frozen['pom_relative'])==sha(job/'pom_before_integration.xml')==frozen['pom_sha256']"
new="""assert sha(job/'repo'/frozen['pom_relative'])==frozen['pom_sha256']
            original_bytes=(job/'repo'/frozen['pom_relative']).read_bytes()
            backup_bytes=(job/'pom_before_integration.xml').read_bytes()
            assert original_bytes.replace(b'\\r\\n',b'\\n')==backup_bytes.replace(b'\\r\\n',b'\\n'), 'Text backup content differs beyond CRLF'
            backup_receipt={'original_raw_sha256':sha(job/'repo'/frozen['pom_relative']),
                            'text_backup_sha256':sha(job/'pom_before_integration.xml'),
                            'raw_byte_identity':original_bytes==backup_bytes,
                            'content_equal_after_CRLF_normalization':True,
                            'reason':'controller read_text/write_text normalized LF to CRLF in its backup; copied POM input itself remains byte-identical to snapshot'}"""
assert text.count(old)==1
text=text.replace(old,new)
text=text.replace("'Maven_input_POMs_inspected':len(inspected)","'backup_comparison':backup_receipt,'Maven_input_POMs_inspected':len(inspected)")
text=text.replace('POM trong job, backup trước integration và blob snapshot có cùng SHA256.',
                  'POM trong job khớp SHA256 blob snapshot. Backup do controller ghi ở text mode khác CRLF, nhưng nội dung XML giống sau chuẩn hóa newline; receipt ghi riêng cả hai hash, không khẳng định byte identity của backup.')
ast.parse(text)
with target.open('x',encoding='utf-8') as f:
    f.write(text)
audit.log('B1_FROZEN_POM_REVIEW_V2_PREPARED',source_sha256=sha(target),prior_failed_source_sha256=sha(source),
          correction='Separate preserved input hash from text-mode backup CRLF; no raw input edited',new_experiment_calls=0)
print('Prepared audit v2; failedv1 source/log retained; no raw input change')
