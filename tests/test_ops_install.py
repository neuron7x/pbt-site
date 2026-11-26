"""Порядок активації user-юнітів у тимчасовій копії з підставним systemctl."""

from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
SITE = "pbt-site.service"
SERVICES = [SITE, "pbt-site-health.service", "pbt-site-backup.service"]
TIMERS = ["pbt-site-health.timer", "pbt-site-backup.timer"]


@pytest.fixture
def installer(tmp_path, monkeypatch):
    home = tmp_path / "home with spaces"
    canonical = home / "projects" / "pbt-site"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    log = tmp_path / "manager.log"
    revision = tmp_path / "running-revision"
    revision.write_text("old", encoding="utf-8")
    config = tmp_path / "xdg config"

    commands = fake_bin / "systemctl"
    commands.write_text(
        """#!/usr/bin/env bash
set -eu
[[ "$1" == --user ]] || exit 98
shift
printf '%s\\n' "$*" >> "$MANAGER_LOG"
case "$1" in
    daemon-reload|enable) ;;
    show)
        if [[ "$4" == "${OVERRIDE_UNIT:-}" ]]; then
            printf '%s\\n' "$HOME"
        else
            printf '%s\\n' "$HOME/projects/pbt-site"
        fi ;;
    restart)
        if [[ "${FAIL_RESTART:-0}" == 1 ]]; then
            exit 17
        fi
        printf new > "$RUNNING_REVISION" ;;
    is-active)
        [[ "$(cat "$RUNNING_REVISION")" == new ]] ;;
    *) exit 98 ;;
esac
""",
        encoding="utf-8",
    )
    commands.chmod(0o755)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PATH", str(fake_bin) + ":/usr/bin:/bin")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config))
    monkeypatch.setenv("MANAGER_LOG", str(log))
    monkeypatch.setenv("RUNNING_REVISION", str(revision))
    monkeypatch.delenv("OVERRIDE_UNIT", raising=False)
    monkeypatch.delenv("FAIL_RESTART", raising=False)

    def run(checkout=canonical):
        ops = checkout / "ops"
        shutil.copytree(ROOT / "ops" / "systemd", ops / "systemd")
        shutil.copyfile(ROOT / "ops" / "install.sh", ops / "install.sh")
        return subprocess.run(
            ["bash", str(ops / "install.sh")], cwd=tmp_path, capture_output=True,
            text=True, timeout=10,
        )

    return run, config / "systemd" / "user", log, revision


def test_install_restarts_running_service_before_activating_timers(installer):
    run, units, log, revision = installer
    result = run()
    assert result.returncode == 0, result.stderr
    assert revision.read_text(encoding="utf-8") == "new"
    calls = log.read_text(encoding="utf-8").splitlines()
    assert calls[:4] == [
        "daemon-reload",
        *[f"show --property=WorkingDirectory --value {unit}" for unit in SERVICES],
    ]
    assert calls[4:] == [
        f"enable {SITE}",
        f"restart {SITE}",
        f"is-active --quiet {SITE}",
        "enable --now " + " ".join(TIMERS),
    ]
    assert set(path.name for path in units.iterdir()) == set(SERVICES + TIMERS)
    for unit in SERVICES + TIMERS:
        assert (units / unit).read_bytes() == (ROOT / "ops" / "systemd" / unit).read_bytes()


def test_install_rejects_other_checkout_before_touching_manager(installer, tmp_path):
    run, units, log, revision = installer
    result = run(tmp_path / "other checkout")
    assert result.returncode != 0
    assert "projects/pbt-site" in result.stderr
    assert not units.exists()
    assert not log.exists()
    assert revision.read_text(encoding="utf-8") == "old"


def test_install_rejects_overridden_unit_path_before_restart(installer, monkeypatch):
    run, _, log, revision = installer
    monkeypatch.setenv("OVERRIDE_UNIT", SERVICES[-1])
    result = run()
    assert result.returncode != 0
    assert SERVICES[-1] in result.stderr
    assert "restart" not in log.read_text(encoding="utf-8")
    assert "enable" not in log.read_text(encoding="utf-8")
    assert revision.read_text(encoding="utf-8") == "old"


def test_restart_failure_preserves_error_and_leaves_timers_untouched(installer, monkeypatch):
    run, _, log, revision = installer
    monkeypatch.setenv("FAIL_RESTART", "1")
    result = run()
    assert result.returncode == 17
    calls = log.read_text(encoding="utf-8").splitlines()
    assert calls[-1] == f"restart {SITE}"
    assert not any(timer in call for timer in TIMERS for call in calls)
    assert revision.read_text(encoding="utf-8") == "old"
