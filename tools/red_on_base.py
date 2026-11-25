#!/usr/bin/env python3
"""Червоне на базі: кожен новий або змінений тест PR мусить ПАДАТИ на коді бази (main), інакше він нічого не охороняє.

Тест, що зелений і до зміни, і після, не доводить зміни: це перевірка, яку агент досі робив руками (тимчасова копія
main + перенесений тест). Тут — кодом і fail-closed:

  * Python: функції test_* у tests/**/test_*.py, нові або з іншим AST тіла (рядки/коментарі не рахуються);
  * Node: test('назва', …) у tests/*.test.cjs з новою назвою;
  * база = merge-base; дерево бази з тестами голови (tests/ голови цілком — фікстури й хелпери ті самі);
  * червоне = failed або error (зокрема імпорт/require, якого на базі ще нема); passed і skipped — НЕ червоне;
  * свідомий виняток (рефакторинг, перенесення без зміни поведінки) — рядок у повідомленні коміта діапазону:
        Green-on-base: tests/test_x.py::test_y — причина (≥ 10 символів)
    виняток без причини не приймається; виняток для тесту, що й так червоний, — помилка (застарілий виняток).

  python3 tools/red_on_base.py [--base REV] [--head REV] [--repo DIR] [--out artifacts/red-on-base.json]
Код виходу: 0 — усі нові тести червоні на базі (або винятки з причинами); 1 — є зелений без винятку; 2 — збій інструмента.
"""
import argparse
import ast
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

EXEMPT = re.compile(r'^Green-on-base:[ \t]*(\S+)[ \t]+[—-]+[ \t]*(\S.{9,})$', re.M)
NODE_TEST = re.compile(r"""\btest\(\s*(['"])((?:(?!\1).)+)\1""")


def git(repo, *args):
    return subprocess.run(['git', *args], cwd=repo, check=True, capture_output=True, text=True).stdout


def show(repo, rev, path):
    p = subprocess.run(['git', 'show', f'{rev}:{path}'], cwd=repo, capture_output=True, text=True)
    return p.stdout if p.returncode == 0 else None


def py_tests(src):
    """{node-id-suffix: дамп AST тіла} для test_* на рівні модуля й у класах Test*."""
    out = {}
    if src is None:
        return out
    tree = ast.parse(src)
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith('test'):
            out[n.name] = ast.dump(n, include_attributes=False)
        elif isinstance(n, ast.ClassDef) and n.name.startswith('Test'):
            for m in n.body:
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)) and m.name.startswith('test'):
                    out[f'{n.name}::{m.name}'] = ast.dump(m, include_attributes=False)
    return out


def node_tests(src):
    return set() if src is None else {m.group(2) for m in NODE_TEST.finditer(src)}


def changed_tests(repo, base, head):
    files = [f for f in git(repo, 'diff', '--name-only', '--diff-filter=AMR', base, head, '--', 'tests').split()
             if re.search(r'(^|/)test_[^/]*\.py$', f) or f.endswith('.test.cjs')]
    py, node = [], []
    for f in files:
        new, old = show(repo, head, f), show(repo, base, f)
        if f.endswith('.py'):
            a, b = py_tests(new), py_tests(old)
            py += [f'{f}::{k}' for k, v in a.items() if b.get(k) != v]
        else:
            node += [(f, name) for name in sorted(node_tests(new) - node_tests(old))]
    return py, node


def exemptions(repo, base, head):
    log = git(repo, 'log', '--format=%B%x00', f'{base}..{head}')
    return {m.group(1): m.group(2).strip() for m in EXEMPT.finditer(log)}


def run_python(tree, ids):
    """{id: outcome} з короткого підсумку pytest -rA (nodeid стабільний, на відміну від classname у junit,
    що залежить від rootdir). Параметризований тест червоний, якщо червоний хоч один параметр."""
    if not ids:
        return {}
    env = {**os.environ, 'PYTEST_ADDOPTS': '', 'PYTHONDONTWRITEBYTECODE': '1', 'COLUMNS': '400'}
    p = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-rA', '-p', 'no:cacheprovider', '-p', 'no:randomly', *ids],
                       cwd=tree, env=env, capture_output=True, text=True, timeout=1800)
    res = {}
    for m in re.finditer(r'^(PASSED|FAILED|ERROR) (\S+?)(?:\[[^\]]*\])?(?: - .*)?$', p.stdout, re.M):
        o = 'green' if m.group(1) == 'PASSED' else 'red'
        res[m.group(2)] = 'red' if 'red' in (res.get(m.group(2)), o) else o
    for i in ids:                                         # помилка збору файлу (імпорт того, чого на базі нема): ERROR <файл>
        f = i.split('::')[0]
        if i not in res and re.search(rf'^ERROR {re.escape(f)}(?: |$)', p.stdout, re.M):
            res[i] = 'red'
    if not res and p.returncode not in (0, 1):
        raise RuntimeError(f'pytest не запустився (код {p.returncode}): {p.stdout[-400:]}{p.stderr[-400:]}')
    return res


def run_node(tree, items):
    res = {}
    for f, name in items:
        p = subprocess.run(['node', '--test', '--test-reporter=tap', f'--test-name-pattern=^{re.escape(name)}$', f],
                           cwd=tree, capture_output=True, text=True, timeout=600)
        m_pass, m_fail = re.search(r'^# pass (\d+)', p.stdout, re.M), re.search(r'^# fail (\d+)', p.stdout, re.M)
        ran = (int(m_pass.group(1)) if m_pass else 0) + (int(m_fail.group(1)) if m_fail else 0)
        res[f'{f}::{name}'] = 'red' if p.returncode != 0 else ('green' if ran else 'not-run')
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--repo', default='.')
    ap.add_argument('--base', default=None, help='за замовчуванням merge-base з origin/main')
    ap.add_argument('--head', default='HEAD')
    ap.add_argument('--out', default='artifacts/red-on-base.json')
    a = ap.parse_args()
    repo = Path(a.repo).resolve()
    base = git(repo, 'merge-base', a.base or 'origin/main', a.head).strip()
    head = git(repo, 'rev-parse', a.head).strip()
    py, node = changed_tests(repo, base, head)
    ex = exemptions(repo, base, head)
    report = {'schema': 'pbt-red-on-base-v1', 'base': base, 'head': head, 'tests': {}, 'violations': []}
    if py or node:
        tmp = Path(tempfile.mkdtemp(prefix='red-on-base-'))
        tree = tmp / 'base'
        try:
            git(repo, 'worktree', 'add', '-q', '--detach', str(tree), base)
            shutil.rmtree(tree / 'tests', ignore_errors=True)                  # тести рівно з коміта голови
            for f in git(repo, 'ls-tree', '-r', '--name-only', head, 'tests').split():
                (tree / f).parent.mkdir(parents=True, exist_ok=True)
                (tree / f).write_bytes(subprocess.run(['git', 'show', f'{head}:{f}'], cwd=repo, check=True,
                                                      capture_output=True).stdout)
            outcomes = {**run_python(tree, py), **run_node(tree, node)}
        finally:
            subprocess.run(['git', 'worktree', 'remove', '--force', str(tree)], cwd=repo, capture_output=True)
            shutil.rmtree(tmp, ignore_errors=True)
        for tid in py + [f'{f}::{n}' for f, n in node]:
            o = outcomes.get(tid, 'not-run')
            report['tests'][tid] = {'on_base': o, 'exemption': ex.get(tid)}
            if o != 'red' and tid not in ex:
                report['violations'].append(f'{tid}: {o} на базі {base[:10]} — тест не доводить зміни')
            if o == 'red' and tid in ex:
                report['violations'].append(f'{tid}: червоний на базі, а виняток Green-on-base заявлено — прибрати')
    for tid in ex:
        if tid not in report['tests']:
            report['violations'].append(f'{tid}: виняток Green-on-base для тесту, якого PR не додає й не змінює')
    out = repo / a.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    for tid, r in report['tests'].items():
        print(f"{r['on_base']:>8}  {tid}" + (f"  [виняток: {r['exemption']}]" if r['exemption'] else ''))
    if not report['tests']:
        print('нових або змінених тестів нема')
    for v in report['violations']:
        print('ПОРУШЕННЯ:', v)
    return 1 if report['violations'] else 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (subprocess.CalledProcessError, RuntimeError, SyntaxError) as e:
        print(f'red_on_base: збій інструмента: {e}', file=sys.stderr)
        sys.exit(2)
