"""ADV-02: the runner itself must not be able to report a kill it did not observe."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import mutation_run as mr

ROOT = Path(__file__).resolve().parents[1]


def _tree(tmp_path, source='VALUE = 1\n', test='from target import VALUE\n\ndef test_value():\n    assert VALUE == 1\n'):
    (tmp_path / 'target.py').write_text(source)
    (tmp_path / 'test_target.py').write_text(test)
    return tmp_path


def _mutant(find='VALUE = 1', replace='VALUE = 2', oracle=('test_target.py',)):
    return {'id': 'M', 'edits': [{'file': 'target.py', 'find': find, 'replace': replace}], 'oracle': list(oracle)}


def test_detected_fault_is_killed_and_tree_is_restored(tmp_path):
    tree = _tree(tmp_path)
    assert mr.execute(_mutant(), tree, 60)['verdict'] == 'KILLED'
    assert (tree / 'target.py').read_text() == 'VALUE = 1\n'


def test_undetected_fault_survives(tmp_path):
    assert mr.execute(_mutant(replace='VALUE = 1 # same'), _tree(tmp_path), 60)['verdict'] == 'SURVIVED'


def test_edit_that_does_not_apply_is_invalid_not_killed(tmp_path):
    assert mr.execute(_mutant(find='ABSENT'), _tree(tmp_path), 60)['verdict'] == 'INVALID'


def test_ambiguous_edit_is_invalid(tmp_path):
    tree = _tree(tmp_path, source='VALUE = 1\nVALUE = 1\n')
    assert mr.execute(_mutant(), tree, 60)['verdict'] == 'INVALID'


def test_collection_error_is_invalid_not_killed(tmp_path):
    assert mr.execute(_mutant(oracle=('no_such_test_file.py',)), _tree(tmp_path), 60)['verdict'] == 'INVALID'


def test_hang_is_not_reported_as_a_kill(tmp_path):
    tree = _tree(tmp_path, test='import time\nfrom target import VALUE\n\ndef test_value():\n    time.sleep(30 if VALUE == 2 else 0)\n')
    assert mr.execute(_mutant(), tree, 2)['verdict'] == 'INVALID'


def test_full_run_refuses_a_node_oracle_that_fails_on_clean_code(tmp_path):
    catalog = tmp_path / 'catalog.json'
    catalog.write_text(json.dumps({'mutants': [{'id': 'N', 'task': 'X', 'edits': [{'file': 'README.md', 'find': 'ABSENT', 'replace': 'x'}],
                                                'oracle': ['node', '--test', 'tests/missing.test.cjs']}]}))
    assert mr.main(['--catalog', str(catalog), '--jobs', '1']) == 1


def test_catalog_shape_is_complete():
    catalog = json.loads((ROOT / 'config/mutation-catalog.json').read_text(encoding='utf-8'))
    ids = [m['id'] for m in catalog['mutants']]
    assert len(ids) == len(set(ids)) >= 40
    for m in catalog['mutants']:
        if m.get('expected') == 'UNTESTABLE':
            assert len(m['reason']) > 20
        else:
            assert m['edits'] and m['oracle'], m['id']
            for edit in m['edits']:
                assert edit['find'] != edit['replace'], m['id']
                assert (ROOT / edit['file']).read_text(encoding='utf-8').count(edit['find']) == 1, m['id']
