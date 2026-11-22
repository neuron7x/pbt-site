# Multifile package budget · source-bound 2026-11-22

**Status: NOT YET ACCEPTED / MEDIA VALIDATION HOLD.** This is a reproducible arithmetic proof of an oversized **unoptimized** candidate, not a verified optimized package or field visual acceptance.

## Resolution · 2026-11-22 (`fix/artifact-hero-sd-20261122`)

**Status: FITS, measured on a full local build.** The Artifact preview omits the 1920 hero copy
`media/video/hero-wide.mp4` (9,397,955 bytes) and sets `window.PBT.heroSD = true`, so `heroHD()`
selects `hero-wide-720.mp4`. Nothing is re-encoded; the live site and the single-file bundle keep
every source asset. Explicit trade-off: in the claude.ai preview only, screens with
`innerWidth × devicePixelRatio ≥ 1600` see the 720p hero instead of 1920p.

| Measurement | Bytes |
|---|---:|
| Built `dist/artifact` total (`dist/artifact-budget.json`, `ok: true`) | **58,656,312** |
| Maximum | 67,108,864 |
| Margin | **8,452,552** |

Chromium on the served preview: 1920×1080 requests `hero-wide-720.mp4`, 390×844@3 requests
`hero-tall.mp4`; 0 HTTP ≥ 400, 0 page errors. Guard: `tests/test_artifact_hero_sd.py`
(3/3 mutants killed). The cap is unchanged; the reproducibility test now sees exit 0.


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

- **Normal `tools/inline.py` is deterministic, byte-for-byte copying the approved repository media.** It writes the complete SHA-256/byte preflight report outside `dist/artifact`, then performs the unchanged **67,108,864-byte hard gate**. An oversized package is **rejected** with an inspectable final report. The build never reencodes video, drops media or weakens the cap.
- **Optional offline *postbuild* trial:** `python3 tools/artifact_video_fit.py --root dist/artifact`. This is deliberately **not invoked by `make gate` or the exporter**; real GitHub CI proved auto-encoding breaks the deterministic/reproducibility contract. The trial touches **copied** MP4 inside the output directory only, never `web/media`. It creates `dist/artifact-video-fit.json` and `dist/artifact-budget-after-fit.json`, with clear `release_authorization=NOT_GRANTED`.
- A suggested transcode is usable only if **actual bytes decrease**, decoded dimensions and frame count match, `mean(framewise SSIM) >= 0.995`, `min(framewise SSIM) >= 0.985`, and the input and output SHA-256 values are retained. These are **objective rejection controls**, **not a claim of perceptual equivalence or human acceptance**. Six trials maximum, 360-second target, bounded subprocesses and 2 encoder threads.
- An optimized disposable output is **not** a reproducible canonical release until the selected binaries are independently reviewed, accepted and distributed as approved immutable source assets; simply rerunning the exporter would recreate the original source-driven bytes and rightly fail the size gate.
- Verified CI red evidence: [validation PR #40](https://github.com/neuron7x/pbt-site/pull/40), source `2d7eff17a55d497e31e761477427601dead31e86`, mutation job failed `positive_control_failed` because `test_reproducibility.py` received a nonzero return from the exporter. The auto-fitting design has been **withdrawn**; the reproducibility test now explicitly requires any nonzero result to be the measured, deterministic **size-budget rejection** and rejects other failures. No change to production or media assets.
- Original full-resolution video media remain intact; release still requires genuine binary budget compliance, browser codec/playback proof, human premium-quality acceptance and owner rights/availability approvals.

## Pending independent evidence and exit condition

1. Run complete `make gate` on the **exact new candidate SHA** with actual 132 source media; archive `dist/artifact-budget-preflight.json`, `dist/artifact-video-fit.json` (if invoked), `dist/artifact-budget.json` and actual optimized output byte hashes.
2. Verify video playback on desktop/mobile browsers, motion/reduced-motion, poster fallback and codec support. SSIM is necessary **but insufficient** for a premium aesthetic claim.
3. Check original/optimized MP4 samples with a named human evaluator and retain the acceptance matrix; otherwise remain HOLD.
4. Close the provider's complete source-bound evidence / owner decisions in `docs/PRODUCTION_HOLD.md`; a green size check does **not** authorize public deployment.
5. If no candidate meets quality and size constraints, **leave release blocked** and seek better source-based encoding settings or authorized publication format changes; do not weaken either size or quality thresholds.

**No claim that the 64 MiB target is achieved until a complete binary build demonstrates it.**
