# Research-grade copy toolchain · PLAINBUD · 2026-11-23

**Evidence not prestige.** A standard specifies constraints, a linter detects strings, a buyer study tests comprehension, and a randomized experiment estimates causal effects. None of these alone proves a unique aesthetic or company-wide leadership. Tool maintenance/version information has not been independently rechecked on 2026-11-23; verify release metadata before installing.

## Authority hierarchy by proposition

1. **Company truth:** dated signed owner tariff/dispatch receipt, operational fleet inventory, permissions for each image/video, proof of completed work, material-batch certificate, authorized CRM status. Current repository has open release blockers and no such full set of independent operational receipts. The owner-supplied company card does not establish superiority or fleet ownership.
2. **Norms / public regulation:** applicable Ukrainian advertising law (https://zakon.rada.gov.ua/laws/show/270/96-%D0%B2%D1%80#Text), data protection (https://zakon.rada.gov.ua/laws/show/2297-17#Text), official Ukrainian orthography and published legal interpretations. Authoritative for legal/linguistic constraints, NOT for conversion uplift. Current legal amendments require verification at review time.
3. **Normative web accessibility:** W3C WCAG 2.2 (https://www.w3.org/TR/WCAG22/) supplies testable success criteria. Automated axe tests are necessary regression evidence, not complete conformance certification.
4. **Search engine implementation guidance:** Google Search Central (https://developers.google.com/search/docs/fundamentals/creating-helpful-content) for helpful content and clear search intent; Search Console after domain authorization. Vendor guidance does not constitute an academic causal result.
5. **Methods for controlled vocabulary/plain language:** ISO 704 and ISO 24495-1 are relevant paid standards; exact edition, licensing and verbatim requirements should be reviewed before declaring conformance. Their names are not evidence that our copy improves B2B leads.
6. **Empirical evidence:** peer-reviewed studies with a representative industry population, documented tasks, limitations, preregistration and uncertainty; moderated Ukrainian buyer comprehension studies can be more locally valid than generic marketing benchmarks.
7. **Usability heuristics:** NN/g, Baymard and industry examples are secondary guidance. Different populations, devices, services and business contexts limit transfer.
8. **Generators/LLM copy tools:** useful for variants and adversarial objections; **no epistemic authority** for operational facts, buyer behavior, originality or performance.

## Recommended constrained stack (implemented vs proposed)

| Tool | Role | Status in this repo / limit |
| --- | --- | --- |
| Python 3 stdlib + HTMLParser | Static content extraction and claim-state lint | Implemented: tools/copy_gate.py and tests/test_copy_gate.py; only prelisted obvious claims, not a semantic truth oracle |
| pytest | Regression/mutation counterexamples | Existing repository runner; copy tests included in make test and gate |
| Playwright Chromium/WebKit + axe-core | Text wrap, accessible labels, reduced motion, user flow and contrast | Existing test tools; screenshot/browser execution must be evidenced on the PR head |
| Vale (official https://vale.sh/) | Extensible prose lint with project-specific vocabulary rules | Candidate; Ukrainian morphology and quality are not established by merely adding regex; benchmark false positives on site |
| LanguageTool (https://languagetool.org/) | Candidate Ukrainian spelling/grammar review | Language coverage, backend availability, policy, API rate and data transmission must be verified; no external service called by this PR |
| Ukrainian morphological resources (e.g. Universal Dependencies models / Stanza) | Optional lemma and part-of-speech terminology checks | Research option; pretest domain-language accuracy; not a replacement for technical copy editor |
| Lighthouse / PageSpeed (https://developer.chrome.com/docs/lighthouse/) | Lab page metrics / a11y diagnostics | Candidate after test-site deployment; field Core Web Vitals cannot be inferred from lab alone |
| Schema.org Validator / Google Rich Results Test | Inspect structured data and supported search features | Candidate after business identity/domain evidence; schema markup does not imply Google endorsement |
| Google Search Console | Search query and CTR diagnosis | Not enabled until verified domain + owner permission |
| Matomo (self-hosted) | First-party aggregate measurement after privacy decision | Not installed; still requires consent/legal basis review and retention settings |
| CRM qualified-outcome ledger | Decided/quoted/completed lead indicators | Private, separate repo; use existing signed contract and approved joins, never modify wire format |

Do not add all tools to runtime. Tier 1 is stdlib + repo tests + human review + owner receipts; Tier 2 enables external measurement only after authorization and adequate volume.

## Buyer interview / measurement protocol

Recruit real procurement staff, site managers and buyers; do not fabricate personas as evidence. Ask each participant to complete a realistic request: choose an amphibian for restricted access, identify the crane capacity, compare transport constraints, and determine whether a displayed price is binding. Record success, misunderstanding, time and independently coded objections. Use the same tasks for baseline/variant, blind where practical. Capture minimal personal data with approval.

A/B tests are hypotheses, not promises. Preregister primary outcome **qualified lead** as a CRM-reviewed feasible site inquiry, and guardrails: spam, duplicate leads, bad-price objections, a11y, latency, no-contact requests. For sparse B2B traffic, report descriptive estimates and uncertainty; avoid p-hacking by not peeking and stopping on favorable clicks. Do not invent traffic, sample size, uplift or buyer sentiment.

## Competitive evidence register (not yet populated)

A serious comparison requires time-stamped public competitor URLs, exact service categories, target city, quoted prices with VAT/dispatch scope, proof portfolio and a verifiable lead path. This repository alone cannot establish competitor offerings. Classify each as owner data, public self-claim or independently verifiable outcome; never conclude «№1» from copied headings. A future research agent may populate a separate comparison dataset with source, capture date and expiries, without touching source copy until approved.

## 7 / 30 / 90-day action sequence (relative to approval, not a promise)

**Day 0–7**: complete receipt requests B1/B2/B5/B6/B7/B8, human Ukrainian technical editing, compare desktop/mobile text wrap, run exact-head make gate. No production push merely because this PR is green.

**Day 8–30**: conduct 5–8 task-based interviews as a research planning target, not a claim of statistical generality; reconcile documentation, validate asset rights, review competitors with captured evidence and prepare restrained structured data after domain decision.

**Day 31–90**: if authorized pilot is live, collect privacy-approved aggregate lead funnel and CRM outcomes, preregister one change at a time, assess qualified leads and adverse pricing contacts. If sample insufficient, prefer qualitative design iteration over manufactured significance.

Release falsification: one unsupported promise, a broken input mapping, a changed PBT signature contract, a false pricing condition, or a visual accessibility regression means HOLD. No deployment or business claim promotion from documentation alone.

