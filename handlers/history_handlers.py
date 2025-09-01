from aiogram import Router, F
from aiogram.types import CallbackQuery
from services.db import get_db
from datetime import datetime

router = Router()

def format_date(dt_str: str) -> str:
    """Формат даты: ДД.ММ.ГГГГ ЧЧ:ММ"""
    try:
        dt = datetime.fromisoformat(dt_str)
        return dt.strftime("%d.%m.%Y %H:%M")
    except Exception:
        return dt_str

@router.callback_query(F.data == "history_orders")
async def show_history(c: CallbackQuery):
    user_id = c.from_user.id
    db = await get_db()

    # берём 3 последних заказа
    cur = await db.execute(
        "SELECT id, created_at FROM orders WHERE user_id = ? ORDER BY id DESC LIMIT 3",
        (user_id,)
    )
    orders = await cur.fetchall()

    if not orders:
        await db.close()
        await c.message.edit_text("🧾 У вас пока нет заказов.")
        return await c.answer()

    text = ["🧾 <b>Ваши последние 3 заказа:</b>\n"]

    for o in orders:
        order_id = o["id"]
        created_at = format_date(o["created_at"])
        text.append(f"<b>Заявка #{order_id}</b> от {created_at}")

        # товары по заявке
        cur_items = await db.execute(
            "SELECT title, qty FROM order_items WHERE order_id = ?",
            (order_id,)
        )
        items = await cur_items.fetchall()

        if not items:
            text.append("   (товары не найдены)")
        else:
            for it in items:
                text.append(f"   • {it['title']} × {it['qty']}")

        text.append("")

    await db.close()
    await c.message.edit_text("\n".join(text), parse_mode="HTML")
    await c.answer()