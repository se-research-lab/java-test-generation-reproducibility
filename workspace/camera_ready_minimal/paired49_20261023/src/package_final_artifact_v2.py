"""Package accepted experiment evidence only. No generator/build-tool/API execution."""
import csv,json,sys,shutil,hashlib,re,zipfile
from pathlib import Path
from dotenv import dotenv_values
B=Path(__file__).resolve().parents[1];sys.path.insert(0,str(B));import audit
H=B/'final_handoff_20261024';A=H/'artifact';provenance=[]
def dump(p,obj):
 p.parent.mkdir(parents=True,exist_ok=True)
 if p.exists():
  assert json.loads(p.read_text(encoding='utf-8'))==obj;return
 with p.open('x',encoding='utf-8') as f:json.dump(obj,f,ensure_ascii=False,indent=2)
def put(p,t):
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x',encoding='utf-8') as f:f.write(t)
def copy(p,n):
 p=Path(p);q=A/n;q.parent.mkdir(parents=True,exist_ok=True);
 if q.exists():assert audit.sha(q)==audit.sha(p)
 else:shutil.copy2(p,q)
 assert audit.sha(p)==audit.sha(q)
 provenance.append({'member':n,'source':str(p),'sha256':audit.sha(p)})
def tree(root,prefix):
 for p in sorted(root.rglob('*')):
  if p.is_file() and '__pycache__' not in p.parts:copy(p,prefix+'/'+p.relative_to(root).as_posix())
assert not (A/'MANIFEST.json').exists();assert (B/'repeated_subset_v1/STOP_DO_NOT_RESUME.json').exists()
run=B/'backup/original/scripts_v2/results/runs/full300_merged_20260724_paper'
names=['metrics_wide.csv','metrics_long.csv','rq_decisions.csv','rq4_pairwise_strict_mutation.csv','statistical_test_inputs.csv','failure_diagnostics.csv','summary.csv','manifest.json','generated_tests_manifest.csv','api_log.csv','api_prompts.jsonl']
for n in names:
 p=run/n
 if not p.exists():p=audit.ROOT/'scripts_v2/results/runs/full300_merged_20260724_paper'/n
 copy(p,'data/historical300/'+n)
# Existing successful outputs, never a generation invocation.
src=audit.ROOT/'scripts_v2/results/runs/full300_merged_20260724_paper/generated_tests.zip'
with zipfile.ZipFile(src) as z:
 for n in z.namelist():
  if n.endswith('/'):continue
  q=A/'data/historical_generated_tests'/n;assert q.resolve().is_relative_to(A.resolve());q.parent.mkdir(parents=True,exist_ok=True);
  if q.exists():assert q.read_bytes()==z.read(n)
  else:q.write_bytes(z.read(n))
for n in ['class_sampling_manifest_final_seed42.csv','build_recipes_portable.csv','manifest_split_report.json']:copy(audit.ROOT/'scripts_v2/data_new'/n,'config/'+n)
for p in sorted((B/'backup/original/scripts_v2').glob('*.py')):copy(p,'code/historical/'+p.name)
tree(B/'backup/original/scripts_v2/AgoneTest','code/historical/AgoneTest')
for n in ['requirements.txt','run_settings.yaml']:
 p=audit.ROOT/'scripts_v2/AgoneTest'/n
 if p.exists():copy(p,'code/historical/AgoneTest/'+n)
selected=['e49_driver.py','run_e49_supplement.py','replay_fixed49_measurement_v5.py','diagnose_e1_compatibility_v4.py','analyze_e49_final_v2.py','analyze_measurement_compat49_v3.py','junit_method_inventory_v1.py','analyze49.py','analyze_cluster300.py','analyze_maven260.py','analyze_failure_stages.py']
for n in selected:copy(B/'src'/n,'code/E1/'+n)
for n in ['mavenLib.py','evosuite_profile.py']:copy(B/'evo_patch/working/AgoneTest'/n,'code/E1/AgoneTest/'+n)
copy(B/'audit.py','code/E1/audit.py')
jobs=json.loads((B/'e49_driver/input_manifest49.json').read_text());dump(A/'config/input_jobs49.json',jobs)
dump(A/'config/seeds49.json',[{k:j[k] for k in ['job_index','sample_index','class_key','seed']} for j in jobs])
copy(B/'e49_measurement_compat_v1/protocol.json','config/E1_measurement_protocol.json')
copy(B/'e49_driver/protocol49.json','config/E1_generation_protocol.json')
copy(B/'e49_driver/readiness_lock.json','config/recorded_environment_hashes.json')
for folder in ['cluster300_sensitivity','maven260_sensitivity','failure_stage_complete']:
 for p in sorted((B/'outputs'/folder).iterdir()):
  if p.is_file() and p.suffix in ['.json','.csv']:copy(p,'data/sensitivities/'+folder+'/'+p.name)
copy(B/'outputs/paired49.csv','data/historical_paired49.csv')
copy(B/'outputs/statistics.json','data/historical_paired49_statistics.json')
rows=[]
for j in jobs:
 i=j['job_index'];jj=f'{i:02}';raw=B/'e49_measurement_compat_v1/jobs'/jj;dest='evidence/E1/'+jj
 manifest=json.loads((raw/'artifact_manifest.json').read_text());copied=[]
 for x in manifest:
  p=B/x['path'];assert audit.sha(p)==x['sha256'],p
  n=p.relative_to(raw).as_posix();copy(p,dest+'/'+n);copied.append(n)
 cmds=[]
 for n in copied:
  if re.fullmatch(r'command_\d+\.json',n):
   c=json.loads((raw/n).read_text())
   if c['argv'][-5:]==['clean','verify','jacoco:prepare-agent','jacoco:report','org.pitest:pitest-maven:mutationCoverage']:cmds.append(n)
 assert len(cmds)==1;cmd=json.loads((raw/cmds[0]).read_text())
 idx={'pit_csv':[n for n in copied if n.endswith('/target/pit-reports/mutations.csv')],'measurement_commands':cmds,'measurement_stdout':Path(cmd['stdout']).name}
 assert len(idx['pit_csv'])==1;dump(A/dest/'raw_index.json',idx)
 # Exact generator command records and output, separate from measurement records.
 for p in sorted((B/'e49_driver/jobs'/jj).glob('command_*')):copy(p,dest+'/generation/'+p.name)
 focal=Path(j['source_repo'])/j['focal_path'];assert audit.sha(focal)==j['focal_sha256'];copy(focal,dest+'/focal/'+j['focal_class']+'.java')
 r=json.loads((raw/'result.json').read_text());rows.append({'job_index':i,'class_key':j['class_key'],'repo_id':j['repo_id'],'G0_mutation_percent':j['gpt_archived_mutation_percent'],'E0_mutation_percent':j['e0_archived_mutation_percent'],'E1_mutation_percent':r['legacy_strict_mutation_percent'],'process_build':r['legacy_process_build'],'focal_mutants':r['focal_mutants'],'killed_mutants':r['killed_mutants'],'seed':j['seed']})
with (A/'data/E1_fixed49.csv').open('x',encoding='utf-8',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
put(A/'requirements-analysis.txt','numpy==1.26.4\n')
put(A/'README.md','''# Accepted-data replication artifact

This package supports offline checking of historical G0/E0 (300 classes) and the final assertion-enabled E1 supplement (the same 49 historical common-build classes). It contains no incomplete repeated-subset observations. The five RQs and GPT cohorts 61/45/300 remain unchanged. E1 does not establish non-inferiority on 300 classes.

## Reproduce accepted-data analytics

Use Python 3.10 and NumPy 1.26.4 (requirements-analysis.txt). From this extracted directory:

    python -B reproduce_analytics.py --out ../analytics_check.json

Use a fresh output filename. The command verifies every packaged hash, reconstructs each final E1 focal score from raw PIT CSV plus the recorded process gate, checks the 49 keys against historical common builds, checks Table 3 denominators and recomputes the 20,000-draw repository bootstrap (seed 20261023). It never imports the archived experimental harness, invokes Java/Maven/Gradle, or accesses an API. This reproduces the stated E49 comparison; it does not remeasure GPT, rerun the historical RQ tests, or estimate run-to-run variance. Historical test inputs, decisions, and sensitivity outputs are included for inspection.

## Layout and interpretation

- data/historical300: unchanged archived metrics, decisions, prompt and API records; two preprocessing rows have no API generation.
- data/E1_fixed49.csv: public labels G0/E0/E1; no mixing with the other 251 historical rows.
- evidence/E1/01..49: exact final measurement evidence, generated Java and bytecode, effective POMs/classpaths, commands/stdout/stderr, focal source and PIT/JaCoCo/Surefire reports. Generation commands live in generation/.
- config: sample/commit/build recipes, generation and measurement protocols, per-class seeds and recorded environment hashes.
- code/historical: protected original runner and AgoneTest implementation. code/E1: archived generation, scoped integration and analysis implementations. Internal E2 identifiers in these unmodified code/evidence files refer to the accepted final measurement version; the manuscript calls this final configuration E1. They are not a second scoring scale.

## Environment and scope of regeneration

Historical GPT: gpt-4o-mini-2024-07-18, temperature 0, top_p 1, max_tokens 2048, no explicit API seed, no repair. Historical E0: EvoSuite 1.2.0, BRANCH/search_budget 60, assertions/scaffolding disabled, no runtime dependency, test archive and separate classloader disabled; no recorded explicit random seed. E1: assertions=true, assertion_strategy=MUTATION, scaffolding=true, no_runtime_dependency=false; other listed search options retained. Exact E1 seeds are in config/seeds49.json. Generation cap 240 s, measurement cap 300 s; at most one conditional sanitized-classpath retry with the same seed, not best-run selection.

Measurement environment: Windows, JDK 8u172, Maven (exact captured environment/command hashes in config and evidence), EvoSuite 1.2.0 plus matching standalone runtime, PIT 1.16.0, JaCoCo 0.8.7, historical GPT Surefire 2.22.2 and E-only Surefire 2.17. Conditional E-only JUnit 4.13.2/Hamcrest compatibility and include policy are described by config/E1_measurement_protocol.json and per-job policy_applied.json. The process gate is BUILD SUCCESS with no timeout; it can ignore test errors. Mutation is KILLED/all rows for the focal source-file/package (including nested classes), rounded to two decimals. Execution evidence is separate from scores. The zero/error/placeholder cases remain.

For future regeneration, first recover the repository URLs/commits and module recipes in config, create new isolated working copies, and verify focal/source hashes against config/input_jobs49.json. Install matching tool versions and resolve the dependencies listed by effective POMs and classpath/tree evidence. Inspect the archived driver and map its recorded Windows paths to that new environment before any explicit generation launch. Preserve the frozen prompt and same scoring/gates; do not change shared GPT integration to make E1 build. Archive every command, environment allowlist and failure. These archived drivers contain workspace-specific locks and are NOT a portable one-command benchmark launcher. Source revisions beyond the verified focal/source snapshots and exact historical regeneration are not certified. Third-party repository sources, JDK, Maven cache and binary dependencies are not redistributed wholesale; network/dependency availability is external.

No generation or Java measurement was executed to produce or validate this handoff. The author has stopped further GPT/EvoSuite/E300/Gradle jobs. Do not resume an old batch. No API key is included; never place credentials in this archive. The analysis-only command needs no credentials. Full regeneration, if separately authorized in the future, requires independent environment preparation and API access; outcome identity is not guaranteed.

## Availability and rights

Public hosting URL/DOI and artifact licensing have not been finalized. This is a local handoff, not a claim of public availability. Original Java sources and third-party code retain their existing notices; authors must confirm redistribution permissions before public release. The manuscript/source upload ZIP is separate from this experimental artifact. MANIFEST.json and SHA256SUMS list archive contents and hashes; scanner results are recorded separately in the handoff validation. Pattern-based scanning is not a universal proof of absence of all possible secrets.
''')
# Scan privately against actual locally configured secret values, plus common token/header patterns.
secrets=[str(v).encode() for k,v in dotenv_values(audit.ROOT/'scripts_v2/.env').items() if v and len(str(v))>=12 and re.search(r'KEY|TOKEN|SECRET|PASSWORD',k,re.I)]
patterns=[rb'sk-(?:proj-)?[A-Za-z0-9_-]{24,}',rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',rb'gh[pousr]_[A-Za-z0-9]{30,}',rb'AKIA[0-9A-Z]{16}',rb'(?i)Authorization\s*[:=]\s*[\"\x27]?Bearer\s+[A-Za-z0-9._-]{20,}']
findings=[]
for p in sorted(A.rglob('*')):
 if not p.is_file():continue
 data=p.read_bytes()
 if p.name=='.env' or p.suffix.lower() in ['.pem','.p12','.pfx'] or any(s in data for s in secrets) or any(re.search(pat,data) for pat in patterns):findings.append(p.relative_to(A).as_posix())
dump(H/'validation/artifact_secret_scan.json',{'status':'PASS' if not findings else 'BLOCKED','file_findings_without_secret_values':findings,'known_secret_values_checked':len(secrets),'pattern_classes':len(patterns),'no_secret_values_logged':True})
assert not findings,findings
dump(H/'validation/artifact_copy_provenance.json',provenance)
entries=[{'path':p.relative_to(A).as_posix(),'bytes':p.stat().st_size,'sha256':audit.sha(p)} for p in sorted(A.rglob('*')) if p.is_file()]
dump(A/'MANIFEST.json',{'scope':'accepted historical300 plus final E1_fixed49 only','files':entries})
put(A/'SHA256SUMS',''.join(x['sha256']+'  '+x['path']+'\n' for x in entries)+audit.sha(A/'MANIFEST.json')+'  MANIFEST.json\n')
audit.log('ACCEPTED_ARTIFACT_PACKAGED',files=len(entries),manifest_sha256=audit.sha(A/'MANIFEST.json'),new_experiment_calls=0)
print(json.dumps({'status':'PACKAGED_PENDING_OFFLINE_CHECK','files':len(entries),'bytes':sum(x['bytes'] for x in entries)}))
