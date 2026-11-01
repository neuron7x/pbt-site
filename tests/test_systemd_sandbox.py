"""NET-08 technical part. Directives in a file are a claim; ops/sandbox_probe.py measures them on a host.
This suite checks the probe's judgment and the candidate unit's content. It proves nothing about any target host."""
import configparser
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('sandbox_probe', ROOT / 'ops/sandbox_probe.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)
HELD = {'home_canary_readable': False, 'home_writable': False, 'usr_writable': False, 'etc_writable': False,
        'memory_max': str(128 * 1024 * 1024), 'tasks_max': '32', 'no_new_privs': True}


def test_probe_passes_only_when_every_boundary_held():
    assert all(probe.boundaries(HELD).values())


def test_probe_reports_the_measured_user_manager_failure():
    seen = {**HELD, 'home_canary_readable': True, 'home_writable': True}
    held = probe.boundaries(seen)
    assert held['home_read_blocked'] is False and held['home_write_blocked'] is False
    assert not all(held.values())


def test_probe_treats_an_absent_limit_as_not_held():
    assert probe.boundaries({**HELD, 'memory_max': 'max'})['memory_limit_applied'] is False
    assert probe.boundaries({**HELD, 'tasks_max': 'max'})['task_limit_applied'] is False


def _unit(path):
    parser = configparser.ConfigParser(strict=False, interpolation=None, delimiters=('=',))
    parser.optionxform = str
    parser.read(path, encoding='utf-8')
    return parser['Service']


def test_candidate_unit_declares_identity_isolation_and_limits():
    service = _unit(ROOT / 'ops/systemd/system/pbt-site.service')
    for key, value in {'DynamicUser': 'yes', 'ProtectSystem': 'strict', 'ProtectHome': 'yes', 'NoNewPrivileges': 'yes',
                       'PrivateTmp': 'yes', 'PrivateDevices': 'yes', 'MemoryMax': '512M', 'TasksMax': '256'}.items():
        assert service[key] == value, key
    assert 'ReadWritePaths' not in service, 'only StateDirectory may be writable'


def test_installer_does_not_silently_deploy_the_candidate():
    assert 'ops/systemd/system' not in (ROOT / 'ops/install.sh').read_text(encoding='utf-8')
    assert 'ops/systemd/*.service' in (ROOT / 'ops/install.sh').read_text(encoding='utf-8')


def test_user_unit_states_its_measured_limit():
    assert 'does NOT' in (ROOT / 'ops/systemd/pbt-site.service').read_text(encoding='utf-8')
