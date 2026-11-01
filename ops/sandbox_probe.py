#!/usr/bin/env python3
"""Measure whether a unit's sandbox directives take effect, on this host, under a transient unit.

  sandbox_probe.py --manager user    # systemd --user, as ops/systemd/pbt-site.service runs
  sandbox_probe.py --manager system  # requires root; candidate ops/systemd/system/pbt-site.service

A synthetic canary is planted in the invoking user's home. The probe never touches real files.
Exit 0 only if every boundary held. Directives written in a unit file are a claim; this is the test.
"""
import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys

DIRECTIVES = ['ProtectSystem=strict', 'ProtectHome=yes', 'PrivateTmp=yes', 'NoNewPrivileges=yes',
              'MemoryMax=128M', 'TasksMax=32']
SYSTEM_ONLY = ['PrivateDevices=yes', 'RestrictSUIDSGID=yes']  # A user manager refuses these (exit 218).


def probe_script(canary_path, canary_value):
    return f"""
import json,os,pathlib,resource
out={{}}
def attempt(f):
    try: return f()
    except OSError as e: return 'denied:'+type(e).__name__
try:
    value=pathlib.Path({canary_path!r}).read_text()
    out['home_canary_readable']=value.strip()=={canary_value!r}
except OSError:
    out['home_canary_readable']=False
def w(p):
    pathlib.Path(p).write_text('x'); pathlib.Path(p).unlink(); return True
out['home_writable']=attempt(lambda:w({str(Path(canary_path).parent / '.pbt-sandbox-write')!r}))is True
out['usr_writable']=attempt(lambda:w('/usr/.pbt-sandbox-write'))is True
out['etc_writable']=attempt(lambda:w('/etc/.pbt-sandbox-write'))is True
cg='/sys/fs/cgroup'+open('/proc/self/cgroup').read().split(':')[-1].strip()
out['memory_max']=open(cg+'/memory.max').read().strip()
out['tasks_max']=open(cg+'/pids.max').read().strip()
out['no_new_privs']='NoNewPrivs:\\t1' in open('/proc/self/status').read()
print(json.dumps(out))
"""


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manager', choices=('user', 'system'), required=True)
    p.add_argument('--canary-dir', type=Path, default=Path.home())
    a = p.parse_args(argv)
    value = secrets.token_hex(8)
    canary = a.canary_dir / f'.pbt-sandbox-canary-{value}'
    canary.write_text(value)
    canary.chmod(0o644)
    try:
        command = ['systemd-run', '--wait', '--pipe', '-q']
        if a.manager == 'user':
            command.append('--user')
        else:
            command += ['-p', 'DynamicUser=yes']
            for directive in SYSTEM_ONLY:
                command += ['-p', directive]
        for directive in DIRECTIVES:
            command += ['-p', directive]
        command += ['/usr/bin/python3', '-c', probe_script(str(canary), value)]
        r = subprocess.run(command, capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            print(json.dumps({'status': 'UNKNOWN', 'manager': a.manager, 'reason': 'unit_failed', 'rc': r.returncode}))
            return 2
        seen = json.loads(r.stdout)
    finally:
        canary.unlink(missing_ok=True)
    held = {
        'home_read_blocked': seen['home_canary_readable'] is False,
        'home_write_blocked': seen['home_writable'] is False,
        'usr_write_blocked': seen['usr_writable'] is False,
        'etc_write_blocked': seen['etc_writable'] is False,
        'memory_limit_applied': seen['memory_max'] == str(128 * 1024 * 1024),
        'task_limit_applied': seen['tasks_max'] == '32',
        'no_new_privileges': seen['no_new_privs'] is True,
    }
    ok = all(held.values())
    print(json.dumps({'status': 'PASS' if ok else 'FAIL', 'manager': a.manager, 'boundaries': held,
                      'uid_run_as': 'dynamic' if a.manager == 'system' else os.getuid(),
                      'kernel': os.uname().release}, sort_keys=True))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
