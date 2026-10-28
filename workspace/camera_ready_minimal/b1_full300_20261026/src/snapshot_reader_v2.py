"""Read-only source capture with validated directory identity caching.
Every file is still read and hashed. No content is inferred from mtime or another repo.
"""
import os,stat
from pathlib import Path
from snapshot_store_v1 import IntegrityError,safe_relative,digest

class SourceReader:
 def __init__(self,root,conn):
  self.root=Path(root).resolve();self.conn=conn;self.dirs={};self.known={h:n for h,n in conn.execute('SELECT sha256,nbytes FROM blobs')}
  self._directory(self.root)
 def _directory(self,path):
  if path in self.dirs:return
  if path!=self.root:
   if not path.is_relative_to(self.root):raise IntegrityError('Directory outside source root')
   self._directory(path.parent)
  s=path.lstat()
  if not stat.S_ISDIR(s.st_mode) or getattr(s,'st_file_attributes',0)&1024:raise IntegrityError('Source directory reparse/non-directory')
  self.dirs[path]=(s.st_dev,s.st_ino)
 def validate_directories(self):
  for path,identity in self.dirs.items():
   s=path.lstat()
   if not stat.S_ISDIR(s.st_mode) or getattr(s,'st_file_attributes',0)&1024 or identity!=(s.st_dev,s.st_ino):
    raise IntegrityError('Source directory identity changed during capture')
 def capture(self,relative,expected_size=None,expected_sha=None):
  p=self.root/safe_relative(relative);self._directory(p.parent);before=p.lstat()
  if not stat.S_ISREG(before.st_mode) or getattr(before,'st_file_attributes',0)&1024:raise IntegrityError('Nonregular/reparse source file')
  if expected_size is not None and before.st_size!=expected_size:raise IntegrityError('Size changed after census')
  with p.open('rb') as f:
   opened=os.fstat(f.fileno())
   if (opened.st_dev,opened.st_ino)!=(before.st_dev,before.st_ino):raise IntegrityError('Source file identity changed at open')
   data=f.read();after=os.fstat(f.fileno())
  if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns) or len(data)!=after.st_size:raise IntegrityError('Source changed during read')
  h=digest(data)
  if expected_sha is not None and h!=expected_sha:raise IntegrityError('Expected hash mismatch')
  if h not in self.known:
   self.conn.execute('INSERT INTO blobs VALUES (?,?,?)',(h,len(data),data));self.known[h]=len(data)
  elif self.known[h]!=len(data):raise IntegrityError('Content address length collision')
  return {'relative':relative,'sha256':h,'bytes':len(data),'mode':stat.S_IMODE(before.st_mode),'mtime_ns_at_capture':before.st_mtime_ns}
