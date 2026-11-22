# PLAINBUD: HTTP boundaries and source-evidence integrity

Iteration date: **2026-11-21**. Repository: `neuron7x/pbt-site`.
[PR #34](https://github.com/neuron7x/pbt-site/pull/34).
Remote parent: `30e71f17370ff36f40fe3814a75f5db7795aa142`.
Observed main: `828abe1fd3daf0540cd28cd6636600331c195412`.

This record covers a further engineering pass after
[runtime evidence hardening](RUNTIME_EVIDENCE_HARDENING.md). It preserves
the public blue/gold design, normal animations, catalog, prices, API payloads,
CRM references, HMAC, storage keys and production holds.

## Reproduced defects and corrections

| Boundary | Correction and behavioral controls |
|---|---|
| Media byte ranges | Decimal bounds are compared as normalized strings before bounded integer conversion. A 5,000-digit Range no longer terminates the connection. ASCII syntax, repeated fields, reversed ranges, empty files, suffixes and leading zeros have actual HTTP controls. |
| Compression and caching | Exact gzip/x-gzip/wildcard tokens and bounded quality parameters determine compression; an explicit zero refuses it across repeated fields. Identity text responses also send `Vary: Accept-Encoding`. GET/HEAD agree on compressed metadata and conditional responses. |
| HEAD APIs | `/api/config` and `/api/health` provide GET-equivalent status and metadata without response bytes, including degraded 503. Unknown endpoints and HEAD `/api/lead` retain 404 and an empty body. |
| Proxy identity | A trusted proxy's selected forwarded value must parse as an actual IP address. Valid values are normalized; malformed values use the peer identity instead of minting another quota key. Trust configuration is unchanged. |
| Submission confirmation | A 201 response confirms success only with boolean `ok: true` and a positive `PBT-` reference containing at least six ASCII digits. Short, zero, missing or malformed references retain safe retry state and use the fallback. Existing honeypot 200 rejection behavior is preserved. |
| Date validation | Kyiv civil dates are assembled from explicit date parts with ISO calendar and Latin digits. Locale field ordering cannot change the comparison format. Both Kyiv/Kiev time-zone names remain supported. |
| Media policy | Empty or malformed rules, boolean limits, duplicate JSON keys and non-finite constants cannot produce a clean media-policy result. Evidence recomputation uses the same strict canonical-policy parser; existing ceilings and categories are unchanged. |
| Scoped static source | The CLI compares the complete Python inventory and each byte snapshot against actual Git blobs at the requested SHA. Edits, deletions, untracked Python, index-hidden edits, scoped symlinks and unsupported Git entries fail closed. Git replacement refs are disabled for source identity and tree reads. The same verified bytes feed the AST parser and per-file SHA-256 inventory. |
| CI job provenance | Collection requires an explicit integer provider job count matching the complete returned list, valid identities and unique names/IDs within each attempt. Duplicate jobs cannot overwrite failure facts. Failed or unfinished facts remain available to the separate offline gate; the collector does not invent a success verdict. |

The static guard remains a narrow AST primitive check over `server/` and
`ops/`. Its new inventory binds what the producer scanned; it is not a
complete import-graph audit, a signature, or a new independent attestation
of the producer. Gzip selection is not a claim of full RFC negotiation
coverage, including every possible 406 case.

## Verification

**Final combined local selection: 1,019 passed, zero failures, errors or
skips, 122.04 seconds.** Source hashes before and after the run matched.
This adds **155 regression cases**, and includes ten existing fixture-based
media/evidence checks beyond the preceding 854-test selection.

JUnit SHA-256:
`82960d069b0661919f580ac8d51ea3f79b20e9c09095751ea54e693c86399ef8`.

Reproductions and independent review:

- HTTP boundary regressions initially produced **27 failures / 5 passes**.
  The final focused selection passed **116** checks, including all 69
  mutation-anchor applicability checks. Two existing proxy mutants were
  **KILLED** with passing healthy controls.
- Frontend boundary tests initially produced **28 failures / 9 passes**.
  The final new module has **42** passing Node runtime cases. Independent
  review also covered malformed JSON, safe retry and the real honeypot path.
- Media-policy regressions initially produced **28 failures / 8 passes**.
  The final selection passed **49** checks, including existing positive
  media and evidence-recomputation controls.
- Static source controls initially produced **7 failures / 1 pass**.
  Review found two more directory-alias cases and one Git-replacement case;
  each was reproduced before correction. The final static/catalog selection
  passed **16** checks.
- Job-listing controls initially produced **25 failures / 1 pass**.
  Missing-count rejection was added during independent review. Collector
  and offline-gate checks passed **142** cases together.
- Cross-review added **25** independent HTTP probes. Final independent
  source/collector review passed **70** focused checks. Changed Python AST,
  Node syntax and whitespace checks passed.

These counts describe overlapping focused selections and are **not added**
to the final 1,019 total. Mutation results cover the selected actual mutants;
no full mutation score is claimed.

## Build and execution limits

The complete local selection is not `make gate` or provider acceptance.
Browser/visual execution, three existing Range tests requiring the real
unmaterialized `karier-m.mp4`, complete media/portable builds, live OSV/SAST
and the 1,800-second release soak remain unestablished here. Tests and
required gates have not been disabled or weakened.

Dependencies were reused: Python 3.12.14, pytest 9.0.3, Node 24.22.3,
PyYAML 6.0.3 and packaging 25.0. This is not a new lock-matching install.
The local checkout has synthetic ancestry; its results are local diagnostics,
not provider artifacts for a remote commit.

The multifile export has a separately identified size risk. Its unchanged
132 selected remote asset blobs total **67,086,838 bytes**. Actual emitted
HTML from the final source is **967,391 bytes** (SHA-256
`811ef5e102cfce65b9b94a802f72be2852dce5fe5555b3f7330a50946e09d0dc`).
The metadata-derived sum is **68,054,229 bytes**, exceeding the documented
64 MiB / 67,108,864 bytes by **945,365 bytes**. This calculation uses Git
asset-size metadata plus real HTML; it is not a completed binary build.
The current builder reports size but does not enforce that multifile limit.
Resolved 2026-11-22: the preview serves the 720p hero and omits the 1920 copy;
built package 58,656,312 bytes, cap unchanged — see
[MULTIFILE_BUDGET_PROOF_20261122.md](MULTIFILE_BUDGET_PROOF_20261122.md#resolution--2026-11-22-fixartifact-hero-sd-20261122).

## Integration rule

All six workflows at the remote parent failed before execution: **11 jobs**
with `runner_id=0`, empty runner name and no steps, including the independent
main control. The exact platform cause remains unknown. Current evidence
and the final candidate's run links are maintained in
[issue #35](https://github.com/neuron7x/pbt-site/issues/35).

There are five required candidate-head roles: quality, transport, visual,
security and soak. Evidence closure separately measures exact main; on PR
events it targets the base SHA. Merge remains conditional on actual green
gates and source-bound provider artifacts for the final candidate. No
deployment, forced merge or assurance-ledger promotion is performed.

External launch conditions remain in [PRODUCTION_HOLD.md](PRODUCTION_HOLD.md).
