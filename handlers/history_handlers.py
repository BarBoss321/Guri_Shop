from aiogram import Router, F
from aiogram.types import CallbackQuery
from services.db import get_last_orders

router = Router()

@router.callback_query(F.data == "history_orders")
async def show_history(c: CallbackQuery):
    user_id = c.from_user.id
    rows = get_last_orders(user_id, limit=3)   # СИНХРОННАЯ функция — БЕЗ await

    if not rows:
        await c.message.answer("📭 История пуста: ещё не было заявок.")
        await c.answer()
        return

    lines = ["🧾 <b>Ваши последние заявки</b>:\n"]
    for r in rows:
        order_id  = r["order_id"]
        created   = r["created_at"] or ""
        item_name = r["item_name"]
        qty       = r["qty"]
        lines.append(f"📦 <code>#{order_id}</code> от {created}\n • {item_name} × {qty}")

    await c.message.answer("\n\n".join(lines), parse_mode="HTML")
    await c.answer()