#!/usr/bin/env python3
"""Бюджет фактичних медіа з SHA-256. Не прирівнювати до завантаження сторінки."""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def audit_media(media_root: Path, budgets: dict) -> dict:
    failures: list[str] = []
    if budgets.get("schema_version") != 1:
        failures.append("Невідома версія бюджету")
    files = sorted(p for p in media_root.rglob("*") if p.is_file() or p.is_symlink())
    entries: list[dict] = []
    for p in files:
        rel = p.relative_to(media_root).as_posix()
        if p.is_symlink():
            failures.append(f"Симлінк у медіа заборонено: {rel}")
            continue
        h = hashlib.sha256()
        with p.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                h.update(block)
        entries.append({"path": rel, "bytes": p.stat().st_size, "sha256": h.hexdigest()})
    total = sum(rec["bytes"] for rec in entries)
    max_total = budgets.get("max_total_bytes")
    if not isinstance(max_total, int) or max_total <= 0:
        failures.append("Невалідний загальний бюджет")
    elif total > max_total:
        failures.append(f"Медіапак перевищує бюджет: {total} > {max_total} байтів")
    max_single = budgets.get("max_single_asset_bytes")
    if not isinstance(max_single, int) or max_single <= 0:
        failures.append("Невалідний бюджет одного файла")
    else:
        for e in entries:
            if e["bytes"] > max_single:
                failures.append(f"{e['path']}: {e['bytes']} > {max_single} байтів")
    groups = []
    for rule in budgets.get("rules", []):
        pattern = rule.get("glob", "")
        ceiling = rule.get("max_bytes")
        minimum = rule.get("min_count")
        # Патерни прив'язані виключно до web/media; зовнішні шляхи не читаємо.
        if (not pattern or pattern.startswith("/") or ".." in Path(pattern).parts
                or not isinstance(ceiling, int) or ceiling <= 0
                or not isinstance(minimum, int) or minimum < 1):
            failures.append(f"Невалідне правило бюджету: {pattern!r}")
            continue
        group = [e for e in entries if fnmatch.fnmatchcase(e["path"], pattern)]
        groups.append({
            "glob": pattern, "count": len(group),
            "largest_bytes": max((e["bytes"] for e in group), default=0),
            "max_bytes": ceiling,
        })
        if len(group) < minimum:
            failures.append(f"Відсутні активи {pattern}: {len(group)} < {minimum}")
        failures.extend(f"{e['path']}: {e['bytes']} > {ceiling} байтів"
                        for e in group if e["bytes"] > ceiling)
    return {
        "schema_version": 1, "measurement_type": "repository file sizes, not network transfer",
        "media_files": len(entries), "total_bytes": total,
        "groups": groups, "files": entries, "failures": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT / "web" / "media")
    parser.add_argument("--budget", type=Path, default=ROOT / "config" / "visual-budgets.json")
    parser.add_argument("--report", type=Path, default=ROOT / "artifacts" / "media-budget.json")
    args = parser.parse_args()
    if not args.root.is_dir():
        print(f"FAIL: медіатека не знайдена: {args.root}", file=sys.stderr)
        return 1
    try:
        budgets = json.loads(args.budget.read_text(encoding="utf-8"))
        result = audit_media(args.root, budgets)
    except (ValueError, OSError, TypeError) as exc:
        print(f"FAIL: невірний бюджет: {exc}", file=sys.stderr)
        return 1
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Файлів: {result['media_files']} | {result['total_bytes']} байтів | "
          f"порушень: {len(result['failures'])} | {args.report}")
    for violation in result["failures"]:
        print("FAIL:", violation, file=sys.stderr)
    return 1 if result["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
