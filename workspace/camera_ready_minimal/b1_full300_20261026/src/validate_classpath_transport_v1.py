"""Static/string/file-only transport checks. No tool runtime or admission."""
import copy,json,os,sys
from pathlib import Path
from classpath_transport_v1 import prepare,inflate,argv_sha256,serialized_units,needs_transport,WINDOWS_COMMAND_LIMIT
from maven_adapter_v1 import R,GuardAbort,sha,dump
B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
O=R/'validation/classpath_transport_v1';O.mkdir(parents=True,exist_ok=False);checks=[]
original=R/'jobs/012';source_hashes={str(p):sha(p) for p in [original/'result.json',original/'artifact_manifest.json',original/'commands/002/plan.json',original/'classpath_guards/01.json']}
plan=json.loads((original/'commands/002/plan.json').read_text(encoding='utf-8'));args=plan['argv'];cp=args[args.index('-projectCP')+1];guardrows=json.loads((original/'classpath_guards/01.json').read_text(encoding='utf-8'))
def reject(name,fn):
 try:fn()
 except GuardAbort:checks.append(name)
 else:raise AssertionError('Unsafe case accepted: '+name)
def case(name,logical,rows=None):
 out=O/name;out.mkdir();p=out/'classpath_guards/01.json';p.parent.mkdir()
 rows=rows if rows is not None else [{'path':x} for x in logical[logical.index('-projectCP')+1].split(os.pathsep)]
 dump(p,rows);proof={'profile_seed_tools_validated':True,'logical_argv_sha256':argv_sha256(logical),'classpath_guard_path':str(p.resolve()),'classpath_guard_sha256':sha(p),'scope':'static validation only; no execution admission'}
 return out,proof
out,proof=case('original012_simulation',args,guardrows);result=prepare(args,out,1,proof);assert result['applied'];manifest=Path(result['transport_manifest']);record=json.loads(manifest.read_text(encoding='utf-8'));actual=Path(record['classpath_file']).read_bytes()
assert actual==cp.encode('ascii')+b'\n';assert inflate(result['argv'],record,out)==args;checks.append('012 exact215orderedCPentries preserved incl duplicate tools.jar')
assert len(cp.split(os.pathsep))==215 and len(set(cp.split(os.pathsep)))==214;checks.append('no CP deduplication or filtering')
assert serialized_units(args)==33976 and serialized_units(result['argv'])<=WINDOWS_COMMAND_LIMIT;checks.append('only over-limit012parent command shortened')
assert result['argv'][:args.index('-projectCP')]==args[:args.index('-projectCP')] and result['argv'][args.index('-projectCP')+1:]==args[args.index('-projectCP')+2:];checks.append('every other arg including seed/options unchanged')
assert all(sha(p)==h for p,h in result['input_hashes'].items());checks.append('CP file manifest prior guard all returned as pinned process inputs')
reject('exclusive attempt refuses overwrite',lambda:prepare(args,out,1,proof))
short=list(args);short[short.index('-projectCP')+1]=guardrows[0]['path'];small,sproof=case('short_noop',short);before=set(small.iterdir());noop=prepare(short,small,1,sproof)
assert not noop['applied'] and noop['argv']==short and set(small.iterdir())==before;checks.append('short argv byte-for-byte no-op without CP/manifest files')
base=['C:/fixture/java.exe','-jar','C:/fixture/evosuite.jar','-class','fixture.X','-projectCP','x']
length=serialized_units(base);edge=base[:-1]+['x'*(1+WINDOWS_COMMAND_LIMIT-length)];assert serialized_units(edge)==WINDOWS_COMMAND_LIMIT and not needs_transport(edge);assert needs_transport(edge[:-1]+[edge[-1]+'x']);checks.append('exact32767inclNUL boundary no-op;32768 triggers')
assert serialized_units(['x\U0001f600'])==len('x\U0001f600')+2;checks.append('UTF16 surrogate-pair units counted rather than Python characters')
bad=copy.deepcopy(proof);bad['profile_seed_tools_validated']=False;reject('external validation required first',lambda:prepare(args,out,2,bad))
bad=copy.deepcopy(proof);bad['logical_argv_sha256']='0'*64;reject('changed logical argv rejected',lambda:prepare(args,out,2,bad))
bad=copy.deepcopy(proof);bad['classpath_guard_sha256']='0'*64;reject('prior classpath guard hash drift rejected',lambda:prepare(args,out,2,bad))
alter=list(args);alter[alter.index('-projectCP')+1]=cp+';C:/unvalidated.jar';aout,aproof=case('unvalidated_entry',alter,guardrows);reject('ordered CP evidence mismatch rejected',lambda:prepare(alter,aout,1,aproof))
alter=list(args);alter[alter.index('-projectCP')+1]=cp+'\n';aout,aproof=case('newline_rejected',alter);reject('CP newline rejected',lambda:prepare(alter,aout,1,aproof))
alter=list(args);alter[alter.index('-projectCP')+1]=cp+'\u00e9';aout,aproof=case('unicode_rejected',alter);reject('unqualified Scanner encoding rejected',lambda:prepare(alter,aout,1,aproof))
alter=args+['-projectCP',cp];aout,aproof=case('duplicate_route',alter,guardrows);reject('duplicate projectCP rejected',lambda:prepare(alter,aout,1,aproof))
alter=args+['-DCP_file_path=C:/other.txt'];aout,aproof=case('ambiguous_route',alter,guardrows);reject('second CP file route rejected',lambda:prepare(alter,aout,1,aproof))
alter=list(result['argv']);alter[-1]=alter[-1]+'tamper';reject('effective argv tamper detected by inverse hash',lambda:inflate(alter,record,out))
for p,h in source_hashes.items():assert sha(p)==h
checks.append('original012 plan guard result archive bytes untouched')
report={'status':'PASS_STATIC_ONLY','qualification':'NOT_RUNTIME_QUALIFIED','benchmark_admitted':False,'checks':checks,'source012_generation_plans':1,'source012_EvoSuite_processes_started':0,'logical012_UTF16_units_including_NUL':serialized_units(args),'transformed_fixture_UTF16_units_including_NUL':serialized_units(result['argv']),'processes_started':0,'Java_calls':0,'Maven_calls':0,'Gradle_calls':0,'EvoSuite_calls':0,'GPT_API_calls':0,'source012_hashes':source_hashes,'code_hashes':{str(p):sha(p) for p in [R/'src/classpath_transport_v1.py',Path(__file__)]},'limitations':['External semantic argv/tool/classpath guards remain mandatory','Native CP_file_path runtime fixture not yet qualified','No existing benchmark attempt rerun or changed','No admission, metric or parser change']}
dump(O/'result.json',report);audit.log('B1_CLASSPATH_TRANSPORT_STATIC_VALIDATED',result_sha256=sha(O/'result.json'),checks=len(checks),experiment_calls=0);print(json.dumps({k:v for k,v in report.items() if k not in {'source012_hashes','code_hashes'}},indent=2))
