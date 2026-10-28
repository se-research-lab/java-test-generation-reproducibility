"""Inventory remaining original reports without inferring arm ownership from filenames alone."""
import csv
import json
import re
import shutil
import sys
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET

BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE))
import audit


def readcsv(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))


def main():
    out=BASE/'evo_patch/reports/raw49';out.mkdir(exist_ok=False)
    copied=[]
    def archive(path):
        if not path.is_file():return None
        assert path.resolve().is_relative_to(audit.ROOT)
        rel=path.relative_to(audit.ROOT)
        dest=BASE/'evo_patch/artifacts/raw49'/rel
        if not dest.exists():
            h=audit.sha(path);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest)
            assert audit.sha(dest)==h==audit.sha(path)
            copied.append({'source':str(path),'copy':str(dest.relative_to(BASE)),'sha256':h,'bytes':path.stat().st_size})
        return dest
    pairs=readcsv(BASE/'outputs/paired49.csv')
    gm=readcsv(BASE/'backup/original/scripts_v2/results/runs/full300_merged_20260724_paper/generated_tests_manifest.csv')
    rows=[];pools=[];xmls=[]
    for pair in pairs:
        recs=[r for r in gm if r['class_key']==pair['class_key']]
        assert len(recs)==2 and {r['arm'] for r in recs}=={'gpt','evosuite'}
        g=next(r for r in recs if r['arm']=='gpt')
        original=Path(g['original_source_path'])
        sandbox=original.parents[2]
        assert sandbox.parent.name==g['source_run_id']
        module=sandbox/'compiledrepos'/pair['repo_id']/pair['module']
        target=module/'target'
        log=audit.RUN/'class_logs'/g['source_run_id']/f"{int(g['source_run_sample_index']):03d}_{pair['repo_id']}_{pair['focal_class']}.stdout.log"
        log_copy=archive(log)
        text=log_copy.read_text(encoding='utf-8',errors='replace') if log_copy else ''
        gpos=text.find('STARTING gpt-4o-mini');epos=text.find('STARTING evosuite')
        if gpos<0:gpos=text.find("STARTING 'gpt-4o-mini")
        if epos<0:epos=text.find("STARTING 'evosuite")
        order='E_before_G' if epos>=0 and gpos>epos else 'not_established'
        # Arm-named summary CSV files retain some arm provenance; target reports do not.
        summaries=[]
        if original.parent.is_dir():
            for p in original.parent.glob('TestClasses_*.csv'):
                cp=archive(p)
                summaries.append(str(cp.relative_to(BASE)))
        tests=[]
        sr=target/'surefire-reports'
        if sr.is_dir():
            for p in sorted(sr.glob('TEST-*.xml')):
                cp=archive(p)
                try:
                    root=ET.parse(cp).getroot()
                    suites=[root] if root.tag=='testsuite' else list(root.iter('testsuite'))
                    counts={k:sum(int(x.attrib.get(k,'0')) for x in suites) for k in ['tests','failures','errors','skipped']}
                    entry={'class_key':pair['class_key'],'report':str(cp.relative_to(BASE)),
                           'suite_names':[x.attrib.get('name','') for x in suites],**counts,
                           'arm_attribution':'not certified; shared target after sequential arms',
                           'parse_status':'ok'}
                except Exception as exc:entry={'class_key':pair['class_key'],'report':str(cp.relative_to(BASE)),'parse_status':type(exc).__name__}
                tests.append(entry);xmls.append(entry)
        pit=target/'pit-reports/mutations.csv';pc=archive(pit)
        counts=Counter();focals=Counter()
        if pc:
            with pc.open(encoding='utf-8-sig',newline='') as f:
                for record in csv.reader(f):
                    if len(record)>=7:
                        counts[record[5]]+=1;focals[record[1]]+=1
            pools.append({'class_key':pair['class_key'],'report':str(pc.relative_to(BASE)),
                          'rows':sum(counts.values()),'statuses':dict(counts),'mutated_classes':dict(focals),
                          'arm_attribution':'not certified; do not assign same pool to both arms'})
        for p in [target/'site/jacoco/jacoco.csv',target/'site/jacoco/jacoco.xml']:
            archive(p)
        rows.append({'class_key':pair['class_key'],'repo_id':pair['repo_id'],'sandbox':str(sandbox),
                     'sandbox_exists':sandbox.is_dir(),'class_log_exists':bool(log_copy),
                     'arm_order_in_log':order,'arm_summary_csvs':len(summaries),
                     'surefire_xml_files':len(tests),'remaining_pit_csv':bool(pc),
                     'remaining_pit_rows':sum(counts.values()),
                     'observed_xml_failure_or_error':any(x.get('failures',0)+x.get('errors',0)>0 for x in tests),
                     'both_arms_raw_validity_certified':False})
    for name,data in [('inventory.csv',rows)]:
        with (out/name).open('w',encoding='utf-8-sig',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(data[0]));writer.writeheader();writer.writerows(data)
    for name,data in [('copied_evidence.json',copied),('remaining_pit_pools.json',pools),('remaining_surefire.json',xmls)]:
        (out/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    summary={'n':len(rows),'sandboxes_found':sum(r['sandbox_exists'] for r in rows),
             'logs_found':sum(r['class_log_exists'] for r in rows),
             'E_before_G_logs':sum(r['arm_order_in_log']=='E_before_G' for r in rows),
             'classes_with_surefire':sum(r['surefire_xml_files']>0 for r in rows),
             'classes_with_remaining_PIT':sum(r['remaining_pit_csv'] for r in rows),
             'classes_with_remaining_XML_failure_or_error':sum(r['observed_xml_failure_or_error'] for r in rows),
             'raw_both_arm_validity_certified':0,'files_archived':len(copied),
             'conclusion':'Remaining target reports cannot certify both arm-specific executions. No eligibility/score modified.',
             'limits':'Inventory anchored to49 historical sandboxes; not an exhaustive search of all archives; PIT counts unassigned to arm.'}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    audit.log('RAW49_EVIDENCE_ARCHIVED',summary=summary,manifest='evo_patch/reports/raw49/copied_evidence.json',
              sha256=audit.sha(out/'copied_evidence.json'))
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
