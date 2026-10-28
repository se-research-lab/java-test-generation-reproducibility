import shutil,sys
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));import audit
p=BASE/'BAO_CAO_CHAN_DOAN_COMPATIBILITY_E1.md';backup=BASE/'backup/report_editorial_v1/BAO_CAO_CHAN_DOAN_COMPATIBILITY_E1.md';backup.parent.mkdir(parents=True,exist_ok=False)
h=audit.sha(p);shutil.copy2(p,backup);assert audit.sha(backup)==h
p.write_text((BASE/'validation/readable_diagnostic_report_text.md').read_text(encoding='utf-8'),encoding='utf-8')
audit.log('FILE_REVISION',path=p.relative_to(BASE).as_posix(),before_sha256=h,after_sha256=audit.sha(p),backup=backup.relative_to(BASE).as_posix(),reason='Improve Vietnamese readability; reflect completed rather than conditional diagnostic findings; numbers/raw inputs unchanged')
print('REPORT READABILITY UPDATED; RAW DATA UNCHANGED')
