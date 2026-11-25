"""Вхідні числа моделі tools/sky.py звірено з першоджерелами 25.11.2026; тут вони закріплені, щоб тиха правка коду це зламала.

Значення нижче виписано з самих джерел (docs/BIBLIOGRAPHY.md, розділ 5), а не з коду:
  Pope & Fry 1997 — файл даних omlc.org/spectra/water/data/pope97.txt, одиниці 1/см;
  Wyman, Sloan, Shirley 2013 — таблиця параметрів багатопелюсткового наближення, γ і δ — обернені ширини;
  Kasten & Young 1989 — формула (3): 1 / (cos z + 0,50572·(96,07995° − z)^−1,6364).
"""
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
import sky  # noqa: E402

POPE_FRY_PER_CM = {380: 0.0001137, 400: 0.0000663, 420: 0.0000454, 440: 0.0000635, 460: 0.0000979, 480: 0.000127, 500: 0.000204,
                   520: 0.000409, 540: 0.000474, 560: 0.000619, 580: 0.000896, 600: 0.002224, 620: 0.002755, 640: 0.003108,
                   660: 0.0041, 680: 0.00465, 700: 0.00624}
# (амплітуда α, центр β нм, γ для λ < β, δ для λ ≥ β)
WYMAN = {'x': [(0.362, 442.0, 0.0624, 0.0374), (1.056, 599.8, 0.0264, 0.0323), (-0.065, 501.1, 0.0490, 0.0382)],
         'y': [(0.821, 568.8, 0.0213, 0.0247), (0.286, 530.9, 0.0613, 0.0322)],
         'z': [(1.217, 437.0, 0.0845, 0.0278), (0.681, 459.0, 0.0385, 0.0725)]}


def test_water_absorption_table_matches_pope_and_fry_1997():
    table = dict(sky.WATER)
    assert len(POPE_FRY_PER_CM) == 17
    for nm, per_cm in POPE_FRY_PER_CM.items():
        assert math.isclose(table[nm], per_cm * 100, abs_tol=5.1e-5), (nm, table[nm], per_cm * 100)   # 1/см → 1/м, округлення до 4 знаків


def test_colour_matching_fit_matches_wyman_sloan_shirley_2013():
    def reference(lobes, nm):
        return sum(a * math.exp(-0.5 * ((nm - b) * (g if nm < b else d)) ** 2) for a, b, g, d in lobes)
    worst = 0.0
    for nm in sky.WL:
        got = sky.cmf(nm)
        for value, key in zip(got, 'xyz'):
            worst = max(worst, abs(value - reference(WYMAN[key], nm)))
    assert worst < 4e-3, worst                    # код тримає ширини як σ = 1/γ, округлені до 0,1 нм — звідси залишок
    assert sum(len(v) for v in WYMAN.values()) * 4 == 28


def test_air_mass_formula_matches_kasten_and_young_1989():
    for z in (0.0, 30.0, 60.0, 75.0, 85.0, 89.0):
        reference = 1.0 / (math.cos(math.radians(z)) + 0.50572 * (96.07995 - z) ** -1.6364)
        assert math.isclose(sky.air_mass(z), reference, rel_tol=1e-12), z
    assert math.isclose(sky.air_mass(0.0), 1.0, abs_tol=2e-3)
    assert 36 < sky.air_mass(89.9) < 40           # біля обрію ≈ 38


def test_rayleigh_fit_has_the_coefficients_attributed_to_hansen_and_travis():
    u = 0.55
    assert math.isclose(sky.tau_rayleigh(550), 0.008569 * u ** -4 * (1 + 0.0113 * u ** -2 + 0.00013 * u ** -4), rel_tol=1e-12)
