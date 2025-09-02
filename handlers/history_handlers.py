from aiogram import Router, F
from aiogram.types import CallbackQuery
from services.db import get_last_grouped_orders

router = Router()

def format_order_block(order_no: int, created_at: str, items_join: str) -> str:
    """
    items_join: строка вида "Название : Кол-во || Название : Кол-во ..."
    created_at: строка даты-времени, берём только дату
    """
    order_date = created_at.split(" ")[0] if created_at else "—"

    lines = []
    if items_join:
        for raw in items_join.split("||"):
            raw = raw.strip()
            if not raw:
                continue
            if ":" in raw:
                name, qty = raw.split(":", 1)
                lines.append(f"• {name.strip()} × {qty.strip()}")
            else:
                lines.append(f"• {raw.strip()} × 1")

    body = "\n".join(lines) if lines else "—"

    return (
        f"📦 Заказ №{order_no}\n"
        f"🗓 {order_date}\n"
        f"━━━━━━━━━━━━━━\n"
        f"{body}"
    )

@router.callback_query(F.data == "history_orders")
async def show_history(callback: CallbackQuery):
    uid = callback.from_user.id
    rows = get_last_grouped_orders(uid, limit=3)

    if not rows:
        await callback.message.edit_text("Пока нет заявок.", parse_mode="HTML")
        await callback.answer()
        return

    parts = ["🧾 <b>Ваши последние заявки:</b>", ""]
    blocks = []

    for order_no, created_at, items_join in rows:
        blocks.append(format_order_block(order_no, created_at, items_join))

    # Соединяем блоки через длинный разделитель
    text = "\n\n───────────────────────\n\n".join(blocks)

    final_text = "\n".join(parts) + text
    await callback.message.edit_text(final_text, parse_mode="HTML")
    await callback.answer()
    for order_no, created_at, items_join in rows:
        parts.append(format_order_block(order_no, created_at, items_join))
        parts.append("")

    text = "\n".join(parts).rstrip()
    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.answer()