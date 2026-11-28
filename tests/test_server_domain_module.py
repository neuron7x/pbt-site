"""Наказ А1, крок 1: домен заявки — окремий чистий модуль server/domain.py.

Критерій наказу для цього кроку: модуль імпортується без побічних ефектів і без оточення; server/app.py користується
ним, а не власною копією.
"""
import ast
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOMAIN = ROOT / 'server/domain.py'
NAMES = ('CTRL', 'KYIV', 'METHODS', 'MSG', 'MSG_SUBJECT', 'TYPES', '_contact', '_date', '_int', 'clean', 'date_allowed', 'kyiv_date', 'validate')
PURE_IMPORTS = {'re', 'unicodedata', 'datetime', 'zoneinfo'}


def _tree():
    assert DOMAIN.is_file(), 'server/domain.py відсутній'
    return ast.parse(DOMAIN.read_text(encoding='utf-8'))


def test_domain_module_imports_nothing_that_can_touch_the_world():
    imported = set()
    for node in ast.walk(_tree()):
        if isinstance(node, ast.Import):
            imported |= {alias.name.split('.')[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or '').split('.')[0])
    assert imported <= PURE_IMPORTS, imported - PURE_IMPORTS            # ні os, ні sqlite3, ні socket, ні logging
    calls = {node.func.id for node in ast.walk(_tree()) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
    assert not calls & {'open', 'print', 'exec', 'eval', '__import__'}, calls


def test_importing_the_domain_in_an_empty_directory_creates_nothing(tmp_path):
    code = ("import sys, json; sys.path.insert(0, sys.argv[1]); import domain\n"
            "out, err = domain.validate({'type': 'rent', 'subject': 'Екскаватор', 'method': 'phone', 'contact': '067 123 45 67', 'hours': '16'})\n"
            "print(json.dumps([out['contact'], out['hours'], err, sorted(domain.TYPES), sorted(domain.METHODS)]))\n")
    env = {k: v for k, v in os.environ.items() if k in ('PATH', 'LANG', 'LC_ALL')}                  # жодної змінної сервера
    run = subprocess.run([sys.executable, '-s', '-B', '-c', code, str(ROOT / 'server')], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=30)
    assert run.returncode == 0, run.stderr
    assert json.loads(run.stdout) == ['+380671234567', 16, {}, ['material', 'other', 'rent', 'transport'], ['phone', 'telegram', 'viber', 'whatsapp']]
    assert list(tmp_path.iterdir()) == []                                                           # ні теки data, ні журналу, ні солі


def test_the_server_uses_the_domain_module_and_keeps_no_copy():
    source = (ROOT / 'server/app.py').read_text(encoding='utf-8')
    tree = ast.parse(source)
    defined = {node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
    assert not defined & set(NAMES)
    for name in NAMES:
        bindings = [node.value for node in tree.body if isinstance(node, ast.Assign)
                    and any(isinstance(target, ast.Name) and target.id == name for target in node.targets)]
        assert len(bindings) == 1 and ast.unparse(bindings[0]) == f'_domain.{name}', name


def test_path_loaded_server_retains_the_installed_domain(tmp_path):
    code = """
import json, runpy, sys, types
from pathlib import Path
sys.modules['domain'] = types.ModuleType('domain')
before = sys.path.copy()
app = runpy.run_path(sys.argv[1])
source = Path(app['validate'].__code__.co_filename).resolve()
print(json.dumps([source == Path(sys.argv[1]).with_name('domain.py'), before == sys.path]))
"""
    env = {'PBT_DATA_DIR': str(tmp_path), 'DELIVERY_WORKER': '0'}
    run = subprocess.run([sys.executable, '-B', '-c', code, str(ROOT / 'server/app.py')],
                         env=env, capture_output=True, text=True, timeout=20)
    assert run.returncode == 0, run.stderr
    assert json.loads(run.stdout) == [True, True]
