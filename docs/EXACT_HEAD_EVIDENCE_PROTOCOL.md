# Exact-HEAD evidence graph / self-falsifying automation

This protocol makes a **machine-reproducible distinction** between *a workflow
reported success*, *its artifact bytes were verified*, and *the deployed system
actually meets a stated objective*. None is interchangeable.

## Epistemic levels / acceptance rule

1. **Provider facts:** fetch PR HEAD, base SHA, event, workflow run ID/attempt,
   job conclusions and artifact IDs using the authenticated GitHub connector.
   Refetch before writing a receipt or changing refs. A manually authored
   manifest is **not** cryptographically authenticated provider data.
2. **Artifact integrity:** download eight ZIP files; independently validate
   SHA-256, ZIP CRC, member lists, JUnit outcomes, offline HTML hashes,
   screenshots/PNG CRCs, synthetic mobile claim boundaries, scoped AST/OSV
   receipts and the exact HEAD in every report that supplies it.
3. **Behavioral falsification:** independently recompute every raw soak p99
   latency sample, two process epochs of main+child RSS, retry/fault counts,
   bounded resources, backups and accepted-lead/outbox equality.
4. **Meta-falsification:** feed the verifier deliberately stale/cancelled
   metadata, forged PASS labels, altered raw measurements, inconsistent RSS,
   bad HMAC outcomes, missing artifacts and corrupted image evidence. A
   verifier that fails to reject any negative control cannot certify evidence.
5. **External reality:** live CRM/TLS, recipient dedup, off-device recovery
   RPO, field INP/CWV, SLA/SLO and a full security assessment remain
   **NOT VERIFIED** until separately observed with their own provenance.

**Acceptance is conjunctive, not a weighted average.** Any missing mandatory
proof is a HOLD; 99 green unit checks do not compensate for one unbounded
data-loss defect. Weights can prioritize investigations, never waive an
invariant.

## Offline verifier

The stdlib-only evaluator is `tools/meta_evidence_gate.py`. It expects a
JSON manifest `pbt-exact-head-evidence-matrix-v2` with:

- `head_sha`, `base_sha`, `target` (`kind`, `pr_number`, `ref`, bound by `config/evidence-policy.json`);
- exactly five run roles: `full`, `transport`, `visual`, `security`,
  `soak`, each with authenticated `id`, `head_sha`, `event:pull_request`,
  `attempt`, `status:completed`, `conclusion:success`; `event` must belong to the target's receipts: pull-request receipts never certify `main` and vice versa;
- exactly eight artifacts: `release`, `baseline`, `mobile`, `http`,
  `visual`, `osv`, `static`, `soak`, each with `id`, `run_id`,
  `filename` (`<role>.zip`) and independently computed `sha256`.

After retrieving **all eight actual ZIP bytes**:

```sh
python3 tools/meta_evidence_gate.py \
  --manifest evidence/manifest.json \
  --evidence-dir evidence \
  --policy config/runtime-soak-budgets.json \
  --expected-head "$CURRENT_PR_HEAD" \
  --expected-base "$CURRENT_MAIN_SHA"
```

The explicit SHA arguments must come from a **fresh, independent read of
GitHub refs**. Output is canonical sorted-key JSON. Exit 0 means all currently
specified offline checks PASS; otherwise nonzero with a bounded reason.
It does **not** sign or authenticate the GitHub API snapshot. Do not use
a fabricated manifest to justify merging.

## Automation that tests its own acceptance machinery

`tests/test_meta_evidence_gate.py` generates a hermetic positive control and
16 adversarial negative controls. Run:

```sh
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q \
  tests/test_meta_evidence_gate.py
```

The PR workflow runs these mutation checks in a separate job with exact
HEAD checkout and a preserved JUnit artifact. The full `make gate` also
discovers them. A gate cannot be promoted merely because it prints PASS:
the *negative-control test* must itself complete successfully.

### Controller state machine

```text
FETCH_HEAD -> FREEZE -> COLLECT -> VERIFY_ALL -> FALSIFY_VERIFIER
             |              |           |             |
             v              v           v             v
           DRIFT?         MISSING?   INVARIANT?    MUTANT_PASSED?
             |              |           |             |
            HOLD           HOLD        HOLD          HOLD
                            \___________________________/
                                         |
                                  ROOT_CAUSE / FIX
                                         |
                               GUARDED_FAST_FORWARD
                                         |
                                   FRESH_NEW_HEAD
```

Do not publish a new commit during a 30-minute mandatory soak without a
reproduced P0 reason: GitHub `cancel-in-progress` invalidates the existing
expensive observation. Never mix old-head artifacts with new-head conclusions.
Only the owner-authorized conditional merge path is permitted; deployment,
production telemetry and pricing/VAT authorization are independent.
No separate formal human review gate is required for this solo project.

## Boundaries and caveats

- Sampled `VmRSS` across process descendants is **not** a continuous peak,
  USS/PSS, kernel-cgroup charge or the external CRM's resource usage.
- Loopback synthetic 1800-second soak is not a production SLO, live receiver
  certificate proof, saturation proof or field INP.
- Media inventory hashes in a report do not independently prove bytes that
  were not included in the artifact.
- A GitHub workflow may report success while a missing/diluted oracle would
  accept a bad implementation. The independent verifier and negative tests
  reduce that risk but do not eliminate it.
- The verifier's supplied run metadata and artifact SHA values depend on an
  **independent authenticated fetch**. It cannot generate trust ex nihilo.
- Static Python AST rules and OSV findings do not constitute full SAST,
  OWASP ASVS 5.0 certification or NIST SSDF certification.
