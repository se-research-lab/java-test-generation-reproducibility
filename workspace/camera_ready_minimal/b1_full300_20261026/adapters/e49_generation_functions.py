"""E49 function-only copy. Load with explicit E-only bindings; no top-level side effects."""

def command_output_tail(result, limit=2500):
    parts = [getattr(result, 'stdout', '') or '', getattr(result, 'stderr', '') or '']
    return '\n'.join((part for part in parts if part)).strip()[-limit:]

def timeout_output_tail(exc, limit=2500):
    stdout = exc.stdout or ''
    stderr = exc.stderr or ''
    if isinstance(stdout, bytes):
        stdout = stdout.decode('utf-8', errors='replace')
    if isinstance(stderr, bytes):
        stderr = stderr.decode('utf-8', errors='replace')
    return '\n'.join((part for part in [stdout, stderr] if part)).strip()[-limit:]

def evosuite_classpath_entries(items):
    entries = []
    skipped = []
    for item in items:
        raw = str(item).strip().strip('"')
        if not raw:
            continue
        path = Path(raw)
        try:
            resolved = path.resolve()
        except Exception:
            resolved = path.absolute()
        if resolved.is_dir():
            entries.append(str(resolved))
            continue
        if resolved.is_file() and resolved.suffix.lower() == '.jar':
            if zipfile.is_zipfile(resolved):
                entries.append(str(resolved))
            else:
                skipped.append(f'invalid jar: {resolved}')
            continue
        if resolved.exists():
            skipped.append(f'non-jar classpath entry: {resolved}')
        else:
            skipped.append(f'missing classpath entry: {resolved}')
    return (entries, skipped)

def sanitize_evosuite_generation_classpath(entries):
    sanitized = []
    skipped = []
    for item in entries:
        name = Path(item).name.lower()
        if Path(item).is_file() and any((pattern in name for pattern in EVOSUITE_TEST_FRAMEWORK_JAR_PATTERNS)):
            skipped.append(item)
        else:
            sanitized.append(item)
    return (sanitized, skipped)

def should_retry_evosuite_with_sanitized_classpath(output):
    text = str(output or '').lower()
    retry_markers = ['displaynamegenerator', 'innerclasses attribute', 'mockmethodadvice', 'mockmethoddispatcher', 'bytebuddy', 'should be in target project, but could not be found', 'error while initializing target class: org/mockito']
    return any((marker in text for marker in retry_markers))

def write_pom_tree(tree, pom_path):
    root = tree.getroot()
    match = re.match('\\{([^}]+)\\}', root.tag)
    if match:
        ET.register_namespace('', match.group(1))
    tree.write(pom_path, encoding='utf-8', xml_declaration=True)
    try:
        with open(pom_path, 'r', encoding='utf-8') as file:
            content = file.read()
        content = re.sub('<ns\\d+:project\\s+xmlns:ns\\d+=\\"([^\\"]+)\\"', '<project xmlns=\\"\\1\\"', content, count=1)
        content = re.sub('</ns\\d+:project>', '</project>', content)
        content = re.sub('<ns\\d+:', '<', content)
        content = re.sub('</ns\\d+:', '</', content)
        content = re.sub('\\s+xmlns:ns\\d+=\\"[^\\"]+\\"', '', content)
        with open(pom_path, 'w', encoding='utf-8', newline='') as file:
            file.write(content)
    except Exception as exc:
        print(f'[RBL4] Warning: could not normalize POM namespace for {pom_path}: {exc}')

def common_maven_skip_args():
    return ['-Drat.skip=true', '-DfailIfNoTests=false', '-DfailIfNoSpecifiedTests=false', '-Dcheckstyle.skip=true', '-Dgpg.skip=true', '-Djavadoc.skip=true', '-Dmaven.javadoc.skip=true', '-Dlicense.skip=true', '-Ddependency-check.skip=true', '-Dfrontend.skip=true', '-Dskip.npm=true', '-Dskip.bower=true', '-Dskip.yarn=true', '-Dskip.grunt=true', '-Dskip.gulp=true', '-Dskip.webpack=true', '-Dfindbugs.skip=true', '-Dpmd.skip=true', '-Dcpd.skip=true', '-Dspring-boot.repackage.skip=true', '-Denforcer.skip=true', '-Dspotbugs.skip=true', '-Dspotless.skip=true', '-Dspotless.apply.skip=true', '-Dspotless.check.skip=true', '-Dspotless.maven.plugin.version=2.30.0', '-Dspotless.version=2.30.0', '-Dspotless-maven-plugin.version=2.30.0', '-Dformatter.skip=true', '-Dexec.skip=true']

def edit_pom_file(path, project_dataframe, junit_version, testng_version):
    """
    Edits the pom.xml file of the given Maven project to add the Jacoco and PITest dependencies.
        Parameters:
                    path: the path of the Maven project or of the module
                    project_dataframe (Dataframe): the dataframe containing all the focal classes and test classes that are to be executed with Pitest 
                    junit_version: the JUnit version of the Maven project, 'None' if the project does not implement the JUnit framework
                    testng_version: the TestNG version of the Maven project, 'None' if the project does not implement the TestNG framework

        Returns:
                    tree_old (ElementTree): the content of the pom.xml file before the edit, 'None' if an error occurred
    """
    project_df = project_dataframe.copy()
    ET.register_namespace('', 'http://maven.apache.org/POM/4.0.0')
    try:
        pom_path = os.path.join(path, 'pom.xml')
        tree_old = ET.parse(pom_path)
        tree_new = ET.parse(pom_path)
        root = tree_new.getroot()
    except Exception as e:
        print(e)
        return None
    ns = {'maven': 'http://maven.apache.org/POM/4.0.0'}
    if len(root.findall('maven:build', ns)) == 1:
        build = root.find('maven:build', ns)
    else:
        build = ET.SubElement(root, 'build')
    if len(build.findall('maven:plugins', ns)) == 1:
        plugins = build.find('maven:plugins', ns)
    else:
        plugins = ET.SubElement(build, 'plugins')
    for plugin in plugins.findall('maven:plugin', ns):
        group_id = plugin.find('maven:groupId', ns)
        artifact_id = plugin.find('maven:artifactId', ns)
        if group_id is None or artifact_id is None:
            continue
        if group_id.text == 'org.pitest':
            plugins.remove(plugin)
        if group_id.text == 'org.jacoco':
            plugins.remove(plugin)
        if artifact_id.text == 'maven-surefire-plugin':
            plugins.remove(plugin)
    pitest_plugin = ET.SubElement(plugins, 'plugin')
    pitest_group_id = ET.SubElement(pitest_plugin, 'groupId')
    pitest_group_id.text = 'org.pitest'
    pitest_artifact_id = ET.SubElement(pitest_plugin, 'artifactId')
    pitest_artifact_id.text = 'pitest-maven'
    pitest_version = ET.SubElement(pitest_plugin, 'version')
    pitest_version.text = '1.16.0'
    if junit_version is not None:
        if junit_version.startswith('5'):
            pitest_dependencies = ET.SubElement(pitest_plugin, 'dependencies')
            pitest_dependency = ET.SubElement(pitest_dependencies, 'dependency')
            pitest_dependency_group_id = ET.SubElement(pitest_dependency, 'groupId')
            pitest_dependency_group_id.text = 'org.pitest'
            pitest_dependency_artifact_id = ET.SubElement(pitest_dependency, 'artifactId')
            pitest_dependency_artifact_id.text = 'pitest-junit5-plugin'
            pitest_dependency_version = ET.SubElement(pitest_dependency, 'version')
            pitest_dependency_version.text = '1.2.1'
    if testng_version is not None:
        pitest_dependencies = ET.SubElement(pitest_plugin, 'dependencies')
        pitest_dependency = ET.SubElement(pitest_dependencies, 'dependency')
        pitest_dependency_group_id = ET.SubElement(pitest_dependency, 'groupId')
        pitest_dependency_group_id.text = 'org.pitest'
        pitest_dependency_artifact_id = ET.SubElement(pitest_dependency, 'artifactId')
        pitest_dependency_artifact_id.text = 'pitest-testng-plugin'
        pitest_dependency_version = ET.SubElement(pitest_dependency, 'version')
        pitest_dependency_version.text = '1.0.0'
    pitest_configuration = ET.SubElement(pitest_plugin, 'configuration')
    pitest_skip = ET.SubElement(pitest_configuration, 'skip')
    pitest_skip.text = 'false'
    pitest_output_formats = ET.SubElement(pitest_configuration, 'outputFormats')
    pitest_output_format = ET.SubElement(pitest_output_formats, 'outputFormat')
    pitest_output_format.text = 'CSV'
    pitest_export_line_coverage = ET.SubElement(pitest_configuration, 'exportLineCoverage')
    pitest_export_line_coverage.text = 'true'
    pitest_timestamped_reports = ET.SubElement(pitest_configuration, 'timestampedReports')
    pitest_timestamped_reports.text = 'false'
    pitest_features = ET.SubElement(pitest_configuration, 'features')
    pitest_feature = ET.SubElement(pitest_features, 'feature')
    pitest_feature.text = '+CLASSLIMIT(limit[42])'
    pitest_feature2 = ET.SubElement(pitest_features, 'feature')
    pitest_feature2.text = '+auto_threads'
    pitest_target_tests = ET.SubElement(pitest_configuration, 'targetTests')
    try:
        target_tests = project_df['Test_Path'].tolist()
        target_tests = [test_path.split('test/java/')[1].replace('/', '.').replace('.java', '') for test_path in target_tests]
    except Exception as e:
        return None
    for test in target_tests:
        ET.SubElement(pitest_target_tests, 'param').text = test
    surefire_plugin = ET.SubElement(plugins, 'plugin')
    surefire_group_id = ET.SubElement(surefire_plugin, 'groupId')
    surefire_group_id.text = 'org.apache.maven.plugins'
    surefire_artifact_id = ET.SubElement(surefire_plugin, 'artifactId')
    surefire_artifact_id.text = 'maven-surefire-plugin'
    surefire_version = ET.SubElement(surefire_plugin, 'version')
    surefire_version.text = '2.22.2'
    surefire_configuration = ET.SubElement(surefire_plugin, 'configuration')
    surefire_arg_line = ET.SubElement(surefire_configuration, 'argLine')
    surefire_arg_line.text = '${surefireArgLine} -Djdk.attach.allowAttachSelf=true'
    surefire_test_failure_ignore = ET.SubElement(surefire_configuration, 'testFailureIgnore')
    surefire_test_failure_ignore.text = 'true'
    surefire_fork_count = ET.SubElement(surefire_configuration, 'forkCount')
    surefire_fork_count.text = '2'
    surefire_reuse_forks = ET.SubElement(surefire_configuration, 'reuseForks')
    surefire_reuse_forks.text = 'true'
    jacoco_plugin = ET.SubElement(plugins, 'plugin')
    jacoco_group_id = ET.SubElement(jacoco_plugin, 'groupId')
    jacoco_group_id.text = 'org.jacoco'
    jacoco_artifact_id = ET.SubElement(jacoco_plugin, 'artifactId')
    jacoco_artifact_id.text = 'jacoco-maven-plugin'
    jacoco_version = ET.SubElement(jacoco_plugin, 'version')
    jacoco_version.text = '0.8.7'
    jacoco_configuration = ET.SubElement(jacoco_plugin, 'configuration')
    jacoco_property = ET.SubElement(jacoco_configuration, 'propertyName')
    jacoco_property.text = 'surefireArgLine'
    jacoco_skip = ET.SubElement(jacoco_configuration, 'skip')
    jacoco_skip.text = 'false'
    jacoco_data_file = ET.SubElement(jacoco_configuration, 'dataFile')
    jacoco_data_file.text = '${project.build.directory}/jacoco.exec'
    jacoco_output_file = ET.SubElement(jacoco_configuration, 'output')
    jacoco_output_file.text = 'file'
    jacoco_formats_file = ET.SubElement(jacoco_configuration, 'formats')
    jacoco_format_file = ET.SubElement(jacoco_formats_file, 'format')
    jacoco_format_file.text = 'CSV'
    jacoco_executions = ET.SubElement(jacoco_plugin, 'executions')
    jacoco_execution = ET.SubElement(jacoco_executions, 'execution')
    jacoco_id = ET.SubElement(jacoco_execution, 'id')
    jacoco_id.text = 'jacoco-initialize'
    jacoco_goals = ET.SubElement(jacoco_execution, 'goals')
    jacoco_goal = ET.SubElement(jacoco_goals, 'goal')
    jacoco_goal.text = 'prepare-agent'
    jacoco_execution2 = ET.SubElement(jacoco_executions, 'execution')
    jacoco_id2 = ET.SubElement(jacoco_execution2, 'id')
    jacoco_id2.text = 'jacoco-site'
    jacoco_phase = ET.SubElement(jacoco_execution2, 'phase')
    jacoco_phase.text = 'test'
    jacoco_goals2 = ET.SubElement(jacoco_execution2, 'goals')
    jacoco_goal2 = ET.SubElement(jacoco_goals2, 'goal')
    jacoco_goal2.text = 'report'
    write_pom_tree(tree_new, pom_path)
    return tree_old

def run_maven_test_command(path, project_dataframe, system):
    """
    Runs the package command for the given Maven project. 
    It generates the Jacoco and PITest reports. 
        Parameters:
                    path: the path of the project or of the module
                    project_dataframe (Dataframe): the dataframe that contains the focal classes and test classes that are to be executed by mvn
                    system (string): the current OS (Windows, Linux, etc..)  
        Returns:
                    :'True' if the project has been compiled successfully, 'False' if the project has been compiled with errors
    """
    project_df = project_dataframe.copy()
    started_at = time.time()
    project = str(project_df.iloc[0].get('Project', '')) if not project_df.empty else ''
    module = str(project_df.iloc[0].get('Module', '')) if not project_df.empty and 'Module' in project_df.columns else ''
    try:
        test_classes = project_df['Test_Path'].tolist()
        result = None
        test_classes = [test_path.split('test/java/')[1].replace('/', '.').replace('.java', '') for test_path in test_classes]
        test_classes = ','.join(test_classes)
        test_classes = f'-Dtest={test_classes}'
        print(f'Test classes: {test_classes}')
        subprocess.check_call([java_command(system), '-version'], timeout=15)
        command = [maven_command(system), *maven_settings_args(), test_classes, *common_maven_skip_args(), 'clean', 'verify', 'jacoco:prepare-agent', 'jacoco:report', 'org.pitest:pitest-maven:mutationCoverage']
        result = subprocess.run(command, cwd=path, capture_output=True, text=True, timeout=MAVEN_TIMEOUT_SECONDS)
        if result.stdout.__contains__(f'BUILD SUCCESS'):
            utils.append_phase_log('maven_verify_jacoco_pit', project=project, module=module, status='PASS', started_at=started_at, detail=test_classes)
            return (True, None)
        else:
            errori = errorCorrection.extract_errors(result.stdout, result.stderr)
            print('\n--------------------')
            print(errori)
            print('\n--------------------')
            utils.append_phase_log('maven_verify_jacoco_pit', project=project, module=module, status='FAIL', started_at=started_at, detail=errori)
            return (False, errori)
    except subprocess.TimeoutExpired as e:
        detail = f'Maven timed out after {MAVEN_TIMEOUT_SECONDS}s\n{timeout_output_tail(e)}'
        utils.append_phase_log('maven_verify_jacoco_pit', project=project, module=module, status='ERROR', started_at=started_at, detail=detail)
        print(detail)
        return (False, detail)
    except Exception as e:
        utils.append_phase_log('maven_verify_jacoco_pit', project=project, module=module, status='ERROR', started_at=started_at, detail=e)
        print(e)
        return (False, None)

def run_evosuite_generation_maven(path, focal_path, system, generation_profile=evosuite_profile.LEGACY):
    """
    Given a focal class of a Maven project, it runs EvoSuite to generate the corresponding test class.
        Parameters:
                path: the path of the project or of the module
                focal_path: the path of the focal class 
                system (string): the current OS (Windows, Linux, etc..)  

        Returns:
                :'True' if the generation has been executed correctly, 'False' otherwise
       
    """
    started_at = time.time()
    try:
        root_path = os.path.abspath(path)
        focal_path_abs = os.path.abspath(focal_path)
        focal_path_norm = focal_path_abs.replace('\\', '/')
        if '/src/main/java/' in focal_path_norm:
            focal_class_path = focal_path_norm.split('/src/main/java/', 1)[1]
        elif 'java/' in focal_path_norm:
            focal_class_path = focal_path_norm.split('java/', 1)[1]
        else:
            raise ValueError(f'Cannot infer Java class name from focal path: {focal_path}')
        name_class_to_test = focal_class_path.replace('.java', '').replace('/', '.')
        project = focal_path_norm.split('compiledrepos/')[1].split('/')[0] if 'compiledrepos/' in focal_path_norm else ''
        work_path = root_path
        search_dir = os.path.dirname(focal_path_abs)
        while search_dir and os.path.abspath(search_dir) != os.path.dirname(os.path.abspath(search_dir)):
            if os.path.exists(os.path.join(search_dir, 'pom.xml')):
                work_path = os.path.abspath(search_dir)
                break
            if os.path.abspath(search_dir) == root_path:
                break
            search_dir = os.path.dirname(search_dir)
        target_dir = os.path.join(work_path, 'target')
        os.makedirs(target_dir, exist_ok=True)
        classpath_file = os.path.join(target_dir, 'evosuite-classpath.txt')
        compile_command = [maven_command(system), *maven_settings_args(), *common_maven_skip_args(), '-DskipTests=true', 'compile', 'dependency:build-classpath', f'-Dmdep.outputFile={classpath_file}']
        result_mvn = subprocess.run(compile_command, cwd=work_path, capture_output=True, text=True, timeout=MAVEN_TIMEOUT_SECONDS)
        if result_mvn.returncode != 0:
            utils.append_phase_log('evosuite_generate', project=project, arm='evosuite', focal_class=name_class_to_test.split('.')[-1], status='FAIL', started_at=started_at, detail=command_output_tail(result_mvn))
            return False
        classpath_parts = []
        classes_dir = os.path.join(work_path, 'target', 'classes')
        if os.path.isdir(classes_dir):
            classpath_parts.append(classes_dir)
        if os.path.exists(classpath_file):
            with open(classpath_file, 'r', encoding='utf-8', errors='ignore') as file:
                dependency_cp = file.read().strip()
            if dependency_cp:
                classpath_parts.extend(dependency_cp.replace('\n', os.pathsep).split(os.pathsep))
        (valid_classpath_parts, skipped_classpath_parts) = evosuite_classpath_entries(classpath_parts)
        if skipped_classpath_parts:
            print('[RBL4] EvoSuite classpath skipped: ' + '; '.join(skipped_classpath_parts[:20]))
        project_cp = os.pathsep.join(valid_classpath_parts)
        if not project_cp:
            detail = f'Empty EvoSuite project classpath for module {work_path}'
            if skipped_classpath_parts:
                detail += '\nSkipped entries:\n' + '\n'.join(skipped_classpath_parts[:50])
            utils.append_phase_log('evosuite_generate', project=project, arm='evosuite', focal_class=name_class_to_test.split('.')[-1], status='FAIL', started_at=started_at, detail=detail)
            return False
        test_dir = os.path.join(work_path, 'src', 'test', 'java')
        if '/src/main/java/' in focal_path_norm:
            test_dir = focal_path_norm.split('/src/main/java/')[0] + '/src/test/java'
        test_dir = str(Path(test_dir).resolve())
        os.makedirs(test_dir, exist_ok=True)
        expected_name = f"{name_class_to_test.split('.')[-1]}_ESTest.java"
        expected_path = os.path.join(test_dir, *name_class_to_test.split('.')[:-1], expected_name)

        def copy_generated_test_if_needed():
            if os.path.exists(expected_path):
                return
            for (root_dir, _, files) in os.walk(test_dir):
                if expected_name in files:
                    generated_path = os.path.join(root_dir, expected_name)
                    os.makedirs(os.path.dirname(expected_path), exist_ok=True)
                    if os.path.abspath(generated_path) != os.path.abspath(expected_path):
                        with open(generated_path, 'r', encoding='utf-8', errors='replace') as src:
                            content = src.read()
                        utils.write_text_file(expected_path, content)
                    break

        def run_evosuite_with_classpath(classpath, retry_label='primary'):
            evosuite_command = [java_command(system), '-jar', toolchains.evosuite_jar(), '-class', name_class_to_test, '-projectCP', classpath, '-Dtest_dir=' + test_dir, '-Dreport_dir=' + str(Path(work_path, 'evosuite-report').resolve()), *evosuite_profile.maven_generation_options(generation_profile)]
            result = subprocess.run(evosuite_command, cwd=work_path, capture_output=True, text=True, timeout=EVOSUITE_TIMEOUT_SECONDS)
            copy_generated_test_if_needed()
            return result
        result_generate = run_evosuite_with_classpath(project_cp)
        output_text = (result_generate.stdout or '') + '\n' + (result_generate.stderr or '')
        retry_detail = ''
        if result_generate.returncode != 0 or not os.path.exists(expected_path):
            (sanitized_classpath_parts, sanitized_skipped_parts) = sanitize_evosuite_generation_classpath(valid_classpath_parts)
            sanitized_cp = os.pathsep.join(sanitized_classpath_parts)
            if sanitized_cp and sanitized_cp != project_cp and should_retry_evosuite_with_sanitized_classpath(output_text):
                retry_detail = 'sanitized retry; skipped test-framework jars: ' + ', '.join((Path(part).name for part in sanitized_skipped_parts[:30]))
                if os.path.exists(expected_path):
                    os.remove(expected_path)
                result_generate = run_evosuite_with_classpath(sanitized_cp, retry_label='sanitized')
                output_text = (result_generate.stdout or '') + '\n' + (result_generate.stderr or '')
        if result_generate.returncode == 0 and os.path.exists(expected_path):
            detail = name_class_to_test if not retry_detail else f'{name_class_to_test}; {retry_detail}'
            utils.append_phase_log('evosuite_generate', project=project, arm='evosuite', focal_class=name_class_to_test.split('.')[-1], status='PASS', started_at=started_at, detail=detail)
            return True
        else:
            detail = command_output_tail(result_generate)
            if retry_detail:
                detail = f'{retry_detail}\n{detail}'
            utils.append_phase_log('evosuite_generate', project=project, arm='evosuite', focal_class=name_class_to_test.split('.')[-1], status='FAIL', started_at=started_at, detail=detail)
            return False
    except subprocess.TimeoutExpired as e:
        detail = f'EvoSuite generation timed out after {EVOSUITE_TIMEOUT_SECONDS}s\n{timeout_output_tail(e)}'
        utils.append_phase_log('evosuite_generate', arm='evosuite', status='ERROR', started_at=started_at, detail=detail)
        print(detail)
        return False
    except Exception as e:
        utils.append_phase_log('evosuite_generate', arm='evosuite', status='ERROR', started_at=started_at, detail=e)
        print(e)
        return False

def add_evosuite_pom(path):
    """
    Adds the evosuite dependency and the evosuite plugin (version 1.2.0) to the pom.xml file of the given project.
        Parameters:
                    path: the path of the project or of the module
        Returns:
                    tree_old (ElementTree): the content of the pom.xml file before the edit, 'None' if an error occurred
    """
    ET.register_namespace('', 'http://maven.apache.org/POM/4.0.0')
    try:
        pom_path = os.path.join(path, 'pom.xml')
        tree_old = ET.parse(pom_path)
        tree_new = ET.parse(pom_path)
        root = tree_new.getroot()
    except Exception as e:
        print(e)
        return None
    ns = {'maven': 'http://maven.apache.org/POM/4.0.0'}
    if len(root.findall('maven:build', ns)) == 1:
        build = root.find('maven:build', ns)
    else:
        build = ET.SubElement(root, 'build')
    if len(build.findall('maven:plugins', ns)) == 1:
        plugins = build.find('maven:plugins', ns)
    else:
        plugins = ET.SubElement(build, 'plugins')
    all_plugins_sections = root.findall('maven:build/maven:plugins', ns)
    for plugins_section in all_plugins_sections:
        for plugin in plugins_section.findall('maven:plugin', ns):
            group_id = plugin.find('maven:groupId', ns)
            artifact_id = plugin.find('maven:artifactId', ns)
            if group_id is None or artifact_id is None:
                continue
            if group_id.text == 'org.evosuite.plugins':
                plugins.remove(plugin)
            if artifact_id.text == 'maven-surefire-plugin':
                plugins.remove(plugin)
    surefire_plugin = ET.SubElement(plugins, 'plugin')
    surefire_group_id = ET.SubElement(surefire_plugin, 'groupId')
    surefire_group_id.text = 'org.apache.maven.plugins'
    surefire_artifact_id = ET.SubElement(surefire_plugin, 'artifactId')
    surefire_artifact_id.text = 'maven-surefire-plugin'
    surefire_version = ET.SubElement(surefire_plugin, 'version')
    surefire_version.text = '2.17'
    surefire_configuration = ET.SubElement(surefire_plugin, 'configuration')
    surefire_arg_line = ET.SubElement(surefire_configuration, 'argLine')
    surefire_arg_line.text = '${surefireArgLine} -Djdk.attach.allowAttachSelf=true'
    surefire_test_failure_ignore = ET.SubElement(surefire_configuration, 'testFailureIgnore')
    surefire_test_failure_ignore.text = 'true'
    surefire_fork_count = ET.SubElement(surefire_configuration, 'forkCount')
    surefire_fork_count.text = '2'
    surefire_reuse_forks = ET.SubElement(surefire_configuration, 'reuseForks')
    surefire_reuse_forks.text = 'false'
    if len(root.findall('maven:dependencies', ns)) == 1:
        evosuite_dependencies_root = root.find('maven:dependencies', ns)
    else:
        evosuite_dependencies_root = ET.SubElement(root, 'dependencies')
    evosuite_dependency_root = ET.SubElement(evosuite_dependencies_root, 'dependency')
    evosuite_dependency_group_id_root = ET.SubElement(evosuite_dependency_root, 'groupId')
    evosuite_dependency_group_id_root.text = 'org.evosuite'
    evosuite_dependency_artifact_id_root = ET.SubElement(evosuite_dependency_root, 'artifactId')
    evosuite_dependency_artifact_id_root.text = 'evosuite-standalone-runtime'
    evosuite_dependency_version_root = ET.SubElement(evosuite_dependency_root, 'version')
    evosuite_dependency_version_root.text = '1.2.0'
    evosuite_dependency_scope_root = ET.SubElement(evosuite_dependency_root, 'scope')
    evosuite_dependency_scope_root.text = 'system'
    evosuite_dependency_system_path = ET.SubElement(evosuite_dependency_root, 'systemPath')
    evosuite_dependency_system_path.text = toolchains.evosuite_runtime_jar().replace('\\', '/')
    tools_jar = jdk_tools_jar()
    if tools_jar:
        tools_dependency_root = ET.SubElement(evosuite_dependencies_root, 'dependency')
        tools_dependency_group_id_root = ET.SubElement(tools_dependency_root, 'groupId')
        tools_dependency_group_id_root.text = 'com.sun'
        tools_dependency_artifact_id_root = ET.SubElement(tools_dependency_root, 'artifactId')
        tools_dependency_artifact_id_root.text = 'tools'
        tools_dependency_version_root = ET.SubElement(tools_dependency_root, 'version')
        tools_dependency_version_root.text = '1.8.0'
        tools_dependency_scope_root = ET.SubElement(tools_dependency_root, 'scope')
        tools_dependency_scope_root.text = 'system'
        tools_dependency_system_path = ET.SubElement(tools_dependency_root, 'systemPath')
        tools_dependency_system_path.text = tools_jar.replace('\\', '/')
    write_pom_tree(tree_new, pom_path)
    return tree_old
