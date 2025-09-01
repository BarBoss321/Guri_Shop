from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from services.db import get_db

router = Router()

@router.callback_query(F.data.startswith("cat_"))
async def handle_category(callback: CallbackQuery):
    db = await get_db()
    try:
        raw = callback.data.replace("cat_", "")
        parts = raw.split(":")
        cat_id = int(parts[0])
        parent_id = int(parts[1]) if len(parts) > 1 else 0
        grand_id = int(parts[2]) if len(parts) > 2 else 0

        # родитель текущей считаем из БД — он источник правды
        cur = await db.execute("SELECT COALESCE(parent_id, 0) FROM categories WHERE id = ?", (cat_id,))
        row = await cur.fetchone()
        current_parent_id = int(row[0]) if row else 0

        # подкатегории и товары
        cur = await db.execute("SELECT id, name FROM categories WHERE parent_id = ?", (cat_id,))
        subcats = await cur.fetchall()
        cur = await db.execute("SELECT id, name FROM items WHERE category_id = ?", (cat_id,))
        items = await cur.fetchall()

        buttons = []

        # подкатегории: next: (child : current : current_parent)
        for child_id, name in subcats:
            buttons.append([InlineKeyboardButton(
                text=name,
                callback_data=f"cat_{child_id}:{cat_id}:{current_parent_id or 0}"
            )])

        # товары: (item : current : current_parent : grand_id)
        for item_id, name in items:
            buttons.append([InlineKeyboardButton(
                text=name,
                callback_data=f"item_{item_id}:{cat_id}:{current_parent_id or 0}:{grand_id or 0}"
            )])

        # Назад: если у текущей категории есть родитель
        if current_parent_id:
            buttons.append([InlineKeyboardButton(
                text="🔙 Назад",
                callback_data=f"cat_{current_parent_id}:{grand_id or 0}:0"
            )])

        buttons.append([
            InlineKeyboardButton(text="🛒 Корзина", callback_data="view_cart"),
            InlineKeyboardButton(text="🔥 Популярное", callback_data="popular"),
            [InlineKeyboardButton(text="🗂️ История заказов", callback_data="history_orders")],
        ])

        text = "📦 Выберите подкатегорию или товар:" if (subcats or items) else "❌ Здесь пока нет товаров."
        await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    finally:
        await db.close()
        await callback.answer()