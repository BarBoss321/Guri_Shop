from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.markdown import hbold, hcode
from services.db import fetch_last_orders, fetch_order_items

router = Router()

@router.callback_query(F.data == "history_orders")
async def show_history(callback: CallbackQuery):
    user_id = callback.from_user.id

    orders = await fetch_last_orders(user_id, limit=3)
    if not orders:
        await callback.message.edit_text("🧾 История пуста: ещё не было заявок.")
        await callback.answer()
        return

    parts = ["🧾 " + hbold("Ваши последние заявки:") + "\n"]
    for o in orders:
        head = f"— Заявка #{hcode(str(o['id']))} от {o['created_at'] or ''}:"
        items = await fetch_order_items(o["id"])
        body = "\n".join([f"   • {row['title']} × {row['qty']}" for row in items]) or "   • (пусто)"
        parts.append(head + "\n" + body + "\n")

    text = "\n".join(parts)
    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.answer()