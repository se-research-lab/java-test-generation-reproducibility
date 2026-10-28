"""Load only four audited read-only functions, without importing dispatchers."""
import ast
import csv
import json
from pathlib import Path
from collections import Counter
from maven_adapter_v1 import R, sha, dump
from parallel_pin_verify_v1 import verify_pins

A=R/'completion_amendment_v1'
B=R.parent/'paired49_20261023'
SOURCE=R/'src/audit_completion_results_v6.py'
tree=ast.parse(SOURCE.read_text(encoding='utf-8'))
names={'load','pin','commands','evidence'}
functions=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name in names]
assert {node.name for node in functions}==names
exec(compile(ast.Module(body=functions,type_ignores=[]),str(SOURCE),'exec'),globals())
