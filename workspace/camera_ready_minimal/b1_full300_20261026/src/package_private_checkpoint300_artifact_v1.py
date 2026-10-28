"""Package existing private evidence/code only; refuse credential candidates."""
import hashlib,json,re,sys,zipfile
from pathlib import Path
R=Path(__file__).resolve().parents[1];ROOT=R.parents[1];O=R/'camera_ready_checkpoint300_v1';D=O/'delivery';B=R.parent/'paired49_20261023';F=R/'completion_amendment_v1/final300_offline_v1'
sys.path.insert(0,str(B));import audit
def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
items={}
def add(p):
 p=Path(p)
 if p.is_file() and p.is_relative_to(ROOT):items[str(p)]=p.relative_to(ROOT).as_posix()
for entry in load(F/'EXTERNAL_EVIDENCE_MANIFEST.json')['files']:
 assert sha(entry['path'])==entry['sha256'];add(entry['path'])
for folder in [F,R/'src',B/'backup/original/scripts_v2']:
 for p in folder.rglob('*'):
  if p.suffix.lower() in {'.py','.ps1','.cmd','.md','.json','.jsonl','.csv','.txt','.gradle','.xml','.properties'}:add(p)
for folder in [R,R/'completion_amendment_v1']:
 for p in folder.iterdir():
  if p.suffix.lower() in {'.md','.json','.jsonl'}:add(p)
# Keep selected suite bytes and selected archive metadata without bundling caches/classes/jars.
for row in load(F/'class_results300.json'):
 job=Path(row['selected_result']['path']).parent;manifest=job/'artifact_manifest.json'
 if not manifest.exists():continue
 add(manifest)
 data=load(manifest)
 if isinstance(data,list):
  for e in data:
   rel=e.get('relative','');p=job/rel
   if p.suffix.lower() in {'.java','.xml','.csv','.json','.txt','.md','.gradle','.properties'} and p.is_file():
    assert sha(p)==e['sha256'],str(p);add(p)
# Existing policy-attempt audit remains a separate member in the private artifact.
oldzip=R/'policy_history_private_audit_v1.zip';add(oldzip)
add(ROOT/'scripts_v2/results/runs/full300_merged_20260724_paper/metrics_wide.csv')
for p in [ROOT/'scripts_v2/requirements.txt',ROOT/'requirements.txt',B/'audit/events_serialized_v2.jsonl']:add(p)
patterns=[('openai_key',rb'\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{24,}'),('private_key',rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),('aws_access_key',rb'\bAKIA[A-Z0-9]{16}\b'),('github_token',rb'\bgh[pousr]_[A-Za-z0-9]{30,}'),('bearer_literal',rb'(?i)authorization[\s"\x27:=]+bearer\s+[A-Za-z0-9._-]{24,}')]
findings=[];manifest=[]
for path,member in sorted(items.items()):
 p=Path(path);raw=p.read_bytes()
 if p.suffix.lower()!='.zip':
  for label,pattern in patterns:
   if re.search(pattern,raw):findings.append({'file':member,'pattern':label})
 else:
  with zipfile.ZipFile(p) as z:
   for name in z.namelist():
    for label,pattern in patterns:
     if re.search(pattern,z.read(name)):findings.append({'file':member+'!'+name,'pattern':label})
 manifest.append({'member':member,'source_path':path,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)})
scan={'files_scanned':len(items),'findings':findings,'patterns':[x[0] for x in patterns],'scope':'common high-confidence credential signatures; no claim of exhaustive semantic secret detection','new_experiments':0}
(O/'private_artifact_secret_scan.json').write_text(json.dumps(scan,indent=2),encoding='utf-8')
assert not findings,'Credential candidate detected; preserve source and do not package'
readme='''# Private experimental code and audit artifact — checkpoint300

NOT FOR PUBLIC RELEASE. This archive is separate from the camera-ready manuscript ZIP. No upload or publication has been performed. Do not launch a batch merely to inspect this archive.

The directory hierarchy under the archive root mirrors D:/A_ThucNghiem. ARTIFACT_MANIFEST.json records every original source path, archive member, SHA-256 and byte count. Files are copied unchanged. Paths inside original manifests remain absolute; this is an audit snapshot for the frozen Windows workspace, not a portable environment image.

## Scope

Contains experimental/analysis source, locked generation profiles and seeds, post-outcome policy/admission files, selected results, command plans/logs, selected archive text/XML/CSV/Java evidence, the300-class manifest, frozen G0/E0 per-class exports, offline statistics and the previous policy/attempt-history audit ZIP. Historical E0 raw reports are not independently recoverable by arm; do not assign final GPT reports to E0. Nonselected raw attempts remain in the original workspace; their available history/provenance is retained rather than silently overwritten.

## Read and reproduce analyses

Start with camera_ready_minimal/b1_full300_20261026/completion_amendment_v1/final300_offline_v1/README.md. The300-row JSON/CSV and statistics are self-contained inputs for numeric reanalysis. The independent verifier recomputes17principal means/CI checks using Python+NumPy and also validates pinned files in the original workspace. It never invokes experiment scripts. To inspect on another machine, use ARTIFACT_MANIFEST.json as the source-path/member mapping; do not silently edit locked manifests or treat missing environment paths as experimental failures.

## Dependencies and frozen configuration

Historical generation: gpt-4o-mini-2024-07-18,temperature0,top_p1,max2048tokens; no API seed. GPT/API is disabled for this revision and is not needed for analysis.
EvoSuite1.2.0, effectiveJDK8, BRANCH,search_budget60; E1 assertions=true,assertion_strategy=MUTATION,test_scaffolding=true,no_runtime_dependency=false,test_archive=false,use_separate_classloader=false; seed20261023+original1-basedindex. E0 settings and missing explicit seed are documented in the manuscript and original source.
Maven measurement: PIT1.16.0 and JaCoCo0.8.7. Gradle versions are wrapper-specific; the ten amended Spikes cases retain PIT1.3.1/plugin1.3.0. Exact resolved dependency closures, commands, limits and artifact hashes in the selected archives are authoritative. JUnit integration and measurement support are asymmetric across G0/E0/E1; never infer equal environments from shared focal source.
Analysis: Python3,NumPy; orchestration/audit uses psutil and the frozen source modules. PDF validation uses PyMuPDF and Poppler; manuscript build usesTectonic0.17.0. No scientific calculation requires Excel.

## Experimental replication is a separate action

Repository commit/module/focal paths are in manifest300.json; restore those exact inputs and JDK/tool versions in isolated workspaces. Recover dependencies from pinned closures and verify hashes before running any archived command. Binary tools,caches,fullthird-party repositories and credentials are not bundled. The current instruction forbids new experiments: this archive is evidence and code, not authorization to run them. No public artifact URL,license signature,registration or payment is claimed.

## Result semantics

221 observed PIT scores,58 conventional pipeline zeros,21 unresolved E1 scores;222 process passes,58 failures,20unknowns. Class294=0KILLED/44; sixTIMED_OUT are denominator-only. Whole-process timeouts112/269 do not have observed0% scores. Do not use E1-full300-complete wording. Single-run limitation,post-outcome support,diagnostic class3selection and original-outcome sensitivity remain explicit.
'''
zpath=D/'PRIVATE_checkpoint300_code_evidence.zip'
with zipfile.ZipFile(zpath,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 z.writestr('README_PRIVATE.md',readme);z.writestr('ARTIFACT_MANIFEST.json',json.dumps(manifest,indent=2));z.writestr('SECRET_SCAN.json',json.dumps(scan,indent=2))
 for p,member in sorted(items.items()):z.write(p,member)
with zipfile.ZipFile(zpath) as z:assert z.testzip() is None
receipt={'path':str(zpath),'sha256':sha(zpath),'files':len(items),'source_bytes':sum(x['bytes'] for x in manifest),'zip_bytes':zpath.stat().st_size,'secret_signature_findings':0,'private_only':True,'all_nonselected_raw_attempts_bundled':False,'new_experiments':0}
(O/'private_artifact_receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8');audit.log('CAMERA_READY_PRIVATE_ARTIFACT',**receipt);print(json.dumps(receipt,indent=2))
