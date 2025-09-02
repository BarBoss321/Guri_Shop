from aiogram import Router, F
from aiogram.types import CallbackQuery
from services.db import get_last_grouped_orders

router = Router()

@router.callback_query(F.data == "history_orders")
async def show_history(callback: CallbackQuery):
    uid = callback.from_user.id
    rows = get_last_grouped_orders(uid, limit=3)

    if not rows:
        await callback.message.edit_text("📄 История пуста — ещё не было заявок.")
        await callback.answer()
        return

    # rows: [ {order_no, created_at, items_join}, ... ]
    lines = ["🧾 <b>Ваши последние заявки:</b>", ""]
    for r in rows:
        order_no = r["order_no"]
        created = r["created_at"] or ""
        items = r["items_join"] or ""

        lines.append(f"📦 <b>#{order_no}</b> от {created}")
        pretty = "• " + items.replace(" || ", "\n• ")
        lines.append(pretty)
        lines.append("")  # пустая строка-разделитель

    await callback.message.edit_text("\n".join(lines), parse_mode="HTML")
    await callback.answer()