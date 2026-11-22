# PBT Site — Primary-source Bibliography and Standard-to-Test Mapping

**Evidence date:** 2026-11-02. **Method:** prefer the originator's normative specification, published version and official documentation; record distinction between normative requirement, guidance, methodology, industry-adopted practice, and draft. A link does NOT itself certify this project. All project mapping here is an audit proposal, not a claim of total conformance.

## A. Secure software lifecycle and assurance

| Ref | Source, version/status | Primary URL | PBT scope and falsifiable use |
|---|---|---|---|
| NIST-SSDF-11 | NIST SP 800-218, Secure Software Development Framework v1.1, final 2022 (still final in NIST list at audit) | https://csrc.nist.gov/pubs/sp/800/218/final | W0/EVD provenance, PW secure coding, RV feedback, PS integrity; assess evidence binding, not marketing claims |
| NIST-SSDF-12-DRAFT | NIST SP 800-218 Rev.1 SSDF v1.2, initial public draft dated 2025-12-17; **NOT FINAL** | https://csrc.nist.gov/pubs/sp/800/218/r1/ipd | Research comparison only; cannot claim final-standard conformity |
| OWASP-ASVS-5 | OWASP Application Security Verification Standard 5.0.0, stable release 2025-05-30 | https://asvs.owasp.org/ and https://asvs.owasp.org/downloads/ | Control-by-control security requirements for HTTP, logging, injection, resource/process controls; version IDs `v5.0.0-N.N.N`, no blanket ASVS certification |
| OWASP-WSTG-42 | OWASP Web Security Testing Guide 4.2 (stable while 5.0 is development) | https://wstg.owasp.org/v4.2/4-Web_Application_Security_Testing/ | Reproducible adversarial web scenarios; check input, configuration, errors, weak cryptography and logic; WSTG is guidance, not an automatic certificate |
| SLSA-12 | SLSA specification v1.2 **Approved**, current version at audit | https://slsa.dev/spec/v1.2/ | Source/build integrity provenance and independent verification; do not declare a SLSA level until full published controls are met |
| GITHUB-SECURE | GitHub Actions secure-use reference | https://docs.github.com/en/actions/reference/security/secure-use | Pinned full-sha Actions, least-privilege token, workflow trust and avoidance of secret leakage |
| GITHUB-ATTEST | GitHub artifact attestation guide | https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations | Evaluate verifiable build provenance; if unsupported for private repo/plan, explicitly mark unavailable rather than claim attested |
| GITHUB-RULESETS | GitHub managing rulesets, documented plan eligibility | https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets | Fix `main.protected=false` with actual enforceable admission where the owner's GitHub plan supports it |

## B. HTTP, SQLite and recoverability

| Ref | First-party specification | URL | Observable PBT test or gate |
|---|---|---|---|
| RFC9112 | IETF RFC 9112 HTTP/1.1, Internet Standard June 2022 | https://www.rfc-editor.org/rfc/rfc9112 | Header and framing ambiguities, duplicate/mismatched length, body close, parsing, request-smuggling disagreement, connection deadlines; NET-01/NET-02 |
| SQLITE-FK | SQLite Foreign Key Support / PRAGMA | https://www.sqlite.org/foreignkeys.html and https://www.sqlite.org/pragma.html | Explicit per-connection `PRAGMA foreign_keys=ON` outside transactions + readback, orphan rejection; DB-01/DB-02 |
| SQLITE-BACKUP | SQLite Online Backup API | https://www.sqlite.org/backup.html | Consistent live snapshot and integrity; DB-06; not power-loss certification |
| NIST-DR | NIST SP 800-34 Rev.1 contingency planning update (final update 2010-11-11) | https://csrc.nist.gov/pubs/sp/800/34/r1/upd1/final | Recovery priorities, independent host DR, authorized RPO/RTO and evidence; DB-07/DB-08 |
| LAMPORT-TLA | Leslie Lamport, Specifying Systems (2002), primary technical book | https://www.microsoft.com/en-us/research/publication/specifying-systems-the-tla-language-and-tools-for-hardware-and-software-engineers/ | Optional formal state model of lead/outbox crash/retry machine; TLC exploration is recommended if model is written, not claimed performed |

## C. Accessibility, visual evidence and field performance

| Ref | Originator and current status | URL | PBT application |
|---|---|---|---|
| WCAG22 | W3C WCAG 2.2 Recommendation (2024-12-12 edition) | https://www.w3.org/TR/WCAG22/ | A/AA full-page conformance including 320CSS px reflow, keyboard, contrast, motion and time-based media; WEB-01/WEB-04 |
| WCAG-EM2 | W3C WCAG Evaluation Methodology 2.0 (published 2026-07-23) | https://www.w3.org/WAI/test-evaluate/conformance/wcag-em/ | Structured conformance scope, sample, accessibility tools, manual assistive-tech verification and report; WEB-01/ADV-07 |
| CWV | Google web.dev Core Web Vitals thresholds | https://web.dev/articles/vitals | Field 75th percentile, mobile/desktop separate: good LCP <=2.5 sec, INP <=200 ms, CLS <=0.1; WEB-02/WEB-03 |
| SRE-SLO | Google SRE Workbook: Implementing SLOs | https://sre.google/workbook/implementing-slos/ | Explicit customer-critical SLIs, adopted SLO and error-budget policy before reporting production reliability; OPS-01..03 |

## D. Applicable Ukrainian law — not a U.S. technical standard

| Ref | Primary law | URL | Required local assessment |
|---|---|---|---|
| UA-PD-2297 | Law of Ukraine No.2297-VI On Personal Data Protection, effective edition shown on Parliament site (2025-06-14) | https://zakon.rada.gov.ua/laws/show/2297-17 | Art.6 legal purpose, transparent processing and limited identifying retention; Art.8 subject rights; lawful basis, informed notice, actual retention/deletion and legitimate accounting records must be set by owner with qualified counsel. Do not infer universal mandatory consent from the law without case-specific grounds. |

## E. Source version integrity instructions

1. Cite immutable editions where possible: OWASP ASVS v5.0.0 and WSTG v4.2, WCAG 2.2 W3C Recommendation and current approved SLSA 1.2, rather than `master/latest` with mutable contents.
2. Verify the exact relevant control text before writing an ASVS requirement ID. Avoid fabricating requirement IDs or treating broad mappings as formal verification.
3. Separate normative `MUST` in primary RFC/WCAG from RECOMMENDED engineering choices; a WSTG exercise is not a legal obligation.
4. NIST SSDF 1.2 remains DRAFT per the NIST publications index as reviewed; stable baseline is SP 800-218 v1.1.
5. A test for one property does not establish total conformance with an entire standard. Each claimed requirement requires its own implementation, environment, evidence and failure model.
6. Record publication date, accessed date, source URL, expected version and relation to a specific PBT test or evidence object; archive citations in the issue/PR.

## F. Operational toolchain and standards-scoped controls

| Goal | Available/recommended tool | Acceptance criterion / caveat |
|---|---|---|
| Browser UX, video and keyboard | Playwright Chromium/WebKit, screenshot manifest, axe-core | Browser-specific reproducible state; axe zero != full WCAG |
| Performance | Browser PerformanceObserver, repeatable Lighthouse/lab probe, field `web-vitals`/CrUX where permitted | Raw samples, per-theme p75, device split and actual user exposure |
| Durability | SQLite transactions/PRAGMAs, isolated process SIGKILL, fault injection | Durable lead/outbox invariants + declared storage assumptions |
| Evidence | GitHub Actions API artifacts, SHA256, ZIP/PNG CRC, JUnit, `meta_evidence_gate.py` | Authentic source-event-run-artifact binding, corrupted bytes fail closed |
| Code and supply chain | pinned dependency audit, targeted AST/SAST, SBOM and SLSA provenance verifier | Only claim tested vulnerability classes; no silent failure and no unsupported SLSA level |
| Reproducible media | FFmpeg, versioned filter graph/LUT, SHA256 checked original sources | Results hashed under declared source/toolchain input; AI upscaling is not original footage proof |
| Operations | systemd dedicated system unit, sandbox probe, external encrypted backup and separate-host drill | Real host resources constrained; actual RPO/RTO and receiver-side receipt |

**Bibliographic warning:** `IEEE/ISO compliant`, `NIST certified`, `WCAG certified`, `SLSA L3`, `pen-tested`, and `100% secure` are NOT justified by the present source or CI status. This bibliography is the basis for new independent verification, not a certificate.

**Evidence links:** `00_AUDIT_ACT.md`, `01_TASK_REGISTER.md`, `02_EXECUTION_AND_ACCEPTANCE.md`.