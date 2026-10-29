# Industrial Precision — visual system, PR-01

**Baseline:** `main@7be8bba75ef612bfc424f31b894e354876d4525b` (2026-10-29).
**Status:** design implementation proposed in a draft PR, **not yet browser-verified**.

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

**Owner decision — issue #4 (29 October 2026):** The first proposal's separate\n`precision.css` has been **removed**. Both \u00abНебо і золото\u00bb (`sky`, default) and\n\u00abIndustrial Precision\u00bb (`precision`) are now configured by semantic\ncustom properties on `:root[data-theme=...]` inside **one `web/css/site.css`**.\nAll components consume the same properties; no duplicate theme stylesheet is\nloaded by the browser or embedded bundle. The header provides keyboard-accessible\n`aria-pressed` buttons; a CSP-hashed inline bootstrap sets the saved theme\nbefore the CSS loads, using fail-safe `localStorage` reads. The media and\nCRM lead contracts are unchanged. Both themes still require their own CI,\naccessibility and screenshot proof before a merge.

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
2. Run `make run` and `make shots`. Compare desktop at 1440×900,
   1366×650, 1024×768 and mobile at 390×844, 360×640, 320×568.
   Manually inspect responsive typography, real videos and content hierarchy.
3. Check focus navigation, menu, filters, calculator, form and success/error
   states using keyboard and touch.
4. Use Lighthouse on mobile, CPU/network constrained, and measure LCP,
   INP, CLS. Targets: LCP ≤2.5 s; INP ≤200 ms; CLS ≤0.1. Report
   three cold-load runs and measured median. Never infer a PASS from CSS alone.
5. Execute axe + human WCAG 2.2 AA review; inspect contrast on multiple
   actual video frames. Axe alone cannot verify every accessibility requirement.
6. Verify all video sources, poster fallbacks, external licensing and original
   footage owner approval. AI super-resolution increases apparent sharpness,
   **not** the actual recorded detail or authenticity.
7. Recheck source prices and VAT against owner-approved CRM records before
   public presentation.

## Baseline evidence limits

`docs/RELEASE_STATUS.md` reports historic Lighthouse mobile performance ~50,
182 tests passing at an older commit (`d5193f1`). Neither result proves
the current branch is correct. No new Lighthouse, screenshot comparison or
local `make gate` execution has been claimed by this PR.

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
