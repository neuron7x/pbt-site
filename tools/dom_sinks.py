#!/usr/bin/env python3
"""Fail-closed inventory of DOM execution/markup sinks in first-party JS.

Every sink statement is fingerprinted in config/dom-sinks.json; each was reviewed for what reaches it.
A new or edited sink stays red until the inventory is regenerated deliberately (--write), so a data flow
cannot enter a sink unnoticed. It is an inventory, not taint analysis: it cannot prove a reviewed sink safe.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

SINK = re.compile(r"""\.innerHTML\s*=(?!=)|\.outerHTML\s*=(?!=)|insertAdjacentHTML\s*\(|document\.write|\beval\s*\(|new\s+Function\s*\(|\.setAttribute\s*\(\s*['"]on|\.(?:href|src)\s*=(?!=)|srcdoc""")


def inventory(root):
    found = {}
    for path in sorted((root / 'web' / 'js').glob('*.js')):
        for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
            for match in SINK.finditer(line):
                key = hashlib.sha256(f'{path.name}\0{match.group(0)}\0{" ".join(line.split())}'.encode()).hexdigest()[:24]
                found[key] = {'file': path.name, 'line': number, 'sink': ' '.join(match.group(0).split())}
    return found


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=Path(__file__).resolve().parent.parent)
    p.add_argument('--write', action='store_true')
    a = p.parse_args(argv)
    found = inventory(a.root)
    target = a.root / 'config' / 'dom-sinks.json'
    if a.write:
        target.write_text(json.dumps({'schema': 'pbt-dom-sinks-v1', 'sinks': found}, indent=1, sort_keys=True) + '\n', encoding='utf-8')
        print(f'wrote {len(found)} reviewed sinks')
        return 0
    try:
        known = json.loads(target.read_text(encoding='utf-8'))['sinks']
    except (OSError, ValueError, KeyError) as exc:
        print(json.dumps({'status': 'FAIL', 'reason': f'inventory_unreadable_{type(exc).__name__}'}))
        return 1
    new = sorted(k for k in found if k not in known)
    gone = sorted(k for k in known if k not in found)
    if not found:
        print(json.dumps({'status': 'FAIL', 'reason': 'no_sources_scanned'}))
        return 1
    if new or gone:
        print(json.dumps({'status': 'FAIL', 'reason': 'unreviewed_sink' if new else 'stale_inventory',
                          'unreviewed': [found[k] for k in new], 'stale': len(gone)}, ensure_ascii=False))
        return 1
    print(json.dumps({'status': 'PASS', 'sinks': len(found)}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
