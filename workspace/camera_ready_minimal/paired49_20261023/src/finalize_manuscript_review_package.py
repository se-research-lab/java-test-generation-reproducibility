"""Seal the reviewer draft after visual review; no Java, API, or original edits."""
import json,re,shutil,sys,zipfile
from datetime import datetime,timezone
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE));import audit
REV=BASE/'manuscript_revision_v1';SRC=REV/'source';ORIG=BASE.parents[1]/'paper'
def read(p):return p.read_text(encoding='utf-8')
def dump(p,obj):
    with p.open('x',encoding='utf-8',newline='\n') as f:json.dump(obj,f,ensure_ascii=False,indent=2);f.write('\n')
def tabbody(text,label):
    pos=text.index('\\label{'+label+'}')
    start=text.rfind('\\begin{table}',0,pos)
    end=text.index('\\end{table}',pos)
    block=text[start:end]
    a=block.index('\\begin{tabularx}')
    return block[a:block.index('\\end{tabularx}',a)+len('\\end{tabularx}')]
def rqblock(text):
    a=text.index('\\begin{itemize}');b=text.index('\\end{itemize}',a)
    return text[a:b+len('\\end{itemize}')]
def evidence(text):
    lines=[s for s in text.splitlines() if re.match(r'^RQ[1-5] &',s)]
    assert len(lines)==5
    return [[x.strip() for x in s.split('&')[:5]] for s in lines]
def main():
    build=REV/'build_03';summary=json.loads(read(build/'build_summary.json'))
    assert summary['returncode']==0
    for rel,h in summary['input_hashes'].items():assert audit.sha(SRC/rel)==h,rel
    controls={
        'all5_RQ_wordings_exact':rqblock(read(SRC/'sections/01_introduction.tex'))==rqblock(read(ORIG/'sections/01_introduction.tex')),
        'sampling_funnel_numeric_table_exact':tabbody(read(SRC/'sections/03_method.tex'),'tab:sample')==tabbody(read(ORIG/'sections/03_method.tex'),'tab:sample'),
        'historical_metrics_table_body_exact':tabbody(read(SRC/'sections/04_results.tex'),'tab:metrics')==tabbody(read(ORIG/'sections/04_results.tex'),'tab:metrics'),
        'RQ_evidence_numeric_columns_exact':evidence(read(SRC/'sections/04_results.tex'))==evidence(read(ORIG/'sections/04_results.tex')),
        'conference_class_unchanged':audit.sha(SRC/'llncs.cls')==audit.sha(ORIG/'llncs.cls'),
        'all_compiled_source_hashes_match_current':True,
        'E1_results_inserted':True,
    }
    assert all(controls.values()),controls
    stats=json.loads(read(BASE/'outputs/e49_final_v2/statistics.json'))
    assert stats['n']==49 and stats['GPT_API_calls']==0 and stats['RQ123_membership_or_scores_updated'] is False
    assert stats['G0_minus_E1']['G_higher']==18 and stats['G0_minus_E1']['E_higher']==23 and stats['G0_minus_E1']['ties']==8
    assert stats['E1_counts']['measurement_evidence_complete']==41
    e1=read(SRC/'sections/04a_supplement.tex')
    for token in ['50.41','58.44','17.63','8.03','32.78','[-4.80, 26.99]','41/49','77.78']:assert token in e1,token
    audit.verify_chain()
    protected=json.loads(read(BASE/'audit/protected_manifest.json'))
    assert all(audit.sha(r['source'])==r['sha256']==audit.sha(r['backup']) for r in protected)
    render=json.loads(read(build/'rendered/render_manifest.json'))
    assert render['PDF_sha256']==audit.sha(build/'main.pdf')==summary['PDF_sha256']
    assert len(render['pages'])==17
    assert not any(p['has_replacement_character'] or p['has_undefined_reference'] for p in render['pages'])
    old=json.loads(read(REV/'build_02/rendered/render_manifest.json'))
    different=[p for p in range(1,18) if render['rendered_PNGs'][f'page_{p:02}.png']!=old['rendered_PNGs'][f'page_{p:02}.png']]
    assert different==[8,12],different
    qa={
        'status':'PASS','PDF_sha256':summary['PDF_sha256'],'pages':17,
        'latest_changed_pages_reviewed_full_resolution':[8,12],
        'other_pages_identical_to_previously_visually_reviewed_build02':[p for p in range(1,18) if p not in different],
        'build02_review':'Root contacts1-17 and individual4,7,8,9; independent reviewer individual10-17; no clipping/overlap/overflow',
        'latest_review':'Pages8/12 inspected; readable, no clipping/overlap. Table5 header tight but legible.',
        'font_and_class_changed_to_fit':False,
        'page_allowance_confirmed':False,
        'submission_metadata_complete':False,
        'renderer':'PyMuPDF; Poppler unavailable on PATH',
        'note':'Visual/layout pass does not close scientific or metadata issues.'
    }
    dump(REV/'visual_QA_final.json',qa)
    readme=REV/'README.md';backup=REV/'backup_final_package01/README.md'
    backup.parent.mkdir(exist_ok=False);before=audit.sha(readme);shutil.copy2(readme,backup);assert audit.sha(backup)==before
    readme.write_text('''# Bản sửa riêng cho camera-ready: draft để rà soát

Nguồn source/ được sao chép riêng từ paper/ phục dựng theo PDF đã nộp. Không sửa paper/, scripts_v2/ hoặc PDF đã nộp. source_backup_manifest.json và các thư mục backup_* giữ các phiên bản trước sửa; audit ledger ghi before/after hashes.

## Kết quả và file dùng để review

- E1 đã hoàn tất49/49 trên đúng fixed49 Maven; không gọi GPT mới. Mean G0/E0/E1=58,44/17,63/50,41%; mean G0−E1=8,03pp, repo CI[−4,80;26,99]. Không suy GPT vượt trội ổn định hoặc NI300 từ supplement này.
- 41/49 suite/report evidence đầy đủ;8 ca còn execution/report issues, không tự động coi cả8 là điểm0. Case thiếu XML vẫn ghi PIT77,78%.
- Năm RQ giữ nguyên; số liệu GPT và các numeric columns của bảng lịch sử không đổi. RQ1/2/3 giữ61/45/300.
- PDF dùng để review: output/pdf/FISAT2026_revision_draft.pdf (byte-identical build_03/main.pdf),17 trang, references bắt đầu15.
- Source package: output/FISAT2026_revision_review_sources.zip; final_validation.json, visual_QA_final.json và output/release_manifest.json giữ control/hash.
- Báo cáo chính: ../BAO_CAO_CHOT_49_VA_KE_HOACH_CAMERA_READY.md. Ma trận reviewer: ../REVIEWER_TASK_MATRIX_FINAL49.md.

## Chưa sẵn sàng nộp

Còn mở:8 E1 execution cases; repeated subset chưa chạy; practical rationale5pp chưa có căn cứ trực tiếp; pre-pilot analytical lock chưa chứng nhận; budgets mới accounting, chưa equalized. Tên tác giả/affiliation/artifact URL vẫn ẩn danh; disclosure/funding/COI cần tác giả kiểm tra.17 trang tổng chưa được xác nhận phù hợp track/page allowance.

Không đưa lịch sử trial/debug vào manuscript. Không trộn49E1+251E0; không đổi P/C, prompt, gate, shared Gradle/JUnit/PIT hoặc mẫu GPT để giữ kết luận cũ.

## Build

Source dùng conference-supplied llncs.cls đã giữ nguyên. Bản dựng hiện tại dùng Tectonic0.17.0 và workspace-owned cached TeX bundle, lệnh đầy đủ trong build_03/build_summary.json. Có thể build main.tex với toolchain LaTeX tương thích; package không kèm cache lớn hoặc experimental raw archives. Raw evidence và audit nằm ngoài ZIP tại workspace phân tích.
''',encoding='utf-8')
    audit.log('FILE_REVISION',path=readme.relative_to(BASE).as_posix(),before_sha256=before,after_sha256=audit.sha(readme),backup=backup.relative_to(BASE).as_posix(),reason='Update stale draft README after completed E1 and final visual review; no manuscript or experiment edit')
    output=REV/'output';(output/'pdf').mkdir(parents=True,exist_ok=False)
    dest=output/'pdf/FISAT2026_revision_draft.pdf'
    with dest.open('xb') as f:f.write((build/'main.pdf').read_bytes())
    assert audit.sha(dest)==summary['PDF_sha256']
    final={
        'status':'PASS_FOR_REVIEW_DRAFT','timestamp_utc':datetime.now(timezone.utc).isoformat(),
        'submission_ready':False,'controls':controls,'protected_original_and_backup_pairs':len(protected),
        'all_original_backup_bytes_match':True,
        'PDF_sha256':audit.sha(dest),'pages':17,'source_inputs':summary['input_hashes'],
        'E1_statistics_sha256':audit.sha(BASE/'outputs/e49_final_v2/statistics.json'),
        'E1_results49_sha256':audit.sha(BASE/'e49_driver/results49.json'),
        'E1_counts':stats['E1_counts'],
        'visual_QA_sha256':audit.sha(REV/'visual_QA_final.json'),
        'open_items':['8 E1 execution/report cases','repeated subset not performed','practical5pp rationale not validated','pre-pilot analytical lock not certified','compute not equalized','author/artifact/disclosure metadata','track page allowance'],
    }
    dump(REV/'final_validation.json',final)
    members=[]
    for p in sorted(SRC.rglob('*')):
        if p.is_file() and p.suffix in {'.tex','.cls','.bst','.bib'}:members.append((p,'source/'+p.relative_to(SRC).as_posix()))
    for rel in ['README.md','final_validation.json','visual_QA_final.json','source_backup_manifest.json','planned_text_changes.json','e1_insert_manifest.json']:
        members.append((REV/rel,rel))
    members.append((dest,'pdf/'+dest.name))
    for name in ['BAO_CAO_CHOT_49_VA_KE_HOACH_CAMERA_READY.md','REVIEWER_TASK_MATRIX_FINAL49.md']:
        members.append((BASE/name,'analysis/'+name))
    package=output/'FISAT2026_revision_review_sources.zip'
    with zipfile.ZipFile(package,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p,name in members:z.write(p,name)
    with zipfile.ZipFile(package) as z:
        assert z.testzip() is None
        for p,name in members:assert z.read(name)==p.read_bytes(),name
    release={
        'status':'REVIEW_DRAFT_ONLY','PDF':{'path':str(dest),'sha256':audit.sha(dest),'bytes':dest.stat().st_size},
        'ZIP':{'path':str(package),'sha256':audit.sha(package),'bytes':package.stat().st_size},
        'ZIP_members':[{'name':name,'sha256':audit.sha(p),'bytes':p.stat().st_size} for p,name in members],
        'includes_experiment_raw_cache':False,'original_files_changed':False,
        'reference_page_start':15,'total_pages':17,'not_submission_ready':True,
    }
    dump(output/'release_manifest.json',release)
    audit.log('FINAL49_MANUSCRIPT_REVIEW_PACKAGE_COMPLETE',PDF_sha256=audit.sha(dest),ZIP_sha256=audit.sha(package),manifest_sha256=audit.sha(output/'release_manifest.json'),validation_sha256=audit.sha(REV/'final_validation.json'),visual_QA_sha256=audit.sha(REV/'visual_QA_final.json'),original_files_changed=False,submission_ready=False)
    print(json.dumps({'status':'PASS_FOR_REVIEW_DRAFT','controls':controls,'PDF_sha256':audit.sha(dest),'pages':17,'zip_bytes':package.stat().st_size,'submission_ready':False},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
