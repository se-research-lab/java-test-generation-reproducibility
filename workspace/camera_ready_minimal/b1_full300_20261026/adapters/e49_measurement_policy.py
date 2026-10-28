"""E49 function-only copy. Load with explicit E-only bindings; no top-level side effects."""

def normalize(root):
    root = copy.deepcopy(root)
    for e in root.iter():
        if e.text is not None and (not e.text.strip()):
            e.text = None
        if e.tail is not None and (not e.tail.strip()):
            e.tail = None
    return ET.tostring(root)

def patch_pom(j, module, out, before_dep, surefire):
    path = module / 'pom.xml'
    before = path.read_text(encoding='utf-8')
    text = before
    changes = []
    root = ET.fromstring(text)
    selected = [r for r in before_dep['classpath'] if r['path'].startswith('junit/junit/')]
    assert len(selected) <= 1
    lacks = False
    if selected:
        with zipfile.ZipFile(selected[0]['absolute_path']) as z:
            assert 'org/junit/Test.class' in z.namelist(), 'JUnit4 API precondition not met'
            lacks = 'org/junit/rules/TestRule.class' not in z.namelist()
    if lacks:
        ds = [d for d in root.findall('m:dependencies/m:dependency', NS) if d.findtext('m:groupId', namespaces=NS) == 'junit' and d.findtext('m:artifactId', namespaces=NS) == 'junit']
        assert len(ds) == 1 and ds[0].findtext('m:scope', namespaces=NS) == 'test', 'Unsafe JUnit dependency scope'
        candidates = [m for m in re.finditer('<dependency\\b[^>]*>.*?</dependency>', text, re.S) if re.search('<groupId>\\s*junit\\s*</groupId>', m.group()) and re.search('<artifactId>\\s*junit\\s*</artifactId>', m.group())]
        assert len(candidates) == 1
        m = candidates[0]
        chunk = m.group()
        old = ds[0].findtext('m:version', namespaces=NS)
        if old:
            chunk2 = re.sub('<version>.*?</version>', '<version>4.13.2</version>', chunk, count=1, flags=re.S)
        else:
            chunk2 = chunk.replace('</artifactId>', '</artifactId><version>4.13.2</version>', 1)
        text = text[:m.start()] + chunk2 + text[m.end():]
        changes.append({'kind': 'test_JUnit_API', 'old_version': old, 'new_version': '4.13.2'})
    executions = surefire.findall('m:executions/m:execution', NS)
    regular = [e for e in executions if e.findtext('m:id', namespaces=NS) == 'regular-tests']
    inc = [i.text for e in regular for i in e.findall('m:configuration/m:includes/m:include', NS)]
    selector = bool(len(executions) > 1 and regular and any((v and v.startswith('/') for v in inc)))
    if selector:
        assert surefire.findtext('m:version', namespaces=NS) == '2.17' and len(regular) == 1
        selected_path = j['selected_test_fqcn'].replace('.', '/') + '.java'
        blocks = [m for m in re.finditer('<plugin\\b[^>]*>.*?</plugin>', text, re.S) if '<artifactId>maven-surefire-plugin</artifactId>' in m.group()]
        assert len(blocks) == 1
        m = blocks[0]
        chunk = m.group()
        p = ET.fromstring('<root xmlns="' + NS['m'] + '">' + chunk + '</root>')[0]
        assert p.find('m:executions', NS) is None, 'Unproven module execution shape; stop'
        addition = '<executions><execution><id>regular-tests</id><configuration><includes combine.self="override"><include>' + selected_path + '</include></includes></configuration></execution></executions>'
        text = text[:m.start()] + chunk.replace('</plugin>', addition + '</plugin>', 1) + text[m.end():]
        changes.append({'kind': 'regular_exact_relative_include', 'old_effective_includes': inc, 'new_include': selected_path})
    reverted = ET.fromstring(text)
    for change in changes:
        if change['kind'] == 'test_JUnit_API':
            d = next((d for d in reverted.findall('m:dependencies/m:dependency', NS) if d.findtext('m:groupId', namespaces=NS) == 'junit' and d.findtext('m:artifactId', namespaces=NS) == 'junit'))
            v = d.find('m:version', NS)
            if change['old_version'] is None:
                d.remove(v)
            else:
                v.text = change['old_version']
        else:
            p = next((p for p in reverted.findall('m:build/m:plugins/m:plugin', NS) if p.findtext('m:artifactId', namespaces=NS) == 'maven-surefire-plugin'))
            p.remove(p.find('m:executions', NS))
    assert normalize(reverted) == normalize(ET.fromstring(before)), 'POM semantic diff outside allowlist'
    backup = out / 'backup_before_policy/pom.xml'
    backup.parent.mkdir()
    shutil.copy2(path, backup)
    if text != before:
        path.write_text(text, encoding='utf-8')
    diff = out / 'policy_patch.diff'
    diff.write_text(''.join(difflib.unified_diff(before.splitlines(True), text.splitlines(True), fromfile='before/pom.xml', tofile='after/pom.xml')), encoding='utf-8')
    policy = {'JUnit_rule_applied': lacks, 'selector_rule_applied': selector, 'direct_JUnit_present': bool(selected), 'TestRule_missing_before': lacks, 'changes': changes, 'before_sha256': audit.sha(backup), 'after_sha256': audit.sha(path), 'diff_sha256': audit.sha(diff), 'only_allowlisted_semantic_changes': True}
    dump(out / 'policy_applied.json', policy)
    event('COPIED_POLICY_RECORDED', job_index=j['job_index'], policy=policy)
    return policy

def compare_cp(a, b, policy):
    sig = lambda rows: [(r['path'], r['sha256']) for r in rows]
    assert sig(a['compile_classpath']) == sig(b['compile_classpath']), 'Production compile closure drift'
    allowed = lambda r: r['path'].startswith('junit/junit/') or r['path'] == 'org/hamcrest/hamcrest-core/1.3/hamcrest-core-1.3.jar'
    if policy['JUnit_rule_applied']:
        assert sig([r for r in a['classpath'] if not allowed(r)]) == sig([r for r in b['classpath'] if not allowed(r)]), 'Non JUnit/Hamcrest test closure drift'
        selected = [r for r in b['classpath'] if r['path'].startswith('junit/junit/')]
        assert len(selected) == 1 and selected[0]['path'] == 'junit/junit/4.13.2/junit-4.13.2.jar'
        with zipfile.ZipFile(selected[0]['absolute_path']) as z:
            assert 'org/junit/rules/TestRule.class' in z.namelist()
        assert len([r for r in b['classpath'] if r['path'] == 'org/hamcrest/hamcrest-core/1.3/hamcrest-core-1.3.jar']) == 1, 'Expected Hamcrest1.3 transitive closure missing'
    else:
        assert sig(a['classpath']) == sig(b['classpath']), 'Unpatched test closure drift'
