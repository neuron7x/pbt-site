# Multifile package budget · source-bound 2026-11-22

**Status: NOT YET ACCEPTED / MEDIA VALIDATION HOLD.** This is a reproducible arithmetic proof of an oversized **unoptimized** candidate, not a verified optimized package or field visual acceptance.

## Two independent inputs

| Measurement | Grounding | Bytes |
|---|---|---:|
| `dist/artifact/index.html` | GitHub Actions full-quality [run 44994717961](https://github.com/neuron7x/pbt-site/actions/runs/44994717961), release ZIP artifact ID `14744155704`, exact PR #34 candidate `d6cbc7d7d6fb31993cac796b37472ceb814231f4`; raw ZIP member size and SHA256 independently checked | **967,391** |
| Assets copied by `tools/inline.py` | Exact GitHub tree `018536e9b3f42aa34dfbd2b635652cc86395c997` (equivalent media tree after main reconciliation); 132 entries selected by source copier's extension/name rules; sum of authenticated Git blob `size` fields | **67,086,838** |
| **Implied complete unoptimized package** | Integer addition; archive metadata plus verified emitted HTML, **not measured full-media directory bytes** | **68,054,229** |
| Maximum | `64 * 1024 * 1024` bytes | **67,108,864** |
| **Excess** | `max(0, 68,054,229 - 67,108,864)` | **945,365** |

The HTML's independently verified SHA256 is `811ef5e102cfce65b9b94a802f72be2852dce5fe5555b3f7330a50946e09d0dc`. The CI release ZIP digest is `b495714762da1d5e81cd3ba16d7c3a3a6cec7f2da13e4093d2b75ec37ec57a76`; its ZIP contains the emitted HTML **but not the 132 media files**. Thus the overall 68,054,229 bytes is a tightly source-derived accounting **conditional on the copier**, not a falsely claimed full binary export read.

**Do not remove** source videos, mobile variants, high-density material images, motion features or any source attribution merely to pass the limit. An apparently unused media filename requires independently verified HTML/JS/CSS dynamic-reference evidence before exclusion.

## Implemented controls · [Draft PR #36](https://github.com/neuron7x/pbt-site/pull/36)

- Unoptimized output is inventoried with actual bytes and SHA-256; a full preflight report is written outside `dist/artifact/`.
- **Only if oversize**, a bounded video-optimization attempt operates on MP4 **copies inside the export**, not on `web/media/` or CRM assets. No video is silently omitted, disabled, substituted by a lower-resolution variant or sent to an external encoder.
- A candidate is accepted only when its **actual bytes decrease**, decoded dimensions and frame count are preserved, `mean(framewise SSIM) >= 0.995`, `min(framewise SSIM) >= 0.985`, and its pre/post SHA-256 are recorded. These are **objective regression controls**, **not perceptual equivalence or human acceptance**. Six trials maximum with 360-second elapsed target, bounded subprocess timeouts, 2 encoder threads.
- After any accepted candidates, the builder re-audits **all actual export files** and enforces the unchanged **67,108,864-byte hard limit**. Exceeding it fails the bundle. Metrics plus hashes remain inspectable.
- The full original source media are unchanged by construction; release still requires a separate browser / human premium-quality and rights review of actual optimized videos. No exact-head GitHub runner test of this PR has been executed at this writing.

## Pending independent evidence and exit condition

1. Run complete `make gate` on the **exact new candidate SHA** with actual 132 source media; archive `dist/artifact-budget-preflight.json`, `dist/artifact-video-fit.json` (if invoked), `dist/artifact-budget.json` and actual optimized output byte hashes.
2. Verify video playback on desktop/mobile browsers, motion/reduced-motion, poster fallback and codec support. SSIM is necessary **but insufficient** for a premium aesthetic claim.
3. Check original/optimized MP4 samples with a named human evaluator and retain the acceptance matrix; otherwise remain HOLD.
4. Close the provider's complete source-bound evidence / owner decisions in `docs/PRODUCTION_HOLD.md`; a green size check does **not** authorize public deployment.
5. If no candidate meets quality and size constraints, **leave release blocked** and seek better source-based encoding settings or authorized publication format changes; do not weaken either size or quality thresholds.

**No claim that the 64 MiB target is achieved until a complete binary build demonstrates it.**
