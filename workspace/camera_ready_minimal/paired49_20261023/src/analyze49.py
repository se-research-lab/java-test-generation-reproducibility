"""Historical common-success analysis; reads backup only, writes isolated outputs."""
import argparse
import hashlib
import json
import platform
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

BASE = Path(__file__).resolve().parents[1]
BACKUP = BASE/'backup/original'
RUN = BACKUP/'scripts_v2/results/runs/full300_merged_20260724_paper'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path,obj):
    with path.open('x',encoding='utf-8') as f:
        json.dump(obj,f,ensure_ascii=False,indent=2,allow_nan=False)
        f.write('\n')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',default='outputs')
    args=parser.parse_args();out=(BASE/args.out).resolve()
    assert out.is_relative_to(BASE) and not out.is_relative_to(BASE/'backup')
    out.mkdir(parents=True,exist_ok=True)
    assert not any(out.iterdir()), 'Output must be empty; never overwrite prior evidence'
    protocol=json.loads((BASE/'protocol.json').read_text(encoding='utf-8'))
    manifest=json.loads((BASE/'audit/protected_manifest.json').read_text(encoding='utf-8'))
    for row in manifest:
        assert digest(row['backup'])==row['sha256'],row['relative']
    w=pd.read_csv(RUN/'metrics_wide.csv',dtype={'class_key':str,'repo_id':str})
    long=pd.read_csv(RUN/'metrics_long.csv',dtype={'class_key':str,'repo_id':str})
    assert len(w)==300 and w.class_key.is_unique
    assert len(long)==600 and not long.duplicated(['class_key','arm']).any()
    assert set(long.arm)=={'gpt','evosuite'}
    assert w.groupby('repo_id').size().eq(10).all() and w.repo_id.nunique()==30
    assert w.gpt_compilation.isin([0,1]).all() and w.evosuite_compilation.isin([0,1]).all()
    # Independently check all archived wide metrics against the per-arm source table.
    for arm in ['gpt','evosuite']:
        a=long[long.arm.eq(arm)].set_index('class_key').reindex(w.class_key)
        assert len(a)==300 and a.repo_id.notna().all()
        for col in ['compilation','mutation_coverage','strict_mutation_coverage','branch_coverage']:
            assert np.allclose(w[f'{arm}_{col}'].to_numpy(),a[col].to_numpy(),rtol=0,atol=0,equal_nan=True)
    paired=w[w.gpt_compilation.eq(1)&w.evosuite_compilation.eq(1)].copy().sort_values('class_key')
    assert len(paired)==protocol['expected_n']==49
    assert paired.repo_id.nunique()==15 and paired.build_tool.eq('Maven').all()
    g=paired.gpt_mutation_coverage.to_numpy();e=paired.evosuite_mutation_coverage.to_numpy()
    assert np.isfinite(g).all() and np.isfinite(e).all()
    assert ((g>=0)&(g<=100)&(e>=0)&(e<=100)).all()
    paired['difference_pp']=np.round(g-e,8)
    paired['direction']=np.select([paired.difference_pp.gt(0),paired.difference_pp.lt(0)],['GPT_higher','E0_higher'],default='tie')
    paired['measurement_configuration']='submitted_G0_vs_E0_assertions_off'
    paired['eligibility']='historical_compilation_flag_1_both; not a fresh suite-pass audit'
    cols=['class_key','repo_id','focal_class','focal_path','module','build_tool','split_name',
          'gpt_mutation_coverage','evosuite_mutation_coverage','difference_pp','direction',
          'measurement_configuration','eligibility']
    paired[cols].to_csv(out/'paired49.csv',index=False,encoding='utf-8-sig')
    repo=paired.groupby('repo_id',sort=True).agg(n=('class_key','size'),gpt_mean=('gpt_mutation_coverage','mean'),
          evo_mean=('evosuite_mutation_coverage','mean'),difference_sum=('difference_pp','sum'),
          mean_difference_pp=('difference_pp','mean'),gpt_wins=('difference_pp',lambda x:int((x>0).sum())),
          evo_wins=('difference_pp',lambda x:int((x<0).sum())),ties=('difference_pp',lambda x:int((x==0).sum())))
    repo.to_csv(out/'repository_summary.csv',encoding='utf-8-sig')
    rng=np.random.default_rng(protocol['seed'])
    ix=rng.integers(0,len(repo),(protocol['resamples'],len(repo)))
    # Each draw samples 15 whole repositories with replacement, retaining all their pairs.
    sums=repo.difference_sum.to_numpy();counts=repo.n.to_numpy()
    boot=sums[ix].sum(axis=1)/counts[ix].sum(axis=1)
    macro=repo.mean_difference_pp.to_numpy()[ix].mean(axis=1)
    ci=np.quantile(boot,[.025,.975]).tolist()
    pd.DataFrame({'draw':np.arange(len(boot)),'class_weighted_difference_pp':boot,
                  'repository_equal_difference_pp':macro}).to_csv(out/'cluster_bootstrap_draws.csv',index=False)
    loo=pd.DataFrame({'excluded_repo':repo.index,'remaining_n':len(paired)-counts,
                      'mean_difference_pp':(sums.sum()-sums)/(len(paired)-counts)})
    loo.to_csv(out/'leave_one_repository_out.csv',index=False)
    # Save untouched RQ inputs separately; never construct them from paired49.
    masks={'rq1':w.gpt_compilation.eq(1)&w.gpt_mutation_coverage.notna(),
           'rq2':w.gpt_compilation.eq(1)&w.gpt_branch_coverage.notna(),
           'rq3':pd.Series(True,index=w.index)}
    frozen=json.loads((BACKUP/'review_reports/minimal_camera_ready_20261023/rq123_frozen_manifest.json').read_text(encoding='utf-8'))
    # String-preserving reads avoid serialization changes in the protected original fields.
    text_w=pd.read_csv(RUN/'metrics_wide.csv',dtype=str,keep_default_na=False)
    for rq,mask in masks.items():
        keys=sorted(w.loc[mask,'class_key'])
        assert keys==frozen['cohort_keys'][rq]
        text_w[text_w.class_key.isin(keys)].to_csv(out/f'{rq}_input_unchanged.csv',index=False)
    gen=pd.read_csv(RUN/'generated_tests_manifest.csv',keep_default_na=False)
    protected={r['source']:r for r in manifest}
    evidence=[]
    for r in paired.itertuples():
        for arm in ['gpt','evosuite']:
            files=gen[gen.class_key.eq(r.class_key)&gen.arm.eq(arm)]
            assert len(files)>0,(r.class_key,arm,'missing generated artifact manifest')
            for f in files.itertuples():
                archived=protected.get(f.stored_path)
                assert archived is not None,(f.stored_path,'not backed up')
                evidence.append(dict(class_key=r.class_key,arm=arm,source_run_id=f.source_run_id,
                                     source_run_sample_index=f.source_run_sample_index,
                                     original_path=f.stored_path,backup_relative=archived['relative'],
                                     sha256=archived['sha256'],bytes=archived['bytes']))
    pd.DataFrame(evidence).to_csv(out/'paired49_artifact_provenance.csv',index=False,encoding='utf-8-sig')
    d=paired.difference_pp.to_numpy()
    strict=np.round(w.gpt_strict_mutation_coverage-w.evosuite_strict_mutation_coverage,8)
    tie_decomp=[]
    for (gb,eb),subset in w[strict.eq(0)].groupby(['gpt_compilation','evosuite_compilation']):
        tie_decomp.append(dict(gpt_build=int(gb),evo_build=int(eb),pairs=len(subset)))
    stats={
        'dataset':'submitted full300_merged_20260724_paper; E0 assertions=false',
        'n':49,'repositories':15,'maven':49,'gradle':0,
        'gpt_mean':float(g.mean()),'evo_mean':float(e.mean()),
        'gpt_median':float(np.median(g)),'evo_median':float(np.median(e)),
        'paired_mean_difference_pp':float(d.mean()),'paired_median_difference_pp':float(np.median(d)),
        'gpt_wins':int((d>0).sum()),'evo_wins':int((d<0).sum()),'ties':int((d==0).sum()),
        'paired_directional_probability_half_ties':float(((d>0).sum()+.5*(d==0).sum())/49),
        'cluster_percentile_95ci_mean_difference_pp':ci,
        'bootstrap_seed':protocol['seed'],'bootstrap_draws':len(boot),
        'repository_equal_mean_difference_pp':float(repo.mean_difference_pp.mean()),
        'repository_equal_cluster_95ci':np.quantile(macro,[.025,.975]).tolist(),
        'repository_means_positive_zero_negative':[int((repo.mean_difference_pp>0).sum()),int((repo.mean_difference_pp==0).sum()),int((repo.mean_difference_pp<0).sum())],
        'leave_one_repository_out_range_pp':[float(loo.mean_difference_pp.min()),float(loo.mean_difference_pp.max())],
        'original_survivors':{'gpt_n':int(w.gpt_compilation.sum()),'evo_n':int(w.evosuite_compilation.sum()),
                             'gpt_median':float(w.loc[w.gpt_compilation.eq(1),'gpt_mutation_coverage'].median()),
                             'evo_median':float(w.loc[w.evosuite_compilation.eq(1),'evosuite_mutation_coverage'].median())},
        'strict300_context':{'mean_difference_pp':float(strict.mean()),'gpt_wins':int((strict>0).sum()),
                             'evo_wins':int((strict<0).sum()),'ties':int((strict==0).sum()),'tie_build_decomposition':tie_decomp},
        'artifact_files_in_paired49':len(evidence),'new_generation_calls':0,'new_java_measurement_jobs':0,
        'limitations':['historical process/build gate, not a fresh passing-test or raw-PIT audit',
                       'E0 assertions disabled; does not establish fairness of oracle configuration',
                       'conditional survivor cohort, all Maven, not representative of all300 buildability',
                       'rounded archived percentages, no inference of raw mutant counts',
                       '15 observed repository clusters; CI conditional on this cohort and assumptions',
                       'post-review analysis, outcomes previously seen; no new confirmatory/NI claim'],
        'environment':{'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__,'matplotlib':matplotlib.__version__},
    }
    write_json(out/'statistics.json',stats)
    pd.DataFrame([{'population':'historical common-success49','n':49,'gpt_mean_pct':g.mean(),
                  'evo_mean_pct':e.mean(),'gpt_median_pct':np.median(g),'evo_median_pct':np.median(e),
                  'paired_mean_pp':d.mean(),'paired_median_pp':np.median(d),'cluster_ci_low_pp':ci[0],
                  'cluster_ci_high_pp':ci[1],'gpt_win':int((d>0).sum()),'evo_win':int((d<0).sum()),'tie':int((d==0).sum())}]).to_csv(out/'paper_table49.csv',index=False)
    fig,ax=plt.subplots(figsize=(6.3,5.3))
    unique=paired.groupby(['evosuite_mutation_coverage','gpt_mutation_coverage']).size().reset_index(name='count')
    ax.scatter(unique.evosuite_mutation_coverage,unique.gpt_mutation_coverage,s=30+18*unique['count'],alpha=.75,color='#24607d',edgecolor='white')
    ax.plot([0,100],[0,100],color='#555555',linestyle='--',linewidth=1)
    ax.set(xlim=(-3,103),ylim=(-3,103),xlabel='EvoSuite E0 mutation score (%) — assertions off',
           ylabel='GPT G0 mutation score (%)',title='Same 49 historical build-success classes\n39 GPT higher · 4 E0 higher · 6 ties')
    ax.grid(alpha=.18);fig.tight_layout()
    fig.savefig(out/'paired49_scatter.png',dpi=180);fig.savefig(out/'paired49_scatter.svg');plt.close(fig)
    paragraph=(f'To address survivor-population mismatch, we additionally compared mutation scores on the 49 focal classes '
               f'for which both original pipelines met the reported build gate (15 repositories, all Maven). '
               f'GPT-4o-mini and EvoSuite had mean mutation scores of {g.mean():.2f}% and {e.mean():.2f}%, '
               f'and medians of {np.median(g):.2f}% and {np.median(e):.2f}%, respectively. '
               f'The mean within-class difference was {d.mean():.2f} percentage points '
               f'(95% whole-repository percentile bootstrap interval [{ci[0]:.2f}, {ci[1]:.2f}]; '
               f'20,000 resamples), and the median within-class difference was {np.median(d):.2f} points. '
               f'GPT scored higher on {int((d>0).sum())} pairs, lower on {int((d<0).sum())}, and equally on {int((d==0).sum())}. '
               'This post-review conditional analysis removes the mismatch between the two survivor sets, '
               'but it remains a comparison with the evaluated assertions-disabled EvoSuite configuration. '
               'It does not establish superiority over assertion-enabled EvoSuite or performance across all 300 classes.')
    (out/'paper_insert_en.md').write_text('# Proposed Results insertion (not yet integrated)\n\n'+paragraph+'\n\n'
        'Methods: Resample the 15 represented repositories with replacement, retain every paired class in each sampled repository, '
        'and recompute the class-weighted paired mean as total paired differences divided by total sampled classes. '
        'Use percentile bounds, seed 20261023, and 20,000 draws. Keep RQ1–RQ3 inputs unchanged.\n',encoding='utf-8')
    tex=('\\begin{table}[t]\n\\caption{Paired mutation scores on the 49 historical common-build-success classes. '
         'EvoSuite E0 uses assertions disabled. Scores are percentages; differences are percentage points.}\n'
         '\\label{tab:paired49}\\centering\n\\begin{tabular}{lrr}\n\\hline\nStatistic & GPT & EvoSuite E0\\\\\n\\hline\n'
         f'Mean & {g.mean():.2f} & {e.mean():.2f}\\\\\nMedian & {np.median(g):.2f} & {np.median(e):.2f}\\\\\n'
         '\\hline\n\\end{tabular}\n\\par\\smallskip\n'
         f'Paired mean difference: {d.mean():.2f} pp; repository-bootstrap 95\\% CI [{ci[0]:.2f}, {ci[1]:.2f}]. '
         f'Paired median difference: {np.median(d):.2f} pp. GPT higher/lower/tied: 39/4/6.\n\\end{{table}}\n')
    (out/'paper_table49.tex').write_text(tex,encoding='utf-8')
    summary=f'''# Báo cáo analytics49: so sánh trên cùng class

## Kết quả

Đã phân tích lại dữ liệu submitted G0/E0 trên đúng **49 class thuộc15 repositories, toàn Maven**. Đây là analytics; không sinh tests hay chạy Maven/Gradle/PIT mới.

| Đại lượng | GPT G0 | EvoSuite E0 |
| --- | --- | --- |
| Mean mutation score | {g.mean():.2f}% | {e.mean():.2f}% |
| Median mutation score | {np.median(g):.2f}% | {np.median(e):.2f}% |

- Mean paired difference GPT−E0: **+{d.mean():.2f} điểm phần trăm**.
- Median của49 paired differences: **{np.median(d):.2f}pp**, không phải hiệu hai medians.
-95% repository-bootstrap CI cho mean difference: **[{ci[0]:.2f}, {ci[1]:.2f}]pp**;20.000 draws, seed20261023. Đây là CI bổ sung sau review, không phải CI của paper gốc.
- GPT cao hơn/thấp hơn/bằng E0: **{int((d>0).sum())}/{int((d<0).sum())}/{int((d==0).sum())}**.
- Trung bình khi mỗi repository có trọng số bằng nhau: {stats['repository_equal_mean_difference_pp']:.2f}pp; là estimand sensitivity khác, không thay mean theo class.
- Loại từng repository một: mean difference còn từ {loo.mean_difference_pp.min():.2f} đến {loo.mean_difference_pp.max():.2f}pp. Đây là diagnostic về ảnh hưởng từng repository, không phải CI mới.

## Phân tích này làm rõ tính công bằng đến đâu?

So sánh median66,67% trên61 GPT survivors với median8,11% trên158 E0 survivors sử dụng hai quần thể khác nhau. Bảng49 ghép đúng cùng class, nên giải quyết survivor-population mismatch mà R1.2/R2.3 nêu. Kết quả trong cohort này vẫn nghiêng về GPT theo các summaries trên.

**Chưa giải quyết oracle-configuration fairness:** E0 vẫn tắt assertions. Không được viết rằng GPT nói chung mạnh hơn EvoSuite chuẩn, rằng bật assertions không ảnh hưởng, hoặc rằng R2.1 đã đóng. Cũng chưa chứng nhận các suite đều pass dựa trên raw XML/PIT: eligibility ở đây giữ đúng historical build/process gate. Validity audit thiếu/chưa làm được nêu rõ thay vì tự đổi gate.

49 class là subset đã được chọn bởi kết quả thành công của cả hai pipeline; không đại diện buildability toàn300, không có Gradle và không chứng minh hiệu ứng nhân quả do generator. CI dùng15 clusters có giới hạn precision/coverage; không biến thành confirmatory NI claim.

## Bối cảnh whole-sample và RQ1–RQ3

Historical strict300 có mean difference+{strict.mean():.2f}pp, GPT higher/lower/tied={int((strict>0).sum())}/{int((strict<0).sum())}/{int((strict==0).sum())};130 cặp cảhai không build. Trên cohort49 không còn joint-build-failure pairs, nhưng vẫn có6 ties. Hai tập trả lời hai câu hỏi khác nhau; không thay strict300 bằng49.

RQ1 vẫn61 keys, RQ2 vẫn45, RQ3 vẫn300 và61 build success. Các input được xuất riêng từ frozen full300, không lấy từ paired49. Không tính lại hoặc thay quyết định RQ1–RQ3 trong bước này.

## Audit và backup

- Chỉ đọc inputs từ `../backup/original/`;585 original/source/artifact files đã được backup trước execution.
- `../audit/events.jsonl`: chuỗi event có timestamp UTC, hashes nối tiếp; command start/end, exit code và stdout/stderr. Đây là log kiểm chứng trong workspace, không phải kho lưu trữ chống sửa bởi bên ngoài.
- `../audit/protected_manifest.json`: vị trí original/backup và hash từng file.
- `../protocol.json`: scope, selection, seed và analysis rules; outcomes cũ đã được biết trước, không giả danh preregistration.
- `paired49_artifact_provenance.csv`: provenance và hashes của{len(evidence)} generated artifacts thuộc49 cặp.
- `statistics.json`, `paired49.csv`, `repository_summary.csv`, bootstrap draws và leave-one-out: kết quả có thể tái tính.
- `paper_insert_en.md` và `paper_table49.tex`: đề xuất để tích hợp sau review, **chưa sửa paper cũ**.

## Trạng thái reviewer và bước tiếp theo

| Point | Trạng thái trong lượt này |
| --- | --- |
| R1.2/R1.12 phần paired49 | Analytics hoàn tất; chưa tích hợp manuscript |
| R2.3 | Có49 và descriptive context300; không tạo NI test mới |
| R2.6 | Có repository sensitivity cho49; full-study clustering task riêng |
| R2.1 assertions | Chưa xử lý bằng thí nghiệm mới; vẫn mở |
| R1.7/R2.5 repeats | Chưa chạy; không thay bằng bootstrap |

Tiếp theo có thể rà raw validity evidence của49 và chuẩn bị patch EvoSuite trong bản sao riêng. Mọi sửa code phải gắn reviewer point, có backup trước edit và diff; không đụng original scripts/paper. Không nhập kết quả của các lần hiệu chỉnh trước vào bảng49 này.
'''
    (out/'BAO_CAO_ANALYTICS_49.md').write_text(summary.replace('\n+-95','\n+- 95'),encoding='utf-8')
    write_json(out/'output_manifest.json',{p.name:digest(p) for p in sorted(out.iterdir()) if p.is_file()})
    print(json.dumps({k:stats[k] for k in ['n','repositories','gpt_mean','evo_mean','paired_mean_difference_pp',
                                          'cluster_percentile_95ci_mean_difference_pp','gpt_wins','evo_wins','ties',
                                          'artifact_files_in_paired49']},indent=2))


if __name__=='__main__':
    main()
