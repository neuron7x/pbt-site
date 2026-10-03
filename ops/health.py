#!/usr/bin/env python3
"""Сторож: код 0 лише якщо /api/health відповів 200 {ok: true} за ≤ 5 с. Будь-що інше (відмова, таймаут, 503) → код 1."""
import json, os, sys, urllib.request
URL = os.environ.get('HEALTH_URL', 'http://127.0.0.1:4180/api/health')
try:
    with urllib.request.urlopen(URL, timeout=5) as r:
        ok = r.status == 200 and json.loads(r.read()).get('ok') is True
except Exception as e:  # noqa: BLE001
    print(f'health FAIL: {type(e).__name__}: {e}', file=sys.stderr); sys.exit(1)
print('health', 'OK' if ok else 'FAIL'); sys.exit(0 if ok else 1)
