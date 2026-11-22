# ПЛЕЙНБУД — публічний сайт

Техніка, що працює там, де інші не доїдуть. Оренда спецтехніки з оператором у Полтаві та 9 областях.

Назву, контакти та реквізити ТОВ «ПЛЕЙНБУД» оновлено за карткою компанії, наданою власником 21.11.2026.
Межі перейменування й сумісність з наявною CRM: [`docs/PLAINBUD_REBRAND.md`](docs/PLAINBUD_REBRAND.md).

## Запуск
```bash
./run.sh            # або: make run → http://127.0.0.1:4180/
```
Python 3.10+, без залежностей (stdlib). Фронтенд — статика (`web/`), API заявок — `server/app.py`
(успадковано з проєкту ЛЮБЕ АВТО того ж автора: JSON-only, перевірка Origin, honeypot, rate limit, `Idempotency-Key`,
SQLite-outbox із повторами доставки в Telegram/вебхук, безпекові заголовки, CSP без `unsafe-inline` для скриптів).

## Тести
```bash
python3 -m pip install --require-hashes -r requirements.txt && python3 -m playwright install chromium
make test-api       # API, ідемпотентність, безпека
make test-site      # 3 в'юпорти, відео-герой і сцена, поява секцій, лічильники, маршрути на карті, парк, калькулятор, форма → БД, спільні вектори, WCAG 2.2 AA (axe)
make test           # усе
make gate           # тести + одно-файлова збірка; дерево після гейта чисте
```

## Збірка й огляд
```bash
make media          # відео з references/*.mp4 (кліпи клієнта; детерміновано; джерела — docs/PROVENANCE.md)
make stock          # секція «Масштаб»: ілюстративні кліпи з Wikimedia Commons (ліцензії й sha256 — config/stock.json)
make shots          # знімки екранів → artifacts/shots/
make bundle         # dist/pbt-site.html (один файл, без сервера) + dist/pbt-site.artifact.html (для Artifact)
```

## Дані, які підтверджує власник
`docs/PRODUCTION_HOLD.md` — відкриті рішення перед публікацією: ціни, ПДВ, канал заявок, домен, права на кадри та політика конфіденційності.
`config/business.json` — єдине джерело контактів і JSON-LD; `null` = не вигадувати.

## Структура
```
web/        index.html · 404.html · css/ (fonts, site) · js/ (data, site) · fonts/ · media/ (video, park, mat, logo, map)
server/     app.py — статика, /api/config, /api/health, /api/lead
config/     business.json · env.template
data/       catalog.json (парк і матеріали з публічного прайсу) · leads.db (створюється сервером)
tests/      test_api · test_leads · test_hardening · test_site · contracts/lead_vectors.json · vendor/axe.min.js
tools/      media.py · shots.py · inline.py
ops/        systemd/ (pbt-site, health, backup) · install.sh · health.py · backup.py · restore.py
docs/       DESIGN.md · PROVENANCE.md · RELEASE_STATUS.md
```

## Assurance

What the system guarantees and what it does not: `docs/ASSURANCE.md`. Production state and missing external facts: `docs/PRODUCTION_HOLD.md`.
