"""Restore the exact previously pinned PDF compiler in the isolated workspace."""
import hashlib
import json
import sys
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
import audit
EXPECTED = '99ffcfdbf1ebf8bdda9e791942e3d06aedb12463fddc33f07de6f5211c8bf08d'
URL = ('https://github.com/tectonic-typesetting/tectonic/releases/download/'
       'tectonic%400.17.0/tectonic-0.17.0-x86_64-pc-windows-msvc.zip')
TOOLS = BASE / 'tools'
DEST = TOOLS / 'tectonic-0.17.0-x86_64-pc-windows-msvc'
ARCHIVE = TOOLS / 'tectonic-0.17.0-x86_64-pc-windows-msvc.zip'
MANIFEST = TOOLS / 'tectonic_restore_manifest_v1.json'
def digest(data):
    return hashlib.sha256(data).hexdigest()
def main():
    TOOLS.mkdir(exist_ok=True)
    assert not ARCHIVE.exists() and not DEST.exists() and not MANIFEST.exists(), 'Never overwrite a prior download or restoration.'
    audit.log('TOOL_RESTORE_START', source_url=URL, expected_binary_sha256=EXPECTED,
              destination=str(DEST.relative_to(BASE)), script_sha256=audit.sha(__file__))
    request = urllib.request.Request(URL, headers={'User-Agent': 'FISAT-camera-ready-tool-restore'})
    with urllib.request.urlopen(request, timeout=60) as response:
        final_url = response.url
        payload = response.read()
    with ARCHIVE.open('xb') as f:
        f.write(payload)
    audit.log('NEW_FILE_REGISTERED', path=ARCHIVE.relative_to(BASE).as_posix(),
              sha256=digest(payload), bytes=len(payload), change_type='Official release tool archive; no original overwritten')
    with zipfile.ZipFile(ARCHIVE) as z:
        names = z.namelist()
        executables = [n for n in names if Path(n).name == 'tectonic.exe']
        assert len(executables) == 1, names
        binary = z.read(executables[0])
    assert digest(binary) == EXPECTED, 'Official compiler differs from previous pinned SHA; do not use.'
    DEST.mkdir()
    executable = DEST / 'tectonic.exe'
    with executable.open('xb') as f:
        f.write(binary)
    assert audit.sha(executable) == EXPECTED
    audit.log('NEW_FILE_REGISTERED', path=executable.relative_to(BASE).as_posix(),
              sha256=EXPECTED, bytes=len(binary), change_type='Exact pinned compiler restored; no original overwritten')
    result = dict(status='RESTORED_EXACT_PIN', time_utc=datetime.now(timezone.utc).isoformat(),
                  source_url=URL, resolved_download_url=final_url, archive_sha256=digest(payload),
                  archive_bytes=len(payload), zip_members=names, executable=str(executable),
                  executable_bytes=len(binary), executable_sha256=EXPECTED,
                  previous_external_path='D:/FISAT_B1/tools/latex/tectonic-0.17.0-x86_64-pc-windows-msvc/tectonic.exe',
                  previous_external_file_absent=True, original_files_edited=False)
    with MANIFEST.open('x', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
        f.write(chr(10))
    audit.log('NEW_FILE_REGISTERED', path=MANIFEST.relative_to(BASE).as_posix(),
              sha256=audit.sha(MANIFEST), bytes=MANIFEST.stat().st_size,
              change_type='Compiler provenance and exact pin verification')
    audit.log('TOOL_RESTORE_COMPLETE', manifest=MANIFEST.relative_to(BASE).as_posix(),
              manifest_sha256=audit.sha(MANIFEST), executable=str(executable), executable_sha256=EXPECTED)
    print(json.dumps(result, ensure_ascii=False, indent=2))
if __name__ == '__main__':
    main()
