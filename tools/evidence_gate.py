#!/usr/bin/env python3
"""Independent, fail-closed verification of screenshot and media evidence.

Verify artifact bytes and measured provenance after capture, not merely the
producer's exit code. No deployment authorization or field-CWV claims.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path

if __package__:
    from . import media_budget, visual_contract as vc
else:
    import media_budget
    import visual_contract as vc

ROOT = Path(__file__).resolve().parent.parent


def _load_json(path: Path, failures: list[str], *, loader=json.loads):
    try:
        value = loader(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("top-level JSON is not an object")
        return value
    except (OSError, ValueError, UnicodeError) as exc:
        failures.append(f"{path}: {type(exc).__name__}: {exc}")
        return None


def _sha256(path: Path):
    h = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_evidence(
    shots: Path, media_report: Path, media_root: Path,
    budget_path: Path, expected_sha: str,
) -> dict:
    failures: list[str] = []
    expected_sha = (expected_sha or "").strip()
    if not re.fullmatch(r"[0-9a-f]{40}", expected_sha):
        failures.append("Expected immutable 40-character HEAD SHA is missing or invalid")
    manifest_path = shots / "manifest.json"
    report = _load_json(manifest_path, failures)
    media = _load_json(media_report, failures)
    captures = []
    if report is not None:
        if report.get("revision") != expected_sha:
            failures.append("Screenshot revision differs from tested checkout SHA")
        if report.get("measurement_type") != "laboratory screenshot audit; NOT field Core Web Vitals":
            failures.append("Screenshot measurement type changed or absent")
        if any(report.get(key) is not None for key in
               ("field_lcp_ms", "field_inp_ms", "field_cls")):
            failures.append("Screenshots must not claim field Core Web Vitals")
        if not isinstance(report.get("failures"), list) or report["failures"]:
            failures.append("Capture producer reported errors or an invalid failures field")
        if not isinstance(report.get("browser"), dict) or (
            report["browser"].get("engine") != "chromium"
            or not report["browser"].get("version")
        ):
            failures.append("Missing genuine Chromium capture provenance")
        captures = report.get("captures")
        if not isinstance(captures, list) or not all(isinstance(c, dict) for c in captures):
            failures.append("Screenshot capture records missing or malformed")
            captures = []
        else:
            try:
                failures.extend(vc.verify_capture_manifest(report, shots))
            except (OSError, ValueError, TypeError, KeyError) as exc:
                failures.append(f"Screenshot manifest could not be verified: {exc}")
            for record in captures:
                name = record.get("filename")
                if isinstance(name, str) and (shots / name).is_symlink():
                    failures.append("Symlink screenshot is forbidden: " + name)
        expected_profiles = {(theme, vp[0]) for theme in vc.THEMES for vp in vc.VIEWPORTS}
        profiles = report.get("viewports")
        if not isinstance(profiles, list) or not all(isinstance(p, dict) for p in profiles):
            failures.append("Viewport profiles missing or malformed")
        else:
            actual_profiles = [(p.get("theme"), p.get("viewport")) for p in profiles]
            if len(actual_profiles) != len(expected_profiles) or set(actual_profiles) != expected_profiles:
                failures.append("Incomplete, duplicated or unexpected viewport profiles")
            for profile in profiles:
                probe = profile.get("probe")
                if not isinstance(probe, dict) or probe.get("theme") != profile.get("theme"):
                    failures.append("Viewport theme/probe provenance mismatch")
                else:
                    failures.extend(vc.audit_layout(probe))
    if media is not None:
        if not media_root.is_dir() or not budget_path.is_file():
            failures.append("Media root or canonical budget file is missing")
        else:
            budgets = _load_json(budget_path, failures, loader=media_budget.parse_budget)
            if budgets is not None:
                try:
                    recalculated = media_budget.audit_media(media_root, budgets)
                    if media != recalculated:
                        failures.append("Stored media inventory/budget differs from independently recomputed bytes")
                    if recalculated.get("failures"):
                        failures.extend(recalculated["failures"])
                except (OSError, ValueError, TypeError, KeyError) as exc:
                    failures.append(f"Media budget recomputation failed: {exc}")
        if media.get("measurement_type") != "repository file sizes, not network transfer":
            failures.append("Media audit falsely claims page-transfer measurements")
    digests = {}
    for name, path in (("shots_manifest", manifest_path), ("media_report", media_report)):
        if path.is_file() and not path.is_symlink():
            digests[name] = {"sha256": _sha256(path), "bytes": path.stat().st_size}
    return {
        "schema_version": 1,
        "expected_head_sha": expected_sha,
        "measurement_type": "independent evidence integrity, NOT release approval",
        "screenshot_count": len(captures),
        "evidence": digests,
        "failures": failures,
        "ok": not failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shots", type=Path, default=ROOT / "artifacts/shots")
    parser.add_argument("--media-report", type=Path, default=ROOT / "artifacts/media-budget.json")
    parser.add_argument("--media-root", type=Path, default=ROOT / "web/media")
    parser.add_argument("--budget", type=Path, default=ROOT / "config/visual-budgets.json")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/evidence-verification.json")
    parser.add_argument("--expected-sha", default=os.environ.get("PBT_HEAD_SHA", ""))
    args = parser.parse_args()
    result = verify_evidence(args.shots, args.media_report, args.media_root, args.budget, args.expected_sha)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(f"Evidence: {result['screenshot_count']} PNG; "
          f"failures={len(result['failures'])}; {args.output}")
    for problem in result["failures"]:
        print("FAIL:", problem, file=sys.stderr)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
