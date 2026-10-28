"""Bounded parallel full-byte SHA256 checks; no stat cache and no mutations."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from maven_adapter_v1 import GuardAbort,sha

def verify_pins(records):
 rows=list(records.items())
 def check(row):
  path,expected=row
  if sha(path)!=expected:raise GuardAbort('Code/input hash drift: '+str(path))
  return 1
 with ThreadPoolExecutor(max_workers=8,thread_name_prefix='b1-read-sha256') as pool:
  return sum(pool.map(check,rows))
