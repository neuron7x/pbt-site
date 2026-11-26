#!/usr/bin/env python3
"""Каталог мутантів (config/mutation-catalog.json) — без ручного редагування JSON.

Раніше мутант дописувався руками в кінець файлу: форматування дрейфувало (json.dumps з іншим indent переписав
2187 рядків), а паралельні PR конфліктували саме на хвості. Тут:

  add    перевіряє й додає мутант, одразу проганяє його (tools/mutation_run.py --only) — у каталог потрапляє
         лише перевірений KILLED; edits і oracle — як у каталозі:
           python3 tools/mutant_new.py add M-X-01 TASK-1 --file web/js/a.js --find 'old' --replace 'new' \\
                   --oracle tests/test_a.py::test_b --note 'Що саме зламано і чому це небезпечно.'
           (кілька правок: повторити --file/--find/--replace; Node-оракул одним рядком: --oracle 'node --test tests/x.test.cjs')
  check  каталог канонічний: відсортовано за id, indent=1, ensure_ascii=False, \\n у кінці; id унікальні;
         кожен find трапляється у своєму файлі рівно раз (інакше мутант INVALID ще до прогону)
  fmt    привести до канонічної форми

Сортування за id розносить нові записи по файлу: конфлікт злиття лише між мутантами однієї задачі.
"""
import argparse
import fcntl
import json
import os
import shlex
from pathlib import Path
import subprocess
import sys
import tempfile

from mutation_run import mutation_target

ROOT = Path(__file__).resolve().parent.parent
CAT = ROOT / 'config' / 'mutation-catalog.json'


def canonical(d):
    d = {**d, 'mutants': sorted(d['mutants'], key=lambda m: m['id'])}
    return json.dumps(d, ensure_ascii=False, indent=1) + '\n'


def problems(d, root=ROOT):
    out, seen = [], set()
    for m in d['mutants']:
        if m['id'] in seen:
            out.append(f"{m['id']}: id повторюється")
        seen.add(m['id'])
        if m.get('expected') == 'UNTESTABLE':
            if len(m.get('reason', '')) < 40:
                out.append(f"{m['id']}: UNTESTABLE без змістовної причини")
            continue
        if not m.get('oracle'):
            out.append(f"{m['id']}: без оракула")
        if not m.get('edits'):
            out.append(f"{m['id']}: без правок")
        for e in m.get('edits', []):
            try:
                p = mutation_target(root, e['file'])
            except (OSError, ValueError) as exc:
                out.append(f"{m['id']}: {exc}")
                continue
            if not e['find'] or e['find'] == e['replace']:
                out.append(f"{m['id']}: неприпустима правка у {e['file']}")
                continue
            n = p.read_text(encoding='utf-8').count(e['find'])
            if n != 1:
                out.append(f"{m['id']}: find у {e['file']} трапляється {n} раз (має 1)")
    return out


def publish(path, before, after):
    """Атомарно замінити каталог, якщо ніхто не змінив прочитані байти."""
    directory = os.open(path.parent, os.O_RDONLY)
    try:
        fcntl.flock(directory, fcntl.LOCK_EX)
        if path.read_bytes() != before.encode('utf-8'):
            return False
        with tempfile.NamedTemporaryFile(dir=path.parent, mode='wb', delete=False) as staged:
            temporary = Path(staged.name)
            try:
                staged.write(after.encode('utf-8'))
                staged.close()
                temporary.chmod(path.stat().st_mode & 0o777)
                temporary.replace(path)
            finally:
                temporary.unlink(missing_ok=True)
    finally:
        os.close(directory)
    return True


def confirmed_kill(candidate, mutant_id):
    with tempfile.TemporaryDirectory(prefix='pbt-candidate-mutant-') as directory:
        catalogue = Path(directory) / 'catalogue.json'
        report = Path(directory) / 'report.json'
        catalogue.write_text(candidate, encoding='utf-8')
        run = subprocess.run([sys.executable, str(ROOT / 'tools' / 'mutation_run.py'),
                              '--catalog', str(catalogue), '--only', mutant_id, '--out', str(report)],
                             cwd=ROOT, capture_output=True, text=True)
        print(run.stdout.strip().splitlines()[-1] if run.stdout.strip() else run.stderr[-400:])
        if run.returncode != 0 or not report.is_file():
            return False
        result = json.loads(report.read_text(encoding='utf-8'))
        rows = result.get('results', [])
        return (result.get('status') == 'PASS' and len(rows) == 1
                and rows[0].get('id') == mutant_id and rows[0].get('verdict') == 'KILLED')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('check')
    sub.add_parser('fmt')
    a = sub.add_parser('add')
    a.add_argument('id')
    a.add_argument('task')
    a.add_argument('--file', action='append', required=True)
    a.add_argument('--find', action='append', required=True)
    a.add_argument('--replace', action='append', required=True)
    a.add_argument('--oracle', required=True, help='pytest node id або команда одним рядком (shlex)')
    a.add_argument('--note', required=True)
    args = ap.parse_args(argv)
    raw = CAT.read_bytes().decode('utf-8')
    d = json.loads(raw)
    if args.cmd == 'fmt':
        if publish(CAT, raw, canonical(d)):
            return 0
        print('Каталог змінився під час форматування. Повторіть команду.')
        return 1
    if args.cmd == 'check':
        bad = problems(d) + ([] if raw == canonical(d) else ['каталог не канонічний: python3 tools/mutant_new.py fmt'])
        print('\n'.join(bad) or f"mutation catalog OK: {len(d['mutants'])} мутантів")
        return 1 if bad else 0
    if not (len(args.file) == len(args.find) == len(args.replace)):
        ap.error('--file/--find/--replace мають іти трійками')
    m = {'id': args.id, 'task': args.task,
         'edits': [{'file': f, 'find': fi, 'replace': r} for f, fi, r in zip(args.file, args.find, args.replace)],
         'oracle': shlex.split(args.oracle), 'note': args.note}
    if any(e['find'] == e['replace'] for e in m['edits']):
        ap.error('replace == find: це не мутант')
    new = {**d, 'mutants': d['mutants'] + [m]}
    bad = problems(new)
    if bad:
        print('\n'.join(bad))
        return 1
    candidate = canonical(new)
    if not confirmed_kill(candidate, args.id):
        print(f'{args.id}: немає підтвердженого KILLED для цього id')
        return 1
    if not publish(CAT, raw, candidate):
        print('Каталог змінився під час перевірки. Повторіть команду.')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
