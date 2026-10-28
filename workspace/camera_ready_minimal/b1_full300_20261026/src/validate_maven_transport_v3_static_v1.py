"""Static source/wiring review only; never import or execute the runtime fixture."""
import ast,hashlib,json,sys
from pathlib import Path
R=Path(__file__).resolve().parents[1];B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
names=['b1_maven_commands_v3.py','run_long_classpath_fixture_v1.py','classpath_transport_v1.py']
trees={n:ast.parse((R/'src'/n).read_text(encoding='utf-8')) for n in names}
old=(R/'src/b1_maven_commands_v2.py').read_bytes()
assert hashlib.sha256(old).hexdigest()=='a163aaf8c4230848a3f45c7d617dd0b5469174eabb05d85efeb96af994222f45'
c2=next(x for x in ast.parse(old).body if isinstance(x,ast.ClassDef));c3=next(x for x in trees['b1_maven_commands_v3.py'].body if isinstance(x,ast.ClassDef))
f2={x.name:x for x in c2.body if isinstance(x,ast.FunctionDef)};f3={x.name:x for x in c3.body if isinstance(x,ast.FunctionDef)}
unchanged=['check_call','maven_args','archive_attempt'];assert all(ast.dump(f2[k])==ast.dump(f3[k]) for k in unchanged)
text=(R/'src/b1_maven_commands_v3.py').read_text(encoding='utf-8');run=ast.get_source_segment(text,f3['run'])
assert run.index('checked_generation_argv')<run.index('guard=self.verify_classpath')<run.index('prepare_transport')<run.index('ticket=')<run.index('self.supervisor.run')
assert "prior['argv']" in run and "'argv':logical_args" in run and "'executed_argv':executed_args" in run
assert "self.supervisor.run(executed_args,cwd,timeout,self.lock['tool_hashes'][str(Path(executed_args[0]).resolve())],process_inputs)" in run
assert "Path(__file__).resolve(),R/'src/classpath_transport_v1.py'" in text
fixture=(R/'src/run_long_classpath_fixture_v1.py').read_text(encoding='utf-8')
assert fixture.index('msvcrt.locking(mutex.fileno(),msvcrt.LK_NBLCK,1)')<fixture.index('O.mkdir(')<fixture.index('result=execute(')
assert "jar.stat().st_size<100000" in fixture and "synthetic_long_classpath_fixture" in fixture
out=R/'validation/maven_transport_v3_static_v1';out.mkdir(parents=True,exist_ok=False)
report={'status':'PASS_STATIC_ONLY','qualification':'RUNTIME_FIXTURE_NOT_EXECUTED','syntax_sources':names,'unchanged_v2_methods':unchanged,'v2_bytes_unchanged':True,'logical_guard_before_transport_before_ticket':True,'retry_reads_logical_argv':True,'effective_argv_and_transport_inputs_passed_to_supervisor':True,'new_bridge_and_transport_code_explicitly_pinned':True,'mutex_before_fixture_mkdir_and_runtime':True,'small_Hamcrest_duplicates_synthetic_scope_only':True,'long_fixture_directory_exists':(R/'validation/long_classpath_fixture_v1').exists(),'fixture_executed_by_this_validation':False,'new_experiment_calls':0,'source_hashes':{n:audit.sha(R/'src'/n) for n in names}}
with (out/'result.json').open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
audit.log('B1_MAVEN_TRANSPORT_V3_STATIC_REVIEWED',result_sha256=audit.sha(out/'result.json'),experiment_calls=0);print(json.dumps(report,indent=2))
