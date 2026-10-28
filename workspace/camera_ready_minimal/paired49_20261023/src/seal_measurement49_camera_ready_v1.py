"""Close an explicit hash registry for final49 outputs; no experiment or original edits."""
import hashlib,json,re,sys
from pathlib import Path
from datetime import datetime,timezone
B=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(B))
import audit
sha=audit.sha
rel=lambda p:Path(p).relative_to(B).as_posix()
registry=B/'audit/measurement49_camera_ready_registry_v1.json'
assert not registry.exists()
for p in [Path(__file__),B/'BAO_CAO_KET_QUA_49_VA_CAMERA_READY_MOI.md']:
    audit.log('NEW_FILE_REGISTERED',path=rel(p),sha256=sha(p),bytes=p.stat().st_size,change_type='new isolated final report or release registry script')
report=(B/'BAO_CAO_KET_QUA_49_VA_CAMERA_READY_MOI.md').read_text(encoding='utf-8')
links=re.findall(r'\]\(([^)]+)\)',report)
for target in links:
    if '://' not in target: assert (B/target.split('#')[0]).exists(),target
entries=set()
for r in ['BAO_CAO_KET_QUA_49_VA_CAMERA_READY_MOI.md','audit/final49_static_registry_v1.json','audit/compatibility_15page_static_registry_v1.json','audit/protected_manifest.json','protocol.json','PROTOCOL_REPEATED_SUBSET_DE_XUAT.md','SLR_MARGIN_PILOT_EVIDENCE_20261023.md']:
    entries.add(B/r)
for r in ['src/finalize_compat49_release_v1.py','src/seal_measurement49_camera_ready_v1.py','src/replay_fixed49_measurement_v5.py','src/junit_method_inventory_v1.py','src/analyze_measurement_compat49_v3.py','src/independent_measurement49_raw_audit_v3.py','src/compare_compat49_verified_raw_late_v1.py','src/update_v3_final_compat49_results_v6.py','src/build_manuscript_compat49_v2.py','src/render_manuscript_compat49_v1.py']:
    entries.add(B/r)
for dirname in ['outputs/e49_measurement_compat_v1','validation/camera_ready_compat49_release_v1','validation/independent_compat49_raw_v1','validation/independent_compat49_late_comparison_v1','validation/independent_manifest_selfhash_correction_v1','validation/critical_runtime_cache_final_v1','validation/packaged_class_index_correction_v1','validation/inspection_amendment_v1','validation/junit_inventory_annotation_v1','validation/replay_guard_controls_v2','manuscript_revision_v3_compat49/source','manuscript_revision_v3_compat49/backups','manuscript_revision_v3_compat49/output','manuscript_revision_v3_compat49/build_04']:
    entries.update(p for p in (B/dirname).rglob('*') if p.is_file())
entries.update(p for p in (B/'e49_measurement_compat_v1').iterdir() if p.is_file())
man=json.loads((B/'outputs/e49_measurement_compat_v1/output_manifest.json').read_text(encoding='utf-8'))
entries.update(B/p for p in man['inputs'])
rows=[]
for p in sorted(entries):
    assert p.is_file(),p
    rows.append({'path':rel(p),'sha256':sha(p),'bytes':p.stat().st_size})
prior=audit.events()[-1]
obj={'created_utc':datetime.now(timezone.utc).isoformat(),'status':'CLOSED_FIXED49_AND_VERIFIED_15PAGE_REVIEW_DRAFT','files':rows,'ledger_head_before_registry':{'seq':prior['seq'],'sha256':prior['event_sha256']},'raw_file_integrity':'8897 raw files rehashed in final_validation; their manifests pinned here','raw_measurement_calls':49,'final_measurement_generation_calls':0,'GPT_API_calls':0,'originals_read_only':True,'excluded':'Live audit ledger, Maven/Tectonic caches and working checkout bulk; integrity scoped by manifests and guards','remaining_review_concerns':['Repeated-run variance not measured','5pp practical margin and pre-pilot analysis lock not established','Fixed49 supplement does not replace assertion-disabled full300 baseline','Artifact access URL pending']}
with registry.open('x',encoding='utf-8') as f:json.dump(obj,f,ensure_ascii=False,indent=2);f.write('\n')
audit.log('CLOSED_REGISTRY_CREATED',path=rel(registry),sha256=sha(registry),files=len(rows),purpose='final49 results, readable report and 15-page draft/source ZIP')
for row in rows:assert sha(B/row['path'])==row['sha256'],row['path']
audit.verify()
print(json.dumps({'status':'PASS','closed_registry_files':len(rows),'registry':str(registry),'registry_sha256':sha(registry),'report_links_checked':len(links),'report_sha256':sha(B/'BAO_CAO_KET_QUA_49_VA_CAMERA_READY_MOI.md'),'original_files_modified':False,'submission_performed':False},indent=2))
