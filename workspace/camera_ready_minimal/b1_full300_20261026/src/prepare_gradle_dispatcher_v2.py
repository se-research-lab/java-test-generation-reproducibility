"""Add end-of-pass original-cache verification before sealing any batch."""
import ast,difflib,sys
from maven_adapter_v1 import R,sha,dump
B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
old=R/'src/run_gradle_full40_v1.py';new=R/'src/run_gradle_full40_v2.py';text=old.read_text(encoding='utf-8')
needle="   receipt={'status':'ONE_PASS_COMPLETED'"
replacement="""   source_cache=Path('C:/Users/admin/.gradle')
   original_cache_rows=load(R/'cache_preparation_gradle_v1/recovery_v2/manifest.json')
   verify_pins({str((source_cache/r['relative']).resolve()):r['sha256'] for r in original_cache_rows})
   receipt={'all_original_cache_files_unchanged':True,'status':'ONE_PASS_COMPLETED'"""
assert text.count(needle)==1;text=text.replace(needle,replacement);ast.parse(text)
with new.open('x',encoding='utf-8') as f:f.write(text)
out=R/'audit/gradle_dispatcher_review_v2';out.mkdir(exist_ok=False)
diff=out/'dispatcher.diff';diff.write_text(''.join(difflib.unified_diff(old.read_text(encoding='utf-8').splitlines(True),text.splitlines(True),fromfile=old.name,tofile=new.name)),encoding='utf-8')
dump(out/'review.json',{'scope':'pre-admission dispatcher review','old_sha256':sha(old),'new_sha256':sha(new),'diff_sha256':sha(diff),'change':'Full original cache verification before reporting pass completion','generation_measurement_policy_unchanged':True,'corpus_jobs_started':0})
audit.log('B1_GRADLE_DISPATCHER_V2_PREPARED',receipt_sha256=sha(out/'review.json'),new_experiment_calls=0)
print('PASS dispatcher review; no batch admission/execution')
