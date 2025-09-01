from aiogram import Router, F
from aiogram.types import CallbackQuery
from services.db import get_last_grouped_orders

router = Router()

@router.callback_query(F.data == "history_orders")
async def show_history(c: CallbackQuery):
    uid = c.from_user.id
    rows = get_last_grouped_orders(uid, limit=3)
    if not rows:
        await c.answer("История пуста.", show_alert=True)
        return

    out = ["🧾 <b>Ваши последние заявки:</b>"]
    for order_id, created_at, items_concat in rows:
        out.append(f"\n📦 <b>#{order_id}</b> от {created_at}")
        # items_concat = "Товар1 × 2||Товар2 × 5"
        for line in (items_concat or "").split("||"):
            if line.strip():
                out.append(f"• {line.strip()}")

    await c.message.edit_text("\n".join(out), parse_mode="HTML")