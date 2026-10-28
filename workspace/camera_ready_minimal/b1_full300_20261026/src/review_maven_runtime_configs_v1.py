"""Review frozen .mvn launch options without executing or modifying them."""
import json,sqlite3,hashlib,re,sys
from pathlib import Path
R=Path(__file__).resolve().parents[1];B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
def load(p):return json.loads(p.read_text(encoding='utf-8'))
S=R/'inputs/snapshot_v3';rows=load(R/'audit/frozen_inputs251_review_v1/rows.json');mapping={i:x for x in load(S/'index.json') for i in x['class_indices']};findings=[]
with sqlite3.connect((S/'content.sqlite3').as_uri()+'?mode=ro',uri=True) as db:
 for j in rows:
  if j['build_tool']!='maven':continue
  for name in j['runtime_config_paths']:
   entry=mapping[j['sample_index_1based']];manifest=load(R/entry['manifest']);f=next(r for r in manifest['files'] if r['relative']==name)
   data=db.execute('SELECT data FROM blobs WHERE sha256=?',(f['sha256'],)).fetchone()[0];assert hashlib.sha256(data).hexdigest()==f['sha256']
   tokens=[v for line in data.decode('utf-8-sig').splitlines() if line.strip() and not line.lstrip().startswith('#') for v in line.split()]
   # Keep all unchanged launch options. Only common memory sizes, stack size and reactor parallelism are approved here.
   allowed=[];unknown=[]
   i=0
   while i<len(tokens):
    token=tokens[i]
    if re.fullmatch(r'-X(?:mx|ms|ss)\d+[kKmMgG]?',token) or re.fullmatch(r'-XX:(?:MaxPermSize|ReservedCodeCacheSize)=\d+[kKmMgG]?',token):allowed.append(token)
    elif token in ['-T','--threads'] and i+1<len(tokens) and re.fullmatch(r'\d+(?:\.\d+)?C?',tokens[i+1]):allowed.extend(tokens[i:i+2]);i+=1
    elif re.fullmatch(r'-T\d+(?:\.\d+)?C?',token):allowed.append(token)
    else:unknown.append({'sha256':hashlib.sha256(token.encode()).hexdigest(),'option_name':token.split('=',1)[0] if token.startswith('-') else 'non-option-value'})
    i+=1
   findings.append({'sample_index':j['sample_index_1based'],'relative':name,'sha256':f['sha256'],'allowed_original_options':allowed,'unqualified_options':unknown,'status':'UNCHANGED_ACCEPTABLE' if not unknown else 'NEEDS_REVIEW'})
report={'class_count':len({r['sample_index'] for r in findings}),'files':findings,'unqualified_class_indices':sorted({r['sample_index'] for r in findings if r['unqualified_options']}),'source_changes':0,'experiment_calls':0,'note':'Original project options preserved. Maven -T is internal reactor concurrency; benchmark job concurrency remains1. No budget-equality claim.'}
dest=R/'audit/maven_runtime_configs_v1.json'
with dest.open('x',encoding='utf-8') as f:json.dump(report,f,ensure_ascii=False,indent=2)
audit.log('B1_MAVEN_RUNTIME_CONFIG_REVIEW',report_sha256=audit.sha(dest),unqualified=report['unqualified_class_indices']);print(json.dumps(report,indent=2))
