"""WEB-07 mechanism: one published catalogue fact, one value. Current quotes require approved terms.

The archival catalogue is an evidence input. Transactional terms belong to the quote workflow.
"""
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent.parent
CATALOG = json.loads((ROOT / 'data/catalog.json').read_text(encoding='utf-8'))
BUSINESS = json.loads((ROOT / 'config/business.json').read_text(encoding='utf-8'))


def _data_js():
    code = ("const fs=require('fs'),vm=require('vm');const w={};vm.runInNewContext(fs.readFileSync('web/js/data.js','utf8'),{window:w});"
            "process.stdout.write(JSON.stringify(w.PBT))")
    return json.loads(subprocess.run(['node', '-e', code], cwd=ROOT, capture_output=True, text=True, timeout=30, check=True).stdout)


def _facts(items):
    return {i['id']: (i.get('unit'), i['name']) for i in items}


def test_fleet_and_material_facts_agree_between_catalog_and_interface():
    data = _data_js()
    assert _facts(data['fleet']) == _facts(CATALOG['fleet'])
    assert _facts(data['materials']) == _facts(CATALOG['materials'])
    assert all('price' not in item for item in data['fleet'] + data['materials'])


def test_business_identity_agrees_between_config_and_interface():
    data = _data_js()['business']
    public = {k: v for k, v in BUSINESS.items() if k != '_status'}
    assert data == public
    assert (ROOT / 'web' / public['logo'].lstrip('/')).is_file(), 'published logo path is dangling'


def test_no_price_is_fabricated_as_zero_or_negative():
    for item in CATALOG['fleet'] + CATALOG['materials']:
        assert item.get('price') is None or (type(item['price']) is int and item['price'] > 0), item['id']
    assert {'trailers', 'priceDate', 'priceSource'}.isdisjoint(_data_js())


def test_catalog_declares_that_its_prices_are_not_yet_owner_approved():
    """Fail the day someone marks B1/B2 approved here without the evidence channel in the assurance ledger."""
    ledger = json.loads((ROOT / 'assurance/ledger.json').read_text(encoding='utf-8'))
    assert {o['obligation_id']: o['disposition'] for o in ledger['obligations']}['OPS-06'] == 'BLOCKED_EXTERNAL'
