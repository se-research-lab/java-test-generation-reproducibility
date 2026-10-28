"""Keep legacy Gradle measurement domain/resource settings in the prototype."""
import sys
from maven_adapter_v1 import R,sha,dump
B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
source=R/'src/gradle_native_recipe_v2.py';target=R/'src/gradle_native_recipe_v3.py'
text=source.read_text(encoding='utf-8').replace('gradle_native_recipe_v2','gradle_native_recipe_v3')
text=text.replace("[b1FocalFqcn, b1FocalFqcn + '$*']","[b1FocalFqcn]")
text=text.replace('// DISCLOSED AMENDMENT: focal + nested targets, never a broad same-prefix match.','// Preserve the legacy Gradle exact-focal measurement target; no nested expansion.')
text=text.replace("nativeTest.ignoreFailures = false", """// Copy declarative resources and process gate; isolate only native discovery.
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
    nativeTest.enabled = nativeTest.enabled && originalTest.enabled""")
text=text.replace('nativeEnabled: nativeTest.enabled, nestedTargetAmendment: true',"nativeEnabled: nativeTest.enabled, legacyExactFocalTarget: true, originalIgnoreFailures: originalTest.ignoreFailures, nativeIgnoreFailures: nativeTest.ignoreFailures, originalMaxHeap: originalTest.maxHeapSize, nativeMaxHeap: nativeTest.maxHeapSize")
text=text.replace("'exact focal plus focal+$*; frozen before any future Gradle outcomes; differs from legacy exact-focal-only target'","'NONE: preserve legacy exact focal FQCN; do not expand the measured mutant domain'")
text=text.replace('and "b1FocalFqcn + \'$*\'" in measure', 'and "b1FocalFqcn + \'$*\'" not in measure and "pit.targetClasses" in measure')
text=text.replace('Native discovery or nested target scope missing','Native discovery or legacy exact-focal target missing')
text=text.replace('Native discovery or nested target scope missing','Native discovery or legacy exact-focal target missing')
text=text.replace("checks=[];artifacts=[]", "checks=[];artifacts=[]\n require('originalTest.ignoreFailures' in measurement_script(config,base/'in_memory/measure') and 'originalTest.maxHeapSize' in measurement_script(config,base/'in_memory/measure'),'Original task resources/gate not preserved')\n checks.append('native task copies original declarative resources/gate; provider/selector/dependsOn remain separate')")
compile(text,str(target),'exec')
with target.open('x',encoding='utf-8') as f:f.write(text)
dump(R/'audit/gradle_recipe_v3_changes.json',{'old_source_sha256':sha(source),'new_source_sha256':sha(target),'reason':'Scope control before any Gradle benchmark: preserve original Gradle exact focal mutant target and original task resource/process-gate settings','changes':['remove unrequested nested-target expansion from unadmitted prototype','copy heap/JVM/system properties/assertions/forks/workingdir/ignoreFailures; do not reenable a disabled original task','keep native JUnit provider/selector and separate task dependencies'],'runtime_qualified':False,'GPT_modified':False,'new_experiment_calls':0})
audit.log('B1_GRADLE_RECIPE_V3_SCOPE_CORRECTED',source_sha256=sha(target),prior_sha256=sha(source),new_experiment_calls=0);print('Prepared recipe v3; exact legacy target/resource gate; still unqualified')
