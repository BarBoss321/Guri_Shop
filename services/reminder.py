"""Напоминания в рабочий чат про заявки: пн и чт в 6:00 по Москве.

Текст каждый раз собирается заново из случайных кусочков, со смайликами
и регистром вперемешку; последние сообщения запоминаются, чтобы не повторяться.
"""
import asyncio
import hashlib
import json
import logging
import os
import random
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram import Bot

from services.db import BASE_DIR

logger = logging.getLogger(__name__)

TZ = ZoneInfo(os.getenv("REMINDER_TZ", "Europe/Moscow"))
DAYS = {0: "понедельник", 3: "четверг"}   # weekday() → название
HOUR, MINUTE = 6, 0
LATE_LIMIT = timedelta(hours=2)          # бот перезапускался в 6:00 — догоняем, но не к обеду
STATE_FILE = BASE_DIR / "data" / "reminder.json"
REMEMBER_LAST = 50

EMOJI = list("🔥⚡💥🚀🍾🍷🍺🥃🍸🍹🧉☕🍋🍊🍒🎉🎊🥳😎🤩🙌👏💪✨🌟⭐💫🌈📦📝📋✅❗‼🔔📣📢⏰🕕🦾🤘👀💯🫡😤🤓🧾🛒")
DECOR = ["★彡", "✧･ﾟ:*", "~*~", "✦✦✦", "»»——", "☆ﾟ.*･｡ﾟ", "•°•°•", "♪♫♪", "✿❀✿", "▼▲▼", "⚡⚡⚡", "=^_^=", "(ﾉ◕ヮ◕)ﾉ*:･ﾟ✧", "ʕ•ᴥ•ʔ", "(•̀ᴗ•́)و"]

GREETINGS = [
    "Доброе утро, команда", "Подъём, легенды бара", "Утро доброе, коллеги", "Всем бодрого утра",
    "Йо-хо-хо, команда", "Рота, подъём", "Салют, бармены", "Хэй-хэй, вся смена", "Привет, мои звёзды",
    "Внимание, внимание", "Доброе утро, страна", "Ку-ку, кофе уже налит",
]
DAY_LINES = [
    "Сегодня {day} — день заявок", "{Day}! А значит, пора собирать заявки", "Наступил {day}, время заказов",
    "{Day} пришёл — заявки ждут", "Это не просто {day}, это ДЕНЬ ЗАЯВОК", "Календарь шепчет: {day}, заявки",
    "Сегодня {day}, бар сам себя не закупит",
]
# правила из вкладки «Правила» таблицы «Закуп»; из каждой группы — не больше одной фразы
DEADLINE = ["Заявки отправляем до 14:00", "Дедлайн по заявкам — 14:00", "В 14:00 заявки улетают"]
RULE_GROUPS = [
    ["Сначала смотрим остатки на складе, потом заказываем", "Проверьте склад, прежде чем заказывать"],
    ["Сверяйтесь с ограничениями в таблице", "Не больше, чем разрешено в таблице ограничений"],
    ["Не забудьте очистить свою таблицу перед новой заявкой", "Старую заявку из таблицы — стереть"],
    ["Оформить заявку можно прямо в боте: /s"],
]
CLOSINGS = [
    "Всем продуктивного дня", "Погнали", "Кто первый — тот молодец", "Без заявки — без пива",
    "Давайте без опозданий", "Верю в вас", "Вы лучшие", "Хорошей смены", "Работаем красиво",
    "Пусть склад будет полным", "Ждём ваши заявки",
]

KEEP = re.compile(r"^(/s|\d.*)$")   # «/s» и время «14:00» не коверкаем


def _mangle(word: str, rnd: random.Random) -> str:
    if KEEP.match(word) or len(word) < 3:
        return word
    style = rnd.choice(["upper", "lower", "alt", "alt2", "spaced", "keep", "keep", "cap"])
    if style == "upper":
        return word.upper()
    if style == "lower":
        return word.lower()
    if style in ("alt", "alt2"):
        shift = 0 if style == "alt" else 1
        return "".join(c.upper() if (i + shift) % 2 else c.lower() for i, c in enumerate(word))
    if style == "spaced" and len(word) <= 8:
        return " ".join(word.upper())
    if style == "cap":
        return word[:1].upper() + word[1:].lower()
    return word


def _scramble(text: str, rnd: random.Random) -> str:
    out = []
    for word in text.split(" "):
        out.append(_mangle(word, rnd))
        if rnd.random() < 0.25:
            out.append(rnd.choice(EMOJI))
    return " ".join(out)


def _emojis(rnd: random.Random, n: tuple[int, int] = (1, 3)) -> str:
    return "".join(rnd.choices(EMOJI, k=rnd.randint(*n)))


def build_message(weekday: int, rnd: random.Random | None = None) -> str:
    rnd = rnd or random.Random()
    day = DAYS.get(weekday, "сегодня")
    deco = rnd.choice(DECOR)
    lines = [
        f"{deco} {_emojis(rnd)} {_scramble(rnd.choice(GREETINGS), rnd)}! {_emojis(rnd)} {deco[::-1] if rnd.random() < 0.5 else deco}",
        "",
        f"{_emojis(rnd, (1, 2))} {_scramble(rnd.choice(DAY_LINES).format(day=day, Day=day.capitalize()), rnd)} {_emojis(rnd)}",
        "",
    ]
    # правило про 14:00 — всегда, остальные — 2–3 разных по смыслу
    rules = [rnd.choice(DEADLINE)] + [rnd.choice(g) for g in rnd.sample(RULE_GROUPS, rnd.randint(2, 3))]
    rnd.shuffle(rules)
    bullets = rnd.choice([["👉"], ["▶️"], ["✔️"], ["🔸", "🔹"], ["⚡"], ["➤"], ["🍋", "🍊", "🍒"]])
    for i, rule in enumerate(rules):
        lines.append(f"{bullets[i % len(bullets)]} {_scramble(rule, rnd)}")
    lines += ["", f"{_emojis(rnd)} {_scramble(rnd.choice(CLOSINGS), rnd)}! {_emojis(rnd, (2, 4))}"]
    if rnd.random() < 0.6:
        lines.append(rnd.choice(DECOR))
    return "\n".join(lines)


# ---------- состояние: куда слать и что уже отправлено ----------

def load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {}


def save_state(state: dict):
    STATE_FILE.parent.mkdir(exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, STATE_FILE)


def fresh_message(weekday: int, state: dict) -> str:
    """Сообщение, которого не было среди последних REMEMBER_LAST."""
    recent = state.get("recent", [])
    for _ in range(20):
        text = build_message(weekday)
        digest = hashlib.sha1(text.encode()).hexdigest()[:12]
        if digest not in recent:
            state["recent"] = (recent + [digest])[-REMEMBER_LAST:]
            return text
    return text


def next_run(now: datetime) -> datetime:
    for add in range(8):
        day = (now + timedelta(days=add)).replace(hour=HOUR, minute=MINUTE, second=0, microsecond=0)
        if day.weekday() in DAYS and day > now:
            return day
    raise RuntimeError("не нашёл дня для напоминания")


async def send_reminder(bot: Bot, chat_id: int, weekday: int) -> None:
    state = load_state()
    text = fresh_message(weekday, state)
    await bot.send_message(chat_id, text, parse_mode=None)
    save_state(state)


async def reminder_loop(bot: Bot):
    """Фоновая задача: спит до ближайшего пн/чт 6:00 по Москве и пишет в чат."""
    while True:
        try:
            now = datetime.now(TZ)
            state = load_state()
            today = now.date().isoformat()
            due = now.replace(hour=HOUR, minute=MINUTE, second=0, microsecond=0)
            if (now.weekday() in DAYS and due <= now < due + LATE_LIMIT
                    and state.get("chat_id") and state.get("last_sent") != today):
                await send_reminder(bot, state["chat_id"], now.weekday())
                state = load_state()
                state["last_sent"] = today
                save_state(state)
                logger.info("напоминание отправлено в чат %s", state["chat_id"])
            # спим кусками не больше часа: так переживаем перевод часов и сон сервера
            wait = (next_run(datetime.now(TZ)) - datetime.now(TZ)).total_seconds()
            await asyncio.sleep(max(5, min(wait, 3600)))
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("ошибка в напоминаниях, повтор через минуту")
            await asyncio.sleep(60)
