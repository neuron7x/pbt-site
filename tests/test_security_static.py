"""Adversarial mutation tests for the narrow PBT AST static security guard."""
from pathlib import Path

from tools import security_static as guard

ROOT = Path(__file__).resolve().parent.parent


def test_real_server_ops_tree_is_parseable_and_has_no_denied_calls():
    evidence = guard.run(['server', 'ops'])
    assert evidence['files_scanned'] >= 4
    assert evidence['findings'] == [], evidence


def test_mutant_eval_subprocess_pickle_and_unbounded_webhook_are_rejected():
    cases = [
        "eval('1 + 1')\n",
        "exec('print(1)')\n",
        "import os\nos.system('echo unsafe')\n",
        "import subprocess\nsubprocess.run('echo bad', shell=True)\n",
        "import pickle\npickle.loads(b'bad')\n",
        "import urllib.request\nurllib.request.urlopen('https://example.invalid')\n",
        "import requests\nrequests.post('https://example.invalid')\n",
        "import urllib.request\nopener = urllib.request.build_opener()\nopener.open('https://example.invalid')\n",
        "from urllib.request import build_opener\nclient = build_opener()\nclient.open('https://example.invalid')\n",
        "def func(:\n",
    ]
    for code in cases:
        assert guard.scan_source(code, 'deliberate_mutant.py'), code


def test_bounded_http_and_safe_standard_library_operations_remain_allowed():
    code = """
import urllib.request
import sqlite3
def retrieve(url):
    with urllib.request.urlopen(url, timeout=5) as response:
        return response.status
"""
    assert guard.scan_source(code, 'safe.py') == []


def test_custom_opener_is_allowed_only_with_explicit_socket_timeout():
    source = """
import urllib.request
opener = urllib.request.build_opener()
with opener.open('https://example.invalid', timeout=3) as response:
    print(response.status)
"""
    assert guard.scan_source(source, 'bounded_custom_opener.py') == []
