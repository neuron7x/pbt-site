"""А1 (аудит п.24/34): каталог стану сервера — властивість розгортання, PBT_DATA_DIR; за замовчуванням <repo>/data як і раніше."""
import os
import sys
import urllib.request
from pathlib import Path

from test_leads import Srv

ROOT = Path(__file__).resolve().parents[1]


def test_state_goes_to_pbt_data_dir_and_not_to_the_repo(tmp_path):
    repo_log = ROOT / 'data' / 'server.log'
    before = repo_log.stat().st_size if repo_log.exists() else None
    state = tmp_path / 'state'
    state.mkdir()
    s = Srv(tmp_path / 'leads.db', PBT_DATA_DIR=str(state), IP_HASH_SALT='', DELIVERY_WORKER='0')
    try:
        with urllib.request.urlopen(s.base + '/', timeout=5) as r:
            assert r.status == 200
    finally:
        s.kill()
    assert (state / 'server.log').stat().st_size > 0
    assert (state / '.ip_salt').exists() and oct((state / '.ip_salt').stat().st_mode & 0o777) == '0o600'
    after = repo_log.stat().st_size if repo_log.exists() else None
    assert after == before, 'сервер з PBT_DATA_DIR дописав у репозиторний data/server.log'


def test_default_data_dir_is_unchanged_for_existing_deployments(tmp_path):
    """Без PBT_DATA_DIR — як до зміни: <repo>/data (чинні розгортання й ops/restore.py нічого не помічають)."""
    import subprocess
    probe = ("import os, runpy, sys; os.environ.pop('PBT_DATA_DIR', None); sys.argv=['app.py'];"
             "import importlib.util as u; s=u.spec_from_file_location('app_probe', r'%s'); m=u.module_from_spec(s);"
             "s.loader.exec_module(m); print(m.DATA)") % (ROOT / 'server' / 'app.py')
    env = {k: v for k, v in os.environ.items() if k != 'PBT_DATA_DIR'}
    env['LEAD_DB'] = str(tmp_path / 'leads.db')
    out = subprocess.run([sys.executable, '-c', probe], env=env, capture_output=True, text=True, timeout=30, cwd=tmp_path)
    assert out.returncode == 0, out.stderr[-500:]
    assert Path(out.stdout.strip().splitlines()[-1]) == (ROOT / 'data').resolve()
