import re
import os
import subprocess
import sys
import time
from pathlib import Path

import errorCorrection
import utils
import shutil
import toolchains


EVOSUITE_TIMEOUT_SECONDS = int(os.getenv("RBL4_EVOSUITE_TIMEOUT_SECONDS", "240"))
GRADLE_PITEST_PLUGIN_VERSION_OVERRIDE = os.getenv("RBL4_GRADLE_PITEST_PLUGIN_VERSION", "").strip()
PITEST_JUNIT5_PLUGIN_VERSION = os.getenv("RBL4_PITEST_JUNIT5_PLUGIN_VERSION", "1.2.1")
PITEST_TESTNG_PLUGIN_VERSION = os.getenv("RBL4_PITEST_TESTNG_PLUGIN_VERSION", "1.0.0")
GRADLE_JACOCO_TOOL_VERSION = os.getenv("RBL4_GRADLE_JACOCO_TOOL_VERSION", "0.8.6")


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


def java_command():
    java_home = os.environ.get("JAVA_HOME")
    executable = "java.exe" if os.name == "nt" else "java"
    if java_home:
        candidate = Path(java_home) / "bin" / executable
        if candidate.exists():
            return str(candidate)
    return "java"


def is_testng_project(testng_version):
    return testng_version is not None and str(testng_version).strip() not in {"", "None", "none", "nan"}


def is_junit5_project(junit_version):
    return junit_version is not None and str(junit_version).strip().startswith("5")


def parse_gradle_version(compiler_version):
    match = re.search(r"(\d+)(?:\.(\d+))?", str(compiler_version or ""))
    if not match:
        return None
    major = int(match.group(1))
    minor = int(match.group(2) or 0)
    return major, minor


def gradle_version_at_least(compiler_version, major, minor=0):
    parsed = parse_gradle_version(compiler_version)
    if parsed is None:
        return True
    return parsed >= (major, minor)


def pitest_plugin_version_for_gradle(compiler_version):
    if GRADLE_PITEST_PLUGIN_VERSION_OVERRIDE:
        return GRADLE_PITEST_PLUGIN_VERSION_OVERRIDE
    parsed = parse_gradle_version(compiler_version)
    if parsed is None:
        return "1.15.0"
    if parsed < (4, 0):
        return "1.3.0"
    if parsed < (5, 6):
        return "1.4.0"
    if parsed < (6, 4):
        return "1.6.0"
    return "1.15.0"


def testng_pitest_dependency_for_plugin(pitest_plugin_version):
    parsed = parse_gradle_version(pitest_plugin_version)
    if parsed is None:
        return PITEST_TESTNG_PLUGIN_VERSION
    if parsed >= (1, 9):
        return PITEST_TESTNG_PLUGIN_VERSION
    if (1, 7) <= parsed < (1, 9):
        return "0.1"
    return None


def gradle_test_classes(project_dataframe):
    project_df = project_dataframe.copy()
    classes = []
    for test_path in project_df["Test_Path"].tolist():
        normalized = str(test_path).replace("\\", "/")
        if "test/java/" not in normalized:
            continue
        classes.append(normalized.split("test/java/", 1)[1].replace("/", ".").replace(".java", ""))
    return classes


def gradle_test_selector_args(test_classes):
    args = []
    for test_class in test_classes:
        args.extend(["--tests", test_class])
    return args


def gradle_test_include_patterns(test_classes):
    patterns = []
    for test_class in test_classes:
        simple_name = str(test_class).split(".")[-1]
        if simple_name:
            patterns.append(f"**/{simple_name}.class")
    return list(dict.fromkeys(patterns))


def gradle_quoted_list(test_classes):
    return ",".join("'" + test_class + "'" for test_class in test_classes)


def gradle_kts_quoted_list(test_classes):
    return ",".join('"' + test_class + '"' for test_class in test_classes)


def gradle_include_lines(patterns):
    return "".join(f"        include '{pattern}'\n" for pattern in patterns)


def gradle_include_lines_kts(patterns):
    return "".join(f'    include("{pattern}")\n' for pattern in patterns)


def resolve_generated_test_path(path, test_path):
    normalized = str(test_path or "").replace("\\", "/")
    candidates = [
        Path(normalized),
        Path(normalized.replace("repos/", "compiledrepos/", 1)),
    ]
    if "repos/" in normalized:
        rel = normalized.split("repos/", 1)[1]
        current = Path(path).resolve()
        for _ in range(8):
            candidates.append(current / "compiledrepos" / rel)
            candidates.append(current / rel)
            if current.parent == current:
                break
            current = current.parent
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def generated_tests_use_testng(path, project_dataframe):
    for test_path in project_dataframe.get("Test_Path", []):
        resolved = resolve_generated_test_path(path, test_path)
        if not resolved or not resolved.exists():
            continue
        try:
            text = resolved.read_text(encoding="utf-8", errors="replace").lower()
        except Exception:
            continue
        if "org.testng" in text or "testng.annotations" in text:
            return True
    return False


def gradle_command_with_common_exclusions(gradle_cmd, args, path, timeout):
    command = [gradle_cmd] + args + ["-x", "downloadPortal", "-x", "unzipPortal", "-x", "check"]
    result = subprocess.run(command, cwd=path, capture_output=True, text=True, timeout=timeout)
    combined_output = f"{result.stdout}\n{result.stderr}"
    missing_excluded_task = (
        "Task 'downloadPortal' not found" in combined_output
        or "Task 'unzipPortal' not found" in combined_output
        or "not found in root project" in combined_output
    )
    if result.returncode != 0 and missing_excluded_task:
        command = [gradle_cmd] + args + ["-x", "check"]
        result = subprocess.run(command, cwd=path, capture_output=True, text=True, timeout=timeout)
    return result


def normalize_gradle_rel_path(value):
    value = str(value or "").replace("\\", "/").strip()
    if value in {"", ".", "None", "none", "nan"}:
        return ""
    return value.strip("/")


def repo_root_from_module_path(path, module):
    current = Path(path).resolve()
    module_rel = normalize_gradle_rel_path(module)
    if module_rel:
        parts = Path(module_rel).parts
        for _ in parts:
            current = current.parent
        return current
    if current.name == "compiledrepos":
        return current
    return current


def gradle_task_prefix(module_selector):
    selector = normalize_gradle_rel_path(module_selector)
    if not selector:
        return ""
    return ":" + selector.replace("/", ":") + ":"


def gradle_execution_context(path, project_dataframe):
    project_df = project_dataframe.copy()
    if project_df.empty:
        return Path(path).resolve(), ""
    first = project_df.iloc[0]
    module = first.get("Module", "")
    build_root = normalize_gradle_rel_path(first.get("Build_Root", ""))
    module_selector = first.get("Module_Selector", "")
    repo_root = repo_root_from_module_path(path, module)
    if build_root:
        execution_dir = repo_root / build_root
    elif normalize_gradle_rel_path(module_selector):
        execution_dir = repo_root
    else:
        execution_dir = Path(path).resolve()
    if not execution_dir.exists():
        execution_dir = Path(path).resolve()
    return execution_dir, gradle_task_prefix(module_selector)




def search_modules_build_gradle(project_path, project_dataframe, project_id):
    """
    Searches all the modules where are stored build.gradle (or build.gradle.kts) files

        Parameters:
                    project_path: the path of the proejct
                    project_dataframe (Dataframe): the dataframe containing all the focal classes and test classes
                    project_id: the ID of the project
        Returns:
                    modules (List): the list of modules found               
    """
    project_df = project_dataframe.copy()
    modules = []
    for index, row in project_df.iterrows():
            location = row['Test_Path'].replace(f'repos/{project_id}/', '').replace(f"{row['Test_Class']}.java", '')
            file_name = f"/{row['Test_Class']}.java"
            while ((os.path.isfile(f"{project_path}/{location}/build.gradle")) or (os.path.isfile(f"{project_path}/{location}/build.gradle.kts"))) == False:
                location = os.path.dirname(location)
                if location == '':
                    break
            if location != '':
                modules.append(location)
    # remove duplicates
    modules = list(dict.fromkeys(modules)) 
    return modules


def extract_gradle_version_from_gradle_wrapper(project_name):
    """
    Extracts Gradle version from the given project. 
    This function searches for the Gradle version in the gradle-wrapper properties file of the given project.
        Parameters:
                    project_name: the ID of the project
        Returns:
                    compiler_version: the Gradle version expressed as a numeric value, 'None' if the function did not find it or if an error occured
    """
    compiler_version = None
    gradleWrapperFile = f'repos/{project_name}/gradle/wrapper/gradle-wrapper.properties'
    try:
        with open(gradleWrapperFile, 'r') as file:
            for line in file:
                if line.strip().startswith('distributionUrl'):
                    gradleVersionMatch = re.search(r'gradle-(.*?)(?:-bin)?(?:-all)?\.zip', line)
                    if gradleVersionMatch:
                        compiler_version = gradleVersionMatch.group(1)
                    break
    except Exception as e:
        print(e)
    return compiler_version


def extract_gradle_version_from_gradle_properties(project_name):
    """
    Extracts Gradle version from the given project. 
    This function searches for the Gradle version in the gradle.properties file of the given project.
        Parameters:
                    project_name: the ID of the project
        Returns:
                    compiler_version: the Gradle version expressed as a numeric value, 'None' if the function did not find it or if an error occured
    """
    compiler_version = None
    gradleProperties = f'repos/{project_name}/gradle.properties'
    try:
        with open(gradleProperties, 'r') as file:
                content=file.read()
                content = content.replace("\n", "")
                gradleVersionMatch = re.search(r'gradle.version\s*=\s*([\d.]+)', content)
                if gradleVersionMatch:
                    compiler_version = gradleVersionMatch.group(1)
    except Exception as e:
        print(e)
    return compiler_version





def extract_info_build_gradle(path, compiler_search):
    """
    Extracts java version, Gradle version and JUnit or TestNG version from the given project. 
    This function searches for all the versions in the build.gradle file of the given project.  
        Parameters:
                    project_path: the path of the project or of the module
                    compiler_search: If 'True' indicates that the function has to search for the Gradle version, if 'False' indicates that the function should not search for the Gradle version

        Returns:
                    java_version: if the function finds the Java version it returns a numeric value, otherwise it returns None
                    junit_version: if the function finds the Junit version it returns a numeric value, otherwise it returns None
                    testng_version: if the function finds the TestNG version it returns a numeric value, otherwise it returns None
                    compiler_version [if compiler_search is set to 'True']: if the function finds the Gradle version it returns a numeric value, otherwise it returns None
    """
    java_version = None
    junit_version = None
    testng_version = None
    compiler_version = None
    path_build_gradle=f'{path}/build.gradle'
    path_build_gradle_kts=f'{path}/build.gradle.kts'
    path_file = None # path of the file to be opened
    try:
        if os.path.exists(path_build_gradle):
            path_file = path_build_gradle
        else:
            path_file = path_build_gradle_kts
        with open(path_file, 'r') as file:
            content=file.read()
            content = content.replace("\n", " ")
            if compiler_search is True:
                gradleVersionMatch = re.search(r"gradleVersion\s*=\s*\'([\d.]+)\'", content)
                if gradleVersionMatch:
                    compiler_version = gradleVersionMatch.group(1)


            findJava = False # True if I found the java version, false otherwhise
            # research java version
            java_version_match = re.search(r"sourceCompatibility\s*=\s*([\d.]+)", content)
            if java_version_match:
                java_version = java_version_match.group(1)
                findJava = True
            if findJava == False: # if expressed with letters
                java_version_match = re.search(r"sourceCompatibility\s*=\s*JavaVersion\.(\S*)", content)
                if java_version_match:
                    java_version_text = java_version_match.group(1)
                    findJava = True
                    if java_version_text == 'Version_1.5' or java_version_text == 'Version_1_5' or java_version_text == 'Version_5' or java_version_text == 'VERSION_1.5' or java_version_text == 'VERSION_1_5' or java_version_text == 'VERSION_5':
                        java_version = '1.5'
                    elif java_version_text == 'Version_1.6' or java_version_text == 'Version_1_6' or java_version_text == 'Version_6' or java_version_text == 'VERSION_1.6' or java_version_text == 'VERSION_1_6' or java_version_text == 'VERSION_6':
                        java_version = '1.6'
                    elif java_version_text == 'Version_1.7' or java_version_text == 'Version_1_7' or java_version_text == 'Version_7' or java_version_text == 'VERSION_1.7' or java_version_text == 'VERSION_1_7' or java_version_text == 'VERSION_7':
                        java_version = '1.7'
                    elif java_version_text == 'Version_1.8' or java_version_text == 'Version_1_8' or java_version_text == 'Version_8' or java_version_text == 'VERSION_1.8' or java_version_text == 'VERSION_1_8' or java_version_text == 'Version_8':
                        java_version = '1.8'
                    elif java_version_text == 'Version_11' or java_version_text == 'VERSION_11':
                        java_version = '11'
                    elif java_version_text == 'Version_17' or java_version_text == 'VERSION_17':
                        java_version = '17'
                    elif java_version_text == 'Version_21' or java_version_text == 'VERSION_21':
                        java_version = '21'
                    else:
                        findJava = False
                
            # research test version
            findTest = False # True if I found the Junit/testNG version, false otherwhise
            # research junit version
            junit_version_match = re.search(r"junit(?:5)?Version\s*=\s*[\'\"]([0-9.]+)[\'\"]", content)
            if junit_version_match:
                junit_version = junit_version_match.group(1)
                findTest = True
            if findTest == False:
                dependency_match = re.search(r"(testCompile|testImplementation|testCompileOnly|implementation).?[\'\"]junit:junit:([0-9.]+)[\'\"]", content)
                if dependency_match:
                    junit_version = dependency_match.group(2)
                    findTest = True
            if findTest == False:
                dependency_match = re.search(r"(testCompile|testImplementation|testCompileOnly|implementation)\s+\'junit:junit:([0-9.]+)\'", content)
                if dependency_match:
                    junit_version = dependency_match.group(2)
                    findTest = True
            if findTest == False:
                dependency_match = re.search(r"name:\s*\'junit\',\s*version:\s*\'([0-9.]+)\'", content)
                if dependency_match:
                    junit_version = dependency_match.group(1)
                    findTest = True
            if findTest == False: #build-gradle.kts
                dependency_match = re.search(r'(testCompile|testImplementation|testCompileOnly|implementation)\s*\("junit:junit:([0-9.]+)"\)', content)
                if dependency_match:
                    junit_version = dependency_match.group(2)
                    findTest = True
            if findTest == False:
                dependency_match = re.search(r'(testCompile|testImplementation|testCompileOnly|implementation)\s+\'org.junit.jupiter:junit-jupiter:([0-9.]+)\'', content)
                if dependency_match:
                    junit_version = dependency_match.group(2)
                    findTest = True
            if findTest == False:
                dependency_match = re.search(r'(testCompile|testImplementation|testCompileOnly|implementation)\s+\'org.junit.jupiter:junit-jupiter-api:([0-9.]+)\'', content)
                if dependency_match:
                    junit_version = dependency_match.group(2)
                    findTest = True

                                    

            # research testng version
            if findTest == False:
                testng_version_match = re.search(r"testng(?:5)?Version\s*=\s*[\'\"]([0-9.]+)[\'\"]", content)
                if testng_version_match:
                    testng_version = testng_version_match.group(1)
                    findTest = True
            if findTest == False:
                dependency_match = re.search(r"(testCompile|testImplementation|testCompileOnly|implementation).?[\'\"]testng:testng::([0-9.]+)[\'\"]", content)
                if dependency_match:
                    testng_version = dependency_match.group(2)
                    findTest = True
            if findTest == False:
                dependency_match = re.search(r"(testCompile|testImplementation|testCompileOnly|implementation)\s+\'testng:testng:([0-9.]+)\'", content)
                if dependency_match:
                    testng_version = dependency_match.group(2)
                    findTest = True
            if findTest == False:
                dependency_match = re.search(r"name:\s*\'testng\',\s*version:\s*\'([0-9.]+)\'", content)
                if dependency_match:
                    testng_version = dependency_match.group(1)
                    findTest = True     
            if findTest == False: #build-gradle.kts
                dependency_match = re.search(r'(testCompile|testImplementation|testCompileOnly|implementation)\s*\("testng:testng:([0-9.]+)"\)', content)
                if dependency_match:
                    testng_version = dependency_match.group(2)
                    findTest = True
    
    except Exception as e:
        print(e)
    if compiler_search is True:
        return java_version, junit_version, testng_version, compiler_version
    else:
        return java_version, junit_version, testng_version







def find_gradle_main_classes_location(location):
    """
    Finds the Gradle project directory and compiled main-classes directory for old and new Gradle layouts.
    """
    def class_dir_candidates(base):
        return [
            os.path.join(base, "build", "classes", "java", "main"),
            os.path.join(base, "build", "classes", "main"),
            os.path.join(base, "build", "classes", "kotlin", "main"),
        ]

    current = os.path.abspath(location)
    while True:
        for classes_dir in class_dir_candidates(current):
            if os.path.isdir(classes_dir):
                return current, str(Path(classes_dir).resolve())
        parent = os.path.dirname(current)
        module_name = os.path.basename(current)
        if module_name:
            for relative in [
                os.path.join("build", module_name, "classes", "java", "main"),
                os.path.join("build", module_name, "classes", "main"),
                os.path.join("build", module_name, "classes", "kotlin", "main"),
            ]:
                classes_dir = os.path.join(parent, relative)
                if os.path.isdir(classes_dir):
                    return current, str(Path(classes_dir).resolve())
        if parent == current or current == '':
            return '', ''
        current = parent


def run_evosuite_generation_gradle(focal_path):
    """
    Given a focal class of a Gradle project, it runs EvoSuite to generate the corresponding test class.
    This function uses the evosuite-1.2.0.jar file; therefore, the evosuite JAR file must be present in the experiment root.
        Parameters:
                focal_path: the path of the focal class
        Returns:
                :'True' if the generation has been executed correctly, 'False' otherwise
       
    """
    started_at = time.time()
    focal_path_abs = os.path.abspath(focal_path)
    focal_path_norm = focal_path_abs.replace("\\", "/")
    if "/src/main/java/" in focal_path_norm:
        focal_class_path = focal_path_norm.split("/src/main/java/", 1)[1]
    elif "java/" in focal_path_norm:
        focal_class_path = focal_path_norm.split("java/", 1)[1]
    else:
        utils.append_phase_log("evosuite_generate", arm="evosuite", status="FAIL", started_at=started_at, detail=f"Cannot infer Java class name from focal path: {focal_path}")
        return False
    name_focal_class = focal_class_path.replace(".java", "").replace("/", ".")
    project = focal_path_norm.split("compiledrepos/")[1].split("/")[0] if "compiledrepos/" in focal_path_norm else ""
    location, project_cp = find_gradle_main_classes_location(focal_path_abs)
    if location == '':
        utils.append_phase_log("evosuite_generate", project=project, arm="evosuite", focal_class=name_focal_class.split(".")[-1], status="FAIL", started_at=started_at, detail="missing Gradle main classes directory; checked build/classes/java/main, build/classes/main, build/classes/kotlin/main")
        return False

    command = [
        java_command(),
        "-jar",
        toolchains.evosuite_jar(),
        "-class",
        name_focal_class,
        "-projectCP",
        project_cp,
        "-Dtest_archive=false",
        "-Dcriterion=BRANCH",
        "-Dassertions=false",
        "-Dno_runtime_dependency=true",
        "-Dtest_scaffolding=false",
        "-Dsearch_budget=60",
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=EVOSUITE_TIMEOUT_SECONDS)
        if result.returncode == 0 and result.stdout.__contains__("Computation finished"):
            utils.append_phase_log("evosuite_generate", project=project, arm="evosuite", focal_class=name_focal_class.split(".")[-1], status="PASS", started_at=started_at, detail=name_focal_class)
            return True
        else:
            utils.append_phase_log("evosuite_generate", project=project, arm="evosuite", focal_class=name_focal_class.split(".")[-1], status="FAIL", started_at=started_at, detail=command_output_tail(result))
            return False
    except subprocess.TimeoutExpired as e:
        detail = f"EvoSuite generation timed out after {EVOSUITE_TIMEOUT_SECONDS}s\n{timeout_output_tail(e)}"
        utils.append_phase_log("evosuite_generate", project=project, arm="evosuite", focal_class=name_focal_class.split(".")[-1], status="ERROR", started_at=started_at, detail=detail)
        print(detail)
        return False
    except Exception as e:
        utils.append_phase_log("evosuite_generate", project=project, arm="evosuite", focal_class=name_focal_class.split(".")[-1], status="ERROR", started_at=started_at, detail=e)
        print(e)
        return False
    


def add_evosuite_build_gradle(path):
    """
    Adds the evosuite dependency (version 1.2.0) to the build.gradle file of the given project.
        Parameters:
                    project_path: the path of the Gradle project or of the module
        Returns:
                    old_build_gradle: the content of the build.gradle file before the edit, 'None' if an error occured
    """
    build_gradle_path = os.path.join(path, "build.gradle")
    build_gradle_kts_path = os.path.join(path, "build.gradle.kts")
    runtime_jar = toolchains.evosuite_runtime_jar().replace("\\", "/")
    if os.path.exists(build_gradle_path):
        try:
            with open(build_gradle_path, "r") as file:
                build_gradle_content = file.read()
        except Exception as e:
            print(e)
            return None
        old_build_gradle = build_gradle_content
        build_gradle_content = build_gradle_content.replace("apply plugin: 'jacoco'", f"""apply plugin: 'jacoco' \n dependencies{{\n implementation files('{runtime_jar}')\n}}""")
        try:
            with open(build_gradle_path, "w") as file:
                file.write(build_gradle_content)
        except Exception as e:
            print(e)
            return None
        return old_build_gradle
    
    elif os.path.exists(build_gradle_kts_path):
        try:
            with open(build_gradle_kts_path, "r") as file:
                build_gradle_content = file.read()
        except Exception as e:
            print(e)
            return None
        old_build_gradle = build_gradle_content
        build_gradle_content = build_gradle_content.replace('apply(plugin = "jacoco")', f"""apply(plugin = "jacoco") \n dependencies{{\n implementation(files("{runtime_jar}"))\n}}""")
        try:
            with open(build_gradle_kts_path, "w") as file:
                file.write(build_gradle_content)
        except Exception as e:
            print(e)
            return None
        return old_build_gradle
    else:
        return None
    


    



def run_gradle_test_command(path, project_dataframe, system):
    """
    Runs the package command for the given Gradle project. 
    It generates the Jacoco and PITest reports. 
        Parameters:
                    path: the path of the project or of the module
                    project_dataframe (Dataframe): the dataframe containing the focal classes and test classes that are to be executed by gradle
                    system (string): the current OS (Windows, Linux, etc..)  
        Returns:
                    : 'True' if the project has been compiled successfully,'False' if the project has been compiled with errors
    """
    project_df = project_dataframe.copy()
    started_at = time.time()
    project = str(project_df.iloc[0].get('Project', '')) if not project_df.empty else ''
    module = str(project_df.iloc[0].get('Module', '')) if not project_df.empty and 'Module' in project_df.columns else ''
    try:
        test_classes = gradle_test_classes(project_df)
        test_detail = ",".join(test_classes)
        framework_args = ["-Prbl4TestFramework=testng"] if generated_tests_use_testng(path, project_df) else []
        print(f"Test classes: {test_detail}")
        subprocess.check_call([java_command(), '-version'])
        execution_dir, task_prefix = gradle_execution_context(path, project_df)
        # Find gradlew / gradlew.bat by checking path and parent directories
        gradlew_name = 'gradlew.bat' if system == 'Windows' else 'gradlew'
        curr = str(execution_dir)
        gradlew_path = None
        for _ in range(4):
            candidate = os.path.join(curr, gradlew_name)
            if os.path.exists(candidate):
                gradlew_path = os.path.abspath(candidate)
                break
            parent = os.path.dirname(curr)
            if parent == curr:
                break
            curr = parent

        if system == 'Windows':
            gradle_cmd = gradlew_path if gradlew_path else 'gradle.bat'
        else: 
            gradle_cmd = gradlew_path if gradlew_path else 'gradle'

        test_started_at = time.time()
        result = gradle_command_with_common_exclusions(
            gradle_cmd,
            framework_args + [f'{task_prefix}clean', f'{task_prefix}test', f'{task_prefix}jacocoTestReport'],
            str(execution_dir),
            timeout=900,
        )
        if result.returncode != 0:
            errori = errorCorrection.extract_gradle_errors(result.stdout, result.stderr)
            print("\n--------------------")
            print(errori)
            print("\n--------------------")
            detail = f"cwd={execution_dir}; tasks={task_prefix}test,{task_prefix}jacocoTestReport; {errori}"
            utils.append_phase_log("gradle_test_jacoco", project=project, module=module, status="FAIL", started_at=test_started_at, detail=detail)
            utils.append_phase_log("gradle_test_jacoco_pitest", project=project, module=module, status="FAIL", started_at=started_at, detail=detail)
            return False, errori

        utils.append_phase_log("gradle_test_jacoco", project=project, module=module, status="PASS", started_at=test_started_at, detail=f"cwd={execution_dir}; tasks={task_prefix}test,{task_prefix}jacocoTestReport; tests={test_detail}")

        pit_started_at = time.time()
        pit_result = gradle_command_with_common_exclusions(
            gradle_cmd,
            framework_args + [f'{task_prefix}pitest'],
            str(execution_dir),
            timeout=int(os.getenv("RBL4_GRADLE_PIT_TIMEOUT_SECONDS", "900")),
        )
        if pit_result.returncode != 0:
            errori = errorCorrection.extract_gradle_errors(pit_result.stdout, pit_result.stderr)
            print("\n--------------------")
            print(errori)
            print("\n--------------------")
            utils.append_phase_log("gradle_pitest", project=project, module=module, status="FAIL", started_at=pit_started_at, detail=f"cwd={execution_dir}; task={task_prefix}pitest; {errori}")
            utils.append_phase_log(
                "gradle_test_jacoco_pitest",
                project=project,
                module=module,
                status="PASS",
                started_at=started_at,
                detail=f"cwd={execution_dir}; tests={test_detail}; pitest_failed_after_successful_test_jacoco: {errori}",
            )
            return True, errori

        utils.append_phase_log("gradle_pitest", project=project, module=module, status="PASS", started_at=pit_started_at, detail=f"cwd={execution_dir}; task={task_prefix}pitest; tests={test_detail}")
        utils.append_phase_log("gradle_test_jacoco_pitest", project=project, module=module, status="PASS", started_at=started_at, detail=f"cwd={execution_dir}; tests={test_detail}")
        return True, None
            
    except Exception as e:
            utils.append_phase_log("gradle_test_jacoco_pitest", project=project, module=module, status="ERROR", started_at=started_at, detail=e)
            print(e)
            return False, str(e)
    


def edit_build_gradle_file(path, project_dataframe, junit_version, testng_version=None, compiler_version=None):
    """
    Edits the build.gradle file to add JaCoCo and PIT dependencies.
    The injected Gradle syntax is selected from the project Gradle version so
    old wrappers such as Gradle 2.x/5.x are not broken by modern plugin APIs.
    """
    project_df = project_dataframe.copy()
    build_gradle_path = os.path.join(path, 'build.gradle')
    build_gradle_kts_path = os.path.join(path, 'build.gradle.kts')

    test_class_names = gradle_test_classes(project_df)
    test_classes = gradle_quoted_list(test_class_names)
    test_classes_kts = gradle_kts_quoted_list(test_class_names)
    test_include_patterns = gradle_test_include_patterns(test_class_names)
    test_include_config = gradle_include_lines(test_include_patterns)
    test_include_config_kts = gradle_include_lines_kts(test_include_patterns)

    focal_classes = project_df['Focal_Path'].tolist()
    focal_classes = [focal_path.split('main/java/')[1].replace('/', '.').replace('.java', '') for focal_path in focal_classes]
    focal_classes_groovy = gradle_quoted_list(focal_classes)
    focal_classes_kts = gradle_kts_quoted_list(focal_classes)

    pitest_plugin_version = pitest_plugin_version_for_gradle(compiler_version)
    junit5_pitest_config = f"        junit5PluginVersion = '{PITEST_JUNIT5_PLUGIN_VERSION}'\n" if is_junit5_project(junit_version) else ""
    junit5_pitest_config_kts = f'        junit5PluginVersion.set("{PITEST_JUNIT5_PLUGIN_VERSION}")\n' if is_junit5_project(junit_version) else ""
    if gradle_version_at_least(compiler_version, 7, 0):
        junit_dependency = """
    dependencies {
        testImplementation 'junit:junit:4.13.2'
        testRuntimeOnly 'org.hamcrest:hamcrest-core:1.3'
    }
"""
        junit_dependency_kts = """
dependencies {
    "testImplementation"("junit:junit:4.13.2")
    "testRuntimeOnly"("org.hamcrest:hamcrest-core:1.3")
}
"""
    else:
        junit_dependency = """
    dependencies {
        testCompile 'junit:junit:4.13.2'
        testRuntime 'org.hamcrest:hamcrest-core:1.3'
    }
"""
        junit_dependency_kts = """
dependencies {
    "testCompile"("junit:junit:4.13.2")
    "testRuntime"("org.hamcrest:hamcrest-core:1.3")
}
"""

    if gradle_version_at_least(compiler_version, 7, 0):
        jacoco_reports_config = """            xml.required = false
            html.required = false
            csv.required = true
            csv.outputLocation = file("${buildDir}/reports/jacoco/jacoco.csv")
"""
        jacoco_reports_config_kts = """            xml.required.set(false)
            html.required.set(false)
            csv.required.set(true)
            csv.outputLocation.set(file("${buildDir}/reports/jacoco/jacoco.csv"))
"""
    else:
        jacoco_reports_config = """            xml.enabled = false
            html.enabled = false
            csv.enabled = true
            csv.destination file("${buildDir}/reports/jacoco/jacoco.csv")
"""
        jacoco_reports_config_kts = """            xml.isEnabled = false
            html.isEnabled = false
            csv.isEnabled = true
            csv.destination = file("${buildDir}/reports/jacoco/jacoco.csv")
"""

    if gradle_version_at_least(compiler_version, 4, 7):
        test_filter_config = """        filter {
            setFailOnNoMatchingTests(false)
        }
"""
        test_filter_config_kts = """        filter {
            setFailOnNoMatchingTests(false)
        }
"""
    else:
        test_filter_config = ""
        test_filter_config_kts = ""

    if is_testng_project(testng_version):
        testng_pitest_dependency_version = testng_pitest_dependency_for_plugin(pitest_plugin_version)
        if testng_pitest_dependency_version:
            testng_dependency = f"""
    dependencies {{
        pitest 'org.pitest:pitest-testng-plugin:{testng_pitest_dependency_version}'
    }}
"""
            testng_dependency_kts = f"""
    dependencies {{
        "pitest"("org.pitest:pitest-testng-plugin:{testng_pitest_dependency_version}")
    }}
"""
            testng_pitest_config = """        if (project.hasProperty('rbl4TestFramework') && project.property('rbl4TestFramework') == 'testng') {
            testPlugin = 'testng'
        }
"""
            testng_pitest_config_kts = """    if ((project.findProperty("rbl4TestFramework") as String?) == "testng") {
        testPlugin.set("testng")
    }
"""
        else:
            testng_dependency = ""
            testng_dependency_kts = ""
            testng_pitest_config = ""
            testng_pitest_config_kts = ""
        testng_test_config = """        if (project.hasProperty('rbl4TestFramework') && project.property('rbl4TestFramework') == 'testng') {
            useTestNG()
        }
"""
        testng_test_config_kts = """    if ((project.findProperty("rbl4TestFramework") as String?) == "testng") {
        useTestNG()
    }
"""
    else:
        testng_dependency = ""
        testng_dependency_kts = ""
        testng_pitest_config = ""
        testng_pitest_config_kts = ""
        testng_test_config = ""
        testng_test_config_kts = ""

    if os.path.exists(build_gradle_path):
        try:
            with open(build_gradle_path, 'r') as file:
                build_gradle_content = file.read()
        except Exception as e:
            print(e)
            return None

        add_dependecies = f"""buildscript {{
    repositories {{
        mavenCentral()
    }}
    dependencies {{
        classpath 'info.solidsoft.gradle.pitest:gradle-pitest-plugin:{pitest_plugin_version}'
        classpath 'org.jacoco:org.jacoco.core:0.8.9'
    }}
}}

"""
        configure_measurement = f"""

allprojects {{
    apply plugin: 'java'
    apply plugin: 'info.solidsoft.pitest'
    apply plugin: 'jacoco'

    repositories {{
        mavenCentral()
    }}
{junit_dependency}
{testng_dependency}
    pitest {{
{junit5_pitest_config}{testng_pitest_config}        targetTests = [{test_classes}]
        targetClasses = [{focal_classes_groovy}]
        outputFormats = ['csv']
        threads = 4
        failWhenNoMutations = false
    }}

    jacoco {{
        toolVersion = '{GRADLE_JACOCO_TOOL_VERSION}'
    }}

    jacocoTestReport {{
        dependsOn test
        reports {{
{jacoco_reports_config}        }}
    }}

    test {{
{testng_test_config}{test_include_config}{test_filter_config}        finalizedBy jacocoTestReport
    }}
}}
"""
        old_build_gradle_content = build_gradle_content
        build_gradle_content = add_dependecies + build_gradle_content + configure_measurement
        try:
            with open(build_gradle_path, 'w') as file:
                file.write(build_gradle_content)
        except Exception as e:
            print(e)
            return None
        return old_build_gradle_content

    if os.path.exists(build_gradle_kts_path):
        try:
            with open(build_gradle_kts_path, 'r') as file:
                build_gradle_content = file.read()
        except Exception as e:
            print(e)
            return None

        old_build_gradle_content = build_gradle_content
        plugin_lines = f'    id("info.solidsoft.pitest") version "{pitest_plugin_version}"\n    jacoco\n'
        if re.search(r'(?m)^\s*plugins\s*\{', build_gradle_content):
            build_gradle_content = re.sub(
                r'(?m)^(\s*plugins\s*\{\s*)',
                lambda match: match.group(1) + "\n" + plugin_lines,
                build_gradle_content,
                count=1,
            )
        else:
            build_gradle_content = f"plugins {{\n{plugin_lines}}}\n\n" + build_gradle_content

        configure_measurement = f"""

repositories {{
    mavenCentral()
}}
{junit_dependency_kts}
{testng_dependency_kts}
pitest {{
{junit5_pitest_config_kts}{testng_pitest_config_kts}    targetTests.set(setOf({test_classes_kts}))
    targetClasses.set(setOf({focal_classes_kts}))
    outputFormats.set(setOf("csv"))
    threads.set(4)
    failWhenNoMutations.set(false)
}}

extensions.configure<org.gradle.testing.jacoco.plugins.JacocoPluginExtension>("jacoco") {{
    toolVersion = "{GRADLE_JACOCO_TOOL_VERSION}"
}}

tasks.named<org.gradle.testing.jacoco.tasks.JacocoReport>("jacocoTestReport") {{
    dependsOn(tasks.named("test"))
    reports {{
{jacoco_reports_config_kts}    }}
}}

tasks.named<org.gradle.api.tasks.testing.Test>("test") {{
{testng_test_config_kts}{test_include_config_kts}{test_filter_config_kts}    finalizedBy("jacocoTestReport")
}}
"""
        build_gradle_content = build_gradle_content + configure_measurement
        try:
            with open(build_gradle_kts_path, 'w') as file:
                file.write(build_gradle_content)
        except Exception as e:
            print(e)
            return None
        return old_build_gradle_content

    return None
    


def write_build_gradle(path, build_gradle_content):
    """
    Writes the build.gradle file of the given project with the given content.
        Parameters:
                    path: the path of the project or of the module
                    build_gradle_content: the content that needs to be written
    """
    
    build_gradle_path = os.path.join(path, 'build.gradle')
    build_gradle_kts_path = os.path.join(path, 'build.gradle.kts')
    if os.path.exists(build_gradle_path):
        try:
            with open(build_gradle_path, 'w') as build_gradle_file:
                build_gradle_file.write(build_gradle_content)
        except Exception as e:
            print(e)
    elif (os.path.exists(build_gradle_kts_path)):
        try:
            with open(build_gradle_kts_path, 'w') as build_gradle_file:
                build_gradle_file.write(build_gradle_content)
        except Exception as e:
            print(e)





def process_gradle_project(project, test_types, techniques, project_path, project_df, compiler_version, java_version, junit_version, testng_version, has_mockito, system, project_structure, project_dependencies, correct):
    """
    It processes the given Gradle project with the given test types and techniques.
    Parameters:
                project: the ID of the project.
                test_types (List): the list of test types to execute.
                techniques (List): the list of prompt techniques (for the AI test types) to execute.
                project_path: the path of the project. 
                project_df: the dataframe that contains all the focal/test classes of the project.
                compilter_version: the Gradle version of the given project.
                java_version: the Java version of the given project.
                junit_version: the Junit version of the given project.
                testng_version: the testNG version of the given project.
                has_mockito: the string that will be used to specify to the API whether the AI test types can use the Mockito framework or not.
                system (String): the current OS (Windows, Linux, etc...)
    Returns:
                0(int) if the process failed.
    """
    swtich_to_next_project = False
    if is_testng_project(testng_version):
        print(f"{project} is a Gradle TestNG project; enabling TestNG execution and PIT TestNG plugin support.")
    gradle_directory = r"/Gradle"
    utils.set_gradle_variable(gradle_directory, '8', system)
    # add jacoco and pitest dependecies to build.gradle
    original_build_gradle = edit_build_gradle_file(project_path, project_df, junit_version, testng_version, compiler_version)
    if(original_build_gradle==False):
        print(f"{project} skipped because pitest or jacoco is already implemented in the build.gradle file. Switch to next project...")
        return 0 # Switch to next project
    elif(original_build_gradle==None):
        print(f"{project} skipped because an error occurred while trying to integrate the Jacoco and Pitest dependencies into the build.gradle file. Switch to next project...")
        return 0 # Switch to next project
    for i, test_type in enumerate(test_types):
        output_path_failed = f'./output/{project}/TestClasses_{project}_{test_type}.failed' # Indicate that the test type failed due to an error during the execution of the script.
        output_path_failed_gradle = f'./output/{project}/TestClasses_{project}_{test_type}.gradlefailed' # Indicates that all the test classes of the test type failed during the gradle execution.

        restart_test_type = False
        print('\n----')
        print(f"STARTING {test_type} test type\n")
        if test_type == "human":
            # configure the test smell detector
            csv_path_input_test_smell = utils.configure_test_smell_detector(project_df, project)
            # Run the Gradle package command. 
            print("--//loading gradle execution..//")
            if(run_gradle_test_command(project_path, project_df, system)[0]==True):
                print(f"Package command completed for {project}\n")
            else:
                print(f"Package command failed for {project}. Switch to next project...\n")
                write_build_gradle(project_path, original_build_gradle)
                swtich_to_next_project = True
                break # switch to next project

            # Run the test smell detector
            path_csv_result_test_smell = utils.run_test_smell_detector(csv_path_input_test_smell, project, test_type, None)
            if path_csv_result_test_smell is None:
                print("An error occured while trying to run the test smell detector")
            else:
                print("The test smell detector ended successfully")  
            # Retrieve Code Coverage and Cyclomatic Complexity on test classes
            measures_df = utils.retrieve_code_coverage_and_cyclomatic_complexity(project_path, project_df, project, 'Gradle')
            if measures_df is None:
                print(f"Switch to next project because edit_build_gradle_file() failed for the project {project}")
                write_build_gradle(project_path, original_build_gradle)
                swtich_to_next_project = True
                break # Switch to next project
            output_csv_path = utils.generate_output_csv_test_type(project, test_type, None, measures_df, path_csv_result_test_smell)
            if output_csv_path is None:
                print("An errore occured while trying to save the test type csv file!")
            else:
                print(f"DataFrame saved to {output_csv_path}")
        elif test_type == 'evosuite':
            project_df_evosuite = project_df.copy() # dataframe for the evosuite test type
            build_gradle_before_evosuite = add_evosuite_build_gradle(project_path)
            if build_gradle_before_evosuite is None:
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
                last_execution = None # outcome of the last gradle execution, True = Build Success, False = Build Failure
                try:
                    human_test_class = utils.read_text_file(test_path) # save the human version of the test class
                    dictionary_for_restore[test_path] =  human_test_class
                    os.remove(test_path)      
                except Exception as e:
                    print(f"An error occured while trying to open and read the test_path: {e}")
                    try:
                        write_build_gradle(project_path, build_gradle_before_evosuite)
                        utils.remove_evosuite_scaffolding_files(list(dictionary_for_restore.keys()))
                        utils.write_files(dictionary_for_restore)
                        with open(output_path_failed, 'w') as file:
                            pass
                    except Exception as e:
                        write_build_gradle(project_path, original_build_gradle)
                        utils.remove_evosuite_scaffolding_files(list(dictionary_for_restore.keys()))
                        utils.write_files(dictionary_for_restore)
                        print(f'An error occured while trying to open output_path_failed: {e}')
                        sys.exit(1)
                    restart_test_type = True # Switch to next test type
                    break
                
                print("--//loading evosuite generation..//")
                if run_evosuite_generation_gradle(focal_path) == False: # if error while running evosuite
                    print ("An error accored while trying to run the evosuite generation")
                    try:
                        write_build_gradle(project_path, build_gradle_before_evosuite)
                        utils.remove_evosuite_scaffolding_files(list(dictionary_for_restore.keys()))
                        utils.write_files(dictionary_for_restore)
                        with open(output_path_failed, 'w') as file:
                            pass
                    except Exception as e:
                        write_build_gradle(project_path, original_build_gradle)
                        utils.remove_evosuite_scaffolding_files(list(dictionary_for_restore.keys()))
                        utils.write_files(dictionary_for_restore)
                        print(f'An error occured while trying to open output_path_failed: {e}')
                        sys.exit(1)
                    restart_test_type = True
                    break # Switch to next test type
                else:
                    print(f"Evosuite generation performed correctly for the {name_focal_class} class")

                # Insert the test class generated by evosuite in the test_path
                test_path_package_evosuite = test_path.split('java/')[1].replace(f'{name_test_class}.java', f'{name_focal_class}_ESTest.java')
                evosuite_test_path = f'evosuite-tests/{test_path_package_evosuite}'
                try:
                    if not os.path.exists(evosuite_test_path):
                        project_df_evosuite = project_df_evosuite[project_df_evosuite['Test_Path'] != row['Test_Path']] # Delete the row from the DataFrame that corresponds to the test class causing an error during Gradle execution
                        utils.write_file(test_path, human_test_class) # Restore to human version the test class causing an error during Gradle execution
                        utils.remove_evosuite_scaffolding_files(list(test_path))
                        utils.remove_directory_evosuite_command_line()
                        continue 
                    evosuite_content = utils.read_text_file(evosuite_test_path)
                    evosuite_content = evosuite_content.replace(F'public class {name_focal_class}_ESTest', f'public class {name_test_class}') 
                    evosuite_content = evosuite_content.replace('separateClassLoader = true', 'separateClassLoader = false') # when setting separateClassLoader to false, JaCoCo can correctly calculate code coverage
                    utils.save_generated_test(project, 'evosuite', None, name_test_class, evosuite_content)
                    utils.write_text_file(test_path, evosuite_content)
                except Exception as e:
                    print(f"An error occured while trying to copy the evosuite class test: {e}")
                    try:
                        write_build_gradle(project_path, build_gradle_before_evosuite)
                        utils.write_files(dictionary_for_restore)
                        utils.remove_evosuite_scaffolding_files(list(dictionary_for_restore.keys()))
                        utils.remove_directory_evosuite_command_line()
                        with open(output_path_failed, 'w') as file:
                            pass
                    except Exception as e:
                        write_build_gradle(project_path, original_build_gradle)
                        utils.remove_evosuite_scaffolding_files(list(dictionary_for_restore.keys()))
                        utils.write_files(dictionary_for_restore)
                        utils.remove_directory_evosuite_command_line()
                        print(f'An error occured while trying to open output_path_failed: {e}')
                        sys.exit(1)
                    restart_test_type = True
                    break # Switch to next test type 
                
                # Move the scaffolding file in the test class directory
                test_path_package_evosuite_scaffolding = test_path.split('java/')[1].replace(f'{name_test_class}.java', f'{name_focal_class}_ESTest_scaffolding.java')
                evosuite_test_path_scaffolding = f'evosuite-tests/{test_path_package_evosuite_scaffolding}'
                try:
                    shutil.move(evosuite_test_path_scaffolding, test_path.replace('.java', '').replace(f'{name_test_class}', ''))
                except Exception as e:
                    print(f"An error occured while trying to move the scaffolding file: {e}")
                    try:
                        write_build_gradle(project_path, build_gradle_before_evosuite)
                        utils.write_files(dictionary_for_restore)
                        utils.remove_evosuite_scaffolding_files(list(dictionary_for_restore.keys()))
                        utils.remove_directory_evosuite_command_line()
                        with open(output_path_failed, 'w') as file:
                            pass
                    except Exception as e:
                        write_build_gradle(project_path, original_build_gradle)
                        utils.remove_evosuite_scaffolding_files(list(dictionary_for_restore.keys()))
                        utils.write_files(dictionary_for_restore)
                        utils.remove_directory_evosuite_command_line()
                        print(f'An error occured while trying to open output_path_failed: {e}')
                        sys.exit(1)
                    restart_test_type = True
                    break # Switch to next test type 
                
                print("--//loading gradle execution..//")
                if run_gradle_test_command(project_path, project_df, system)[0]==False: # if error while running gradle
                    print(f"Package command failed for project: {project}, test type: {test_type}\n")
                    project_df_evosuite = project_df_evosuite[project_df_evosuite['Test_Path'] != row['Test_Path']] # Delete the row from the DataFrame that corresponds to the test class causing an error during Gradle execution
                    utils.write_file(test_path, human_test_class) # Restore to human version the test class causing an error during Gradle execution
                    utils.remove_evosuite_scaffolding_files(list(test_path))
                    utils.remove_directory_evosuite_command_line()
                    last_execution = False
                    continue 
                else:
                    last_execution = True
                    print(f"Package command completed for {project}\n") 


                utils.remove_directory_evosuite_command_line()

            if restart_test_type == True:
                continue
            
            if project_df_evosuite.empty: # If all the test classes provided by Evosuite failed during Gradle execution
                try:
                    with open(output_path_failed_gradle, 'w') as file:
                        pass
                except Exception as e:
                    write_build_gradle(project_path, original_build_gradle)
                    utils.write_files(dictionary_for_restore)
                    utils.remove_evosuite_scaffolding_files(list(dictionary_for_restore.keys()))
                    print(f'An error occured while trying to open output_path_failed_gradle: {e}')
                    sys.exit(1)
            else: # if at least one of the test classes provided by Evosuite runned succesfully during Gradle execution
                # configure the test smell detector
                csv_path_input_test_smell = utils.configure_test_smell_detector(project_df_evosuite, project)
                # Run the test smell detector
                path_csv_result_test_smell = utils.run_test_smell_detector(csv_path_input_test_smell, project, test_type, None)
                if path_csv_result_test_smell is None:
                    print("An error occured while trying to run the test smell detector")
                else:
                    print("The test smell detector ended successfully")  
                if last_execution == False: # if last gradle execution outcome is False, then I run one more time gradle
                    print("--//loading gradle execution..//")
                    if run_gradle_test_command(project_path, project_df, system)[0]==False: # if error while running gradle
                        print('An error occured while trying to execute the final version of test classes.\n')
                        try:
                            write_build_gradle(project_path, build_gradle_before_evosuite)
                            utils.remove_evosuite_scaffolding_files(list(dictionary_for_restore.keys()))
                            utils.write_files(dictionary_for_restore)
                            with open(output_path_failed, 'w') as file:
                                pass
                        except Exception as e:
                            write_build_gradle(project_path, original_build_gradle)
                            utils.remove_evosuite_scaffolding_files(list(dictionary_for_restore.keys()))
                            utils.write_files(dictionary_for_restore)
                            print(f'An error occured while trying to open output_path_failed: {e}')
                            sys.exit(1)
                        continue # Switch to next test type
                    # Retrieve Code Coverage and Cyclomatic Complexity on test classes
                measures_df = utils.retrieve_code_coverage_and_cyclomatic_complexity(project_path, project_df_evosuite, project, 'Gradle')
                if measures_df is not None:
                    output_csv_path = utils.generate_output_csv_test_type(project, test_type, None, measures_df, path_csv_result_test_smell)
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
                        write_build_gradle(project_path, original_build_gradle)
                        utils.remove_evosuite_scaffolding_files(list(dictionary_for_restore.keys()))
                        utils.write_files(dictionary_for_restore)
                        print(f'An error occured while trying to open output_path_failed: {e}')
                        sys.exit(1)
            utils.write_files(dictionary_for_restore)
            utils.remove_evosuite_scaffolding_files(list(dictionary_for_restore.keys()))
            write_build_gradle(project_path, build_gradle_before_evosuite)



        else:
            # Iterate over each technique
            for j, technique in enumerate(techniques):  
                output_path_failed = f'./output/{project}/TestClasses_{project}_{test_type}_{technique}.failed' # Indicate that the test type/technique failed due to an error during the execution of the script or during a call to the API
                output_path_failed_gradle = f'./output/{project}/TestClasses_{project}_{test_type}_{technique}.gradlefailed' # Indicates that all the test classes of the test type failed during the gradle execution.

                restart_technique = False 
                print(f"\nProcessing test_type: {test_type}, technique: {technique}")
                project_df_technique = project_df.copy() # dataframe of the current test type and technique
                dictionary_for_restore = {} # dictionary that contains test_path as keys and the respective 'human_test_class' as values. This dictionary is used to restore the test classes to the human version.
                for index, row in project_df_technique.iterrows(): # iterate over each test class and focal class
                    name_focal_class = row['Focal_Class']
                    name_test_class = row['Test_Class']
                    focal_path = row['Focal_Path'].replace('repos/', 'compiledrepos/')
                    test_path = row['Test_Path'].replace('repos/', 'compiledrepos/')
                    last_execution = None # outcome of the last gradle execution, True = Build Success, False = Build Failure
                    testing_framework = None
                    if junit_version is not None:
                        testing_framework = 'Junit version ' + junit_version
                    elif is_testng_project(testng_version):
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
                            utils.write_files(dictionary_for_restore)
                            write_build_gradle(project_path, original_build_gradle)
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
                            utils.write_files(dictionary_for_restore)
                            write_build_gradle(project_path, original_build_gradle)
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
                            utils.write_files(dictionary_for_restore)
                            write_build_gradle(project_path, original_build_gradle)
                            print(f'An error occured while trying to open output_path_failed: {e}')
                            sys.exit(1)
                        restart_technique = True # Switch to next technique
                        break 
                                

                    # Run the Gradle package command
                    print("--//loading gradle execution..//")
                    esito, errori = run_gradle_test_command(project_path, project_df, system)
                    if not esito and correct == True: # if error while running gradle
                        chance_result = False
                        for num_chance in range (2,6):
                            if chance_result:
                                break
                            chance_result, errori = errorCorrection.correct_errors(project, test_type, technique, test_path, project_path, project_df, system, messages, errori, dictionary_for_restore, num_chance, "Gradle")
                        errorCorrection.save_conversation_to_json(messages, name_test_class, "/Users/nicomede/Desktop/classes2test_private")
                    elif not esito and correct == False:
                        print(
                            f"Package command failed for project: {project}, test type: {test_type}, technique: {technique}\n")
                    elif esito:
                        last_execution = True
                        print(f"Package command completed for {project}\n")

                if restart_technique == True:
                    continue

                    
                if project_df_technique.empty: # If all the test classes provided by the API failed during Gradle execution
                    try:
                        with open(output_path_failed_gradle, 'w') as file:
                            pass
                    except Exception as e:
                        utils.write_files(dictionary_for_restore)
                        write_build_gradle(project_path, original_build_gradle)
                        print(f'An error occured while trying to open output_path_failed_gradle: {e}')
                        sys.exit()
                else: # if at least one of the test classes provided by the API runned succesfully during Gradle execution
                    # configure the test smell detector
                    csv_path_input_test_smell = utils.configure_test_smell_detector(project_df_technique, project)
                    # Run the test smell detector
                    path_csv_result_test_smell = utils.run_test_smell_detector(csv_path_input_test_smell, project, test_type, technique)
                    if path_csv_result_test_smell is None:
                        print("An error occured while trying to run the test smell detector")
                    else:
                        print("The test smell detector ended successfully")  
                    if last_execution == False: # if last gradle execution outcome is False, then I run one more time gradle
                        print("--//loading gradle execution..//")
                        if run_gradle_test_command(project_path, project_df, system)[0]==False: # if error while running gradle
                            print('An error occured while trying to execute the final version of test classes.\n')
                            try:
                                utils.write_files(dictionary_for_restore)
                                with open(output_path_failed, 'w') as file:
                                    pass
                            except Exception as e:
                                utils.write_files(dictionary_for_restore)
                                write_build_gradle(project_path, original_build_gradle)
                                print(f'An error occured while trying to open output_path_failed: {e}')
                                sys.exit(1)
                            continue  # switch to next technique      
                    # Retrieve Code Coverage and Cyclomatic Complexity on test classes
                    measures_df = utils.retrieve_code_coverage_and_cyclomatic_complexity(project_path, project_df_technique, project, 'Gradle')
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
                            utils.write_files(dictionary_for_restore)
                            write_build_gradle(project_path, original_build_gradle)
                            print(f'An error occured while trying to open output_path_failed: {e}')
                            sys.exit(1)
                    utils.write_files(dictionary_for_restore)
    if swtich_to_next_project == True:
        return 0
    write_build_gradle(project_path, original_build_gradle)



def process_gradle_module(project, module, test_types, techniques, path, module_df, compiler_version, java_version, junit_version, testng_version, has_mockito, system, project_structure, project_dependencies):
    """
    It processes the given Gradle module with the given test types and techniques.
    Parameters:
                project: the ID of the project.
                module: the name of the module.
                test_types (List): the list of test types to execute.
                techniques (List): the list of prompt techniques (for the AI test types) to execute.
                path: the path of the module. 
                module_df: the dataframe that contains all the focal/test classes of the module.
                compilter_version: the Gradle version of the given project.
                java_version: the Java version of the given project.
                junit_version: the Junit version of the given project.
                testng_version: the testNG version of the given project.
                has_mockito: the string that will be used to specify to the API whether the AI test types can use the Mockito framework or not.
    Returns:
                0(int) if the process failed.
    """
    if is_testng_project(testng_version):
        print(f"{project}_{module} is a Gradle TestNG module; enabling TestNG execution and PIT TestNG plugin support.")
    gradle_directory = r"/Gradle"
    utils.set_gradle_variable(gradle_directory, '8', system)
    # add jacoco and pitest dependecies to build.gradle
    original_build_gradle = edit_build_gradle_file(path, module_df, junit_version, testng_version, compiler_version)
    if(original_build_gradle==False):
        print(f"{project} skipped because pitest or jacoco is already implemented in the build.gradle file. Switch to next project/module...")
        return 0 # Switch to next project or module
    elif(original_build_gradle==None):
        print(f"{project} skipped because an error occurred while trying to integrate the Jacoco and Pitest dependencies into the build.gradle file. Switch to next project/module...")
        return 0 # Switch to next project or module
    for test_type in test_types:
        output_path_failed = f'./output/{project}/TestClasses_{project}_{test_type}.failed' # Indicate that the test type failed due to an error during the execution of the script.
        output_path_failed_gradle = f'./output/{project}/TestClasses_{project}_{test_type}.gradlefailed' # Indicates that all the test classes of the test type failed during the gradle execution.

        restart_test_type = False
        print('\n----')
        print(f"STARTING {test_type} test type\n")
        if test_type == "human":
            # configure the test smell detector
            csv_path_input_test_smell = utils.configure_test_smell_detector(module_df, project)
            # Run the Gradle package command. 
            print("--//loading gradle execution..//")
            if(run_gradle_test_command(path, module_df, system)[0]==True):
                print(f"Package command completed for {project}_{module}\n")
            else:
                print(f"Package command failed for {project}_{module}. Switch to next project/module...\n")
                write_build_gradle(path, original_build_gradle)
                return None # switch to next project

            # Run the test smell detector
            path_csv_result_test_smell = utils.run_test_smell_detector(csv_path_input_test_smell, project, test_type, None, module)
            if path_csv_result_test_smell is None:
                print("An error occured while trying to run the test smell detector")
            else:
                print("The test smell detector ended successfully")  
            # Retrieve Code Coverage and Cyclomatic Complexity on test classes                measures_df = utils.retrieve_code_coverage_and_cyclomatic_complexity(f'compiledrepos/{project}', module_df, project, type_project, module)
            if measures_df is None:
                print(f"Switch to next project/module because edit_build_gradle_file() failed for the project {project}_{module_df}")
                write_build_gradle(path, original_build_gradle)
                return 0 # Switch to next project or module
            output_csv_path = utils.generate_output_csv_test_type(project, test_type, None, measures_df, path_csv_result_test_smell, module)
            if output_csv_path is None:
                print("An errore occured while trying to save the test type csv file!")
            else:
                print(f"DataFrame saved to {output_csv_path}")
        elif test_type == 'evosuite':
            module_df_evosuite = module_df.copy() # dataframe for the evosuite test type
            build_gradle_before_evosuite = add_evosuite_build_gradle(path)
            if build_gradle_before_evosuite is None:
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
                last_execution = None # outcome of the last gradle execution, True = Build Success, False = Build Failure
                try:
                    human_test_class = utils.read_text_file(test_path) # save the human version of the test class
                    dictionary_for_restore[test_path] =  human_test_class
                    os.remove(test_path)      
                except Exception as e:
                    print(f"An error occured while trying to open and read the test_path: {e}")
                    try:
                        write_build_gradle(path, build_gradle_before_evosuite)
                        utils.remove_evosuite_scaffolding_files(list(dictionary_for_restore.keys()))
                        utils.write_files(dictionary_for_restore)
                        with open(output_path_failed, 'w') as file:
                            pass
                    except Exception as e:
                        write_build_gradle(path, original_build_gradle)
                        utils.remove_evosuite_scaffolding_files(list(dictionary_for_restore.keys()))
                        utils.write_files(dictionary_for_restore)
                        print(f'An error occured while trying to open output_path_failed: {e}')
                        sys.exit(1)
                    restart_test_type = True # Switch to next test type
                    break
                
                print("--//loading evosuite generation..//")
                if run_evosuite_generation_gradle(focal_path) == False: # if error while running evosuite
                    print ("An error accored while trying to run the evosuite generation")
                    try:
                        write_build_gradle(path, build_gradle_before_evosuite)
                        utils.remove_evosuite_scaffolding_files(list(dictionary_for_restore.keys()))
                        utils.write_files(dictionary_for_restore)
                        with open(output_path_failed, 'w') as file:
                            pass
                    except Exception as e:
                        write_build_gradle(path, original_build_gradle)
                        utils.remove_evosuite_scaffolding_files(list(dictionary_for_restore.keys()))
                        utils.write_files(dictionary_for_restore)
                        print(f'An error occured while trying to open output_path_failed: {e}')
                        sys.exit(1)
                    restart_test_type = True
                    break # Switch to next test type
                else:
                    print(f"Evosuite generation performed correctly for the {name_focal_class} class")

                # Insert the test class generated by evosuite in the test_path
                test_path_package_evosuite = test_path.split('java/')[1].replace(f'{name_test_class}.java', f'{name_focal_class}_ESTest.java')
                evosuite_test_path = f'evosuite-tests/{test_path_package_evosuite}'
                try:
                    if not os.path.exists(evosuite_test_path):
                        project_df_evosuite = project_df_evosuite[project_df_evosuite['Test_Path'] != row['Test_Path']] # Delete the row from the DataFrame that corresponds to the test class causing an error during Gradle execution
                        utils.write_file(test_path, human_test_class) # Restore to human version the test class causing an error during Gradle execution
                        utils.remove_evosuite_scaffolding_files(list(test_path))
                        utils.remove_directory_evosuite_command_line()
                        continue 
                    evosuite_content = utils.read_text_file(evosuite_test_path)
                    evosuite_content = evosuite_content.replace(F'public class {name_focal_class}_ESTest', f'public class {name_test_class}') 
                    evosuite_content = evosuite_content.replace('separateClassLoader = true', 'separateClassLoader = false') # when setting separateClassLoader to false, JaCoCo can correctly calculate code coverage
                    utils.save_generated_test(project, 'evosuite', None, name_test_class, evosuite_content)
                    utils.write_text_file(test_path, evosuite_content)
                except Exception as e:
                    print(f"An error occured while trying to copy the evosuite class test: {e}")
                    try:
                        write_build_gradle(path, build_gradle_before_evosuite)
                        utils.write_files(dictionary_for_restore)
                        utils.remove_evosuite_scaffolding_files(list(dictionary_for_restore.keys()))
                        utils.remove_directory_evosuite_command_line()
                        with open(output_path_failed, 'w') as file:
                            pass
                    except Exception as e:
                        write_build_gradle(path, original_build_gradle)
                        utils.remove_evosuite_scaffolding_files(list(dictionary_for_restore.keys()))
                        utils.write_files(dictionary_for_restore)
                        utils.remove_directory_evosuite_command_line()
                        print(f'An error occured while trying to open output_path_failed: {e}')
                        sys.exit(1)
                    restart_test_type = True
                    break # Switch to next test type 
                
                # Move the scaffolding file in the test class directory
                test_path_package_evosuite_scaffolding = test_path.split('java/')[1].replace(f'{name_test_class}.java', f'{name_focal_class}_ESTest_scaffolding.java')
                evosuite_test_path_scaffolding = f'evosuite-tests/{test_path_package_evosuite_scaffolding}'
                try:
                    shutil.move(evosuite_test_path_scaffolding, test_path.replace('.java', '').replace(f'{name_test_class}', ''))
                except Exception as e:
                    print(f"An error occured while trying to move the scaffolding file: {e}")
                    try:
                        write_build_gradle(path, build_gradle_before_evosuite)
                        utils.write_files(dictionary_for_restore)
                        utils.remove_evosuite_scaffolding_files(list(dictionary_for_restore.keys()))
                        utils.remove_directory_evosuite_command_line()
                        with open(output_path_failed, 'w') as file:
                            pass
                    except Exception as e:
                        write_build_gradle(path, original_build_gradle)
                        utils.remove_evosuite_scaffolding_files(list(dictionary_for_restore.keys()))
                        utils.write_files(dictionary_for_restore)
                        utils.remove_directory_evosuite_command_line()
                        print(f'An error occured while trying to open output_path_failed: {e}')
                        sys.exit(1)
                    restart_test_type = True
                    break # Switch to next test type 
                
                print("--//loading gradle execution..//")
                if run_gradle_test_command(path, module_df, system)[0]==False: # if error while running gradle
                    print(f"Package command failed for project: {project}_{module}, test type: {test_type}\n")
                    module_df_evosuite = module_df_evosuite[module_df_evosuite['Test_Path'] != row['Test_Path']] # Delete the row from the DataFrame that corresponds to the test class causing an error during Gradle execution
                    utils.write_file(test_path, human_test_class) # Restore to human version the test class causing an error during Gradle execution
                    utils.remove_evosuite_scaffolding_files(list(test_path))
                    utils.remove_directory_evosuite_command_line()
                    last_execution = False
                    continue 
                else:
                    last_execution = True
                    print(f"Package command completed for {project}_{module}\n") 


                utils.remove_directory_evosuite_command_line()

            if restart_test_type == True:
                continue
            
            if module_df_evosuite.empty: # If all the test classes provided by Evosuite failed during Gradle execution
                try:
                    with open(output_path_failed_gradle, 'w') as file:
                        pass
                except Exception as e:
                    write_build_gradle(path, original_build_gradle)
                    utils.write_files(dictionary_for_restore)
                    utils.remove_evosuite_scaffolding_files(list(dictionary_for_restore.keys()))
                    print(f'An error occured while trying to open output_path_failed_gradle: {e}')
                    sys.exit(1)
            else: # if at least one of the test classes provided by Evosuite runned succesfully during Gradle execution
                # configure the test smell detector
                csv_path_input_test_smell = utils.configure_test_smell_detector(module_df_evosuite, project)
                # Run the test smell detector
                path_csv_result_test_smell = utils.run_test_smell_detector(csv_path_input_test_smell, project, test_type, None, module)
                if path_csv_result_test_smell is None:
                    print("An error occured while trying to run the test smell detector")
                else:
                    print("The test smell detector ended successfully")  
                if last_execution == False: # if last gradle execution outcome is False, then I run one more time gradle
                    print("--//loading gradle execution..//")
                    if run_gradle_test_command(path, module_df, system)[0]==False: # if error while running gradle
                        print('An error occured while trying to execute the final version of test classes.\n')
                        try:
                            write_build_gradle(path, build_gradle_before_evosuite)
                            utils.remove_evosuite_scaffolding_files(list(dictionary_for_restore.keys()))
                            utils.write_files(dictionary_for_restore)
                            with open(output_path_failed, 'w') as file:
                                pass
                        except Exception as e:
                            write_build_gradle(path, original_build_gradle)
                            utils.remove_evosuite_scaffolding_files(list(dictionary_for_restore.keys()))
                            utils.write_files(dictionary_for_restore)
                            print(f'An error occured while trying to open output_path_failed: {e}')
                            sys.exit(1)
                        continue # Switch to next test type
                    # Retrieve Code Coverage and Cyclomatic Complexity on test classes
                measures_df = utils.retrieve_code_coverage_and_cyclomatic_complexity(f'compiledrepos/{project}', module_df_evosuite, project, 'Gradle', module)
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
                        write_build_gradle(path, original_build_gradle)
                        utils.remove_evosuite_scaffolding_files(list(dictionary_for_restore.keys()))
                        utils.write_files(dictionary_for_restore)
                        print(f'An error occured while trying to open output_path_failed: {e}')
                        sys.exit(1)
            utils.write_files(dictionary_for_restore)
            utils.remove_evosuite_scaffolding_files(list(dictionary_for_restore.keys()))
            write_build_gradle(path, build_gradle_before_evosuite)



        else:
            # Iterate over each technique
            for technique in techniques: 
                output_path_failed = f'./output/{project}/TestClasses_{project}_{test_type}_{technique}.failed' # Indicate that the test type/technique failed due to an error during the execution of the script or during a call to the API
                output_path_failed_gradle = f'./output/{project}/TestClasses_{project}_{test_type}_{technique}.gradlefailed' # Indicates that all the test classes of the test type failed during the gradle execution.
            
                restart_technique = False 
                print(f"\nProcessing test_type: {test_type}, technique: {technique}")
                module_df_technique = module_df.copy() # dataframe of the current test type and technique
                dictionary_for_restore = {} # dictionary that contains test_path as keys and the respective 'human_test_class' as values. This dictionary is used to restore the test classes to the human version.
                for index, row in module_df_technique.iterrows(): # iterate over each test class and focal class
                    name_focal_class = row['Focal_Class']
                    name_test_class = row['Test_Class']
                    focal_path = row['Focal_Path'].replace('repos/', 'compiledrepos/')
                    test_path = row['Test_Path'].replace('repos/', 'compiledrepos/')
                    last_execution = None # outcome of the last gradle execution, True = Build Success, False = Build Failure
                    testing_framework = None
                    if junit_version is not None:
                        testing_framework = 'Junit version ' + junit_version
                    elif is_testng_project(testng_version):
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
                            utils.write_files(dictionary_for_restore)
                            write_build_gradle(path, original_build_gradle)
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
                            utils.write_files(dictionary_for_restore)
                            write_build_gradle(path, original_build_gradle)
                            print(f'An error occured while trying to open output_path_failed: {e}')
                            sys.exit(1)
                        restart_technique = True # Switch to next technique
                        break 
                    
                    # Create the file and write the reponse to it
                    try:
                        human_test_class = utils.read_text_file(test_path) # save the human version of the test class
                        dictionary_for_restore[test_path] = human_test_class
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
                            utils.write_files(dictionary_for_restore)
                            write_build_gradle(path, original_build_gradle)
                            print(f'An error occured while trying to open output_path_failed: {e}')
                            sys.exit(1)
                        restart_technique = True # Switch to next technique
                        break 
                                

                    # Run the Gradle package command
                    print("--//loading gradle execution..//")
                    if run_gradle_test_command(path, module_df, system)[0]==False: # if error while running gradle
                        print(f"Package command failed for project: {project}_{module}, test type: {test_type}, technique: {technique}\n")
                        module_df_technique = module_df_technique[module_df_technique['Test_Path'] != row['Test_Path']] # Delete the row from the DataFrame that corresponds to the test class causing an error during Gradle execution
                        utils.write_file(test_path, human_test_class) # Restore to human version the test class causing an error during Gradle execution
                        last_execution = False
                        continue
                    else:
                        last_execution = True
                        print(f"Package command completed for {project}_{module}\n")

                if restart_technique == True:
                    continue

                    
                if module_df_technique.empty: # If all the test classes provided by the API failed during Gradle execution
                    try:
                        with open(output_path_failed_gradle, 'w') as file:
                            pass
                    except Exception as e:
                        utils.write_files(dictionary_for_restore)
                        write_build_gradle(path, original_build_gradle)
                        print(f'An error occured while trying to open output_path_failed_gradle: {e}')
                        sys.exit()
                else: # if at least one of the test classes provided by the API runned succesfully during Gradle execution
                    # configure the test smell detector
                    csv_path_input_test_smell = utils.configure_test_smell_detector(module_df_technique, project)
                    # Run the test smell detector
                    path_csv_result_test_smell = utils.run_test_smell_detector(csv_path_input_test_smell, project, test_type, technique, module)
                    if path_csv_result_test_smell is None:
                        print("An error occured while trying to run the test smell detector")
                    else:
                        print("The test smell detector ended successfully")  
                    if last_execution == False: # if last gradle execution outcome is False, then I run one more time gradle
                        print("--//loading gradle execution..//")
                        if run_gradle_test_command(path, module_df, system)[0]==False: # if error while running gradle
                            print('An error occured while trying to execute the final version of test classes.\n')
                            try:
                                utils.write_files(dictionary_for_restore)
                                with open(output_path_failed, 'w') as file:
                                    pass
                            except Exception as e:
                                utils.write_files(dictionary_for_restore)
                                write_build_gradle(path, original_build_gradle)
                                print(f'An error occured while trying to open output_path_failed: {e}')
                                sys.exit(1)
                            continue  # switch to next technique      
                    # Retrieve Code Coverage and Cyclomatic Complexity on test classes
                    measures_df = utils.retrieve_code_coverage_and_cyclomatic_complexity(f'compiledrepos/{project}', module_df_technique, project, 'Gradle', module)
                    if measures_df is not None:
                        output_csv_path = utils.generate_output_csv_test_type(project, test_type, technique, measures_df, path_csv_result_test_smell, module)
                        if output_csv_path is None:
                            print("An errore occured while trying to save the test type csv file!")
                        else:
                            print(f"DataFrame saved to {output_csv_path}")
                    else:
                        print(f"An occured while trying to retrieve data coverage of the project {project}_{module}.")
                        try:
                            with open(output_path_failed, 'w') as file:
                                pass
                        except Exception as e:
                            utils.write_files(dictionary_for_restore)
                            write_build_gradle(path, original_build_gradle)
                            print(f'An error occured while trying to open output_path_failed: {e}')
                            sys.exit(1)
                    utils.write_files(dictionary_for_restore)
    write_build_gradle(path, original_build_gradle)


