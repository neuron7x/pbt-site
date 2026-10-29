# Industrial Precision + Sky and Gold — canonical dual-theme system, issue #4 / draft PR #2

**Baseline:** `main@7be8bba75ef612bfc424f31b894e354876d4525b` (2026-10-29).
**Status (2026-10-29):** release gate **PASS on SHA `6c7eefe7985c39a7f5bdd7a1277a9817f52e36e0`** (two independent CI runs, each 255 tests). The follow-up test-coverage commit requires fresh CI; **CWV field proof and owner visual acceptance are still OPEN**.

## Design hypothesis

The existing page has enough motion; adding more creates competing attentional
targets. High-end industrial communication should make physical capability and
procurement decisions legible: real machine → clear task → specifications →
transparent estimate → reliable lead capture.

Reinterpret the original **Sky and Gold** identity rather than replacing the logo.
The original corporate blue `#1A87F5` and gold `#FDC501` remain controlled
action/identity accents. Graphite `#101820`, neutral paper `#F5F5F2`, thin rules,
real photography and typography become the dominant visual substrate.

## UI changes implemented

| Surface | Previous behavior | Industrial Precision |
|---|---|---|
| Hero | Saturated sky montage, sparkles, beams, oversize centered logo, water illustration | Dark cinematic grading, left-aligned editorial composition on desktop, single focal message, subdued transition |
| Navigation | Scroll progress bar, auto-hiding header | Stable header, clear navigation, restrained underline |
| Typography | Widespread uppercase Tektur | IBM Plex Sans editorial hierarchy, mono only for data |
| Services | Five equal mini-cards across desktop | 7/5 feature pair followed by three balanced cards |
| Fleet | 3D cursor tilt, large shadows, gradient buttons | Flat readable cards, specification hierarchy, controlled hover |
| Quote | Decorative colored sum and controls | Clear financial data, dark estimate surface, precise controls |
| Proof | Saturated stats, animated logos | Evidence-first photography, plain stats and static partner logos |
| Decorative motion | Cursor glow, waves, depth gauge | Removed from visible interface; functional animations and existing scroll contracts retained |

**Owner decision — issue #4 (29 October 2026):** The first proposal's separate
`precision.css` has been **removed**. Both «Небо і золото» (`sky`, default) and
«Industrial Precision» (`precision`) are now configured by semantic
custom properties on `:root[data-theme=...]` inside **one `web/css/site.css`**.
All components consume the same properties; no duplicate theme stylesheet is
loaded by the browser or embedded bundle. The header provides keyboard-accessible
`aria-pressed` buttons; a CSP-hashed inline bootstrap sets the saved theme
before the CSS loads, using fail-safe `localStorage` reads. The media and
CRM lead contracts are unchanged. Both themes still require their own CI,
accessibility and screenshot proof before a merge.

## Explicit non-goals and preserved invariants

- No change to `/api/lead`, `/api/config`, `/api/health`, lead fields,
  `Idempotency-Key`, HMAC signature, SQLite outbox or CRM webhook endpoint.
- No fabricated photos, work sites, unit availability, prices or partners.
- No external fonts, trackers, third-party JavaScript, framework or runtime dependency.
- No test disablement and no reduction of existing CI thresholds.
- No direct push to `main`; no deploy or merge in this PR.
- `prefers-reduced-motion` keeps content visible without hero video.
- Current price ambiguity remains a release blocker: marketing visuals must not
  imply that estimates are confirmed quotations.

## Falsification protocol before merge

1. Run `make gate` with all original tests and new visual-contract tests.
2. Run `make shots` / PR #3 for **both themes** at six viewports:
   1440×900, 1024×768, 820×1180, 390×844, 360×640, 320×568.
   Inspect pixels, dimensions and SHA-256 for each screenshot; the actual media
   and content hierarchy require human visual review.
3. Check focus navigation, menu, filters, calculator, form and success/error
   states using keyboard and touch.
4. Use Lighthouse on mobile, CPU/network constrained, and measure LCP,
   INP, CLS. Targets: LCP ≤2.5 s; INP ≤200 ms; CLS ≤0.1. Report
   three cold-load runs and measured median. Never infer a PASS from CSS alone.
5. Execute axe WCAG 2.2 AA with **zero violations in each theme**, plus
   keyboard/focus, live footage contrast and layout-stability checks.
   Axe alone cannot verify every accessibility requirement.
6. Verify all video sources, poster fallbacks, external licensing and original
   footage owner approval. AI super-resolution increases apparent sharpness,
   **not** the actual recorded detail or authenticity.
7. Recheck source prices and VAT against owner-approved CRM records before
   public presentation.

## Verified CI evidence and remaining limits (29 October 2026)

| Scope | Immutable SHA | GitHub Actions run | Observed result |
|---|---|---|---|
| PR #2 canonical two-theme branch | `6c7eefe7985c39a7f5bdd7a1277a9817f52e36e0` | [40865394201](https://github.com/neuron7x/pbt-site/actions/runs/40865394201) | Smoke **29 passed**; `make gate` **255 passed**, workflow success; seven baseline screenshots uploaded |
| PR #2 independent verification | same SHA | [40865387315](https://github.com/neuron7x/pbt-site/actions/runs/40865387315) | Smoke **29 passed**; `make gate` **255 passed**, workflow success |
| Stacked PR #3 screenshot/evidence scope (not PR #2 code) | `62567ea85364bb2c4a8637c8b96a19518796d8b8` | [40865735337](https://github.com/neuron7x/pbt-site/actions/runs/40865735337) | `make gate` **268 passed**; media budget: **160 files, 116103276 bytes, zero violations**; **32 screenshots**, Chromium 143.0.7499.4, screenshot script reports zero violations and generated `artifacts/shots/manifest.json` |
| Stacked PR #3 general quality workflow | same SHA | [40865735489](https://github.com/neuron7x/pbt-site/actions/runs/40865735489) | Workflow success |

The old failure in run [40864813680](https://github.com/neuron7x/pbt-site/actions/runs/40864813680)
was a **test/source import-string expectation mismatch**
(`test_inline_builder_uses_shared_contract_for_both_outputs`, 1 failed
and 28 passed), not a proof of an actual CSS duplication. The current
SHA passes the corrected contract. Cancelled superseded runs do not
count as passing or failing verification.

**What these results do and do not establish.** The committed PR #2
tests cover both `sky` and `precision` with axe WCAG 2.2 AA on
desktop and phone, six viewport sizes for keyboard persistence,
localStorage-denied mode, no unrequested media replacement, prepaint
CSP-hashed restore, reduced motion and a desktop layout-shift observer.
This follow-up coverage commit expands **axe to 2 themes × 6 viewports**
and **layout-shift observation to 6 viewports**; those new checks must
pass at the new SHA before being called verified. PR #3 owns screenshot
acceptance; a generated PNG and SHA-256 alone do **not** establish visual
quality. Owner pixel-level review remains outstanding.

`docs/RELEASE_STATUS.md` cites historic Lighthouse mobile performance
~50 at a different commit. **No verified mobile CWV results for this
head** demonstrate LCP ≤ 2.5 s, INP ≤ 200 ms or CLS ≤ 0.1 under real
field conditions. Real video-frame contrast, source-data freshness,
copyright/footage approval and owner visual acceptance remain open.
Do not infer an accessibility certification solely from axe, or a
release authorization from a successful automated gate.

## Follow-up PR sequence

- **PR-02:** select high-quality authentic hero/poster material; optimize decode
  budget and mobile poster-first behavior.
- **PR-03:** catalog/estimate ergonomics and price integrity; fix `Маса` vs
  `Вага` mass field; validate accounting, distance and VAT explicitly.
- **PR-04:** modularize CSS/JS with stable render and data contracts; add visual
  screenshot comparisons and performance budgets.
- **PR-05:** read-only CRM-backed public catalog and pricing snapshots with
  TTL, provenance and fail-closed data quality.

**Merge condition:** real green gate + browser evidence + owner-approved
visual comparison. A premium visual impression is not machine-verifiable
from source code alone.
