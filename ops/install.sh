#!/usr/bin/env bash
# Встановлює/оновлює user-юніти ПБТ (systemd --user, linger має бути увімкнено). Ідемпотентно.
set -euo pipefail
cd "$(dirname "$0")/.."
dst="$HOME/.config/systemd/user"; mkdir -p "$dst"
for u in ops/systemd/*.service ops/systemd/*.timer; do install -m 0644 "$u" "$dst/$(basename "$u")"; done
systemctl --user daemon-reload
systemctl --user enable --now pbt-site.service pbt-site-health.timer pbt-site-backup.timer
systemctl --user --no-pager status pbt-site.service | head -5
