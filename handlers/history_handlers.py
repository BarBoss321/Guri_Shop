import asyncio
import html

from aiogram import Router, F
from aiogram.types import CallbackQuery
from services.db import get_last_grouped_orders

router = Router()

# заметный разделитель между заказами
ORDER_SPLIT = "\n<b>───────────────────</b>\n\n"   # 24 символа

def format_order_block(order_no: int, created_at: str, items_join: str, company: str | None = None) -> str:
    """
    items_join: 'Название : Кол-во || Название : Кол-во ...'
    created_at: 'YYYY-MM-DD HH:MM:SS' — берём только дату.
    company: юрлицо заявки (у заявок до ноября 2026 не записано).
    """
    order_date = created_at.split(" ")[0] if created_at else "—"

    lines = []
    if items_join:
        for raw in items_join.split("||"):
            raw = raw.strip()
            if not raw:
                continue
            if ":" in raw:
                # rsplit: двоеточие может быть и в самом названии
                name, qty = raw.rsplit(":", 1)
                name = name.strip()
                qty = qty.strip()
            else:
                name, qty = raw.strip(), "1"
            # экранируем: «Moët & Chandon» иначе ломает HTML и всю историю
            lines.append(f"• {html.escape(name)} × {qty}")

    body = "\n".join(lines) if lines else "• —"

    # Заголовок — в одну строку: номер + дата, ниже — юрлицо
    header = f"📦 <b>Заказ №{order_no}</b> · 🗓 {order_date}"
    if company:
        header += f"\n🏢 {html.escape(company)}"

    return f"{header}\n{body}"

@router.callback_query(F.data == "history_orders")
async def show_history(c: CallbackQuery):
    uid = c.from_user.id
    # синхронный sqlite — в отдельном потоке, чтобы не блокировать остальных пользователей
    rows = await asyncio.to_thread(get_last_grouped_orders, uid, 3)

    if not rows:
        await c.message.edit_text(
            "Пока нет заявок.",
            parse_mode="HTML",
            reply_markup=history_back_kb()
        )
        await c.answer()
        return

    blocks = [format_order_block(no, dt, join, company) for (no, dt, join, company) in rows]
    text = "🧾 <b>Ваши последние заявки:</b>\n\n" + ORDER_SPLIT.join(blocks)

    await c.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=history_back_kb()
    )
    await c.answer()

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def history_back_kb() -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)