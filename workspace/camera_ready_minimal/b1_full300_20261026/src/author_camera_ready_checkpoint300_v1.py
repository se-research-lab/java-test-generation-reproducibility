"""Create isolated manuscript revision from sealed offline analysis. No experiments."""
import json,shutil,sys,difflib
from pathlib import Path
R=Path(__file__).resolve().parents[1];OLD=R/'analysis_camera_ready_rq45_v1';O=R/'camera_ready_checkpoint300_v1';B=R.parent/'paired49_20261023'
sys.path.insert(0,str(B));import audit
assert not O.exists();O.mkdir();shutil.copytree(OLD/'manuscript',O/'backup/manuscript');shutil.copytree(OLD/'manuscript',O/'manuscript')
S=O/'manuscript/sections'
def put(name,text):(S/name).write_text(text.strip()+'\n',encoding='utf-8')
def replace(name,old,new):
 p=S/name;t=p.read_text(encoding='utf-8');assert old in t,(name,old);p.write_text(t.replace(old,new),encoding='utf-8')
put('00_abstract.tex',r'''
\begin{abstract}
We evaluate GPT-4o-mini zero-shot and EvoSuite 1.2.0 on 300 Java classes from 30 repositories, separating mutation strength from pipeline outcomes. GPT passes the historical process gate on 61/300 classes (20.33\%), below AgoneTest's 28.6\% reference, versus 158/300 for assertion-disabled EvoSuite E0. GPT's mutation median is 66.67\% on 61 observations; the published 44.5\% aggregate is a fixed threshold with uncertain cross-study comparability. Across 300 E0 pairs, the mean difference favours GPT by 4.84 points, but 46/70/184 higher/lower/tied pairs and $A_{12}=0.443$ favour E0; 130 ties are joint failures. Assertion-enabled E1 with runtime support attains mean 59.16\% on the fixed49 common-build cohort versus GPT's 58.44\%; the paired gap is $-0.72$ points (repository-bootstrap 95\% interval [-7.50, 8.38]). E1 provides 221 observed mutation scores, 58 policy failure zeros and 21 unresolved scores. On 279 determinate pairs, GPT/E1 means are 12.75/34.28\%. Full300 E1 mean bounds are [31.88, 38.88]\%. Missing outcomes and unequal integration support preclude transferring E0 non-inferiority to E1. Results identify a GPT buildability shortfall and configuration-dependent mutation evidence, without establishing a general generator ranking.
\keywords{Unit test generation \and GPT-4o-mini \and EvoSuite \and Mutation testing \and Buildability \and Java}
\end{abstract}
''')
replace('03_method.tex',r'For PIT, mutation score is KILLED divided by all report rows belonging to the focal compilation unit, multiplied by 100 and rounded to two decimals. The archived reader groups by source-file name and package, including nested classes when they share that source unit. Absolute mutant counts accompany the supplementary percentages. Remaining historical raw reports are not assumed to certify both arms\' denominators.'.replace("\\'","'"),r'''For PIT, mutation score is $100K/N$, rounded to two decimals: $K$ counts KILLED and $N$ all focal source-file/package rows, including nested classes. TIMED\_OUT contributes to $N$, not $K$; $N=0$ is undefined. This is the shared historical reducer, not an assumed PIT summary metric. Raw reports reverify 61 G0 and 221 E1 scores. E0 exports and reducer code are preserved, but surviving shared-workspace reports cannot independently certify E0 denominators.''')
replace('03_method.tex',r'\textbf{strict whole-sample} view zero-fills across all $N$ classes:',r'\textbf{historical strict whole-sample} view zero-fills across all $N$ classes:')
replace('03_method.tex',r'The Gradle40 batch uses the resolved main runtime classpath, native JUnit4 and external integration scripts, offline caches, and wrapper-compatible PIT/JaCoCo. Unlike Maven compatibility, it does not upgrade existing JUnit; missing JUnit4 is supplied only in test scope. Test/JaCoCo and PIT commands have 900-second caps. All 40 slots were processed under one frozen policy, with 30 generation calls and no retry. These integration differences are part of the measured pipeline, not model-only effects.',r'''The initial Gradle40 batch used resolved runtime classpaths, native JUnit4, external scripts, offline caches and wrapper-compatible PIT/JaCoCo, with 900-second test/measurement caps. It made 30 generation calls without retry; ten slots lacked an integration task. A subsequent locked amendment resolved measurement-tool dependencies for ten existing suites without regeneration. Maven amendments restored preparation-damaged POM inputs with provenance and supplied test-only JUnit3 compatibility; the latter did not establish valid PIT measurements. Production source and generated Java/assertions were not repaired. These post-outcome amendments, attempts and retained suite hashes are documented; G0 receives no matching support.''')
replace('03_method.tex',r'The E1 extension retains 30 unscored classes as missing, not zero, and reports its 270 recorded outcomes separately from the fixed300 historical baseline. We use the same process gate and PIT formula, not a new quality scale. Whole-repository bootstrap intervals on observed keys are exploratory; they do not correct nonrandom missingness or post-outcome policy changes. For unresolved E1 outcomes, deterministic full300 bounds allow each score in [0,100] and each build flag in [0,1], keeping G0 fixed. A second bound treats ten missing-task failures as unresolved. These bounds are not confidence intervals or NI tests. Historical log symptoms are extracted within arm-specific execution blocks, with lines/hashes retained; overlapping symptoms are not exclusive causal diagnoses.',r'''E1 retains the PIT formula and distinguishes observed scores, conventional end-to-end failure zeros, and unresolved values. Unlike historical zero-fill, adapter/provider uncertainty and zero focal denominators remain missing. A completed pipeline failure, including a whole-measurement timeout, receives conventional zero without an observed PIT score. Generation, compilation artifacts, native test results, PIT reports and process gates are recorded separately. Reports must be complete, attributable to the focal source and selected suite, and from a completed measurement. Repository bootstrap intervals are exploratory and conditional on determinate keys. Full300 bounds vary unknown scores over [0,100] and unknown gates over [0,1], keeping G0 fixed; they are not confidence intervals or NI tests. Arm-scoped log symptoms are diagnostic, not exclusive causal labels.''')
put('04a_supplement.tex',r'''
\subsection{Assertion-enabled E1 on Fixed49}
All 49 historical common-build keys remain fixed. GPT--E1 has mean difference $-0.72$ points (15-repository 95\% bootstrap interval [-7.50, 8.38]), median $-5.00$, and 14/26/9 higher/lower/tied pairs. The interval establishes neither equivalence nor NI at five points. The marginal $A_{12}=0.503$ differs from the paired higher-plus-half-ties proportion, 0.378.

\begin{table}[htbp]
\caption{Mutation pipeline scores on fixed49. Process-gate success does not certify all assertions passed.}
\label{tab:e1}\centering\small
\begin{tabularx}{\linewidth}{@{}Yrrr@{}}\toprule
Statistic & GPT (G0) & E0 & E1\\\midrule
Mean mutation (\%) & 58.44 & 17.63 & 59.16\\
Median mutation (\%) & 65.79 & 12.90 & 71.43\\
Recorded process gate & 49/49 & 49/49 & 49/49\\
Suite/report evidence & not certified & not certified & 48/49\\\bottomrule
\end{tabularx}\end{table}

All 49 E1 focal reports are nonempty. Native suite bytes are preserved; one suite has sandbox/resource-limit errors, and another contains only an empty placeholder. A passing gate therefore does not imply useful assertions. Across all attributable reports, focal mutant counts have median 14 (IQR 6--31, range 1--47) for G0's 61 classes and 17 (IQR 8--33, range 1--68) for E1's 221; these are different cohorts, not a paired denominator comparison. E0 raw counts are not independently reverified.

\subsection{E1 Extension: Evidence and RQ4--RQ5 Sensitivities}
The reconciled ledger contains all 300 unique keys, but not 300 measured E1 scores. It contains 221 valid observed scores (41 equal zero), 58 conventional pipeline-failure zeros, and 21 unresolved end-to-end scores. The latter comprise ten JUnit3/provider cases, ten Gradle missing-task cases and one completed report with zero focal mutants. Within the 30-class completion amendment, 12 lack valid measurements: ten provider cases and two whole-process timeouts. Those two receive policy zero, not observed zero, and are already included in the 58 failures.

\begin{table}[htbp]
\caption{E1 evidence on 300 keys. Rows are distinct indicators, not an additive failure taxonomy; unknown is not compile failure.}
\label{tab:e1stages}\centering\small
\begin{tabularx}{\linewidth}{@{}Yrrr@{}}\toprule
Indicator & Pass/available & Fail/unsuccessful & Other/unknown\\\midrule
Generation: complete suite & 253 & 37 & 10 not started\\
Production compilation artifact & 285 & -- & 15\\
Test compilation artifact/XML & 248 & -- & 52\\
Native test execution & 240 & 4 & 4 skip; 52 unknown\\
PIT: nonempty valid focal report & 221 & -- & 79\\
Process gate: Maven & 203 & 47 & 10\\
Process gate: Gradle & 19 & 11 & 10\\
Process gate: all & 222 & 58 & 20\\\bottomrule
\end{tabularx}\end{table}

The 16 previously flagged gate-pass cases resolve into nine valid PIT reports lacking focal JaCoCo evidence, six valid PIT reports with failed/skipped/incomplete native suites, and one zero-mutant denominator. Report validity and suite success remain distinct. Class294 illustrates score provenance: its completed E1 measurement has 0 KILLED, 38 NO\_COVERAGE and 6 TIMED\_OUT mutants, hence $0/44=0\%$, with eight passing tests. Its historical G0/E0 zeros instead denote pipeline failure. Adding mutant timeouts to the numerator would change the locked formula; whole-measurement timeouts provide no valid observed score.

\textbf{RQ4.} On 279 determinate pairs from 28 repositories, G0/E1 end-to-end means are 12.75/34.28\%; the difference is $-21.53$ points (repository-bootstrap interval [-27.78, -15.55]), with 20/161/98 higher/lower/tied pairs. E1's observed-only mean is 43.28\% on 221 classes; it must not be compared with G0's full300 mean. Allowing 21 unknown scores in [0,100] gives E1 full300 mean bounds [31.88, 38.88]\% and G0--E1 bounds [-27.03, -20.03] points, conditional on the 58 policy zeros. These are missingness bounds, not CI or NI decisions. Keeping the two measurement timeouts unknown instead gives difference bounds [-27.69, -20.03].

The Maven sensitivity has 249 determinate scores among 260 slots: G0--E1 mean gap $-21.40$ (25-repository interval [-27.37, -15.66]). Gradle has 30 among 40: $-22.66$ (three-repository interval [-53.10, 10.00]); few clusters and missingness sharply limit interpretation. Holding the six nonpassing-suite scores unknown expands full300 difference bounds to [-28.91, -19.91]. These analyses cannot transfer E0-specific NI to E1.

\textbf{RQ5.} E1 has 222 gate passes, 58 failures and 20 unknowns: 222/280 determinate gates, or 79.29\% (repository interval [65.36, 91.79]\%). Full300 gate bounds are [74.00, 80.67]\%. Among those 280 pairs, 60 jointly pass, one is G0-only, 162 E1-only and 57 jointly fail. G0 remains 61/300 in RQ3. Raw legacy zeros for adapter/provider uncertainty are not 20 additional compile failures. The new 60-key common-success set is diagnostic only, never a replacement for fixed49 or the 61/45/300 GPT cohorts.

Retaining class3's original outcome instead of its post-outcome diagnostic selection yields 221/280 E1 gate passes and a 279-pair mean gap $-21.18$ (interval [-27.43, -15.16]). This sensitivity exposes selection effects without choosing the better result by score. E1 has stronger recorded pipeline outcomes under additional environment support; it is not an isolated assertion-only or generator-only effect.
''')
replace('05_discussion.tex','including nine Gradle successes','including 19 Gradle gate passes')
replace('06_threats.tex','Thirty unscored slots, ten missing-task zeros and incomplete evidence on passing rows prevent a validated full300 E1 comparison.','Twenty-one unresolved scores, 20 unknown gates and incomplete native-suite evidence prevent a complete full300 E1 comparison. E0 raw report ownership is not independently reverified; historical exports and the common reducer are retained.')
replace('06_threats.tex','27 observed-E1 repositories','28 determinate-E1 repositories')
replace('07_conclusion.tex','Its 270 observed outcomes favour E1 in mutation and recorded builds, while 30 slots remain unscored.','Its 279 determinate end-to-end scores favour E1 under the amended pipeline; 21 scores remain unresolved, and gate bounds are [74.00, 80.67]\\%.')
replace('08_disclosure.tex','is available at [replication package withheld for double-blind review; submitted as supplementary material]','has the following availability statement: ``replication package withheld for double-blind review; submitted as supplementary material\'\'')
diff=[];manifest=[]
for p in sorted((O/'manuscript').rglob('*')):
 if p.is_file():
  rel=p.relative_to(O/'manuscript');old=O/'backup/manuscript'/rel
  manifest.append({'path':str(rel),'before':audit.sha(old),'after':audit.sha(p)})
  if audit.sha(old)!=audit.sha(p):diff.extend(difflib.unified_diff(old.read_text(encoding='utf-8').splitlines(True),p.read_text(encoding='utf-8').splitlines(True),fromfile='baseline/'+str(rel),tofile='revision/'+str(rel)))
(O/'manuscript_changes.diff').write_text(''.join(diff),encoding='utf-8');(O/'source_change_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
audit.log('CAMERA_READY_CHECKPOINT300_AUTHORED',path=str(O),manifest_sha256=audit.sha(O/'source_change_manifest.json'),new_experiments=0)
print(json.dumps({'output':str(O),'changed_files':sum(x['before']!=x['after'] for x in manifest)}))
