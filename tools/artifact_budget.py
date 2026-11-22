#!/usr/bin/env python3
"""Fail-closed size and integrity audit for a finished multifile HTML artifact.

Counts actual bytes on disk; no network-transfer or decoded-media claims.
This is a preflight/reporting tool, not a media optimizer or release approval.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

DEFAULT_LIMIT = 64 * 1024 * 1024
MEDIA_SUFFIXES = {".mp4", ".webp", ".png", ".svg", ".jpg", ".webm"}


def audit_artifact(root: Path, limit: int = DEFAULT_LIMIT) -> dict:
    if type(limit) is not int or limit <= 0:
        raise ValueError("limit must be a positive integer")
    if not root.is_dir() or root.is_symlink():
        raise ValueError("artifact root absent or symlinked")
    entries = []
    root_real = root.resolve(strict=True)
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError("artifact contains symlink: " + path.relative_to(root).as_posix())
        if not path.is_file():
            continue
        if not path.resolve(strict=True).is_relative_to(root_real):
            raise ValueError("artifact path escapes root")
        name = path.relative_to(root).as_posix()
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        entries.append({"path": name, "bytes": path.stat().st_size, "sha256": digest.hexdigest()})
    if not entries or not any(e["path"] == "index.html" for e in entries):
        raise ValueError("artifact missing index.html or has no files")
    total = sum(e["bytes"] for e in entries)
    return {
        "schema_version": 1,
        "measurement_type": "on-disk artifact bytes; not transfer or render metrics",
        "limit_bytes": limit,
        "total_bytes": total,
        "over_budget_bytes": max(0, total - limit),
        "ok": total <= limit,
        "asset_count": len(entries),
        "media_bytes": sum(e["bytes"] for e in entries if Path(e["path"]).suffix.lower() in MEDIA_SUFFIXES),
        "files": entries,
        "largest": sorted(entries, key=lambda e: (-e["bytes"], e["path"]))[:12],
    }


def _save_report(result: dict, report_path: Path) -> None:
    """Write complete byte/digest evidence atomically, without following old symlinks."""
    import tempfile
    report_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix="." + report_path.name + ".", suffix=".tmp",
                                dir=report_path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(result, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, report_path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def enforce_artifact_budget(root: Path, report_path: Path,
                            limit: int = DEFAULT_LIMIT) -> dict:
    """Fail a portable export above its exact byte cap, preserving a failure report."""
    result = audit_artifact(root, limit)
    _save_report(result, report_path)
    if not result["ok"]:
        raise ValueError(
            "Multifile artifact exceeds " + str(result["limit_bytes"]) + " bytes by "
            + str(result["over_budget_bytes"]) + " bytes; see " + str(report_path)
        )
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1] / "dist/artifact")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    try:
        result = audit_artifact(args.root, args.limit)
    except (OSError, ValueError) as exc:
        print(json.dumps({"ok": False, "reason": type(exc).__name__, "detail": str(exc)}))
        return 1
    if args.report:
        _save_report(result, args.report)
    print(json.dumps({k: result[k] for k in ("ok", "total_bytes", "limit_bytes",
                                            "over_budget_bytes", "asset_count", "media_bytes")}, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
