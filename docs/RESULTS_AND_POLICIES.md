# Result semantics and policy history

## Cohorts

- G0/E0 historical: 300 paired class keys, 30 repositories, 10 classes per repository.
- GPT RQ1/RQ2/RQ3 cohorts: 61 / 45 / 300, unchanged.
- Fixed49: original 49 common process-gate passes, 15 Maven repositories; not a newly selected E1 intersection.
- E1: 221 valid observed PIT scores + 58 policy failure zeros + 21 unresolved = 300 rows.
- E1 native gate: 222 pass + 58 fail + 20 unresolved. The additional score-unknown case has a passing gate but zero focal mutants.
- 279 determinate mutation pairs include 58 policy zeros. They are not 279 observed PIT reports.

## Formula and uncertainty

Mutation score is round(100*KILLED/N,2), with N all accepted focal SourceFile/package mutant rows including nested classes. TIMED_OUT is denominator-only under the archived reducer. Zero mutants means undefined, not a measured 0%. Whole-measurement timeout is distinct from a mutant TIMED_OUT result.

Class294 has 0 KILLED/44 mutants, including 6 TIMED_OUT: valid observed0%. Classes112/269 have whole-measurement timeouts and policy0 without valid observed scores. Twenty score-unknown cases are ten provider/JUnit3 and ten Gradle pre-generation task/adapter cases; class6 with zero focal mutants makes21. Full300 bounds and available-cohort CIs are different quantities.

## Class3 exception

The initial attempt generated a suite but failed due to missing org.junit. A later measurement diagnostic reused the suite, added test-only JUnit support, passed and killed1/1 mutant. It was initially labelled diagnostic-only and was later admitted by the result-map amendment. Keep both the original metadata and later selection record; do not rewrite their flags. The canonical table retains this selection and has an original-outcome sensitivity. This is a post-outcome compatibility exception, not a prospectively fixed technical retry.

## Source/policy navigation

Read the E1 top-level `EXPERIMENT_CONFIGURATION_FREEZE_20261026.json`, `MAVEN_NATIVE_JUNIT_AMENDMENT_V2.md`, `measurement_result_map_v2.json`/v3, admissions v1–v6, Gradle protocol, and `completion_amendment_v1/` annexes. The accepted E1 audit folder provides class/attempt histories. Do not infer current policy from an early README/protocol status string alone.

## Scientific limits

RQ4's historical NI is E0-specific; E1 does not establish general generator superiority/NI. RQ5 concerns the evaluated integration pipelines. G0 did not receive matching E1 environment support. Repeated-run variance, budget equalization, practical validation of margin5pp and complete E0 raw ownership remain limited. Code related to incomplete repeated subsets or other diagnostics is not evidence of completed repeated-run evaluation.

## Bundle scope

Frozen summary data and source are present; full raw jobs/logs/generated suites remain local and are referenced by unchanged manifests. This folder is not the full evidence release described in the earlier GitHub artifact plan. Public licensing, redaction review and actual artifact URL remain author decisions.
