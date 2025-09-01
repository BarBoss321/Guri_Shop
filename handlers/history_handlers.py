from aiogram import Router, F
from aiogram.types import CallbackQuery
from services.db import get_last_grouped_orders

router = Router()

@router.callback_query(F.data == "history_orders")
async def show_history(c: CallbackQuery):
    uid = c.from_user.id
    rows = get_last_grouped_orders(uid, limit=3)

    if not rows:
        await c.message.edit_text("📜 История пуста.")
        await c.answer()
        return

    parts = ["🧾 <b>Ваши последние заявки:</b>"]
    for r in rows:
        when = r["created_at"] or ""
        parts.append(f"\n📦 <b>#{r['order_no']}</b> от {when}")

        # items_join = "Товар1:2||Товар2:5||..."
        for raw in (r["items_join"] or "").split("||"):
            if not raw:
                continue
            name, qty = raw.split(":", 1)
            parts.append(f"• {name} × {qty}")

    await c.message.edit_text("\n".join(parts), parse_mode="HTML")
    await c.answer()