from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from services.db import (
    toggle_item_received, order_with_items, all_items_received, close_followup,
    get_due_followups, mark_followup_sent
)

router = Router()

# ---------- утилиты оформления ----------
def followup_text(order, items):
    lines = [f"📦 Контроль поставки по заявке #{order['id']} от {order['created_at']}:"]
    for it in items:
        mark = "✅" if it["received"] else "⏳"
        lines.append(f"{mark} {it['title']} × {it['qty']}")
    lines.append("\nНажимайте по позициям, чтобы отметить получение.")
    return "\n".join(lines)

def followup_kb(items, order_id: int):
    kb = InlineKeyboardBuilder()
    for it in items:
        text = ("✅ " if it["received"] else "⏳ ") + it["title"]
        kb.button(text=text, callback_data=f"fu:toggle:{order_id}:{it['id']}")
    kb.button(text="Все получено", callback_data=f"fu:done:{order_id}")
    kb.adjust(1)
    return kb.as_markup()

# ---------- коллбэки от пользователя ----------
@router.callback_query(F.data.startswith("fu:toggle:"))
async def fu_toggle(c: CallbackQuery):
    _, _, order_id, item_id = c.data.split(":")
    toggle_item_received(int(item_id))
    order, items = order_with_items(int(order_id))
    await c.message.edit_text(
        followup_text(order, items),
        reply_markup=followup_kb(items, int(order_id)),
    )
    await c.answer("Обновлено")

@router.callback_query(F.data.startswith("fu:done:"))
async def fu_done(c: CallbackQuery):
    order_id = int(c.data.split(":")[2])
    if all_items_received(order_id):
        close_followup(order_id)
        await c.message.edit_text("🎉 Отлично! Все позиции получены. Контроль закрыт.")
    else:
        await c.answer("Есть позиции в статусе «⏳». Отметьте все полученные.", show_alert=True)

# ---------- отправка фоллоуапа и воркер ----------
async def send_followup(bot: Bot, fu_row):
    # fu_row — sqlite3.Row (dict-like)
    order_id = fu_row["order_id"]
    chat_id = fu_row["chat_id"]
    order, items = order_with_items(order_id)
    if not order or not items:
        close_followup(order_id)
        return
    msg = await bot.send_message(chat_id, followup_text(order, items), reply_markup=followup_kb(items, order_id))
    mark_followup_sent(fu_row["id"], chat_id, msg.message_id)

async def followup_worker(bot: Bot):
    import asyncio, logging
    logging.info("followup_worker started")
    while True:
        try:
            due = get_due_followups()
            if due:
                logging.info("followup_worker: %d task(s) due", len(due))
            for fu in due:
                await send_followup(bot, fu)
        except Exception as e:
            logging.exception("followup_worker error: %s", e)
        await asyncio.sleep(10)  # можно временно 10 для теста