import os
import csv
import pandas as pd
import subprocess
import shutil
import re
import xml.etree.ElementTree as ET
import ctypes
import copy
import time
from datetime import datetime, timezone
import mavenLib
import toolchains
from dotenv import load_dotenv
from litellm import completion
from execution_manager import ExecutionManager

load_dotenv()


class CrossProcessFileLock:
    def __init__(self, target_path, timeout_sec=60.0):
        self.lock_path = f"{target_path}.lock"
        self.timeout_sec = timeout_sec
        self.handle = None

    def __enter__(self):
        parent = os.path.dirname(self.lock_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        deadline = time.time() + self.timeout_sec
        while True:
            try:
                self.handle = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
                os.write(self.handle, str(os.getpid()).encode("ascii", errors="ignore"))
                return self
            except FileExistsError:
                try:
                    if time.time() - os.path.getmtime(self.lock_path) > max(self.timeout_sec, 300.0):
                        os.remove(self.lock_path)
                        continue
                except OSError:
                    pass
                if time.time() >= deadline:
                    raise TimeoutError(f"Timed out waiting for file lock: {self.lock_path}")
                time.sleep(0.05)

    def __exit__(self, exc_type, exc, tb):
        if self.handle is not None:
            os.close(self.handle)
            self.handle = None
        try:
            os.remove(self.lock_path)
        except OSError:
            pass


def read_text_file(file_path):
    """
    Reads repository text files with deterministic encodings on Windows.
    Some sampled Java files contain bytes that cannot be decoded by cp1252.
    """
    for encoding in ("utf-8", "utf-8-sig", "cp1252"):
        try:
            with open(file_path, "r", encoding=encoding) as file:
                return file.read()
        except UnicodeDecodeError:
            continue
    with open(file_path, "r", encoding="utf-8", errors="replace") as file:
        return file.read()


def detect_java_source_compatibility(*source_paths):
    for source_path in source_paths:
        if not source_path:
            continue
        current = os.path.abspath(str(source_path))
        if os.path.isfile(current):
            current = os.path.dirname(current)
        while current and current != os.path.dirname(current):
            pom_path = os.path.join(current, "pom.xml")
            if os.path.exists(pom_path):
                pom_text = read_text_file(pom_path)
                for pattern in [
                    r"<maven\.compiler\.source>\s*([^<\s]+)\s*</maven\.compiler\.source>",
                    r"<source>\s*([^<\s]+)\s*</source>",
                    r"<release>\s*([^<\s]+)\s*</release>",
                ]:
                    match = re.search(pattern, pom_text)
                    if match:
                        return match.group(1).strip()
            current = os.path.dirname(current)
    return None


def java_language_rules(java_version):
    version = str(java_version or "").strip()
    if version in {"1.5", "5", "1.6", "6"}:
        return (
            "Use only Java 6 compatible syntax: do not use diamond operator <>, "
            "lambdas, method references, try-with-resources, multi-catch, var, "
            "or JUnit 5 APIs. Always write explicit generic types."
        )
    if version in {"1.7", "7"}:
        return (
            "Use only Java 7 compatible syntax: do not use lambdas, method "
            "references, var, streams, or JUnit 5 APIs."
        )
    if version:
        return f"Use syntax compatible with Java source level {version}."
    return "Use syntax compatible with the project's configured Java source level."


def write_text_file(file_path, content):
    parent = os.path.dirname(file_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(file_path, "w", encoding="utf-8", errors="replace") as file:
        file.write(content)


def safe_file_name(value):
    return str(value).replace("/", "_").replace("\\", "_").replace(":", "_")


def save_generated_test(project, generator, technique, test_class, content):
    generator_name = safe_file_name(generator)
    test_class_name = safe_file_name(test_class)
    if technique is None or technique == "-":
        file_name = f"response_{generator_name}_{test_class_name}.java"
    else:
        file_name = f"response_{generator_name}_{safe_file_name(technique)}_{test_class_name}.java"
    path = os.path.join("output", str(project), file_name)
    write_text_file(path, content)
    return path


def append_phase_log(phase, project="", module="", arm="", focal_class="", test_class="", status="", started_at=None, detail=""):
    log_path = os.getenv("RBL4_PHASE_LOG_CSV")
    if not log_path:
        return
    ended_at = time.time()
    row = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "phase": phase,
        "project": project,
        "module": module,
        "arm": arm,
        "sample_index": os.getenv("RBL4_SAMPLE_INDEX", ""),
        "class_key": os.getenv("RBL4_CLASS_KEY", ""),
        "focal_class": focal_class,
        "test_class": test_class,
        "status": status,
        "duration_sec": round(ended_at - started_at, 3) if started_at is not None else "",
        "detail": str(detail)[:4000],
    }
    fieldnames = [
        "timestamp_utc",
        "phase",
        "project",
        "module",
        "arm",
        "sample_index",
        "class_key",
        "focal_class",
        "test_class",
        "status",
        "duration_sec",
        "detail",
    ]
    parent = os.path.dirname(log_path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    def write_row(target_path):
        with CrossProcessFileLock(target_path):
            exists = os.path.exists(target_path)
            with open(target_path, "a", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
                if not exists:
                    writer.writeheader()
                writer.writerow(row)

    for attempt in range(10):
        try:
            write_row(log_path)
            return
        except (PermissionError, TimeoutError):
            time.sleep(0.1 * (attempt + 1))
    fallback_path = f"{log_path}.fallback.csv"
    try:
        write_row(fallback_path)
    except Exception as exc:
        print(f"[RBL4] Could not write phase log row: {exc}")


def set_gradle_variable(gradle_directory, gradle_version, system):
    """
    Sets the gradle variable accordingly to the given gradle version.
        Parameters:
                gradle_directory (String): the directory containing the gradle bin files.
                gradle_version (String): the version of Gradle
                system (String): the current OS (Windows, Linux, etc..)   
    """
    if gradle_version.startswith('4'):
        gradle_variable = f"{gradle_directory}/gradle-4.10.2"
    elif gradle_version.startswith('5'):
        gradle_variable = f"{gradle_directory}/gradle-5.6.4"
    elif gradle_version.startswith('6'):
        gradle_variable = f"{gradle_directory}/gradle-6.8.3"
    elif gradle_version.startswith('7'):
        gradle_variable = f"{gradle_directory}/gradle-7.6"
    elif gradle_version.startswith('8'):
        gradle_variable = f"{gradle_directory}/gradle-8.6"
    else:
        gradle_variable = f"{gradle_directory}/gradle-8.6"
    if system=="Windows":
        os.environ['PATH'] = f"{gradle_variable}/bin;{os.environ['PATH']}"
    else: # for Linux and Darwin
        os.environ['PATH'] = f"{gradle_variable}/bin:{os.environ['PATH']}"


def set_java_home(java_directory, java_version, system):
    """
    Sets the java home variable accordingly to the given java version.
        Parameters:
                java_directory (String): the directory containing the jdk files.
                java_version (String): the version of Java
                system (String): the current OS (Windows, Linux, etc..)   
    """
    java_home = toolchains.activate_java_home(java_version, min_major=8)
    if java_home is None:
        print("[WARNING] No compatible JDK found. Using system default Java.")
    else:
        print(f"[RBL4] {toolchains.describe(java_version, min_major=8)}")
    append_phase_log("toolchain", status="PASS" if java_home else "WARN", detail=toolchains.describe(java_version, min_major=8))


    
def read_class_content(file_path): 
    """
    Reads the content of a test class or focal class.
        Parameters:
                    file_path (string): the path of the test class/focal class
        Returns:
                    :the content of the given test class/focal class. 'None' if the given path is not a class, if the given path does not exist or if an error occurred while reading the file 
    """
    # if the given file is not a class
    if file_path.endswith(".java") == False:
        return None
    # If the file exists
    try:
        if os.path.exists(file_path):
            return read_text_file(file_path)
        else:
            # If the file does not exist, return None
            return None
    except Exception as e:
        print(e)
        # If an exception occurs, return None
        return None
    


def verify_if_folder_has_already_been_processed(folder):
    """
    Verifies if the given folder has already been processed. 
        Parameters:
                    folder: the ID of the project (that is the name of the corresponding folder)
        Returns:
                    :'True' if the folder has already been processed, False otherwise
    """
    compiled_path = f'compiledrepos/{folder}'
    failed_path = f'failedrepos/{folder}'
    if os.path.exists(compiled_path):
        return True
    elif os.path.exists(failed_path):
        return True
    else:
        return False
    


def count_files_of_a_dir(dir_path):
    """
    Returns the number of files given a directory path.
        Parameters:
                    dir_path: the directory path
        Returns:
                    count: the number of files
    """
    count = 0
    # Iterate directory
    for path in os.listdir(dir_path):
        # check if current path is a file
        if os.path.isdir(os.path.join(dir_path, path)):
            count += 1
    return count





def remove_missing_files_from_dataframe(project_df):
    """
    Removes from the given dataframe all the rows that contain a missing file (in other words, a file that is not present in the corresponding repository directory)        
        Parameters:
                    project_df (Dataframe): the dataframe containing the names and paths of the focal classes and the associated test classes
        Returns:
                    proejct_df (Dataframe): the new dataframe without the rows that contain a missing file
    """
    index_to_remove = set() # contains all the indexes that are to be removed because the corresponding focal path or test path is not present in the repository
    # If a test_path or a focal_path of the project_df (that is output/classes.csv filtered with the current project) doesn't exist in the repository, it will be removed from the dataframe
    for index, row in project_df.iterrows():
        if "repos/" in row['Test_Path']:
            test_path = row['Test_Path'].replace("repos/", "compiledrepos/")
            focal_path = row['Focal_Path'].replace("repos/", "compiledrepos/")
        else:
            project = row['Project']
            test_path = f"compiledrepos/{project}/" + row['Test_Path']
            focal_path = f"compiledrepos/{project}/" + row['Focal_Path']
        if not (os.path.isfile(test_path) and os.path.isfile(focal_path)):
            index_to_remove.add(index)
    project_df = project_df.drop(index=index_to_remove)
    project_df = project_df.reset_index()
    return project_df



def configure_test_smell_detector(project_dataframe, project):
    """
    Configures tsDetect to analyze the focal classes and the test classes specified in the given dataframe. 
    It must be executed prior to running tsDetect.
        Parameters:
                    project_dataframe (Dataframe): the dataframe that contains all the focal classes and test classes that are to be executed by tsDetect
                    project: the ID of the project
        Returns:
                    csv_path: the path of the CSV file that needs to be passed as input to the test smell detector
    """
    data = []
    project_df = project_dataframe.copy()

    def compiled_absolute_path(path_value, project_id):
        path_text = str(path_value).replace("\\", "/")
        if path_text.startswith("compiledrepos/"):
            compiled_path = path_text
        elif path_text.startswith("repos/"):
            compiled_path = path_text.replace("repos/", "compiledrepos/", 1)
        else:
            compiled_path = os.path.join("compiledrepos", str(project_id), path_text)
        return os.path.abspath(compiled_path)

    for index, row in project_df.iterrows():
        test_path_absolute = compiled_absolute_path(row['Test_Path'], project)
        focal_path_absolute = compiled_absolute_path(row['Focal_Path'], project)
        data.append([project, test_path_absolute, focal_path_absolute])
    df = pd.DataFrame(data)
    csv_path = f"output/{project}/pathToInputFile.csv"
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    df.to_csv(csv_path, index=False, header=False, na_rep="-")
    return csv_path




           

def run_test_smell_detector(csv_path, project, test_type, technique, module=None):
    """
    Runs tsDetect and saves the result in the 'TestSmellDetection_{project}_{test_type}_{technique}.csv' file. 
    It must be executed after configure_test_smell_detector().
    This function uses the TestSmellDetector.jar file; therefore, the tsDetect JAR file must be present in the same directory as utils.py
        Parameters:
                    csv_path: the path of the CSV file returned by configure_test_smell_detector()
                    project: the ID of the project
                    test_type: the type of the test
                    technique: the prompt technique adopted if the test type is an AI model, 'None' if it is not an AI model
                    module: the name of the module of the project
        Returns:
                    result_path: the path of the CSV file containing the results provided by tsDetect. 'None' if an error occurred while trying to run tsDetect
    """
    command = ["java", "-jar", "./TestSmellDetector.jar", csv_path]
    try:
        output = subprocess.check_output(command, stderr=subprocess.STDOUT)
    except Exception as e:
        print(e.output.decode("utf-8")) 
        return None
    files = os.listdir(os.getcwd())
    result_path = None
    for file in files:
        if file.startswith('Output_TestSmellDetection'): 
            safe_module = safe_file_name(module) if module is not None else None
            safe_test_type = safe_file_name(test_type)
            safe_technique = safe_file_name(technique) if technique is not None else None
            if module is None:  
                if technique is not None:
                    new_name = f'TestSmellDetection_{project}_{safe_test_type}_{safe_technique}.csv'
                else:
                    new_name = f'TestSmellDetection_{project}_{safe_test_type}.csv'
            else:
                if technique is not None:
                    new_name = f'TestSmellDetection_{project}_{safe_module}_{safe_test_type}_{safe_technique}.csv'
                else:
                    new_name = f'TestSmellDetection_{project}_{safe_module}_{safe_test_type}.csv'
            if os.path.exists(f'{new_name}'):
                os.remove(f'{new_name}')
            os.rename(file, new_name)  
            result_path = f'output/{project}/{new_name}'
            if os.path.exists(result_path):
                os.remove(result_path)
            shutil.move(new_name, f'output/{project}')
            break
    return result_path




def retrieve_code_coverage_and_cyclomatic_complexity(project_path, project_dataframe, project_id, type_project, module=None):
    """
    Retrieves the code coverage (Branch, Method, Line and Mutation) of the single classes from the given Maven/Gradle project.
    Retriveves also the cyclomatic_complexity of the single classes from the given Maven/Gradle projects.
    Parameters:
                    project_path: the path of the project
                    project_dataframe (Dataframe): the dataframe that contains the focal classes and the test classes of the project involved in the code and mutation coverage
                    project_id: the ID of the project
                    type_project: the type of the project (if Maven or Gradle project)
                    module (optional): the module to analyze
    Returns:
                    measures_df (DataFrame): The DataFrame containing the measures of code coverage and cyclomatic complexity for individual classes from the given Maven/Gradle project.

    """
    
    def focal_package_from_path(focal_path):
        normalized = str(focal_path or "").replace("\\", "/")
        if "main/java/" not in normalized:
            return ""
        rel = normalized.split("main/java/", 1)[1]
        parts = rel.split("/")[:-1]
        return ".".join(parts)

    project_df = project_dataframe.copy()
    project_df["Focal_Package"] = project_df["Focal_Path"].map(focal_package_from_path)
    if module is None:
        # find all modules and save their paths in a list for JaCoCo and PITest
        modules = search_modules(project_path, project_df, project_id, type_project)
        if not modules:
            return None
    else:
        modules = [module]
        
    jacoco_df_all = None
    pitest_df_all = None
    def first_existing_file(paths):
        for candidate in paths:
            if os.path.exists(candidate):
                return candidate
        return None

    def gradle_report_roots(project_root, module_name, module_path):
        roots = [module_path]
        normalized_module = str(module_name or "").replace("\\", "/").strip("/")
        if normalized_module:
            roots.append(os.path.join(project_root, "build", *normalized_module.split("/")))
            roots.append(os.path.join(project_root, "build", normalized_module.replace("/", "_")))
        roots.append(project_root)
        deduped = []
        seen = set()
        for root in roots:
            normalized = os.path.normpath(root)
            if normalized not in seen:
                deduped.append(root)
                seen.add(normalized)
        return deduped

    def append_nested_pitest_reports(candidates, report_root):
        for pitest_root in [
            os.path.join(report_root, f"build/reports/pitest"),
            os.path.join(report_root, f"reports/pitest"),
        ]:
            if not os.path.isdir(pitest_root):
                continue
            for current_root, _, files in os.walk(pitest_root):
                if "mutations.csv" in files:
                    candidates.append(os.path.join(current_root, "mutations.csv"))

    # For each module, retrieve the .csv files and read them to obtain the results from JaCoCo and PITest. All the results are then merged into a single DataFrame.
    for module in modules:
        jacoco_df = None
        pitest_df = None
        path = os.path.join(project_path, module)
        if type_project == 'Maven':
            jacoco_path = first_existing_file(
                [
                    os.path.join(path, f"target/site/jacoco/jacoco.csv"),
                    os.path.join(path, f"target/site/jacoco-ut/jacoco.csv"),
                ]
            )
            if jacoco_path:
                jacoco_df = pd.read_csv(jacoco_path)

            
            pitest_path = first_existing_file([os.path.join(path, f"target/pit-reports/mutations.csv")])
            if pitest_path:
                pitest_df = pd.read_csv(pitest_path, header=None)
        else:
            jacoco_candidates = []
            pitest_candidates = []
            for report_root in gradle_report_roots(project_path, module, path):
                jacoco_candidates.extend(
                    [
                        os.path.join(report_root, f"build/reports/jacoco/jacoco.csv"),
                        os.path.join(report_root, f"build/reports/jacoco-ut/jacoco.csv"),
                        os.path.join(report_root, f"reports/jacoco/jacoco.csv"),
                        os.path.join(report_root, f"reports/jacoco-ut/jacoco.csv"),
                        os.path.join(report_root, f"reports/jacoco/test/jacocoTestReport.csv"),
                        os.path.join(report_root, f"reports/jacoco/test/jacoco.csv"),
                    ]
                )
                pitest_candidates.extend(
                    [
                        os.path.join(report_root, f"build/reports/pitest/mutations.csv"),
                        os.path.join(report_root, f"reports/pitest/mutations.csv"),
                    ]
                )
                append_nested_pitest_reports(pitest_candidates, report_root)
            jacoco_path = first_existing_file(jacoco_candidates)
            pitest_path = first_existing_file(pitest_candidates)
            if jacoco_path:
                jacoco_df = pd.read_csv(jacoco_path)
            if pitest_path:
                pitest_df = pd.read_csv(pitest_path, header=None)
        
        if jacoco_df is None:
            append_phase_log(
                "coverage_metric_retrieval",
                project=project_id,
                module=module,
                status="FAIL",
                detail=f"jacoco_report_missing: {path}",
            )
            return None

        if pitest_df is None:
            append_phase_log(
                "coverage_metric_retrieval",
                project=project_id,
                module=module,
                status="WARN",
                detail=f"pit_report_missing; Mutation_Coverage set to 0: {path}",
            )
            pitest_df = project_df[["Focal_Class", "Focal_Package"]].drop_duplicates().copy()
            pitest_df["Mutation_Coverage"] = 0.0
        else:
            pitest_df[0] = pitest_df[0].str.replace('.java', '')
            pitest_df.columns = ['Focal_Class', 'Qualified_Class', 'Mutation_Name', 'Method_Name', 'Line_Number', 'Result', 'Killing_test']
            pitest_df['Focal_Package'] = pitest_df['Qualified_Class'].astype(str).apply(
                lambda value: value.rsplit('.', 1)[0] if '.' in value else ''
            )
            # Each row of the pitest_df DataFrame represents a mutation
            # Focal_Class: the name of the focal class without the .java extension
            # Package: the package of the focal class
            # Mutation_Name: the name of the engine used for the mutation
            # Method_Signature: the name of the method involved in the mutation
            # Line_Number: the number of the line of code involved in the mutation
            # Killing_Test: the test that ultimately killed the mutation
            pitest_df = pitest_df.groupby(['Focal_Class', 'Focal_Package']).agg(
                {'Result': lambda x: round((x == 'KILLED').sum() / len(x) * 100, 2)})
            pitest_df = pitest_df.rename(columns={'Result': 'Mutation_Coverage'})
            pitest_df = pitest_df.reset_index()
        pitest_df_all = pd.concat([pitest_df_all, pitest_df], ignore_index=True)

        jacoco_df = jacoco_df.rename(columns={'CLASS': 'Focal_Class', 'PACKAGE': 'Focal_Package'})
        jacoco_df_all = pd.concat([jacoco_df_all, jacoco_df], ignore_index=True)

        
    project_df = pd.merge(project_df, jacoco_df_all, how="left", on=['Focal_Class', 'Focal_Package'])
            

    # add branch, method and line coverage as a percentages
    # add the cyclomatic complexity
    measures_data = []
    for index, row in project_df.iterrows():
        focal_class = row['Focal_Class']
        try:
            if row['BRANCH_COVERED'] + row ['BRANCH_MISSED'] != 0:
                branch_coverage = round((row['BRANCH_COVERED']/(row['BRANCH_COVERED'] + row ['BRANCH_MISSED'])*100),2)
            else:
                branch_coverage = '-'
        except Exception as e:
            branch_coverage = '-'
            
        try:
            if row['METHOD_COVERED'] + row ['METHOD_MISSED'] != 0:
                method_coverage = round((row['METHOD_COVERED']/(row['METHOD_COVERED'] + row ['METHOD_MISSED'])*100),2)
            else:
                method_coverage = '-'
        except Exception as e:
            method_coverage = '-'
            
        try:
            if row['LINE_COVERED'] + row ['LINE_MISSED'] != 0:
                line_coverage = round((row['LINE_COVERED']/(row['LINE_COVERED'] + row ['LINE_MISSED'])*100),2)
            else:
                line_coverage = '-'
        except Exception as e:
            line_coverage = '-'
            
        try:
            cyclomatic_complexity = row['COMPLEXITY_MISSED'] + row['COMPLEXITY_COVERED']
        except Exception as e:
            cyclomatic_complexity = '-'
        try:
            loc = row['LINE_MISSED'] + row['LINE_COVERED']
        except Exception as e:
            loc = '-'


        measures_data.append([focal_class, cyclomatic_complexity, loc, branch_coverage, method_coverage, line_coverage])
    
    measures_df = pd.DataFrame(measures_data, columns=['Focal_Class', 'Cyclomatic_complexity', 'Lines_of_code', 'Branch_coverage', 'Method_coverage', 'Line_coverage'])
    measures_df = pd.merge(project_df, measures_df, how="left",
                            on=['Focal_Class'])
    measures_df = pd.merge(measures_df, pitest_df_all, how="left",
                                on=['Focal_Class', 'Focal_Package'])
    measures_df['Mutation_Coverage'] = measures_df['Mutation_Coverage'].fillna(0.0)
    measures_df.drop(columns=['GROUP', 'PACKAGE', 'Focal_Package', 'INSTRUCTION_MISSED', 'INSTRUCTION_COVERED', 'BRANCH_MISSED', 'BRANCH_COVERED', 'LINE_MISSED', 'LINE_COVERED', 'COMPLEXITY_MISSED', 'COMPLEXITY_COVERED', 'METHOD_MISSED', 'METHOD_COVERED'], inplace=True, errors='ignore')


    return measures_df





def generate_output_csv_test_type(project_id, test_type, technique, measures_df, csv_path_test_smell, module=None):
    """
    Generates and saves the output CSV file that contains all the measures about the single test type applied in the project (code coverage, mutation coverage and number of test smells)
        Parameters:
                    project_id: the ID of the project
                    test_type: the type of the test (e.g 'human', 'evosuite',...)
                    technique: the prompt technique adopted if the test type is an AI model, 'None' if it is not an AI model
                    measures_df (Dataframe): the dataframe containing measures about code coverage and cyclomatic complexity
                    csv_path_test_smell: the path of the CSV file returned by tsDetect
                    module: the name of the project module (optional)
        Returns:
                    csv_path: the path of the output CSV file that includes all the measures about the single test type applied in the project (code coverage, mutation coverage and number of test smells)
                    : 'None' if an error occurred
    """

    if csv_path_test_smell is not None:
        if os.path.exists(csv_path_test_smell):
            test_smell_df = pd.read_csv(csv_path_test_smell)
            # remove .java from the TestClass column
            test_smell_df['TestClass']=test_smell_df['TestClass'].str.replace('.java','')
            test_smell_df['TestClass'] = test_smell_df['TestClass'].str.split('/').str[-1]
            test_smell_df = test_smell_df.drop(columns=['App', 'TestFilePath', 'ProductionFilePath', 'RelativeTestFilePath', 'RelativeProductionFilePath'])
            # rename the column TestClass to Test_Class
            test_smell_df = test_smell_df.rename(columns={'TestClass':'Test_Class'})
            measures_df = pd.merge(measures_df, test_smell_df, how="left", on=['Test_Class'])

    # replace /repos with /compiledrepos in Focal_path e Test_Path
    for index, row in measures_df.iterrows():
        measures_df.at[index, 'Focal_Path'] = row['Focal_Path'].replace('repos/', 'compiledrepos/')
        measures_df.at[index, 'Test_Path'] = row['Test_Path'].replace('repos/', 'compiledrepos/')

    csv_path = None
    safe_test_type = safe_file_name(test_type)
    safe_technique = safe_file_name(technique) if technique is not None else None
    safe_module = safe_file_name(module) if module is not None else None
    if module is None:
        if technique is not None:
            csv_path = f'./output/{project_id}/TestClasses_{project_id}_{safe_test_type}_{safe_technique}.csv'
        else:
            csv_path = f'./output/{project_id}/TestClasses_{project_id}_{safe_test_type}.csv'
    else:
        if technique is not None:
            csv_path = f'./output/{project_id}/TestClasses_{project_id}_{safe_module}_{safe_test_type}_{safe_technique}.csv'
        else:
            csv_path = f'./output/{project_id}/TestClasses_{project_id}_{safe_module}_{safe_test_type}.csv'
    try:
        os.makedirs(os.path.dirname(csv_path), exist_ok=True)
        measures_df.to_csv(csv_path, index=False, na_rep="-")
    except Exception as e:
        append_phase_log(
            "agone_result_csv_write",
            project=project_id,
            module=module or "",
            arm=test_type,
            status="FAIL",
            detail=f"{type(e).__name__}: {e}; csv_path={csv_path}",
        )
        return None
    return csv_path

    


def search_modules(project_path, project_dataframe, project_id, type_project):
    """
    Searches all the modules where are stored pitest and jacoco measures. 
    It works with either Maven and Gradle projects.
        Parameters:
                    project_path: the path of the proejct
                    project_dataframe (Dataframe): the dataframe containing the focal classes and the test classes for which to search the modules
                    project_id: the ID of the project
                    type_project: the type of the project (if Maven or Gradle project)
        Returns:
                    modules (List): the list of modules found
                    
    """
    project_df = project_dataframe.copy()
    modules = set()
    if type_project == 'Maven':
        for index, row in project_df.iterrows():
            location = row['Test_Path'].replace(f'repos/{project_id}/', '').replace(f"{row['Test_Class']}.java", '')
            while not os.path.isfile(f"{project_path}/{location}/target/site/jacoco/jacoco.csv") and not os.path.isfile(f"{project_path}/{location}/target/site/jacoco-ut/jacoco.csv"):
                location = os.path.dirname(location)
                if location == '':
                    break
            if location != '':
                modules.add(location)
    elif type_project == 'Gradle':
        for index, row in project_df.iterrows():
            location = row['Test_Path'].replace(f'repos/{project_id}/', '').replace(f"{row['Test_Class']}.java", '')
            while not os.path.isfile(f"{project_path}/{location}/build/reports/jacoco/jacoco.csv") and not os.path.isfile(f"{project_path}/{location}/build/reports/jacoco-ut/jacoco.csv"):
                location = os.path.dirname(location)
                if location == '':
                    break
            if location != '':
                modules.add(location)
    return list(modules)





def verify_mockito(type_project, path):
    """
    Verifies if the given project implements the Mockito framework or not.
        Parameters:
                    type_project: the type of the project (if Maven or Gradle project)
                    path: the path of the project or of the module
        Returns:
                   :'True' if the given project implements the Mockito framework, 'False' if the given project does not implement the Mockito framework or if an error occurred
                   
    """
    if type_project == 'Maven':
        ns = {'mvn': 'http://maven.apache.org/POM/4.0.0'}
        try:
            tree = ET.parse(os.path.join(path, 'pom.xml'))
            root = tree.getroot()
            dependencies_root=root.findall('mvn:dependencies/mvn:dependency', ns)
            dependencies_management=root.findall('mvn:dependencyManagement/mvn:dependencies/mvn:dependency', ns)
            all_dependencies=dependencies_root+dependencies_management
            for dependency in all_dependencies:
                group_id = dependency.find('mvn:groupId', ns)
                artifact_id = dependency.find('mvn:artifactId', ns)
                if group_id is not None and group_id.text.__contains__('org.mockito'):
                    return True
                elif artifact_id is not None and artifact_id.text.__contains__('mockito'):
                    return True
            return False
        except Exception as e:
            print(e)
            return False

    elif type_project == 'Gradle':
        path_build_gradle=os.path.join(path, 'build.gradle')
        path_build_gradle_kts=os.path.join(path, 'build.gradle.kts')
        path_file = None # path of the file to be opened
        try:
            if os.path.exists(path_build_gradle):
                path_file = path_build_gradle
            else:
                path_file = path_build_gradle_kts
            with open(path_file, 'r') as file:
                content=file.read()
                if content.__contains__('mockito'):
                    return True
                else:
                    return False
        except Exception as e:
            print(e)
            return False
    return False




def make_api_call(test_type, technique, focal_class, focal_path, testing_framework, java_version, has_mockito, test_path, name_test_class, project_structure, project_dependencies, package_test_class=None):
    """
    Given a focal class, it generates the test class making an API call to the AI model corresponding to the test type. 
    Note: At the moment, it supports only 'gpt-4o-mini' test type.
    Note: At the moment, it supports the 'zeroshot1', 'zeroshot2', 'oneshot1' and 'oneshot2' techniques.

        Parameters:
                test_type: the type of the test (e.g 'gpt-4o-mini',...)
                technique: the prompt technique 
                focal_class: the content of the focal class
                testing_framework (String): a sentence that indicates to the AI model which testing framework (and eventually which version) it can use.
                java_version: the java version implemented in the focal class
                has_mockito (Boolean): 'True' if the prompt should inform the AI model that it can use the Mockito framework., 'False' otherwise
                test_path: the path of the test
                name_test_class: the currently name of the test class (ALERT* must be without the .java suffix, e.g. 'foo') 
                package_test_class (None): the package of the test class
        Returns:
                response: the java test class returned by the API call, 'None' if the response is Anomalous

    """
    def replace_placeholders(text, replacements_dict):
        return re.sub(r'\{\{(\w+)\}\}', lambda match: replacements_dict.get(match.group(1), match.group(0)), text)
    def get_attribute_by_model(model_name, attribute_name):
        agents = ExecutionManager.get_agents()
        return agents.get(model_name, None).get(attribute_name, None)
    def get_prompt_by_name(prompt_name):
        prompts = ExecutionManager.get_prompts()
        raw_prompt = prompts.get(prompt_name, None)
        final_prompt = copy.deepcopy(raw_prompt)
        for role in final_prompt:
            role['content'] = replace_placeholders(role['content'], prompt_data)
        return final_prompt

    set_key_as_os_environ(test_type)
    java_class_example = 'package com.example.project;\n\npublic class Calculator {\n\n	public int add(int a, int b) {\n\n	return a + b;\n	}\n\n}'
    test_class_example = 'package com.example.project;\n\nimport static org.junit.jupiter.api.Assertions.assertEquals;\nimport org.junit.jupiter.api.DisplayName;\nimport org.junit.jupiter.api.Test;\nimport org.junit.jupiter.params.ParameterizedTest;\nimport org.junit.jupiter.params.provider.CsvSource;\n\nclass CalculatorTests {\n\n	@Test\n	@DisplayName("1 + 1 = 2")\n	void addsTwoNumbers() {\n		Calculator calculator = new Calculator();\n		assertEquals(2, calculator.add(1, 1), "1 + 1 should equal 2");\n	}\n\n	@ParameterizedTest(name = "{0} + {1} = {2}")\n	@CsvSource({\n			"0,    1,   1",\n			"1,    2,   3",\n			"49,  51, 100",\n			"1,  100, 101"\n	})\n	void add(int first, int second, int expectedResult) {\n		Calculator calculator = new Calculator();\n		assertEquals(expectedResult, calculator.add(first, second),\n				() -> first + " + " + second + " should equal " + expectedResult);\n	}\n}'
    example_testing_framework = 'JUnit 5'
    example_java_version = '11'
    # Define the response
    response = None
    can_use_mockito = None
    try:
        # Leggi il contenuto della classe di test
        test_file_content = read_text_file(test_path)
    except Exception as e:
        print(e)
        return None

    if has_mockito == True or test_file_content.__contains__("mockito"):
        can_use_mockito = "You can use the Mockito framework."
    else:
        can_use_mockito = "You cannot use the Mockito framework."

    set_public = "You must declare the test class and all the test methods with the public access modifier."

    messages = []

    effective_java_version = detect_java_source_compatibility(test_path, focal_path) or java_version
    prompt_data = {
        "focal_class": focal_class,
        "focal path": focal_path,
        "testing_framework": testing_framework,
        "java_version": effective_java_version,
        "java_language_rules": java_language_rules(effective_java_version),
        "project_structure": str(project_structure),
        "project_dependencies": str(project_dependencies),
        "java_class_example": java_class_example,
        "test_class_example": test_class_example,
        "example_testing_framework": example_testing_framework,
        "example_java_version": example_java_version,
        "can_use_mockito": can_use_mockito,
        "set_public": set_public

    }
    prompt = get_prompt_by_name(technique)

    messages = [{"role": role["role"], "content": role["content"]} for role in prompt]

    temperature = get_attribute_by_model(test_type, 'temperature')
    api_base = get_attribute_by_model(test_type, 'api_base')
    stream = bool(get_attribute_by_model(test_type, 'stream'))
    response = completion(model=test_type, messages=prompt, temperature=temperature, api_base=api_base, stream=stream)

    if response == " " or response is None or not response.choices:
        return None, messages
    
    result = response.choices[0].message['content']
    # Check if "```java" and "```" are in the result
    if "```.java\n" in result and "```" in result:
        # Extract only the text between "```java" and "```"
        match = re.search(r'```.java\n(.*?)```', result, re.DOTALL)
        if match:
            result = match.group(1)
            if result is None:
                # Gestisci il caso in cui result è None
                return None, messages
            # Extract the class name from the result
            class_name_match = re.search(r'class (\w+)', result)
            if class_name_match:
                if class_name_match.group(1) != name_test_class:
                    # Cange the class name to the original one
                    result = re.sub(r'class (\w+)', f'class {name_test_class}', result)

        # Verify if the package is specified in the test class provided by the API call. If not, add it manually.
        if package_test_class:
            cleaned_content = re.sub(r'//.*', '', result) # Remove the single-line comments
            cleaned_content = re.sub(r'/\*.*?\*/', '', cleaned_content, flags=re.DOTALL)  # Remove the multi-lines comments
            pattern = r'package\s+' + re.escape(package_test_class) + r';'
            match = re.search(pattern, cleaned_content)
            if match is None:
                result = 'package' + ' ' + package_test_class + ';' + '\n' + result
        messages.append({"role": "assistant", "content": result})  # Aggiungi la risposta al contesto
        return result, messages
    elif "```java" in result and "```" in result:
        # Extract only the text between "```java" and "```"
        match = re.search(r'```java(.*?)```', result, re.DOTALL)
        if match:
            result = match.group(1)
            if result is None:
                # Gestisci il caso in cui result è None
                return None, messages
            # Extract the class name from the result
            class_name_match = re.search(r'class (\w+)', result)
            if class_name_match:
                if class_name_match.group(1) != name_test_class:
                    # Cange the class name to the original one
                    result = re.sub(r'class (\w+)', f'class {name_test_class}', result)

        # Verify if the package is specified in the test class provided by the API call. If not, add it manually.
        if package_test_class:
            cleaned_content = re.sub(r'//.*', '', result) # Remove the single-line comments
            cleaned_content = re.sub(r'/\*.*?\*/', '', cleaned_content, flags=re.DOTALL)  # Remove the multi-lines comments
            pattern = r'package\s+' + re.escape(package_test_class) + r';'
            match = re.search(pattern, cleaned_content)
            if match is None:
                result = 'package' + ' ' + package_test_class + ';' + '\n' + result
        messages.append({"role": "assistant", "content": result})  # Aggiungi la risposta al contesto
        return result, messages
    elif result and result.strip():
        result = result.strip()
        class_name_match = re.search(r'class\s+(\w+)', result)
        if class_name_match and class_name_match.group(1) != name_test_class:
            result = re.sub(r'class\s+(\w+)', f'class {name_test_class}', result, count=1)
        if package_test_class:
            cleaned_content = re.sub(r'//.*', '', result)
            cleaned_content = re.sub(r'/\*.*?\*/', '', cleaned_content, flags=re.DOTALL)
            pattern = r'package\s+' + re.escape(package_test_class) + r';'
            if re.search(pattern, cleaned_content) is None:
                result = 'package' + ' ' + package_test_class + ';' + '\n' + result
        messages.append({"role": "assistant", "content": result})
        return result, messages
    return None, messages


def set_key_as_os_environ(test_type):
    """
    Given the AI test type, sets the appropriate key as an environment variable.
    This function must be executed to make the API call to the corresponding AI model.
    Note: At the moment, it supports only the 'gpt-4o-mini', 'claude3', 'perplexity' test types.
        Parameters:
                test_type: the type of the test (e.g 'gpt-4o-mini',...)
       
    """
    # Set ENV variables
    if test_type == 'gpt-4o-mini':
        os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")
    elif test_type == 'claude3':
        os.environ["ANTHROPIC_API_KEY"] = os.getenv("ANTHROPIC_API_KEY")
    elif test_type == 'perplexity':
        os.environ['PERPLEXITYAI_API_KEY'] = os.getenv('PERPLEXITYAI_API_KEY')
    elif test_type == 'gemini':
        os.environ['GEMINI_API_KEY'] = os.getenv('GEMINI_API_KEY')




def generate_output_csv_project(project, project_dataframe, test_types, techniques, module=None):
    """
    Generates and saves the output CSV file that includes all the measures about all the test types applied in the project (code coverage, mutation coverage and number of test smells).
    Parameters:
                project: the ID of the project
                project_dataframe (Dataframe): the dataframe that contains all the focal classes and test classes involved in the test types 
                test_types: all the test types
                techniques: all the prompt techniques associated with the AI test types
                module: the name of the module (optional)
    Returns:
                df_output (Dataframe): the dataframe that includes all the measures about all the test types applied in the project (code coverage, mutation coverage and number of test smells).
                output_csv_path: the path of the CSV file that includes all the measures about all the test types applied in the project (code coverage, mutation coverage and number of test smells)    
    """
    # richiama il dataframe df_chance che si trova in mavenLib.py
    df_chance = mavenLib.df_chance
    project_df = project_dataframe.copy()
    files = os.listdir(f'output/{project}')
    # dictionary where the keys are the dataframes label and the values are the dataframes. There is a dataframe for each TestClasses file
    dataframes = dict()
    for test_type in test_types:
        if test_type == 'human' or  test_type == 'evosuite':
            dataframes[test_type] = pd.DataFrame()
        else:
            for technique in techniques:
                dataframes[f'{test_type}_{technique}'] = pd.DataFrame()

    # if the TestClasses file is maven failed or gradle failed (all the test classes failed during the maven execution), then leave the corresponding dataframe empty
    # if the TestClasses file is failed (generic error in AgoneTest.py) or not found, then set the corresponding dataframe to None
    # if the TestClasses file is a csv, then set the dataframe to the content of the csv
    if module is None:
        for key in dataframes.keys():
            find = False
            for file in files:
                if file.__contains__(f"TestClasses_{project}_{key}"):
                    find = True
                    if file.endswith(".csv"):
                        dataframes[key] = pd.read_csv(f'output/{project}/{file}')
                    elif file.endswith('.failed'):
                        dataframes[key] = None     
                    break
            if find == False:
                dataframes[key] = None
    else:
         safe_module = safe_file_name(module)
         for key in dataframes.keys():
            find = False
            for file in files:
                if file.__contains__(f"TestClasses_{project}_{safe_module}_{key}") or file.__contains__(f"TestClasses_{project}_{module}_{key}"):
                    find = True
                    if file.endswith(".csv"):
                        dataframes[key] = pd.read_csv(f'output/{project}/{file}')
                    elif file.endswith('.failed'):
                        dataframes[key] = None
                    break
            if find == False:
                dataframes[key] = None
        

    # Remove from the dictionary the keys associated to a dataframe setted to None
    key_to_remove = set()
    for key in dataframes.keys():
        if dataframes[key] is None:
            key_to_remove.add(key)
    for key in key_to_remove:
        del dataframes[key]

    
    focal_classes = project_df['Focal_Class'].tolist() 
    data_df_output = []
    df_output = pd.DataFrame(data_df_output, columns=['ID_Focal_Class', 'Cyclomatic_Complexity_Focal_Class', 'Lines_Of_Code_Focal_Class', 'Generator(LLM/EVOSUITE)', 'Prompt_Technique', 'Branch_Coverage', 'Line_Coverage', 'Method_Coverage', 'Compilation', 'Mutation_Coverage','NumberOfMethods', 'Assertion Roulette', 'Conditional Test Logic',
        'Constructor Initialization', 'Default Test', 'EmptyTest',
        'Exception Catching Throwing', 'General Fixture', 'Mystery Guest',
        'Print Statement', 'Redundant Assertion', 'Sensitive Equality',
        'Verbose Test', 'Sleepy Test', 'Eager Test', 'Lazy Test',
        'Duplicate Assert', 'Unknown Test', 'IgnoredTest', 'Resource Optimism',
        'Magic Number Test', 'Dependent Test', 'Chance'])

    for focal_class in focal_classes:
        for test_type in test_types: 
            if test_type != "human" and test_type != "evosuite": # in other words, if test_type is an AI model
                for technique in techniques:
                    if (f"{test_type}_{technique}" in dataframes.keys()) == False:
                        continue
                    dataframe = dataframes.get(f'{test_type}_{technique}')
                    if dataframe is not None:
                        find_focal_class = False
                        for index, row in dataframe.iterrows():
                            if row['Focal_Class'] == focal_class:
                                if 'NumberOfMethods' in row.index:
                                    data_df_output = [f'{project}_{focal_class}', row['Cyclomatic_complexity'], row['Lines_of_code'], test_type, technique, row['Branch_coverage'], row['Line_coverage'], row['Method_coverage'], "1", row['Mutation_Coverage'], row['NumberOfMethods'], row['Assertion Roulette'], row['Conditional Test Logic'], row['Constructor Initialization'], row['Default Test'], row['EmptyTest'], row['Exception Catching Throwing'], row['General Fixture'], row['Mystery Guest'], row['Print Statement'], row['Redundant Assertion'], row['Sensitive Equality'], row['Verbose Test'], row['Sleepy Test'], row['Eager Test'], row['Lazy Test'], row['Duplicate Assert'], row['Unknown Test'], row['IgnoredTest'], row['Resource Optimism'], row['Magic Number Test'], row['Dependent Test']]
                                else:
                                    data_df_output = [f'{project}_{focal_class}', row['Cyclomatic_complexity'], row['Lines_of_code'], test_type, technique, row['Branch_coverage'], row['Line_coverage'], row['Method_coverage'], "1", row['Mutation_Coverage']]
                                find_focal_class = True
                                break
                        if find_focal_class == False:
                            data_df_output = [f'{project}_{focal_class}', row['Cyclomatic_complexity'], row['Lines_of_code'], test_type, technique, "-", "-", "-", "0", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-"]

                        if len(data_df_output) != len(df_output.columns):
                            missing_length = len(df_output.columns) - len(data_df_output)
                            print(f"Adjusting data_df_output length. Expected {len(df_output.columns)}, got {len(data_df_output)}")
                            data_df_output += ['-'] * missing_length  # Completa con '-' per le colonne mancanti

                        if len(data_df_output) == len(df_output.columns):
                            df_output.loc[len(df_output)] = data_df_output
                            nom = focal_class + 'Test'
                            for index, row in df_chance.iterrows():
                                if row['Test_Class'] == nom:
                                    df_output.at[len(df_output)-1, 'Chance'] = row['Chance']
                            if df_output.at[len(df_output) - 1, 'Chance'] == 6:
                                df_output.at[len(df_output) - 1, 'Compilation'] = "0"

                        else:
                            print(f"[Error]Error: Mismatched columns for focal class {focal_class}. Expected {len(df_output.columns)}, got {len(data_df_output)}")
                         
            else: # if the test_type is 'human' or 'evosuite'
                if (f"{test_type}" in dataframes.keys()) == False:
                        continue
                dataframe = dataframes[f'{test_type}']
                if dataframe is not None:
                    find_focal_class = False
                    for index, row in dataframe.iterrows():
                        if row['Focal_Class'] == focal_class:
                            if 'NumberOfMethods' in row.index:
                                data_df_output = [f'{project}_{focal_class}', row['Cyclomatic_complexity'], row['Lines_of_code'], test_type, "-", row['Branch_coverage'], row['Line_coverage'], row['Method_coverage'], "1", row['Mutation_Coverage'], row['NumberOfMethods'], row['Assertion Roulette'], row['Conditional Test Logic'], row['Constructor Initialization'], row['Default Test'], row['EmptyTest'], row['Exception Catching Throwing'], row['General Fixture'], row['Mystery Guest'], row['Print Statement'], row['Redundant Assertion'], row['Sensitive Equality'], row['Verbose Test'], row['Sleepy Test'], row['Eager Test'], row['Lazy Test'], row['Duplicate Assert'], row['Unknown Test'], row['IgnoredTest'], row['Resource Optimism'], row['Magic Number Test'], row['Dependent Test']]
                            else:
                                data_df_output = [f'{project}_{focal_class}', row['Cyclomatic_complexity'], row['Lines_of_code'], test_type, "-", row['Branch_coverage'], row['Line_coverage'], row['Method_coverage'], "1", row['Mutation_Coverage']]
                            find_focal_class = True
                            break
                    if find_focal_class == False:
                        data_df_output = [f'{project}_{focal_class}', row['Cyclomatic_complexity'], row['Lines_of_code'], test_type, "-", "-", "-", "0", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-"]

                    if len(data_df_output) != len(df_output.columns):
                        missing_length = len(df_output.columns) - len(data_df_output)
                        print(
                            f"Adjusting data_df_output length. Expected {len(df_output.columns)}, got {len(data_df_output)}")
                        data_df_output += ['-'] * missing_length  # Completa con '-' per le colonne mancanti

                    if len(data_df_output) == len(df_output.columns):
                            df_output.loc[len(df_output)] = data_df_output
                    else:
                        print(f"[Error]Error: Mismatched columns for focal class {focal_class}. Expected {len(df_output.columns)}, got {len(data_df_output)}")
                         
    if module is None:
        df_output_path = f"output/{project}/{project}_Output.csv"
    else:
        df_output_path = f"output/{project}/{project}_{module}_Output.csv"
    os.makedirs(os.path.dirname(df_output_path), exist_ok=True)

    df_new_execution = pd.DataFrame()
    if os.path.exists(df_output_path):
        try:
            df_previous_execution = pd.read_csv(df_output_path)
            if not df_previous_execution.empty and not df_output.empty:
                df_new_execution = pd.concat([df_previous_execution, df_output], ignore_index=True)
            elif df_previous_execution.empty and not df_output.empty:
                df_new_execution = df_output
            else:
                df_new_execution = df_previous_execution
        except Exception as e:
            try:
                df_new_execution = df_output
            except Exception as e:
                print(e)
                return None
    else:
        try:
            df_new_execution = df_output
        except Exception as e:
            print(e)
            return None
    df_new_execution.drop_duplicates(subset={'ID_Focal_Class', 'Generator(LLM/EVOSUITE)', 'Prompt_Technique'}, keep='last', inplace=True)
    df_new_execution.to_csv(df_output_path, index=False, na_rep="-") 
        
    output_csv_path = f"/{project}_Output.csv"

    return df_new_execution, output_csv_path




def write_file(file_path, content):
    """
    Writes the given content in the given file. 
        Parameters:
                    file_path: the path of the file
                    content: the content that needs to be written                
    """
    try:
        write_text_file(file_path, content)
    except Exception as e:
        print(e)



def write_files(dictionary_for_write):
   """
    Writes the given contents in the given files.
        Parameters:
                    dictionary_for_write: it has file paths as keys and file contents as values
    """
   for file_path, content in dictionary_for_write.items():
    try:
        write_text_file(file_path, content)
    except Exception as e:
       print(e)



def remove_evosuite_scaffolding_files(test_paths):
    """
    Removes the scaffolding files added by evosuite.       
        Parameters:
                    test_paths (List): list containing all the paths that refere to test classes presumably associated to a scaffolding file
    """
    for test_path in test_paths:
        name_focal_class = ''
        regex_name_focal_class = r'/([^\/]+)\.java'
        match = re.search(regex_name_focal_class, test_path)
        if match:
            name_focal_class = match.group(0)
            name_focal_class = name_focal_class.replace('.java', '').replace('/', '').replace('Test', '').replace('test', '')

        regex_pattern = r'.*/'
        match = re.search(regex_pattern, test_path)
        if match:
            scaffolding_path = f"{match.group(0)}{name_focal_class}_ESTest_scaffolding.java"
            try:
                if os.path.exists(scaffolding_path):
                    os.remove(scaffolding_path)
            except Exception as e:
                print(e)



def remove_dot_evosuite_dir(project, module):
    """
    Removes the .evosuite directory    
        Parameters:
                    project: the ID of the project containing the .evosuite directory
                    module: the project module containing the .evosuite directory
    """
    if module is not None:
        dot_evosuite_to_remove = f'compiledrepos/{project}/{module}/.evosuite'
        try:
            if os.path.exists(dot_evosuite_to_remove):
                shutil.rmtree(dot_evosuite_to_remove)
        except Exception as e:
            print(e)


def find_module_class(project, class_path):
    """
    Searches the module of the given focal or test class. 
        Parameters:
                    project: the ID of the project
                    class_path: the path of the focal or test class
        Returns:
                    module: the module of the given focal of test class, 'None' if an error occurred

    """
    # Search the current module
    module = None
    regex = rf"{project}/(.*?)/"
    match = re.search(regex, class_path)
    if match:
        module = match.group(0)
        module = module.replace('/', '').replace(f'{project}', '')
        return  module
    else:
        return None
    

def remove_directory_evosuite_command_line():
    """
    Removes the directory generated by evosuite jar file  
    """
    evosuite_tests_path = 'evosuite-tests'
    evosuite_report_path = 'evosuite-report'
    if os.path.exists(evosuite_tests_path):
        shutil.rmtree(evosuite_tests_path)
    if os.path.exists(evosuite_report_path):
        shutil.rmtree(evosuite_report_path)


def check_version(version):
    """
    Check if the given version matches the correct pattern for versions (e.g., 1.2.3, 1.2, or 12.3.1).
        Parameters:
                version: the version to check
        Returns:
                :True if the given version matches the correct pattern for versions, False otherwise."""
    pattern = r'^(\d{1,3})(\.(\d{1,3}))*$'
    if version is None:
        return False
    if re.match(pattern, version):
        return True
    else:
        return False
    

def find_package(class_path):
    """
    Search the package of the given class.
        Parameters:
                class_path: the path of the focal or test class.
        Returns:
                :the package as a string, 'None' if the package was not found
    """
    class_content = read_text_file(class_path)
    cleaned_content = re.sub(r'//.*', '', class_content) # Remove the single-line comments
    cleaned_content = re.sub(r'/\*.*?\*/', '', cleaned_content, flags=re.DOTALL)  # Remove the multi-lines comments
    match = re.search(r'package\s+([\w.]+);', cleaned_content)
    if match:
        return match.group(1)
    else:
        return None
    


def find_max_value(values):
    """
    Search for the maximum value in the given list or set.
    
    Parameters:
            values (list or set): the list or set of values in which to search for the maximum.
        
    Returns:
            :the maximum value found, or 'None' if the given list/set is empty.
    """
    if len(values) == 0:
        return None
    if isinstance(values, set):
        values = list(values)
    max_value = values[0]
    for value in values:
        if value>max_value:
            max_value = value
    return max_value
            
    

def find_min_value(values):
    """
    Search for the minimum value in the given list or set.
    
    Parameters:
            values (list or set): the list or set of values in which to search for the minimum.
        
    Returns:
            :the minimum value found, or 'None' if the given list/set is empty.
    """
    if len(values) == 0:
        return None  
    if isinstance(values, set):
        values = list(values)
    min_value = values[0]
    for value in values:
        if value < min_value:
            min_value = value
    return min_value



def is_admin(system):
    """
    Check if the script is running with or without the administrator privileges.
    Parameters:
            system (String): the current OS (Windows, Linux, etc..)   
    Returns:
            :True if the script is running with the administrator privileges, False otherwise.
    """
    if system == 'Windows':
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False
    else:
        try:
            if os.geteuid() == 0:
                return True
            else:
                return False
        except:
            return False
