"""Copy only reviewed function ASTs, with exact AST equality and source provenance."""
import ast,json,hashlib,sys
from pathlib import Path
R=Path(__file__).resolve().parents[1];B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
specs=[('backups/accepted49_adapter/evo_patch/working/AgoneTest/mavenLib.py','adapters/e49_generation_functions.py',['command_output_tail','timeout_output_tail','evosuite_classpath_entries','sanitize_evosuite_generation_classpath','should_retry_evosuite_with_sanitized_classpath','common_maven_skip_args','write_pom_tree','edit_pom_file','add_evosuite_pom','run_evosuite_generation_maven','run_maven_test_command']),('backups/accepted49_adapter/src/replay_fixed49_measurement_v5.py','adapters/e49_measurement_policy.py',['normalize','patch_pom','compare_cp']),('backups/accepted49_adapter/evo_patch/working/AgoneTest/evosuite_profile.py','adapters/e49_profile.py',['maven_generation_options'])]
records=[]
for source,target,names in specs:
 p=R/source;tree=ast.parse(p.read_text(encoding='utf-8-sig'));functions=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
 assert {n.name for n in functions}==set(names)
 for fn in functions:
  assert not fn.decorator_list,'Unexpected decorator'
  assert not any(isinstance(n,(ast.Import,ast.ImportFrom)) for n in ast.walk(fn)),'Nested import outside whitelist'
 text='"""E49 function-only copy. Load with explicit E-only bindings; no top-level side effects."""\n\n'+'\n\n'.join(ast.unparse(fn) for fn in functions)+'\n'
 dest=R/target;dest.parent.mkdir(parents=True,exist_ok=True)
 with dest.open('x',encoding='utf-8') as f:f.write(text)
 outtree=ast.parse(text);copied=[n for n in outtree.body if isinstance(n,ast.FunctionDef)]
 assert [ast.dump(n,include_attributes=False) for n in functions]==[ast.dump(n,include_attributes=False) for n in copied]
 records.append({'source':source,'source_sha256':audit.sha(p),'target':target,'target_sha256':audit.sha(dest),'functions':[n.name for n in copied],'AST_unchanged':True})
report={'status':'PASS','modules':records,'experiment_calls':0,'scope':'function-only extraction, no module execution and no benchmark admission'}
with (R/'audit/adapter_extraction_v1.json').open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
audit.log('B1_E49_FUNCTION_EXTRACTION',report_sha256=audit.sha(R/'audit/adapter_extraction_v1.json'),AST_unchanged=True,experiment_calls=0)
print(json.dumps(report,indent=2))
