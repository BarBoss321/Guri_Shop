import html
from datetime import datetime

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from config import ADMIN_ID
from services.reminder import TZ, DAYS, load_state, save_state, next_run, fresh_message, send_reminder

router = Router()
router.message.filter(F.from_user.id == ADMIN_ID)

WEEKDAYS = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]


def _when() -> str:
    run = next_run(datetime.now(TZ))
    return f"{WEEKDAYS[run.weekday()]} {run:%d.%m в %H:%M} (МСК)"


@router.message(Command("remind_here"))
async def remind_here(message: Message):
    if message.chat.type == "private":
        await message.answer("Отправьте /remind_here в рабочем чате, куда бот должен писать напоминания.")
        return
    state = load_state()
    state.update(chat_id=message.chat.id, chat_title=message.chat.title)
    save_state(state)
    await message.answer(
        f"✅ Буду напоминать сюда про заявки по понедельникам и четвергам в 6:00 (МСК).\n"
        f"Ближайшее напоминание: {_when()}."
    )


@router.message(Command("remind_off"))
async def remind_off(message: Message):
    state = load_state()
    title = state.pop("chat_title", None)
    state.pop("chat_id", None)
    save_state(state)
    await message.answer(f"🔕 Напоминания выключены{f' (чат «{html.escape(title)}»)' if title else ''}.")


@router.message(Command("remind_test"))
async def remind_test(message: Message):
    weekday = datetime.now(TZ).weekday()
    weekday = weekday if weekday in DAYS else min(DAYS)
    if message.chat.type == "private":
        # предпросмотр только админу — в историю «не повторяться» не записываем
        await message.answer(fresh_message(weekday, {}), parse_mode=None)
        return
    await send_reminder(message.bot, message.chat.id, weekday)


@router.message(Command("remind"))
async def remind_status(message: Message):
    state = load_state()
    if not state.get("chat_id"):
        await message.answer(
            "🔕 Напоминания не настроены.\n\n"
            "Добавьте бота в рабочий чат и напишите там /remind_here.\n"
            "/remind_test — показать пример сообщения"
        )
        return
    await message.answer(
        f"🔔 Напоминания идут в чат «{html.escape(state.get('chat_title') or str(state['chat_id']))}»\n"
        f"Пн и чт в 6:00 (МСК). Ближайшее: {_when()}.\n\n"
        "/remind_test — пример сообщения (в чате — отправит туда)\n"
        "/remind_off — выключить"
    )
