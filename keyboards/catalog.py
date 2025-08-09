from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import aiosqlite
from services.db import get_db

async def get_main_menu_keyboard():
    db = await get_db()
    cursor = await db.execute("SELECT id, name FROM categories WHERE parent_id IS NULL")
    rows = await cursor.fetchall()
    await cursor.close()
    await db.close()

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=row[1], callback_data=f"cat_{row[0]}")] for row in rows
    ])
    return keyboard