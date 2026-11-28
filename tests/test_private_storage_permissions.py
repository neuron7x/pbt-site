"""Regression: accepted-lead PII must never inherit permissive host file modes."""

import json
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest


APP = Path(__file__).resolve().parents[1] / "server" / "app.py"


@pytest.mark.parametrize("scenario", ["fresh", "legacy", "external_db"])
def test_accepted_leads_logs_and_database_are_private_under_umask_022(tmp_path, scenario):
    site = tmp_path / "isolated-site"
    installed = site / "server"
    installed.mkdir(parents=True)
    for module in APP.parent.glob("*.py"):
        shutil.copyfile(module, installed / module.name)
    data = site / "data"
    database = site / "external.db" if scenario == "external_db" else data / "leads.db"
    if scenario != "fresh":
        data.mkdir(mode=0o755)
        (data / "server.log").write_text("legacy log\n", encoding="utf-8")
        sqlite3.connect(database).close()
        for file in (data / "server.log", database):
            os.chmod(file, 0o644)
        os.chmod(data, 0o755)

    env = os.environ.copy()
    for name in ("IP_HASH_SALT", "LEAD_WEBHOOK_URL", "LEAD_WEBHOOK_SECRET",
                 "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "TELEGRAM_API_BASE",
                 "PBT_DATA_DIR"):                  # перевіряється типовий <site>/data, не сесійний каталог тестів
        env.pop(name, None)
    env.update({
        "LEAD_DB": str(database),
        "PBT_PROBE_APP": str(installed / APP.name),
        "PBT_PROBE_DATA": str(data),
        "MIGRATE_BOOT_ATTEMPTS": "1",
        "DELIVERY_WORKER": "0",
    })
    probe = r'''
import json, os, runpy, stat
from pathlib import Path
os.umask(0o022)
runpy.run_path(os.environ["PBT_PROBE_APP"], run_name="pbt_permission_probe")
items = {
    "data": Path(os.environ["PBT_PROBE_DATA"]),
    "log": Path(os.environ["PBT_PROBE_DATA"]) / "server.log",
    "database": Path(os.environ["LEAD_DB"]),
}
print(json.dumps({name: stat.S_IMODE(path.stat().st_mode) for name, path in items.items()}))
'''
    run = subprocess.run([sys.executable, "-c", probe], env=env,
                         capture_output=True, text=True, timeout=20, check=False)
    assert run.returncode == 0, run.stderr
    modes = json.loads(run.stdout.strip().splitlines()[-1])
    assert modes == {"data": 0o700, "log": 0o600, "database": 0o600}
