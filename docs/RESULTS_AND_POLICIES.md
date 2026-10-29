# Result semantics and policy history

## Cohorts

- G0/E0 historical: 300 paired class keys, 30 repositories, 10 classes per repository.
- GPT RQ1/RQ2/RQ3 cohorts: 61 / 45 / 300, unchanged.
- Fixed49: original 49 common process-gate passes, 15 Maven repositories; not a newly selected E1 intersection.
- E1: 221 valid observed PIT scores + 58 policy failure zeros + 21 unresolved = 300 rows.
- E1 recorded process gate: 222 pass + 58 fail + 20 unresolved. The additional score-unknown case has a passing gate but zero focal mutants.
- 279 determinate mutation pairs include 58 policy zeros. They are not 279 observed PIT reports.

## Formula and uncertainty

Mutation score is round(100*KILLED/N,2), with N all accepted focal SourceFile/package mutant rows including nested classes. TIMED_OUT is denominator-only under the archived reducer. Zero mutants means undefined, not a measured 0%. Whole-measurement timeout is distinct from a mutant TIMED_OUT result.

Class294 has 0 KILLED/44 mutants, including 6 TIMED_OUT: valid observed0%. Classes112/269 have whole-measurement timeouts and policy0 without valid observed scores. Twenty score-unknown cases are ten provider/JUnit3 and ten Gradle pre-generation task/adapter cases; class6 with zero focal mutants makes21. Full300 bounds and available-cohort CIs are different quantities.

## Class3 exception

The initial attempt generated a suite but failed due to missing org.junit. A later measurement diagnostic reused the suite, added test-only JUnit support, passed and killed1/1 mutant. It was initially labelled diagnostic-only and was later admitted by the result-map amendment. Keep both the original metadata and later selection record; do not rewrite their flags. The canonical table retains this selection and has an original-outcome sensitivity. This is a post-outcome compatibility exception, not a prospectively fixed technical retry.

## Source/policy navigation

Read the E1 top-level `EXPERIMENT_CONFIGURATION_FREEZE_20261026.json`, versioned admissions/result-map JSON, adapters/controllers and completion source. The already-published E1 execution-audit tables retain class/attempt histories. Earlier Markdown policy files removed from `workspace/` are not restored; do not rely on dead links to them.

## Scientific limits

RQ4's historical NI is E0-specific; E1 does not establish general generator superiority/NI. RQ5 concerns the evaluated integration pipelines. G0 did not receive matching E1 environment support. Repeated-run variance, budget equalization, practical validation of margin5pp and complete E0 raw ownership remain limited. Code related to incomplete repeated subsets or other diagnostics is not evidence of completed repeated-run evaluation.

## Bundle scope

Frozen primary results and source, Data V3 provenance/readiness evidence, benchmark snapshots and manuscript are present. Full raw jobs/logs/generated suites remain local. Additional post-review diagnostic code/evidence remains local; this is not a complete full-evidence release. Repository URL: https://github.com/se-research-lab/java-test-generation-reproducibility . The paper pins source/data snapshot 86799597262e; no new license or paper DOI is asserted.

## Fixed49 report evidence

The revised Table 5 separates valid focal PIT reports from native execution. G0 and E1 each have 49/49 attributable nonempty focal PIT reports. E1 has 48/49 native passes, including an empty placeholder among the passes; the other suite has native errors. Native-suite pass remains uncertified for historical G0/E0, and E0 report ownership is not independently reverified. None of these editorial evidence labels changes the fixed49 mutation scores.
