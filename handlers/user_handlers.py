import asyncio
import logging

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.exceptions import TelegramNetworkError
from aiogram.fsm.context import FSMContext

from services.db import get_db

router = Router()
logger = logging.getLogger(__name__)


async def _build_root_menu():
    db = await get_db()

    cur = await db.execute("SELECT id FROM categories WHERE parent_id = 0 ORDER BY id LIMIT 1")
    row = await cur.fetchone()

    if not row:
        cur = await db.execute("SELECT id FROM categories WHERE LOWER(name)='catalog' ORDER BY id LIMIT 1")
        row = await cur.fetchone()

    if not row:
        await db.close()
        return None

    root_id = row[0]
    cur = await db.execute("SELECT id, name FROM categories WHERE parent_id = ?", (root_id,))
    cats = await cur.fetchall()
    await db.close()

    buttons = [
        [InlineKeyboardButton(text=name, callback_data=f"cat_{cid}:{root_id}:0")]
        for cid, name in cats
    ]

    buttons.append([
        InlineKeyboardButton(text="🗂️  История заказов", callback_data="history_orders"),
        InlineKeyboardButton(text="🛒  Корзина", callback_data="view_cart")
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def safe_answer(message: Message, text: str, reply_markup=None, retries: int = 3):
    for attempt in range(retries):
        try:
            await message.answer(text, reply_markup=reply_markup)
            return True
        except TelegramNetworkError:
            logger.warning("Telegram timeout in message.answer, attempt %s/%s", attempt + 1, retries)
            await asyncio.sleep(2)

    logger.error("Failed to send message after %s attempts", retries)
    return False


async def safe_edit_text(callback: CallbackQuery, text: str, reply_markup=None, retries: int = 3):
    for attempt in range(retries):
        try:
            await callback.message.edit_text(text, reply_markup=reply_markup)
            return True
        except TelegramNetworkError:
            logger.warning("Telegram timeout in edit_text, attempt %s/%s", attempt + 1, retries)
            await asyncio.sleep(2)

    logger.error("Failed to edit message after %s attempts", retries)
    return False


@router.message(F.text == "/s")
async def open_catalog(message: Message):
    kb = await _build_root_menu()
    if not kb:
        await safe_answer(message, "❌ Корневая категория не найдена.")
        return

    ok = await safe_answer(message, "📦 Выберите категорию:", reply_markup=kb)
    if not ok:
        logger.error("open_catalog: failed to send root menu to user %s", message.from_user.id)


@router.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()

    kb = await _build_root_menu()
    if not kb:
        await safe_edit_text(callback, "❌ Корневая категория не найдена.")
        await callback.answer()
        return

    await safe_edit_text(callback, "📦 Выберите категорию:", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "popular")
async def show_popular(callback: CallbackQuery):
    user_id = callback.from_user.id
    await callback.answer()

    try:
        db = await get_db()

        cursor = await db.execute("""
            SELECT i.id, i.name, i.category_id, SUM(o.quantity) AS total_qty
            FROM orders o
            JOIN items i ON i.id = o.item_id
            WHERE o.user_id = ?
            GROUP BY i.id, i.name, i.category_id
            ORDER BY total_qty DESC
            LIMIT 8
        """, (user_id,))
        rows = await cursor.fetchall()
        await db.close()

        if not rows:
            await safe_edit_text(
                callback,
                "🔥  Популярное пусто.\nСделайте несколько заказов — и здесь появятся ваши самые частые позиции."
            )
            return
            
        buttons = [[InlineKeyboardButton(
                text=f"{name} • {total_qty}",
                callback_data=f"item_{item_id}:{cat_id}:0:0"
        )]
            for (item_id, name, cat_id, total_qty) in rows
        ]

        buttons.append([
            InlineKeyboardButton(text="🔙  Назад", callback_data="back_to_menu"),
            InlineKeyboardButton(text="🛒  Корзина", callback_data="view_cart"),
        ])

        await safe_edit_text(
            callback,
            "🔥  Ваше популярное (топ-8):",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
        )

    except Exception as e:
        logger.exception("POPULAR ERROR: %r", e)
        try:
            await safe_edit_text(callback, "❌ Не удалось загрузить популярное. Попробуйте позже.")
        except Exception:
            pass
