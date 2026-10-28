"""Create a separate manuscript and evidence report from checked offline analysis."""
import json, shutil, sys, difflib
from pathlib import Path
R=Path(__file__).resolve().parents[1];B=R.parent/'paired49_20261023';O=R/'analysis_camera_ready_rq45_v1'
sys.path.insert(0,str(B));import audit
old=B/'final_handoff_20261025_private/manuscript';source=O/'manuscript';backup=O/'backup/manuscript'
assert not source.exists() and not backup.exists()
original={}
for p in old.rglob('*'):
    if p.is_file() and p.suffix in ('.tex','.bib','.cls','.bst'):
        rel=p.relative_to(old);original[rel.as_posix()]=audit.sha(p)
        for dest in (source/rel,backup/rel):
            dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest);assert audit.sha(dest)==original[rel.as_posix()]
def get(name):return (source/'sections'/name).read_text(encoding='utf-8')
def put(name,text):(source/'sections'/name).write_text(text,encoding='utf-8')
def replace(name,old,new):
    text=get(name);assert text.count(old)==1,(name,old[:60]);put(name,text.replace(old,new))

put('00_abstract.tex',r'''\begin{abstract}
We evaluate GPT-4o-mini zero-shot and EvoSuite 1.2.0 on 300 Java classes from 30 repositories, separating conditional mutation scores from pipeline outcomes. Historical EvoSuite E0 disables assertions. GPT passes the process-build gate on 61/300 classes (20.33\%), below AgoneTest's 28.6\% reference, versus E0's 158/300. GPT's mutation median is 66.67\% on 61 observations; the published 44.5\% aggregate remains a fixed threshold with uncertain cross-study comparability. Across 300 E0 pairs, the mean difference favours GPT by 4.84 points, but directional counts of 46/70/184 higher/lower/tied and $A_{12}=0.443$ favour E0; 130 ties are joint build failures. Assertion-enabled E1 with runtime support reaches mean 59.16\% on the fixed49 common-build cohort versus GPT's 58.44\%; the paired gap is $-0.72$ points (repository-bootstrap 95\% interval [-7.50, 8.38]). The E1 extension has 270 operational outcomes and 30 unscored classes. On those 270 keys, GPT/E1 means are 11.35/31.65\% and build counts 56/204. Missing outcomes and unequal integration support preclude transferring the E0 non-inferiority conclusion to E1. Failure-stage and repository analyses identify both a GPT buildability bottleneck and substantial environment dependence, without establishing a general generator ranking.
\keywords{Unit test generation \and GPT-4o-mini \and EvoSuite \and AgoneTest \and Mutation testing \and Buildability \and Java}
\end{abstract}
''')
replace('01_introduction.tex','RQ1--RQ3 compare GPT with AgoneTest\'s fixed reference values; RQ4--RQ5 compare the paired historical pipelines. Complexity and failure taxonomy are supporting diagnostics.',"RQ1--RQ3 compare GPT with AgoneTest's fixed reference values. RQ4--RQ5 retain the paired historical E0 baseline and assess its robustness through E1 configuration and pipeline sensitivities; the questions and GPT observations are unchanged.")
text=get('03_method.tex')
start=text.index('The supplementary EvoSuite configuration (E1)')
end=text.index("AgoneTest's 44.5",start)
new=r'''E1 enables assertions (MUTATION), scaffolding and runtime, retaining BRANCH, a 60-second search budget, disabled test archive/separate classloader, and seed 20261023 plus the original 1-based class index. Native test/scaffold sources are not repaired. Generation has a 240-second cap and at most one same-seed retry after specified technical initialization failures, never after a low score; Maven measurement has a 300-second cap.

\textbf{Integration support and timing.} E1 uses native JUnit integration: runtime support, missing test-scope JUnit4, a conditional JUnit4 upgrade when TestRule is absent, and exact-test selector corrections where required. These E-only rules were developed after integration failures; fixed49 suites were remeasured without changing their Java sources. One later Maven measurement override was selected after a successful diagnostic; its original result is retained as a sensitivity. Thus E1 is not a uniform assertion-only intervention or a prospectively outcome-blind treatment. G0 receives no corresponding support or remeasurement. Final Maven V6 and Gradle policies were locked before their respective batches; attempts and selection rules are auditable.

The Gradle40 batch uses the resolved main runtime classpath, native JUnit4 and external integration scripts, offline caches, and wrapper-compatible PIT/JaCoCo. Unlike Maven compatibility, it does not upgrade existing JUnit; missing JUnit4 is supplied only in test scope. Test/JaCoCo and PIT commands have 900-second caps. All 40 slots were processed under one frozen policy, with 30 generation calls and no retry. These integration differences are part of the measured pipeline, not model-only effects.

The E1 extension retains 30 unscored classes as missing, not zero, and reports its 270 recorded outcomes separately from the fixed300 historical baseline. We use the same process gate and PIT formula, not a new quality scale. Whole-repository bootstrap intervals on observed keys are exploratory; they do not correct nonrandom missingness or post-outcome policy changes. For unresolved E1 outcomes, deterministic full300 bounds allow each score in [0,100] and each build flag in [0,1], keeping G0 fixed. A second bound treats ten missing-task failures as unresolved. These bounds are not confidence intervals or NI tests. Historical log symptoms are extracted within arm-specific execution blocks, with lines/hashes retained; overlapping symptoms are not exclusive causal diagnoses.

'''
put('03_method.tex',text[:start]+new+text[end:])
# Remove a nonessential descriptive complexity paragraph to make room for reviewer-requested evidence.
text=get('04_results.tex');start=text.index(r'\textbf{Complexity.}');end=text.index(r'\textbf{Failure taxonomy.}',start);text=text[:start]+text[end:]
oldpara='Operational owner labels classify 160 GPT rows as generator\\_output and 79 as harness, versus 34 and 108 for E0; these labels do not prove a sole causal origin.'
newpara='Recorded stages are operational labels, not validated causal attribution. Arm-scoped logs are available for 298 classes per arm. Among GPT failures, 106 contain unresolved-symbol, 41 type/signature, 22 artifact/plugin-resolution and 11 license-header markers; these overlap. Of 158 rows labelled test-compilation failure, 156 name a generated-test source location. The other two lack that specific marker, and an existing production/dependency error occurs in one row. A location or label alone does not establish model fault. E0 logs expose a test-copy variable error on 20 Gradle classes; other failures require separate diagnosis.'
assert oldpara in text;text=text.replace(oldpara,newpara)
put('04_results.tex',text)
put('04a_supplement.tex',r'''\subsection{Assertion-enabled E1 on Fixed49}
All 49 historical common-build keys are retained, with unchanged GPT scores. Table~\ref{tab:e1} uses the original process-gate/PIT scoring convention. GPT--E1 has mean difference $-0.72$ points (whole-repository 95\% bootstrap interval [-7.50, 8.38]), median $-5.00$, and 14/26/9 higher/lower/tied pairs. The interval leaves the mean ordering uncertain; it does not establish equivalence or full300 NI.

\begin{table}[htbp]
\caption{Mutation pipeline scores on fixed49. E1 enables assertions and runtime support; evidence flags do not redefine scores.}
\label{tab:e1}\centering\small\setlength{\tabcolsep}{6pt}
\begin{tabularx}{\linewidth}{@{}Yrrr@{}}\toprule
Statistic & GPT (G0) & E0 & E1\\\midrule
Mean mutation (\%) & 58.44 & 17.63 & 59.16\\
Median mutation (\%) & 65.79 & 12.90 & 71.43\\
Recorded process-build & 49/49 & 49/49 & 49/49\\
Suite/report evidence & not certified & not certified & 48/49\\\bottomrule
\end{tabularx}\end{table}

All 49 focal PIT reports are nonempty, with 1--47 mutants per source unit (median 17, mean 20.20). Native suite bytes are preserved. One suite contains only an empty placeholder; another has sandbox/resource-limit errors. The gate can ignore test failures, so 49/49 builds neither certifies oracle quality nor estimates unconditional buildability. Assertions, runtime, seeds and integration change jointly relative to E0.

\subsection{E1 Extension: Failures and RQ4--RQ5 Sensitivities}
E1 comprises the fixed49 and the remaining 251 class slots. Table~\ref{tab:e1stages} partitions all 300. There are 270 recorded outcomes and 30 unscored slots, not a complete new 300-pair NI experiment. Of 243 classes with native suites, 204 pass the process gate, 19 fail the measurement lifecycle (8 license checks, 10 PIT minion failures, 1 test-execution failure), and 20 remain unmeasured (10 JUnit guards, 10 PIT dependency failures). No generated-test compiler error was found among those 19 lifecycle failures. Six gate-passing suites lack complete execution evidence, and 16 lack complete measurement evidence; flags accompany, rather than replace, the legacy score.

\begin{table}[htbp]
\caption{E1 operational outcomes on the fixed300 sample. Counts are mutually exclusive; unscored slots are not assigned zero.}
\label{tab:e1stages}\centering\small
\begin{tabularx}{\linewidth}{@{}Yrr@{}}\toprule
Stage/outcome & Maven & Gradle\\\midrule
Process gate passed & 195 & 9\\
Missing integration task before generation & 0 & 10\\
Generation unsuccessful & 27 & 10\\
License-header check failed & 8 & 0\\
PIT coverage-minion failure & 10 & 0\\
Generated-test execution failure & 0 & 1\\
Unscored: frozen POM / JUnit guard / PIT dependency & 20 & 10\\\midrule
Total & 260 & 40\\\bottomrule
\end{tabularx}\end{table}

Gradle contributes nine passing measurements, one test runtime failure, three class-loading failures, six unsupported-bytecode failures, one generation timeout, ten missing-task failures and ten unscored PIT-dependency failures. The latter ten already have generated suites; they are not ten observed test-build failures. Missing-task failures retain their raw zero scores for audit, but require integration-validity review. These observations improve on E0's zero Gradle builds without establishing uniform Gradle support.

\textbf{RQ4.} On the 270 observed keys, GPT/E1 strict means are 11.35/31.65\%, with paired difference $-20.31$ points (27-repository bootstrap interval [-26.90, -13.94]) and 16/149/105 higher/lower/tied pairs. This observed subset is not the original full300 estimand. Allowing the 30 unresolved E1 scores to vary over [0,100] yields full300 mean-difference bounds [-26.63, -16.63] points; additionally treating ten missing-task zeros as unresolved gives [-29.96, -16.63]. These are bounds conditional on the other recorded outcomes, not NI tests of the signed-rank location. Fixed49 and the extension therefore do not justify carrying E0's conditional NI conclusion over to E1.

\textbf{RQ5.} On those same 270 keys, GPT/E1 pass on 56/204; paired counts are 55 joint passes, 1 GPT-only, 149 E1-only and 65 joint failures. GPT remains 61/300 in RQ3. With 30 unresolved E1 flags, full300 build-rate bounds are [68.00,78.00]\%; with missing-task failures also unresolved, [68.00,81.33]\%. Retaining the original result instead of the post-outcome measurement override changes E1 to 203 passes and the observed mutation gap to $-19.94$ points, without reversing either descriptive direction. E1 has greater recorded pipeline buildability, but unequal environment support prevents attributing the difference solely to generation. The new 55-key common-success set is diagnostic only and never replaces fixed49 or GPT's 61/45/300 cohorts.
''')
put('05_discussion.tex',r'''\section{Discussion}

\textbf{Buildability constrains replication.} GPT's 61/300 builds are 8.27 points below AgoneTest's reference. Mutation median 66.67\% selects 61 rows, and branch evidence is descriptive at $n=45$. The 44.5\% source aggregate is not a known population median with compatible uncertainty; integration and aggregation differences prevent model-only attribution.

\textbf{RQ4 is configuration-dependent.} E0's positive strict mean gap coexists with 70 E0-higher versus 46 GPT-higher pairs. $A_{12}$ compares all cross-arm combinations, not paired wins; the NI rank effect concerns shifted $d_i+5$. Fixed49 pairing removes the original survivor mismatch, but E1's interval spans zero there, while its observed extension favours E1. Neither finding transfers E0 NI to assertion-enabled EvoSuite. Missing outcomes, policy amendments and unequal runtime support constrain inference. The 5-point tolerance remains without stakeholder validation.

\textbf{RQ5 concerns pipelines.} E0's Maven advantage survives excluding Gradle; E1 also records more builds, including nine Gradle successes. However, unresolved task/dependency failures and error-ignoring gates preclude a generator-only success rate. Stage labels, arm-scoped log symptoms and suite/report flags distinguish available evidence without inventing a second primary score. Unknown outcomes remain explicit.

\textbf{Variance and scope.} API latency/token caps and search budgets are not equal compute. Repair/context-enhanced GPT and hybrids are separate treatments~\cite{ref10}. Each configuration has one scheduled generation run per class; conditional technical retries are not variance replications. No complete repeated-run evaluation is available, and repository bootstrap does not estimate within-class run-to-run variance.
''')
replace('06_threats.tex',"One E1 suite has sandbox/resource-limit errors, limiting runtime interpretation despite the recorded process gate.","E1 includes post-outcome compatibility decisions and one diagnostic selection; retaining the original diagnostic-class outcome does not reverse the observed direction. Thirty unscored slots, ten missing-task raw zeros and incomplete evidence on some passing rows prevent treating the extension as a fully validated 300-pair comparison.")
replace('06_threats.tex','bootstrap sensitivities condition on 30 or 15 clusters.','bootstrap sensitivities condition on observed repository clusters (30 historical, 15 fixed49, 27 E1 observed).')
put('07_conclusion.tex',r'''\section{Conclusion}
GPT-4o-mini zero-shot passes the process gate on 61/300 Java classes (20.33\%), below AgoneTest's 28.6\% reference. RQ1 remains a fixed-threshold comparison on 61 observations and RQ2 descriptive at 45. Historical E0 builds more often (158/300), but disables assertions; its $+4.84$-point GPT strict mean gap, contrary directional counts and conditional NI result do not generalize to E1.

Assertion-enabled E1 yields a fixed49 gap of $-0.72$ points with interval [-7.50, 8.38]. Its 270 observed outcomes favour E1 in mutation and recorded builds, while 30 slots remain unscored. RQ4 therefore retains E0-specific NI without asserting E1 NI; RQ5 supports a pipeline-level buildability advantage with explicit environment limitations. All five questions and GPT's original cohorts remain intact. Uniform integration and repeated-run evidence are still needed for broader claims.
''')
# Hash every copied original and produce a reviewable diff; no original is overwritten.
changes=[]
for rel,h in original.items():
    assert audit.sha(old/rel)==h==audit.sha(backup/rel)
    if audit.sha(source/rel)!=h:
        changes.append(rel)
diff=''.join(''.join(difflib.unified_diff((backup/rel).read_text(encoding='utf-8').splitlines(True),(source/rel).read_text(encoding='utf-8').splitlines(True),fromfile='before/'+rel,tofile='after/'+rel)) for rel in changes)
(O/'manuscript_changes.diff').write_text(diff,encoding='utf-8')
(O/'source_change_manifest.json').write_text(json.dumps({'original_source':str(old),'backup_hashes':original,'changed_sources':changes,'after_hashes':{rel:audit.sha(source/rel) for rel in original},'original_unchanged':True},indent=2),encoding='utf-8')
audit.log('B1_RQ45_ISOLATED_MANUSCRIPT_PREPARED',change_manifest_sha256=audit.sha(O/'source_change_manifest.json'),diff_sha256=audit.sha(O/'manuscript_changes.diff'),original_modified=False,experiment_calls=0)
print(json.dumps({'source':str(source),'changed':changes},indent=2))
