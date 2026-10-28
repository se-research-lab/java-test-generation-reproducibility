"""PURE Gradle native-suite recipe prototype; deliberately not runtime qualified.

No Java/build/API/process launcher. Only new files below B1/validation may be
written by this version. A controller must qualify every task/plugin API before
any generated script can be used in a benchmark. Original projects stay intact.
"""
import copy,hashlib,json,re,sys,stat
from pathlib import Path,PureWindowsPath

R=Path(__file__).resolve().parents[1]
VERSIONS={'2.13':('1.3.0','1.3.1'),'5.2.1':('1.4.0','1.4.3'),'6.9.4':('1.15.0','1.15.0'),'8.14.4':('1.15.0','1.15.0')}
IDENT=re.compile(r'[A-Za-z_$][A-Za-z0-9_$]*\Z')
HEX=re.compile(r'[0-9a-f]{64}\Z')
RECIPE_STATUS='NOT_RUNTIME_QUALIFIED'

class RecipeError(ValueError):pass

def require(ok,why):
 if not ok:raise RecipeError(why)
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def groovy(value):
 require(isinstance(value,str) and not any(ord(c)<32 for c in value),'Unsafe literal control character')
 return "'"+value.replace('\\','\\\\').replace("'","\\'")+"'"
def absolute(value):
 require(isinstance(value,str) and not any(ord(c)<32 for c in value),'Invalid absolute path')
 path=PureWindowsPath(value)
 require(path.is_absolute() and re.fullmatch(r'[A-Za-z]:',path.drive) is not None,'Local absolute Windows path required')
 require('..' not in path.parts and not any(c in value for c in '%!&|<>^"'),'Unsafe or nonlocal path')
 return str(path).replace('\\','/')

def owned_path(value):
 path=Path(absolute(str(value))).resolve()
 roots=[(R/'jobs').resolve(),(R/'validation').resolve()]
 require(any(path.is_relative_to(root) and path!=root for root in roots),'Recipe path outside owned B1 sandbox')
 cursor=path
 while cursor.is_relative_to(R):
  if cursor.exists() or cursor.is_symlink():
   require(not cursor.is_symlink() and not getattr(cursor.lstat(),'st_file_attributes',0)&getattr(stat,'FILE_ATTRIBUTE_REPARSE_POINT',0x400),'Recipe reparse/junction path refused')
  if cursor==R:break
  cursor=cursor.parent
 return path.as_posix()

def relative(value):
 require(isinstance(value,str),'Module path must be text')
 if value in {'','.'}:return ''
 require(value==value.strip('/') and '\\' not in value and all(re.fullmatch(r'[A-Za-z0-9_.-]+',s) and s not in {'.','..'} for s in value.split('/')),'Unsafe module path')
 return value
def fqcn(value):
 require(isinstance(value,str) and value and all(IDENT.fullmatch(p) for p in value.split('.')),'Invalid Java FQCN')
 return value
def pin(value):
 require(isinstance(value,dict) and set(value)=={'path','sha256'},'JAR pin requires only path and sha256')
 path=absolute(value['path']);require(path.lower().endswith('.jar') and isinstance(value['sha256'],str) and HEX.fullmatch(value['sha256']),'Invalid JAR pin')
 return {'path':path,'sha256':value['sha256']}

def validate_config(config):
 c=copy.deepcopy(config)
 required={'Gradle_version','repo_root','build_root','module_selector','focal_fqcn','test_fqcn','runtime_jar','pit_plugin_classpath','source_context_sha256','add_junit4','resolved_cp_audit'}
 require(isinstance(c,dict) and set(c)==required,'Unknown/missing recipe field')
 require(c['Gradle_version'] in VERSIONS,'Wrapper version has no qualified candidate mapping')
 c['repo_root']=owned_path(c['repo_root']);c['build_root']=relative(c['build_root']);c['module_selector']=relative(c['module_selector'])
 c['focal_fqcn']=fqcn(c['focal_fqcn']);c['test_fqcn']=fqcn(c['test_fqcn'])
 require(c['test_fqcn']==c['focal_fqcn']+'_ESTest','Native test must match focal FQCN exactly')
 require(isinstance(c['source_context_sha256'],str) and HEX.fullmatch(c['source_context_sha256']),'Missing frozen metadata hash')
 c['runtime_jar']=pin(c['runtime_jar'])
 require(isinstance(c['pit_plugin_classpath'],list) and 1<=len(c['pit_plugin_classpath'])<=256,'Pinned plugin classpath required')
 c['pit_plugin_classpath']=[pin(p) for p in c['pit_plugin_classpath']]
 require(len({p['path'].casefold() for p in c['pit_plugin_classpath']})==len(c['pit_plugin_classpath']),'Duplicate plugin classpath path')
 require(type(c['add_junit4']) is bool,'JUnit flag must be explicit boolean')
 receipt=c['resolved_cp_audit']
 if c['add_junit4']:
  require(isinstance(receipt,dict) and set(receipt)=={'status','junit4_missing','evidence_sha256'},'External resolved-CP audit receipt required for JUnit addition')
  require(receipt['status']=='PASS_RESOLVED_CP_AUDIT' and receipt['junit4_missing'] is True and isinstance(receipt['evidence_sha256'],str) and HEX.fullmatch(receipt['evidence_sha256']),'JUnit addition lacks passed missing-JUnit audit')
 else:require(receipt is None,'Unexpected JUnit-addition receipt when flag is false')
 return c

def constants(c,phase_dir):
 phase_dir=Path(owned_path(phase_dir))
 selector=':'+c['module_selector'].replace('/',':') if c['module_selector'] else ':'
 build='/'.join(p for p in [c['repo_root'],c['build_root']] if p)
 module='/'.join(p for p in [build,c['module_selector']] if p)
 return '''// PROTOTYPE: NOT_RUNTIME_QUALIFIED. No benchmark admission is implied.
import groovy.json.JsonOutput
import org.gradle.api.GradleException
import org.gradle.api.tasks.testing.Test

def b1SelectedPath = @SELECTOR@
def b1ExpectedBuildRoot = new File(@BUILD@).canonicalFile
def b1ExpectedModule = new File(@MODULE@).canonicalFile
def b1EvidenceDir = new File(@EVIDENCE@).canonicalFile
def b1NativeFqcn = @TEST@
def b1FocalFqcn = @FOCAL@
if (!gradle.startParameter.offline) throw new GradleException('B1 requires explicit offline execution')
if (!b1EvidenceDir.isDirectory()) throw new GradleException('Owned empty evidence directory required')

def b1Sha = { File file ->
    def md = java.security.MessageDigest.getInstance('SHA-256')
    file.withInputStream { input ->
        byte[] buffer = new byte[65536]
        int count
        while ((count = input.read(buffer)) != -1) md.update(buffer, 0, count)
    }
    md.digest().encodeHex().toString()
}
def b1Write = { String name, String text ->
    if (!(name ==~ /[A-Za-z0-9_.-]+/)) throw new GradleException('Invalid owned evidence basename')
    File dest = new File(b1EvidenceDir, name).canonicalFile
    if (dest.parentFile != b1EvidenceDir) throw new GradleException('Evidence escapes owned directory')
    if (dest.exists()) {
        if (name != 'b1_recipe_configuration.json' || !dest.isFile() || dest.getText('UTF-8') != text) throw new GradleException('Evidence exists or sealed configuration differs')
        return // identical sealed configuration may be read by a later PIT invocation
    }
    if (!dest.createNewFile()) throw new GradleException('Exclusive evidence creation failed')
    dest.setText(text, 'UTF-8')
}
def b1Project = {
    if (gradle.rootProject.projectDir.canonicalFile != b1ExpectedBuildRoot) throw new GradleException('Wrong build root')
    def selected = gradle.rootProject.project(b1SelectedPath)
    if (selected.projectDir.canonicalFile != b1ExpectedModule || !selected.plugins.hasPlugin('java')) throw new GradleException('Wrong selected Java module')
    selected
}
'''.replace('@SELECTOR@',groovy(selector)).replace('@BUILD@',groovy(build)).replace('@MODULE@',groovy(module)).replace('@EVIDENCE@',groovy(absolute(str(phase_dir/'evidence')))).replace('@TEST@',groovy(c['test_fqcn'])).replace('@FOCAL@',groovy(c['focal_fqcn']))

def main_audit_script(config,phase_dir):
 c=validate_config(config)
 return constants(c,Path(phase_dir))+'''
// PRE-GENERATION ONLY: no JUnit/runtime/PIT/JaCoCo additions.
gradle.projectsEvaluated {
    def p = b1Project()
    if (p.tasks.findByName('b1WriteClasspaths') != null) throw new GradleException('Owned task collision')
    def write = p.tasks.create('b1WriteClasspaths')
    write.dependsOn(p.tasks.getByName('classes'))
    write.outputs.upToDateWhen { false }
    write.doLast {
        def ss = p.sourceSets
        def collections = [main_runtime: ss.main.runtimeClasspath, test_compile: ss.test.compileClasspath, main_compile: ss.main.compileClasspath]
        def audit = [:]
        collections.each { key, collection ->
            def files = collection.files.toList() // retain the Gradle runtime classpath order
            b1Write('b1_' + key + '_classpath.txt', files.collect { it.canonicalPath }.join(File.pathSeparator))
            audit[key] = files.collect { File file ->
                [path: file.canonicalPath, exists: file.exists(), kind: file.isDirectory() ? 'directory' : (file.isFile() ? 'file' : 'missing'), bytes: file.isFile() ? file.length() : null, sha256: file.isFile() ? b1Sha(file) : null]
            }
        }
        def production = [:]
        ss.main.output.files.findAll { it.isDirectory() }.each { File root ->
            root.eachFileRecurse { File file ->
                if (file.isFile() && file.name.endsWith('.class')) {
                    def key = root.canonicalPath + '::' + root.toPath().relativize(file.toPath()).toString().replace('\\\\','/')
                    production[key] = b1Sha(file)
                }
            }
        }
        b1Write('b1_compile_audit.json', JsonOutput.prettyPrint(JsonOutput.toJson(audit)))
        b1Write('b1_production_classes.json', JsonOutput.prettyPrint(JsonOutput.toJson(production)))
    }
}
gradle.taskGraph.whenReady { graph ->
    if (graph.allTasks.any { it instanceof Test || it.name in ['check', 'asyncTests', 'testsWithoutAssertion'] }) throw new GradleException('Main audit must not execute original test/check tasks')
}
'''

def plugin_loader(c):
 pins='['+', '.join('[path: '+groovy(p['path'])+', sha256: '+groovy(p['sha256'])+']' for p in c['pit_plugin_classpath'])+']'
 return '''// PIT classes are loaded only in MEASURE phase, from explicitly pinned local JARs.
initscript {
    def pins = @PINS@
    pins.each { pin ->
        File jar = new File(pin.path)
        if (!jar.isFile()) throw new GradleException('Pinned plugin JAR missing')
        def md = java.security.MessageDigest.getInstance('SHA-256')
        jar.withInputStream { input ->
            byte[] buffer = new byte[65536]
            int count
            while ((count = input.read(buffer)) != -1) md.update(buffer, 0, count)
        }
        if (md.digest().encodeHex().toString() != pin.sha256) throw new GradleException('Pinned plugin JAR hash drift')
    }
    dependencies { classpath files(pins.collect { it.path }) }
}
'''.replace('@PINS@',pins)

def measurement_script(config,phase_dir):
 c=validate_config(config);old=c['Gradle_version']=='2.13';modern=c['Gradle_version']=='8.14.4';lazy=VERSIONS[c['Gradle_version']][0]=='1.15.0'
 testconfig='testCompile' if old else 'testImplementation'
 runtime=c['runtime_jar'];junit="        p.dependencies.add("+groovy(testconfig)+", 'junit:junit:4.13.2')\n" if c['add_junit4'] else ''
 testdirs='nativeTest.testClassesDir = ss.test.output.classesDir' if old else 'nativeTest.testClassesDirs = ss.test.output.classesDirs'
 xml="nativeTest.reports.junitXml.required.set(true)\n    nativeTest.reports.junitXml.outputLocation.set(new File(b1EvidenceDir, 'surefire-native'))" if modern else "nativeTest.reports.junitXml.enabled = true\n    nativeTest.reports.junitXml.destination = new File(b1EvidenceDir, 'surefire-native')"
 classes="report.classDirectories = p.files(ss.main.output.classesDir)\n    report.sourceDirectories = p.files(ss.main.allSource.srcDirs)" if old else "report.classDirectories.setFrom(ss.main.output.classesDirs)\n    report.sourceDirectories.setFrom(ss.main.allSource.srcDirs)"
 reports="report.reports.csv.required.set(true)\n    report.reports.csv.outputLocation.set(new File(b1EvidenceDir, 'jacoco-native.csv'))\n    report.reports.xml.required.set(false)\n    report.reports.html.required.set(false)" if modern else "report.reports.csv.enabled = true\n    report.reports.csv.destination = new File(b1EvidenceDir, 'jacoco-native.csv')\n    report.reports.xml.enabled = false\n    report.reports.html.enabled = false"
 engine=VERSIONS[c['Gradle_version']][1]
 if lazy:
  pit="""pit.pitestVersion.set(@ENGINE@)
    pit.targetTests.set([b1NativeFqcn] as Set)
    pit.targetClasses.set([b1FocalFqcn] as Set)
    pit.threads.set(4)
    pit.outputFormats.set(['CSV'] as Set)
    pit.failWhenNoMutations.set(false)
    pit.reportDir.set(new File(b1EvidenceDir, 'pit-native'))
    def provider = pit.testPlugin.orNull"""
 else:
  pit="""pit.pitestVersion = @ENGINE@
    pit.targetTests = [b1NativeFqcn]
    pit.targetClasses = [b1FocalFqcn]
    pit.threads = 4
    pit.outputFormats = ['CSV']
    pit.failWhenNoMutations = false
    pit.reportDir = new File(b1EvidenceDir, 'pit-native')
    def provider = pit.testPlugin"""
 pit=pit.replace('@ENGINE@',groovy(engine))
 body='''
// BEFORE evaluation: apply typed PIT and JaCoCo only to the exact selected Java module.
// Plugin APIs remain candidates until wrapper-specific runtime fixtures pass.
gradle.beforeProject { p ->
    if (p.path == b1SelectedPath) {
        p.plugins.withId('java') {
            if (!p.plugins.hasPlugin('jacoco')) p.plugins.apply('jacoco')
            p.plugins.apply(info.solidsoft.gradle.pitest.PitestPlugin)
        }
    }
}
gradle.projectsEvaluated {
    def p = b1Project()
    ['b1NativeTest', 'b1NativeJacocoReport'].each { name ->
        if (p.tasks.findByName(name) != null) throw new GradleException('Owned task collision')
    }
    File runtimeJar = new File(@RUNTIME@)
    if (!runtimeJar.isFile() || b1Sha(runtimeJar) != @RUNTIMEHASH@) throw new GradleException('Pinned native runtime drift')
    p.dependencies.add(@TESTCONFIG@, p.files(runtimeJar))
@JUNIT@    def ss = p.sourceSets
    def nativeTest = p.tasks.create('b1NativeTest', Test)
    nativeTest.dependsOn(p.tasks.getByName('testClasses'))
    @TESTDIRS@
    nativeTest.classpath = ss.test.runtimeClasspath
    nativeTest.useJUnit()
    nativeTest.setIncludes([b1NativeFqcn.replace('.', '/') + '.class'] as Set)
    // Copy declarative resources and process gate; isolate only native discovery.
    def originalTest = p.tasks.findByName('test')
    if (originalTest == null || !(originalTest instanceof Test)) throw new GradleException('Original test model required for resource/gate audit')
    nativeTest.minHeapSize = originalTest.minHeapSize
    nativeTest.maxHeapSize = originalTest.maxHeapSize
    nativeTest.setJvmArgs(new ArrayList(originalTest.jvmArgs ?: []))
    nativeTest.systemProperties.putAll(originalTest.systemProperties)
    nativeTest.enableAssertions = originalTest.enableAssertions
    nativeTest.maxParallelForks = originalTest.maxParallelForks
    nativeTest.forkEvery = originalTest.forkEvery
    nativeTest.workingDir = originalTest.workingDir
    nativeTest.ignoreFailures = originalTest.ignoreFailures
    nativeTest.enabled = nativeTest.enabled && originalTest.enabled
    nativeTest.outputs.upToDateWhen { false }
    @XML@
    // Existing withType<Test> hooks remain; ordinary test tasks are untouched.
    def jacoco = p.extensions.getByName('jacoco')
    jacoco.toolVersion = '0.8.6' // legacy helper candidate; actual agent must be audited.
    def agent = nativeTest.extensions.getByType(org.gradle.testing.jacoco.plugins.JacocoTaskExtension)
    agent.destinationFile = new File(b1EvidenceDir, 'native.exec')
    def report = p.tasks.create('b1NativeJacocoReport', org.gradle.testing.jacoco.tasks.JacocoReport)
    report.dependsOn(nativeTest)
    report.executionData(new File(b1EvidenceDir, 'native.exec'))
    @CLASSES@
    @REPORTS@
    report.outputs.upToDateWhen { false }
    // Preserve the legacy Gradle exact-focal measurement target; no nested expansion.
    def pit = p.extensions.getByName('pitest')
    @PIT@
    if (provider != null && provider.toString().toLowerCase().contains('testng')) throw new GradleException('Native JUnit provider requires separate qualification; refuse TestNG')
    // No mutators override: retain the explicitly pinned engine defaults.
    if (p.tasks.findByName('b1WriteClasspaths') != null) throw new GradleException('Owned dependency audit task collision')
    def dependencyAudit = p.tasks.create('b1WriteClasspaths')
    dependencyAudit.dependsOn(p.tasks.getByName('classes'))
    dependencyAudit.outputs.upToDateWhen { false }
    dependencyAudit.doLast {
        def collections = [main_runtime: ss.main.runtimeClasspath, main_compile: ss.main.compileClasspath, test_compile: ss.test.compileClasspath, test_runtime: ss.test.runtimeClasspath, pit_engine: p.tasks.getByName('pitest').launchClasspath, jacoco_agent: p.configurations.getByName('jacocoAgent'), jacoco_ant: p.configurations.getByName('jacocoAnt')]
        def evidence = [:]
        collections.each { key, collection ->
            evidence[key] = collection.files.toList().collect { File file ->
                [path: file.canonicalPath, exists: file.exists(), kind: file.isDirectory() ? 'directory' : (file.isFile() ? 'file' : 'missing'), bytes: file.isFile() ? file.length() : null, sha256: file.isFile() ? b1Sha(file) : null]
            }
        }
        b1Write('b1_measurement_dependency_audit.json', JsonOutput.prettyPrint(JsonOutput.toJson(evidence)))
    }
    def pitTask = p.tasks.getByName('pitest')
    pitTask.outputs.upToDateWhen { false }
    b1Write('b1_recipe_configuration.json', JsonOutput.prettyPrint(JsonOutput.toJson([
        status: 'CONFIGURATION_ONLY_NOT_EXECUTION_EVIDENCE', notTaskExecutionEvidence: true, selectedProject: p.path,
        nativeTest: nativeTest.path, report: report.path, pitTask: pitTask.path,
        providerClaim: provider == null ? null : provider.toString(),
        engineVersionCandidate: @ENGINE@, nativeTestFramework: nativeTest.options.class.name,
        ordinaryTasksEdited: false, addJUnit4FromExternalAudit: @JUNITBOOL@,
        nativeEnabled: nativeTest.enabled, legacyExactFocalTarget: true, originalIgnoreFailures: originalTest.ignoreFailures, nativeIgnoreFailures: nativeTest.ignoreFailures, originalMaxHeap: originalTest.maxHeapSize, nativeMaxHeap: nativeTest.maxHeapSize
    ])))
}
gradle.taskGraph.whenReady { graph ->
    def wanted = b1SelectedPath == ':' ? ':b1NativeTest' : b1SelectedPath + ':b1NativeTest'
    if (graph.allTasks.any { (it instanceof Test && it.path != wanted) || it.name in ['test', 'check', 'asyncTests', 'testsWithoutAssertion'] }) throw new GradleException('Native phase forbids original test/check/async task execution')
}
'''
 values={'RUNTIME':groovy(runtime['path']),'RUNTIMEHASH':groovy(runtime['sha256']),'TESTCONFIG':groovy(testconfig),'JUNIT':junit,'TESTDIRS':testdirs,'XML':xml,'CLASSES':classes,'REPORTS':reports,'PIT':pit,'ENGINE':groovy(engine),'JUNITBOOL':str(c['add_junit4']).lower()}
 for key,value in values.items():body=body.replace('@'+key+'@',value)
 # initscript is evaluated in its own first pass; its GradleException is fully qualified.
 return plugin_loader(c).replace('new GradleException(','new org.gradle.api.GradleException(')+constants(c,Path(phase_dir))+body

def write_recipe(config,out):
 """Only prototype evidence under a new validation directory is writable here."""
 c=validate_config(config);out=Path(out).resolve();allowed=(R/'validation').resolve()
 require(out.is_relative_to(allowed) and out!=allowed and not out.exists(),'Prototype output must be a new owned validation directory')
 for parent in [out.parent,*out.parents]:
  if parent.exists():require(not parent.is_symlink(),'Symlink output parent forbidden')
 main=out/'main_audit';measure=out/'measure'
 scripts={'main_audit':main_audit_script(c,main),'measure':measurement_script(c,measure)}
 require(all('@' not in text for text in scripts.values()),'Unexpanded template marker')
 out.mkdir(parents=True,exist_ok=False)
 for phase,text in scripts.items():
  folder=out/phase;folder.mkdir();(folder/'evidence').mkdir()
  with (folder/'init.gradle').open('x',encoding='utf-8',newline='\n') as f:f.write(text)
 plugin,engine=VERSIONS[c['Gradle_version']]
 manifest={'status':RECIPE_STATUS,'scope':'pure prototype only; validation files are not benchmark admission','config':c,'plugin_version_candidate':plugin,'engine_version_candidate':engine,'effective_versions_verified':False,'nested_target_amendment':'NONE: preserve legacy exact focal FQCN; do not expand the measured mutant domain','mutators':'no override; pinned engine defaults require qualification','phases':{phase:{'init_relative':phase+'/init.gradle','sha256':sha(out/phase/'init.gradle'),'evidence_relative':phase+'/evidence'} for phase in scripts},'new_experiment_calls':0,'GPT_API_calls':0,'benchmark_admitted':False,'runtime_qualification_required':['per-wrapper plugin/task API and Groovy DSL','exact native JUnit4 discovery and positive testcase XML','agent/runtime/dependency and production bytecode guards','PIT effective engine/provider and focal/nested mutant inventory','taskgraph without ordinary test/check/async execution','stage gate and timeout mapping in an independently sealed controller']}
 with (out/'recipe.json').open('x',encoding='utf-8') as f:json.dump(manifest,f,ensure_ascii=False,indent=2)
 return manifest

def validate_prototype():
 """Pure meaningful guard checks; outputs can never be interpreted as runtime PASS."""
 base=R/'validation/gradle_native_recipe_v6';require(not base.exists(),'Validation output exists; preserve prior evidence')
 root=base/'fixture_repo';context=R/'inputs/gradle40_context_v2/manifest.json'
 config={'Gradle_version':'2.13','repo_root':str(root),'build_root':'.','module_selector':'.','focal_fqcn':'fixture.BranchFixture','test_fqcn':'fixture.BranchFixture_ESTest','runtime_jar':{'path':str(R.parents[1]/'scripts_v2/evosuite-standalone-runtime-1.2.0.jar'),'sha256':sha(R.parents[1]/'scripts_v2/evosuite-standalone-runtime-1.2.0.jar')},'pit_plugin_classpath':[{'path':'D:/prototype-only/plugin.jar','sha256':'0'*64}],'source_context_sha256':sha(context),'add_junit4':False,'resolved_cp_audit':None}
 checks=[];artifacts=[]
 audit_text=measurement_script(config,base/'in_memory/measure')
 require('b1_measurement_dependency_audit.json' in audit_text and 'pit_engine:' in audit_text and 'jacoco_agent:' in audit_text and 'jacoco_ant:' in audit_text,'Effective dependency/tool evidence missing')
 checks.append('measurement phase emits resolved engine/agent/test/main classpaths with hashes; no status-derived selection')
 require('originalTest.ignoreFailures' in measurement_script(config,base/'in_memory/measure') and 'originalTest.maxHeapSize' in measurement_script(config,base/'in_memory/measure'),'Original task resources/gate not preserved')
 checks.append('native task copies original declarative resources/gate; provider/selector/dependsOn remain separate')
 require('collection.files.toList().sort' not in main_audit_script(config,base/'in_memory/main'),'Classpath order was sorted')
 checks.append('runtime classpath preserves native Gradle iteration order')
 for invalid in ['D:/foreign/repo',str(R/'inputs')]:
  bad=copy.deepcopy(config);bad['repo_root']=invalid
  try:validate_config(bad)
  except RecipeError:pass
  else:raise AssertionError('Unowned source accepted')
 checks.append('source root outside jobs/validation rejected')
 rendered=measurement_script(config,base/'in_memory/measure')
 require("name != 'b1_recipe_configuration.json'" in rendered and "dest.getText('UTF-8') != text" in rendered and 'CONFIGURATION_ONLY_NOT_EXECUTION_EVIDENCE' in rendered,'Configuration receipt reuse/label guard missing')
 checks.append('second init load may reuse only identical sealed configuration; runtime evidence still required')
 require(groovy("D:/research/O'Brien/$name.jar")=="'D:/research/O\\'Brien/$name.jar'",'Literal escaping regressed');checks.append('apostrophe and dollar in path remain single-quoted data')
 cases=[]
 for key,value in [('Gradle_version','9.0'),('module_selector','../other'),('repo_root','relative/repo'),('repo_root','D:/repo\nrun'),('repo_root','//server/repo'),('focal_fqcn',"fixture.X';throw bad"),('test_fqcn','unrelated.Other_ESTest'),('source_context_sha256','x'),('add_junit4',1),('add_junit4',True)]:
  changed=copy.deepcopy(config);changed[key]=value;cases.append(changed)
 changed=copy.deepcopy(config);changed['pit_plugin_classpath']*=2;cases.append(changed)
 for bad in cases:
  try:validate_config(bad)
  except RecipeError:pass
  else:raise AssertionError('Unsafe or unproven config accepted')
 checks.append('11 unsafe version/path/FQCN/hash/JUnit-receipt/duplicate-classpath cases rejected')
 # All phases rendered in memory before any validation artifacts are written.
 for version in VERSIONS:
  c=copy.deepcopy(config);c['Gradle_version']=version;c['module_selector']='module'
  main=main_audit_script(c,base/'in_memory/main');measure=measurement_script(c,base/'in_memory/measure')
  require('initscript' not in main and 'pitest' not in main and 'jacoco' not in main and "dependencies.add" not in main and 'useJUnit()' not in main,'Pre-generation phase leaked test instrumentation')
  require('ss.main.runtimeClasspath' in main and 'ss.test.compileClasspath' in main and 'ss.main.compileClasspath' in main and "getByName('classes')" in main,'Pre-generation classpath audit missing')
  require('allprojects' not in main+measure and 'p.path == b1SelectedPath' in measure,'Overlay not module-scoped')
  require('nativeTest.useJUnit()' in measure and "getByName('testClasses')" in measure and "b1FocalFqcn + '$*'" not in measure and "pit.targetClasses" in measure,'Native discovery or legacy exact-focal target missing')
  require('nativeTest.dependsOn(p.tasks.getByName(\'test\'))' not in measure and "pit.mutators" not in measure and "'testng'" not in measure.split('def pit =')[0],'Unexpected ordinary task/mutator/provider override')
  require(('nativeTest.testClassesDir =' in measure)==(version=='2.13'),'Old/new test class directory API mapping changed')
  require(('reports.csv.required.set(true)' in measure)==(version=='8.14.4'),'Old/new report API mapping changed')
 checks.append('all4wrapper main/measure scope and version-specific API branches checked statically')
 with_junit=copy.deepcopy(config);with_junit['add_junit4']=True;with_junit['resolved_cp_audit']={'status':'PASS_RESOLVED_CP_AUDIT','junit4_missing':True,'evidence_sha256':'a'*64}
 require("'junit:junit:4.13.2'" in measurement_script(with_junit,base/'in_memory/measure') and "junit:junit" not in main_audit_script(with_junit,base/'in_memory/main'),'JUnit addition escaped measurement phase');checks.append('external-audit JUnit addition is measurement-only')
 for version in VERSIONS:
  c=copy.deepcopy(config);c['Gradle_version']=version;c['module_selector']='module'
  manifest=write_recipe(c,base/('gradle_'+version.replace('.','_')))
  artifacts.append({'version':version,'recipe_relative':('gradle_'+version.replace('.','_'))+'/recipe.json','recipe_sha256':sha(base/('gradle_'+version.replace('.','_'))/'recipe.json'),'phases':manifest['phases']})
 try:write_recipe(config,base/'gradle_2_13')
 except RecipeError:checks.append('existing recipe directory cannot be overwritten')
 else:raise AssertionError('Existing recipe overwrite accepted')
 try:write_recipe(config,R/'jobs/recipe_must_not_exist')
 except RecipeError:checks.append('prototype writer rejects benchmark job location')
 else:raise AssertionError('Prototype wrote benchmark files')
 result={'status':'PASS_PURE_VALIDATION','recipe_status':RECIPE_STATUS,'source_sha256':sha(__file__),'checks':checks,'recipes':artifacts,'validation_inputs':'synthetic plugin path/hash; deliberately unusable for runtime; no admission','runtime_qualification':False,'new_experiment_calls':0,'Java_Gradle_EvoSuite_calls':0,'GPT_API_calls':0,'benchmark_admitted':False}
 with (base/'result.json').open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
 return result

if __name__=='__main__':
 result=validate_prototype()
 B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
 audit.log('B1_GRADLE_NATIVE_RECIPE_PURE_VALIDATED',source_sha256=sha(__file__),result_sha256=sha(R/'validation/gradle_native_recipe_v6/result.json'),runtime_qualified=False,new_experiment_calls=0,GPT_API_calls=0)
 audit.verify()
 print(json.dumps(result,ensure_ascii=False,indent=2))
