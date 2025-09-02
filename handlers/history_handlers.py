from aiogram import Router, F
from aiogram.types import CallbackQuery
from services.db import get_last_grouped_orders

router = Router()

# заметный разделитель между заказами
ORDER_SPLIT = "\n<b>───────────────────</b>\n\n"   # 24 символа

def format_order_block(order_no: int, created_at: str, items_join: str) -> str:
    """
    items_join: 'Название : Кол-во || Название : Кол-во ...'
    created_at: 'YYYY-MM-DD HH:MM:SS' — берём только дату.
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
                name = name.strip()
                qty = qty.strip()
            else:
                name, qty = raw.strip(), "1"
            lines.append(f"• {name} × {qty}")

    body = "\n".join(lines) if lines else "• —"

    # Заголовок — в одну строку: номер + дата
    header = f"📦 <b>Заказ №{order_no}</b> · 🗓 {order_date}"

    return f"{header}\n{body}"

@router.callback_query(F.data == "history_orders")
async def show_history(c: CallbackQuery):
    uid = c.from_user.id
    rows = get_last_grouped_orders(uid, limit=3)  # (order_no, created_at, items_join)

    if not rows:
        await c.message.edit_text("Пока нет заявок.", parse_mode="HTML")
        await c.answer()
        return

    blocks = [format_order_block(no, dt, join) for (no, dt, join) in rows]
    text = "🧾 <b>Ваши последние заявки:</b>\n\n" + ORDER_SPLIT.join(blocks)

    await c.message.edit_text(text, parse_mode="HTML")
    await c.answer()

