"""Re-read archived accepted49; creates no tests or benchmark measurements."""
import json,sys
from pathlib import Path
from measurement_parser_v1 import parse
R=Path(__file__).resolve().parents[1];B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
stage=B/'e49_measurement_compat_v1';jobs=json.loads((stage/'input_manifest49.json').read_text(encoding='utf-8'));results=[]
for j in jobs:
 out=stage/'jobs'/f"{j['job_index']:02d}";old=json.loads((out/'result.json').read_text(encoding='utf-8'))
 # Verify archived evidence before trusting either raw files or the expected result.
 for item in json.loads((out/'artifact_manifest.json').read_text(encoding='utf-8')):assert audit.sha(B/item['path'])==item['sha256'],item['path']
 r=parse(out/'repo'/j['module'],j['focal_class'],j['package'],j['selected_test_fqcn'],bool(old['legacy_process_build']))
 fields=['legacy_process_build','legacy_strict_mutation_percent','focal_mutants','killed_mutants','strict_suite_evidence','strict_measurement_evidence']
 differences={k:{'accepted':old[k],'parser':r[k]} for k in fields if old[k]!=r[k]}
 assert not differences,{'job':j['job_index'],'differences':differences}
 results.append({'job_index':j['job_index'],'class_key':j['class_key'],'score':r['legacy_strict_mutation_percent'],'mutants':r['focal_mutants'],'suite':r['strict_suite_evidence'],'placeholder_count':r['inventory']['no_behavior_placeholder_count'] if r['inventory'] else None,'fields_equal':fields})
report={'status':'PASS','n':len(results),'exact_score_and_evidence_flags_equal_to_accepted49':True,'score_mean':sum(r['score'] for r in results)/len(results),'strict_suite_count':sum(r['suite'] for r in results),'rows':results,'parser_sha256':audit.sha(R/'src/measurement_parser_v1.py'),'new_experiment_calls':0}
dest=R/'validation/measurement_parser_v1';dest.mkdir(parents=True,exist_ok=False)
with (dest/'result.json').open('x',encoding='utf-8') as f:json.dump(report,f,ensure_ascii=False,indent=2)
audit.log('B1_PARSER_RECHECK_ACCEPTED49',n=49,report_sha256=audit.sha(dest/'result.json'),new_experiment_calls=0)
print(json.dumps({k:v for k,v in report.items() if k!='rows'},indent=2))
