from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path
from typing import Any

import pandas as pd


ARTIFACT_NAMES = [
    "metrics_long.csv",
    "metrics_wide.csv",
    "summary.csv",
    "rq_decisions.csv",
    "statistical_test_inputs.csv",
    "rq4_pairwise_strict_mutation.csv",
    "generated_failures.csv",
    "failure_diagnostics.csv",
    "baseline_scope_build.csv",
    "baseline_sandbox_readiness.csv",
    "baseline_classes.csv",
    "preflight_classes.csv",
    "preflight_report.json",
    "generation_classes.csv",
    "generated_tests_manifest.csv",
    "generated_tests.zip",
    "error_summary.csv",
    "skipped_classes.csv",
    "phase_log.csv",
    "api_log.csv",
    "api_prompts.jsonl",
    "runtime_errors.csv",
    "environment_checks.csv",
    "manifest.json",
    "experiment_report.xlsx",
    "stdout.log",
    "stderr.log",
]


def read_csv_records(path: Path, limit: int | None = None) -> list[dict[str, Any]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    try:
        df = pd.read_csv(path)
    except Exception:
        return []
    if limit is not None:
        df = df.tail(limit)
    return df.fillna("").to_dict(orient="records")


def write_excel_report(run_dir: Path) -> Path:
    xlsx_path = run_dir / "experiment_report.xlsx"
    sheets = {
        "Summary": run_dir / "summary.csv",
        "Metrics": run_dir / "metrics_long.csv",
        "Metrics Wide": run_dir / "metrics_wide.csv",
        "RQ Decisions": run_dir / "rq_decisions.csv",
        "Stats Inputs": run_dir / "statistical_test_inputs.csv",
        "RQ4 Pairwise": run_dir / "rq4_pairwise_strict_mutation.csv",
        "Failures": run_dir / "generated_failures.csv",
        "Failure Diagnostics": run_dir / "failure_diagnostics.csv",
        "Baseline Scopes": run_dir / "baseline_scope_build.csv",
        "Sandbox Readiness": run_dir / "baseline_sandbox_readiness.csv",
        "Baseline Classes": run_dir / "baseline_classes.csv",
        "Preflight Classes": run_dir / "preflight_classes.csv",
        "Generation Classes": run_dir / "generation_classes.csv",
        "Generated Tests": run_dir / "generated_tests_manifest.csv",
        "Error Summary": run_dir / "error_summary.csv",
        "Skipped": run_dir / "skipped_classes.csv",
        "Phase Log": run_dir / "phase_log.csv",
        "API Log": run_dir / "api_log.csv",
        "Runtime Errors": run_dir / "runtime_errors.csv",
        "Environment": run_dir / "environment_checks.csv",
    }
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        wrote_sheet = False
        for sheet_name, csv_path in sheets.items():
            if csv_path.exists() and csv_path.stat().st_size > 0:
                try:
                    df = pd.read_csv(csv_path)
                except Exception as exc:
                    df = pd.DataFrame([{"error": f"{type(exc).__name__}: {exc}"}])
            else:
                df = pd.DataFrame()
            df.to_excel(writer, sheet_name=sheet_name[:31], index=False)
            wrote_sheet = True

        manifest_path = run_dir / "manifest.json"
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest_df = pd.DataFrame(
                    [{"key": key, "value": json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value}
                     for key, value in manifest.items()]
                )
            except Exception as exc:
                manifest_df = pd.DataFrame([{"key": "error", "value": f"{type(exc).__name__}: {exc}"}])
            manifest_df.to_excel(writer, sheet_name="Manifest", index=False)
            wrote_sheet = True

        if not wrote_sheet:
            pd.DataFrame([{"message": "No report data available"}]).to_excel(writer, sheet_name="Report", index=False)
    return xlsx_path


def classify_issue(phase: str, status: str, detail: str, error_type: str = "") -> tuple[str, str, str, str]:
    text = f"{phase}\n{status}\n{detail}\n{error_type}".lower()
    if phase.lower() in {"baseline_build", "baseline_scope_build"} and status.upper() in {"FAIL", "ERROR"}:
        return (
            "repo_baseline_build_failed",
            "error",
            "Repo/module không build sạch trước khi sinh test, nên class này phải được loại khỏi bước GPT/EvoSuite và không được tính là lỗi generated test.",
            "Sửa dependency/build tool/module metadata hoặc loại instance khỏi sample; sau đó chạy lại để chỉ sinh test trên repo baseline-pass.",
        )
    if status.upper() == "CANCELLED":
        return (
            "run_cancelled",
            "warning",
            "Run đã bị dừng trước khi pipeline hoàn tất, nên một số report/metric có thể chỉ là dữ liệu tạm.",
            "Chạy lại full-run tới khi completed nếu cần metrics JaCoCo/PIT đầy đủ; partial artifacts chỉ dùng để debug.",
        )
    if (
        "evosuite-maven-plugin" in text
        and "1.2.0" in text
        and (
            "could not be resolved" in text
            or "was not found" in text
            or "failed to transfer" in text
            or "blocked mirror" in text
        )
    ):
        return (
            "evosuite_maven_plugin_unresolved",
            "error",
            "Maven không resolve được org.evosuite.plugins:evosuite-maven-plugin:1.2.0; Maven arm đang gọi plugin remote trong khi artifact này không tải được từ repository hiện tại hoặc đã bị cache fail trong ~/.m2.",
            "Ưu tiên chuyển Maven EvoSuite sang CLI jar local evosuite-1.2.0.jar hoặc cấu hình đúng repository/plugin rồi force update bằng -U và xóa cache fail trong ~/.m2.",
        )
    if "branchcoveragetestfitness" in text and "criterion is not enabled" in text:
        return (
            "evosuite_archive_criterion_mismatch",
            "error",
            "EvoSuite 1.2.0 bị lỗi nội bộ khi archive/criterion không khớp, khiến generate kết thúc mà không ghi test class.",
            "Runner đã cấu hình EvoSuite CLI với -Dtest_archive=false và -Dcriterion=BRANCH; chạy lại bằng phiên bản tool mới để tránh lỗi này.",
        )
    if (
        phase.lower() == "evosuite_generate"
        and (
            "displaynamegenerator" in text
            or "innerclasses attribute" in text
            or "mockmethodadvice" in text
            or "mockmethoddispatcher" in text
            or "should be in target project, but could not be found" in text
        )
    ):
        return (
            "evosuite_test_framework_classpath_crash",
            "error",
            "EvoSuite 1.2.0 bị crash khi phân tích các dependency test-framework như JUnit Jupiter/Mockito/ByteBuddy nằm trong projectCP, trước khi sinh được test.",
            "Chạy lại bằng runner mới: Maven EvoSuite sẽ retry với classpath đã lọc test-framework jars khỏi bước generation, trong khi Maven verify vẫn giữ dependency của project.",
        )
    if "attachnotsupportedexception" in text or "no providers installed" in text or "error during attachment" in text:
        return (
            "evosuite_runtime_agent_attach_failure",
            "error",
            "Generated EvoSuite test đang kích hoạt runtime agent/InitializingListener nhưng JVM test fork không attach được agent.",
            "Runner đã sinh EvoSuite test không scaffolding/EvoRunner và bỏ InitializingListener; chạy lại để tránh self-attach khi đo JaCoCo/PIT.",
        )
    if (
        ("failed to transfer metadata" in text or "failed to read artifact descriptor" in text or "could not collect dependencies" in text)
        and "snapshot" in text
        and ("-am" in text or "public-snapshots" in text or "sonatype" in text or "cached in the local repository" in text)
    ):
        return (
            "maven_reactor_scope_dependency_error",
            "error",
            "Baseline build đã pass theo reactor/module scope nhưng bước sinh hoặc đo test đang chạy Maven trong module rời, làm Maven cố tải dependency SNAPSHOT/sibling module từ remote thay vì dùng reactor local.",
            "Chạy bằng phiên bản runner có maven_reactor_prewarm hoặc giữ nguyên Maven reactor context (-f root pom -pl module -am) cho cả EvoSuite và GPT; không tính lỗi này là lỗi năng lực sinh test.",
        )
    if phase.lower() == "maven_reactor_prewarm" and status.upper() in {"FAIL", "ERROR"}:
        if "jar:tests" in text and "was not found" in text:
            return (
                "maven_prewarm_testjar_classifier_missing",
                "error",
                "Prewarm Maven dùng install nhưng đã skip phần test quá mạnh, làm module phụ không tạo tests-classifier jar cần cho module kế tiếp trong reactor.",
                "Chạy lại bằng runner mới: maven_reactor_prewarm không dùng -Dmaven.test.skip=true để giữ hành vi test-compile tương đương baseline.",
            )
        if "rbl4test" in text and ("no header" in text or "check-file-header" in text):
            return (
                "maven_prewarm_placeholder_license_header",
                "error",
                "Prewarm Maven bị nhiễu bởi placeholder test tạm của tool; license plugin kiểm tra file test rỗng trước khi GPT/EvoSuite thật sự sinh test.",
                "Chạy lại bằng runner mới: placeholder test được ẩn trong lúc prewarm để baseline/prewarm chỉ phản ánh source gốc.",
            )
        return (
            "maven_reactor_prewarm_failed",
            "error",
            "Bước chuẩn bị dependency reactor trong sandbox thất bại, nên tool chưa tạo được điều kiện build tương đương baseline cho focal class.",
            "Mở phase_log.csv ở dòng maven_reactor_prewarm để sửa recipe/module selector/JDK/dependency trước khi chạy GPT/EvoSuite.",
        )
    if phase.lower() == "baseline_sandbox_readiness" and status.upper() in {"FAIL", "ERROR"}:
        return (
            "baseline_sandbox_readiness_failed",
            "error",
            "Class đã qua baseline scope build nhưng chưa qua điều kiện sandbox/prewarm giống chạy thật, nên generation phải bị chặn trước khi gọi GPT/EvoSuite.",
            "Mở baseline_sandbox_readiness.csv và các phase prewarm liên quan để sửa recipe/tool; không tính lỗi này là lỗi năng lực sinh test.",
        )
    if phase.lower() == "runner" and "baseline/sandbox readiness gate failed" in text:
        return (
            "baseline_sandbox_readiness_gate_failed",
            "error",
            "Runner dừng đúng chính sách vì còn class chưa qua sandbox readiness, nên chưa gọi GPT/EvoSuite.",
            "Sửa các dòng baseline_sandbox_readiness/maven_reactor_prewarm fail trước đó rồi chạy lại; lỗi này là hệ quả của readiness gate, không phải lỗi năng lực sinh test.",
        )
    if phase.lower() == "gradle_sandbox_prewarm" and status.upper() in {"FAIL", "ERROR"}:
        return (
            "gradle_sandbox_prewarm_failed",
            "error",
            "Sandbox Gradle chưa compile được module/focal class trước khi gọi AgoneTest, nên tool chưa tạo được build/classes/java/main tương đương baseline.",
            "Mở phase_log.csv ở dòng gradle_sandbox_prewarm để sửa recipe Gradle/module wrapper/JDK; GPT/EvoSuite chưa được gọi cho class này.",
        )
    if "missing build/classes/java/main" in text or "missing gradle main classes directory" in text:
        return (
            "gradle_evosuite_missing_compiled_classes",
            "error",
            "EvoSuite Gradle cần thư mục compiled main classes nhưng sandbox đã bỏ qua thư mục build và chưa compile lại hoặc chưa nhận diện đúng layout Gradle.",
            "Chạy lại bằng runner có gradle_sandbox_prewarm để mỗi sandbox tự chạy Gradle testClasses trước khi gọi EvoSuite/GPT.",
        )
    if "unsupportedclassversionerror" in text or "unsupported major.minor version" in text:
        return (
            "java_runtime_too_old_for_maven",
            "error",
            "Một Java runtime quá cũ đang chạy Maven/plugin nên không load được class file mới hơn, ví dụ class version 52.0 tương ứng Java 8.",
            "Kiểm tra JAVA_HOME/PATH trong subprocess theo từng repo; dùng JDK đủ mới cho Maven launcher, và chỉ hạ source/target ở compiler config nếu project yêu cầu.",
        )
    if ("file not found" in text or "filenotfounderror" in text) and "testsmelldetection_" in text:
        return (
            "test_smell_output_path_invalid",
            "error",
            "TestSmellDetector tạo file output nhưng bước rename dùng tên module chứa dấu / nên Windows hiểu thành thư mục con và báo không tìm thấy đường dẫn.",
            "Đã vá tool để sanitize module/test_type/prompt trước khi đặt tên file TestSmellDetection.",
        )
    if (
        "could not resolve dependencies" in text
        or "could not find artifact" in text
        or "dependencyresolutionexception" in text
    ):
        return (
            "project_dependency_resolution_error",
            "error",
            "Maven/Gradle không resolve được dependency của project, thường gặp ở multi-module SNAPSHOT khi module phụ chưa được install hoặc thiếu repository nội bộ.",
            "Build/install project từ root trước khi đo, ví dụ mvn install -DskipTests ở root, hoặc loại instance này khỏi sample nếu dependency không thể khôi phục.",
        )
    if "build.gradle.kts" in text and ("no such file or directory" in text or "filenotfounderror" in text):
        return (
            "gradle_build_file_path_resolution_bug",
            "error",
            "Tool Gradle mở nhầm build.gradle/build.gradle.kts hoặc ghép sai path module trên Windows, nên chưa tới bước sinh/đo test thật.",
            "Chạy lại bằng bản đã sửa gradleLib.edit_build_gradle_file; không tính lỗi này là lỗi năng lực EvoSuite/GPT.",
        )
    if "exec-maven-plugin" in text and ("python-test" in text or "command execution failed" in text):
        return (
            "maven_external_exec_goal_interference",
            "error",
            "Maven verify kích hoạt goal phụ ngoài protocol RBL-4, ví dụ exec-maven-plugin chạy python-test, làm nhiễu phép đo focal generated test.",
            "Chạy lại bằng bản có -Dexec.skip=true trong Maven measurement; nếu repo vẫn bắt buộc goal ngoài Java thì ghi nhận là tool/protocol exclusion, không phải generated-test failure.",
        )
    if "non-parseable pom" in text or "expected root element 'project' but found 'ns0:project'" in text:
        return (
            "pom_rewrite_namespace_error",
            "error",
            "POM bị ghi lại với namespace/prefix không hợp lệ sau khi tool chèn plugin/dependency, khiến Maven không đọc được pom.xml.",
            "Khôi phục pom.xml từ backup/source trước khi chạy lại; cần sửa bước rewrite POM để giữ đúng Maven namespace mặc định.",
        )
    if "dependency management issues found" in text or "version mismatch for plugin" in text:
        return (
            "maven_plugin_management_policy_failure",
            "error",
            "Build fail vì project có rule kiểm tra dependency/plugin management và phát hiện version plugin bị thay đổi hoặc không khớp policy.",
            "Với project có enforcer/dependency-management check, cần đo bằng profile phù hợp hoặc loại khỏi sample nếu việc chèn JaCoCo/PIT/Surefire làm phá policy.",
        )
    if "source 1.6" in text or "source 1.5" in text or "diamond operator is not supported" in text:
        return (
            "java_source_level_incompatible",
            "error",
            "Test/source đang dùng cú pháp Java mới hơn mức compiler của project, ví dụ diamond operator nhưng Maven compile với -source 1.6.",
            "Dùng đúng JDK/source level theo project hoặc sửa/loại test sinh ra dùng cú pháp không tương thích; với thực nghiệm fairness thì nên ghi nhận fail_stage thay vì sửa test.",
        )
    if (
        "compilation errors were encountered" in text
        and ("src/test/java" in text or "src\\test\\java" in text)
        and ("rbl4" in text or "evosuite" in text)
    ):
        return (
            "generated_test_compile_failed",
            "error",
            "Generated test đã được sinh ra nhưng không compile được trong module đo; đây là lỗi output test/harness đo, không phải bằng chứng repo gốc không build.",
            "Giữ compilation=0 và strict metrics=0 cho arm tương ứng. Nếu lỗi do thiếu dependency harness như JUnit runtime thì sửa tool; nếu lỗi do symbol/API sai trong test thì ghi nhận là lỗi generator.",
        )
    if "build failed" in text and "gradle" in text:
        return (
            "gradle_build_failed",
            "error",
            "Gradle build fail khi chạy test/JaCoCo/PIT; log hiện tại chỉ có stderr rút gọn nên chưa đủ nguyên nhân sâu.",
            "Chạy lại Gradle với --stacktrace/--info hoặc mở log thô của module để biết lỗi dependency, compile, plugin hay test runtime.",
        )
    if "package org.junit.jupiter.api does not exist" in text or "cannot find symbol" in text and "junit" in text:
        return (
            "test_framework_dependency_missing",
            "error",
            "Generated test dùng framework/import không có trong dependency test của module, ví dụ JUnit Jupiter nhưng project chưa có junit-jupiter-api.",
            "Không sửa test sau sinh trong protocol fairness; ghi nhận fail. Nếu chạy pilot debug, cần chọn đúng JUnit version theo project hoặc bổ sung dependency test.",
        )
    if "tests run:" in text and ("<<< failure" in text or "failures:" in text):
        return (
            "generated_test_assertion_failure",
            "error",
            "Test compile và chạy được nhưng assertion fail, nên JaCoCo/PIT không được tính là pass đầy đủ.",
            "Ghi nhận fail_stage; không sửa assertion nếu đang chạy protocol no-repair.",
        )
    if "cannot find symbol" in text or "compilation errors were encountered" in text:
        return (
            "project_compilation_error",
            "error",
            "Project hoặc module Java không compile được khi đo JaCoCo/PIT; đây là lỗi source/dependency/build của repo, không nhất thiết là lỗi GPT.",
            "Xem phase_log.csv để biết file Java và symbol lỗi; cần sửa dependency/source hoặc loại instance khỏi sample nếu precheck không tái lập buildability.",
        )
    if "no compilation errors or general issues found" in text and status.upper() == "FAIL":
        return (
            "metric_failure_without_parser_detail",
            "warning",
            "Maven/Gradle command fail nhưng parser không tìm thấy lỗi compile cụ thể; thường là lỗi plugin, test runtime, PIT/JaCoCo output thiếu, hoặc process return code khác 0.",
            "Mở stdout/stderr, phase_log.csv và output/<project>/*.failed để xem log thô.",
        )
    if ("openai" in text or "api" in text) and status.upper() in {"FAIL", "ERROR"}:
        return (
            "llm_api_error",
            "error",
            "Có lỗi khi gọi model/API hoặc ghi nhận response.",
            "Kiểm tra OPENAI_API_KEY, quota, mạng và api_log.csv.",
        )
    return (
        "unclassified_runtime_issue",
        "warning" if status.upper() == "FAIL" else "error",
        "Tool ghi nhận lỗi nhưng chưa phân loại được tự động.",
        "Xem detail trong phase_log.csv/runtime_errors.csv để phân tích thủ công.",
    )


def failure_owner_for_issue(category: str, phase: str, detail: str, arm: str = "") -> tuple[str, str]:
    text = f"{category}\n{phase}\n{detail}\n{arm}".lower()
    owner_map = {
        "repo_baseline_build_failed": "repository_or_environment",
        "project_dependency_resolution_error": "repository_or_environment",
        "java_runtime_too_old_for_maven": "repository_or_environment",
        "maven_plugin_management_policy_failure": "repository_or_environment",
        "generated_test_compile_failed": "generator_output",
        "generated_test_assertion_failure": "generator_output",
        "java_source_level_incompatible": "generator_output",
        "gpt_generation_failed": "generator_output",
        "llm_api_error": "llm_api_or_network",
        "evosuite_archive_criterion_mismatch": "evosuite_engine",
        "evosuite_test_framework_classpath_crash": "evosuite_engine",
        "evosuite_runtime_agent_attach_failure": "evosuite_engine",
        "maven_reactor_scope_dependency_error": "agonetest_harness",
        "maven_reactor_prewarm_failed": "agonetest_harness",
        "maven_prewarm_testjar_classifier_missing": "agonetest_harness",
        "maven_prewarm_placeholder_license_header": "agonetest_harness",
        "baseline_sandbox_readiness_failed": "agonetest_harness",
        "baseline_sandbox_readiness_gate_failed": "agonetest_harness",
        "gradle_sandbox_prewarm_failed": "agonetest_harness",
        "gradle_evosuite_missing_compiled_classes": "agonetest_harness",
        "gradle_build_file_path_resolution_bug": "agonetest_harness",
        "gradle_build_failed": "agonetest_harness",
        "gradle_testng_pitest_unsupported": "agonetest_harness",
        "agone_metric_extraction_failed": "agonetest_harness",
        "agone_result_csv_write_failed": "agonetest_harness",
        "pom_rewrite_namespace_error": "agonetest_harness",
        "test_smell_output_path_invalid": "agonetest_harness",
        "maven_external_exec_goal_interference": "agonetest_harness",
        "metric_failure_without_parser_detail": "agonetest_harness",
    }
    owner = owner_map.get(category, "")
    if not owner:
        if phase.lower().startswith("baseline"):
            owner = "repository_or_environment"
        elif "src/test/java" in text or "src\\test\\java" in text:
            owner = "generator_output"
        elif "gradle" in text or "agone" in text or "prewarm" in text or "jacoco" in text or "pit" in text:
            owner = "agonetest_harness"
        else:
            owner = "unknown_needs_manual_review"
    explanations = {
        "repository_or_environment": "Lỗi nằm ở repo/dependency/JDK/recipe build đầu vào hoặc môi trường, không phải do năng lực sinh test.",
        "agonetest_harness": "Lỗi nằm ở cách AgoneTest/RBL4 runner chuẩn bị sandbox, chỉnh POM/Gradle, chạy JaCoCo/PIT hoặc trích xuất metric.",
        "generator_output": "Test đã được sinh nhưng code test sai/không tương thích nên arm đó phải compilation=0 và strict metrics=0.",
        "evosuite_engine": "EvoSuite 1.2.0 crash hoặc không sinh được test trước bước đo; đây là giới hạn/lỗi engine EvoSuite.",
        "llm_api_or_network": "Lỗi ở API/model/network/quota, không phản ánh chất lượng test đã sinh.",
        "unknown_needs_manual_review": "Chưa đủ dấu hiệu tự động để quy trách nhiệm, cần đọc log thô.",
    }
    return owner, explanations.get(owner, "")


def build_error_summary(run_dir: Path) -> Path:
    rows: list[dict[str, Any]] = []
    baseline_final_pass_keys: set[tuple[str, str]] = set()

    baseline_path = run_dir / "baseline_scope_build.csv"
    if baseline_path.exists() and baseline_path.stat().st_size > 0:
        try:
            baseline_df = pd.read_csv(baseline_path, dtype=str).fillna("")
            if {"project", "module", "status"}.issubset(baseline_df.columns):
                passed = baseline_df[baseline_df["status"].astype(str).str.upper() == "PASS"]
                baseline_final_pass_keys = {
                    (str(row.get("project", "")), str(row.get("module", "")))
                    for _, row in passed.iterrows()
                }
        except Exception:
            baseline_final_pass_keys = set()

    phase_path = run_dir / "phase_log.csv"
    if phase_path.exists() and phase_path.stat().st_size > 0:
        try:
            phase_df = pd.read_csv(phase_path, dtype=str).fillna("")
            failed = phase_df[phase_df["status"].astype(str).str.upper().isin(["FAIL", "ERROR", "CANCELLED"])]
            for _, row in failed.iterrows():
                phase = str(row.get("phase", ""))
                status = str(row.get("status", ""))
                project = str(row.get("project", ""))
                module = str(row.get("module", ""))
                if (
                    phase.lower() in {"baseline_build", "baseline_scope_build"}
                    and status.upper() in {"FAIL", "ERROR"}
                    and (project, module) in baseline_final_pass_keys
                ):
                    continue
                category, severity, explanation, suggested_action = classify_issue(
                    phase,
                    status,
                    str(row.get("detail", "")),
                )
                failure_owner, owner_note = failure_owner_for_issue(
                    category,
                    phase,
                    str(row.get("detail", "")),
                    str(row.get("arm", "")),
                )
                rows.append(
                    {
                        "timestamp_utc": row.get("timestamp_utc", ""),
                        "source": "phase_log",
                        "project": project,
                        "module": module,
                        "arm": row.get("arm", ""),
                        "sample_index": row.get("sample_index", ""),
                        "class_key": row.get("class_key", ""),
                        "focal_class": row.get("focal_class", ""),
                        "test_class": row.get("test_class", ""),
                        "phase": phase,
                        "status": status,
                        "category": category,
                        "failure_owner": failure_owner,
                        "owner_note_vi": owner_note,
                        "severity": severity,
                        "explanation_vi": explanation,
                        "suggested_action_vi": suggested_action,
                        "detail": str(row.get("detail", ""))[:2000],
                    }
                )
        except Exception as exc:
            rows.append(
                {
                    "timestamp_utc": "",
                    "source": "phase_log",
                    "project": "",
                    "module": "",
                    "arm": "",
                    "sample_index": "",
                    "class_key": "",
                    "focal_class": "",
                    "test_class": "",
                    "phase": "error_summary",
                    "status": "ERROR",
                    "category": "error_summary_parse_failed",
                    "failure_owner": "agonetest_harness",
                    "owner_note_vi": "Không parse được log/report do tool hoặc artifact bị lỗi.",
                    "severity": "error",
                    "explanation_vi": f"Không đọc được phase_log.csv: {type(exc).__name__}: {exc}",
                    "suggested_action_vi": "Mở phase_log.csv thủ công để kiểm tra định dạng.",
                    "detail": "",
                }
            )

    runtime_path = run_dir / "runtime_errors.csv"
    if runtime_path.exists() and runtime_path.stat().st_size > 0:
        try:
            runtime_df = pd.read_csv(runtime_path).fillna("")
            failed_runtime = runtime_df[runtime_df["status"].astype(str).str.upper().isin(["ERROR", "FAIL"])]
            for _, row in failed_runtime.iterrows():
                detail = f"{row.get('error_type', '')}: {row.get('error_message', '')}\n{row.get('traceback', '')}"
                category, severity, explanation, suggested_action = classify_issue(
                    "runtime_error",
                    str(row.get("status", "")),
                    detail,
                    str(row.get("error_type", "")),
                )
                failure_owner, owner_note = failure_owner_for_issue(
                    category,
                    "runtime_error",
                    detail,
                    "",
                )
                rows.append(
                    {
                        "timestamp_utc": row.get("timestamp_utc", ""),
                        "source": "runtime_errors",
                        "project": row.get("project", ""),
                        "module": "",
                        "arm": "",
                        "sample_index": row.get("sample_index", ""),
                        "class_key": row.get("class_key", ""),
                        "focal_class": "",
                        "test_class": "",
                        "phase": "runtime_error",
                        "status": row.get("status", ""),
                        "category": category,
                        "failure_owner": failure_owner,
                        "owner_note_vi": owner_note,
                        "severity": severity,
                        "explanation_vi": explanation,
                        "suggested_action_vi": suggested_action,
                        "detail": detail[:2000],
                    }
                )
        except Exception:
            pass

    out_path = run_dir / "error_summary.csv"
    columns = [
        "timestamp_utc",
        "source",
        "project",
        "module",
        "arm",
        "sample_index",
        "class_key",
        "focal_class",
        "test_class",
        "phase",
        "status",
        "category",
        "failure_owner",
        "owner_note_vi",
        "severity",
        "explanation_vi",
        "suggested_action_vi",
        "detail",
    ]
    pd.DataFrame(rows, columns=columns).to_csv(out_path, index=False)
    return out_path


def collect_generated_tests(
    run_dir: Path,
    output_dir: Path,
    projects: list[str],
    modified_after_epoch: float | None = None,
) -> Path:
    generated_dir = run_dir / "generated_tests"
    if generated_dir.exists():
        shutil.rmtree(generated_dir)
    generated_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    for project in sorted(set(str(project) for project in projects)):
        project_output = output_dir / project
        if not project_output.exists():
            continue
        for source_path in sorted(project_output.glob("response_*.java")):
            if modified_after_epoch is not None and source_path.stat().st_mtime < modified_after_epoch:
                continue
            file_name = source_path.name
            arm = "evosuite" if file_name.startswith("response_evosuite") else "gpt" if "gpt" in file_name else "unknown"
            target_dir = generated_dir / project
            target_dir.mkdir(parents=True, exist_ok=True)
            target_path = target_dir / file_name
            shutil.copy2(source_path, target_path)
            rows.append(
                {
                    "project": project,
                    "arm": arm,
                    "file_name": file_name,
                    "source_path": str(source_path),
                    "stored_path": str(target_path),
                    "size_bytes": target_path.stat().st_size,
                    "modified_at": pd.Timestamp.fromtimestamp(target_path.stat().st_mtime).isoformat(),
                }
            )

    manifest_path = run_dir / "generated_tests_manifest.csv"
    pd.DataFrame(
        rows,
        columns=["project", "arm", "file_name", "source_path", "stored_path", "size_bytes", "modified_at"],
    ).to_csv(manifest_path, index=False)

    zip_path = run_dir / "generated_tests.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in generated_dir.rglob("*.java"):
            archive.write(file_path, file_path.relative_to(generated_dir))
    return zip_path


def artifact_infos(run_dir: Path) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    for name in ARTIFACT_NAMES:
        path = run_dir / name
        if not path.exists():
            continue
        stat = path.stat()
        artifacts.append(
            {
                "name": name,
                "path": str(path),
                "size_bytes": stat.st_size,
                "modified_at": pd.Timestamp.fromtimestamp(stat.st_mtime).isoformat(),
            }
        )
    return artifacts
