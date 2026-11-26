"""Перевірка запуску сервера з каталогом стану, оголошеним у системному юніті."""
from pathlib import Path
import select
import shlex
import shutil
import sqlite3
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
UNIT = ROOT / 'ops/systemd/system/pbt-site.service'


def test_system_candidate_starts_with_state_outside_read_only_install(tmp_path):
    lines = UNIT.read_text(encoding='utf-8').splitlines()
    state_name, = [line.removeprefix('StateDirectory=') for line in lines if line.startswith('StateDirectory=')]
    state_root = tmp_path / 'state'
    state = state_root / state_name
    state.mkdir(parents=True, mode=0o700)
    env = {
        key: value.replace('%S', str(state_root))
        for line in lines if line.startswith('Environment=')
        for assignment in shlex.split(line.removeprefix('Environment='))
        for key, value in [assignment.split('=', 1)]
    }
    env.update(HOST='127.0.0.1', PORT='0', DELIVERY_WORKER='0')

    source = tmp_path / 'install'
    app = source / 'server/app.py'
    app.parent.mkdir(parents=True)
    shutil.copyfile(ROOT / 'server/app.py', app)
    app.chmod(0o444)
    app.parent.chmod(0o555)
    source.chmod(0o555)
    try:
        with subprocess.Popen([sys.executable, '-u', str(app)], cwd=source, env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE) as proc:
            try:
                readable, _, _ = select.select([proc.stdout], [], [], 10)
                banner = proc.stdout.readline() if readable else b''
            finally:
                proc.kill()
                _, stderr = proc.communicate(timeout=5)
        assert b'http://127.0.0.1:0/' in banner, stderr.decode(errors='replace')
        assert not (source / 'data').exists()
        assert (state / 'server.log').is_file()
        assert (state / '.ip_salt').stat().st_size > 0
        with sqlite3.connect((state / 'leads.db').as_uri() + '?mode=ro', uri=True) as db:
            assert db.execute('SELECT count(*) FROM leads').fetchone() == (0,)
    finally:
        source.chmod(0o755)
        app.parent.chmod(0o755)
