"""Build a hash inventory; no execution or admission is granted here."""
from pathlib import Path
import json
from maven_adapter_v1 import R,JDK,WORKSPACE,sha,GuardAbort
from gradle_command_policy_v3 import PRIVATE_HOME,CONTEXT,launcher_paths
from parallel_pin_verify_v1 import verify_pins

SOURCES=['gradle_execution_v2.py','gradle_measurement_parser_v1.py','gradle_generation_argv_v1.py','gradle_generation_plan_guard_v1.py','gradle_command_policy_v3.py','gradle_command_policy_v2.py','gradle_process_supervisor_v5.py','gradle_native_recipe_v7.py','parallel_pin_verify_v1.py','gradle_sealed_inputs_v1.py','maven_adapter_v1.py','process_supervisor_v1.py','classpath_transport_v1.py','maven_controller_v2.py','measurement_parser_v1.py','native_junit_policy_candidate_v1.py','pom_integration_guard_v1.py','prepare_sandbox_v1.py','snapshot_store_v1.py','projection_io_v1.py']

def collect(extra=()):
 paths=[R/'src'/s for s in SOURCES]+[Path(x) for x in extra]
 paths += [CONTEXT,R/'manifest300.json',R/'protocol.json',R/'audit/adapter_extraction_v1.json',R/'audit/adapter_backup_manifest_v2.json',R/'backups/accepted49_adapter/src/junit_method_inventory_v1.py',R/'cache_preparation_gradle_v1/recovery_v2/manifest.json',R/'cache_preparation_gradle_v1/recovery_v2/complete.json',R/'cache_preparation_gradle_v1/protocol.json',JDK/'lib/tools.jar',WORKSPACE/'scripts_v2/evosuite-1.2.0.jar',WORKSPACE/'scripts_v2/evosuite-standalone-runtime-1.2.0.jar']
 paths += list((R/'adapters').glob('*.py'))
 records={str(p.resolve()):sha(p) for p in paths}
 rows=json.loads((R/'cache_preparation_gradle_v1/recovery_v2/manifest.json').read_text(encoding='utf-8'))
 for row in rows:
  rel=row['relative']
  if rel.startswith(('wrapper/dists/','caches/modules-2/files-2.1/')):records[str((PRIVATE_HOME/rel).resolve())]=row['sha256']
  if rel.startswith('caches/modules-2/files-2.1/'):records[str((Path('C:/Users/admin/.gradle')/rel).resolve())]=row['sha256']
 verify_pins(records)
 tools={str(p.resolve()):sha(p) for p in [JDK/'bin/java.exe',*launcher_paths().values()]}
 return records,tools
