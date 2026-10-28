"""Extract focal mutant counts from archived raw reports; no arm attribution inferred."""
import csv,json,re,shutil,statistics,sys
from collections import Counter
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));import audit

def read(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def main():
    stage=BASE/'evo_patch';raw=stage/'reports/raw49'
    out=stage/'reports/focal_counts49';out.mkdir(exist_ok=False)
    pairs=read(BASE/'outputs/paired49.csv');inv={r['class_key']:r for r in read(raw/'inventory.csv')}
    pools={r['class_key']:r for r in json.loads((raw/'remaining_pit_pools.json').read_text(encoding='utf-8'))}
    rows=[];copies=[]
    for p in pairs:
        item=inv[p['class_key']];pool=pools[p['class_key']]
        source=Path(item['sandbox'])/'compiledrepos'/p['repo_id']/p['focal_path']
        assert source.is_file(),str(source)
        rel=source.relative_to(audit.ROOT);dest=stage/'artifacts/focal_sources49'/rel
        dest.parent.mkdir(parents=True,exist_ok=True);assert not dest.exists()
        h=audit.sha(source);shutil.copy2(source,dest);assert h==audit.sha(dest)==audit.sha(source)
        copies.append({'source':str(source),'copy':str(dest.relative_to(BASE)),'sha256':h})
        content=dest.read_text(encoding='utf-8-sig',errors='replace')
        package=re.search(r'^\s*package\s+([A-Za-z_$][\w.$]*)\s*;',content,re.M)
        package=package.group(1) if package else ''
        fqcn=(package+'.' if package else '')+p['focal_class']
        with (BASE/pool['report']).open(encoding='utf-8-sig',newline='') as f:allrows=list(csv.reader(f))
        assert all(len(x)==7 for x in allrows)
        # Mirrors the existing reader's SourceFile + package grouping, including inner classes.
        selected=[x for x in allrows if x[0].replace('.java','')==p['focal_class']
                  and (x[1].rsplit('.',1)[0] if '.' in x[1] else '')==package]
        counts=Counter(x[5] for x in selected);n=len(selected)
        score=round(100*counts['KILLED']/n,2) if n else None
        rows.append({'class_key':p['class_key'],'focal_fqcn_from_remaining_source':fqcn,
            'remaining_source_sha256':h,'remaining_PIT_sha256':audit.sha(BASE/pool['report']),
            'module_mutant_rows':len(allrows),'focal_source_group_mutant_rows':n,
            'exact_top_level_fqcn_rows':sum(x[1]==fqcn for x in allrows),
            'KILLED':counts['KILLED'],'SURVIVED':counts['SURVIVED'],'NO_COVERAGE':counts['NO_COVERAGE'],
            'other_status_counts':json.dumps({k:v for k,v in counts.items() if k not in ['KILLED','SURVIVED','NO_COVERAGE']},sort_keys=True),
            'recomputed_remaining_score_percent':score,
            'matches_archived_G0_rounded_score':score==float(p['gpt_mutation_coverage']) if n else False,
            'matches_archived_E0_rounded_score':score==float(p['evosuite_mutation_coverage']) if n else False,
            'arm_attribution':'UNVERIFIED; numerical agreement does not certify provenance',
            'source_provenance':'remaining sandbox snapshot; not proof of byte-identical executed source'})
    with (out/'focal_mutant_counts.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    ns=[r['focal_source_group_mutant_rows'] for r in rows]
    summary={'n':len(rows),'focal_groups_nonempty':sum(n>0 for n in ns),'min':min(ns),
        'median':statistics.median(ns),'max':max(ns),'mean':statistics.mean(ns),
        'matches_G0_rounded_scores':sum(r['matches_archived_G0_rounded_score'] for r in rows),
        'matches_E0_rounded_scores':sum(r['matches_archived_E0_rounded_score'] for r in rows),
        'module_counts_are_not_focal_counts':True,'raw_arm_provenance_certified':False,
        'mutant_identity_pairing_certified':False,'original_metrics_changed':False,
        'use':'internal audit of remaining reports only; not a certified two-arm distribution for the manuscript'}
    for name,obj in [('summary.json',summary),('source_copies.json',copies)]:
        (out/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    audit.log('FOCAL49_RAW_DIAGNOSTIC',summary=summary,source_copies_sha256=audit.sha(out/'source_copies.json'))
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
