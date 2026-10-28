#!/usr/bin/env bash
# Обновление бота с GitHub и перезапуск.
# Запуск на сервере:  bash /opt/GSB/Guri_Shop/deploy.sh
set -euo pipefail

SERVICE=shopbot
DB=shop_bot.db
KEEP_BACKUPS=10

cd "$(dirname "$(readlink -f "$0")")"

if [ "$(id -u)" -ne 0 ]; then
    echo "Запустите от root: sudo bash $0"
    exit 1
fi

old=$(git rev-parse HEAD)

# 1. Бэкап базы: в ней заказы, их терять нельзя
mkdir -p backups
stamp=$(date +%Y%m%d-%H%M%S)
if [ -f "$DB" ]; then
    cp "$DB" "backups/${DB%.db}.$stamp.db"
    ls -1t backups/*.db | tail -n +$((KEEP_BACKUPS + 1)) | xargs -r rm --
    echo "💾 База сохранена: backups/${DB%.db}.$stamp.db"
fi

# 2. Скачиваем обновления. База на сервере всегда остаётся своя:
#    временно убираем её из-под git, а после pull кладём обратно
echo "⬇️  Скачиваю обновления с GitHub..."
git fetch --quiet origin main
if git diff --quiet "$old" origin/main -- "$DB"; then
    db_changed_upstream=0
else
    db_changed_upstream=1
fi
cp "$DB" "/tmp/$DB.$stamp" 2>/dev/null || true
git checkout --quiet -- "$DB" 2>/dev/null || true
if ! git merge --ff-only --quiet origin/main; then
    cp "/tmp/$DB.$stamp" "$DB" 2>/dev/null || true
    echo "❌ Не удалось обновить: на сервере изменены файлы кода (git status покажет какие)."
    exit 1
fi
cp "/tmp/$DB.$stamp" "$DB" 2>/dev/null || true
rm -f "/tmp/$DB.$stamp"
new=$(git rev-parse HEAD)

if [ "$old" = "$new" ]; then
    echo "✅ Обновлений нет, бот уже свежий."
else
    echo "📦 Новое:"
    git log --oneline "$old..$new" | sed 's/^/   /'
fi
if [ "$db_changed_upstream" = 1 ]; then
    echo "⚠️  В GitHub новая версия $DB, но на сервере оставлена своя (иначе пропадут заказы)."
fi

# 3. Библиотеки (быстро, если ничего не поменялось)
.venv/bin/pip install --quiet -r requirements.txt

# 4. Проверка кода до перезапуска: если не собирается — откат на прежнюю версию
if ! .venv/bin/python -m compileall -q -x '/\.venv/' . >/dev/null; then
    echo "❌ В новой версии ошибка в коде — откатываюсь на $old, бот не трогаю."
    git reset --quiet --hard "$old"
    [ -f "backups/${DB%.db}.$stamp.db" ] && cp "backups/${DB%.db}.$stamp.db" "$DB"
    exit 1
fi

# 5. Перезапуск
systemctl restart "$SERVICE"
sleep 3
if systemctl is-active --quiet "$SERVICE"; then
    echo "🚀 Бот перезапущен и работает."
else
    echo "❌ Бот не запустился. Последние строки лога:"
    journalctl -u "$SERVICE" -n 20 --no-pager
    exit 1
fi
