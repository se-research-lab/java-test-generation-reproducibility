"""Static proof of inspection-only analyzer changes; no experiment invocation."""
import ast, hashlib, json
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]
def tree(name): return ast.parse((BASE/'src'/name).read_text(encoding='utf-8'))
def functions(name): return {x.name:x for x in tree(name).body if isinstance(x,ast.FunctionDef)}
def dump(node): return ast.dump(node,include_attributes=False)
o=functions('analyze_measurement_compat49_v1.py'); n=functions('analyze_measurement_compat49_v2.py')
for name in ['pure_original_functions','validate_cohort','frozen_gpt_guard','selected_test_bytecode','validate_test_bytecode']:
    assert dump(o[name])==dump(n[name]),name
class RemoveStats(ast.NodeTransformer):
    def visit_Assign(self,node):
        keys={'no_behavior_placeholder_classes','no_behavior_placeholder_methods','strict_suite_evidence_meaning','placeholder_changes_score_or_denominator','placeholder_diagnostic'}
        if len(node.targets)==1 and isinstance(node.targets[0],ast.Subscript) and isinstance(node.targets[0].slice,ast.Constant) and node.targets[0].slice.value in keys:
            return None
        return self.generic_visit(node)
assert dump(o['summarize_replay'])==dump(RemoveStats().visit(n['summarize_replay']))
a=functions('independent_measurement49_raw_audit_v1.py'); b=functions('independent_measurement49_raw_audit_v2.py')
assert dump(a['summaries'])==dump(RemoveStats().visit(b['summaries']))
for name in ['fingerprint','focal_rows','assert_complete','validate_policy']:
    assert dump(a[name])==dump(b[name]),name
def score_assigns(f,names):
    return [dump(x) for x in ast.walk(f) if isinstance(x,ast.Assign) and any(isinstance(t,ast.Name) and t.id in names for t in x.targets)]
assert score_assigns(o['inspect_job'],{'score','strict_score','actual_gate'})==score_assigns(n['inspect_job'],{'score','strict_score','actual_gate'})
assert score_assigns(a['inspect'],{'gate','rawscore','score'})==score_assigns(b['inspect'],{'gate','rawscore','score'})
print(json.dumps({'status':'PASS','arithmetic_and_bootstrap_AST_unchanged':True,'score_gate_AST_unchanged':True,'legacy_PIT_fingerprint_AST_unchanged':True,'Java_Maven_API_calls':0},indent=2))
