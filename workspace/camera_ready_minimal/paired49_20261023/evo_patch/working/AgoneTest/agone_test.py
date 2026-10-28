import json
import os
import sys
import platform
import pandas as pd
import numpy as np
import utils
import mavenLib
import gradleLib
import warnings
from execution_manager import ExecutionManager
import project_structure_analyzer as psa
import project_dependencies_analyzer as pda
from dotenv import load_dotenv

warnings.simplefilter(action='ignore', category=FutureWarning)

load_dotenv()

ExecutionManager.initialize()
supported_test_types = ExecutionManager.get_agents_list()
supported_techniques = ExecutionManager.get_prompts_list()

def select_projects_to_process():
    """
    Does the intersection of three sets: projects in the classes.csv file, projects in the project_info.json file, and projects in the compiledrepos directory.
    Returns:
        projects_to_process (Set): the projects resulted from the intersection of the three sets, 'None' if an error occurred
    """
    # Read the classes.csv file into a DataFrame
    try:
        df = pd.read_csv('./output/classes.csv')
        projects_in_csv = [str(project) for project in df['Project'].unique().tolist()]
    except Exception as e:
        print(f"Error reading classes.csv: {e}")
        return None

    if os.path.exists('./compiledrepos'):
        # Get the list of directories in ./compiledrepos
        projects_in_compiledrepos = os.listdir('./compiledrepos')
    else:
        return None

    try:
        with open('output/project_info.json', "r") as project_info_file:
            project_info_data = json.load(project_info_file)
            # Get the list of projects in project_info.json
            projects_in_project_info = list(project_info_data.keys())
    except Exception as e:
        print(f"Error reading project_info.json: {e}")
        return None

    projects_to_process = set(projects_in_csv) & set(projects_in_compiledrepos) & set(projects_in_project_info)
    return projects_to_process

def generate_files(test_types, techniques, execution_override, correct, specific_project=None):
    """
    Starts the AgoneTest.py script.
    It generates the following files: output_agone_classes.csv, output_agone_projects.csv, output_agone_mean.csv, output_agone_mean_filtered.csv, and output_agone_info.txt.
    Parameters:
        test_types (List): the list of test types to execute.
        techniques (List): the list of prompt techniques (for the AI test types) to execute.
        execution_override (bool): True if the user wants to re-execute the projects that have already been processed, False otherwise.
        specific_project (optional): the ID of the project to execute (if the function has to execute only one specific project).
    """
    print("Starting to generate files")
    projects_to_process = select_projects_to_process()
    java_directory = os.getenv("JAVA_DIRECTORY")
    if projects_to_process is None:
        print("An error occurred")
        sys.exit(1)
    # False if the project selected by the user was not found, True otherwise
    flag_find = False
    # Extract all versions from project_info.json
    try:
        with open('output/project_info.json', "r") as project_info_file:
            project_info_data = json.load(project_info_file)
    except Exception as e:
        print(f"Error opening project_info.json: {e}")
        sys.exit(1)

    compatible_projects_evosuite, number_projects_evosuite = calculate_number_projects_evosuite_compatibility(projects_to_process, project_info_data)
    print(f"\nAt least {number_projects_evosuite} projects are compatible for evosuite execution!\n")

    output_agone_classes_path = "output/output_agone_classes.csv"
    all_test_types = test_types.copy()
    all_techniques = techniques.copy()
    # Iterate over each project
    for project in projects_to_process:
        if specific_project is not None and project != specific_project:
            continue
        print(f"\n\n\n-------------------------------------------------------------------")
        print(f"PROCESSING PROJECT: '{project}'")
        project_path = f'./compiledrepos/{project}'
        psa.save_project_structure(project_path)
        pda.save_project_dependencies(project_path)
        project_structure = psa.get_structure(project_path)
        project_dependencies = pda.get_structure(project_path)
        flag_find = True

        if not execution_override:
            test_types = set()
            techniques = set()
            for all_test_type in all_test_types:
                if all_test_type == 'human' or all_test_type == 'evosuite':
                    if not verify_if_project_test_type_has_already_been_executed(project, all_test_type, 'output/output_agone_projects.csv', None):
                        test_types.add(all_test_type)
                else:
                    for all_technique in all_techniques:
                        if not verify_if_project_test_type_has_already_been_executed(project, all_test_type, 'output/output_agone_projects.csv', all_technique):
                            test_types.add(all_test_type)
                            techniques.add(all_technique)
            clean_previous_execution_files_project(project)
            test_types = list(test_types)
            techniques = list(techniques)
            # Move the 'human' test type to the first position
            if 'human' in test_types:
                test_types.remove('human')
                test_types.insert(0, 'human')
            elif test_types:
                test_types.insert(0, 'human')
            if 'evosuite' in test_types:
                test_types.remove('evosuite')
                test_types.insert(1, 'evosuite')
        else:
            clean_previous_execution_files_project(project)
            test_types = all_test_types
            techniques = all_techniques

        modules = project_info_data.get(project, {}).get('modules')
        if modules:
            for module in modules:
                name = project + '_' + module
                type_project = project_info_data.get(name, {}).get('type')
                compiler_version = project_info_data.get(name, {}).get('version')
                java_version = project_info_data.get(name, {}).get('java_version')
                junit_version = project_info_data.get(name, {}).get('junit_version')
                testng_version = project_info_data.get(name, {}).get('testng_version')
                result_df_process_module = process_module(module, project, project_path, java_version, junit_version, testng_version, compiler_version, type_project, test_types, techniques, project_structure, project_dependencies)
                if result_df_process_module is not None:
                    if generate_output_agone_files(output_agone_classes_path, result_df_process_module, all_test_types, all_techniques):
                        print(f"Output agone files updated!")
                    else:
                        print(f"Error generating output CSV files for module '{module}'")
                else:
                    print(f"Error processing output CSV files for module '{module}'")
            continue

        type_project = project_info_data.get(project, {}).get('type')
        compiler_version = project_info_data.get(project, {}).get('version')
        java_version = project_info_data.get(project, {}).get('java_version')
        junit_version = project_info_data.get(project, {}).get('junit_version')
        testng_version = project_info_data.get(project, {}).get('testng_version')
        has_mockito = utils.verify_mockito(type_project, project_path)

        utils.set_java_home(java_directory, java_version, system)
        # Read the classes.csv file into a DataFrame
        df = pd.read_csv('./output/classes.csv')
        project_df = df[df['Project'].isin([int(project)])] # I get only the rows of the current project
        project_df = utils.remove_missing_files_from_dataframe(project_df)
        if type_project == 'Maven':
            print(f"\n{project} is a Maven project")
            if mavenLib.process_maven_project(project, test_types, techniques, project_path, project_df, compiler_version, java_version, junit_version, testng_version, has_mockito, system, correct, project_structure, project_dependencies) == 0:
                continue
        elif type_project == 'Gradle':
            print(f"\n{project} is a Gradle project")
            if gradleLib.process_gradle_project(project, test_types, techniques, project_path, project_df, compiler_version, java_version, junit_version, testng_version, has_mockito, system, correct, project_structure, project_dependencies) == 0:
                continue

        result_generate_output_df_project, output_csv_path = utils.generate_output_csv_project(project, project_df, test_types, techniques)
        if result_generate_output_df_project is not None:
            print(f'{output_csv_path} saved correctly')
            if generate_output_agone_files(output_agone_classes_path, result_generate_output_df_project, all_test_types, all_techniques):
                print(f"Output agone files updated!")
            else:
                print(f"Error generating output CSV files for project '{project}'")
        else:
            print(f"Error processing output CSV files for project '{project}'")

        if os.path.exists(f'output/{project}/pathToInputFile.csv'):
            try:
                os.remove(f'output/{project}/pathToInputFile.csv')
            except Exception as e:
                print(f"Error deleting pathToInputFile.csv: {e}")

    if not flag_find:
        print(f"Project '{specific_project}' not found")
        return

def generate_output_agone_files(output_agone_classes_path, new_output_agone_classes_df, test_types_user, techniques_user):
    """
    This function generates the output_agone_classes, output_agone_projects, output_agone_mean and output_agone_mean_filtered CSV files. It also generates the output_agone_info.txt file. 
    Parameters:
                output_agone_classes_path: the path of the CSV file containing the information about all the classes processed.
                new_output_agone_classes_df: the dataframe containing updated information about the classes of a new project or module, related to code coverage, mutation coverage, and the number of test smells.
                test_types_user (List): the list containing all the test types that the user wants to execute.
                techniques_user (List): the list containing all the techniques that the user wants to execute.
    Returns:
                : True if all the generations have been executed successfully, False otherwise.
    """
    # Initialize the output_agone_classes dataframe.
    output_agone_classes_df = pd.DataFrame()
    # Retrieve the previous output_agone_classes dataframe if it exists.
    # Concat the previous dataframe with the new one in the output_agone_class_df.
    if os.path.exists(output_agone_classes_path):
        try:
            old_dataframe_output_agone = pd.read_csv(output_agone_classes_path)
            if not new_output_agone_classes_df.empty and not old_dataframe_output_agone.empty:
                output_agone_classes_df = pd.concat([old_dataframe_output_agone, new_output_agone_classes_df], ignore_index=True)
            elif new_output_agone_classes_df.empty and not old_dataframe_output_agone.empty:
                output_agone_classes_df = old_dataframe_output_agone
            else:
                output_agone_classes_df = new_output_agone_classes_df
        except Exception as e:
            try:
                output_agone_classes_df = new_output_agone_classes_df
            except Exception as e:
               print(e)
               return False
    else:
        try:
            output_agone_classes_df = new_output_agone_classes_df
        except Exception as e:
            return False
    # Remove the duplicated rows
    output_agone_classes_df.drop_duplicates(subset={'ID_Focal_Class', 'Generator(LLM/EVOSUITE)', 'Prompt_Technique'}, keep='last', inplace=True)
    output_agone_classes_df.to_csv(output_agone_classes_path, index=False, na_rep="-")
    if (generate_output_agone_projects(output_agone_classes_df) == False):
        return False
    if (generate_output_agone_mean(supported_test_types, supported_techniques, output_agone_classes_df)==False):
        return False
    if (generate_output_agone_info(supported_test_types, supported_techniques, supported_test_types, supported_techniques)==False):
        return False
    if (generate_output_agone_mean_filtered(supported_test_types, supported_techniques) == False):
        return False
    if (generate_lists_projects_classes_filtered(supported_test_types, supported_techniques) == False):
        return False
    return True

def check_project_has_all_test_types(project, test_types, techniques, output_agone_projects_df):
    """
    This function checks if the given project has been executed with all the given test types and techniques.
    Parameters:
                project: the ID of the project to execute
                test_types (List): the list of test types to execute.
                techniques (List): the list of prompt techniques (for the AI test types) to execute. 
                output_agone_projects_df = The DataFrame containing information about the processed projects
    Returns:
                : True if the project has been executed with all the given test types and techniques, False otherwise.
    """
    for test_type in test_types:
            if test_type != 'human' and test_type != 'evosuite': # if AI test type
                for technique in techniques:
                    exists = ((output_agone_projects_df['Project'] == project) & (output_agone_projects_df['Generator(LLM/EVOSUITE)'] == test_type) & (output_agone_projects_df['Prompt_Technique'] == technique)).any()
                    if exists == False:
                        return False      
            else:
                exists = ((output_agone_projects_df['Project'] == project) & (output_agone_projects_df['Generator(LLM/EVOSUITE)'] == test_type)).any()
                if exists == False:
                    return False
    return True

def check_class_has_all_test_types(java_class, test_types, techniques, output_agone_classes_df):
    """
    This function checks if the given java focal class has been executed with all the given test types and techniques.
    By 'executed', it means that the compilation either failed or was successful.
    Parameters:
                java_class (String): string that specifies both the ID of the project and the name of the Java focal clas (format: IDproject_focalClassName).
                test_types (List): the list of test types.
                techniques (List): the list of prompt techniques (for the AI test types).
                output_agone_classes_df (Dataframe  )= dataframe containing information about processed classes.
    Returns:
                : True if the java focal class has been executed with all the given test types and techniques, False otherwise.
    """
    for test_type in test_types:
            if test_type != 'human' and test_type != 'evosuite': # if AI test type
                for technique in techniques:
                    exists = ((output_agone_classes_df['ID_Focal_Class'] == java_class) & (output_agone_classes_df['Generator(LLM/EVOSUITE)'] == test_type) & (output_agone_classes_df['Prompt_Technique'] == technique)).any()
                    if exists == False:
                        return False      
            else:
                exists = ((output_agone_classes_df['ID_Focal_Class'] == java_class) & (output_agone_classes_df['Generator(LLM/EVOSUITE)'] == test_type)).any()
                if exists == False:
                    return False
    return True

def check_class_has_all_compilation_test_types(java_class, test_types, techniques, output_agone_classes_df):
    """
    This function checks if the given java focal class has been executed with all the given test types and techniques.
    By 'executed', it is meant only that the compilation was successful.
    Parameters:
                java_class (String): string that specifies both the ID of the project and the name of the Java focal clas (format: IDproject_focalClassName).
                test_types (List): the list of test types.
                techniques (List): the list of prompt techniques (for the AI test types).
                output_agone_classes_df (Dataframe  )= dataframe containing information about processed classes.
    Returns:
                : True if the java focal class has been executed with all the given test types and techniques, False otherwise.
    """
    for test_type in test_types:
            if test_type != 'human' and test_type != 'evosuite': # if AI test type
                for technique in techniques:
                    exists = ((output_agone_classes_df['ID_Focal_Class'] == java_class) & (output_agone_classes_df['Generator(LLM/EVOSUITE)'] == test_type) & (output_agone_classes_df['Prompt_Technique'] == technique)).any()
                    if exists == False:
                        return False   
                    row = output_agone_classes_df[
                        (output_agone_classes_df['ID_Focal_Class'] == java_class) & 
                        (output_agone_classes_df['Generator(LLM/EVOSUITE)'] == test_type) & 
                        (output_agone_classes_df['Prompt_Technique'] == technique)]
                    if not row.empty:
                        if row.iloc[0]['Compilation'] == 1 or row.iloc[0]['Compilation'] == '1':
                            return True
                    return False
            else:
                exists = ((output_agone_classes_df['ID_Focal_Class'] == java_class) & (output_agone_classes_df['Generator(LLM/EVOSUITE)'] == test_type)).any()
                if exists == False:
                    return False
                row = output_agone_classes_df[
                    (output_agone_classes_df['ID_Focal_Class'] == java_class) & 
                    (output_agone_classes_df['Generator(LLM/EVOSUITE)'] == test_type)]
                if not row.empty:
                    if row.iloc[0]['Compilation'] == 1 or row.iloc[0]['Compilation'] == '1':
                        return True
                return False
    return True

def generate_lists_projects_classes_filtered(test_types, techniques):
    """
    This function generates CSV files containing only the projects and classes that were executed with the given test types and techniques.
    Parameters:
                test_types (List): the list of test types.
                techniques (List): the list of prompt techniques (for the AI test types).
    Returns:
                (bool): True if the generation has been executed successfully, False if an error occurred.

    """
    initial_check = False
    output_agone_projects_path = 'output/output_agone_projects.csv'
    output_agone_classes_path = 'output/output_agone_classes.csv'
    if os.path.exists(output_agone_projects_path) and os.path.exists(output_agone_classes_path):
        output_agone_projects_df = pd.read_csv(output_agone_projects_path)
        output_agone_classes_df = pd.read_csv(output_agone_classes_path)
        if not output_agone_projects_df.empty and not output_agone_projects_df.empty:
            initial_check = True
    if initial_check == False:
        return False
    projects = output_agone_projects_df['Project'].unique()
    projects_set = set()
    classes_set = set()
    java_classes =  output_agone_classes_df['ID_Focal_Class'].unique()
    for project in projects:
        if (check_project_has_all_test_types(project, test_types, techniques, output_agone_projects_df) == True):
            if (check_project_cyclomatic_complexity_and_loc(project, output_agone_projects_df) == True):
                projects_set.add(project)
    for java_class in java_classes:
        if (check_class_has_all_test_types(java_class, test_types, techniques, output_agone_classes_df) == True):
            if (check_class_cyclomatic_complexity_and_loc(java_class, output_agone_classes_df) == True):
                classes_set.add(java_class)
    projects_list_df = pd.DataFrame(list(projects_set),columns=['Project'])
    classes_list_df = pd.DataFrame(list(classes_set), columns=['ID_Focal_Class'])
    try:
        projects_list_path = 'output/output_agone_projects_filtered.csv'
        classes_list_path = 'output/output_agone_classes_filtered.csv'

        projects_list_df.to_csv(projects_list_path, index=False)
        classes_list_df.to_csv(classes_list_path, index=False)
        return True
    except Exception as e:
        return False

def check_class_cyclomatic_complexity_and_loc(java_class, output_agone_classes_df):
    """
    This function checks if the given dataframe contains information about the cyclomatic complexity and the loc of the given java class.
    Parameters:
                java_class (String): string that specifies both the ID of the project and the name of the Java focal clas (format: IDproject_focalClassName).
                output_agone_classes_df (Dataframe  )= dataframe containing information about processed classes.
    Returns:
                : True if the given dataframe contains information about the cyclomatic complexity and the loc of the given java class, False otherwise.
    """
    try:
        class_row = output_agone_classes_df[output_agone_classes_df['ID_Focal_Class'] == java_class].iloc[0]
        if class_row['Cyclomatic_Complexity_Focal_Class'] is not None and class_row['Cyclomatic_Complexity_Focal_Class'] != '-' and not pd.isna(class_row['Cyclomatic_Complexity_Focal_Class']):
            if class_row['Lines_Of_Code_Focal_Class'] is not None and class_row['Lines_Of_Code_Focal_Class'] != '-' and not pd.isna(class_row['Lines_Of_Code_Focal_Class']):
                return True
        return False
    except Exception as e:
        return False

def generate_output_agone_mean_filtered(test_types, techniques):
    """
    This function generates the 'output_agone_mean_filtered.csv' file.
    It includes information about all the given test types and techniques, considering only the classes that have been correctly processed with all the specified test types and techniques and for which data on cyclomatic complexity and LOC have been reported.
    The information refers to the mean values of code coverage, strong mutation coverage and number of test smells.
    Parameters:
                test_types (List): the list of test types.
                techniques (List): the list of prompt techniques (for the AI test types).
    Returns:
                (bool): True if the generation has been executed successfully, False if an error occurred.

    """
    output_agone_classes_path = 'output/output_agone_classes.csv'
    output_agone_classes_df = pd.read_csv(output_agone_classes_path)
    if output_agone_classes_df is None or output_agone_classes_df.empty:
        return True
    output_agone_mean_filtered_path = 'output/output_agone_mean_filtered.csv'
    java_classes =  output_agone_classes_df['ID_Focal_Class'].unique()
    # All the Java classes that have been executed correctly with all test types (compilation failed inclued), and for which the cyclomatic complexity and LOC are known.
    java_classes_filtered = set()
    # All the Java classes that have been executed correctly with all test types (compilation failed not inclued), and for which the cyclomatic complexity and LOC are known.
    java_classes_filtered_compilation = set()
    for java_class in java_classes:
        if (check_class_has_all_test_types(java_class, test_types, techniques, output_agone_classes_df) == True):
            if (check_class_cyclomatic_complexity_and_loc(java_class, output_agone_classes_df) == True):
                java_classes_filtered.add(java_class)
    for java_class in java_classes_filtered:
        if (check_class_has_all_compilation_test_types(java_class, test_types, techniques, output_agone_classes_df) == True):
               java_classes_filtered_compilation.add(java_class)
        
    output_agone_classes_filtered_df = output_agone_classes_df[output_agone_classes_df['ID_Focal_Class'].isin(java_classes_filtered)].copy()
    output_agone_classes_filtered_df_compilation = output_agone_classes_df[output_agone_classes_df['ID_Focal_Class'].isin(java_classes_filtered_compilation)].copy()

    df_output = pd.DataFrame(columns=[
        'Test_type', 'Prompt_Technique', 'Compilation%', 'Branch_Coverage%',
        'Line_Coverage%', 'Method_Coverage%', 'Mutation_Coverage%',
        'NumberOfMethods', 'Assertion Roulette', 'Conditional Test Logic',
        'Constructor Initialization', 'Default Test', 'EmptyTest',
        'Exception Catching Throwing', 'General Fixture', 'Mystery Guest',
        'Print Statement', 'Redundant Assertion', 'Sensitive Equality',
        'Verbose Test', 'Sleepy Test', 'Eager Test', 'Lazy Test',
        'Duplicate Assert', 'Unknown Test', 'IgnoredTest', 'Resource Optimism',
        'Magic Number Test', 'Dependent Test'
    ])
    for test_type in test_types:
        if test_type == 'human' or test_type == 'evosuite':
            percentage_completition = calculate_compilation(test_type, None, output_agone_classes_filtered_df)
            percentage_branch_coverage = calculate_coverage_mean(test_type, None, 'Branch', output_agone_classes_filtered_df_compilation)
            percentage_line_coverage = calculate_coverage_mean(test_type, None, 'Line', output_agone_classes_filtered_df_compilation)
            percentage_method_coverage = calculate_coverage_mean(test_type, None, 'Method', output_agone_classes_filtered_df_compilation)
            percentage_mutation_coverage = calculate_coverage_mean(test_type, None, 'Mutation', output_agone_classes_filtered_df_compilation)
            test_smell_mean = calculate_test_smell_mean(test_type, None, output_agone_classes_filtered_df_compilation)

            if percentage_completition is None:
                percentage_completition = 'None'
            if percentage_branch_coverage is None:
                percentage_branch_coverage = 'None'
            if percentage_line_coverage is None:
                percentage_line_coverage = 'None'
            if percentage_method_coverage is None:
                percentage_method_coverage = 'None'
            if percentage_mutation_coverage is None:
                percentage_mutation_coverage = 'None'
            if test_smell_mean is None:
                test_smell_mean = 'None'
            test_smell_mean = list(test_smell_mean.values())
            data = [test_type, '-', percentage_completition, percentage_branch_coverage, percentage_line_coverage, percentage_method_coverage, percentage_mutation_coverage]
            data.extend(test_smell_mean)
            df_output.loc[len(df_output)] = data

        else: # if the test type is an AI test type
            for technique in techniques:
                    percentage_completition = calculate_compilation(test_type, technique, output_agone_classes_filtered_df)
                    percentage_branch_coverage = calculate_coverage_mean(test_type, technique, 'Branch', output_agone_classes_filtered_df_compilation)
                    percentage_line_coverage = calculate_coverage_mean(test_type, technique, 'Line', output_agone_classes_filtered_df_compilation)
                    percentage_method_coverage = calculate_coverage_mean(test_type, technique, 'Method', output_agone_classes_filtered_df_compilation)
                    percentage_mutation_coverage = calculate_coverage_mean(test_type, technique, 'Mutation', output_agone_classes_filtered_df_compilation)
                    test_smell_mean = calculate_test_smell_mean(test_type, technique, output_agone_classes_filtered_df_compilation)
                    
                    if percentage_completition is None:
                        percentage_completition = 'None'
                    if percentage_branch_coverage is None:
                        percentage_branch_coverage = 'None'
                    if percentage_line_coverage is None:
                        percentage_line_coverage = 'None'
                    if percentage_method_coverage is None:
                        percentage_method_coverage = 'None'
                    if percentage_mutation_coverage is None:
                        percentage_mutation_coverage = 'None'
                    if test_smell_mean is None:
                        test_smell_mean = 'None'
                    test_smell_mean = list(test_smell_mean.values())
                    data = [test_type, technique, percentage_completition, percentage_branch_coverage, percentage_line_coverage, percentage_method_coverage, percentage_mutation_coverage]
                    data.extend(test_smell_mean)
                    df_output.loc[len(df_output)] = data    
    try:
        df_output.to_csv(output_agone_mean_filtered_path, index=False, na_rep="-")  # Set index=False to exclude row indices in the CSV file
        return True
    except Exception as e:
        return False

def check_project_cyclomatic_complexity_and_loc(project, output_agone_projects_df):
    """
    This function checks if the given dataframe contains information about the cyclomatic complexity and the loc of the given project.
    Parameters:
                project: the ID of the project.
                output_agone_projects_df (F) = The DataFrame containing information about the processed projects.
    Returns:
                : True if the given dataframe contains information about the cyclomatic complexity and the loc of the given project, False otherwise.
    """
    try:
        project_row = output_agone_projects_df[output_agone_projects_df['Project'] == project].iloc[0]
        if project_row['Cyclomatic_Complexity'] is not None and project_row['Cyclomatic_Complexity'] != '-' and not pd.isna(project_row['Cyclomatic_Complexity']):
            if project_row['Lines_Of_Code'] is not None and project_row['Lines_Of_Code'] != '-' and not pd.isna(project_row['Lines_Of_Code']):
                return True
        return False
    except Exception as e:
        return False

def generate_output_agone_info(test_types, techniques, test_types_user, techniques_user):
    """
    This function generates the 'output_agone_info.txt' file. 
    It contains information about the projects that have been processed.
    The information regards the number of projects that have been processed with each test type and technique.
    Parameters:
                test_types (List): the list of all the test types processed.
                techniques (List): the list of all the prompt techniques (for the AI test types) processed.
                test_types_user (List): the list of test types selected by the user.
                techniques_user (List): the list of techniques selected by the user.
    Returns:
                : True if the generation has been executed successfully, False otherwise.
    """
    output_agone_projects_path = 'output/output_agone_projects.csv'
    output_agone_classes_path = 'output/output_agone_classes.csv'
    output_agone_info_path = 'output/output_agone_info.txt'
    try:
        output_agone_projects_df = pd.read_csv(output_agone_projects_path)
        output_agone_classes_df = pd.read_csv(output_agone_classes_path)
        with open(output_agone_info_path, "w") as file:
            file.write("\nPROJECTS\n")
            projects = output_agone_projects_df['Project'].unique()
            num_of_projects_all = len(projects)
            file.write("Total number of projects processed: " + str(num_of_projects_all))
            for test_type in test_types:
                filtered_df_test_type = output_agone_projects_df[output_agone_projects_df['Generator(LLM/EVOSUITE)'] == test_type]
                num_of_projects_test_type = len(filtered_df_test_type['Project'].unique())
                file.write("\nTotal number of projects processed with " + test_type + ": " + str(num_of_projects_test_type))
                if test_type != 'human' and test_type != 'evosuite':  # if AI test type
                    for technique in techniques:
                        filtered_df_technique = filtered_df_test_type[filtered_df_test_type['Prompt_Technique'] == technique]
                        num_of_projects_technique = len(filtered_df_technique['Project'].unique())
                        file.write("\nTotal number of projects processed with " + test_type + " " + technique + ": " + str(num_of_projects_technique))
            num_of_projects_all_test_types = 0
            for project in projects:
                if (check_project_has_all_test_types(project, test_types_user, techniques_user, output_agone_projects_df)) == True:
                    num_of_projects_all_test_types = num_of_projects_all_test_types + 1
            file.write("\nTotal number of projects that have been processed with all the test types and techniques selected by the user: " + str(num_of_projects_all_test_types))
            file.write("\n-------------------------------\n")
            file.write("\nCLASSES\n")
            java_classes = output_agone_classes_df['ID_Focal_Class'].unique()
            num_of_classes_all = len(java_classes)
            file.write("Total number of classes processed: " + str(num_of_classes_all))
            for test_type in test_types:
                filtered_df_test_type = output_agone_classes_df[output_agone_classes_df['Generator(LLM/EVOSUITE)'] == test_type]
                num_of_classes_test_type = len(filtered_df_test_type['ID_Focal_Class'].unique())
                file.write("\nTotal number of classes processed with " + test_type + ": " + str(num_of_classes_test_type))
                if test_type != 'human' and test_type != 'evosuite':  # if AI test type
                    for technique in techniques:
                        filtered_df_technique = filtered_df_test_type[filtered_df_test_type['Prompt_Technique'] == technique]
                        num_of_classes_technique = len(filtered_df_technique['ID_Focal_Class'].unique())
                        file.write("\nTotal number of classes processed with " + test_type + " " + technique + ": " + str(num_of_classes_technique))
            num_of_classes_all_test_types = 0
            for java_class in java_classes:
                if (check_class_has_all_test_types(java_class, test_types_user, techniques_user, output_agone_classes_df)) == True:
                    num_of_classes_all_test_types = num_of_classes_all_test_types + 1
            file.write("\nTotal number of classes that have been processed with all the test types and techniques selected by the user: " + str(num_of_classes_all_test_types))
    except Exception as e:
        return False
    return True

def calculate_compilation(test_type, technique, df):
    """
    This function calculates the percentage of occurrences of '1' values in the compilation column of the given gdataframe.
    Particolarly, it calculates the percentage value for the specified test type and technique.
    Parameters:
                test_type: the type of test for which to calculate the compilation percentage.
                technique: the technique associated with the AI test type, 'None' if the test type is non AI-related.
                df: the dataframe containing information about processed classes.
    Returns:
                percentage_compilation: the percentage of occurrences of '1' values in the compilation column of the dataframe. 'None' if there is no data in the dataframe.
    """
    df_type = df[df['Generator(LLM/EVOSUITE)'] == test_type]
    if technique is not None:
        df_type = df_type[df_type['Prompt_Technique'] == technique]
    counts_type = df_type['Compilation'].value_counts()
    # Convert counts to DataFrame
    counts_type = pd.DataFrame(counts_type)
    if counts_type.empty:
        return None
    # Reset index to make 'Compilation' a column
    counts_type.reset_index(inplace=True)
    # Rename the columns
    counts_type.columns = ['Compilation', 'Count']
    # Calculate the total count of 'Compilation' values where it's either 1 or 0
    total_count = counts_type['Count'].sum()
    # Calculate the count for 'Compilation' value 1
    if '1' in counts_type['Compilation'].values:
        count_compilation_1 = counts_type[counts_type['Compilation'] == '1']['Count'].values[0]
    elif 1 in counts_type['Compilation'].values:
        count_compilation_1 = counts_type[counts_type['Compilation'] == 1]['Count'].values[0]
    else:
        count_compilation_1 = 0
    # Calculate the percentage of 'Compilation' value 1
    percentage_compilation = round((count_compilation_1 / total_count) * 100, 2)
    return percentage_compilation

def calculate_coverage_mean(test_type, technique, criterion, df):
    """
    This function calculates the mean value of the given coverage criterion in the specified dataframe. 
    Particolarly, it calculates the mean for the given test type and technique.
    Parameters:
                test_type: the test type for which to calculate the mean.
                technique: the technique associated with the AI test type, 'None' if the test type is not AI-related.
                criterion: the coverage criterion for which to calculate the mean.
                df: the dataframe containing information about processed classes.

    Returns:
                mean: the mean value of the given coverage criterion in the specified dataframe. 'None' if there is no data about the specified criterion coverage in the dataframe.
    """
    df_type = df[df['Generator(LLM/EVOSUITE)'] == test_type]
    if technique is not None:
        df_type = df_type[df_type['Prompt_Technique'] == technique]        
    df_type.reset_index(drop=True, inplace=True)
    coverage_values = df_type[f'{criterion}_Coverage'].astype(str).tolist()
    sum_coverage = 0
    item_coverage = 0
    for coverage_value in coverage_values:
        if coverage_value is not None and coverage_value != '-' and coverage_value != 'nan' and not pd.isna(coverage_value):
            sum_coverage = sum_coverage + float(coverage_value)
            item_coverage = item_coverage + 1
    if item_coverage == 0:
        return None
    else:
        mean = round(sum_coverage/item_coverage, 2)
        return mean

def calculate_test_smell_mean(test_type, technique, df):
    """
    This function calculates the mean value of the number of test smell occurrences for the given test type, technique, and dataframe.
    Parameters:
                test_type (String): the test type.
                technique (String): the technique.
                df (DataFrame): the dataframe containing the data.
    Returns:
                dict: A dictionary with the mean values for each test smell.
    """
    df_type = df[df['Generator(LLM/EVOSUITE)'] == test_type]
    if technique is not None:
        df_type = df_type[df_type['Prompt_Technique'] == technique]
    df_type.reset_index(drop=True, inplace=True)

    test_smell_columns = [
        'NumberOfMethods', 'Assertion Roulette', 'Conditional Test Logic',
        'Constructor Initialization', 'Default Test', 'EmptyTest',
        'Exception Catching Throwing', 'General Fixture', 'Mystery Guest',
        'Print Statement', 'Redundant Assertion', 'Sensitive Equality',
        'Verbose Test', 'Sleepy Test', 'Eager Test', 'Lazy Test',
        'Duplicate Assert', 'Unknown Test', 'IgnoredTest', 'Resource Optimism',
        'Magic Number Test', 'Dependent Test'
    ]

    test_smell_means = {}
    for column in test_smell_columns:
        values = df_type[column].astype(str).tolist()
        sum_values = 0
        item_count = 0
        for value in values:
            try:
                sum_values += float(value)
                item_count += 1
            except ValueError:
                continue
        if item_count == 0:
            test_smell_means[column] = None
        else:
            test_smell_means[column] = round(sum_values / item_count, 2)

    return test_smell_means

def generate_output_agone_projects(output_agone_classes_df):
    """
    This function generates the 'output_agone_projects.csv' file.
    This file contains data for each project, including mean code coverage, mean strong mutation coverage, total lines of code of the focal classes, mean cyclomatic complexity of the focal classes, and compilation rate for each test type.
    Parameters:
                output_agone_classes_df (Dataframe): dataframe containing data for each test class and each test type, including code coverage, mutation coverage, lines of code of the corresponding focal class, cyclomatic complextity of the corresponding focal class, and compilation rate.
    Returns:
                (bool): True if the generation has been executed successfully, False if an error occurred.
    """
    output_agone_projects_path = 'output/output_agone_projects.csv'
    if output_agone_classes_df is None or output_agone_classes_df.empty:
        empty_df = pd.DataFrame()
        empty_df.to_csv(output_agone_projects_path, index=False, na_rep="-")  
        return True
    id_focal_classes = output_agone_classes_df['ID_Focal_Class'].unique()
    # Convert the ndarray to a list and convert integers to strings
    id_focal_classes = [str(project) for project in  id_focal_classes.tolist()]
    projects = []
    for id_focal_class in id_focal_classes:
        projects.append(id_focal_class.split('_')[0])
    projects = list(set(projects))
   
    output_agone_projects_df = pd.DataFrame(columns=['Project', 'Cyclomatic_Complexity', 'Lines_Of_Code', 'Generator(LLM/EVOSUITE)', 'Prompt_Technique', 'Compilation%', 'Branch_Coverage%', 'Line_Coverage%', 'Method_Coverage%', 'Mutation_Coverage%',
        'NumberOfMethods', 'Assertion Roulette', 'Conditional Test Logic',
        'Constructor Initialization', 'Default Test', 'EmptyTest',
        'Exception Catching Throwing', 'General Fixture', 'Mystery Guest',
        'Print Statement', 'Redundant Assertion', 'Sensitive Equality',
        'Verbose Test', 'Sleepy Test', 'Eager Test', 'Lazy Test',
        'Duplicate Assert', 'Unknown Test', 'IgnoredTest', 'Resource Optimism',
        'Magic Number Test', 'Dependent Test'])
    for project in projects:
        classes_rows_project = output_agone_classes_df[output_agone_classes_df['ID_Focal_Class'].str.contains(project)]
        test_types = classes_rows_project['Generator(LLM/EVOSUITE)'].unique()

        classes_human_rows_project = classes_rows_project[classes_rows_project['Generator(LLM/EVOSUITE)'] == 'human'].copy()
        classes_human_rows_project['Cyclomatic_Complexity_Focal_Class'] = classes_human_rows_project['Cyclomatic_Complexity_Focal_Class'].replace({'-': np.nan, '-0': np.nan}, regex=True)
        classes_human_rows_project['Cyclomatic_Complexity_Focal_Class'] = pd.to_numeric(classes_human_rows_project['Cyclomatic_Complexity_Focal_Class'], errors='coerce')

        classes_human_rows_project['Lines_Of_Code_Focal_Class'] = classes_human_rows_project['Lines_Of_Code_Focal_Class'].replace({'-': np.nan, '-0': np.nan}, regex=True)
        classes_human_rows_project['Lines_Of_Code_Focal_Class'] = pd.to_numeric(classes_human_rows_project['Lines_Of_Code_Focal_Class'], errors='coerce')
        if classes_human_rows_project['Lines_Of_Code_Focal_Class'].isna().all():
            total_lines_of_code = '-'
        else:
            total_lines_of_code = classes_human_rows_project['Lines_Of_Code_Focal_Class'].sum()
        
        cyclomatic_complexity_values = classes_human_rows_project['Cyclomatic_Complexity_Focal_Class'] 
        sum_cyclomatic_complexity = 0
        item_cyclomatic_complexity = 0
        for cyclomatic_complexity in  cyclomatic_complexity_values:
            if cyclomatic_complexity is not None and cyclomatic_complexity != '-' and cyclomatic_complexity != 'nan' and not np.isnan(cyclomatic_complexity):
                sum_cyclomatic_complexity = sum_cyclomatic_complexity + float(cyclomatic_complexity)
                item_cyclomatic_complexity = item_cyclomatic_complexity + 1
        if item_cyclomatic_complexity == 0:
            cyclomatic_complexity_mean = '-'
        else:
            cyclomatic_complexity_mean = round(sum_cyclomatic_complexity/ item_cyclomatic_complexity, 2)

        for test_type in test_types:
            if test_type == 'human' or test_type == 'evosuite':
                percentage_completition = calculate_compilation(test_type, None, classes_rows_project)
                percentage_branch_coverage = calculate_coverage_mean(test_type, None, 'Branch', classes_rows_project)
                percentage_line_coverage = calculate_coverage_mean(test_type, None, 'Line', classes_rows_project)
                percentage_method_coverage = calculate_coverage_mean(test_type, None, 'Method', classes_rows_project)
                percentage_mutation_coverage = calculate_coverage_mean(test_type, None, 'Mutation', classes_rows_project)
                test_smell_mean = calculate_test_smell_mean(test_type, None, classes_rows_project)
                if percentage_completition is None:
                    percentage_completition = '-'
                if percentage_branch_coverage is None:
                    percentage_branch_coverage = '-'
                if percentage_line_coverage is None:
                    percentage_line_coverage = '-'
                if percentage_method_coverage is None:
                    percentage_method_coverage = '-'
                if test_smell_mean is None:
                    test_smell_mean = '-'
                # transform test_smell_mean into a list
                test_smell_mean = list(test_smell_mean.values())
                output_agone_project_data = [project, cyclomatic_complexity_mean, total_lines_of_code, test_type, '-',  percentage_completition, percentage_branch_coverage, percentage_line_coverage, percentage_method_coverage, percentage_mutation_coverage]
                output_agone_project_data.extend(test_smell_mean)
                output_agone_projects_df.loc[len(output_agone_projects_df)] = output_agone_project_data

            else: # in other words, the test type is an AI test type
                classes_test_type_rows_project = classes_rows_project[classes_rows_project['Generator(LLM/EVOSUITE)'] == test_type]
                techniques = classes_test_type_rows_project['Prompt_Technique'].unique()
                for technique in techniques:
                    percentage_completition = calculate_compilation(test_type, technique, classes_rows_project)
                    percentage_branch_coverage = calculate_coverage_mean(test_type, technique, 'Branch', classes_rows_project)
                    percentage_line_coverage = calculate_coverage_mean(test_type, technique, 'Line', classes_rows_project)
                    percentage_method_coverage = calculate_coverage_mean(test_type, technique, 'Method', classes_rows_project)
                    percentage_mutation_coverage = calculate_coverage_mean(test_type, technique, 'Mutation', classes_rows_project)
                    test_smell_mean = calculate_test_smell_mean(test_type, technique, classes_rows_project)
                    if percentage_completition is None:
                        percentage_completition = '-'
                    if percentage_branch_coverage is None:
                        percentage_branch_coverage = '-'
                    if percentage_line_coverage is None:
                        percentage_line_coverage = '-'
                    if percentage_method_coverage is None:
                        percentage_method_coverage = '-'
                    if test_smell_mean is None:
                        test_smell_mean = '-'
                    test_smell_mean = list(test_smell_mean.values())
                    output_agone_project_data = [project, cyclomatic_complexity_mean, total_lines_of_code, test_type, technique, percentage_completition, percentage_branch_coverage, percentage_line_coverage, percentage_method_coverage, percentage_mutation_coverage]
                    output_agone_project_data.extend(test_smell_mean)
                    output_agone_projects_df.loc[len(output_agone_projects_df)] = output_agone_project_data
    try:
        output_agone_projects_df.to_csv(output_agone_projects_path, index=False, na_rep="-")  # Set index=False to exclude row indices in the CSV file
        return True
    except Exception as e:
        return False

def generate_output_agone_mean(test_types, techniques, output_agone_classes_df):
    """
    This function generates the 'output_agone_mean.csv' file. 
    It contains information about all the given test types and techniques for all the projects in the dataframe.
    The information refers to the mean values of code coverage, strong mutation coverage and the number of test smells.
    Parameters:
                test_types (List): the list of test types to process.
                techniques (List): the list of prompt techniques (for the AI test types) to process. 
                output_agone_classes_df (Dataframe): the dataframe containing information about processed classes.
    Returns:
                (bool): True if the generation has been executed successfully, False if an error occurred.

    """
    output_agone_mean_path = 'output/output_agone_mean.csv'

    if output_agone_classes_df is None or output_agone_classes_df.empty:
        empty_df = pd.DataFrame()
        empty_df.to_csv(output_agone_mean_path, index=False, na_rep="-")  
        return True
    
    df_output = pd.DataFrame(columns=['Test_type', 'Prompt_Technique', 'Compilation%', 'Branch_Coverage%', 'Line_Coverage%', 'Method_Coverage%', 'Mutation_Coverage%',
        'NumberOfMethods', 'Assertion Roulette', 'Conditional Test Logic',
        'Constructor Initialization', 'Default Test', 'EmptyTest',
        'Exception Catching Throwing', 'General Fixture', 'Mystery Guest',
        'Print Statement', 'Redundant Assertion', 'Sensitive Equality',
        'Verbose Test', 'Sleepy Test', 'Eager Test', 'Lazy Test',
        'Duplicate Assert', 'Unknown Test', 'IgnoredTest', 'Resource Optimism',
        'Magic Number Test', 'Dependent Test'])
    for test_type in test_types:
        if test_type == 'human' or test_type == 'evosuite':
            percentage_completition = calculate_compilation(test_type, None, output_agone_classes_df)
            percentage_branch_coverage = calculate_coverage_mean(test_type, None, 'Branch', output_agone_classes_df)
            percentage_line_coverage = calculate_coverage_mean(test_type, None, 'Line', output_agone_classes_df)
            percentage_method_coverage = calculate_coverage_mean(test_type, None, 'Method', output_agone_classes_df)
            percentage_mutation_coverage = calculate_coverage_mean(test_type, None, 'Mutation', output_agone_classes_df)
            test_smell_mean = calculate_test_smell_mean(test_type, None, output_agone_classes_df)

            if percentage_completition is None:
                percentage_completition = '-'
            if percentage_branch_coverage is None:
                percentage_branch_coverage = '-'
            if percentage_line_coverage is None:
                percentage_line_coverage = '-'
            if percentage_method_coverage is None:
                percentage_method_coverage = '-'
            if percentage_mutation_coverage is None:
                percentage_mutation_coverage = '-'
            if test_smell_mean is None:
                test_smell_mean = '-'
            test_smell_mean = list(test_smell_mean.values())
            data = [test_type, '-', percentage_completition, percentage_branch_coverage, percentage_line_coverage, percentage_method_coverage, percentage_mutation_coverage]
            data.extend(test_smell_mean)
            df_output.loc[len(df_output)] = data

        else: # if the test type is an AI test type
            for technique in techniques:
                    percentage_completition = calculate_compilation(test_type, technique, output_agone_classes_df)
                    percentage_branch_coverage = calculate_coverage_mean(test_type, technique, 'Branch', output_agone_classes_df)
                    percentage_line_coverage = calculate_coverage_mean(test_type, technique, 'Line', output_agone_classes_df)
                    percentage_method_coverage = calculate_coverage_mean(test_type, technique, 'Method', output_agone_classes_df)
                    percentage_mutation_coverage = calculate_coverage_mean(test_type, technique, 'Mutation', output_agone_classes_df)
                    test_smell_mean = calculate_test_smell_mean(test_type, technique, output_agone_classes_df)
                    
                    if percentage_completition is None:
                        percentage_completition = '-'
                    if percentage_branch_coverage is None:
                        percentage_branch_coverage = '-'
                    if percentage_line_coverage is None:
                        percentage_line_coverage = '-'
                    if percentage_method_coverage is None:
                        percentage_method_coverage = '-'
                    if percentage_mutation_coverage is None:
                        percentage_mutation_coverage = '-'
                    if test_smell_mean is None:
                        test_smell_mean = '-'
                    test_smell_mean = list(test_smell_mean.values())
                    data = [test_type, technique, percentage_completition, percentage_branch_coverage, percentage_line_coverage, percentage_method_coverage, percentage_mutation_coverage]
                    data.extend(test_smell_mean)
                    df_output.loc[len(df_output)] = data    
    try:
        df_output.to_csv(output_agone_mean_path, index=False, na_rep="-")  # Set index=False to exclude row indices in the CSV file
        return True
    except Exception as e:
        return False

def ask_user_project_to_execute():
    """
    Asks the user if they want to execute all projects or a specific project.
    Returns:
            project_input_user: the ID of the project selected by the user (if the user wants to execute only one specific project), 'None' if the user wants to execute all projects
    """
    repeat_error = True
    while (repeat_error == True):
        print("1. A specific project")
        print("2. All projects")
        choice = input("What do you want to do? ")
        #choice = '2'
        if choice == '1':
            project_input_user = input("Insert the project id: ")
            repeat_error = False
        elif choice == '2':
            project_input_user = None
            repeat_error = False
        else: 
            print("You entered an invalid value")
    return project_input_user

def process_module(module, project, project_path, java_version, junit_version, testng_version, compiler_version, type_project, test_types, techniques, project_structure, project_dependencies):
    """
    Process a single module of a project.
    Parameters:
                module: the name of the module
                project: the ID of the project 
                project_path: the path of the project
                java_version: the version of Java detected in the project
                junit_version: the version of JUnit detected in the project
                testng_version: the version of testNG detected in the project
                compiler_version: the version of Maven/Gradle detected in the project
                type_project: if the project is Maven project or a Gradle project
                test_types: all the test types
                techniques: all the prompt techniques associated with the AI test types
    Returns:
                output_classes_dataframe (Dataframe): the dataframe that includes all the measures about all the test types applied in the module (code coverage, mutation coverage and number of test smells)
                :None if an error occured
                    
    """
    print('\n----')
    java_directory = os.getenv("JAVA_DIRECTORY")
    print(f"Processing project: {project}, module: {module}")
    path = os.path.join(project_path, module)
    has_mockito = utils.verify_mockito(type_project, path)
    utils.set_java_home(java_directory, java_version, system)
    # Read the classes.csv file into a DataFrame
    df = pd.read_csv('./output/classes.csv')
    project_df = df[df['Project'].isin([int(project)])] # I get only the rows of the current project
    module_df = project_df[project_df['Module'].isin([module])] # I get only the rows of the current module
    module_df = utils.remove_missing_files_from_dataframe(module_df)
    if type_project == 'Maven':
        print(f"\n{project}_{module} is a Maven project")
        if mavenLib.process_maven_module(project, module, test_types, techniques, path, project_path, module_df, compiler_version, java_version, junit_version, testng_version, has_mockito, system, project_structure, project_dependencies) == 0:
            return None          
    elif type_project == 'Gradle':
        print(f"\n{project}_{module} is a Gradle project")
        if gradleLib.process_gradle_module(project, module, test_types, techniques, path, module_df, compiler_version, java_version, junit_version, testng_version, has_mockito, system, project_structure, project_dependencies) == 0:
            return None
    result_generate_output_csv_project, output_csv_path = utils.generate_output_csv_project(project, module_df, test_types, techniques, module) 
    if os.path.exists(f'output/{project}/pathToInputFile.csv'):
        try:
            os.remove(f'output/{project}/pathToInputFile.csv')
        except Exception as e:
            print("An error occured while trying to delete pathToInputFile.csv") 
    if result_generate_output_csv_project  is not None:
        print(f'{output_csv_path} saved correctly')
        return result_generate_output_csv_project
    else:
        return None

def ask_user_execution_override():
    """
    Asks the user if they want to execute the projects that have already been executed as well.
    Returns:
                execution_ovveride (bool): True if the user want to execute the project that have already been executed as weel, False otherwise.
    """
    while(True):
        choice = input("Execution override function: Do you want to re-execute the projects (with the relative test types) that have already been processed? (Y/N)  ")
        #choice = 'N'
        if choice == 'Y':
            return True
        elif choice == 'N':
            return False
        else:
            print("You entered an invalid value")

def verify_if_project_test_type_has_already_been_executed(project, test_type, output_agone_projects_path, technique=None):
    """
    Verifies whether the given project has already been executed with the specified test type and technique.
    Parameters:
                project: the ID of the project.
                test type: the test type associated with the project.
                output_agone_projects_path: the path of the dataframe containing information about the projects processed.
                technique (optional): the technique associated with the given AI test type.
    Returns:
                execution (bool): True if the project has already been executed, False otherwise.
    """
    check_df = False
    # check if the project/test type has alrady been processed in output_agone_projects dataframe
    while(True):
        if os.path.exists(output_agone_projects_path):
            try:
                output_agone_projects_df = pd.read_csv(output_agone_projects_path)
                if output_agone_projects_df.empty:
                    check_df = False
                    break
                project = int(project)

                if technique is None: # if the test type is not AI-related
                    exists = ((output_agone_projects_df['Project'] == project) & (output_agone_projects_df['Generator(LLM/EVOSUITE)'] == test_type)).any()
                    if exists == True:
                        check_df = True
                    else:
                        check_df = False
                    break
                      
                else: # if the test type is AI-related
                    exists = ((output_agone_projects_df['Project'] == project ) & (output_agone_projects_df['Generator(LLM/EVOSUITE)'] == test_type) & (output_agone_projects_df['Prompt_Technique'] == technique)).any()
                if exists == True:
                    check_df = True
                else:
                    check_df = False
                break
                      
            except Exception as e:
                print(e)
                check_df = False
                break
    return check_df

def ask_user_clean_all():
    """
    Asks the user if they want to clean up all previous executions. 
    If they confirm, it deletes all the output/project CSV files and resets the `output_agone_classes`, `output_agone_projects`, and `output_agone_mean` files to empty DataFrames.
    Returns:
               clean_up (bool): True if the user want to clean up all previous executions, False otherwise.
    """
    while(True):
        choice = input("Reset function: Do you want to clean up all the previous executions? (Y/N)  ")
        #choice = 'N'
        if choice == 'Y':
            for project in os.listdir('./output'):
                project_path = os.path.join('output', project)
                if os.path.isfile(project_path):
                    continue
                print(f"Cleaning '{project}'")
                for filename in os.listdir(project_path):
                    if filename.endswith('.csv'):
                        os.remove(os.path.join(project_path, filename))
            empty_df = pd.DataFrame()
            output_agone_classes_path = 'output/output_agone_classes.csv'
            output_agone_projects_path = 'output/output_agone_projects.csv'
            output_agone_mean_path = 'output/output_agone_mean.csv'
            output_agone_mean_filtered_path = 'output/output_agone_mean_filtered.csv'
            output_agone_info_path = 'output/output_agone_info.txt'
            if os.path.exists(output_agone_classes_path):
                empty_df.to_csv(output_agone_classes_path)
            if os.path.exists(output_agone_projects_path):
                empty_df.to_csv(output_agone_projects_path)
            if os.path.exists(output_agone_mean_path):
                empty_df.to_csv(output_agone_mean_path)
            if os.path.exists(output_agone_mean_filtered_path):
                empty_df.to_csv(output_agone_mean_filtered_path)
            if os.path.exists(output_agone_info_path):
                with open(output_agone_info_path, 'w') as file:
                    file.write('')
            return True
        elif choice == 'N':
            return False
        else:
            print("You entered an invalid value")

def calculate_number_projects_evosuite_compatibility(projects_to_process, project_info_data):
    """
    It calculates and returns the number of projects that are compatible with EvoSuite.
    Parameters:
            projects_to_process (list): The list of projects to be analyzed.
            project_info_data (dict): The JSON-formatted data containing information about the projects.
    Returns:
            number_of_projects (int): The number of projects that are compatible with EvoSuite.
            compatible_projects (list): list of projects that are compatible with EvoSuite execution.

    """
    number_of_project = 0
    compatible_projetcs = set()
    for project in projects_to_process:
        java_version = project_info_data.get(project, {}).get('java_version')
        junit_version = project_info_data.get(project, {}).get('junit_version')
        if junit_version is not None and java_version is not None:
            if junit_version.startswith('4') and ((java_version == '5' or java_version == '1.5') or (java_version == '6' or java_version == '1.6') or (java_version == '7' or java_version == '1.7') or (java_version == '8' or java_version == '1.8')): 
                number_of_project = number_of_project +1
                compatible_projetcs.add(project)
    compatible_projetcs = list(compatible_projetcs)
    return compatible_projetcs, number_of_project

def clean_previous_execution_files_project(project):
    """
    Removes the previous execution files of the given project.
    Parameters:
            project: the ID of the project.
    """
    project_path = os.path.join('output', project)
    if os.path.isfile(project_path):
        for filename in os.listdir(project_path):
            if filename.endswith('.csv') and filename is not f"{project}_Output.csv":
                os.remove(os.path.join(project_path, filename))

def ask_to_correct():
    """
    Asks the user if they want to correct the class that not compile.
    Returns:
            True or False.
    """
    while (True):
        choice = input(
            "Do you want to correct the class that eventualy not compile? (Y/N)  ")
        if choice == 'Y':
            return True
        elif choice == 'N':
            return False
        else:
            print("You entered an invalid value")

# Get the system: Windows, Linux or Darwin
system=platform.system()

def main():
    print("WELCOME TO AGONE TEST!")
    test_types = ExecutionManager.get_agents_list()
    techniques = ExecutionManager.get_prompts_list()
    project_user = ask_user_project_to_execute()
    correct = ask_to_correct()
    if ask_user_clean_all():
        execution_override = True
    else:
        execution_override = ask_user_execution_override()
    generate_files(test_types, techniques, execution_override, correct, project_user)
    print("File processing completed!")

if __name__ == "__main__":
    if not utils.is_admin(system):
        print("This script is running without administrator privileges!")
        print("Please re-run the script with administrator privileges to avoid errors during execution!")
    main()