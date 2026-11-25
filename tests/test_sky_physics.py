"""Палітра «небо над Полтавою і вода» обчислена моделлю tools/sky.py; тут — умови її спростування й синхронність із CSS."""
import math
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
import sky  # noqa: E402


def test_solar_geometry_matches_closed_form_for_poltava():
    # полудень сонцестояння: h = 90° − φ + δ
    assert math.isclose(sky.sun_elevation(12.0), 90 - sky.LAT + sky.DECL, abs_tol=1e-9)
    # симетрія відносно полудня й монотонне зниження після нього
    assert math.isclose(sky.sun_elevation(7.0), sky.sun_elevation(17.0), abs_tol=1e-9)
    assert sky.sun_elevation(12.0) > sky.sun_elevation(16.0) > sky.sun_elevation(18.0) > 0


def test_rayleigh_optical_depth_follows_inverse_fourth_power():
    # без поправочних членів відношення τ(400)/τ(700) = (700/400)⁴ ≈ 9,38; з поправками — у межах 6 %
    ratio = sky.tau_rayleigh(400) / sky.tau_rayleigh(700)
    assert abs(ratio / (700 / 400) ** 4 - 1) < 0.06
    assert 0.08 < sky.tau_rayleigh(550) < 0.11            # довідкове значення на рівні моря ≈ 0,097


def test_colour_matching_approximation_has_the_cie_peaks():
    ys = [(sky.cmf(nm)[1], nm) for nm in sky.WL]
    assert 550 <= max(ys)[1] <= 560                       # максимум ȳ ≈ 555 нм
    assert 440 <= max((sky.cmf(nm)[2], nm) for nm in sky.WL)[1] <= 450


def test_sky_is_bluer_at_zenith_than_at_horizon_and_at_noon_than_in_evening():
    p = sky.palette()
    by = {m['sec']: m for m in p['moments']}
    for m in p['moments']:
        blues = [s['blue'] for s in m['stops']]
        assert blues == sorted(blues, reverse=True), (m['sec'], blues)   # від зеніту до обрію синя складова лише спадає
        assert 235 <= m['stops'][0]['hue'] <= 275, m                      # зеніт — синій сектор OKLab
    assert by['cina']['stops'][0]['blue'] > by['materialy']['stops'][0]['blue'] > by['geo']['stops'][0]['blue']


def test_water_saturates_and_loses_red_with_depth():
    p = sky.palette()
    sats = [x['sat'] for x in p['water']]
    assert sats == sorted(sats) and len(set(sats)) == len(sats)
    red = lambda d: sum(v for nm, v in zip(sky.WL, sky.water_spectrum(d)) if nm >= 620)
    blue = lambda d: sum(v for nm, v in zip(sky.WL, sky.water_spectrum(d)) if nm <= 490)
    assert red(10) / red(0) < 0.06 < 0.8 < blue(10) / blue(0)             # 10 м води: червоне майже зникло, синє лишилось


def test_oklab_round_trip_and_gamut_fit():
    for rgb in ((0.2, 0.4, 0.9), (0.66, 0.77, 0.92), (0.01, 0.08, 0.2)):
        back = sky.oklab_to_lin(sky.lin_to_oklab(rgb))
        assert all(abs(a - b) < 1e-6 for a, b in zip(rgb, back))
    enc, c = sky.fit(0.85, math.radians(255), 0.4)                        # завелика насиченість мусить стиснутись в охоплення
    assert c < 0.4 and all(0 <= v <= 1 for v in enc)


def test_every_text_role_is_readable_on_every_generated_stop():
    p = sky.palette()
    assert sky.audit(p) == []
    surfaces = [s['hex'] for m in p['moments'] for s in m['stops']] + [x['hex'] for x in p['water'] if x['role'] in ('ice-0', 'ice', 'ice-2', 'pool')]
    assert len(surfaces) == 20
    for surface in surfaces:
        for name, colour in sky.TEXT.items():
            assert sky.contrast(colour, surface) >= (3.0 if name == 'accent' else 4.5), (name, surface)
    assert sky.contrast('#777777', '#FFFFFF') < 4.5 < sky.contrast('#767676', '#FFFFFF')   # оракул контрасту відрізняє відому межу AA


def test_audit_rejects_a_palette_that_breaks_the_model():
    p = sky.palette()
    p['moments'][0]['stops'][0]['blue'] = -1.0
    assert any('не синіший' in line for line in sky.audit(p))
    q = sky.palette()
    q['water'][0]['hex'] = '#3A4B6B'
    assert any('вода' in line for line in sky.audit(q))


def test_css_block_is_exactly_what_the_model_generates():
    css = (ROOT / 'web' / 'css' / 'site.css').read_text(encoding='utf-8')
    assert css.count(sky.BEGIN) == 1 and css.count(sky.END) == 1
    block = css[css.index(sky.BEGIN):css.index(sky.END) + len(sky.END)]
    assert block == sky.css_block(sky.palette())
    assert subprocess.run([sys.executable, 'tools/sky.py', '--check'], cwd=ROOT, capture_output=True).returncode == 0


def test_generation_is_deterministic_across_hash_seeds_and_locales():
    runs = [subprocess.run([sys.executable, '-s', 'tools/sky.py'], cwd=ROOT, capture_output=True,
                           env={'PYTHONHASHSEED': seed, 'PATH': '/usr/bin:/bin', 'LC_ALL': locale})
            for seed, locale in (('0', 'C'), ('1', 'C.UTF-8'), ('4242', 'POSIX'))]
    assert [r.returncode for r in runs] == [0, 0, 0], [r.stderr[-300:] for r in runs]
    outs = {r.stdout for r in runs}
    assert len(outs) == 1
    assert 'roboty' in runs[0].stdout.decode('utf-8') and 'вода' in runs[0].stdout.decode('utf-8')
