# Експлуатація

`make ops-install` запускають із копії `~/projects/pbt-site` за окремим дозволом власника. User-юніти використовують цей робочий каталог. Інсталятор перевіряє робочі каталоги системи перед перезапуском, перезапускає `pbt-site.service` на 127.0.0.1:4180 і вмикає таймери після підтвердження активного сервісу. Сторож здоров’я запускається щохвилини, резервне копіювання бази двічі на добу.

Сторож здоров'я не запускається, доки існує
`~/.local/state/pbt-power-guard/stopped.json`: це durable marker навмисної
батарейної зупинки PBT CRM. Після відновлення живлення power guard видаляє
marker, і наступний tick таймера автоматично повертає звичайний health-check.

Публічний доступ — за реверс-проксі з TLS (Caddy/nginx) або Tailscale Funnel; юніт виставляє `TRUST_PROXY=1`
(довіряти `X-Forwarded-*` лише від loopback). Канали доставки заявок — `config/env.template`.

Ліміт ідентичностей для захисту форми має два обмежені рівні: `RATE_IP_CAP`
(типово 8192) і `RATE_OVERFLOW_CAP` (типово 32768). Історія квот зберігається
до завершення її вікна, зокрема добового; коли обидва рівні заповнені,
запити нових ідентичностей отримують HTTP 429 до звільнення місця. Збільшення
цих значень підвищує верхню межу пам’яті процесу. Підбирати значення слід
за доступною пам’яттю і виміряним навантаженням; це не захист від усіх DoS.

A second server on the same `LEAD_DB` refuses to start (`single_process_guard`), and restore holds the same kernel lock; a second concurrent backup exits 2. Measured sandbox limits, readiness, drills and rollback: `docs/ASSURANCE.md`.
