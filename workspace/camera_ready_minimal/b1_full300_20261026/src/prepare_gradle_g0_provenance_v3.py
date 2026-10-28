"""Extend archived provenance to the observed pre-measurement copy failure."""
import sys
from maven_adapter_v1 import R,sha,dump
B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
source=R/'src/audit_gradle_g0_zero_provenance_v2.py';target=R/'src/audit_gradle_g0_zero_provenance_v3.py'
text=source.read_text(encoding='utf-8').replace('gradle_g0_zero_provenance_v2','gradle_g0_zero_provenance_v3')
text=text.replace("E0_scaffolding_move_failed='while trying to move the scaffolding file' in text,", "E0_scaffolding_move_failed='while trying to move the scaffolding file' in text,E0_copy_test_unbound_variable=\"while trying to copy the evosuite class test: local variable 'project_df_evosuite' referenced before assignment\" in text,")
text=text.replace("'while trying to move the scaffolding file','Test classes:'", "'while trying to move the scaffolding file','while trying to copy the evosuite class test:','Test classes:'")
text=text.replace("and logproof.get('E0_scaffolding_move_failed')", "and logproof.get('package_command_completed') and (logproof.get('E0_scaffolding_move_failed') or logproof.get('E0_copy_test_unbound_variable'))")
text=text.replace('EvoSuite cũ lỗi scaffold trước measurement;', 'EvoSuite cũ lỗi chuyển scaffold hoặc chép test do biến chưa gán trước measurement;')
compile(text,str(target),'exec')
with target.open('x',encoding='utf-8') as f:f.write(text)
dump(R/'audit/gradle_g0_provenance_v3_review.json',{'prior_source_sha256':sha(source),'new_source_sha256':sha(target),'new_evidence':'Three archived class logs explicitly show project_df_evosuite referenced before assignment during test copying, before GPT phase and before the sole Gradle measurement','rule':'Require selected passing GPT suite, focal JaCoCo, matching PIT report, sole measurement after GPT start, completed package command and a logged E0 pre-measurement preparation failure. No quality-score selection.','G0_values_changed':False,'new_measurements':0})
audit.log('B1_GRADLE_G0_PROVENANCE_V3_PREPARED',source_sha256=sha(target),prior_source_sha256=sha(source),new_measurements=0,GPT_API_calls=0);print('Prepared provenance v3; old classifications and all measurements preserved')
