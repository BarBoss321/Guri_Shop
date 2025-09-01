cat <<'EOF' > deploy.sh
#!/usr/bin/env bash
set -euo pipefail

# --- настройки ---
APP_DIR="/root/bots/guri_shop2"
VENV_DIR="$APP_DIR/venv"
PYTHON="$VENV_DIR/bin/python"
PIP="$VENV_DIR/bin/pip"
SERVICE="guri_shop2.service"
BRANCH="main"

cd "$APP_DIR"

echo "[0/7] Диагностика до:"
echo "  Папка: $(pwd)"
echo "  Ветка: $(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '-')"
git rev-parse --is-inside-work-tree >/dev/null 2>&1 && git log -1 --oneline || true

echo "[1/7] Git: жёстко подтягиваю origin/$BRANCH…"
if [ -d .git ]; then
  git fetch --all --prune
  git reset --hard "origin/$BRANCH"
  git clean -fd         # удалит неотслеживаемые файлы/папки (__pycache__, лок.хвосты)
else
  echo "⚠️  Здесь нет .git — пропускаю git-шаг."
fi
echo "  Коммит: $(git log -1 --oneline 2>/dev/null || echo 'n/a')"

echo "[2/7] Venv: создаю при необходимости…"
if [ ! -x "$VENV_DIR/bin/python" ]; then
  python3 -m venv "$VENV_DIR"
fi
# shellcheck disable=SC1090
source "$VENV_DIR/bin/activate"

echo "[3/7] Pip: обновляю инструменты…"
$PIP install -U pip wheel setuptools

echo "[4/7] Зависимости проекта…"
# Если есть requirements.txt — ставим, но с приоритетом бинарей
if [ -f requirements.txt ]; then
  # prefer binary чтобы не компилировал исходники
  $PIP install --prefer-binary -r requirements.txt || true
fi

# Критичные пины под стек
$PIP install \
  "aiogram==3.10.0" \
  "redis==5.0.7" \
  "python-dotenv==1.0.1" \
  "magic-filter>=1.0" \
  Babel certifi aiosqlite

# ВАЖНО: aiohttp только колесом под Py3.12 (без сборки)
export PIP_ONLY_BINARY=":all:"
$PIP install --no-cache-dir --only-binary=:all: "aiohttp==3.9.5"

echo "[5/7] Быстрая проверка окружения…"
$PYTHON - <<'PY'
import os, sys
import aiogram, aiohttp
print("python:", sys.version.split()[0])
print("aiogram:", getattr(aiogram, "__version__", "unknown"))
print("aiohttp:", getattr(aiohttp, "__version__", "unknown"))
print("BOT_TOKEN in env (берётся из .env в коде):", "yes" if os.getenv("BOT_TOKEN") else "no")
PY

echo "[6/7] systemd: перезапускаю сервис…"
systemctl daemon-reload
systemctl restart "$SERVICE"

echo "[7/7] Статус и последние логи:"
systemctl --no-pager -l status "$SERVICE" || true
echo "----- journal (Ctrl+C чтобы выйти) -----"
journalctl -u "$SERVICE" -f -n 100
EOF

chmod +x deploy.sh