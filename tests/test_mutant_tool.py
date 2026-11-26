"""tools/mutant_new.py — каталог мутантів канонічний і кожен запис застосовний (find рівно раз у своєму файлі)."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
import mutant_new  # noqa: E402


def test_catalog_is_canonical_and_every_edit_applies():
    r = subprocess.run([sys.executable, 'tools/mutant_new.py', 'check'], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout


@pytest.mark.parametrize('bad, why', [
    ({'id': 'M-A', 'edits': [{'file': 'web/js/site.js', 'find': 'ЦЬОГО РЯДКА НЕМА', 'replace': 'x'}], 'oracle': ['t']}, '0 раз'),
    ({'id': 'M-A', 'edits': [{'file': 'web/js/site.js', 'find': 'const', 'replace': 'x'}], 'oracle': ['t']}, 'має 1'),
    ({'id': 'M-A', 'edits': [], 'oracle': []}, 'без оракула'),
    ({'id': 'M-A', 'expected': 'UNTESTABLE', 'reason': 'бо'}, 'UNTESTABLE'),
])
def test_problems_are_caught(bad, why):
    assert any(why in p for p in mutant_new.problems({'mutants': [bad]})), why


def test_duplicate_ids_and_non_canonical_order_are_caught():
    d = {'schema': 's', 'mutants': [{'id': 'M-B', 'expected': 'UNTESTABLE', 'reason': 'x' * 40},
                                     {'id': 'M-A', 'expected': 'UNTESTABLE', 'reason': 'x' * 40}]}
    assert json.dumps(d, ensure_ascii=False, indent=1) + '\n' != mutant_new.canonical(d)
    assert [m['id'] for m in json.loads(mutant_new.canonical(d))['mutants']] == ['M-A', 'M-B']
    assert any('повторюється' in p for p in mutant_new.problems({'mutants': d['mutants'] * 2}))


def test_publish_rejects_a_stale_writer(tmp_path):
    path = tmp_path / 'catalogue.json'
    path.write_text('old', encoding='utf-8')
    assert mutant_new.publish(path, 'old', 'first')
    assert not mutant_new.publish(path, 'old', 'second')
    assert path.read_text(encoding='utf-8') == 'first'


@pytest.mark.parametrize(('rows', 'accepted'), [
    ([], False),
    ([{'id': 'M-other', 'verdict': 'KILLED'}], False),
    ([{'id': 'M-test', 'verdict': 'UNTESTABLE'}], False),
    ([{'id': 'M-test', 'verdict': 'KILLED'}], True),
])
def test_confirmation_requires_explicit_kill(monkeypatch, rows, accepted):
    def run(command, **kwargs):
        report = Path(command[command.index('--out') + 1])
        report.write_text(json.dumps({'status': 'PASS', 'results': rows}), encoding='utf-8')
        return subprocess.CompletedProcess(command, 0, '', '')

    monkeypatch.setattr(mutant_new.subprocess, 'run', run)
    assert mutant_new.confirmed_kill('{}', 'M-test') is accepted

@pytest.mark.parametrize('args', [['--only'], ['--only', 'M-missing']])
def test_runner_rejects_empty_or_unknown_selector(args):
    result = subprocess.run([sys.executable, str(ROOT / 'tools/mutation_run.py'), *args],
                            cwd=ROOT, text=True, capture_output=True)
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert 'error:' in result.stderr and 'PASS' not in result.stdout


def test_publish_does_not_treat_crlf_as_the_same_bytes(tmp_path):
    path = tmp_path / 'catalogue.json'
    path.write_bytes(b'old\r\n')
    assert not mutant_new.publish(path, 'old\n', 'changed\n')
    assert path.read_bytes() == b'old\r\n'


def test_mutation_targets_must_be_relative_to_the_tree(tmp_path):
    source = tmp_path / 'sample.txt'
    source.write_text('original', encoding='utf-8')
    assert mutant_new.mutation_target(tmp_path, source.name) == source
    with pytest.raises(ValueError, match='invalid_mutation_path'):
        mutant_new.mutation_target(tmp_path, str(source))
    assert source.read_text(encoding='utf-8') == 'original'
