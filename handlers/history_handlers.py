from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.markdown import hbold, hcode
from services.db import fetch_last_orders, fetch_order_items
from services.db import get_last_orders_with_items

router = Router()

@router.callback_query(F.data == "history_orders")
async def show_history(c: CallbackQuery):
    user_id = c.from_user.id

    rows = get_last_orders_with_items(user_id, limit=3)  # синхронная функция -> БЕЗ await
    if not rows:
        await c.message.answer("📭 История пуста: ещё не было заявок.")
        await c.answer()
        return

    # группируем позиции по заказу
    lines = ["🧾 <b>Ваши последние заявки</b>:\n"]
    cur_order_id = None
    bucket = []

    def flush():
        if bucket:
            lines.append("\n".join(bucket))

    for order_id, created_at, item_name, qty in rows:
        if order_id != cur_order_id:
            flush()
            cur_order_id = order_id
            bucket = [f"📦 Заявка <code>#{order_id}</code> от {created_at or ''}"]
        bucket.append(f" • {item_name} × {qty}")

    flush()
    text = "\n\n".join(lines)
    await c.message.answer(text, parse_mode="HTML")
    await c.answer()