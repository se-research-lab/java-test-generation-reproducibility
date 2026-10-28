import re
import xml.etree.ElementTree as ET
import os
import subprocess
import time
import zipfile
from pathlib import Path

import pandas as pd

import errorCorrection
import utils
import toolchains
import sys

df_chance = pd.DataFrame(columns=['Test_Class', 'Test_Path', 'Chance'])

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAVEN_TIMEOUT_SECONDS = int(os.getenv("RBL4_MAVEN_TIMEOUT_SECONDS", "300"))
EVOSUITE_TIMEOUT_SECONDS = int(os.getenv("RBL4_EVOSUITE_TIMEOUT_SECONDS", "240"))


def command_output_tail(result, limit=2500):
    parts = [getattr(result, "stdout", "") or "", getattr(result, "stderr", "") or ""]
    return "\n".join(part for part in parts if part).strip()[-limit:]


def timeout_output_tail(exc, limit=2500):
    stdout = exc.stdout or ""
    stderr = exc.stderr or ""
    if isinstance(stdout, bytes):
        stdout = stdout.decode("utf-8", errors="replace")
    if isinstance(stderr, bytes):
        stderr = stderr.decode("utf-8", errors="replace")
    return "\n".join(part for part in [stdout, stderr] if part).strip()[-limit:]


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
        if resolved.is_file() and resolved.suffix.lower() == ".jar":
            if zipfile.is_zipfile(resolved):
                entries.append(str(resolved))
            else:
                skipped.append(f"invalid jar: {resolved}")
            continue
        if resolved.exists():
            skipped.append(f"non-jar classpath entry: {resolved}")
        else:
            skipped.append(f"missing classpath entry: {resolved}")
    return entries, skipped


EVOSUITE_TEST_FRAMEWORK_JAR_PATTERNS = [
    "junit",
    "jupiter",
    "hamcrest",
    "mockito",
    "byte-buddy",
    "objenesis",
    "opentest4j",
    "apiguardian",
]


def sanitize_evosuite_generation_classpath(entries):
    sanitized = []
    skipped = []
    for item in entries:
        name = Path(item).name.lower()
        if Path(item).is_file() and any(pattern in name for pattern in EVOSUITE_TEST_FRAMEWORK_JAR_PATTERNS):
            skipped.append(item)
        else:
            sanitized.append(item)
    return sanitized, skipped


def should_retry_evosuite_with_sanitized_classpath(output):
    text = str(output or "").lower()
    retry_markers = [
        "displaynamegenerator",
        "innerclasses attribute",
        "mockmethodadvice",
        "mockmethoddispatcher",
        "bytebuddy",
        "should be in target project, but could not be found",
        "error while initializing target class: org/mockito",
    ]
    return any(marker in text for marker in retry_markers)


def java_command(system):
    java_home = os.environ.get("JAVA_HOME")
    executable = "java.exe" if system == "Windows" else "java"
    if java_home:
        candidate = Path(java_home) / "bin" / executable
        if candidate.exists():
            return str(candidate)
    return "java"


def jdk_tools_jar():
    java_home = os.environ.get("JAVA_HOME")
    if not java_home:
        return None
    for candidate in [
        Path(java_home) / "lib" / "tools.jar",
        Path(java_home) / "jre" / "lib" / "tools.jar",
        Path(java_home).parent / "lib" / "tools.jar",
    ]:
        if candidate.exists():
            return str(candidate)
    return None


def write_pom_tree(tree, pom_path):
    root = tree.getroot()
    match = re.match(r"\{([^}]+)\}", root.tag)
    if match:
        ET.register_namespace("", match.group(1))
    tree.write(pom_path, encoding="utf-8", xml_declaration=True)
    try:
        with open(pom_path, "r", encoding="utf-8") as file:
            content = file.read()
        content = re.sub(r"<ns\d+:project\s+xmlns:ns\d+=\"([^\"]+)\"", r"<project xmlns=\"\1\"", content, count=1)
        content = re.sub(r"</ns\d+:project>", "</project>", content)
        content = re.sub(r"<ns\d+:", "<", content)
        content = re.sub(r"</ns\d+:", "</", content)
        content = re.sub(r"\s+xmlns:ns\d+=\"[^\"]+\"", "", content)
        with open(pom_path, "w", encoding="utf-8", newline="") as file:
            file.write(content)
    except Exception as exc:
        print(f"[RBL4] Warning: could not normalize POM namespace for {pom_path}: {exc}")


def maven_command(system):
    return "mvn.cmd" if system == "Windows" else "mvn"


def common_maven_skip_args():
    return [
        "-Drat.skip=true",
        "-DfailIfNoTests=false",
        "-DfailIfNoSpecifiedTests=false",
        "-Dcheckstyle.skip=true",
        "-Dgpg.skip=true",
        "-Djavadoc.skip=true",
        "-Dmaven.javadoc.skip=true",
        "-Dlicense.skip=true",
        "-Ddependency-check.skip=true",
        "-Dfrontend.skip=true",
        "-Dskip.npm=true",
        "-Dskip.bower=true",
        "-Dskip.yarn=true",
        "-Dskip.grunt=true",
        "-Dskip.gulp=true",
        "-Dskip.webpack=true",
        "-Dfindbugs.skip=true",
        "-Dpmd.skip=true",
        "-Dcpd.skip=true",
        "-Dspring-boot.repackage.skip=true",
        "-Denforcer.skip=true",
        "-Dspotbugs.skip=true",
        "-Dspotless.skip=true",
        "-Dspotless.apply.skip=true",
        "-Dspotless.check.skip=true",
        "-Dspotless.maven.plugin.version=2.30.0",
        "-Dspotless.version=2.30.0",
        "-Dspotless-maven-plugin.version=2.30.0",
        "-Dformatter.skip=true",
        "-Dexec.skip=true",
    ]


def maven_settings_args():
    project = os.environ.get("RBL4_CURRENT_PROJECT", "").strip()
    if project:
        repair_settings = Path(BASE_DIR) / "repair_configs" / project / "settings_retry.xml"
        if repair_settings.exists():
            return ["-s", str(repair_settings)]
    settings_path = os.path.abspath("settings.xml")
    return ["-s", settings_path] if os.path.exists(settings_path) else []



def search_modules_pom(project_path, project_dataframe, project_id):
    """
    Searches all the modules where are stored pom.xml files in association with the classes specified in the the dataframe.

        Parameters:
                    project_path: the path of the proejct
                    project_dataframe (Dataframe): the dataframe containing all the focal classes and test classes
                    project_id: the ID of the project
        Returns:
                    modules (List): the list of the modules found               
    """
    project_df = project_dataframe.copy()
    modules = []
    for index, row in project_df.iterrows():
            location = row['Test_Path'].replace(f'repos/{project_id}/', '').replace(f"{row['Test_Class']}.java", '')
            file_name = f"/{row['Test_Class']}.java"
            while not os.path.isfile(f"{project_path}/{location}/pom.xml"):
                location = os.path.dirname(location)
                if location == '':
                    break
            if location != '':
                modules.append(location)
    # remove duplicates
    modules = list(dict.fromkeys(modules)) 
    return modules


def version_as_variable(version, root):
    """
    Given a version expressed as a variable, this function returns the corresponding version as a number. 
    This function works only for Maven Projects. 
        Parameters:
                    version (String): the version represented by a variable (e.g. '${jre.version}')
                    root (Element): root of the pom file
        Returns:
                    :the number corresponding to the variable (e.g. '${jre.version}'  -> 1.8), "None" if the function did not find it
    """
    pattern = r"\${(.*?)}" 
    # I only obtain the content within square brackets. For example, ${jre.version} becomes jre.version
    matches = re.findall(pattern, version)
    if matches:
        result = matches[0]
        version = root.find(
        '{http://maven.apache.org/POM/4.0.0}properties/{http://maven.apache.org/POM/4.0.0}' + result)
        if version is not None:
            return version.text
        else:
            return None
    else:
        return None
    


def extract_maven_version(path):
    """
    Extracts Maven version from the given project.  
        Parameters:
                    path: the path of the project or of the module
        Returns:
                    compiler_version: the Maven version expressed as a numeric value, 'None' if the function did not find it
    """
    compiler_version = None
    tree = ET.parse(os.path.join(path, 'pom.xml'))
    root = tree.getroot()
    find_compiler = False
    compiler_version_find = root.find('{http://maven.apache.org/POM/4.0.0}properties/{http://maven.apache.org/POM/4.0.0}mvn.version')
    if compiler_version_find is not None:
        compiler_version_find = compiler_version_find.text
        if compiler_version_find.startswith('$'):
            compiler_version_find = version_as_variable(compiler_version_find, root)
        if utils.check_version(compiler_version_find)==True:
            find_compiler = True
            compiler_version = compiler_version_find
    if find_compiler == False:
        compiler_version_find = root.find(
        '{http://maven.apache.org/POM/4.0.0}properties/{http://maven.apache.org/POM/4.0.0}maven.version')
        if compiler_version_find is not None:
            compiler_version_find = compiler_version_find.text
            if compiler_version_find.startswith('$'):
                compiler_version_find = version_as_variable(compiler_version_find, root)
            if utils.check_version(compiler_version_find)==True:
                find_compiler = True
                compiler_version = compiler_version_find
    if compiler_version is None:
        compiler_version = '3.8.1'
    return compiler_version



def extract_test_and_java_version_maven(path):
    """
    Extracts Java version and JUnit or TestNG version from the given project. 
        Parameters:
                    path: the path of the project or of the module
        Returns:
                    java_version: if the function finds the Java version, it returns a numeric value, otherwise, it returns 'None'
                    junit_version: if the function finds the Junit version, it returns a numeric value, otherwise, it returns 'None'
                    testng_version: if the function finds the TestNG version, it returns a numeric value, otherwise, it returns 'None'
    """
    java_version = None
    junit_version = None
    testng_version = None
    # Define the namespace
    ns = {'mvn': 'http://maven.apache.org/POM/4.0.0'}
    tree = ET.parse(os.path.join(path, 'pom.xml'))
    root = tree.getroot()
    dependencies_root=root.findall('mvn:dependencies/mvn:dependency', ns)
    dependencies_management=root.findall('mvn:dependencyManagement/mvn:dependencies/mvn:dependency', ns)
    all_dependencies=dependencies_root+dependencies_management
    findTest = False # True if I found the Junit/TestNG version, false otherwhise
    for dependency in all_dependencies:
        # Extract junit or testNG version
        group_id = dependency.find('mvn:groupId', ns)
        artifact_id = dependency.find('mvn:artifactId', ns)
        version = dependency.find('mvn:version', ns)
        # If the groupId and artifactId match 'org.testng' and 'testng' respectively
        if group_id is not None and artifact_id is not None and version is not None:
            if group_id.text.__contains__('testng'):
                    version_text = version.text
                    if version_text.startswith('$'):
                        version_text = version_as_variable(version_text, root)
                    if utils.check_version(version_text)==True:
                        testng_version = version_text
                        findTest = True
                        break
            elif group_id.text.__contains__('junit'):
                version_text = version.text
                if version_text.startswith('$'):
                    version_text = version_as_variable(version_text, root)
                if utils.check_version(version_text)==True:
                    junit_version = version_text
                    findTest = True
                    break
    if findTest==False:
        test_version = root.find(
        '{http://maven.apache.org/POM/4.0.0}properties/{http://maven.apache.org/POM/4.0.0}junit5.version')
        if test_version is not None:
                test_version_text = test_version.text
                if test_version_text.startswith("$"):
                    test_version_text = version_as_variable(test_version_text, root)
                if utils.check_version(test_version_text)==True:
                    junit_version = test_version_text
                    findTest = True
    if findTest==False:
        test_version = root.find(
        '{http://maven.apache.org/POM/4.0.0}properties/{http://maven.apache.org/POM/4.0.0}junit4.version')
        if test_version is not None:
            test_version_text = test_version.text
            if test_version_text.startswith("$"):
                test_version_text = version_as_variable(test_version_text, root)
            if utils.check_version(test_version_text)==True:
                junit_version = test_version_text
                findTest = True
    if findTest==False:
        test_version = root.find(
        '{http://maven.apache.org/POM/4.0.0}properties/{http://maven.apache.org/POM/4.0.0}junit.version')
        if test_version is not None:
            test_version_text = test_version.text
            if test_version_text.startswith("$"):
                test_version_text = version_as_variable(test_version_text, root)
            if utils.check_version(test_version_text)==True:
                junit_version = test_version_text
                findTest = True
    if findTest==False:
        test_version = root.find(
        '{http://maven.apache.org/POM/4.0.0}properties/{http://maven.apache.org/POM/4.0.0}version.junit')
        if test_version is not None:
            test_version_text = test_version.text
            if test_version_text.startswith("$"):
                test_version_text = version_as_variable(test_version_text, root)
            if utils.check_version(test_version_text)==True:
                junit_version = test_version_text
                findTest = True
    if findTest==False:
        test_version = root.find(
        '{http://maven.apache.org/POM/4.0.0}properties/{http://maven.apache.org/POM/4.0.0}testng.version')
        if test_version is not None:
            test_version_text = test_version.text
            if test_version_text.startswith("$"):
                test_version_text = version_as_variable(test_version_text, root)
            if utils.check_version(test_version_text)==True:
                testng_version = test_version_text
                findTest = True
    if findTest==False:
        test_version = root.find(
        '{http://maven.apache.org/POM/4.0.0}properties/{http://maven.apache.org/POM/4.0.0}version.testng')
        if test_version is not None:
            test_version_text = test_version.text
            if test_version_text.startswith("$"):
                test_version_text = version_as_variable(test_version_text, root)
            if utils.check_version(test_version_text)==True:
                testng_version = test_version_text
                findTest = True
        
        
        
    findJava = False # True if I found the java version, false otherwhise
    # Extract Java version
    java_version_find = root.find(
        '{http://maven.apache.org/POM/4.0.0}properties/{http://maven.apache.org/POM/4.0.0}maven.compiler.source')
    if java_version_find is not None:
        java_version_find_text = java_version_find.text
        if java_version_find_text.startswith("$"):
           java_version_find_text = version_as_variable(java_version_find_text, root)
        if utils.check_version(java_version_find_text)==True:
            java_version = java_version_find_text
            findJava = True

    if findJava == False:
        java_version_find = root.find(
            '{http://maven.apache.org/POM/4.0.0}properties/{h ttp://maven.apache.org/POM/4.0.0}javaVersion')
        if java_version_find is not None:
            java_version_find_text = java_version_find.text
            if java_version_find_text.startswith("$"):
                java_version_find_text = version_as_variable(java_version_find_text, root)
            if utils.check_version(java_version_find_text)==True:
                java_version = java_version_find_text
                findJava = True  

    if findJava == False:
        java_version_find = root.find(
            '{http://maven.apache.org/POM/4.0.0}properties/{http://maven.apache.org/POM/4.0.0}java.version')
        if java_version_find is not None:
            java_version_find_text = java_version_find.text
            if java_version_find_text.startswith("$"):
                java_version_find_text = version_as_variable(java_version_find_text, root)
            if utils.check_version(java_version_find_text)==True:
                java_version = java_version_find_text
                findJava = True

    if findJava == False:
        java_version_find = root.find(
            '{http://maven.apache.org/POM/4.0.0}properties/{http://maven.apache.org/POM/4.0.0}maven.compiler.source')
        if java_version_find is not None:
            java_version_find = root.find(
                './/{http://maven.apache.org/POM/4.0.0}plugin'
                '[{http://maven.apache.org/POM/4.0.0}artifactId="maven-compiler-plugin"]'
                '/{http://maven.apache.org/POM/4.0.0}configuration/'
                '{http://maven.apache.org/POM/4.0.0}release')
            if java_version_find is not None:
                java_version_find_text = java_version.text
                if java_version_find_text.startswith("$"):
                    java_version_find_text = version_as_variable(java_version_find_text, root)
                if utils.check_version(java_version_find_text)==True:
                    java_version = java_version_find_text
                    findJava = True

    if findJava == False:
        with open(os.path.join(path, 'pom.xml'), 'r') as f:
            pom_content = f.read()
            java_version_find = re.search(r'<source>(.+?)</source>', pom_content, re.DOTALL)
            if java_version is None:
                java_version_find = re.search(r'<javaVersion>(.+?)</javaVersion>', pom_content, re.DOTALL)
            if java_version is None:
                java_version_find = re.search(r'<release>(.+?)</release>', pom_content, re.DOTALL)
            if java_version_find is not None:
                java_version_find_text = java_version_find.group(1)
                if java_version_find_text.startswith("$"):
                    java_version_find_text = version_as_variable(java_version_find_text, root)
                if utils.check_version(java_version_find_text)==True:
                    java_version = java_version_find_text
                    findJava = True

    if findJava == False:
        java_version_find = root.find(
            '{http://maven.apache.org/POM/4.0.0}properties/{http://maven.apache.org/POM/4.0.0}maven.compiler.release')
        if java_version_find is not None:
            java_version_find_text = java_version_find.text
            if java_version_find_text.startswith("$"):
                java_version_find_text = version_as_variable(java_version_find_text, root)
            if utils.check_version(java_version_find_text)==True:
                java_version = java_version_find_text
                findJava = True

    if findJava == False:
        java_version_find = root.find(
            '{http://maven.apache.org/POM/4.0.0}properties/{http://maven.apache.org/POM/4.0.0}javaVersion')
        if java_version is not None:
            java_version = java_version_find.text
        if java_version is None:
            with open(os.path.join(path, 'pom.xml'), 'r') as f:
                pom_content = f.read()
            java_version = re.search(r'<source>(.+?)</source>', pom_content, re.DOTALL)
            if java_version is not None:
                findJava = True
                java_version = java_version.group(1)

    if findJava == False:
        java_version_find = root.find(
            '{http://maven.apache.org/POM/4.0.0}properties/{http://maven.apache.org/POM/4.0.0}version.java')
        if java_version_find is not None:
            java_version_find_text = java_version_find.text
            if java_version_find_text.startswith("$"):
                java_version_find_text = version_as_variable(java_version_find_text, root)
            if utils.check_version(java_version_find_text)==True:
                java_version = java_version_find_text
                findJava = True

    # Use Java version 1.8 if no version is found
    if java_version is None:
        java_version = '1.8'

    # Set JUnit version to 4 if neither JUnit nor TestNG version is found
    if junit_version is None and testng_version is None:
        junit_version = '4'

    return java_version, junit_version, testng_version






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
    # Parse the 'pom.xml' file
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
    # Check if there is only one 'build' section
    if len(root.findall('maven:build', ns)) == 1:
        build = root.find('maven:build', ns)
    else:
        # Add a 'build' section
        build = ET.SubElement(root, 'build')

    # Check if there is only one 'plugins' section
    if len(build.findall('maven:plugins', ns)) == 1:
        plugins = build.find('maven:plugins', ns)
    else:
        # Add a 'plugins' section
        plugins = ET.SubElement(build, 'plugins')

    # Check se tra i plugin c'è già pitest e jacoco
    for plugin in plugins.findall('maven:plugin', ns):
        group_id = plugin.find('maven:groupId', ns)
        artifact_id = plugin.find('maven:artifactId', ns)
        if group_id is None or artifact_id is None:
            continue
        if group_id.text == 'org.pitest':
            # Remove the 'pitest' plugin
            plugins.remove(plugin)
        if group_id.text == 'org.jacoco':
            # Remove the 'jacoco' plugin
            plugins.remove(plugin)
        if artifact_id.text == 'maven-surefire-plugin':
            plugins.remove(plugin)


    # Add the 'jacoco', 'pitest' and 'maven-surefire-plugin' plugins
    pitest_plugin = ET.SubElement(plugins, 'plugin')
    pitest_group_id = ET.SubElement(pitest_plugin, 'groupId')
    pitest_group_id.text = 'org.pitest'
    pitest_artifact_id = ET.SubElement(pitest_plugin, 'artifactId')
    pitest_artifact_id.text = 'pitest-maven'
    pitest_version = ET.SubElement(pitest_plugin, 'version')
    pitest_version.text = '1.16.0'




    # Add the pitest dependencies for junit 5
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

    # Add the pitest dependencies for testng
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
    # Add the target tests from project_df
        target_tests = project_df['Test_Path'].tolist()      
        # convert the test path to the correct format cut after test/java/
        target_tests = [test_path.split('test/java/')[1].replace('/', '.').replace('.java', '') for test_path in
                        target_tests]
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


    # Write the changes to the 'pom.xml' file
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
        # Create -Dtest= parameter only for the test classes that exist
        test_classes = project_df['Test_Path'].tolist()
        result = None
        # convert the test pathresult =  to the correct format cut after test/java/
        test_classes = [test_path.split('test/java/')[1].replace('/', '.').replace('.java', '') for test_path in
                        test_classes]
        test_classes = ','.join(test_classes)
        test_classes = f'-Dtest={test_classes}'
        print(f"Test classes: {test_classes}")
        subprocess.check_call([java_command(system), '-version'], timeout=15)
        command = [
            maven_command(system),
            *maven_settings_args(),
            test_classes,
            *common_maven_skip_args(),
            'clean',
            'verify',
            'jacoco:prepare-agent',
            'jacoco:report',
            'org.pitest:pitest-maven:mutationCoverage',
        ]
        result = subprocess.run(command, cwd=path, capture_output=True, text=True, timeout=MAVEN_TIMEOUT_SECONDS)

        if result.stdout.__contains__(f'BUILD SUCCESS'):
            utils.append_phase_log("maven_verify_jacoco_pit", project=project, module=module, status="PASS", started_at=started_at, detail=test_classes)
            return True, None
        else:
            errori = errorCorrection.extract_errors(result.stdout, result.stderr)
            print("\n--------------------")
            print (errori)
            print("\n--------------------")
            utils.append_phase_log("maven_verify_jacoco_pit", project=project, module=module, status="FAIL", started_at=started_at, detail=errori)
            return False, errori

    except subprocess.TimeoutExpired as e:
            detail = f"Maven timed out after {MAVEN_TIMEOUT_SECONDS}s\n{timeout_output_tail(e)}"
            utils.append_phase_log("maven_verify_jacoco_pit", project=project, module=module, status="ERROR", started_at=started_at, detail=detail)
            print(detail)
            return False, detail
    except Exception as e:
            utils.append_phase_log("maven_verify_jacoco_pit", project=project, module=module, status="ERROR", started_at=started_at, detail=e)
            print(e)
            return False, None




def run_evosuite_generation_maven(path, focal_path, system):
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
        focal_path_norm = focal_path_abs.replace("\\", "/")
        if "/src/main/java/" in focal_path_norm:
            focal_class_path = focal_path_norm.split("/src/main/java/", 1)[1]
        elif "java/" in focal_path_norm:
            focal_class_path = focal_path_norm.split("java/", 1)[1]
        else:
            raise ValueError(f"Cannot infer Java class name from focal path: {focal_path}")
        name_class_to_test = focal_class_path.replace(".java", "").replace("/", ".")
        project = focal_path_norm.split("compiledrepos/")[1].split("/")[0] if "compiledrepos/" in focal_path_norm else ""
        work_path = root_path
        search_dir = os.path.dirname(focal_path_abs)
        while search_dir and os.path.abspath(search_dir) != os.path.dirname(os.path.abspath(search_dir)):
            if os.path.exists(os.path.join(search_dir, "pom.xml")):
                work_path = os.path.abspath(search_dir)
                break
            if os.path.abspath(search_dir) == root_path:
                break
            search_dir = os.path.dirname(search_dir)

        target_dir = os.path.join(work_path, "target")
        os.makedirs(target_dir, exist_ok=True)
        classpath_file = os.path.join(target_dir, "evosuite-classpath.txt")
        compile_command = [
            maven_command(system),
            *maven_settings_args(),
            *common_maven_skip_args(),
            "-DskipTests=true",
            "compile",
            "dependency:build-classpath",
            f"-Dmdep.outputFile={classpath_file}",
        ]
        result_mvn = subprocess.run(compile_command, cwd=work_path, capture_output=True, text=True, timeout=MAVEN_TIMEOUT_SECONDS)
        if result_mvn.returncode != 0:
            utils.append_phase_log("evosuite_generate", project=project, arm="evosuite", focal_class=name_class_to_test.split(".")[-1], status="FAIL", started_at=started_at, detail=command_output_tail(result_mvn))
            return False

        classpath_parts = []
        classes_dir = os.path.join(work_path, "target", "classes")
        if os.path.isdir(classes_dir):
            classpath_parts.append(classes_dir)
        if os.path.exists(classpath_file):
            with open(classpath_file, "r", encoding="utf-8", errors="ignore") as file:
                dependency_cp = file.read().strip()
            if dependency_cp:
                classpath_parts.extend(dependency_cp.replace("\n", os.pathsep).split(os.pathsep))
        valid_classpath_parts, skipped_classpath_parts = evosuite_classpath_entries(classpath_parts)
        if skipped_classpath_parts:
            print("[RBL4] EvoSuite classpath skipped: " + "; ".join(skipped_classpath_parts[:20]))
        project_cp = os.pathsep.join(valid_classpath_parts)
        if not project_cp:
            detail = f"Empty EvoSuite project classpath for module {work_path}"
            if skipped_classpath_parts:
                detail += "\nSkipped entries:\n" + "\n".join(skipped_classpath_parts[:50])
            utils.append_phase_log("evosuite_generate", project=project, arm="evosuite", focal_class=name_class_to_test.split(".")[-1], status="FAIL", started_at=started_at, detail=detail)
            return False

        test_dir = os.path.join(work_path, "src", "test", "java")
        if "/src/main/java/" in focal_path_norm:
            test_dir = focal_path_norm.split("/src/main/java/")[0] + "/src/test/java"
        test_dir = str(Path(test_dir).resolve())
        os.makedirs(test_dir, exist_ok=True)

        expected_name = f"{name_class_to_test.split('.')[-1]}_ESTest.java"
        expected_path = os.path.join(test_dir, *name_class_to_test.split(".")[:-1], expected_name)

        def copy_generated_test_if_needed():
            if os.path.exists(expected_path):
                return
            for root_dir, _, files in os.walk(test_dir):
                if expected_name in files:
                    generated_path = os.path.join(root_dir, expected_name)
                    os.makedirs(os.path.dirname(expected_path), exist_ok=True)
                    if os.path.abspath(generated_path) != os.path.abspath(expected_path):
                        with open(generated_path, "r", encoding="utf-8", errors="replace") as src:
                            content = src.read()
                        utils.write_text_file(expected_path, content)
                    break

        def run_evosuite_with_classpath(classpath, retry_label="primary"):
            evosuite_command = [
                java_command(system),
                "-jar",
                toolchains.evosuite_jar(),
                "-class",
                name_class_to_test,
                "-projectCP",
                classpath,
                "-Dtest_dir=" + test_dir,
                "-Dreport_dir=" + str(Path(work_path, "evosuite-report").resolve()),
                "-Duse_separate_classloader=false",
                "-Dtest_archive=false",
                "-Dcriterion=BRANCH",
                "-Dassertions=false",
                "-Dno_runtime_dependency=true",
                "-Dtest_scaffolding=false",
                "-Dsearch_budget=60",
            ]
            result = subprocess.run(evosuite_command, cwd=work_path, capture_output=True, text=True, timeout=EVOSUITE_TIMEOUT_SECONDS)
            copy_generated_test_if_needed()
            return result

        result_generate = run_evosuite_with_classpath(project_cp)
        output_text = (result_generate.stdout or "") + "\n" + (result_generate.stderr or "")
        retry_detail = ""
        if result_generate.returncode != 0 or not os.path.exists(expected_path):
            sanitized_classpath_parts, sanitized_skipped_parts = sanitize_evosuite_generation_classpath(valid_classpath_parts)
            sanitized_cp = os.pathsep.join(sanitized_classpath_parts)
            if (
                sanitized_cp
                and sanitized_cp != project_cp
                and should_retry_evosuite_with_sanitized_classpath(output_text)
            ):
                retry_detail = "sanitized retry; skipped test-framework jars: " + ", ".join(
                    Path(part).name for part in sanitized_skipped_parts[:30]
                )
                if os.path.exists(expected_path):
                    os.remove(expected_path)
                result_generate = run_evosuite_with_classpath(sanitized_cp, retry_label="sanitized")
                output_text = (result_generate.stdout or "") + "\n" + (result_generate.stderr or "")

        if result_generate.returncode == 0 and os.path.exists(expected_path):
            detail = name_class_to_test if not retry_detail else f"{name_class_to_test}; {retry_detail}"
            utils.append_phase_log("evosuite_generate", project=project, arm="evosuite", focal_class=name_class_to_test.split(".")[-1], status="PASS", started_at=started_at, detail=detail)
            return True
        else:
            detail = command_output_tail(result_generate)
            if retry_detail:
                detail = f"{retry_detail}\n{detail}"
            utils.append_phase_log("evosuite_generate", project=project, arm="evosuite", focal_class=name_class_to_test.split(".")[-1], status="FAIL", started_at=started_at, detail=detail)
            return False
    except subprocess.TimeoutExpired as e:
        detail = f"EvoSuite generation timed out after {EVOSUITE_TIMEOUT_SECONDS}s\n{timeout_output_tail(e)}"
        utils.append_phase_log("evosuite_generate", arm="evosuite", status="ERROR", started_at=started_at, detail=detail)
        print(detail)
        return False
    except Exception as e:
        utils.append_phase_log("evosuite_generate", arm="evosuite", status="ERROR", started_at=started_at, detail=e)
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
        # Add a 'build' section
        build = ET.SubElement(root, 'build')

    # Check if there is only one 'plugins' section
    if len(build.findall('maven:plugins', ns)) == 1:
        plugins = build.find('maven:plugins', ns)
    else:
        # Add a 'plugins' section
        plugins = ET.SubElement(build, 'plugins')


    all_plugins_sections = root.findall('maven:build/maven:plugins', ns)
    for plugins_section in all_plugins_sections:
        for plugin in plugins_section.findall('maven:plugin', ns):
            group_id = plugin.find('maven:groupId', ns)
            artifact_id = plugin.find('maven:artifactId', ns)
            if group_id is None or artifact_id is None:
                continue
            if group_id.text == 'org.evosuite.plugins':
                # Remove the 'evosuite' plugin
                plugins.remove(plugin)
            if artifact_id.text == 'maven-surefire-plugin':
                plugins.remove(plugin)

    # add surefire plugin
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


    # EvoSuite generation is executed with the local CLI jar. Do not add the
    # evosuite-maven-plugin because version 1.2.0 is not reliably resolvable
    # from Maven Central.

    # Check if there is only one 'dependencies' section
    if len(root.findall('maven:dependencies', ns)) == 1:
        evosuite_dependencies_root = root.find('maven:dependencies', ns)
    else:
        # Add a 'dependencies' section
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
    evosuite_dependency_system_path.text = toolchains.evosuite_runtime_jar().replace("\\", "/")

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
        tools_dependency_system_path.text = tools_jar.replace("\\", "/")

    # Write the changes to the 'pom.xml' file
    write_pom_tree(tree_new, pom_path)
    return tree_old



def process_maven_project(project, test_types, techniques, project_path, project_df, compiler_version, java_version, junit_version, testng_version, has_mockito, system, correct, project_structure, project_dependencies):
    """
    It processes the given Maven project with the given test types and techniques.
    Parameters:
                project: the ID of the project.
                test_types (List): the list of test types to execute.
                techniques (List): the list of prompt techniques (for the AI test types) to execute.
                project_path: the path of the project. 
                project_df: the dataframe that contains all the focal/test classes of the project.
                compilter_version: the Maven version of the given project.
                java_version: the Java version of the given project.
                junit_version: the Junit version of the given project.
                testng_version: the testNG version of the given project.
                has_mockito: the string that will be used to specify to the API whether the AI test types can use the Mockito framework or not.
                system (String): the current OS (Windows, Linux, etc...)
    Returns:
                0(int) if the process failed.
    """
    swtich_to_next_project = False
    # add jacoco and pitest dependecies to pom.xml
    original_pom = edit_pom_file(project_path, project_df, junit_version, testng_version)
    if original_pom is None:
        print("An errore occured while trying to edit the pom file")
        return 0 # Switch to the next project
    for i, test_type in enumerate(test_types):
        output_path_failed = f'./output/{project}/TestClasses_{project}_{test_type}.failed' # Indicates that the test type failed due to an error during the execution of the script.
        output_path_failed_maven = f'./output/{project}/TestClasses_{project}_{test_type}.mavenfailed'  # Indicates that all the test classes of the test type failed during the maven execution.
        swtich_to_next_test_type = False
        print('\n----')
        print(f"STARTING '{test_type}' test type\n")
        if test_type == "human":
            # configure the test smell detector
            csv_path_input_test_smell = utils.configure_test_smell_detector(project_df, project)
            # Run the Maven package command
            print("--//loading maven execution..//")
            if run_maven_test_command(project_path, project_df, system)[0]==True:
                print(f"[INFO] Package command completed for {project}\n")
            else:
                print(f"Package command failed for {project}. Switch to next project...\n")
                write_pom_tree(original_pom, os.path.join(project_path, "pom.xml")) # restore pom to previous version
                swtich_to_next_project = True
                break # analyze the next project

            # Run the test smell detector
            path_csv_result_test_smell = utils.run_test_smell_detector(csv_path_input_test_smell, project, test_type, None)
            if path_csv_result_test_smell is None:
                print("An error occured while trying to run the test smell detector")
            else:
                print("The test smell detector ended successfully")  
            # Retrieve Code Coverage and Cyclomatic Complexity on test classes
            measures_df = utils.retrieve_code_coverage_and_cyclomatic_complexity(project_path, project_df, project, 'Maven')
            if measures_df is None:
                print(f"Switch to next project because edit_pom_xml() failed for the project {project}")
                write_pom_tree(original_pom, os.path.join(project_path, "pom.xml")) # restore pom to previous version
                swtich_to_next_project = True
                break # Switch to next project
            output_csv_path = utils.generate_output_csv_test_type(project, test_type, None, measures_df, path_csv_result_test_smell)
            if output_csv_path is None:
                print("An errore occured while trying to save the test type csv file!")
            else:
                print(f"DataFrame saved to {output_csv_path}")

        elif test_type == 'evosuite':
            project_df_evosuite = project_df.copy() # dataframe for the evosuite test type
            pom_before_evosuite = add_evosuite_pom(project_path)
            if pom_before_evosuite is None:
                try:
                    with open(output_path_failed, 'w') as file:
                        pass
                except Exception as e:
                        print(f'An error occured while trying to open output_path_failed: {e}')
                        sys.exit(1)
                continue # Switch to next test type
            dictionary_for_restore = {} # dictionary that contains test_path as keys and the respective 'human_test_class' as values. This dictionary is used to restore the test classes to the human version.
            for index, row in project_df_evosuite.iterrows(): # iterate over each test class and focal class
                name_focal_class = row['Focal_Class']
                name_test_class = row['Test_Class']
                test_path = row['Test_Path'].replace('repos/', 'compiledrepos/')
                focal_path = row['Focal_Path'].replace('repos/', 'compiledrepos/')
                last_execution = None # outcome of the last maven execution, True = Build Success, False = Build Failure
                current_module = utils.find_module_class(project, test_path)
                try:
                    human_test_class = utils.read_text_file(test_path) # save the human version of the test class
                    dictionary_for_restore[test_path] =  human_test_class
                    os.remove(test_path)

                except Exception as e:
                    print(f"An error occured while trying to open and read the test_path: {e}")
                    try:
                        write_pom_tree(pom_before_evosuite, os.path.join(project_path, "pom.xml")) # restore pom to previous version
                        utils.remove_evosuite_scaffolding_files(list(dictionary_for_restore.keys()))
                        utils.write_files(dictionary_for_restore)
                        with open(output_path_failed, 'w') as file:
                            pass
                    except Exception as e:
                        write_pom_tree(original_pom, os.path.join(project_path, "pom.xml")) # restore pom to previous version
                        utils.remove_evosuite_scaffolding_files(list(dictionary_for_restore.keys()))
                        utils.write_files(dictionary_for_restore)
                        print(f'An error occured while trying to open output_path_failed: {e}')
                        sys.exit(1)
                    swtich_to_next_test_type = True # Switch to next test type
                    break
                
                
                print("--//loading evosuite generation..//")
                if run_evosuite_generation_maven(project_path, focal_path, system) == False: # if error while running evosuite
                    print ("An error accored while trying to run the evosuite generation")
                    try:
                        utils.remove_evosuite_scaffolding_files(list(dictionary_for_restore.keys()))
                        utils.write_files(dictionary_for_restore)
                        write_pom_tree(pom_before_evosuite, os.path.join(project_path, "pom.xml")) # restore pom to previous version
                        with open(output_path_failed, 'w') as file:
                            pass
                    except Exception as e:
                        write_pom_tree(original_pom, os.path.join(project_path, "pom.xml")) # restore pom to previous version
                        utils.remove_evosuite_scaffolding_files(list(dictionary_for_restore.keys()))
                        utils.write_files(dictionary_for_restore)
                        print(f'An error occured while trying to open output_path_failed: {e}')
                        sys.exit(1)
                    swtich_to_next_test_type = True
                    break # Switch to next test type
                else:
                    print(f"Evosuite generation performed correctly for the '{name_focal_class}' class")

                evosuite_test_path = test_path.replace(f'{name_test_class}.java', f'{name_focal_class}_ESTest.java')
                try:
                    if not os.path.exists(evosuite_test_path):
                        project_df_evosuite = project_df_evosuite[project_df_evosuite['Test_Path'] != row['Test_Path']] # Delete the row from the DataFrame that corresponds to the test class causing an error during Maven execution
                        utils.remove_evosuite_scaffolding_files(list(test_path))
                        utils.write_file(test_path, human_test_class) # Restore to human version the test class causing an error during Maven execution
                        utils.remove_dot_evosuite_dir(project, current_module)
                        continue # Switch to next focal class/test class
                    evosuite_content = utils.read_text_file(evosuite_test_path)
                    evosuite_content = evosuite_content.replace(f'public class {name_focal_class}_ESTest', f'public class {name_test_class}') 
                    evosuite_content = evosuite_content.replace('separateClassLoader = true', 'separateClassLoader = false') # when setting separateClassLoader to false, JaCoCo can correctly calculate code coverage
                    utils.save_generated_test(project, 'evosuite', None, name_test_class, evosuite_content)
                    utils.write_text_file(test_path, evosuite_content)
                    os.remove(evosuite_test_path)
                except Exception as e:
                    print(f"An error occured while trying to copy the evosuite class test: {e}")
                    try:
                        write_pom_tree(pom_before_evosuite, os.path.join(project_path, "pom.xml")) # restore pom to previous version
                        utils.remove_evosuite_scaffolding_files(list(dictionary_for_restore.keys()))
                        utils.write_files(dictionary_for_restore)
                        utils.remove_dot_evosuite_dir(project, current_module)
                        with open(output_path_failed, 'w') as file:
                            pass
                    except Exception as e:
                        write_pom_tree(original_pom, os.path.join(project_path, "pom.xml")) # restore pom to previous version
                        utils.remove_evosuite_scaffolding_files(list(dictionary_for_restore.keys()))
                        utils.write_files(dictionary_for_restore)
                        utils.remove_dot_evosuite_dir(project, current_module)
                        print(f'An error occured while trying to open output_path_failed: {e}')
                        sys.exit(1)
                    swtich_to_next_test_type = True
                    break # Switch to next test type
                print("--//loading maven execution..//")
                if run_maven_test_command(project_path, project_df, system)[0]==False: # if error while running maven
                    print(f"Package command failed for project: {project}, test type: {test_type}\n")
                    project_df_evosuite = project_df_evosuite[project_df_evosuite['Test_Path'] != row['Test_Path']] # Delete the row from the DataFrame that corresponds to the test class causing an error during Maven execution
                    utils.remove_evosuite_scaffolding_files(list(test_path))
                    utils.write_file(test_path, human_test_class) # Restore to human version the test class causing an error during Maven execution
                    utils.remove_dot_evosuite_dir(project, current_module)
                    last_execution = False
                    continue # Switch to next focal class/test class
                else:
                    last_execution = True
                    print(f"Package command completed for {project}\n")

                utils.remove_dot_evosuite_dir(project, current_module)
                
            if swtich_to_next_test_type == True:
                continue

                
                    
            if project_df_evosuite.empty: # If all the test classes provided by Evosuite failed during Maven execution
                try:
                    with open(output_path_failed_maven, 'w') as file:
                        pass
                except Exception as e:
                    write_pom_tree(original_pom, os.path.join(project_path, "pom.xml")) # restore pom to previous version
                    utils.write_files(dictionary_for_restore)
                    utils.remove_evosuite_scaffolding_files(list(dictionary_for_restore.keys()))
                    print(f'An error occured while trying to open output_path_failed_maven: {e}')
                    sys.exit(1)
            else: # if at least one of the test classes provided by Evosuite runned succesfully during Maven execution
                # configure the test smell detector
                csv_path_input_test_smell = utils.configure_test_smell_detector(project_df_evosuite, project)
                # Run the test smell detector
                path_csv_result_test_smell = utils.run_test_smell_detector(csv_path_input_test_smell, project, test_type, None)
                if path_csv_result_test_smell is None:
                    print("An error occured while trying to run the test smell detector")
                else:
                    print("The test smell detector ended successfully")  
                if last_execution == False: # if last maven execution outcome is False, then I run one more time maven
                    print("--//loading maven execution..//")
                    if run_maven_test_command(project_path, project_df, system)[0]==False: # if error while running maven
                        print('An error occured while trying to execute the final version of test classes.\n')
                        try:
                            write_pom_tree(pom_before_evosuite, os.path.join(project_path, "pom.xml")) # restore pom to previous version
                            utils.remove_evosuite_scaffolding_files(list(dictionary_for_restore.keys()))
                            utils.write_files(dictionary_for_restore)
                            with open(output_path_failed, 'w') as file:
                                pass
                        except Exception as e:
                            write_pom_tree(original_pom, os.path.join(project_path, "pom.xml")) # restore pom to previous version
                            utils.remove_evosuite_scaffolding_files(list(dictionary_for_restore.keys()))
                            utils.write_files(dictionary_for_restore)
                            print(f'An error occured while trying to open output_path_failed: {e}')
                            sys.exit(1)
                        continue # Switch to next test type
                # Retrieve Code Coverage and Cyclomatic Complexity on test classes
                measures_df  = utils.retrieve_code_coverage_and_cyclomatic_complexity(project_path, project_df_evosuite, project, 'Maven')
                if measures_df is not None:
                    output_csv_path = utils.generate_output_csv_test_type(project, test_type, None, measures_df, path_csv_result_test_smell)
                    if output_csv_path is None:
                        print("An errore occured while trying to save the test type csv file!")
                    else:
                        print(f"DataFrame saved to {output_csv_path}")
                else:
                    print(f"An occured while trying to retrieve data coverage fo the project {project}")
                    try:
                        with open(output_path_failed, 'w') as file:
                            pass
                    except Exception as e:
                        write_pom_tree(original_pom, os.path.join(project_path, "pom.xml")) # restore pom to previous version
                        utils.remove_evosuite_scaffolding_files(list(dictionary_for_restore.keys()))
                        utils.write_files(dictionary_for_restore)
                        print(f'An error occured while trying to open output_path_failed: {e}')
                        sys.exit(1)
                
            utils.write_files(dictionary_for_restore)
            utils.remove_evosuite_scaffolding_files(list(dictionary_for_restore.keys()))
            write_pom_tree(pom_before_evosuite, os.path.join(project_path, "pom.xml")) # restore pom to previous version
                    



        else:
            # Iterate over each technique
            for j, technique in enumerate(techniques):
                global df_chance
                output_path_failed = f'./output/{project}/TestClasses_{project}_{test_type}_{technique}.failed' # Indicates that a test type/technique failed due to an error during the execution of AgonTest.py or during a call to the API
                output_path_failed_maven = f'./output/{project}/TestClasses_{project}_{test_type}_{technique}.mavenfailed' # Indicates that all the test classes of the test type failed during the maven execution.

                restart_technique = False 
                print(f"\nProcessing test_type: {test_type}, technique: {technique}")
                project_df_technique = project_df.copy() # dataframe of the current test type and technique
                dictionary_for_restore = {} # dictionary that contains test_path as keys and the respective 'human_test_class' as values. This dictionary is used to restore the test classes to the human version.
                for index, row in project_df_technique.iterrows(): # iterate over each test class and focal class
                    name_focal_class = row['Focal_Class']
                    name_test_class = row['Test_Class']
                    if "repos/" in row['Test_Path']:
                        test_path = row['Test_Path'].replace("repos/", "compiledrepos/")
                        focal_path = row['Focal_Path'].replace("repos/", "compiledrepos/")
                    else:
                        project = row['Project']
                        test_path = f"compiledrepos/{project}/" + row['Test_Path']
                        focal_path = f"compiledrepos/{project}/" + row['Focal_Path']
                    last_execution = None # outcome of the last maven execution, True = Build Success, False = Build Failure
                    testing_framework = None
                    if junit_version is not None:
                        testing_framework = 'Junit version ' + junit_version
                    elif testng_version is not None:
                        testing_framework = 'testNG version ' + testng_version
                    try:
                        focal_class = utils.read_text_file(focal_path)
                    except Exception as e:
                        print(f"An error occured while trying to open and read the focal class: {e}")
                        try:
                            utils.write_files(dictionary_for_restore)
                            with open(output_path_failed, 'w') as file:
                                pass
                        except Exception as e:
                            write_pom_tree(original_pom, os.path.join(project_path, "pom.xml")) # restore pom to previous version
                            utils.write_files(dictionary_for_restore)
                            print(f'An error occured while trying to open output_path_failed: {e}')
                            sys.exit(1)
                        restart_technique = True # Switch to next technique
                        break 
                    

                    # Make the appropriate API call and get the response
                    print(f"\nMaking API call with llm: {test_type}, technique: {technique}, focal class: {name_focal_class}")
                    package_test_class = utils.find_package(test_path)
                    response, messages = utils.make_api_call(test_type, technique, focal_class, focal_path, testing_framework, java_version, has_mockito, test_path, name_test_class, project_structure, project_dependencies, package_test_class)
                    print(f"API call completed with test_type: {test_type}, technique: {technique}, focal class: {name_focal_class}")
                    if response is None:
                        print(f"ERROR: Anomalous response from the call to the API: {response}")
                        try:
                            utils.write_files(dictionary_for_restore)
                            with open(output_path_failed, 'w') as file:
                                pass
                        except Exception as e:
                            write_pom_tree(original_pom, os.path.join(project_path, "pom.xml")) # restore pom to previous version
                            utils.write_files(dictionary_for_restore)
                            print(f'An error occured while trying to open output_path_failed: {e}')
                            sys.exit(1)
                        restart_technique = True # Switch to next technique
                        break 
                    
                    # Create the file and write the reponse to it
                    try:
                        human_test_class = utils.read_text_file(test_path) # save the human version of the test class
                        dictionary_for_restore[test_path] =  human_test_class
                        utils.write_text_file(test_path, response) # overwrite the test class
                        api_output_file_path = f'output/{project}/response_{test_type}_{technique}_{name_test_class}.java'
                        utils.write_text_file(api_output_file_path, response)
                        print(f"File generated at: {api_output_file_path}")
                    except Exception as e:
                        print(f"An error occured while trying to open and read the test_path: {e}")
                        try:
                            utils.write_files(dictionary_for_restore)
                            with open(output_path_failed, 'w') as file:
                                pass
                        except Exception as e:
                            write_pom_tree(original_pom, os.path.join(project_path, "pom.xml")) # restore pom to previous version
                            utils.write_files(dictionary_for_restore)
                            print(f'An error occured while trying to open output_path_failed: {e}')
                            sys.exit(1)
                        restart_technique = True # Switch to next technique
                        break


                    # Run the Maven package command
                    print("--//loading maven execution..//")
                    esito, errori = run_maven_test_command(project_path, project_df, system)
                    if not esito and correct:  # Se il test Maven fallisce
                        chance_result = False
                        for num_chance in range(1, 5):
                            if chance_result:
                                df_chance = pd.concat([df_chance, pd.DataFrame([{'Test_Class': name_test_class, 'Test_Path': test_path, 'Chance': num_chance}])], ignore_index=True)
                                break
                            chance_result, errori = errorCorrection.correct_errors(project, test_type, technique, test_path, project_path, project_df, system, messages, errori, dictionary_for_restore, num_chance, "Maven")
                        errorCorrection.save_conversation_to_json(messages, name_test_class, f"/Users/nicomede/Desktop/classes2test_private 2/compiledrepos/{project}")
                        if not chance_result:
                            df_chance = pd.concat([df_chance, pd.DataFrame([{'Test_Class': name_test_class, 'Test_Path': test_path, 'Chance': 6}])], ignore_index=True)
                    elif not esito and not correct:
                        print(f"Package command failed for project: {project}, test type: {test_type}, technique: {technique}\n")
                    elif esito:
                        last_execution = True
                        print(f"Package command completed for {project}\n")
                        df_chance = pd.concat([df_chance, pd.DataFrame([{'Test_Class': name_test_class, 'Test_Path': test_path, 'Chance': 0}])], ignore_index=True)

                if restart_technique == True:
                    continue

                    
                if project_df_technique.empty: # If all the test classes provided by the API failed during Maven execution
                    try:
                        with open(output_path_failed_maven, 'w') as file:
                            pass
                    except Exception as e:
                        write_pom_tree(original_pom, os.path.join(project_path, "pom.xml")) # restore pom to previous version
                        utils.write_files(dictionary_for_restore)
                        print(f'An error occured while trying to open output_path_failed_maven: {e}')
                        sys.exit()
                else: # if at least one of the test classes provided by the API runned succesfully during Maven execution
                    # configure the test smell detector
                    csv_path_input_test_smell = utils.configure_test_smell_detector(project_df_technique, project)
                    # Run the test smell detector
                    path_csv_result_test_smell = utils.run_test_smell_detector(csv_path_input_test_smell, project, test_type, technique)
                    if path_csv_result_test_smell is None:
                        print("An error occured while trying to run the test smell detector")
                    else:
                        print("The test smell detector ended successfully")  
                    if last_execution == False: # if last maven execution outcome is False, then I run one more time maven
                        print("--//loading maven execution..//")
                        if run_maven_test_command(project_path, project_df, system)[0]==False: # if error while running maven
                            print('An error occured while trying to execute the final version of test classes.\n')
                            try:
                                utils.write_files(dictionary_for_restore)
                                with open(output_path_failed, 'w') as file:
                                    pass
                            except Exception as e:
                                write_pom_tree(original_pom, os.path.join(project_path, "pom.xml")) # restore pom to previous version
                                utils.write_files(dictionary_for_restore)
                                print(f'An error occured while trying to open output_path_failed: {e}')
                                sys.exit(1)
                            continue  # switch to next technique      
                    # Retrieve Code Coverage and Cyclomatic Complexity on test classes                            
                    measures_df  = utils.retrieve_code_coverage_and_cyclomatic_complexity(project_path, project_df_technique, project, 'Maven')
                    if measures_df is not None:
                        output_csv_path = utils.generate_output_csv_test_type(project, test_type, technique, measures_df, path_csv_result_test_smell)
                        if output_csv_path is None:
                            print("An errore occured while trying to save the test type csv file!")
                        else:
                            print(f"DataFrame saved to {output_csv_path}")
                    else:
                        print(f"An occured while trying to retrieve data coverage of the project {project}")
                        try:
                            with open(output_path_failed, 'w') as file:
                                pass
                        except Exception as e:
                            write_pom_tree(original_pom, os.path.join(project_path, "pom.xml")) # restore pom to previous version
                            utils.write_files(dictionary_for_restore)
                            print(f'An error occured while trying to open output_path_failed: {e}')
                            sys.exit(1)
                    utils.write_files(dictionary_for_restore)
    if swtich_to_next_project == True:
        return 0
    write_pom_tree(original_pom, os.path.join(project_path, "pom.xml")) # restore pom to the original version



def process_maven_module(project, module, test_types, techniques, path, project_path, module_df, compiler_version, java_version, junit_version, testng_version, has_mockito, system, project_structure, project_dependencies):
    """
    It processes the given Maven module with the given test types and techniques.
    Parameters:
                project: the ID of the project.
                module: the name of the module.
                test_types (List): the list of test types to execute.
                techniques (List): the list of prompt techniques (for the AI test types) to execute.
                path: the path of the module. 
                projecty_path: the path of the project.
                module_df: the dataframe that contains all the focal/test classes of the module.
                compilter_version: the Maven version of the given project.
                java_version: the Java version of the given project.
                junit_version: the Junit version of the given project.
                testng_version: the testNG version of the given project.
                has_mockito: the string that will be used to specify to the API whether the AI test types can use the Mockito framework or not.
                system (String): the current OS (Windows, Linux, etc...)
    Returns:
                0(int) if the process failed.
    """
    # add jacoco and pitest dependecies to pom.xml
    original_pom = edit_pom_file(path, module_df, junit_version, testng_version)
    if original_pom is None:
        print("An errore occured while trying to edit the pom file")
        return 0
    for test_type in test_types:
        output_path_failed = f'./output/{project}/TestClasses_{project}_{test_type}.failed' # Indicates that the test type failed due to an error during the execution of the script.
        output_path_failed_maven = f'./output/{project}/TestClasses_{project}_{test_type}.mavenfailed'  # Indicates that all the test classes of the test type failed during the maven execution.

        swtich_to_next_test_type = False
        print('\n----')
        print(f"STARTING {test_type} test typ\n")
        if test_type == "human":
            # configure the test smell detector
            csv_path_input_test_smell = utils.configure_test_smell_detector(module_df, project)
            # Run the Maven package command
            print("--//loading maven execution..//")
            if run_maven_test_command(path, module_df, system)[0]==True:
                print(f"Package command completed for {project}_{module}\n")
            else:
                print(f"Package command failed for {project}_{module}. Switch to next project/module...\n")
                write_pom_tree(original_pom, os.path.join(path, "pom.xml")) # restore pom to previous version
                return 0 # analyze the next module

            # Run the test smell detector
            path_csv_result_test_smell = utils.run_test_smell_detector(csv_path_input_test_smell, project, test_type, None, module)
            if path_csv_result_test_smell is None:
                print("An error occured while trying to run the test smell detector")
            else:
                print("The test smell detector ended successfully")  
            # Retrieve Code Coverage and Cyclomatic Complexity on test classes
            measures_df = utils.retrieve_code_coverage_and_cyclomatic_complexity(f'compiledrepos/{project}', module_df, project, 'Maven', module)
            if measures_df is None:
                print(f"Switch to next project/module because edit_pom_xml() failed for the project {project}_{module}")
                write_pom_tree(original_pom, os.path.join(path, "pom.xml")) # restore pom to previous version
                return 0
            output_csv_path = utils.generate_output_csv_test_type(project, test_type, None, measures_df, path_csv_result_test_smell, module)
            if output_csv_path is None:
                print("An errore occured while trying to save the test type csv file!")
            else:
                print(f"DataFrame saved to {output_csv_path}")

        elif test_type == 'evosuite':
            module_df_evosuite = module_df.copy() # dataframe for the evosuite test type
            pom_before_evosuite = add_evosuite_pom(path)
            if pom_before_evosuite is None:
                try:
                    with open(output_path_failed, 'w') as file:
                        pass
                except Exception as e:
                        print(f'An error occured while trying to open output_path_failed: {e}')
                        sys.exit(1)
                continue # Switch to next test type
            dictionary_for_restore = {} # dictionary that contains test_path as keys and the respective 'human_test_class' as values. This dictionary is used to restore the test classes to the human version.
            for index, row in module_df_evosuite.iterrows(): # iterate over each test class and focal class
                name_focal_class = row['Focal_Class']
                name_test_class = row['Test_Class']
                test_path = row['Test_Path'].replace('repos/', 'compiledrepos/')
                focal_path = row['Focal_Path'].replace('repos/', 'compiledrepos/')
                last_execution = None # outcome of the last maven execution, True = Build Success, False = Build Failure
                try:
                    human_test_class = utils.read_text_file(test_path) # save the human version of the test class
                    dictionary_for_restore[test_path] =  human_test_class
                    os.remove(test_path)      
                except Exception as e:
                    print(f"An error occured while trying to open and read the test_path: {e}")
                    try:
                        write_pom_tree(pom_before_evosuite, os.path.join(path, "pom.xml")) # restore pom to previous version
                        utils.remove_evosuite_scaffolding_files(list(dictionary_for_restore.keys()))
                        utils.write_files(dictionary_for_restore)
                        with open(output_path_failed, 'w') as file:
                            pass
                    except Exception as e: 
                        write_pom_tree(original_pom, os.path.join(path, "pom.xml")) # restore pom to previous version
                        utils.remove_evosuite_scaffolding_files(list(dictionary_for_restore.keys()))
                        utils.write_files(dictionary_for_restore)
                        print(f'An error occured while trying to open output_path_failed: {e}')
                        sys.exit(1)
                    swtich_to_next_test_type = True # Switch to next test type
                    break
                
                print("--//loading evosuite generation..//")
                if run_evosuite_generation_maven(path, focal_path, system) == False: # if error while running evosuite
                    print ("An error accored while trying to run the evosuite generation")
                    try:
                        utils.remove_evosuite_scaffolding_files(list(dictionary_for_restore.keys()))
                        utils.write_files(dictionary_for_restore)
                        write_pom_tree(pom_before_evosuite, os.path.join(path, "pom.xml")) # restore pom to previous version
                        with open(output_path_failed, 'w') as file:
                            pass
                    except Exception as e:
                        write_pom_tree(original_pom, os.path.join(path, "pom.xml")) # restore pom to previous version
                        utils.remove_evosuite_scaffolding_files(list(dictionary_for_restore.keys()))
                        utils.write_files(dictionary_for_restore)
                        print(f'An error occured while trying to open output_path_failed: {e}')
                        sys.exit(1)
                    swtich_to_next_test_type = True
                    break # Switch to next test type
                else:
                    print(f"Evosuite generation performed correctly for the {name_focal_class} class")

                evosuite_test_path = test_path.replace(f'{name_test_class}.java', f'{name_focal_class}_ESTest.java')
                try:
                    if not os.path.exists(evosuite_test_path):
                        project_df_evosuite = project_df_evosuite[project_df_evosuite['Test_Path'] != row['Test_Path']] # Delete the row from the DataFrame that corresponds to the test class causing an error during Maven execution
                        utils.remove_evosuite_scaffolding_files(list(test_path))
                        utils.write_file(test_path, human_test_class) # Restore to human version the test class causing an error during Maven execution
                        utils.remove_dot_evosuite_dir(project, module)
                        continue # Switch to next focal class/test class
                    evosuite_content = utils.read_text_file(evosuite_test_path)
                    evosuite_content = evosuite_content.replace(f'public class {name_focal_class}_ESTest', f'public class {name_test_class}') 
                    evosuite_content = evosuite_content.replace('separateClassLoader = true', 'separateClassLoader = false') # when setting separateClassLoader to false, JaCoCo can correctly calculate code coverage
                    utils.save_generated_test(project, 'evosuite', None, name_test_class, evosuite_content)
                    utils.write_text_file(test_path, evosuite_content)
                    os.remove(evosuite_test_path)
                except Exception as e:
                    print(f"An error occured while trying to copy the evosuite class test: {e}")
                    try:
                        write_pom_tree(pom_before_evosuite, os.path.join(path, "pom.xml")) # restore pom to previous version
                        utils.remove_evosuite_scaffolding_files(list(dictionary_for_restore.keys()))
                        utils.write_files(dictionary_for_restore)
                        utils.remove_dot_evosuite_dir(project, module)
                        with open(output_path_failed, 'w') as file:
                            pass
                    except Exception as e:
                        write_pom_tree(original_pom, os.path.join(path, "pom.xml")) # restore pom to previous version
                        utils.remove_evosuite_scaffolding_files(list(dictionary_for_restore.keys()))
                        utils.write_files(dictionary_for_restore)
                        utils.remove_dot_evosuite_dir(project, module)
                        print(f'An error occured while trying to open output_path_failed: {e}')
                        sys.exit(1)
                    swtich_to_next_test_type = True
                    break # Switch to next test type
                print("--//loading maven execution..//")
                if run_maven_test_command(path, module_df, system)[0]==False: # if error while running maven
                    print(f"Package command failed for project: {project}_{module}, test type: {test_type}\n")
                    module_df_evosuite = module_df_evosuite[module_df_evosuite['Test_Path'] != row['Test_Path']] # Delete the row from the DataFrame that corresponds to the test class causing an error during Maven execution
                    utils.remove_evosuite_scaffolding_files(list(test_path))
                    utils.write_file(test_path, human_test_class) # Restore to human version the test class causing an error during Maven execution
                    utils.remove_dot_evosuite_dir(project, module)
                    last_execution = False
                    continue # Switch to next focal class/test class
                else:
                    last_execution = True
                    print(f"Package command completed for {project}_{module}\n")

                utils.remove_dot_evosuite_dir(project, module)
                
            if swtich_to_next_test_type == True:
                continue

                
                    
            if module_df_evosuite.empty: # If all the test classes provided by Evosuite failed during Maven execution
                try:
                    with open(output_path_failed_maven, 'w') as file:
                        pass
                except Exception as e:
                    write_pom_tree(original_pom, os.path.join(path, "pom.xml")) # restore pom to previous version
                    utils.write_files(dictionary_for_restore)
                    utils.remove_evosuite_scaffolding_files(list(dictionary_for_restore.keys()))
                    print(f'An error occured while trying to open output_path_failed_maven: {e}')
                    sys.exit(1)
            else: # if at least one of the test classes provided by Evosuite runned succesfully during Maven execution
                # configure the test smell detector
                csv_path_input_test_smell = utils.configure_test_smell_detector(module_df_evosuite, project)
                # Run the test smell detector
                path_csv_result_test_smell = utils.run_test_smell_detector(csv_path_input_test_smell, project, test_type, None, module)
                if path_csv_result_test_smell is None:
                    print("An error occured while trying to run the test smell detector")
                else:
                    print("The test smell detector ended successfully")  
                if last_execution == False: # if last maven execution outcome is False, then I run one more time maven
                    print("--//loading maven execution..//")
                    if run_maven_test_command(path, module_df, system)[0]==False: # if error while running maven
                        print('An error occured while trying to execute the final version of test classes.\n')
                        try:
                            write_pom_tree(pom_before_evosuite, os.path.join(path, "pom.xml")) # restore pom to previous version
                            utils.remove_evosuite_scaffolding_files(list(dictionary_for_restore.keys()))
                            utils.write_files(dictionary_for_restore)
                            with open(output_path_failed, 'w') as file:
                                pass
                        except Exception as e:
                            write_pom_tree(original_pom, os.path.join(path, "pom.xml")) # restore pom to previous version
                            utils.remove_evosuite_scaffolding_files(list(dictionary_for_restore.keys()))
                            utils.write_files(dictionary_for_restore)
                            print(f'An error occured while trying to open output_path_failed: {e}')
                            sys.exit(1)
                        continue # Switch to next test type
                # Retrieve Code Coverage and Cyclomatic Complexity on test classes
                measures_df  = utils.retrieve_code_coverage_and_cyclomatic_complexity(f'compiledrepos/{project}', module_df_evosuite, project, 'Maven', module)
                if measures_df is not None:
                    output_csv_path = utils.generate_output_csv_test_type(project, test_type, None, measures_df, path_csv_result_test_smell, module)
                    if output_csv_path is None:
                        print("An errore occured while trying to save the test type csv file!")
                    else:
                        print(f"DataFrame saved to {output_csv_path}")
                else:
                    print(f"An occured while trying to retrieve data coverage of the project {project}_{module}")
                    try:
                        with open(output_path_failed, 'w') as file:
                            pass
                    except Exception as e:
                        write_pom_tree(original_pom, os.path.join(path, "pom.xml")) # restore pom to previous version
                        utils.remove_evosuite_scaffolding_files(list(dictionary_for_restore.keys()))
                        utils.write_files(dictionary_for_restore)
                        print(f'An error occured while trying to open output_path_failed: {e}')
                        sys.exit(1)
                
            utils.write_files(dictionary_for_restore)
            utils.remove_evosuite_scaffolding_files(list(dictionary_for_restore.keys()))
            write_pom_tree(pom_before_evosuite, os.path.join(path, "pom.xml")) # restore pom to previous version
                    



        else:
            # Iterate over each technique
            for technique in techniques:  
                output_path_failed = f'./output/{project}/TestClasses_{project}_{test_type}_{technique}.failed' # Indicates that the test type/technique failed due to an error during the execution of AgonTest.py or during a call to the API
                output_path_failed_maven = f'./output/{project}/TestClasses_{project}_{test_type}_{technique}.mavenfailed'  # Indicates that all the test classes of the test type failed during the maven execution. 
                restart_technique = False 
                print(f"\nProcessing test_type: {test_type}, technique: {technique}")
                module_df_technique = module_df.copy() # dataframe of the current test type and technique
                dictionary_for_restore = {} # dictionary that contains test_path as keys and the respective 'human_test_class' as values. This dictionary is used to restore the test classes to the human version.
                for index, row in module_df_technique.iterrows(): # iterate over each test class and focal class
                    name_focal_class = row['Focal_Class']
                    name_test_class = row['Test_Class']
                    focal_path = row['Focal_Path'].replace('repos/', 'compiledrepos/')
                    test_path = row['Test_Path'].replace('repos/', 'compiledrepos/')
                    last_execution = None # outcome of the last maven execution, True = Build Success, False = Build Failure
                    testing_framework = None
                    if junit_version is not None:
                        testing_framework = 'Junit version ' + junit_version
                    elif testng_version is not None:
                        testing_framework = 'testNG version ' + testng_version
                    try:
                        focal_class = utils.read_text_file(focal_path)
                    except Exception as e:
                        print(f"An error occured while trying to open and read the focal class: {e}")
                        try:
                            utils.write_files(dictionary_for_restore)
                            with open(output_path_failed, 'w') as file:
                                pass
                        except Exception as e:
                            write_pom_tree(original_pom, os.path.join(path, "pom.xml")) # restore pom to previous version
                            utils.write_files(dictionary_for_restore)
                            print(f'An error occured while trying to open output_path_failed: {e}')
                            sys.exit(1)
                        restart_technique = True #Switch to next technique
                        break 
                    
                    
                    # Make the appropriate API call and get the response
                    print(f"\nMaking API call with llm: {test_type}, technique: {technique}, focal class: {name_focal_class}")
                    package_test_class = utils.find_package(test_path)
                    response, messages = utils.make_api_call(test_type, technique, focal_class, focal_path, testing_framework, java_version, has_mockito, test_path, name_test_class, project_structure, project_dependencies, package_test_class)
                    print(f"API call completed with test_type: {test_type}, technique: {technique}, focal class: {name_focal_class}")
                    if response is None:
                        print(f"ERROR: Anomalous response from the call to the API: {response}")
                        try:
                            utils.write_files(dictionary_for_restore)
                            with open(output_path_failed, 'w') as file:
                                pass
                        except Exception as e:
                            write_pom_tree(original_pom, os.path.join(path, "pom.xml")) # restore pom to previous version
                            utils.write_files(dictionary_for_restore)
                            print(f'An error occured while trying to open output_path_failed: {e}')
                            sys.exit(1)
                        restart_technique = True # Switch to next technique
                        break 
                    
                    # Create the file and write the reponse to it
                    try:
                        human_test_class = utils.read_text_file(test_path) # save the human version of the test class
                        dictionary_for_restore[test_path] =  human_test_class
                        utils.write_text_file(test_path, response) # overwrite the test class
                        api_output_file_path = f'output/{project}/response_{test_type}_{technique}_{name_test_class}.java'
                        utils.write_text_file(api_output_file_path, response)
                        print(f"File generated at: {api_output_file_path}")
                    except Exception as e:
                        print(f"An error occured while trying to open and read the test_path: {e}")
                        try:
                            utils.write_files(dictionary_for_restore)
                            with open(output_path_failed, 'w') as file:
                                pass
                        except Exception as e:
                            write_pom_tree(original_pom, os.path.join(path, "pom.xml")) # restore pom to previous version
                            utils.write_files(dictionary_for_restore)
                            print(f'An error occured while trying to open output_path_failed: {e}')
                            sys.exit(1)
                        restart_technique = True # Switch to next technique
                        break 
                                

                    # Run the Maven package command
                    print("--//loading maven execution..//")
                    if run_maven_test_command(path, module_df, system)[0]==False: # if error while running maven
                        print(f"Package command failed for project: {project}_{module}, test type: {test_type}, technique: {technique}\n")
                        module_df_technique = module_df_technique [module_df_technique['Test_Path'] != row['Test_Path']] # Delete the row from the DataFrame that corresponds to the test class causing an error during Maven execution
                        utils.write_file(test_path, human_test_class) # Restore to human version the test class causing an error during Maven execution
                        last_execution = False
                        continue
                    else:
                        last_execution = True
                        print(f"Package command completed for {project}_{module}\n")

                if restart_technique == True:
                    continue

                    
                if module_df_technique.empty: # If all the test classes provided by the API failed during Maven execution
                    try:
                        with open(output_path_failed_maven, 'w') as file:
                            pass
                    except Exception as e:
                        write_pom_tree(original_pom, os.path.join(path, "pom.xml")) # restore pom to previous version
                        utils.write_files(dictionary_for_restore)
                        print(f'An error occured while trying to open output_path_failed_maven: {e}')
                        sys.exit()
                else: # if at least one of the test classes provided by the API runned succesfully during Maven execution
                    # configure the test smell detector
                    csv_path_input_test_smell = utils.configure_test_smell_detector(module_df_technique, project)
                    # Run the test smell detector
                    path_csv_result_test_smell = utils.run_test_smell_detector(csv_path_input_test_smell, project, test_type, technique, module)
                    if path_csv_result_test_smell is None:
                        print("An error occured while trying to run the test smell detector")
                    else:
                        print("The test smell detector ended successfully")  
                    if last_execution == False: # if last maven execution outcome is False, then I run one more time maven
                        print("--//loading maven execution..//")
                        if run_maven_test_command(path, module_df, system)[0]==False: # if error while running maven
                            print('An error occured while trying to execute the final version of test classes.\n')
                            try:
                                utils.write_files(dictionary_for_restore)
                                with open(output_path_failed, 'w') as file:
                                    pass
                            except Exception as e:
                                write_pom_tree(original_pom, os.path.join(path, "pom.xml")) # restore pom to previous version
                                utils.write_files(dictionary_for_restore)
                                print(f'An error occured while trying to open output_path_failed: {e}')
                                sys.exit(1)
                            continue  # switch to next technique      
                    # Retrieve Code Coverage and Cyclomatic Complexity on test classes
                    measures_df  = utils.retrieve_code_coverage_and_cyclomatic_complexity(project_path, module_df_technique, project, 'Maven', module)
                    if measures_df is not None:
                        output_csv_path = utils.generate_output_csv_test_type(project, test_type, technique, measures_df, path_csv_result_test_smell, module)
                        if output_csv_path is None:
                            print("An errore occured while trying to save the test type csv file!")
                        else:
                            print(f"DataFrame saved to {output_csv_path}")
                    else:
                        print(f"An errore occured while trying to retrieve data coverage of the project {project}_{module}")
                        try:
                            with open(output_path_failed, 'w') as file:
                                pass
                        except Exception as e:
                            write_pom_tree(original_pom, os.path.join(path, "pom.xml")) # restore pom to previous version
                            utils.write_files(dictionary_for_restore)
                            print(f'An error occured while trying to open output_path_failed: {e}')
                            sys.exit(1)
                    utils.write_files(dictionary_for_restore)
    write_pom_tree(original_pom, os.path.join(path, "pom.xml")) # restore pom to the original version 

