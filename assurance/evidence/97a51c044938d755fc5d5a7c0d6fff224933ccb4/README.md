# EVD-PERSIST: authenticated exact-main closure originals

**Repository/source**: `neuron7x/pbt-site@97a51c044938d755fc5d5a7c0d6fff224933ccb4` (GitHub push, attempt 1). **State**: `ENGINEERING_ACCEPTED_LOCAL_PROOF_ONLY` for C1–C9; C0/C10 unknown; **PRODUCTION HOLD**. No deployment is authorized.

This folder contains **all 11 byte-exact original files** from original GitHub Actions closure artifact `13193041168` (run `41548280477`; provider original ZIP SHA-256 `22a19aafd8a7e30df37b12ea857d145fc02ee433556f1d457b7ff317b2d6f8fa`). The four critical full receipts are `receipts.json`, `reconciled-ledger.json`, `reconciled-case.json`, and `SHA256SUMS`; all other original ZIP members are retained unchanged. `PROVENANCE.json` adds external independent provider/member SHA-256 and Git blob IDs; it is NOT one of the original ZIP members.

## Verification

From this directory run `sha256sum -c SHA256SUMS` to check the ZIP's seven built-in digest entries. Independently verify **all 11** original members against the `PROVENANCE.json:original_members` SHA-256 and byte sizes, plus the Git blob SHA-1 values before trusting the closure. Cross-check provider artifact ID/digest, exact source SHA and workflow attempt against the authenticated GitHub Actions API; do not substitute a run from another commit. Tampering of any mandatory member, source SHA or provider role MUST fail closed.

This archive was independently audited against 11 freshly downloaded authenticated provider ZIPs: 11,048/11,048 assertions passed; seven adversarial controls rejected (provider ZIP tamper, original receipt mutation, wrong SHA, missing required role, duplicate ZIP entry, soak p99 out-of-budget, falsified evidence). Run the independent audit again on any new source SHA; **these historical values never prove a later commit**.

The reconciled ledger and case are **source-bound read-only proof copies**, not normative updates. Original `assurance/ledger.json` and `assurance/case.json` remain untouched. External B1–B9/R1–R3/H1/F1/S1/D1 lack authorized receipts. Synthetic CI does not establish real receiver/field/production readiness. This persistence PR must independently pass **its own exact-HEAD** applicable Actions and ≥1800s soak before any merge; postmerge needs six fresh exact-new-main workflows and a fresh closure. See issue #30 and controller #15.
