"""tools/red_on_base.py — гейт «новий тест мусить бути червоним на базі». Іграшковий git-репозиторій: база, де mod.f()
повертає 1, голова — 2. Перевіряємо всі гілки рішення, включно з вироджено-зеленими."""
from pathlib import Path
import subprocess
import sys

import pytest

TOOL = Path(__file__).resolve().parent.parent / 'tools' / 'red_on_base.py'


def sh(repo, *a):
    return subprocess.run(['git', *a], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


def commit(repo, files, msg):
    for k, v in files.items():
        p = repo / k
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(v, encoding='utf-8')
    sh(repo, 'add', '-A')
    sh(repo, '-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', msg)
    return sh(repo, 'rev-parse', 'HEAD')


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / 'r'
    r.mkdir()
    sh(r, 'init', '-q')
    base = commit(r, {'mod.py': 'def f():\n    return 1\n', 'mod.cjs': 'exports.f = () => 1;\n',
                      'tests/test_old.py': 'def test_old():\n    assert True\n'}, 'base')
    return r, base


def run(r, base):
    p = subprocess.run([sys.executable, str(TOOL), '--repo', str(r), '--base', base, '--out', 'rob.json'],
                       capture_output=True, text=True, timeout=300)
    return p.returncode, p.stdout + p.stderr


PY_RED = 'import mod\n\ndef test_two():\n    assert mod.f() == 2\n'
PY_GREEN = 'def test_tautology():\n    assert 1 + 1 == 2\n'
NODE = """const test = require('node:test'); const assert = require('node:assert');
const { f } = require('../mod.cjs');
test('two', () => assert.equal(f(), 2));
test('always', () => assert.ok(true));
"""


def test_new_test_red_on_base_passes(repo):
    r, base = repo
    commit(r, {'mod.py': 'def f():\n    return 2\n', 'tests/test_new.py': PY_RED}, 'feat')
    code, out = run(r, base)
    assert code == 0 and 'red  tests/test_new.py::test_two' in out, out


def test_new_test_green_on_base_is_a_violation(repo):
    r, base = repo
    commit(r, {'tests/test_new.py': PY_RED + '\n' + PY_GREEN, 'mod.py': 'def f():\n    return 2\n'}, 'feat')
    code, out = run(r, base)
    assert code == 1 and 'test_tautology: green' in out and 'test_two' not in out.split('ПОРУШЕННЯ')[1], out


def test_exemption_needs_a_reason_and_must_not_be_stale(repo):
    r, base = repo
    commit(r, {'tests/test_new.py': PY_GREEN}, 'refactor\n\nGreen-on-base: tests/test_new.py::test_tautology — move only')
    assert run(r, base)[0] == 1                                            # причина коротша за 10 символів — не виняток
    commit(r, {'tests/test_new.py': PY_GREEN + ' '}, 'x\n\nGreen-on-base: tests/test_new.py::test_tautology — перенесення без зміни поведінки')
    assert run(r, base)[0] == 0
    commit(r, {'mod.py': 'def f():\n    return 2\n', 'tests/test_two.py': PY_RED},
           'y\n\nGreen-on-base: tests/test_two.py::test_two — помилково заявлений виняток')
    code, out = run(r, base)
    assert code == 1 and 'прибрати' in out, out                           # виняток для червоного тесту — застарілий


def test_changed_body_counts_unchanged_body_does_not(repo):
    r, base = repo
    commit(r, {'tests/test_old.py': '# коментар не змінює тест\ndef test_old():\n    assert True\n'}, 'cosmetic')
    code, out = run(r, base)
    assert code == 0 and 'нових або змінених тестів нема' in out, out
    commit(r, {'tests/test_old.py': 'def test_old():\n    assert 2 > 1\n'}, 'changed')
    assert run(r, base)[0] == 1


def test_node_tests_new_names_are_checked(repo):
    r, base = repo
    commit(r, {'mod.cjs': 'exports.f = () => 2;\n', 'tests/m.test.cjs': NODE}, 'node')
    code, out = run(r, base)
    assert code == 1, out
    assert 'red  tests/m.test.cjs::two' in out and 'green  tests/m.test.cjs::always' in out, out


def test_new_direct_module_has_its_own_base_outcome(repo):
    r, base = repo
    commit(r, {'newmod.py': 'X = 1\n', 'tests/test_imp.py': 'from newmod import X\n\ndef test_x():\n    assert X == 1\n'}, 'new module')
    code, out = run(r, base)
    assert code == 0 and 'blocked-by-new-module  tests/test_imp.py::test_x' in out, out

def test_indirect_module_failure_does_not_replace_test_execution(repo):
    r, base = repo
    base = commit(r, {'mod.py': 'from unavailable import f\n'}, 'base import failure')
    commit(r, {'unavailable.py': 'def f():\n    return 2\n', 'tests/test_new.py': PY_RED}, 'feat')
    code, out = run(r, base)
    assert code == 1 and 'test_two: not-run' in out, out


def test_fixture_failure_on_base_does_not_count_as_assertion(repo):
    r, base = repo
    suite = '''import mod
import pytest

@pytest.fixture
def setup():
    assert mod.f() == 2

def test_two(setup):
    assert True
'''
    commit(r, {'mod.py': 'def f():\n    return 2\n', 'tests/test_new.py': suite}, 'feat')
    code, out = run(r, base)
    assert code == 1 and 'test_two: not-run' in out, out


def test_unexecuted_base_test_cannot_use_green_exemption(repo):
    r, base = repo
    suite = '''import mod
import pytest

def test_two():
    if mod.f() == 1:
        pytest.skip('base simplification')
    assert mod.f() == 2
'''
    commit(r, {'mod.py': 'def f():\n    return 2\n', 'tests/test_new.py': suite},
           'feat\n\nGreen-on-base: tests/test_new.py::test_two — перенесення без зміни поведінки')
    code, out = run(r, base)
    assert code == 1 and 'test_two: not-run' in out, out


def test_red_on_both_revisions_cannot_pass_positive_control(repo):
    r, base = repo
    commit(r, {'tests/test_new.py': PY_RED}, 'red everywhere')
    code, out = run(r, base)
    assert code == 1 and 'test_two: red на голові' in out, out


def test_node_file_load_failure_does_not_replace_selected_assertion(repo):
    r, base = repo
    suite = NODE.replace('../mod.cjs', '../new.cjs').split("test('always'")[0]
    commit(r, {'new.cjs': 'exports.f = () => 2;\n', 'tests/m.test.cjs': suite}, 'feat')
    code, out = run(r, base)
    assert code == 1 and 'm.test.cjs::two: not-run' in out, out

