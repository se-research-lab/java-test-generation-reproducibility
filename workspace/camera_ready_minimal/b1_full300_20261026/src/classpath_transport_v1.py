"""Transport-only EvoSuite CP-file candidate. NOT_RUNTIME_QUALIFIED.

Call only AFTER the logical generation argv/profile/seed/tools and every ordered
classpath entry have passed the external guards. This module launches nothing,
does not admit execution, and never filters/reorders/deduplicates the classpath.
"""
import hashlib,json,os,subprocess
from pathlib import Path
from maven_adapter_v1 import GuardAbort,sha,new_job_output

WINDOWS_COMMAND_LIMIT=32767

def ensure(ok,message):
 if not ok:raise GuardAbort(message)

def argv_sha256(argv):
 return hashlib.sha256(json.dumps(list(argv),ensure_ascii=False,separators=(',',':')).encode('utf-8')).hexdigest()

def serialized_units(argv):
 """Windows UTF-16 command-line code units, including the terminating NUL."""
 return len(subprocess.list2cmdline(list(argv)).encode('utf-16-le'))//2+1

def needs_transport(argv):return serialized_units(argv)>WINDOWS_COMMAND_LIMIT

def _logical(argv):
 args=list(argv);ensure(args and all(isinstance(x,str) for x in args),'Logical argv must contain strings')
 ensure(not any('\0' in x or '\r' in x or '\n' in x for x in args),'NUL/newline in logical argv')
 ensure(args.count('-projectCP')==1,'Exactly one logical -projectCP is required')
 index=args.index('-projectCP');ensure(index+1<len(args) and bool(args[index+1]),'Missing logical project classpath')
 ensure(not any(x.startswith('-DCP_file_path=') or x.startswith('-DCP=') for x in args),'Ambiguous existing classpath route')
 ensure('-jar' in args and args.index('-jar')<index,'CP transport must be an EvoSuite CLI option after -jar')
 return args,index,args[index+1]

def _proof(args,cp,out,validation):
 ensure(validation.get('profile_seed_tools_validated') is True,'External argv/profile/seed/tool validation required before transport')
 ensure(validation.get('logical_argv_sha256')==argv_sha256(args),'External logical argv proof differs')
 raw=validation.get('classpath_guard_path');ensure(raw and Path(raw).is_absolute(),'Absolute prior classpath guard required')
 p=Path(raw).resolve();ensure(p.is_relative_to(out/'classpath_guards') and p.is_file(),'Classpath evidence outside owned guard directory')
 ensure(sha(p)==validation.get('classpath_guard_sha256'),'Prior classpath guard hash differs')
 rows=json.loads(p.read_text(encoding='utf-8'));ensure(isinstance(rows,list),'Unexpected classpath evidence shape')
 expected=[str(Path(s).resolve()) for s in cp.split(os.pathsep)]
 ensure([str(Path(r['path']).resolve()) for r in rows]==expected,'Ordered logical CP differs from prior guarded entries')
 return p

def inflate(effective_argv,record,out):
 """Reconstruct the exact guarded logical argv from a sealed transport record."""
 out=new_job_output(out);args=list(effective_argv)
 ensure(record.get('applied') is True,'Inflation requires an applied transport record')
 file=Path(record['classpath_file']).resolve();ensure(file.is_relative_to(out/'classpath_transport'),'Transport CP file outside owned attempt')
 data=file.read_bytes();ensure(hashlib.sha256(data).hexdigest()==record['classpath_file_sha256'],'Transport CP bytes changed')
 ensure(data.endswith(b'\n') and data.count(b'\n')==1 and b'\r' not in data and b'\0' not in data,'Transport file must contain exactly one terminated line')
 cp=data[:-1].decode('ascii');token='-DCP_file_path='+str(file)
 ensure(args.count(token)==1 and '-projectCP' not in args,'Effective classpath route changed')
 ensure(argv_sha256(args)==record['effective_argv_sha256'],'Effective argv changed')
 i=args.index(token);logical=args[:i]+['-projectCP',cp]+args[i+1:]
 ensure(argv_sha256(logical)==record['logical_argv_sha256'],'Inflated logical argv differs')
 return logical

def prepare(argv,out,attempt,validation):
 """Return argv/input hashes; exclusively create CP/manifest only if over limit.

`validation` is external evidence, not a substitute for running the guards:
profile_seed_tools_validated=True, logical_argv_sha256=argv_sha256(checked_argv),
classpath_guard_path=<owned prior guard JSON>, classpath_guard_sha256=<its hash>.
The caller must pass returned input_hashes to its supervised process launcher.
"""
 out=new_job_output(out);ensure(out.is_dir(),'Owned output must already exist')
 ensure(isinstance(attempt,int) and not isinstance(attempt,bool) and 1<=attempt<=2,'Generation attempt outside locked1..2')
 args,index,cp=_logical(argv);guard=_proof(args,cp,out,validation);units=serialized_units(args)
 common={'qualification':'NOT_RUNTIME_QUALIFIED','benchmark_admitted':False,'logical_argv_sha256':argv_sha256(args),'logical_command_UTF16_units_including_NUL':units}
 if units<=WINDOWS_COMMAND_LIMIT:
  return {**common,'applied':False,'argv':list(args),'input_hashes':{str(guard):sha(guard)},'transport_manifest':None}
 ensure(cp.isascii(),'Non-ASCII CP requires separate JVM Scanner encoding qualification')
 folder=out/'classpath_transport'/f'{attempt:02d}';file=folder/'project_classpath.txt'
 ensure(str(file).isascii(),'Transport file path requires ASCII qualification')
 ensure(not folder.exists(),'Transport attempt already exists; no overwrite/retry')
 effective=args[:index]+['-DCP_file_path='+str(file)]+args[index+2:]
 ensure(serialized_units(effective)<=WINDOWS_COMMAND_LIMIT,'Transport command still exceeds Windows limit')
 folder.mkdir(parents=True,exist_ok=False);data=cp.encode('ascii')+b'\n'
 with file.open('xb') as f:f.write(data)
 record={**common,'applied':True,'attempt':attempt,'transport':'EvoSuite CLI CP_file_path after -jar; exact first line','classpath_file':str(file),'classpath_file_sha256':sha(file),'classpath_string_sha256':hashlib.sha256(cp.encode('ascii')).hexdigest(),'CP_entries_including_duplicates':len(cp.split(os.pathsep)),'effective_argv_sha256':argv_sha256(effective),'effective_command_UTF16_units_including_NUL':serialized_units(effective),'logical_argv':args,'effective_argv':effective,'external_validation':dict(validation),'external_classpath_guard_sha256':sha(guard),'no_filter_reorder_deduplicate':True}
 ensure(inflate(effective,record,out)==args,'Inverse transport changed logical generation argv')
 record['inverse_inflation_verified']=True;manifest=folder/'transport_manifest.json'
 with manifest.open('x',encoding='utf-8') as f:json.dump(record,f,ensure_ascii=False,indent=2)
 return {**common,'applied':True,'argv':effective,'input_hashes':{str(file):sha(file),str(manifest):sha(manifest),str(guard):sha(guard)},'transport_manifest':str(manifest),'effective_command_UTF16_units_including_NUL':serialized_units(effective)}
