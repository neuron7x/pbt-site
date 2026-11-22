# ПЛЕЙНБУД — цілісність заявок, резервних копій і доказів

## Межі ітерації

Перевірено й посилено код від PR head
`9ae367c5d643bb9e6260daaf2f935818d0572df3` у `neuron7x/pbt-site`.
Порівняльний `main`: `828abe1fd3daf0540cd28cd6636600331c195412`.
Власник доручив автономно знаходити й виправляти технічні дефекти;
merge лишається умовним до успішного повного gate.

Відтворення використовують тимчасові Git-репозиторії, синтетичні SQLite-бази,
loopback HTTP і контрольовані DOM/media/network stubs. Робочі бази,
credentials, deployment і сторонні репозиторії не змінювалися.

## Інваріанти та закриті дефекти

| Інваріант | Відтворене порушення | Виправлення |
|---|---|---|
| Вихідна база не належить каталогу очищення backup | Retention міг видалити власну source DB і повернути `backup OK`; cleanup міг також зачепити source з назвою `.tmp` | До mkdir/chmod/lock/cleanup перевіряються configured parent та resolved target parent. Колізії, включно із symlink aliases, відхиляються без зміни файлів і прав. |
| Restore читає саме вибраний файл | `snapshot.db#chosen` міг прочитатися як сусідній `snapshot.db` через SQLite URI | Read-only URI формується через `resolve().as_uri()`. `#`, `?` і percent sequences лишаються буквальними частинами імені. Чинні integrity/FK/RPO/cutpoint перевірки збережені. |
| Один HTTP-запит має одну idempotency identity | Два `Idempotency-Key` приймалися за першим значенням; повтор за другим створював іншу заявку | Дублікати будь-якого регістру відхиляються 400 до читання body, квот і запису; з'єднання закривається. Звичайні одиночний ключ, replay і запит без ключа збережені. |
| Помилка підготовки ключа повертає керування користувачу | Rejection до `try/finally` лишав кнопку на «Надсилаю…» без резервного способу передачі | Підготовка ключа перенесена під чинний error boundary. Без готового ключа немає HTTP-запиту; помилка показує існуючий fallback, відновлює кнопку й очищує таймер. |
| Receipt не приписує змінений checkout чистому HEAD | Staged/unstaged/untracked source приймався; `assume-unchanged` / `skip-worktree` приховували зміни від status | Capture й verify відхиляють брудне дерево та index flags, що приховують зміни. Ігноровані generated artifacts дозволені; вхідний SHA та locks перевіряються як раніше. |
| Workflow policy охоплює реальний YAML і повний вміст | `.yaml`, flow mappings і quoted keys могли оминати regex; digest описував тільки action pins і не перевірявся у receipt | Структурний node traversal `yaml.compose(..., Loader=SafeLoader)` читає обидва суфікси, не конструює Python-об'єкти й обходить aliases без повторного розгортання. Duplicate keys і non-string uses відхиляються. Digest зв'язує імена та повні bytes workflow-файлів і перевіряється. |
| SBOM не губить distribution hashes або непізнані рядки | Regex з `\s*` споживав newline/indent і забирав лише перший hash; решта мовчки випадала | Явні межі рядків зберігають усі hashes. Непорожній непізнаний залишок, крім коментарів, відхиляється. Підтримано наявні continuation slashes і EOF без newline. |

## Залежність YAML parser

`PyYAML==6.0.3` уже зафіксований у `requirements-sast.txt`. Його повний блок
із 73 SHA-256 distribution digests без зміни версії чи hashes додано до
`requirements.txt`, щоб quality/mutation jobs також мали parser.
Незалежна перевірка підтвердила байтову тотожність двох блоків.

На поточних lock-файлах SBOM зберігає **329 із 329** hashes звичайного набору
та **85 із 85** security-набору. Це повнота інвентаризації, не новий висновок
про відсутність CVE й не результат свіжого завантаження distributions.

## Верифікація від 21.11.2026

- **279 passed, 40.36 s; 0 failures / errors / skipped** у спільному локальному
  прогоні API, leads, HTTP framing, quotas/deadlines, Telegram, identity/parity,
  submit/media recovery, bundle contracts, backup/restore, supply chain,
  scoped static policy, dependency floors і mutation-anchor applicability.
- До виправлень нові негативні сценарії відтворили невірне приймання запитів,
  зависання форми, помилкові provenance PASS і втрату hashes. Backup/restore
  дефекти додатково відтворені окремими ізольованими subprocess probes.
- 33 backup/restore тести, включно з усіма чинними restore cutpoints, входять
  у спільний прогін. Відмова не змінює вихідні файли або права каталогу.
- Структурний parser читає всі 6 поточних workflow-файлів і 4 унікальні
  SHA-pinned actions; жоден workflow або поріг приймання не послаблено.
- 69 mutation anchors застосовуються рівно один раз. Це не повний запуск
  мутантів і не виміряний mutation score.
- JavaScript syntax, Python AST, DOM sink inventory (28) і diff check пройшли.
- Незалежний reviewer повторив власні контрприклади для index flags і YAML
  flow mapping, окремо звірив усі raw/parsed hashes та dependency blocks.

SHA-256 спільного локального JUnit:
`b06fd28774e8619139a078ca2d7869c44cfbc9ff641be93c1c116aa0b86ca974`.

Середовище: Python 3.12.14, pytest 9.0.3, PyYAML 6.0.3; використано раніше
встановлені залежності. Свіжа hash-locked installation не підтверджена.
Коротка перевірка pip у `--dry-run --no-index` зупинилася на відсутньому
greenlet у локальному індексі; нічого не встановлювала й не є PASS.

## Межа приймання

Публічний вигляд, палітра, тарифи, CRM payload, `X-PBT-Signature`, формат
`PBT-` reference й алгоритм створення ключа не змінювалися. Production hold
лишається в `docs/PRODUCTION_HOLD.md`.

На батьківському head усі 10 jobs п'яти workflows завершувалися до старту
runner (`runner_id=0`, `steps=[]`), включно з незалежним main control.
Тому локальні результати не є зеленим CI, browser/visual evidence, runtime
soak або повним `make gate`. Актуальні runs остаточного head фіксуються в PR.

Provenance тут лишається unsigned, без заявленого SLSA level. Перевірки
доводять зазначені інваріанти в наведених сценаріях; універсальна відсутність
дефектів або відповідність невизначеному корпоративному «рівню» не заявляється.
