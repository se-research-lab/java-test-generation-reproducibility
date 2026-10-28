"""Review fixes before any controller execution; retain candidate v1 as backup."""
import ast,difflib,sys
from maven_adapter_v1 import R,sha,dump
B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
old=R/'src/gradle_execution_candidate_v1.py';new=R/'src/gradle_execution_v2.py';text=old.read_text(encoding='utf-8')
text=text.replace("ensure(not list(commands.repo.rglob('*.exec')),'Stale coverage execution input')", "ensure(not (module/'build').exists(),'Selected module must begin without build outputs')\n ensure(not native_suite(module,job['selected_test_fqcn'])['files'],'No existing native suite before a new generation')")
text=text.replace("'configuration':'E1_Gradle_native_v1_CANDIDATE_REQUIRES_ADMISSION',", "'configuration':'E1_Gradle_native_v1','execution_scope':commands.lock['execution_scope'],'actual_focal_fqcn':job['selected_test_fqcn'].removesuffix('_ESTest'),")
text=text.replace("ensure(self.lock.get('Gradle_benchmark_admitted') is True and self.out.is_relative_to(R/'jobs'),'Benchmark lacks admission')", "ensure(self.lock.get('Gradle_benchmark_admitted') is True and self.out.is_relative_to(R/'jobs') and not job.get('synthetic_fixture'),'Benchmark lacks admission or uses a synthetic job')")
text=text.replace("argv[1:] if stage=='generation' else argv[8:] if init else argv[5:]", "argv[1:] if stage=='generation' else argv[7:] if init else argv[5:]")
ast.parse(text)
with new.open('x',encoding='utf-8') as f:f.write(text)
out=R/'audit/gradle_controller_review_v2';out.mkdir(exist_ok=False)
diff=out/'controller.diff';diff.write_text(''.join(difflib.unified_diff(old.read_text(encoding='utf-8').splitlines(True),text.splitlines(True),fromfile=old.name,tofile=new.name)),encoding='utf-8')
dump(out/'review.json',{'scope':'pre-execution controller review','old_sha256':sha(old),'new_sha256':sha(new),'diff_sha256':sha(diff),'changes':['reject existing native suite before generation','check only selected build output for stale evidence; do not reject legitimate .exec resource fixtures','scope and actual FQCN explicit in result; synthetic job barred in benchmark','remove redundant incorrect intermediate argv tail slice'],'legacy_gate_verified_at':'scripts_v2/AgoneTest/gradleLib.py run_gradle_test_command: successful test+JaCoCo plus non-timeout PIT retains gate even when PIT exits nonzero','new_EvoSuite_calls':0,'benchmark_admitted':False})
audit.log('B1_GRADLE_CONTROLLER_PREEXECUTION_REVIEW_V2',receipt_sha256=sha(out/'review.json'),execution_admitted=False)
print('PASS pre-execution review; v1 preserved; v2 not admitted')
