import aiosqlite
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

DB_PATH = "shop_bot.db"

async def build_root_keyboard():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # ищем корень (parent_id=0) или по имени 'catalog'
        cur = await db.execute("""
            SELECT id FROM categories
            WHERE parent_id = 0
            ORDER BY id LIMIT 1
        """)
        root = await cur.fetchone()
        if not root:
            cur = await db.execute("""
                SELECT id FROM categories
                WHERE LOWER(name)='catalog'
                ORDER BY id LIMIT 1
            """)
            root = await cur.fetchone()

        if not root:
            return InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Пусто", callback_data="noop")]
            ])

        root_id = root["id"]

        # дети корня
        cur = await db.execute("""
            SELECT id, name FROM categories
            WHERE parent_id = ?
            ORDER BY id
        """, (root_id,))
        cats = await cur.fetchall()

    buttons = [
        [InlineKeyboardButton(text=cat["name"], callback_data=f"cat_{cat['id']}")]
        for cat in cats
    ]
    # универсальные
    buttons.append([
        InlineKeyboardButton(text="🛒 Корзина", callback_data="view_cart"),
        InlineKeyboardButton(text="🔥 Популярное", callback_data="popular"),
        InlineKeyboardButton(text="История", callback_data="history_orders"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)