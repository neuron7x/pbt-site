# ПЛЕЙНБУД — security evidence та ізоляція доставки й відновлення

## Межі зміни

Батьківський PR head: `4f96670cca2de26668ec90561c97856e0713b535`.
Незмінний main на початку ітерації: `828abe1fd3daf0540cd28cd6636600331c195412`.
Робота обмежена `neuron7x/pbt-site`, PR #34. CRM, Lab, deployment і робочі
дані не змінювалися. Публічна палітра, CSS, тарифи, API payload та HMAC
контракт збережені.

Інтегровано чотири перевірені security-зміни з
[PR #33](https://github.com/neuron7x/pbt-site/pull/33) на
`f95654619d8f2506c970bf9046fdbfa01495ac3a`: обидва lock-файли тепер мають
окремі OSV scans та receipts. PR #33 цим не оголошується merged або accepted.
Фінальний consumer додатково закриває прогалини primary/secondary OSV
admission, раніше зареєстровані в
[controller #15](https://github.com/neuron7x/pbt-site/issues/15).

## Відтворені дефекти та виправлення

| Межа | Відтворення | Чинний інваріант |
|---|---|---|
| Локальна HTTP-доставка | За успадкованого `HTTP_PROXY` і порожнього `NO_PROXY` synthetic proxy отримував body та HMAC; справжній локальний receiver не отримував заявки, а outbox був `delivered` | Дозволена loopback HTTP-доставка обходить env proxies. HTTPS зберігає чинну proxy-конфігурацію; redirects і deadlines не послаблено. |
| Приватність recovery-файлів | До завершального chmod заповнені `.restore-tmp` та `.part` мали `0644`; SIGKILL залишав їх читабельними у відкритому каталозі | Обидва файли створюються exclusive з `0600` до першого запису. Наявні file/symlink не перезаписуються. |
| Збереження вибраного snapshot | Cleanup міг видалити input, якщо ним був власний staging-файл або його symlink | Resolved source/staging collision відхиляється до lock, cleanup та запису. |
| Буквальна назва destination DB | `leads[1].db`, `leads*.db`, `leads?.db` інтерпретувалися як glob та видаляли схожі сторонні recovery-файли | Спільний helper для preflight і cleanup зіставляє буквальний prefix/suffix. Чужі файли зберігаються. |
| Декоративний canvas | `getContext('2d') == null` спричиняв uncaught TypeError у startup/measure | Ефект очищує частинки й завершується; queued frame не створює новий RAF. Нормальні 28/60 частинок, DPR cap та рух збережені. |
| Повнота vulnerability scan | Workflow перевіряв лише `requirements.txt`, хоча scanner lock містить додаткові залежності | Окремі baseline/full OSV scans і receipts для кожного lock. Перед кожним скануванням перевірено Git blob та вилучено stale output. |
| Незалежне приймання security evidence | Consumer приймав помилковий baseline, validation errors, неправильний lock, неповний SBOM, відсутній secondary receipt і duplicate JSON keys за узгоджених ZIP digests | Обидва receipts перевіряються за v2 schema, flags, action, source digest, точною множиною назв/версій і нульовими vulnerabilities. SBOM містить усі компоненти та hashes обох immutable locks. JSON keys унікальні на кожному рівні. |

Відтворення виконані на synthetic loopback receivers, тимчасових SQLite/Git
fixtures і контрольованих Node DOM/canvas stubs. Факт production-витоку,
відомої CVE або втрати справжніх заявок не встановлювався.

## Зв'язування доказів із джерелом

`lock_sources_at(root, evidence_sha)` читає тільки `requirements.txt` та
`requirements-sast.txt` через `git cat-file blob`. Поточний HEAD, dirty
worktree або видалені локальні копії не підміняють comparison bytes.
`evidence_reconcile`, `assurance_check` та прямий CLI використовують саме
виміряний commit; для synthetic unit fixtures існує лише програмний параметр,
без CLI/environment override.

Поточна множина — **12 primary + 7 SAST records**, разом **19 SBOM components**;
одна залежність у двох locks має два записи з різним source origin.
Збережено **329 + 85 distribution hashes**. Це перевірена повнота інвентарю,
не результат нового live OSV scan.

Shared parsers потребують packaging/PyYAML. Тому evidence-closure workflow
після перевірки source SHA встановлює чинний hash-locked `requirements.txt`
і перевіряє imports до довгого очікування artifacts. Пороги gate, required
workflow roles і правила мерджу збережені. Історичні неповні receipts
не приймаються як новий доказ: потрібні свіжі artifacts остаточного SHA.

## Верифікація від 21.11.2026

- OSV integration: **2 RED** до зміни; **67 PASS** після інтеграції producer,
  workflow та negative configuration controls.
- Security graph: **21 RED / 1 positive PASS** до consumer fix. Незалежний
  reviewer підтвердив повні synthetic producer→consumer reports, відмову
  на duplicate nested JSON та valid-format, але неправильний component hash.
- Окремий спільний security/acceptance/configuration прогін: **318 PASS**;
  додаткові reviewer controls для hash omission, version drift, boolean count,
  malformed envelopes і measured Git source також пройшли.
- Proxy delivery: **2 RED / 1 PASS → 7 PASS**, включно з HTTPS CONNECT,
  redirects, absolute deadline/HMAC та Unicode controls.
- Чинний `M-NET-03-follow-redirect` адаптовано до нового handler construction,
  без зміни ID/oracle/verdict. На disposable copy healthy oracle **5 PASS**,
  справжній mutant **KILLED**. Усі **69 anchors** застосовні; повний mutation
  score не виміряно.
- Restore privacy/path controls: попередні **44 PASS**; нові literal-path
  regressions дали **5 RED / 4 PASS → 20 PASS** у permissions module.
- Canvas: **1 RED / 3 PASS → 4 PASS**, Node execution, без browser claims.
- Фінальний ширший прогін: **601 tests; 600 passed, 1 failed, 0 skipped,
  0 errors; 68.97 s**. Це **не зелений повний прогін**. Єдиний failure:
  `test_sigkill_parent_kills_inflight_delivery_child` не спостеріг активного
  delivery child через `/proc` до crash injection. Тест та його пороги
  залишені незмінними.
- Окремий A/B probe з попереднім і поточним transport та однаковим parent
  підтвердив причину: live child і його PPid видно через `/proc/<pid>/status`,
  але `/proc/<parent>/task/<tid>/children` відсутній у всіх трьох живих threads.
  Для обох transport: 201, один receiver hit, валідний HMAC; після SIGKILL
  parent child зник, одна lead та pending outbox збережені. Це unsupported
  observation precondition середовища, не встановлена transport regression.
  Діагностика не перетворює початковий failed test на PASS.
- JavaScript syntax, змінений Python AST, прямий verifier CLI import smoke
  та `git diff --check` пройшли.

SHA-256 фінального локального JUnit:
`002496192ba9a338a0d88081d7ae301b0c0ff2d394262075399a1a5135a51f99`.

SHA-256 окремої A/B process-visibility діагностики:
`51232be7815204f02aa49b596c6643ab10f52cd62a16c9d6c6fae4eac5f9c4ff`.

Середовище локального прогону: Python 3.12.14, pytest 9.0.3, PyYAML 6.0.3,
packaging 25.0; використані раніше встановлені залежності. Це не нова
hash-locked installation. Broad Bandit scanner у доступному середовищі
відсутній; його execution не заявляється. Browser/visual, повний media build,
live OSV, 1800s soak та fresh provider evidence не підтверджені локально.

## Merge / production

Остаточний SHA, Git tree перевірка і актуальні provider runs фіксуються в
[PR #34](https://github.com/neuron7x/pbt-site/pull/34). На батьківському SHA
10 jobs п'яти workflows завершилися до runner startup (`runner_id=0`,
`steps=[]`); причина platform-level відмови доступними засобами не встановлена.
Це не доказ провалу або успіху самих CI tests.

Без успішних обов'язкових gates на остаточному head PR лишається Draft.
Локальні targeted results не підміняють provider artifacts, а synthetic
security reports не є результатом нового vulnerability scan. Assurance
ledger не підвищувався до VERIFIED. Production HOLD та зовнішні рішення
залишаються в [PRODUCTION_HOLD.md](PRODUCTION_HOLD.md).
