from aiogram import Router, F
from aiogram.types import CallbackQuery
from services.db import get_last_grouped_orders

router = Router()

def format_order_block(order_no: int, created_at: str, items_join: str) -> str:
    """
    items_join приходит строкой вида 'Название : Кол-во || Название : Кол-во ...'
    """
    lines = []
    if items_join:
        for raw in items_join.split("||"):
            raw = raw.strip()
            if not raw:
                continue
            if ":" in raw:
                name, qty = raw.split(":", 1)
                name = name.strip()
                qty = qty.strip()
            else:
                name, qty = raw, "1"
            lines.append(f"• {name} × {qty}")

    body = "\n".join(lines) if lines else "—"
    sep = "─" * 17

    return (
        f"📦 Заказ №{order_no}\n"
        f"🕒 {created_at}\n"
        f"{sep}\n"
        f"{body}"
    )

@router.callback_query(F.data == "history_orders")
async def show_history(callback: CallbackQuery):
    uid = callback.from_user.id
    rows = get_last_grouped_orders(uid, limit=3)  # [(order_no, created_at, items_join), ...]

    if not rows:
        await callback.message.edit_text("Пока нет заявок.", parse_mode="HTML")
        await callback.answer()
        return

    parts = ["🧾 <b>Ваши последние заявки:</b>"]
    for order_no, created_at, items_join in rows:
        parts.append(format_order_block(order_no, created_at, items_join))
        parts.append("")

    text = "\n".join(parts).rstrip()
    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.answer()