"""Public identity must match the supplied company details, including no-JS metadata.

These checks do not approve tariffs, transferred media rights, or a production
domain. Internal PBT protocol identifiers remain a compatibility contract.
"""
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
PHONE = '+380675550317'
EMAIL = 'plainbud@gmail.com'
IBAN = 'UA393077700000026008411259048'


class Document(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.nodes, self.jsonld, self.title = [], [], []
        self._script, self._title = None, False
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        self.nodes.append((tag, values))
        if tag == 'script' and values.get('type') == 'application/ld+json':
            self._script = []
        if tag == 'title':
            self._title = True

    def handle_data(self, value):
        if self._script is not None:
            self._script.append(value)
        if self._title:
            self.title.append(value)

    def handle_endtag(self, tag):
        if tag == 'script' and self._script is not None:
            self.jsonld.append(json.loads(''.join(self._script)))
            self._script = None
        if tag == 'title':
            self._title = False


def business():
    return json.loads((ROOT / 'config/business.json').read_text(encoding='utf-8'))


def test_company_details_match_the_supplied_identity():
    public = {k: v for k, v in business().items() if k != '_status'}
    assert public['brand']['name'] == 'ПЛЕЙНБУД'
    assert public['brand']['alternateName'] == 'PLAINBUD'
    assert public['legalName'] == 'ТОВ «ПЛЕЙНБУД»'
    assert public['edrpou'] == '45318076'
    assert public['contacts']['phone'] == PHONE
    assert public['contacts']['email'] == EMAIL
    address = public['address'].casefold()
    assert all(part in address for part in ('36022', 'полтава', 'небесної сотні'))
    assert re.search(r'69\s*[-–]?\s*б\b', address)
    assert public['director'] == 'Любашевський Дмитро Васильович'
    assert public['responsiblePerson'] == public['director']
    assert public['bank'] == {'name': 'АТ «А-БАНК»', 'iban': IBAN}
    serialized = json.dumps(public, ensure_ascii=False)
    for retired in ('45383082', '+380978637777', '+380958637777', 'Довженка', 'ПолтаваБудТехніка'):
        assert retired not in serialized, retired


def test_supplied_iban_has_valid_ukrainian_length_and_checksum():
    """Checks transcription integrity only; checksum does not prove account ownership."""
    iban = business()['bank']['iban']
    assert iban == IBAN
    assert re.fullmatch(r'UA[0-9]{27}', iban)
    rearranged = iban[4:] + iban[:4]
    digits = ''.join(str(ord(c) - 55) if c.isalpha() else c for c in rearranged)
    assert int(digits) % 97 == 1


def test_unconfirmed_domain_and_social_accounts_are_not_inherited():
    source = business()
    assert source.get('url') is None
    for field in ('phone2', 'telegram', 'viber', 'whatsapp', 'instagram', 'tiktok', 'facebook', 'youtube'):
        assert source['contacts'].get(field) is None, field
    doc = Document((ROOT / 'web/index.html').read_text(encoding='utf-8'))
    for entry in doc.jsonld:
        if entry.get('@type') == 'LocalBusiness':
            assert not entry.get('url')
            assert not entry.get('sameAs')
    links = [attrs.get('href', '') for tag, attrs in doc.nodes if tag in ('a', 'link')]
    assert not any('pbt-spectehnika.com.ua' in value for value in links)


def test_search_metadata_and_no_javascript_contacts_match_plainbud():
    source = business()
    doc = Document((ROOT / 'web/index.html').read_text(encoding='utf-8'))
    assert 'ПЛЕЙНБУД' in ''.join(doc.title)
    local = [entry for entry in doc.jsonld if entry.get('@type') == 'LocalBusiness']
    assert len(local) == 1
    assert local[0]['name'] == source['legalName']
    phones = local[0]['telephone']
    assert set(phones if isinstance(phones, list) else [phones]) == {PHONE}
    assert local[0]['email'] == EMAIL
    links = [attrs.get('href', '') for tag, attrs in doc.nodes if tag == 'a']
    assert {value for value in links if value.startswith('tel:')} == {'tel:' + PHONE}
    assert 'mailto:' + EMAIL in links
    meta = {attrs.get('property', attrs.get('name')): attrs.get('content')
            for tag, attrs in doc.nodes if tag == 'meta'}
    assert 'ПЛЕЙНБУД' in meta['og:title']
    assert meta['og:image'].endswith('/og-plainbud.jpg')
    assert meta['theme-color'] == '#0D6AE0'


def test_public_brand_assets_exist_and_retired_logos_are_not_referenced():
    doc = Document((ROOT / 'web/index.html').read_text(encoding='utf-8'))
    assets = [attrs.get(key, '') for _, attrs in doc.nodes for key in ('src', 'href', 'poster', 'content')
              if '/media/logo/' in '/' + attrs.get(key, '')]
    assert any(value.endswith('/plainbud-logo.webp') for value in assets)
    assert any(value.endswith('/plainbud-logo-nav.webp') for value in assets)
    for value in assets:
        assert not any(old in value for old in ('pbt-logo', 'pbt-mark', 'og-pbt'))
        file = ROOT / 'web' / value.lstrip('/')
        assert file.is_file() and file.stat().st_size > 0, value
    missing = Document((ROOT / 'web/404.html').read_text(encoding='utf-8'))
    assert 'ПЛЕЙНБУД' in ''.join(missing.title)


def test_public_api_serves_the_same_authorized_identity(server):
    with urllib.request.urlopen(server['base'] + '/api/config', timeout=3) as response:
        actual = json.load(response)
    assert actual == {k: v for k, v in business().items() if k != '_status'}
    assert actual['brand']['name'] == 'ПЛЕЙНБУД'
    assert actual['contacts']['phone'] == PHONE
    assert actual['contacts']['email'] == EMAIL
