"""ADV-05: "today" for a lead date is the Kyiv civil date on both sides, regardless of host TZ."""
import importlib.util
from datetime import datetime, timezone
from pathlib import Path
import os
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parent.parent
VECTORS = [
    # instant (UTC)                 Kyiv civil date   rule
    ('2026-03-28T21:59:59+00:00', '2026-03-28', 'before spring DST, UTC+2'),
    ('2026-03-28T22:00:00+00:00', '2026-03-29', 'midnight in UTC+2'),
    ('2026-03-29T00:59:59+00:00', '2026-03-29', 'just before the 03:00 jump'),
    ('2026-03-29T01:00:00+00:00', '2026-03-29', 'after the jump, UTC+3'),
    ('2026-10-24T20:59:59+00:00', '2026-10-24', 'last evening of summer time'),
    ('2026-10-24T21:00:00+00:00', '2026-10-25', 'midnight in UTC+3'),
    ('2026-10-25T00:59:59+00:00', '2026-10-25', 'first 03:59:59 before fallback'),
    ('2026-10-25T01:00:00+00:00', '2026-10-25', 'repeated hour, UTC+2'),
    ('2026-12-31T21:59:59+00:00', '2026-12-31', 'new year boundary'),
    ('2026-12-31T22:00:00+00:00', '2027-01-01', 'new year in Kyiv, still 2026 in UTC'),
]


def _app():
    code = ('import importlib.util,sys,json\n'
            f"s=importlib.util.spec_from_file_location('app',{str(ROOT / 'server/app.py')!r})\n"
            "app=importlib.util.module_from_spec(s);sys.modules['app']=app;s.loader.exec_module(app)\n"
            'from datetime import datetime\n'
            'for line in sys.stdin:\n'
            '    instant, value = line.split()\n'
            "    print(app.kyiv_date(datetime.fromisoformat(instant)).isoformat(), app.date_allowed(value, datetime.fromisoformat(instant)))\n")
    return code


@pytest.mark.parametrize('tz', ['UTC', 'America/Los_Angeles', 'Pacific/Auckland', 'Europe/Kyiv'])
def test_server_civil_date_is_independent_of_host_timezone(tmp_path, tz):
    lines = ''.join(f'{i} {d}\n' for i, d, _ in VECTORS)
    r = subprocess.run([sys.executable, '-c', _app()], input=lines, capture_output=True, text=True, timeout=30,
                       env={**os.environ, 'TZ': tz, 'LEAD_DB': str(tmp_path / 'd.db'), 'DELIVERY_WORKER': '0'})
    assert r.returncode == 0, r.stderr
    got = [ln.split() for ln in r.stdout.splitlines()]
    assert [g[0] for g in got] == [d for _, d, _ in VECTORS]
    assert all(g[1] == 'True' for g in got), 'the Kyiv civil today must be accepted'


@pytest.mark.parametrize('tz', ['UTC', 'America/Los_Angeles', 'Pacific/Auckland', 'Europe/Kyiv'])
def test_server_rejects_kyiv_yesterday_regardless_of_host_timezone(tmp_path, tz):
    # 2026-12-31 22:00 UTC is already 2027-01-01 in Kyiv: 2026-12-31 is yesterday.
    r = subprocess.run([sys.executable, '-c', _app()], input='2026-12-31T22:00:00+00:00 2026-12-31\n', capture_output=True,
                       text=True, timeout=30, env={**os.environ, 'TZ': tz, 'LEAD_DB': str(tmp_path / 'd.db'), 'DELIVERY_WORKER': '0'})
    assert r.returncode == 0, r.stderr
    assert r.stdout.split() == ['2027-01-01', 'False']


@pytest.mark.parametrize(
    'tz, frozen_utc, kyiv_today',
    [
        ('UTC', '2026-12-31T22:30:00+00:00', '2027-01-01'),
        ('America/Los_Angeles', '2026-03-29T14:30:00+00:00', '2026-03-29'),
        ('UTC', '2026-03-28T22:30:00+00:00', '2026-03-29'),
        ('UTC', '2026-10-24T21:30:00+00:00', '2026-10-25'),
        ('Pacific/Auckland', '2026-12-31T11:30:00+00:00', '2026-12-31'),
        ('Pacific/Auckland', '2026-10-25T11:30:00+00:00', '2026-10-25'),
    ],
    ids=['utc-new-year', 'los-angeles-spring', 'utc-spring-dst',
         'utc-autumn-dst', 'auckland-new-year', 'auckland-autumn'],
)
def test_browser_validator_uses_the_same_civil_date(browser, server, tz, frozen_utc, kyiv_today):
    """ADV-05: a fixed browser clock kills host-midnight substitutions every run.

    Each instant is independent of CI wall time; the selected host zones include
    both a local date ahead of Kyiv and one behind Kyiv. Real site JS executes.
    """
    from datetime import date, timedelta

    ctx = browser.new_context(timezone_id=tz, reduced_motion='reduce')
    page = ctx.new_page()
    try:
        # Install before navigation so application code sees the frozen instant.
        # Fixed Date leaves browser timers operational for startup and network.
        page.clock.set_fixed_time(datetime.fromisoformat(frozen_utc))
        page.goto(server['base'], wait_until='domcontentloaded')
        page.wait_for_function("typeof window.PBTv === 'function'")
        seen = page.evaluate("""() => ({
            utc: new Date().toISOString(),
            kyiv: new Intl.DateTimeFormat('en-CA', {
                timeZone: 'Europe/Kyiv', year: 'numeric', month: '2-digit', day: '2-digit'
            }).format(new Date())
        })""")
        assert seen['utc'][:19] == frozen_utc[:19], (tz, seen)
        assert seen['kyiv'] == kyiv_today, (tz, seen)
        today = date.fromisoformat(kyiv_today)
        cases = (
            ((today - timedelta(days=1)).isoformat(), False),
            (today.isoformat(), True),
            ((today + timedelta(days=1)).isoformat(), True),
        )
        for value, accepted in cases:
            ok = page.evaluate("v => window.PBTv('date', v)", value)
            assert ok is accepted, f'{tz} at {frozen_utc}: {value} -> {ok}, expected {accepted}'
    finally:
        ctx.close()

@pytest.mark.parametrize('value', ['2026-02-30', '2026-13-01', '0000-01-01', '9999-12-32', '٢٠٢٧-٠١-٠١', '2027-1-1', '2027-01-01T00:00', ''])
def test_malformed_dates_rejected_by_server_when_nonempty(tmp_path, value):
    code = _app().replace("instant, value = line.split()", "instant, value = line.rstrip('\\n').split(' ', 1)")
    r = subprocess.run([sys.executable, '-c', code], input=f'2026-06-01T00:00:00+00:00 {value}\n', capture_output=True,
                       text=True, timeout=30, env={**os.environ, 'LEAD_DB': str(tmp_path / 'd.db'), 'DELIVERY_WORKER': '0'})
    assert r.returncode == 0, r.stderr
    assert r.stdout.split()[1] == ('True' if value == '' else 'False')


def test_whitespace_date_through_the_real_validator_is_rejected_not_absent(tmp_path):
    code = (_app().split('from datetime import datetime')[0] +
            "print(sorted(app.validate({'type':'rent','subject':'Екскаватор','method':'phone','contact':'0971112233','date':'   '})[1]))\n"
            "print(sorted(app.validate({'type':'rent','subject':'Екскаватор','method':'phone','contact':'0971112233','date':''})[1]))\n")
    r = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, timeout=30,
                       env={**os.environ, 'LEAD_DB': str(tmp_path / 'd.db'), 'DELIVERY_WORKER': '0'})
    assert r.returncode == 0, r.stderr
    assert r.stdout.splitlines() == ["['date']", '[]']


def test_browser_without_the_new_zone_name_can_still_validate_a_date(browser, server):
    ctx = browser.new_context(reduced_motion='reduce')
    ctx.add_init_script("""const Real = Intl.DateTimeFormat;
      Intl.DateTimeFormat = function (l, o) { if (o && o.timeZone === 'Europe/Kyiv') throw new RangeError('old ICU'); return new Real(l, o); };""")
    page = ctx.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    try:
        page.goto(server['base'], wait_until='networkidle')
        assert page.evaluate("() => window.PBTv('date', '2999-01-01')") is True
        assert page.evaluate("() => window.PBTv('date', '2000-01-01')") is False
        assert errors == []
    finally:
        ctx.close()
