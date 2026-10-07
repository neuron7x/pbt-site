"""Секція «Масштаб»: ілюстративна зйомка з Wikimedia Commons.
Інваріанти: ліцензія кожного джерела вільна; атрибуція (автор, назва, ліцензія з посиланнями) біля КОЖНОГО кадру;
сторінка прямо каже, що це не техніка ПБТ; web/js/cine.js не розходиться з config/stock.json; кожен кліп існує в обох профілях."""
import json, re, subprocess, sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / 'config' / 'stock.json').read_text(encoding='utf-8'))
CINE_JS = (ROOT / 'web' / 'js' / 'cine.js').read_text(encoding='utf-8')
CINE = json.loads(re.search(r'window\.PBT_CINE = (\{.*\});', CINE_JS, re.S).group(1))
FREE = {'CC0', 'Public domain', 'CC BY 3.0', 'CC BY 4.0', 'CC BY-SA 3.0', 'CC BY-SA 4.0'}


def test_manifest_licenses_are_free_and_complete():
    assert set(CFG['allowed_licenses']) <= FREE, 'allowed_licenses розширено поза вільні'
    used = {c['source'] for c in CFG['chapters']}
    assert used, 'жодного розділу — секція порожня'
    for key in used:
        s = CFG['sources'][key]
        assert s['license'] in FREE, (key, s['license'])
        assert s['page'].startswith('https://commons.wikimedia.org/wiki/File:'), key
        assert s['license_url'].startswith('https://creativecommons.org/'), key
        assert s['author'].strip() and s['title'].strip(), key
        assert re.fullmatch(r'[0-9a-f]{64}', s['sha256']), key


def test_generated_js_matches_manifest():
    """cine.js генерується; ручна правка або забута регенерація = розбіжність атрибуції з джерелом."""
    expected = [{'id': c['id'], 'word': c['word'], 'line': c['line'],
                 'credit': {k: CFG['sources'][c['source']][k] for k in ('title', 'author', 'license', 'license_url', 'page')}}
                for c in CFG['chapters']]
    assert CINE['chapters'] == expected


@pytest.mark.parametrize('cid', [c['id'] for c in CFG['chapters']])
def test_every_clip_exists_in_both_profiles(cid):
    d = ROOT / 'web' / 'media' / 'cine'
    for prof in ('w', 'm'):
        for ext in ('mp4', 'webm', 'webp'):
            f = d / f'{cid}-{prof}.{ext}'
            assert f.exists() and f.stat().st_size > 10_000, f
        assert (d / f'{cid}-{prof}.mp4').stat().st_size < (4.2 if prof == 'w' else 1.6) * 1024 * 1024, f'{cid}-{prof}: стеля бітрейту зламана'


def test_stock_tool_fails_closed_on_forbidden_license(tmp_path):
    """Мутант даних: ліцензія «All rights reserved» → tools/stock.py --emit падає й не пише cine.js."""
    cfg = json.loads(json.dumps(CFG)); first = CFG['chapters'][0]['source']
    cfg['sources'][first]['license'] = 'All rights reserved'
    root = tmp_path / 'r'; (root / 'config').mkdir(parents=True); (root / 'tools').mkdir(); (root / 'web' / 'js').mkdir(parents=True)
    (root / 'config' / 'stock.json').write_text(json.dumps(cfg), encoding='utf-8')
    (root / 'tools' / 'stock.py').write_text((ROOT / 'tools' / 'stock.py').read_text(encoding='utf-8'), encoding='utf-8')
    r = subprocess.run([sys.executable, str(root / 'tools' / 'stock.py'), '--emit'], capture_output=True, text=True)
    assert r.returncode != 0 and 'не дозволена' in r.stderr, r.stderr
    assert not (root / 'web' / 'js' / 'cine.js').exists()


def _credits(pg):
    return pg.evaluate("""[...document.querySelectorAll('#cine .cine__ch')].map(li => ({
        links: [...li.querySelectorAll('.cine__cr a')].map(a => a.href), text: li.querySelector('.cine__cr').textContent}))""")


def test_page_attributes_every_frame_and_disclaims_fleet(page_factory):
    pg = page_factory()
    cr = _credits(pg)
    assert len(cr) == len(CFG['chapters'])
    for c, ch in zip(cr, CFG['chapters']):
        s = CFG['sources'][ch['source']]
        assert s['page'] in c['links'], (s['page'], c['links'])
        assert s['license_url'] in c['links'], c
        assert s['author'] in c['text'] and s['license'] in c['text'], c
    note = pg.locator('#masshtab .cine__note')
    assert note.is_visible() and 'не техніка ПБТ' in note.text_content()
    assert 'Wikimedia Commons' in pg.locator('.foot__legal').text_content()


def test_stage_plays_and_switches_clip_on_scroll(page_factory):
    pg = page_factory()
    assert pg.evaluate("document.getElementById('masshtab').classList.contains('is-pinned')")
    top = pg.evaluate("document.getElementById('cine-karier').offsetTop + document.getElementById('masshtab').offsetTop")
    pg.evaluate(f"scrollTo({{top: {top}, behavior: 'instant'}})")
    pg.wait_for_function("() => { const v = document.querySelector('#masshtab .cine__v.is-on'); return v && !v.paused && v.currentTime > .2 && /karier-w\\.(webm|mp4)$/.test(v.currentSrc) }", timeout=8000)
    last = CFG['chapters'][-1]['id']
    pg.evaluate(f"document.getElementById('cine-{last}').scrollIntoView({{block: 'center'}})")
    pg.wait_for_function(f"() => {{ const v = document.querySelector('#masshtab .cine__v.is-on'); return v && /{last}-w\\.(webm|mp4)$/.test(v.currentSrc) && !v.paused }}", timeout=8000)
    assert pg.evaluate("document.querySelectorAll('#masshtab .cine__v.is-on').length") == 1
    assert pg.evaluate(f"document.querySelector('#cineRail a.is-on').getAttribute('href')") == f'#cine-{last}'
    pg.evaluate("scrollTo({top: 0, behavior: 'instant'})"); pg.wait_for_timeout(500)
    assert pg.evaluate("[...document.querySelectorAll('#masshtab .cine__v')].every(v => v.paused)"), 'сцена грає поза кадром'


def test_phone_takes_portrait_cut(page_factory):
    pg = page_factory(390, 844, mobile=True)
    pg.evaluate("document.getElementById('cine-voda').scrollIntoView({block: 'center'})")
    pg.wait_for_function("() => { const v = document.querySelector('#masshtab .cine__v.is-on'); return v && /voda-m\\.(webm|mp4)$/.test(v.currentSrc) }", timeout=8000)


def test_reduced_motion_is_static_poster_grid(page_factory):
    pg = page_factory(reduced=True)
    assert not pg.evaluate("document.getElementById('masshtab').classList.contains('is-pinned')")
    assert pg.evaluate("[...document.querySelectorAll('#masshtab video')].every(v => !v.currentSrc)")
    imgs = pg.locator('#cine figure img')
    assert imgs.count() == len(CFG['chapters'])
    imgs.first.scroll_into_view_if_needed(); pg.wait_for_timeout(300)
    assert pg.evaluate("document.querySelector('#cine figure img').naturalWidth") > 0


def test_look_lut_is_valid_and_wired():
    """config/pbt-look.cube: 33³, у [0,1], сіра вісь монотонна (S-крива без інверсій), чорне/біле не зрізані;
    LUT детермінований (tools/lut.py відтворює файл байт-у-байт) і підключений в обидва конвеєри."""
    import numpy as np
    cube = (ROOT / 'config' / 'pbt-look.cube').read_text(encoding='ascii')
    assert 'LUT_3D_SIZE 33' in cube
    v = np.loadtxt(cube.splitlines()[4:]).reshape(33, 33, 33, 3)
    assert v.min() >= 0 and v.max() <= 1
    grey = np.array([v[i, i, i] for i in range(33)]) @ [0.2126, 0.7152, 0.0722]
    assert np.all(np.diff(grey) > 0), 'сіра вісь немонотонна'
    assert grey[0] < 0.03 and grey[-1] > 0.95, (grey[0], grey[-1])
    r = subprocess.run([sys.executable, str(ROOT / 'tools' / 'lut.py')], capture_output=True, text=True)
    assert r.returncode == 0 and (ROOT / 'config' / 'pbt-look.cube').read_text(encoding='ascii') == cube, 'LUT не відтворюється з формул'
    for tool in ('stock.py', 'media.py'):
        assert "lut3d=file={LUT}" in (ROOT / 'tools' / tool).read_text(encoding='utf-8'), tool
