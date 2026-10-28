"""One bounded invocation of the admitted dispatcher; never schedules/resumes.
Publishes an explicit final state even if a pre-job guard stops the dispatcher.
"""
import json,runpy,sys,traceback,shutil
from datetime import datetime,timezone
from pathlib import Path
from maven_adapter_v1 import R,sha,dump
from run_maven_b1_v3 import guards,counters
from projection_io_v1 import publish_json
B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def now():return datetime.now(timezone.utc).isoformat()

def main():
 plan_path=R/'launch_remaining_maven198_v1.json';completion=R/'runtime/remaining_maven198_v1_completion.json'
 assert not plan_path.exists() and not completion.exists(),'No implicit restart of an existing invocation'
 lock=load(R/'admission_maven_v3.json');guards(lock)
 checkpoint=load(R/'audit/progress_v7.json')
 assert checkpoint['terminal_new_classes']==13 and checkpoint['new_classes_accepted_under_v3']==13 and not checkpoint['pending_transport_recovery']
 for i in [12,16,23]:assert not (R/'jobs'/f'{i:03d}_cpfile_v3/interrupted.json').exists()
 dispatcher=R/'src/run_maven_b1_v3.py'
 plan={'started_utc':now(),'scope':'one bounded Maven continuation only; no scheduling or automatic resume','max_new_jobs':198,'workers':1,'admission_sha256':sha(R/'admission_maven_v3.json'),'dispatcher_sha256':sha(dispatcher),'launcher_sha256':sha(__file__),'checkpoint_sha256':sha(R/'audit/progress_v7.json'),'result_map_sha256':sha(R/'measurement_result_map_v3.json'),'Python_executable_sha256':sha(sys.executable),'GPT_generation_authorized':False,'Gradle_benchmark_authorized':False,'paper_edits_authorized_by_this_launcher':False,'minimum_free_bytes_at_job_boundaries':lock['minimum_free_bytes'],'argv':[str(dispatcher),'--max-jobs','198']}
 dump(plan_path,plan);audit.log('B1_REMAINING_MAVEN198_DISPATCH_ENTERED',launch_plan_sha256=sha(plan_path),max_jobs=198,GPT_API_calls=0)
 initial=load(R/'status.json');initial.update(phase='MAVEN198_DISPATCH_ACTIVE_PREPARING_NEXT_JOB',updated_utc=now(),running=0,benchmark_admitted=True)
 initial['blockers']=['Một invocation tối đa198 Maven còn lại, tuần tự theo original order; không tự resume sau lỗi','Gradle40 chưa admit; chỉ có launcher qualification','GPT, repeated subset và paper hiện tại giữ khóa']
 start_receipt=publish_json(R/'status.json',initial,label='maven198_start_state')
 audit.log('B1_REMAINING_MAVEN198_START_UI',publication=start_receipt)
 original_args=list(sys.argv);error=None;code=0
 try:
  sys.argv=list(plan['argv']);runpy.run_path(str(dispatcher),run_name='__main__')
 except BaseException as ex:
  code=1;error={'type':type(ex).__name__,'detail':str(ex),'traceback':traceback.format_exc()}
  audit.log('B1_REMAINING_MAVEN198_STOPPED_NO_AUTO_RESUME',error_type=type(ex).__name__,detail=str(ex))
  traceback.print_exc()
 finally:
  sys.argv=original_args;planned,started,fixtures=counters();s=load(R/'status.json')
  finished_all=s.get('new_policy_accepted')==211 and code==0
  s.update(updated_utc=now(),phase='MAVEN260_TERMINAL_GRADLE40_PENDING' if finished_all else ('STOPPED_NO_AUTOMATIC_RESUME' if code else 'BOUNDED_INVOCATION_COMPLETE_NO_AUTOMATIC_RESUME'),running=0,active_sample_index=None,benchmark_admitted=False,new_API_calls=0,benchmark_EvoSuite_calls=started,benchmark_EvoSuite_commands_planned=planned,fixture_EvoSuite_calls=fixtures,new_EvoSuite_calls=started+fixtures,disk_free_GB=round(shutil.disk_usage(R).free/1e9,2))
  s['blockers']=[('Maven260 có terminal evidence; còn Gradle40 chưa được qualify' if finished_all else 'Invocation đã kết thúc; xem audit trước khi tiếp tục, không tự resume'),'Gradle40 chưa được admit benchmark; paper/E1-full300 chưa chốt','GPT và repeated subset vẫn dừng']
  receipt=publish_json(R/'status.json',s,label='maven198_final_state')
  record={'finished_utc':now(),'exit_code':code,'Maven260_terminal':finished_all,'new_policy_accepted':s.get('new_policy_accepted'),'new_class_terminal_records':s.get('new_completed'),'error':error,'status_publication':receipt,'actual_benchmark_EvoSuite_starts':started,'actual_fixture_EvoSuite_starts':fixtures,'GPT_API_calls':0,'automatic_resume':False,'launch_plan_sha256':sha(plan_path),'full300_complete':False}
  dump(completion,record);audit.log('B1_REMAINING_MAVEN198_INVOCATION_FINISHED',completion_sha256=sha(completion),exit_code=code,Maven260_terminal=finished_all,automatic_resume=False,GPT_API_calls=0)
 return code
if __name__=='__main__':sys.exit(main())
