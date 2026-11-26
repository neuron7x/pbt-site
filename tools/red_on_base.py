#!/usr/bin/env python3
"""Зіставити результати обраних тестів на голові PR і на merge-base.

Покриття: нові або змінені AST-визначення Python у test_*.py та нові назви
верхньорівневих Node test('назва', ...) у *.test.cjs. Зміни тіла Node-тесту зі
старою назвою, динамічні назви та окремі зміни фікстур не виявляються.

Позитивний контроль: кожен обраний варіант проходить на точній голові.
На базі тести беруться з голови. Зараховується збій обраного твердження або
підтверджена відсутність нового прямого Python-імпорту на базі. Збій
запуску, пропуск, xfail або відсутній тест не зараховуються. Виняток
Green-on-base дозволяється тільки обраному тесту, який справді пройшов.
"""
import argparse
import ast
import json
import os
from pathlib import Path
import re
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
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith('test_'):
            out[n.name] = ast.dump(n, include_attributes=False)
        elif isinstance(n, ast.ClassDef) and n.name.startswith('Test'):
            for m in n.body:
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)) and m.name.startswith('test_'):
                    out[f'{n.name}::{m.name}'] = ast.dump(m, include_attributes=False)
    return out


def node_tests(src):
    return set() if src is None else {m.group(2) for m in NODE_TEST.finditer(src)}


def changed_tests(repo, base, head):
    files = [f for f in git(repo, 'diff', '--name-only', '-z', '--diff-filter=AMR', base, head, '--', 'tests').split('\0')
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
    log = git(repo, 'log', '--format=%B', f'{base}..{head}')
    return {m.group(1): m.group(2).strip() for m in EXEMPT.finditer(log)}


PYTEST_PROBE = r'''
import json
from pathlib import Path
import sys
import pytest


class Probe:
    def __init__(self):
        self.items = []
        self.phases = {}
        self.collection = []

    def pytest_collection_finish(self, session):
        self.items = [i.nodeid for i in session.items if not list(i.iter_markers("xfail"))]

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_makereport(self, item, call):
        report = (yield).get_result()
        exc = call.excinfo.value if call.excinfo else None
        if report.passed and not hasattr(report, "wasxfail"):
            state = "pass"
        elif report.failed and isinstance(exc, (AssertionError, pytest.fail.Exception)):
            state = "assertion"
        else:
            state = "incomplete"
        self.phases.setdefault(item.nodeid, {})[report.when] = state

    def pytest_exception_interact(self, node, call, report):
        if getattr(report, "when", None) != "collect":
            return
        exc = call.excinfo.value
        path = Path(node.path).resolve()
        frames = [frame.lineno + 1 for frame in call.excinfo.traceback
                  if Path(frame.path).resolve() == path]
        self.collection.append({
            "file": str(path), "module": exc.name if type(exc) is ModuleNotFoundError else None,
            "lines": frames,
        })


output, *ids = sys.argv[1:]
probe = Probe()
status = pytest.main(["-q", "-p", "no:cacheprovider", *ids], plugins=[probe])
Path(output).write_text(json.dumps(vars(probe)), encoding="utf-8")
sys.exit(status)
'''

NODE_REPORTER = r'''
export default async function* report(source) {
  for await (const { type, data } of source) {
    if (type === 'test:pass' || type === 'test:fail') {
      yield JSON.stringify({
        type, file: data.file, name: data.name, nesting: data.nesting,
        excluded: Boolean(data.skip || data.todo),
        assertion: data.details?.error?.failureType === 'testCodeFailure'
          && data.details?.error?.cause?.code === 'ERR_ASSERTION',
      }) + '\n';
    }
  }
}
'''


def command(tree, args, timeout):
    env = {**os.environ, 'PYTEST_ADDOPTS': '', 'PYTHONDONTWRITEBYTECODE': '1',
           'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1'}
    return subprocess.run(args, cwd=tree, env=env, capture_output=True, text=True,
                          encoding='utf-8', timeout=timeout)


def pytest_outcome(node_id, report):
    items = [item for item in report['items']
             if item == node_id or item.startswith(node_id + '[')]
    matching_phases = {node for node in report['phases']
                       if node == node_id or node.startswith(node_id + '[')}
    if not items or set(items) != matching_phases:
        return 'not-run'
    calls = []
    for item in items:
        phases = report['phases'][item]
        if phases.get('setup') != 'pass' or phases.get('teardown') != 'pass':
            return 'not-run'
        calls.append(phases.get('call'))
    if any(call not in ('pass', 'assertion') for call in calls):
        return 'not-run'
    return 'red' if 'assertion' in calls else 'green'


def direct_new_import(tree, file, report, added):
    """Нова відсутня залежність має бути прямим безумовним імпортом тестового файла."""
    failures = report['collection']
    if report['items'] or report['phases'] or len(failures) != 1:
        return False
    failure = failures[0]
    path = tree / file
    if failure['file'] != str(path.resolve()) or not failure['module']:
        return False
    module = failure['module']
    prefix = module.replace('.', '/')
    if not {f'{prefix}.py', f'{prefix}/__init__.py'} & added:
        return False
    for statement in ast.parse(path.read_text(encoding='utf-8')).body:
        if statement.lineno not in failure['lines']:
            continue
        if isinstance(statement, ast.Import) and any(part.name == module for part in statement.names):
            return True
        if isinstance(statement, ast.ImportFrom) and statement.level == 0 and statement.module == module:
            return True
    return False


def run_python(tree, ids, output, added=frozenset()):
    files = {}
    for node in ids:
        files.setdefault(node.split('::', 1)[0], []).append(node)
    outcomes = {}
    for file, selected in files.items():
        output.unlink(missing_ok=True)
        proc = command(tree, [sys.executable, '-c', PYTEST_PROBE, str(output), *selected], 1800)
        if not output.is_file():
            raise RuntimeError(f'pytest не створив звіт ({file}, exit {proc.returncode}): {proc.stderr[-400:]}')
        report = json.loads(output.read_text(encoding='utf-8'))
        states = dict.fromkeys(selected, 'not-run')
        if proc.returncode in (0, 1) and not report['collection']:
            states = {node: pytest_outcome(node, report) for node in selected}
            if (proc.returncode == 1) != ('red' in states.values()):
                states = dict.fromkeys(selected, 'not-run')
        elif proc.returncode in (2, 4) and direct_new_import(tree, file, report, added):
            states = dict.fromkeys(selected, 'blocked-by-new-module')
        outcomes.update(states)
    return outcomes


def node_outcome(file, name, returncode, events):
    selected = [event for event in events if event.get('file') == str(file)
                and event['name'] == name and event['nesting'] == 0]
    if len(selected) != 1 or selected[0]['excluded']:
        return 'not-run'
    event = selected[0]
    failures = [result for result in events if result['type'] == 'test:fail' and not result['excluded']]
    if returncode == 0 and event['type'] == 'test:pass' and not failures:
        return 'green'
    if returncode == 1 and failures == [event] and event['assertion']:
        return 'red'
    return 'not-run'


def run_node(tree, items, reporter):
    outcomes = {}
    for file, name in items:
        path = (tree / file).resolve()
        pattern = '^' + re.sub(r'([\\.^$|?*+()\[\]{}])', r'\\\1', name) + '$'
        proc = command(tree, ['node', '--test', f'--test-reporter={reporter.as_uri()}',
                              f'--test-name-pattern={pattern}', str(path)], 600)
        events = [json.loads(line) for line in proc.stdout.splitlines() if line]
        outcomes[f'{file}::{name}'] = node_outcome(path, name, proc.returncode, events)
    return outcomes


def measure(repo, base, head, py, node):
    if not py and not node:
        return {}, {}
    added = set(git(repo, 'diff', '--no-renames', '--name-only', '-z', '--diff-filter=A',
                    base, head).split('\0'))
    with tempfile.TemporaryDirectory(prefix='red-on-base-') as directory:
        scratch = Path(directory)
        baseline, candidate = scratch / 'base', scratch / 'head'
        reporter = scratch / 'node-reporter.mjs'
        reporter.write_text(NODE_REPORTER, encoding='utf-8')
        output = scratch / 'pytest.json'
        worktrees = []
        try:
            git(repo, 'worktree', 'add', '-q', '--detach', str(candidate), head)
            worktrees.append(candidate)
            positive = {**run_python(candidate, py, output), **run_node(candidate, node, reporter)}
            if any(state != 'green' for state in positive.values()):
                return positive, {}
            git(repo, 'worktree', 'add', '-q', '--detach', str(baseline), base)
            worktrees.append(baseline)
            git(baseline, 'restore', f'--source={head}', '--worktree', '--', 'tests')
            negative = {**run_python(baseline, py, output, added), **run_node(baseline, node, reporter)}
            return positive, negative
        finally:
            for tree in reversed(worktrees):
                git(repo, 'worktree', 'remove', '--force', str(tree))


def violations(base, result, exemption):
    positive, negative = result['on_head'], result['on_base']
    if positive != 'green':
        return f'{positive} на голові — позитивний контроль не пройшов'
    if negative in ('red', 'blocked-by-new-module'):
        return 'негативний контроль пройшов, а виняток заявлено — прибрати' if exemption else None
    if negative == 'green' and exemption:
        return None
    return f'{negative} на базі {base[:10]} — тест не доводить зміни'


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
    report = {'schema': 'pbt-red-on-base-v2', 'base': base, 'head': head, 'tests': {}, 'violations': []}
    positive, negative = measure(repo, base, head, py, node)
    for tid in py + [f'{f}::{n}' for f, n in node]:
        result = {'on_head': positive.get(tid, 'not-run'), 'on_base': negative.get(tid, 'not-run'),
                  'exemption': ex.get(tid)}
        report['tests'][tid] = result
        problem = violations(base, result, ex.get(tid))
        if problem:
            report['violations'].append(f'{tid}: {problem}')
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
    except (subprocess.SubprocessError, OSError, RuntimeError, SyntaxError, ValueError) as e:
        print(f'red_on_base: збій інструмента: {e}', file=sys.stderr)
        sys.exit(2)
