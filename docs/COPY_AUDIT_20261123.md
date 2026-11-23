# PLAINBUD copy audit · evidence-first intervention · 2026-11-23

Snapshot: main cdfece2463c520f1b499c2b778e126274bde899d. Scope: current web/index.html, catalog, business config, owner decisions, rebrand, production hold and CRM boundary. This is a scoped source audit, not an empirical buyer study or visual acceptance report.

## Prioritized findings (baseline → treatment)

| Severity | Surface | Baseline flaw | Intervention | Validation class |
| --- | --- | --- | --- | --- |
| Critical | #top / #tekhnika / #dokaz | «32 одиниці» implies a verified physical fleet | «32 позиції каталогу»; 8 distinct categories counted from data/catalog.json | Deterministic repository fact, NOT asset ownership |
| Critical | #cina / metadata | Old prices might be read as current; owner register identifies JCB JS220 1,350 site vs 2,700 in 1C | Explicit historic tariff date near form and calculation; no contract quote claim | Owner decision B1/B2 unresolved |
| Critical | #materialy | All fractions allegedly accompanied by certificates and radiation document | Require batch-specific document confirmation before orders | Owner-specific documentary proof needed |
| High | #roboty | «дзвонять найчастіше» asserts non-existent frequency baseline; «техніка на об'єкті в домовлений день» resembles an SLA | Work-class taxonomy; delivery constraints in context | Operational receipts needed for stronger promises |
| High | #dokaz | Legacy PBT media could be confused with verifiable PLAINBUD work | Identify as legacy illustrative source; don't invent completed PLAINBUD projects | Rights/provenance B5/B6 open |
| High | #geo / hero | «9 областей» might read as confirmed dispatch capability | Describe geography as a request and verify routes before quotation | Owner confirmation + dispatch records |
| Medium | #zapyt | «Викликати»/«Замовити цю зміну» implies a booking action | «Надіслати запит» and «Додати параметри до заявки» | CRM contract read; human decision remains |
| Medium | hero | Generic «для складних робіт» not a differentiated buying problem | «Важкі умови. Техніка під об’єкт.» with service-class naming | Editorial hypothesis, not claimed uplift |
| Medium | SEO | Title has many service keywords in one line | More focused title with contextual descriptive metadata | Indexing/CTR must be measured only post-launch |

## What was deliberately NOT implemented

- No market-first claim, copied competitor slogans, customer logos/testimonials or invented case studies.
- No external SEO/analytics/recording tool, fake price discount, time-limited CTA or unapproved domain.
- No change to server/app.py, SQLite outbox, PBT CRM signature/header, input names, type enum, CSS design tokens or motion architecture.
- No change to rate calculation, despite the known discrepancy: adjusting business pricing belongs to the owner, not a copywriter.
- No statement that title, copy, typography or visuals have already improved qualified-lead conversion.

## Audience hypotheses / decision jobs

- Site supervisor: find a technically plausible machine fast; identify site constraints (soil, access, length, load).
- Procurement: receive a reviewable estimate with tariff/VAT basis; avoid hidden minimum shifts and idle costs.
- General contractor: connect machinery class to a specific project phase and coordinate date/logistics.
- Municipal buyer: require documented procurement terms and individual material certifications; no assumptions about tender eligibility.
- Material buyer: request exact fraction, volume, delivery address, and party-specific documents.

These are working hypotheses, not observed visitor research. Interview before running experiments.

## Semantic treatment and future research

Primary intent: "оренда спецтехніки Полтава". Secondary intents: "екскаватор амфібія", "автокран", "перевезення тралом", "днопоглиблення", "щебінь фракція", matched to real catalog and pages. Avoid location doorway texts if no local operational proof.

For real competitor comparison collect URLs and date-stamped screenshots, one row per evidenced claim: available service, fleet documentation, price conditions, actual order path, credibility documents, service area, accessibility. Comparisons cannot be concluded from this source repository. Criteria must be fixed before checking outcomes. Do not rank PLAINBUD No. 1.

## Verification ladder

A. Source parity (code): test catalog count 32 and categories 8; title and accessible CTA text; 2 themes; no substituted form contract. B. Claims ledger: blocked claims cannot appear as unconditional public assertions. C. Business evidence: signed owner acknowledgements and primary records; still HOLD until docs/PRODUCTION_HOLD.md closes. D. Empirical measurement: approved analytics + qualified CRM outcomes + preregistered experiment, not click rates alone.

Dated standards/guidance: W3C WCAG 2.2 https://www.w3.org/TR/WCAG22/ ; Google Search Central https://developers.google.com/search/docs/fundamentals/creating-helpful-content ; Ukrainian laws https://zakon.rada.gov.ua/laws/show/270/96-%D0%B2%D1%80#Text and https://zakon.rada.gov.ua/laws/show/2297-17#Text . These specify constraints/guidance, not evidence that a particular headline sells better.

## Owner-only questions

(1) Effective-dated, approved tariff list and VAT/minimum shift/idle/dispatch policy. (2) Current equipment availability, commercial basis (owned/contracted), capacities and dispatch regions. (3) Per-video source/rights and permission to show under PLAINBUD. (4) Documents per shipped material batch. (5) Privacy notice/retention and live lead receiver, domain and handoff owner.

## Acceptance / falsification

Fail on a new unconditional ownership, leadership, dispatch SLA, batch certification or approved-tariff claim without external receipt. Fail on a changed CRM wire field. Fail on a broken headline layout or inaccessible control. Fail on conversion uplift asserted from code tests. An owner-signed fact authorizes only its scope and effective period, not extrapolation to every project.

No release or merge authorization is expressed by this document.


## Follow-up: adjacent price provenance and operational titles

- Fleet and material prices are generated from data/catalog.json in web/js/site.js. A general note beneath the catalog does not ensure the user notices the date. This PR now places the dated provenance directly next to every numeric card rate; current tariff approval is **still blocked**.
- The word «диспетчер» asserted a staff role not attested in business.json. User-facing fallbacks now invite a phone call without implying a separate dispatch department. This does not change the actual contact channel.
- Hero eyebrow now explicitly states «Оренда спецтехніки · Полтава» to pair an original value proposition with the buyer's service/location vocabulary. Google Search Central title-link guidance is a design constraint, not evidence of higher rankings: https://developers.google.com/search/docs/appearance/title-link .
- Browser test tests/test_frontend_finish.py checks that every rendered priced card carries the historical rate date; field date and prices still require an owner-signed snapshot before launch.
