"""AST impact check and mocked actual Maven-generation argv, no Java/API calls."""
import ast
import difflib
import importlib.util
import json
import os
import sys
import tempfile
import time
import types
from pathlib import Path

BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE))
import audit
STAGE=BASE/'evo_patch'
sys.path.insert(0,str(STAGE/'working/AgoneTest'))
import evosuite_profile as profile


def main():
    before=(STAGE/'backup/mavenLib.py').read_text(encoding='utf-8-sig')
    after=(STAGE/'working/AgoneTest/mavenLib.py').read_text(encoding='utf-8-sig')
    old=ast.parse(before);new=ast.parse(after)
    funcs=lambda tree:{x.name:ast.dump(x,include_attributes=False) for x in tree.body if isinstance(x,(ast.FunctionDef,ast.ClassDef))}
    a,b=funcs(old),funcs(new)
    changed=[name for name in sorted(set(a)|set(b)) if a.get(name)!=b.get(name)]
    assert changed==['run_evosuite_generation_maven'],changed
    strip=lambda t:ast.dump(ast.Module(body=[x for x in t.body if not (isinstance(x,ast.FunctionDef) and x.name in changed)
                and not (isinstance(x,ast.Import) and any(a.name=='evosuite_profile' for a in x.names))],type_ignores=[]),include_attributes=False)
    assert strip(old)==strip(new),'Unapproved top-level edit'
    for name in ['gradleLib.py','utils.py','agone_test.py','toolchains.py','errorCorrection.py']:
        assert audit.sha(STAGE/'backup'/name)==audit.sha(STAGE/'working/AgoneTest'/name),name
    legacy=['-Duse_separate_classloader=false','-Dtest_archive=false','-Dcriterion=BRANCH',
            '-Dassertions=false','-Dno_runtime_dependency=true','-Dtest_scaffolding=false','-Dsearch_budget=60']
    assert profile.maven_generation_options()==legacy
    approved={'assertions':('false','true'),'no_runtime_dependency':('true','false'),
              'test_scaffolding':('false','true'),'assertion_strategy':(None,'MUTATION')}
    props=lambda opts:dict(x[2:].split('=',1) for x in opts)
    oldprops=props(legacy);newprops=props(profile.maven_generation_options(profile.REVIEWER))
    delta={k:(oldprops.get(k),newprops.get(k)) for k in oldprops.keys()|newprops.keys() if oldprops.get(k)!=newprops.get(k)}
    assert delta==approved,delta
    try:profile.maven_generation_options('typo')
    except ValueError:pass
    else:raise AssertionError('Unknown profile accepted')
    # Compile only the target AST function. Never import old utils/API setup or launch subprocesses.
    target=next(x for x in new.body if isinstance(x,ast.FunctionDef) and x.name==changed[0])
    module=ast.Module(body=[target],type_ignores=[]);ast.fix_missing_locations(module)
    captures=[]
    with tempfile.TemporaryDirectory(prefix='argv_controls_',dir=STAGE/'fixtures') as td:
        p=Path(td);focal=p/'src/main/java/fixture/Example.java';focal.parent.mkdir(parents=True)
        focal.write_text('package fixture; public class Example {}',encoding='utf-8')
        (p/'pom.xml').write_text('<project/>');(p/'target/classes').mkdir(parents=True)
        expected=p/'src/test/java/fixture/Example_ESTest.java'
        def fake_run(argv,**kwargs):
            captures.append({'argv':argv,'cwd':kwargs['cwd'],'timeout':kwargs['timeout']})
            if '-jar' in argv:
                expected.parent.mkdir(parents=True,exist_ok=True);expected.write_text('fixture',encoding='utf-8')
            return types.SimpleNamespace(returncode=0,stdout='',stderr='')
        ns=dict(os=os,Path=Path,time=time,evosuite_profile=profile,
                java_command=lambda _: 'java8',maven_command=lambda _: 'mvn',
                maven_settings_args=lambda:[],common_maven_skip_args=lambda:[],
                toolchains=types.SimpleNamespace(evosuite_jar=lambda:'evosuite-1.2.0.jar'),
                subprocess=types.SimpleNamespace(run=fake_run,TimeoutExpired=TimeoutError),
                utils=types.SimpleNamespace(append_phase_log=lambda *a,**k:None),
                evosuite_classpath_entries=lambda items:(items,[]),
                MAVEN_TIMEOUT_SECONDS=300,EVOSUITE_TIMEOUT_SECONDS=240,
                command_output_tail=lambda _: '',timeout_output_tail=lambda _: '')
        exec(compile(module,'isolated-target','exec'),ns)
        for label in [profile.LEGACY,profile.REVIEWER]:
            assert ns['run_evosuite_generation_maven'](str(p),str(focal),'Windows',label)
            argv=captures[-1]['argv']
            expected_options=profile.maven_generation_options(label)
            assert argv[-len(expected_options):]==expected_options
            assert captures[-1]['timeout']==240
    diff=''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),
                fromfile='backup/mavenLib.py',tofile='working/AgoneTest/mavenLib.py'))
    dest=STAGE/'patches/001_generation_profile.diff'
    with dest.open('x',encoding='utf-8') as f:f.write(diff)
    report={'status':'PASS','changed_functions':changed,'approved_option_delta':delta,
            'unchanged_shared_files':5,'all_other_top_level_AST_unchanged':True,
            'legacy_generation_argv_preserved':True,'mock_invocations':captures,
            'original_experiment_code_edits':0,'runtime_integration_tested':False,
            'caller_note':'Existing process_maven_project/module still use legacy default; reviewer profile must be explicitly called by isolated E-only driver.',
            'gitnexus':'No matching indexed repo; inspected callers and AST directly',
            'source_provenance_limit':'Current source snapshot only; not proof of exact historical code version'}
    (STAGE/'reports/patch_validation.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    audit.log('PATCH_VERIFIED',reviewer='R2.1',file='evo_patch/working/AgoneTest/mavenLib.py',
              before_sha256=audit.sha(STAGE/'backup/mavenLib.py'),after_sha256=audit.sha(STAGE/'working/AgoneTest/mavenLib.py'),
              diff=str(dest.relative_to(BASE)),diff_sha256=audit.sha(dest),changed_functions=changed)
    print(json.dumps({k:v for k,v in report.items() if k!='mock_invocations'},indent=2))


if __name__=='__main__':main()
