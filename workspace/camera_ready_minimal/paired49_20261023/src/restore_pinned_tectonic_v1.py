"""Restore byte-identical pinned Tectonic from its official release asset."""
import hashlib, json, subprocess, sys, urllib.request, zipfile
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import audit
BASE=Path(__file__).resolve().parent.parent
DEST=BASE/'tools/tectonic-0.17.0-x86_64-pc-windows-msvc'
URL='https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic%400.17.0/tectonic-0.17.0-x86_64-pc-windows-msvc.zip'
ZIP_SHA='f61ce51f0b0ade1015b7de7ef368541c5424e9756ecbd0d7af97d6d48030845f'
EXE_SHA='99ffcfdbf1ebf8bdda9e791942e3d06aedb12463fddc33f07de6f5211c8bf08d'
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    DEST.mkdir(parents=True, exist_ok=False)
    audit.log('TOOL_RESTORATION_START',source=URL,dest=str(DEST),expected_archive_sha256=ZIP_SHA,expected_binary_sha256=EXE_SHA,restoration_only=True,no_template_or_latex_version_change=True,script_sha256=sha(__file__))
    archive=DEST/'tectonic-0.17.0-x86_64-pc-windows-msvc.zip'
    request=urllib.request.Request(URL,headers={'User-Agent':'FISAT-camera-ready-reproducibility-audit'})
    try:
        with urllib.request.urlopen(request,timeout=120) as response, archive.open('xb') as out:
            while True:
                chunk=response.read(1024*1024)
                if not chunk: break
                out.write(chunk)
        assert sha(archive)==ZIP_SHA, 'Official archive checksum mismatch; do not extract or execute'
        with zipfile.ZipFile(archive) as z:
            names=[n for n in z.namelist() if n.replace('\\','/').split('/')[-1]=='tectonic.exe']
            assert len(names)==1, names
            data=z.read(names[0])
            assert hashlib.sha256(data).hexdigest()==EXE_SHA, 'Binary differs from recorded pinned Tectonic; do not execute'
            executable=DEST/'tectonic.exe'
            with executable.open('xb') as out: out.write(data)
        version=subprocess.run([str(executable),'--version'],capture_output=True,text=True,timeout=30,check=True)
        assert 'Tectonic 0.17.0' in version.stdout or 'tectonic 0.17.0' in version.stdout, version.stdout
        result={'status':'RESTORED_EXACT_PINNED_BINARY','timestamp_utc':datetime.now(timezone.utc).isoformat(),'source':URL,'official_asset_page':'https://github.com/tectonic-typesetting/tectonic/releases/expanded_assets/tectonic%400.17.0','archive':str(archive),'archive_sha256':sha(archive),'binary':str(executable),'binary_sha256':sha(executable),'old_MANUSCRIPT_BUILD_START_binary_sha256':EXE_SHA,'version_stdout':version.stdout,'version_stderr':version.stderr,'script_sha256':sha(__file__),'template_and_paper_edits':False}
        manifest=DEST/'restoration_manifest.json'
        with manifest.open('x',encoding='utf-8') as out: json.dump(result,out,ensure_ascii=False,indent=2)
        audit.log('TOOL_RESTORATION_COMPLETE',**result,manifest=str(manifest),manifest_sha256=sha(manifest))
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except Exception as exc:
        audit.log('TOOL_RESTORATION_ABORT',dest=str(DEST),error_type=type(exc).__name__,error=str(exc))
        raise
if __name__=='__main__': main()
