"""Minimum verified dependency security floors: no known vulnerable pinned toolchain."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def test_known_advisory_floors_and_consistent_locked_versions():
    source = (ROOT / 'requirements.in').read_text()
    lock = (ROOT / 'requirements.txt').read_text()
    for name, floor in (('pillow', (13, 0, 0)), ('pytest', (9, 0, 3))):
        direct = re.search(rf'^{name}==([0-9.]+)$', source, re.M)
        pinned = re.search(rf'^{name}==([0-9.]+) \\\n', lock, re.M)
        assert direct and pinned and direct.group(1) == pinned.group(1)
        assert tuple(map(int, pinned.group(1).split('.'))) >= floor
        section = lock[pinned.start():]
        following = re.search(r'^\\w+==', section[len(pinned.group(0)):], re.M)
        if following:
            section = section[:len(pinned.group(0))+following.start()]
        digests = re.findall(r'--hash=sha256:([0-9a-f]{64})', section)
        assert len(digests) >= 2 and len(digests) == len(set(digests))
    assert '42d63be3af4f9b951b199b0a9d23365d37ab14687e6d77b74940432c8515c4ca' in lock
    assert '2c5efc453d45394fdd706ade797c0a81091eccd1d6e4bccfcd476e2b8e0ab5d9' in lock
