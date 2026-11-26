#!/usr/bin/env bash
# Оновлює user-юніти ПБТ (systemd --user, linger має бути увімкнено).
set -euo pipefail
unset CDPATH
cd -P -- "$(dirname -- "$0")/.."
source_dir=$PWD
checkout="$HOME/projects/pbt-site"
if ! target_dir=$(cd -P -- "$checkout" 2>/dev/null && pwd -P) || [[ "$source_dir" != "$target_dir" ]]; then
    printf 'User-юніти ПБТ прив’язані до %s. Запустіть інсталятор із цієї копії.\n' "$checkout" >&2
    exit 1
fi

site=pbt-site.service
services=("$site" pbt-site-health.service pbt-site-backup.service)
timers=(pbt-site-health.timer pbt-site-backup.timer)
dst="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
mkdir -p -- "$dst"
for unit in "${services[@]}" "${timers[@]}"; do
    install -m 0644 -- "ops/systemd/$unit" "$dst/$unit"
done

systemctl --user daemon-reload
for unit in "${services[@]}"; do
    working_dir=$(systemctl --user show --property=WorkingDirectory --value "$unit")
    if [[ "$working_dir" != /* ]] || ! effective_dir=$(cd -P -- "$working_dir" 2>/dev/null && pwd -P) || [[ "$effective_dir" != "$source_dir" ]]; then
        printf 'Робочий каталог юніта %s не відповідає копії %s.\n' "$unit" "$source_dir" >&2
        exit 1
    fi
done

systemctl --user enable "$site"
systemctl --user restart "$site"
systemctl --user is-active --quiet "$site"
systemctl --user enable --now "${timers[@]}"
