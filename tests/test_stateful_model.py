"""ADV-03: model-based random walks over the real server process, with crashes between steps.

Seeds are fixed, so a failure replays exactly; on failure the sequence is shrunk by greedy deletion and
the minimal counterexample is in the assertion message. Hypothesis was not added: this needs one model
and one seeded generator, not a dependency. Finite walks are evidence, not a proof of the invariants.
"""
import json
import random
import sqlite3

import pytest

from test_leads import LEAD, Srv

QUOTA = 3
KEYS = [f'k-model-{i:04d}' for i in range(16)]
PAYLOADS = [{**LEAD, 'subject': f'Модельна техніка {i}'} for i in range(3)]
ENV = {'RATE_LEAD_10MIN': str(QUOTA), 'RATE_LEAD_DAY': '100000', 'DELIVERY_WORKER': '0',
       'LEAD_WEBHOOK_URL': 'http://127.0.0.1:9/hook', 'LEAD_WEBHOOK_SECRET': 'k'}


def generate(seed, steps):
    rng = random.Random(seed)
    return [('crash',) if rng.random() < .05 else ('submit', rng.choice(KEYS), rng.randrange(len(PAYLOADS)))
            for _ in range(steps)]


def execute(db, sequence, seen=None):
    """Run a sequence on a fresh database. Returns the first violation, or None."""
    seen = {} if seen is None else seen
    db.unlink(missing_ok=True)
    model, charged, last_id, server = {}, 0, 0, Srv(db, **ENV)
    try:
        for step, op in enumerate(sequence):
            if op[0] == 'crash':
                server.kill()
                server = Srv(db, **ENV)
                charged = 0  # Declared limit: quota is in-memory and resets on restart.
                continue
            _, key, which = op
            status, body, _ = server.post(PAYLOADS[which], key)
            if key in model:
                prior, ref = model[key]
                want = (201, ref) if prior == which else (409, None)
                seen['replay' if prior == which else 'conflict'] = seen.get('replay' if prior == which else 'conflict', 0) + 1
                got = (status, body.get('ref'))
                if got != want:
                    return f'step {step} {op}: replay/conflict {got} != {want}'
            elif charged >= QUOTA:
                seen['quota_refusal'] = seen.get('quota_refusal', 0) + 1
                if status != 429:
                    return f'step {step} {op}: over quota got {status}'
            else:
                if status != 201 or body.get('replayed'):
                    return f'step {step} {op}: new key got {status} {body}'
                number = int(body['ref'].split('-')[1])
                if number <= last_id:
                    return f'step {step} {op}: id {number} reused after {last_id}'
                last_id, charged = number, charged + 1
                model[key] = (which, body['ref'])
            with sqlite3.connect(db) as c:
                leads = c.execute('SELECT id, idem_key, payload FROM leads').fetchall()
                outbox = c.execute('SELECT lead_id FROM outbox').fetchall()
                orphans = c.execute('PRAGMA foreign_key_check').fetchall()
            if {k: r for k, (_, r) in model.items()} != {k: f'PBT-{i:06d}' for i, k, _ in leads}:
                return f'step {step} {op}: durable leads diverge from accepted responses'
            if sorted(x for (x,) in outbox) != sorted(i for i, _, _ in leads) or orphans:
                return f'step {step} {op}: outbox is not exactly one row per accepted lead'
            for lead_id, key_, payload in leads:
                if json.loads(payload)['subject'] != PAYLOADS[model[key_][0]]['subject']:
                    return f'step {step} {op}: stored payload replaced'
        return None
    finally:
        server.kill()


def shrink(db, sequence):
    current = list(sequence)
    changed = True
    while changed:
        changed = False
        for i in range(len(current) - 1, -1, -1):
            candidate = current[:i] + current[i + 1:]
            if execute(db, candidate):
                current, changed = candidate, True
    return current


@pytest.mark.parametrize('seed', [20261101, 7, 1729])
def test_random_walk_with_crashes_preserves_every_invariant(tmp_path, seed):
    db = tmp_path / 'model.db'
    sequence = generate(seed, 60)
    assert sum(op[0] == 'crash' for op in sequence) >= 1, 'walk exercised no crash'
    seen = {}
    violation = execute(db, sequence, seen)
    if not violation:
        # A walk that never reached a transition says nothing about it.
        assert all(seen.get(k) for k in ('replay', 'conflict', 'quota_refusal')), seen
    if violation:
        minimal = shrink(db, sequence)
        pytest.fail(f'seed={seed} {violation}\nminimal counterexample: {minimal}\nreplay: {execute(db, minimal)}')
