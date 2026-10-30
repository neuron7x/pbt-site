"""Verify the disclosed security floors and **all** current release hashes in the lock."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_known_advisory_floors_and_complete_hash_lock():
    source = (ROOT / "requirements.in").read_text()
    lines = (ROOT / "requirements.txt").read_text().splitlines()
    heads = [i for i, line in enumerate(lines) if re.match(r"^[a-z][a-z0-9_-]*==", line)]
    sections = {}
    for idx, start in enumerate(heads):
        end = heads[idx + 1] if idx + 1 < len(heads) else len(lines)
        name, rhs = lines[start].split("==", 1)
        version = rhs.split()[0]
        digests = re.findall(r"--hash=sha256:([0-9a-f]{64})", "\n".join(lines[start:end]))
        sections[name] = (version, digests)
    assert len(sections) == len(heads)  # One unique pin per package
    for name, floor, count in (("pillow", (13, 0, 0), 83), ("pytest", (9, 0, 3), 2)):
        version, hashes = sections[name]
        assert f"{name}=={version}" in source.splitlines()
        assert tuple(map(int, version.split("."))) >= floor
        assert len(hashes) == count and len(hashes) == len(set(hashes))
    assert "42d63be3af4f9b951b199b0a9d23365d37ab14687e6d77b74940432c8515c4ca" in sections["pillow"][1]
    assert "cdcd1ba258178f7356d74170c9a81ba4eab6a5d55748bc402a5a2a6fe6be3510" in sections["pillow"][1]
    assert "2c5efc453d45394fdd706ade797c0a81091eccd1d6e4bccfcd476e2b8e0ab5d9" in sections["pytest"][1]
