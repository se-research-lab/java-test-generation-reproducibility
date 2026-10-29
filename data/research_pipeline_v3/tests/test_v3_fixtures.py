import random
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from v3_core import (
    PipelineError,
    PromotionError,
    SELECTION_ALGORITHM,
    analyze_java_file,
    archive_step003_progress,
    assign_relative_complexity_halves,
    build_recipes,
    declared_java_allowed,
    detect_declared_java,
    find_build_scope,
    java_major,
    make_class_key,
    load_config,
    normalize_relative_path,
    pipeline_lock,
    promote_or_retain_qualified_repository,
    qualified_repository_storage_path,
    recover_windows_filesystem_rows,
    safe_remove_generated_tree,
    safe_promote_generated_tree,
    screen_and_build_repositories,
    select_repo_balanced_classes,
    validate_config,
)


def protocol_config():
    return {
        "protocol": {
            "seed": 42,
            "target_repositories": 30,
            "minimum_unique_classes_per_repo": 12,
            "main_classes_per_repo": 10,
            "backup_classes_per_repo": 2,
        },
        "eligibility": {"complexity_gate_enabled": False},
        "java": {
            "effective_runtime": 8,
            "maximum_declared_version": 8,
            "accepted_declared_versions": [5, 6, 7, 8],
            "try_unknown_version_on_jdk8": True,
            "run_all_accepted_versions_on_jdk8": True,
        },
        "build": {
            "allow_ai_recipe_suggestion": False,
            "allow_source_code_modification": False,
            "allow_dependency_modification": False,
        },
    }


def fake_frame():
    rows = []
    for repo_index in range(30):
        repo_id = str(1000 + repo_index)
        for class_index in range(12):
            rows.append({
                "repo_id": repo_id,
                "repo_url": f"https://example.invalid/{repo_id}",
                "commit_sha": "a" * 40,
                "class_key": f"{repo_id}:src/main/java/p/C{class_index}.java".casefold(),
                "focal_class": f"C{class_index}",
                "focal_path": f"src/main/java/p/C{class_index}.java",
                "mapping_count": "1",
                "nloc": str(10 + class_index),
                "token_count": "100",
                "method_count": "2",
                "public_method_count": "1",
                "max_method_cc": str((class_index % 7) + 1),
                "sum_method_cc": str((class_index % 7) + 2),
                "avg_method_cc": "1.5",
                "build_tool": "maven",
                "build_root": ".",
                "module_dir": ".",
                "module_selector": ".",
                "scope_key": "maven:.",
                "declared_java_version": "7",
                "effective_java_runtime": "8",
                "repository_storage_path": f"repos/successful/{repo_id}",
                "promotion_status": "promoted",
            })
    return rows


class IdentityFixtureTests(unittest.TestCase):
    def test_normalization_and_casefold_dedupe(self):
        self.assertEqual(normalize_relative_path(r"./src\main\java\P\A.java"), "src/main/java/P/A.java")
        first = make_class_key("42", r"./src\main\java\P\A.java")
        second = make_class_key("42", "src/main/java/p/a.java")
        self.assertEqual(first, second)

    def test_parent_traversal_is_rejected(self):
        self.assertEqual(normalize_relative_path("../outside.java"), "")
        with self.assertRaises(ValueError):
            make_class_key("42", "../outside.java")


class JavaPolicyFixtureTests(unittest.TestCase):
    def test_java_major_uses_mavens_label_not_mavens_own_version(self):
        output = (
            "Apache Maven 3.9.15 (revision)\n"
            "Maven home: C:\\Program Files\\apache-maven-3.9.15\n"
            "Java version: 1.8.0_172, vendor: Oracle Corporation"
        )
        self.assertEqual(java_major(output), 8)

    def test_java_major_supports_java_and_javac_outputs(self):
        self.assertEqual(java_major('java version "1.8.0_172"'), 8)
        self.assertEqual(java_major('openjdk version "17.0.12"'), 17)
        self.assertEqual(java_major("javac 1.8.0_172"), 8)
        self.assertIsNone(java_major("Apache Maven 3.9.15"))

    def test_java_5_to_8_and_unknown_are_candidates_for_jdk8(self):
        config = protocol_config()
        for declared in (5, 6, 7, 8, None):
            with self.subTest(declared=declared):
                self.assertTrue(declared_java_allowed(declared, config))
        for declared in (9, 11, 17, 21):
            with self.subTest(declared=declared):
                self.assertFalse(declared_java_allowed(declared, config))

    def test_maven_property_resolution_and_highest_version(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pom = root / "pom.xml"
            pom.write_text(
                "<project><properties><java.version>1.7</java.version>"
                "<maven.compiler.target>${java.version}</maven.compiler.target>"
                "</properties></project>", encoding="utf-8"
            )
            version, source, observed = detect_declared_java([pom])
            self.assertEqual(version, 7)
            self.assertIn(7, observed)
            self.assertIn("pom.xml", source)


class Step003RecoveryFixtureTests(unittest.TestCase):
    def test_qualified_storage_accepts_only_owned_repo_locations(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            successful = output / "repos" / "successful" / "42"
            working = output / "repos" / "working" / "42"
            successful.mkdir(parents=True)
            working.mkdir(parents=True)
            self.assertEqual(
                qualified_repository_storage_path(
                    output, {"repo_id": "42", "repository_storage_path": "repos/successful/42"}
                ),
                successful.resolve(),
            )
            self.assertEqual(
                qualified_repository_storage_path(
                    output, {"repo_id": "42", "repository_storage_path": "repos/working/42"}
                ),
                working.resolve(),
            )
            for invalid in ("../42", "repos/working/43", "repos/failed/42"):
                with self.subTest(invalid=invalid), self.assertRaises(PipelineError):
                    qualified_repository_storage_path(
                        output, {"repo_id": "42", "repository_storage_path": invalid}
                    )

    def test_generated_tree_cleanup_handles_readonly_git_pack(self):
        with tempfile.TemporaryDirectory() as temp:
            owned = Path(temp) / "working"
            pack = owned / "42" / ".git" / "objects" / "pack" / "pack-test.idx"
            pack.parent.mkdir(parents=True)
            pack.write_bytes(b"fixture")
            pack.chmod(stat.S_IREAD)
            safe_remove_generated_tree(owned / "42", owned)
            self.assertFalse((owned / "42").exists())

    def test_resume_requeues_only_known_readonly_cleanup_defect(self):
        affected = {
            "repo_id": "42", "status": "rejected", "failure_category": "pipeline_exception",
            "failure_detail": (
                "PermissionError: [WinError 5] Access is denied: "
                "'D:\\run\\data_v3\\repos\\working\\42\\.git\\objects\\pack\\pack-a.idx'"
            ),
        }
        qualified = {
            "repo_id": "43", "status": "qualified", "failure_category": "",
            "failure_detail": "", "unique_eligible_buildable_count": "20",
        }
        unrelated = {
            "repo_id": "44", "status": "rejected", "failure_category": "pipeline_exception",
            "failure_detail": "ValueError: unrelated defect",
        }
        promotion = {
            "repo_id": "45", "status": "rejected", "failure_category": "pipeline_exception",
            "failure_detail": (
                "PermissionError: [WinError 5] Access is denied: "
                "'D:\\run\\data_v3\\repos\\working\\45' -> "
                "'D:\\run\\data_v3\\repos\\successful\\45'"
            ),
        }
        queue = [affected, qualified, unrelated, promotion]
        self.assertEqual(recover_windows_filesystem_rows(queue), ["42", "45"])
        self.assertEqual(affected["status"], "pending")
        self.assertEqual(promotion["status"], "pending")
        self.assertEqual(qualified["status"], "qualified")
        self.assertEqual(qualified["unique_eligible_buildable_count"], "20")
        self.assertEqual(unrelated["status"], "rejected")

    def test_qualified_promotion_retries_transient_windows_access_denied(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            working_root = output / "working"
            successful_root = output / "successful"
            source = working_root / "42"
            destination = successful_root / "42"
            source.mkdir(parents=True)
            successful_root.mkdir(parents=True)
            (source / "result.txt").write_text("qualified", encoding="utf-8")
            real_replace = __import__("os").replace
            attempts = 0

            def flaky_replace(first, second):
                nonlocal attempts
                attempts += 1
                if attempts < 3:
                    raise PermissionError(5, "fixture access denied")
                return real_replace(first, second)

            with mock.patch("v3_core.os.replace", side_effect=flaky_replace), mock.patch("v3_core.time.sleep"):
                safe_promote_generated_tree(source, destination, working_root, successful_root)
            self.assertEqual(attempts, 3)
            self.assertEqual((destination / "result.txt").read_text(encoding="utf-8"), "qualified")

    def test_failed_storage_promotion_retains_qualified_working_repository(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            working_root = output / "working"
            successful_root = output / "successful"
            source = working_root / "42"
            destination = successful_root / "42"
            source.mkdir(parents=True)
            successful_root.mkdir(parents=True)
            with mock.patch(
                "v3_core.safe_promote_generated_tree",
                side_effect=PromotionError("fixture Windows lock"),
            ):
                storage, status, detail = promote_or_retain_qualified_repository(
                    source, destination, working_root, successful_root
                )
            self.assertEqual(storage, source)
            self.assertEqual(status, "retained_in_working")
            self.assertIn("fixture Windows lock", detail)
            self.assertTrue(source.is_dir())

    def test_restart_requires_explicit_confirmation_token(self):
        with self.assertRaises(PipelineError):
            screen_and_build_repositories(
                Path("does-not-matter.yaml"), mode="restart", restart_confirmation="wrong-token"
            )

    def test_restart_archives_progress_instead_of_deleting_it(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            queue = output / "repo_processing_order_seed42.csv"
            queue.write_text("status\nqualified\n", encoding="utf-8")
            successful = output / "repos" / "successful" / "42"
            successful.mkdir(parents=True)
            (successful / "result.txt").write_text("kept", encoding="utf-8")
            archive = archive_step003_progress(output, queue)
            self.assertFalse(queue.exists())
            self.assertEqual(
                (archive / "repos" / "successful" / "42" / "result.txt").read_text(encoding="utf-8"),
                "kept",
            )
            self.assertTrue((output / "repos" / "successful").is_dir())

    def test_pipeline_lock_rejects_a_second_concurrent_step(self):
        with tempfile.TemporaryDirectory() as temp:
            config = {"paths": {"output_root": temp}}
            with pipeline_lock(config, "step003"):
                with self.assertRaises(PipelineError):
                    with pipeline_lock(config, "step003"):
                        pass

class ScopeFixtureTests(unittest.TestCase):
    def test_nearest_maven_module_and_reactor_are_found(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            (repo / "pom.xml").write_text("<project/>", encoding="utf-8")
            module = repo / "modules" / "core"
            source = module / "src" / "main" / "java" / "p" / "A.java"
            source.parent.mkdir(parents=True)
            (module / "pom.xml").write_text("<project/>", encoding="utf-8")
            source.write_text("class A {}", encoding="utf-8")
            scope = find_build_scope(repo, source)
            self.assertIsNotNone(scope)
            self.assertEqual(scope["module_dir"], "modules/core")
            self.assertEqual(scope["build_root"], ".")
            self.assertEqual(scope["module_selector"], "modules/core")

    def test_normal_recipes_precede_external_repository_fallback(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            module = repo / "module"
            module.mkdir()
            (repo / "pom.xml").write_text("<project/>", encoding="utf-8")
            (module / "pom.xml").write_text("<project/>", encoding="utf-8")
            (repo / "mvnw.cmd").write_text("@echo off\n", encoding="utf-8")
            config = protocol_config()
            config["build"].update({
                "prefer_repository_wrapper": True,
                "allow_global_tool_fallback": True,
                "maven_skip_flags": ["-Dcheckstyle.skip=true"],
                "maven_settings_file": str(Path(__file__).resolve().parents[1] / "maven-settings-v3.xml"),
            })
            scope = {
                "build_tool": "maven", "build_root": ".", "module_dir": "module",
                "module_selector": "module", "scope_key": "maven:module",
            }
            recipes = build_recipes(repo, scope, config)
            names = [recipe["name"] for recipe in recipes]
            first_external = next(index for index, name in enumerate(names) if "external_repository" in name)
            self.assertTrue(all("external_repository" not in name for name in names[:first_external]))
            self.assertTrue(any(name.startswith("repository_wrapper") for name in names))
            self.assertTrue(any(name.startswith("global_fallback") for name in names))


class EligibilityFixtureTests(unittest.TestCase):
    def test_real_config_parses_and_java_analysis_has_no_cc_gate(self):
        config_path = Path(__file__).resolve().parents[1] / "config_v3.yaml"
        config = load_config(config_path)
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "src" / "main" / "java" / "p" / "A.java"
            source.parent.mkdir(parents=True)
            source.write_text(
                "package p;\n\npublic class A {\n"
                "  private final int base = 0;\n\n"
                "  public int value(int x) {\n"
                "    if (x > 0) return x;\n"
                "    return base;\n"
                "  }\n"
                "}\n", encoding="utf-8"
            )
            row = {
                "repo_id": "1", "repo_url": "https://example.invalid/1",
                "class_key": "1:src/main/java/p/a.java", "focal_class": "A",
                "focal_path": "src/main/java/p/A.java", "mapping_count": "2",
                "source_json_files": "1.json;2.json", "public_method_count_metadata": "1",
            }
            metric = analyze_java_file(source, row, config)
            self.assertEqual(metric["metric_status"], "success")
            self.assertTrue(metric["eligible_for_sampling"])
            self.assertGreaterEqual(metric["max_method_cc"], 1)


class SamplingFixtureTests(unittest.TestCase):
    def test_exact_invariants_and_no_overlap(self):
        main, backup = select_repo_balanced_classes(fake_frame(), 42)
        self.assertEqual(len(main), 300)
        self.assertEqual(len(backup), 60)
        self.assertEqual(len({row["class_key"] for row in main}), 300)
        self.assertEqual(len({row["class_key"] for row in backup}), 60)
        self.assertFalse({row["class_key"] for row in main} & {row["class_key"] for row in backup})
        self.assertTrue(all(row["selection_algorithm"] == SELECTION_ALGORITHM for row in main + backup))
        self.assertTrue(all(row["repository_storage_path"] == f"repos/successful/{row['repo_id']}" for row in main + backup))
        for repo_index in range(30):
            repo_id = str(1000 + repo_index)
            self.assertEqual(sum(row["repo_id"] == repo_id for row in main), 10)
            self.assertEqual(sum(row["repo_id"] == repo_id for row in backup), 2)

    def test_input_order_and_complexity_do_not_change_selection(self):
        original = fake_frame()
        first_main, first_backup = select_repo_balanced_classes(original, 42)
        changed = [dict(row) for row in original]
        random.Random(9876).shuffle(changed)
        for index, row in enumerate(changed):
            row["max_method_cc"] = str(999 - index)
            row["sum_method_cc"] = str(2000 - index)
        second_main, second_backup = select_repo_balanced_classes(changed, 42)
        self.assertEqual({row["class_key"] for row in first_main}, {row["class_key"] for row in second_main})
        self.assertEqual({row["class_key"] for row in first_backup}, {row["class_key"] for row in second_backup})

    def test_relative_halves_are_assigned_only_after_selection(self):
        main, _ = select_repo_balanced_classes(fake_frame(), 42)
        classified = assign_relative_complexity_halves(main)
        self.assertEqual(sum(row["complexity_half"] == "lower_complexity_half" for row in classified), 150)
        self.assertEqual(sum(row["complexity_half"] == "higher_complexity_half" for row in classified), 150)


class ConfigGuardFixtureTests(unittest.TestCase):
    def test_scientific_integrity_guards(self):
        config = protocol_config()
        validate_config(config)
        config["eligibility"]["complexity_gate_enabled"] = True
        with self.assertRaises(Exception):
            validate_config(config)


if __name__ == "__main__":
    unittest.main(verbosity=2)
