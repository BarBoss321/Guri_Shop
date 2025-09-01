from aiogram import Router, F
from aiogram.types import CallbackQuery
from services.db import get_last_grouped_orders

router = Router()

@router.callback_query(F.data == "history_orders")
async def show_history(c: CallbackQuery):
    uid = c.from_user.id
    rows = get_last_grouped_orders(uid, limit=3)

    if not rows:
        await c.message.edit_text("📜 История пуста. Пока нет заявок.")
        await c.answer()
        return

    parts = ["🧾 <b>Ваши последние заявки:</b>"]
    for r in rows:
        when = r["created_at"] or ""
        items = (r["items_join"] or "").split("||")
        parts.append(f"\n📦 <b>#{r['order_no']}</b> от {when}")
        for it in items:
            parts.append(f"• {it}")

    text = "\n".join(parts)
    await c.message.edit_text(text, parse_mode="HTML")
    await c.answer()