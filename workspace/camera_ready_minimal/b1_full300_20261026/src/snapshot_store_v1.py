"""Private content-addressed backup. No imports of generators or build runners."""
import hashlib,os,sqlite3,stat
from pathlib import Path,PurePosixPath,PureWindowsPath

class IntegrityError(RuntimeError):pass

def digest(data):return hashlib.sha256(data).hexdigest()

def safe_relative(value):
 if not isinstance(value,str) or not value or '\\' in value or ':' in value:
  raise IntegrityError('Invalid relative path')
 rel=PurePosixPath(value)
 if rel.is_absolute() or PureWindowsPath(value).drive or any(p in {'.','..',''} for p in value.split('/')):
  raise IntegrityError('Path traversal or noncanonical path')
 return Path(*rel.parts)

def contained(root,relative):
 root=Path(root).resolve();p=root/safe_relative(relative)
 if not p.resolve().is_relative_to(root):raise IntegrityError('Resolved path outside owned root')
 current=p
 while current!=root:
  if current.exists():
   info=current.lstat()
   if current.is_symlink() or getattr(info,'st_file_attributes',0)&getattr(stat,'FILE_ATTRIBUTE_REPARSE_POINT',1024):
    raise IntegrityError('Reparse point/symlink forbidden')
  current=current.parent
 return p

def open_new_store(path):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 with path.open('xb'):pass
 conn=sqlite3.connect(path)
 conn.execute('CREATE TABLE blobs (sha256 TEXT PRIMARY KEY, nbytes INTEGER NOT NULL, data BLOB NOT NULL)')
 conn.execute('CREATE TABLE metadata (name TEXT PRIMARY KEY, value TEXT NOT NULL)')
 conn.execute("INSERT INTO metadata VALUES ('schema','b1-cas-v1')")
 conn.commit();return conn

def capture_file(conn,root,relative,expected_size=None,expected_sha=None):
 path=contained(root,relative);before=path.stat()
 if not path.is_file():raise IntegrityError('Missing regular file: '+relative)
 if expected_size is not None and before.st_size!=expected_size:raise IntegrityError('Size changed after census: '+relative)
 data=path.read_bytes();after=path.stat()
 if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns) or len(data)!=after.st_size:
  raise IntegrityError('Input changed during snapshot: '+relative)
 h=digest(data)
 if expected_sha is not None and h!=expected_sha:raise IntegrityError('Frozen hash mismatch: '+relative)
 prior=conn.execute('SELECT nbytes FROM blobs WHERE sha256=?',(h,)).fetchone()
 if prior is None:conn.execute('INSERT INTO blobs VALUES (?,?,?)',(h,len(data),data))
 elif prior[0]!=len(data):raise IntegrityError('Content-address collision')
 return {'relative':relative,'sha256':h,'bytes':len(data),'mode':stat.S_IMODE(before.st_mode),'mtime_ns_at_capture':before.st_mtime_ns}

def restore(conn,rows,destination):
 dest=Path(destination)
 if dest.exists():raise IntegrityError('Restore requires a new directory')
 # Validate every name before making output; detect Windows case aliases.
 seen=set()
 for row in rows:
  safe_relative(row['relative']);key=row['relative'].casefold()
  if key in seen:raise IntegrityError('Duplicate or case-colliding paths')
  seen.add(key)
 dest.mkdir(parents=True,exist_ok=False)
 for row in rows:
  p=contained(dest,row['relative']);blob=conn.execute('SELECT nbytes,data FROM blobs WHERE sha256=?',(row['sha256'],)).fetchone()
  if blob is None or blob[0]!=row['bytes'] or len(blob[1])!=row['bytes'] or digest(blob[1])!=row['sha256']:
   raise IntegrityError('Blob integrity failure')
  p.parent.mkdir(parents=True,exist_ok=True)
  with p.open('xb') as f:f.write(blob[1])
  os.chmod(p,row['mode'])
  if digest(p.read_bytes())!=row['sha256']:raise IntegrityError('Restored bytes differ')

def enumerate_census_paths(root):
 root=Path(root);files=set();excluded=[]
 for parent,dirs,names in os.walk(root,followlinks=False):
  p=Path(parent);parts=p.relative_to(root).parts
  for d in dirs[:]:
   q=p/d;reparse=getattr(q.lstat(),'st_file_attributes',0)&getattr(stat,'FILE_ATTRIBUTE_REPARSE_POINT',1024)
   if q.is_symlink() or reparse or d in {'.git','.gradle','.idea','node_modules','__pycache__'} or (d in {'target','build'} and 'src' not in parts):
    excluded.append(q.relative_to(root).as_posix());dirs.remove(d)
  for n in names:
   q=p/n;rel=q.relative_to(root).as_posix()
   if q.is_symlink():excluded.append(rel);continue
   files.add(rel)
 return files,set(excluded)
