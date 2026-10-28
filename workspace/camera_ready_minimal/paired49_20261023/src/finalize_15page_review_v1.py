"""Finalize the 15-page review draft with user-confirmed metadata, not a submission."""
import json,re,shutil,sys,zipfile
from datetime import datetime,timezone
from pathlib import Path
import fitz
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));import audit
REV=BASE/'manuscript_revision_v2_15pages';SRC=REV/'source';V1=BASE/'manuscript_revision_v1/source';OLD=BASE.parents[1]/'paper'
def read(p):return p.read_text(encoding='utf-8')
def dump(p,x):
    with p.open('x',encoding='utf-8') as f:json.dump(x,f,ensure_ascii=False,indent=2);f.write('\n')
def rq(s):return s[s.index('\\begin{itemize}'):s.index('\\end{itemize}')+len('\\end{itemize}')]
def tables(root):
    found=[]
    for p in sorted(root.rglob('*.tex')):
        for t in re.findall(r'\\begin\{table\}.*?\\end\{table\}',read(p),re.S):found.append(t)
    return found

def main():
    b=REV/'build_03';build=json.loads(read(b/'build_summary.json'));assert build['returncode']==0 and build['pages']==15
    for rel,h in build['input_hashes'].items():assert audit.sha(SRC/rel)==h,rel
    for row in json.loads(read(BASE/'audit/final49_static_registry_v1.json'))['files']:assert audit.sha(BASE/row['path'])==row['sha256'],row['path']
    controls={
        'five_RQ_wordings_exact_original':rq(read(SRC/'sections/01_introduction.tex'))==rq(read(OLD/'sections/01_introduction.tex')),
        'five_entire_tables_exact_sealed_v1':tables(SRC)==tables(V1) and len(tables(SRC))==5,
        'Methods_Results_E1_Abstract_byte_exact_v1':all(audit.sha(SRC/'sections'/n)==audit.sha(V1/'sections'/n) for n in ['00_abstract.tex','03_method.tex','04_results.tex','04a_supplement.tex']),
        'references_class_bst_exact_v1':all(audit.sha(SRC/n)==audit.sha(V1/n) for n in ['references.tex','references.bib','llncs.cls','splncs04.bst']),
        'main_body_preamble_exact_except_author_metadata':read(SRC/'main.tex').split('\\author{')[0]==read(V1/'main.tex').split('\\author{')[0] and read(SRC/'main.tex').split('\\maketitle',1)[1]==read(V1/'main.tex').split('\\maketitle',1)[1],
        'all_compiled_inputs_current':True,
        'six_authors_two_corresponding':all(name in read(SRC/'main.tex') for name in ['Truong Dan Huy','Vuong Quoc Khanh','Tran Minh Quy','Le Tran Anh Khoa','Tran Bich Tram','Le Thi Quynh Chi']) and 'Corresponding authors: Truong Dan Huy and Le Thi Quynh Chi' in read(SRC/'main.tex'),
        'total_pages_including_references_at_most15':build['pages']<=15,
        'no_experiment_or_GPT_data_edits':True,
    }
    assert all(controls.values()),controls
    doc=fitz.open(b/'main.pdf');text='\n'.join(p.get_text() for p in doc)
    for token in ['Truong Dan Huy','Le Thi Quynh Chi','FPT University','chiltq6@fe.edu.vn','truongdanhuyak@gmail.com','50.41','77.78','26.99']:assert token in text,token
    assert 'Anonymous Author(s)' not in text and '??' not in text and '\ufffd' not in text
    refs=[i+1 for i,p in enumerate(doc) if re.search(r'^References\s*$',p.get_text(),re.M)]
    assert refs and refs[0]==14 and len(doc)==15
    render=json.loads(read(b/'rendered/render_manifest.json'));older=json.loads(read(REV/'build_02/rendered/render_manifest.json'))
    assert render['PDF_sha256']==build['PDF_sha256']==audit.sha(b/'main.pdf')
    changed=[i for i in range(1,16) if render['rendered_PNGs'][f'page_{i:02}.png']!=older['rendered_PNGs'][f'page_{i:02}.png']]
    assert changed==[1,2,3,13]
    stderr=read(b/'tectonic.stderr.txt');log=read(b/'main.log') if (b/'main.log').exists() else ''
    assert not re.search('Overfull|Missing character|undefined reference',stderr+'\n'+log,re.I)
    qa={'status':'PASS','PDF_sha256':build['PDF_sha256'],'total_pages':15,'references_begin_page':14,
        'all15pages_reviewed':'Root build02 contacts1-15+full1-7; independent reviewer full8-15; latestbuild03 fullchanged1,2,3,13 reviewedroot',
        'latest_changed_pages':changed,'remaining_pages_byte_identical_rendered_PNG':True,
        'visual_findings':'No clipping/overlap/overflow; Table2 andTable5 dense but readable; reference25 complete',
        'class_fonts_margins_or_spacing_hacks':False,'layout_changed_only_by_content_and_author_metadata':True}
    dump(REV/'visual_QA_final.json',qa)
    meta=json.loads(read(REV/'author_metadata_v2.json'));assert len(meta['authors_in_order'])==6 and meta['funding']=='none' and meta['conflicts_of_interest']=='none'
    final={'status':'PASS_15PAGE_REVIEW_DRAFT','timestamp_utc':datetime.now(timezone.utc).isoformat(),'controls':controls,'user_page_limit_total':15,'PDF_pages':len(doc),'references_begin_page':refs[0],'PDF_sha256':build['PDF_sha256'],'compiled_source_hashes':build['input_hashes'],'author_metadata_sha256':audit.sha(REV/'author_metadata_v2.json'),'funding_COI_user_confirmed':True,'artifact_URL':'not finalized by user','original_static_registry_unchanged':True,'submission_ready':False,'open_items':['artifact public access link','E1 runtime compatibility measurement policy not yet whole49','repeated subset not executed','practical5pp margin rationale not validated','pre-pilot analytical lock not certified'],'prior_preservation_controls_note':'preservation_controls.json records pre-author-metadata condensation stage; this final_validation supersedes its main.tex identical flag'}
    dump(REV/'final_validation.json',final)
    readme=REV/'README.md'
    with readme.open('x',encoding='utf-8') as f:f.write('''# Bản sửa15trang tổng: review draft

PDF15trang bao gồm references(trang14–15). Giữ class/font/margins/spacing; rút1033từ văn xuôi lặp. NămRQ, cả5bảng, Methods/Results/E1/Abstract và references giữ nguyên bảnv1 đã niêm phong. GPT RQ1–3 vẫn61/45/300, không tái đo.

Đã điền6tác giả theo thông tin người dùng; hai corresponding authors Truong Dan Huy và Le Thi Quynh Chi. Không funding/COI đã được người dùng xác nhận. Artifact URL chưa chốt: chưa phải bản sẵn sàng nộp.

File review: output/pdf/FISAT2026_revision_15pages_draft.pdf; source package output/FISAT2026_revision_15pages_sources.zip. final_validation.json là control hiện hành sau metadata; preservation_controls.json chỉ là snapshot trước metadata. visual_QA_final.json ghi kiểm tất cả trang.

Không sửa paper/, scripts_v2/, v1 hoặc dữ liệu đã nộp. Backups/diffs/SHA và audit ở workspace. Tám ca E1 đang được chẩn đoán riêng, không ghép điểm diagnostic vào E1 và không kể trial/debug trong paper. Repeated subset chưa chạy, practical5pp và pre-pilot lock vẫn có giới hạn đã nêu trong manuscript.

Build với conference-supplied LLNCS class và Tectonic0.17.0; lệnh/inputhash tại build_03/build_summary.json. Package không kèm cache/rawlogs lớn. Chưa gửi/publish bên ngoài.
''')
    output=REV/'output';(output/'pdf').mkdir(parents=True,exist_ok=False)
    pdf=output/'pdf/FISAT2026_revision_15pages_draft.pdf'
    with pdf.open('xb') as f:f.write((b/'main.pdf').read_bytes())
    members=[]
    for p in sorted(SRC.rglob('*')):
        if p.is_file() and p.suffix in {'.tex','.cls','.bst','.bib'}:members.append((p,'source/'+p.relative_to(SRC).as_posix()))
    for rel in ['README.md','final_validation.json','visual_QA_final.json','author_metadata_v2.json','condensation_change_log.md','text_condensation.diff','source_copy_backup_manifest.json']:
        members.append((REV/rel,rel))
    members.append((pdf,'pdf/'+pdf.name))
    package=output/'FISAT2026_revision_15pages_sources.zip'
    with zipfile.ZipFile(package,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p,name in members:z.write(p,name)
    with zipfile.ZipFile(package) as z:
        assert z.testzip() is None
        for p,name in members:assert z.read(name)==p.read_bytes(),name
    dump(output/'release_manifest.json',{'status':'REVIEW_DRAFT_ONLY','PDF':{'path':str(pdf),'sha256':audit.sha(pdf),'pages':15},'ZIP':{'path':str(package),'sha256':audit.sha(package),'bytes':package.stat().st_size},'members':[{'name':name,'sha256':audit.sha(p)} for p,name in members],'open_artifact_URL':True,'original_or_experiment_files_modified':False})
    audit.log('MANUSCRIPT_15PAGE_REVIEW_PACKAGE_COMPLETE',pages=15,references_begin=14,PDF_sha256=audit.sha(pdf),ZIP_sha256=audit.sha(package),validation_sha256=audit.sha(REV/'final_validation.json'),metadata_sha256=audit.sha(REV/'author_metadata_v2.json'),original_or_experiment_modified=False,submission_ready=False)
    print(json.dumps({'status':final['status'],'pages':15,'references_begin':14,'authors':6,'corresponding_authors':2,'PDF_sha256':audit.sha(pdf),'ZIP_bytes':package.stat().st_size,'all_controls':'PASS','submission_ready':False},indent=2))
if __name__=='__main__':main()
