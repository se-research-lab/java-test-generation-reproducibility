"""Read-only JUnit4 source inventory for frozen EvoSuite evidence.

This is a deliberately bounded Java lexical parser, not a Java compiler. It finds
@Test / @org.junit.Test annotations outside comments/literals and requires an
explicit public void, zero-argument method with a braced body. Unsupported test
shapes fail closed. Names are Java identifiers, without a test* naming rule.
No test, runner, gate, mutation score, or cohort is modified by this module.
"""
import re
import unicodedata


def _start(ch):
    return bool(ch) and (ch in '_$' or unicodedata.category(ch) in {'Lu','Ll','Lt','Lm','Lo','Nl','Sc','Pc'})


def _part(ch):
    return _start(ch) or bool(ch) and unicodedata.category(ch) in {'Mn','Mc','Nd','Cf'}


def is_java_identifier(value):
    return bool(value) and _start(value[0]) and all(_part(c) for c in value[1:])


def _tokens(source):
    """Return (token, offset) pairs; comments and literal contents cannot match."""
    out=[]; i=0; n=len(source)
    while i<n:
        c=source[i]
        if c.isspace(): i+=1; continue
        if source.startswith('//',i):
            j=source.find('\n',i+2); i=n if j<0 else j+1; continue
        if source.startswith('/*',i):
            j=source.find('*/',i+2)
            if j<0: raise ValueError('Unterminated Java block comment')
            i=j+2; continue
        if c in '\"\'':
            quote=c; start=i; i+=1
            while i<n:
                if source[i]=='\\': i+=2
                elif source[i]==quote: i+=1; break
                else: i+=1
            else: raise ValueError('Unterminated Java literal')
            out.append(('<literal>',start)); continue
        if _start(c):
            start=i; i+=1
            while i<n and _part(source[i]): i+=1
            out.append((source[start:i],start)); continue
        out.append((c,i)); i+=1
    return out


def _balanced(tokens,pos,opening,closing):
    if pos>=len(tokens) or tokens[pos][0]!=opening:
        raise ValueError('Expected '+opening)
    depth=0
    for i in range(pos,len(tokens)):
        if tokens[i][0]==opening: depth+=1
        elif tokens[i][0]==closing:
            depth-=1
            if depth==0: return i+1
    raise ValueError('Unbalanced '+opening+closing)


def _annotation(tokens,pos):
    assert tokens[pos][0]=='@'
    i=pos+1; parts=[]
    if i>=len(tokens) or not is_java_identifier(tokens[i][0]):
        raise ValueError('Invalid annotation name')
    parts.append(tokens[i][0]); i+=1
    while i<len(tokens) and tokens[i][0]=='.':
        i+=1
        if i>=len(tokens) or not is_java_identifier(tokens[i][0]):
            raise ValueError('Invalid qualified annotation name')
        parts.append(tokens[i][0]); i+=1
    if i<len(tokens) and tokens[i][0]=='(': i=_balanced(tokens,i,'(',')')
    return '.'.join(parts),i


def inventory_java_tests(source):
    tokens=_tokens(source); methods=[]; annotation_count=0; i=0
    while i<len(tokens):
        if tokens[i][0]!='@': i+=1; continue
        annotation,end=_annotation(tokens,i)
        if annotation not in {'Test','org.junit.Test'}: i=end; continue
        annotation_count+=1; start=tokens[i][1]; p=end
        # Allow other method annotations between @Test and the method signature.
        while p<len(tokens) and tokens[p][0]=='@':
            another,p=_annotation(tokens,p)
            if another in {'Test','org.junit.Test'}:
                raise ValueError('Duplicate @Test annotation on one declaration')
        modifiers=[]
        while p<len(tokens) and tokens[p][0] in {'public','protected','private','static','final','synchronized','strictfp','native','abstract'}:
            modifiers.append(tokens[p][0]); p+=1
        if modifiers.count('public')!=1 or any(v in modifiers for v in ['private','protected','static','native','abstract']):
            raise ValueError('Unsupported @Test visibility/modifiers at line '+str(source.count('\n',0,start)+1))
        if p+2>=len(tokens) or tokens[p][0]!='void' or not is_java_identifier(tokens[p+1][0]) or tokens[p+2][0]!='(':
            raise ValueError('Unsupported @Test method signature at line '+str(source.count('\n',0,start)+1))
        name=tokens[p+1][0]; argstart=p+2; argend=_balanced(tokens,argstart,'(',')')
        if argend!=argstart+2: raise ValueError('Parameterized @Test method unsupported: '+name)
        p=argend
        if p<len(tokens) and tokens[p][0]=='throws':
            p+=1
            while p<len(tokens) and (is_java_identifier(tokens[p][0]) or tokens[p][0] in {'.',','}): p+=1
        if p>=len(tokens) or tokens[p][0]!='{': raise ValueError('Missing braced @Test method body: '+name)
        endbody=_balanced(tokens,p,'{','}'); body=[v for v,_ in tokens[p+1:endbody-1]]
        empty=all(v==';' for v in body)
        methods.append({'name':name,'annotation':annotation,'line':source.count('\n',0,start)+1,
                        'empty_or_semicolon_only_body':empty,
                        'no_behavior_placeholder':name=='notGeneratedAnyTest' and empty})
        i=endbody
    names=[m['name'] for m in methods]
    if len(names)!=len(set(names)): raise ValueError('Duplicate @Test method name')
    placeholders=sorted(m['name'] for m in methods if m['no_behavior_placeholder'])
    return {'parser':'junit_method_inventory_v1','annotation_count':annotation_count,
            'methods':sorted(names),'method_details':methods,
            'no_behavior_placeholder_methods':placeholders,
            'no_behavior_placeholder_count':len(placeholders),
            'behavior_test_method_count':len(methods)-len(placeholders)}


def test_methods(source):
    return inventory_java_tests(source)['methods']


def normalize_case(name,test):
    """Accept a plain Java identifier or exact Surefire/TestNG duplicate token.

    This only normalizes syntax: callers must still require the resulting method
    to belong to the source inventory and the XML classname to equal the native
    selected FQCN. No suffix/substring/whitespace or foreign-class acceptance.
    """
    if not isinstance(name,str) or not isinstance(test,str): return None
    if is_java_identifier(name): return name
    marker=' on '
    if name.count(marker)!=1: return None
    method,rest=name.split(marker,1)
    if is_java_identifier(method) and rest==method+'('+test+')': return method
    return None
