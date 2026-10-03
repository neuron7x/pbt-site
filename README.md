# ПБТ · ПолтаваБудТехніка — публічний сайт

Техніка, що працює там, де інші не доїдуть. Оренда спецтехніки з оператором у Полтаві та 9 областях.

## Запуск
```bash
./run.sh            # або: make run → http://127.0.0.1:4180/
```
Python 3.10+, без залежностей (stdlib). Фронтенд — статика (`web/`), API заявок — `server/app.py`
(успадковано з проєкту ЛЮБЕ АВТО того ж автора: JSON-only, перевірка Origin, honeypot, rate limit, `Idempotency-Key`,
SQLite-outbox із повторами доставки в Telegram/вебхук, безпекові заголовки, CSP без `unsafe-inline` для скриптів).

## Тести
```bash
python3 -m pip install pytest playwright pillow && python3 -m playwright install chromium
make test-api       # API, ідемпотентність, безпека
make test-site      # 3 в'юпорти, сцена героя, парк, калькулятор, форма → БД, спільні вектори валідації, WCAG 2.2 AA (axe)
make test           # усе
make gate           # тести + одно-файлова збірка; дерево після гейта чисте
```

## Збірка й огляд
```bash
make hero           # кадри героя з references/hero.mp4 (детерміновано; джерело — docs/PROVENANCE.md)
make shots          # знімки екранів → artifacts/shots/
make bundle         # dist/pbt-site.html (один файл, без сервера) + dist/pbt-site.artifact.html (для Artifact)
```

## Дані, які підтверджує власник
`docs/RELEASE_STATUS.md` — 8 блокерів (ціни, ПДВ, канал заявок, домен, права на кадри, ліцензія фону, політика конфіденційності, email).
`config/business.json` — єдине джерело контактів і JSON-LD; `null` = не вигадувати.

## Структура
```
web/        index.html · 404.html · css/ (fonts, site) · js/ (data, site) · fonts/ · media/ (hero, park, svc, mat, proof, logo, map)
server/     app.py — статика, /api/config, /api/health, /api/lead
config/     business.json · env.template
data/       catalog.json (парк і матеріали з публічного прайсу) · leads.db (створюється сервером)
tests/      test_api · test_leads · test_hardening · test_site · contracts/lead_vectors.json · vendor/axe.min.js
tools/      hero_frames.py · shots.py · inline.py
ops/        systemd/ (pbt-site, health, backup) · install.sh · health.py · backup.py · restore.py
docs/       DESIGN.md · PROVENANCE.md · RELEASE_STATUS.md
```
