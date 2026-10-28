"""Final read-only pause audit and handoff; never launches a benchmark or queue."""
import json,psutil,sys,subprocess
from pathlib import Path
from datetime import datetime,timezone
from maven_adapter_v1 import R,sha,dump
from projection_io_v1 import publish_json
A=R/'completion_amendment_v1';O=A/'pause_20261027_after173_v1';B=R.parent/'paired49_20261023'
sys.path.insert(0,str(B));import audit
def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def main():
 checkpoint=load(O/'checkpoint.json');assert (R/'STOP_REQUESTED.json').exists()
 owners=[]
 for name in ['maven_pom_run_v3','maven_junit3_run_v2','gradle_pit_run_v2','remaining_pom8_launch_v1','automatic_finalization_v1','automatic_finalization_v2','automatic_finalization_v3','automatic_finalization_v4']:
  p=A/name/'owner.json'
  if not p.exists():continue
  d=load(p);alive=False
  try:proc=psutil.Process(d['pid']);alive=proc.create_time()==d['create_time']
  except psutil.NoSuchProcess:pass
  owners.append({'name':name,'pid':d['pid'],'create_time':d['create_time'],'same_process_alive':alive});assert not alive,'A worker/queue is still active: '+name
 scoped=[];unknown=[];monitors=[]
 patterns=['complete_maven_groups','run_remaining5_after173','run_remaining_maven','run_gradle_full40','run_completion_maven_sequence','run_stage_completion_sequence','launch_remaining_pom8','finalize_completion_when_ready','run_repeated_subset']
 for proc in psutil.process_iter(['pid','name','cmdline']):
  try:
   name=(proc.info['name'] or '').lower();cmd=' '.join(proc.info['cmdline'] or []);in_scope=str(R).lower() in cmd.lower()
   if in_scope and (name in {'java.exe','javaw.exe'} or name=='python.exe' and any(x in cmd for x in patterns)):scoped.append({'pid':proc.pid,'name':name,'argv':proc.info['cmdline']})
   if in_scope and name=='python.exe' and any(x in cmd for x in ['serve_completion_preview','monitor/serve','monitor\\serve']):monitors.append({'pid':proc.pid,'name':name,'read_only':True})
  except (psutil.NoSuchProcess,psutil.AccessDenied):
   if (proc.info.get('name') or '').lower() in {'java.exe','javaw.exe'}:unknown.append(proc.pid)
 assert not scoped and not unknown,'Cannot certify experiment quiescence'
 nextjob=R/'jobs/211_completion_pom_v3';assert not list((nextjob/'commands').glob('*/started.json'))
 status={'status':'PAUSED_AND_NO_EXPERIMENT_WORKERS','verified_utc':datetime.now(timezone.utc).isoformat(),'known_worker_queue_identities':owners,'scoped_experiment_processes':scoped,'uninspectable_Java_pids':unknown,'read_only_monitors':monitors,'STOP_persistent':True,'automatic_resume':False,'scheduled_restart':False,'new_generation_calls_during_pause':0,'new_measurement_calls_during_pause':0,'class211_started_commands':0}
 dump(O/'worker_quiescence.json',status)
 guard=R.parents[1]/'review_reports/minimal_camera_ready_20261023/guard_rq123_frozen.py'
 proc=subprocess.run([sys.executable,'-B','-X','utf8',str(guard)],capture_output=True,text=True,creationflags=subprocess.CREATE_NO_WINDOW);assert proc.returncode==0,proc.stderr;g=json.loads(proc.stdout);assert g['status']=='PASS';dump(O/'GPT_RQ123_guard.json',g)
 audit.verify()
 progress={'phase':'PAUSED_BY_USER_AFTER_VERIFIED173','active_index':None,'finished_indices':checkpoint['accepted25_indices'],'remaining_indices':checkpoint['remaining_indices'],'completed_checkpoints':25,'remaining_count':5,'updated_utc':status['verified_utc'],'worker_experiment_count':0,'follow_on_queues_enabled':False,'STOP_persistent':True,'automatic_resume':False,'scheduled_restart':False,'GPT_API_calls':0,'full300_complete':False}
 publish_json(R/'runtime/completion_progress.json',progress,label='user_paused_verified')
 pending=load(O/'remaining5.json');accepted=load(O/'accepted25.json')
 python='C:\\Users\\admin\\AppData\\Local\\Programs\\Python\\Python310\\python.exe';command='& "'+python+'" -B -X utf8 "'+str(R/'src/resume_user_paused_e1_v1.py')+'" --explicit-user-resume'
 (O/'RESUME_COMMAND.ps1.txt').write_text('# Chỉ chạy SAU khi tác giả yêu cầu resume; không có timer/auto-resume.\n'+command+'\n',encoding='utf-8')
 lines=['# Checkpoint tạm dừng sau class173','', 'Đã kiểm chứng archive173 và không còn worker thực nghiệm hoặc queue nối tiếp. STOP_REQUESTED.json giữ khóa. Chỉ trang preview read-only có thể tiếp tục chạy. Không có lịch tự khởi động sau một giờ.','',f"Thời điểm kiểm chứng UTC: {status['verified_utc']}.",'','## Phạm vi đã lưu','', '25 class có checkpoint: 24 class trước đó và class173 vừa hoàn tất. Checkpoint không đồng nghĩa tất cả đã có mutation score:10 JUnit3 vẫn chưa có PIT hoàn chỉnh;112 là timeout với observed mutation=null và conventional end-to-end0. Các trạng thái này giữ nguyên.','', 'Class173 có report PIT hoàn chỉnh, observed mutation90.00%, source/production-bytecode guards PASS. Original archive giữ nguyên; hai receipt derived-POM ghi sau archive được kiểm chứng và đưa vào current173_complete_archive.json.','', 'Dispatcher đã bắt đầu khôi phục workspace211 ngay khi173 kết thúc. Lệnh thực nghiệm đầu tiên bị STOP chặn:0 compile/generation/test/measurement commands started. Workspace này được giữ nguyên và có hash manifest; đây không phải một class đã sinh test hoặc có kết quả.','', '## Năm class còn lại','', '| Index | Focal class | Seed |','|---:|---|---:|']
 for j in pending:lines.append(f"| {j['sample_index_1based']} | {j['focal_class']} | {j['seed']} |")
 lines += ['','## Resume khi có yêu cầu mới','', 'Lệnh đã chuẩn bị, chưa chạy:','', '```powershell',command,'```','', 'Lệnh chỉ nhận211,220,269,275,294, dùng output namespace mới; bỏ toàn bộ25 checkpoint đã lưu. Policy, profile, seed, timeout, dependencies, PIT engine/mutators/targets và core controller hashes không đổi. STOP chỉ được chuyển vào evidence khi lệnh explicit-resume được tác giả yêu cầu. Không tự chạy queue audit/package hoặc gọi GPT/API.','', 'File chính: checkpoint.json; accepted25.json; remaining5.json; checkpoint_pins.json; current173_complete_archive.json; worker_quiescence.json; resume_admission_v1.json; resume_dispatch_only.diff.','', 'Bộ25 thuộc đợt bổ sung30 class. Dữ liệu270 trước đó, GPT/E0, RQ1–RQ3, fixed49 và paper giữ nguyên.']
 (O/'CHECKPOINT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
 manifest=[{'relative':p.relative_to(O).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(O.rglob('*')) if p.is_file()]
 dump(O/'PAUSE_MANIFEST.json',manifest);(O/'SHA256SUMS.txt').write_text('\n'.join(row['sha256']+'  '+row['relative'] for row in manifest)+'\n',encoding='utf-8')
 audit.log('USER_PAUSE_CONFIRMED_NO_EXPERIMENT_WORKERS',pause_manifest_sha256=sha(O/'PAUSE_MANIFEST.json'),quiescence_sha256=sha(O/'worker_quiescence.json'),completed_checkpoints=25,remaining=checkpoint['remaining_indices'],automatic_resume=False,scheduled_restart=False)
 print(json.dumps({'status':status['status'],'completed':25,'remaining':checkpoint['remaining_indices'],'worker_count':0,'queues_enabled':False,'policy_seed_config_changed':False,'resume_command_prepared_only':True,'checkpoint':str(O/'CHECKPOINT.md')},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
