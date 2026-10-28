"""Bounded concurrent file reads; only the caller writes the SQLite snapshot.
Concurrency applies solely to copying source bytes, never to experimental jobs.
"""
import os,stat
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from snapshot_store_v1 import IntegrityError,safe_relative,digest
from snapshot_reader_v2 import SourceReader

def read_one(root,row,expected_sha):
 relative=row['path'];p=root/safe_relative(relative);before=p.lstat()
 if not stat.S_ISREG(before.st_mode) or getattr(before,'st_file_attributes',0)&1024:raise IntegrityError('Nonregular/reparse file')
 if before.st_size!=row['bytes']:raise IntegrityError('Size drift')
 with p.open('rb') as f:
  opened=os.fstat(f.fileno())
  if (opened.st_dev,opened.st_ino)!=(before.st_dev,before.st_ino):raise IntegrityError('File identity changed')
  data=f.read();after=os.fstat(f.fileno())
 if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns) or len(data)!=after.st_size:raise IntegrityError('File changed during read')
 h=digest(data)
 if expected_sha is not None and h!=expected_sha:raise IntegrityError('Expected hash mismatch')
 return {'relative':relative,'sha256':h,'bytes':len(data),'mode':stat.S_IMODE(before.st_mode),'mtime_ns_at_capture':before.st_mtime_ns},data

def capture_many(root,conn,files,hashes,stop,progress,workers=8):
 root=Path(root).resolve();reader=SourceReader(root,conn)
 # Validate directories before read workers start. Revalidate every identity at completion.
 for parent in sorted({(root/safe_relative(r['path'])).parent for r in files},key=str):reader._directory(parent)
 rows=[]
 with ThreadPoolExecutor(max_workers=workers) as pool:
  for offset in range(0,len(files),64):
   stop();chunk=files[offset:offset+64]
   futures=[pool.submit(read_one,root,row,hashes.get(row['path'])) for row in chunk]
   for future in futures:
    row,data=future.result();h=row['sha256']
    if h not in reader.known:conn.execute('INSERT INTO blobs VALUES (?,?,?)',(h,len(data),data));reader.known[h]=len(data)
    elif reader.known[h]!=len(data):raise IntegrityError('Digest size mismatch')
    rows.append(row)
   progress(len(rows),len(files))
 reader.validate_directories();return rows
