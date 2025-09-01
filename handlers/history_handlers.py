from aiogram import Router, F
from aiogram.types import CallbackQuery
from services.db import get_last_orders

router = Router()

@router.callback_query(F.data == "history_orders")
async def show_history(callback: CallbackQuery):
    user_id = callback.from_user.id
    orders = get_last_grouped_orders(user_id, limit=3)

    if not orders:
        await callback.message.edit_text("🧾 История пуста.")
        await callback.answer()
        return

    lines = ["🧾 <b>Ваши последние заявки:</b>\n"]
    for order_id, created_at, items_text in orders:
        lines.append(f"📦 <b>#{order_id}</b> от {created_at}\n• {items_text}\n")

    text = "\n".join(lines).strip()
    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.answer()