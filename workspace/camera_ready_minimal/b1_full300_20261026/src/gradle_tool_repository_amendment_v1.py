"""Post-observed adapter amendment: PIT1.3 root buildscript repository, offline.
No production build/source rewrite, generation change, dependency/version override.
"""
import json
from pathlib import Path
import gradle_native_recipe_v7 as base
from gradle_native_recipe_v7 import VERSIONS,groovy,main_audit_script,validate_config
from maven_adapter_v1 import sha,dump

def measurement_script(config,phase_dir):
 text=base.measurement_script(config,phase_dir)
 if config['Gradle_version']=='2.13':
  needle='gradle.beforeProject { p ->\n'
  assert text.count(needle)==1
  text=text.replace(needle,needle+'''    // Post-outcome amendment. PIT1.3 obtains its engine via root buildscript repositories.
    // Offline only; all resolved artifacts and main closures must still pass pin guards.
    if (p == p.rootProject && p.buildscript.repositories.isEmpty()) {
        p.buildscript.repositories.mavenCentral()
    }
''')
 return text

def write_recipe(config,out):
 c=validate_config(config);out=Path(out).resolve()
 base.require(out.is_relative_to((base.R/'validation').resolve()) and not out.exists(),'New fixture output only')
 out.mkdir(parents=True)
 for phase,fn in [('main_audit',main_audit_script),('measure',measurement_script)]:
  folder=out/phase;folder.mkdir();(folder/'evidence').mkdir()
  (folder/'init.gradle').write_text(fn(c,folder),encoding='utf-8',newline='\n')
 dump(out/'recipe.json',{'base_recipe':sha(base.__file__),'amendment_recipe':sha(__file__),'config':c,'post_outcome':True,'benchmark_admitted':False,'phases':{n:sha(out/n/'init.gradle') for n in ['main_audit','measure']}})
