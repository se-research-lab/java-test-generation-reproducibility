"""Extend the read-only preview to the final two-class namespace only."""
import ast
import difflib
import json
import subprocess
import sys
from pathlib import Path
import psutil
from maven_adapter_v1 import R, sha, dump

A = R / 'completion_amendment_v1'
O = A / 'preview_v4'


def main():
    old = R / 'src/serve_completion_preview_v3.py'
    new = R / 'src/serve_completion_preview_v4.py'
    original = old.read_text(encoding='utf-8')
    text = original
    before = "+list((R/'jobs').glob('*_completion_pom_resume_after173_v1'))"
    assert text.count(before) == 1
    text = text.replace(before, before + "+list((R/'jobs').glob('*_completion_pom_resume_final2_v1'))")
    before = "'maven_pom_resume_after173_v1','gradle_pit_run_v2'"
    assert text.count(before) == 1
    text = text.replace(before, "'maven_pom_resume_after173_v1','maven_pom_resume_final2_v1','gradle_pit_run_v2'")
    text = text.replace('resume211/220/269/275/294; 25 checkpoint giữ nguyên',
                        'resume275/294; 28 kết quả giai đoạn giữ nguyên; timeout269 không retry')
    ast.parse(text)
    with new.open('x', encoding='utf-8') as f:
        f.write(text)
    O.mkdir(exist_ok=False)
    (O / 'display_only.diff').write_text(''.join(difflib.unified_diff(original.splitlines(True),
        text.splitlines(True), fromfile=old.name, tofile=new.name)), encoding='utf-8')
    owner = json.loads((A / 'preview_v3/owner.json').read_text(encoding='utf-8'))
    proc = psutil.Process(owner['pid'])
    assert proc.create_time() == owner['create_time']
    assert any(x.endswith('serve_completion_preview_v3.py') for x in proc.cmdline())
    assert all(x.name().lower() == 'conhost.exe' for x in proc.children(recursive=True))
    proc.terminate()
    proc.wait(15)
    with (O / 'stdout.txt').open('xb') as so, (O / 'stderr.txt').open('xb') as se:
        child = subprocess.Popen([sys.executable, '-B', '-X', 'utf8', str(new)], cwd=R,
                                 stdout=so, stderr=se, stdin=subprocess.DEVNULL,
                                 creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP)
        dump(O / 'owner.json', {'pid': child.pid, 'create_time': psutil.Process(child.pid).create_time(),
                                'script_sha256': sha(new), 'url': 'http://127.0.0.1:8767/',
                                'read_only': True, 'benchmark_process_terminated': False})
    print('Read-only preview includes final2 namespace; experiment core unchanged')


if __name__ == '__main__':
    main()
