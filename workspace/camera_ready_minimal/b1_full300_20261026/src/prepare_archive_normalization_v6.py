"""Pure audit performance correction: bound archive keys lexically before file hashing."""
import ast,difflib
from maven_adapter_v1 import R,sha,dump
A=R/'completion_amendment_v1'
def main():
 out=A/'archive_normalization_v6_preparation';out.mkdir(exist_ok=False)
 old=R/'src/audit_completion_results_v5.py';new=R/'src/audit_completion_results_v6.py';t=old.read_text()
 before="""  item=folder/row['relative'] if 'relative' in row else B/row['path']
  rel=item.resolve().relative_to(folder.resolve()).as_posix()
  assert rel not in entries,'Duplicate archive key'
  entries[rel]=row"""
 after="""  if 'relative' in row:rel=row['relative']
  else:
   prefix=folder.relative_to(B).as_posix()+'/'
   assert row['path'].startswith(prefix),'Archive path outside selected E49 job'
   rel=row['path'][len(prefix):]
  assert rel and '\\\\' not in rel and ':' not in rel and not rel.startswith('/') and all(s not in {'','..','.'} for s in rel.split('/')),'Unsafe archive key'
  assert rel not in entries,'Duplicate archive key'
  entries[rel]=row"""
 assert before in t;t=t.replace(before,after)
 # These are pure string basenames, avoiding repeated Windows path construction.
 t=t.replace("  parts=Path(rel).parts", "  name=rel.rsplit('/',1)[-1];suffix='.'+name.rsplit('.',1)[-1] if '.' in name else ''")
 t=t.replace('Path(rel).name','name').replace('Path(rel).suffix','suffix')
 ast.parse(t)
 with new.open('x',encoding='utf-8') as f:f.write(t)
 (out/'audit.diff').write_text(''.join(difflib.unified_diff(old.read_text().splitlines(True),t.splitlines(True),fromfile=old.name,tofile=new.name)),encoding='utf-8')
 oldf=R/'src/finalize_completion_when_ready_v3.py';newf=R/'src/finalize_completion_when_ready_v4.py';f=oldf.read_text().replace("O=A/'automatic_finalization_v3'","O=A/'automatic_finalization_v4'").replace('audit_completion_results_v5.py','audit_completion_results_v6.py');ast.parse(f)
 with newf.open('x',encoding='utf-8') as stream:stream.write(f)
 dump(out/'receipt.json',{'old_sha256':sha(old),'new_sha256':sha(new),'new_finalizer_sha256':sha(newf),'score_and_selection_rules_changed':False,'file_bytes_still_hashed_against_archive':True,'original_evidence_unchanged':True,'purpose':'remove repeated filesystem resolve calls for every manifest entry; retain containment grammar and hash checks','new_experiment_calls':0})
 print('Prepared equivalent bounded archive normalization; report scoring unchanged')
if __name__=='__main__':main()
