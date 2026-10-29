#!/usr/bin/env python3
"""Фальсифікований pixel-by-pixel аналіз: не видає різницю за покращення.

    python tools/compare_shots.py artifacts/baseline artifacts/candidate [artifacts/diff]

Перш ніж порівнювати, перевіряє CRC/SHA-256 кожного PNG, версію браузера,
однакові в'юпорти і матрицю. Повертає числові відмінності, а не «бал дизайну».
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageEnhance, ImageStat

from visual_contract import verify_capture_manifest

PREVIEWS = {
    ("desktop-1440", "top"),
    ("desktop-1440", "cina"),
    ("desktop-1440", "zapyt"),
    ("mobile-390", "top"),
    ("mobile-390", "cina"),
    ("mobile-390", "zapyt"),
}


def read_validated(directory: Path) -> dict:
    source = directory / "manifest.json"
    data = json.loads(source.read_text(encoding="utf-8"))
    errors = verify_capture_manifest(data, directory)
    if errors or data.get("failures"):
        raise ValueError(f"Неприйнятні докази {directory}: " + "; ".join(errors + data.get("failures", [])))
    if data.get("field_lcp_ms") is not None or data.get("field_inp_ms") is not None or data.get("field_cls") is not None:
        raise ValueError(f"{directory}: польові Web Vitals не можуть походити зі скриншотів")
    return data


def image_difference(before: Image.Image, after: Image.Image) -> tuple[dict, Image.Image]:
    if before.size != after.size:
        raise ValueError(f"Несумісні розміри: {before.size}, {after.size}")
    delta = ImageChops.difference(before.convert("RGB"), after.convert("RGB")).convert("L")
    count = before.width * before.height
    histogram = delta.histogram()
    mean = sum(i * number for i, number in enumerate(histogram)) / count
    changed = sum(histogram[16:]) / count
    return {
        "width": before.width, "height": before.height,
        "mean_absolute_luma_difference": round(mean, 4),
        "changed_pixel_fraction_above_15": round(changed, 6),
    }, delta


def compare(baseline: Path, candidate: Path, output: Path) -> dict:
    a = read_validated(baseline)
    b = read_validated(candidate)
    if a.get("browser") != b.get("browser"):
        raise ValueError("Різна версія браузера: візуальна дифузія може бути не зміною дизайну")
    pa, pb = {r["filename"]: r for r in a["captures"]}, {r["filename"]: r for r in b["captures"]}
    if pa.keys() != pb.keys():
        raise ValueError("Неповна чи різна матриця знімків")
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    for name in sorted(pa):
        before = Image.open(baseline / name).convert("RGB")
        after = Image.open(candidate / name).convert("RGB")
        metrics, delta = image_difference(before, after)
        row = {
            "filename": name, "viewport": pa[name]["viewport"],
            "section": pa[name]["section"], **metrics,
            "baseline_sha256": pa[name]["sha256"],
            "candidate_sha256": pb[name]["sha256"],
        }
        rows.append(row)
        if (row["viewport"], row["section"]) in PREVIEWS:
            diff = ImageEnhance.Contrast(delta).enhance(4).convert("RGB")
            contact = Image.new("RGB", (before.width * 3, before.height))
            contact.paste(before, (0, 0))
            contact.paste(after, (before.width, 0))
            contact.paste(diff, (before.width * 2, 0))
            contact.save(output / f"compare--{name}", optimize=True)
    report = {
        "schema_version": 1, "measurement_type": "pixel difference; not aesthetic quality",
        "baseline_revision": a.get("revision"), "candidate_revision": b.get("revision"),
        "browser": a["browser"], "screenshots_compared": len(rows), "comparisons": rows,
    }
    (output / "comparison.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# Порівняння кадрів ПБТ (не оцінка краси)",
        "",
        "Той самий Chromium, reduced-motion, в'юпорти й назви секцій. Кожен PNG перевірено за SHA-256.",
        "Середня абсолютна різниця яскравості (0–255) і частка пікселів із різницею ≥16 — **описові виміри**.",
        "**Менша або більша різниця не означає кращий дизайн.** Додатково потрібен людський огляд.",
        "",
        "| Кадр | Δ яскравості | Змінено ≥16 |",
        "|---|---:|---:|",
    ]
    for row in rows:
        lines.append(f"| {row['filename']} | {row['mean_absolute_luma_difference']:.3f} | {row['changed_pixel_fraction_above_15'] * 100:.2f}% |")
    lines += ["", "Контакт-листи: **ліворуч baseline, центр candidate, праворуч посилена різниця ×4**.",
              "Посилення застосовано **лише** до третьої панелі."]
    lines.extend(f"- [{row['filename']}](compare--{row['filename']})" for row in rows
                 if (row["viewport"], row["section"]) in PREVIEWS)
    (output / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("output", type=Path, nargs="?", default=Path("artifacts/diff"))
    args = parser.parse_args()
    try:
        result = compare(args.baseline, args.candidate, args.output)
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(1, f"FAIL: {exc}\n")
    print(f"Порівняно: {result['screenshots_compared']} PNG | {args.output / 'comparison.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
