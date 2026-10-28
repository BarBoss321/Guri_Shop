import html
import json
import os
from pathlib import Path
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware, Bot
from aiogram.types import Message, CallbackQuery, TelegramObject
from config import ALLOWED_USERS_FILE, ADMIN_ID

BASE_DIR = Path(__file__).resolve().parent.parent
# не в git: список меняется командами /add и /rem прямо на сервере,
# и git pull не должен с ним конфликтовать
ACCESS_FILE = BASE_DIR / "data" / "access.json"

# ids     — у кого есть доступ
# pending — логины, добавленные через /add до того, как человек написал боту
# known   — логин → id всех, кто писал боту (по-другому id по @login не узнать)
# names   — id → имя и логин для /list
_access: dict | None = None


def _norm(login: str) -> str:
    return login.strip().lstrip("@").lower()


def load_allowed_users():
    try:
        with open(BASE_DIR / ALLOWED_USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print("Ошибка при загрузке allowed_users.json:", e)
        return []


def _load() -> dict:
    global _access
    if _access is None:
        if ACCESS_FILE.exists():
            _access = json.loads(ACCESS_FILE.read_text(encoding="utf-8"))
            _access.setdefault("names", {})
        else:
            # первый запуск: переносим старый список из allowed_users.json
            _access = {"ids": [int(i) for i in load_allowed_users()], "pending": [], "known": {}, "names": {}}
            _save()
    return _access


def _save():
    ACCESS_FILE.parent.mkdir(exist_ok=True)
    tmp = ACCESS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(_access, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, ACCESS_FILE)


def remember_user(user_id: int, username: str | None, full_name: str | None = None):
    """Запоминает логин и выдаёт доступ, если логин ждал в pending."""
    data = _load()
    changed = False
    profile = {"name": full_name or "", "username": username or ""}
    if data["names"].get(str(user_id)) != profile:
        data["names"][str(user_id)] = profile
        changed = True
    if username:
        login = _norm(username)
        if data["known"].get(login) != user_id:
            data["known"][login] = user_id
            changed = True
        if login in data["pending"]:
            data["pending"].remove(login)
            if user_id not in data["ids"]:
                data["ids"].append(user_id)
            changed = True
    if changed:
        _save()


def is_user_allowed(user_id: int) -> bool:
    return user_id == ADMIN_ID or user_id in _load()["ids"]


def add_user(target: str) -> str:
    data = _load()
    if target.lstrip("-").isdigit():
        user_id = int(target)
        if user_id in data["ids"]:
            return f"ℹ️ ID {user_id} уже есть в списке."
        data["ids"].append(user_id)
        _save()
        return f"✅ ID {user_id} добавлен."

    login = _norm(target)
    user_id = data["known"].get(login)
    if user_id is not None:
        if user_id in data["ids"]:
            return f"ℹ️ @{login} уже есть в списке."
        data["ids"].append(user_id)
        _save()
        return f"✅ @{login} добавлен."

    if login in data["pending"]:
        return f"ℹ️ @{login} уже ждёт: доступ откроется, когда он напишет боту."
    data["pending"].append(login)
    _save()
    return (f"⏳ @{login} ещё не писал боту. Доступ откроется автоматически, "
            f"как только он отправит боту любое сообщение.")


def remove_user(target: str) -> str:
    data = _load()
    if target.lstrip("-").isdigit():
        user_id, name = int(target), f"ID {target}"
    else:
        login = _norm(target)
        user_id, name = data["known"].get(login), f"@{login}"
        if login in data["pending"]:
            data["pending"].remove(login)
            _save()
            return f"🗑 {name} удалён из ожидания."

    if user_id == ADMIN_ID:
        return "⚠️ Администратора удалить нельзя."
    if user_id is None or user_id not in data["ids"]:
        return f"ℹ️ {name} нет в списке."
    data["ids"].remove(user_id)
    _save()
    return f"🗑 {name} удалён, доступа больше нет."


def _format_user(uid: int, profile: dict | None) -> str:
    profile = profile or {}
    parts = [html.escape(profile.get("name") or "Без имени")]
    if profile.get("username"):
        parts.append(f"@{html.escape(profile['username'])}")
    return f"• {' · '.join(parts)} — <code>{uid}</code>"


async def list_users(bot: Bot) -> str:
    data = _load()
    for uid in data["ids"]:
        if str(uid) in data["names"]:
            continue
        # человек давно не писал боту — спрашиваем имя у Telegram один раз и запоминаем
        try:
            chat = await bot.get_chat(uid)
            remember_user(uid, chat.username, chat.full_name)
        except Exception:
            # Telegram не отдал данные (человек не запускал бота) — не спрашиваем снова
            remember_user(uid, None, None)
    lines = [_format_user(uid, data["names"].get(str(uid))) for uid in data["ids"]]
    lines += [f"• @{login} (ждёт первого сообщения)" for login in data["pending"]]
    return "👥 <b>Доступ к боту:</b>\n" + ("\n".join(lines) if lines else "пусто")


class AccessMiddleware(BaseMiddleware):
    """Пропускает к хендлерам только тех, кто в списке доступа."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = getattr(event, "from_user", None)
        if user is None:
            return await handler(event, data)

        remember_user(user.id, user.username, user.full_name)
        if is_user_allowed(user.id):
            return await handler(event, data)

        who = f"@{user.username}" if user.username else f"ID {user.id}"
        text = f"⛔️ Доступ запрещён.\nПопросите администратора добавить вас: {who}"
        if isinstance(event, CallbackQuery):
            await event.answer(text, show_alert=True)
        elif isinstance(event, Message):
            await event.answer(text, parse_mode=None)
