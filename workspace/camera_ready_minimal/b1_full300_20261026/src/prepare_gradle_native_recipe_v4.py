"""Add resolved tool/dependency evidence to the unadmitted Gradle recipe."""
import sys
from maven_adapter_v1 import R,sha,dump
B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
source=R/'src/gradle_native_recipe_v3.py';target=R/'src/gradle_native_recipe_v4.py'
text=source.read_text(encoding='utf-8').replace('gradle_native_recipe_v3','gradle_native_recipe_v4')
marker="    def pitTask = p.tasks.getByName('pitest')"
addition='''    if (p.tasks.findByName('b1WriteClasspaths') != null) throw new GradleException('Owned dependency audit task collision')
    def dependencyAudit = p.tasks.create('b1WriteClasspaths')
    dependencyAudit.dependsOn(p.tasks.getByName('classes'))
    dependencyAudit.outputs.upToDateWhen { false }
    dependencyAudit.doLast {
        def collections = [main_runtime: ss.main.runtimeClasspath, main_compile: ss.main.compileClasspath, test_compile: ss.test.compileClasspath, test_runtime: ss.test.runtimeClasspath, pit_engine: p.configurations.getByName('pitest'), jacoco_agent: p.configurations.getByName('jacocoAgent'), jacoco_ant: p.configurations.getByName('jacocoAnt')]
        def evidence = [:]
        collections.each { key, collection ->
            evidence[key] = collection.files.toList().collect { File file ->
                [path: file.canonicalPath, exists: file.exists(), kind: file.isDirectory() ? 'directory' : (file.isFile() ? 'file' : 'missing'), bytes: file.isFile() ? file.length() : null, sha256: file.isFile() ? b1Sha(file) : null]
            }
        }
        b1Write('b1_measurement_dependency_audit.json', JsonOutput.prettyPrint(JsonOutput.toJson(evidence)))
    }
'''
assert marker in text;text=text.replace(marker,addition+marker)
text=text.replace("checks=[];artifacts=[]", "checks=[];artifacts=[]\n audit_text=measurement_script(config,base/'in_memory/measure')\n require('b1_measurement_dependency_audit.json' in audit_text and 'pit_engine:' in audit_text and 'jacoco_agent:' in audit_text and 'jacoco_ant:' in audit_text,'Effective dependency/tool evidence missing')\n checks.append('measurement phase emits resolved engine/agent/test/main classpaths with hashes; no status-derived selection')")
compile(text,str(target),'exec')
with target.open('x',encoding='utf-8') as f:f.write(text)
dump(R/'audit/gradle_recipe_v4_changes.json',{'old_source_sha256':sha(source),'new_source_sha256':sha(target),'changes':['add a separate resolved dependency/tool evidence task for the measurement phase','preserve main classpath order and compare compile closure before/after test integration','leave exact focal target, original resources/gate, native provider/selector and task isolation unchanged'],'new_processes':0,'runtime_qualified':False})
audit.log('B1_GRADLE_RECIPE_V4_PREPARED',prior_source_sha256=sha(source),new_source_sha256=sha(target),new_experiment_calls=0);print('Prepared pure recipe v4; effective-engine evidence still requires runtime')
