#!/usr/bin/env python3
"""Каталог мутантів (config/mutation-catalog.json) — без ручного редагування JSON.

Раніше мутант дописувався руками в кінець файлу: форматування дрейфувало (json.dumps з іншим indent переписав
2187 рядків), а паралельні PR конфліктували саме на хвості. Тут:

  add    перевіряє й додає мутант, одразу проганяє його (tools/mutation_run.py --only) — у каталог потрапляє
         лише KILLED; edits і oracle — як у каталозі:
           python3 tools/mutant_new.py add M-X-01 TASK-1 --file web/js/a.js --find 'old' --replace 'new' \\
                   --oracle tests/test_a.py::test_b --note 'Що саме зламано і чому це небезпечно.'
           (кілька правок: повторити --file/--find/--replace; Node-оракул одним рядком: --oracle 'node --test tests/x.test.cjs')
  check  каталог канонічний: відсортовано за id, indent=1, ensure_ascii=False, \\n у кінці; id унікальні;
         кожен find трапляється у своєму файлі рівно раз (інакше мутант INVALID ще до прогону)
  fmt    привести до канонічної форми

Сортування за id розносить нові записи по файлу: конфлікт злиття лише між мутантами однієї задачі.
"""
import argparse
import json
import shlex
from pathlib import Path
import subprocess
import sys

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
        for e in m.get('edits', []):
            p = root / e['file']
            n = p.read_text(encoding='utf-8').count(e['find']) if p.is_file() else -1
            if n != 1:
                out.append(f"{m['id']}: find у {e['file']} трапляється {n} раз (має 1)")
    return out


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
    a.add_argument('--no-run', action='store_true', help='не проганяти (лише для тестів інструмента)')
    args = ap.parse_args(argv)
    raw = CAT.read_text(encoding='utf-8')
    d = json.loads(raw)
    if args.cmd == 'fmt':
        CAT.write_text(canonical(d), encoding='utf-8')
        return 0
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
    CAT.write_text(canonical(new), encoding='utf-8')
    if args.no_run:
        return 0
    r = subprocess.run([sys.executable, str(ROOT / 'tools' / 'mutation_run.py'), '--only', args.id], cwd=ROOT,
                       capture_output=True, text=True)
    print(r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-400:])
    if r.returncode != 0:
        CAT.write_text(raw, encoding='utf-8')                             # не вбитий — у каталог не потрапляє
        print(f'{args.id}: не KILLED — каталог повернуто як був')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
