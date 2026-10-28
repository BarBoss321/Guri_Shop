# Запуск бота на VPS (через PuTTY)

Все команды вводятся в окне PuTTY после входа на сервер.
Вставить текст в PuTTY — правой кнопкой мыши.

## 0. Остановить старую версию

```bash
sudo systemctl stop shopbot
sudo systemctl disable shopbot
pkill -f "python bot.py"
```

Важно: бот с одним токеном должен работать **только в одном месте**.
Если он запущен ещё где-то (на компьютере, на Render), Telegram раздаёт
сообщения то одному, то другому — бот «тормозит» и теряет нажатия.

## 1. Поставить Python, Redis и git

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip redis-server git
sudo systemctl enable --now redis-server
redis-cli ping
```

Последняя команда должна ответить `PONG`.

## 2. Скачать бота с GitHub

```bash
sudo mkdir -p /opt/GSB
cd /opt/GSB
sudo git clone https://github.com/BarBoss321/Guri_Shop.git
cd Guri_Shop
```

## 3. Создать файл .env (токен)

```bash
sudo cp .env.example .env
sudo nano .env
```

Вписать **новый** токен от @BotFather и свой ADMIN_ID.
Сохранить: `Ctrl+O`, `Enter`, выйти: `Ctrl+X`.

## 4. Виртуальное окружение и библиотеки

```bash
sudo python3 -m venv .venv
sudo .venv/bin/pip install -r requirements.txt
```

## 5. Проверочный запуск вручную

```bash
sudo .venv/bin/python bot.py
```

Напишите боту `/s` в Telegram. Работает — остановите: `Ctrl+C`.

## 6. Запуск как служба (работает после закрытия PuTTY и перезагрузки)

```bash
sudo cp deploy/shopbot.service /etc/systemd/system/shopbot.service
sudo systemctl daemon-reload
sudo systemctl enable --now shopbot
sudo systemctl status shopbot
```

В статусе должно быть `active (running)`. Выход из просмотра — `q`.

## Доступ к боту

Пользоваться ботом могут только админ и те, кого он добавил командами в Telegram:

- `/add @login` — дать доступ (если человек ещё не писал боту, доступ откроется при первом сообщении)
- `/rem @login` — забрать доступ
- `/list` — список с именами и ID

Список хранится на сервере в `data/access.json` (не в git — `git pull` его не трогает).
При первом запуске в него переносятся ID из `allowed_users.json`.

## Обновление бота

```bash
bash /opt/GSB/Guri_Shop/deploy.sh
```

Скрипт сам: сохраняет копию базы в `backups/` (хранит 10 последних), скачивает обновления
с GitHub, ставит библиотеки, проверяет код и перезапускает бота. База на сервере всегда
остаётся своя — с заказами, даже если на GitHub залита новая. Если в новой версии ошибка,
скрипт откатывается на прежнюю и бота не трогает.

## Полезные команды

```bash
sudo journalctl -u shopbot -f
sudo systemctl restart shopbot
cd /opt/GSB/Guri_Shop && sudo git pull && sudo systemctl restart shopbot
```

Первая — смотреть логи в реальном времени (выход `Ctrl+C`),
вторая — перезапуск, третья — обновить код с GitHub и перезапустить.

## Если Telegram всё равно медленный

Если сервер в России, связь с api.telegram.org может быть замедлена.
Варианты: VPS за границей или http-прокси — строка в `.env`:

```
PROXY_URL=http://user:pass@host:port
```
