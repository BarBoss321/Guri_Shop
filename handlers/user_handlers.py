from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from services.db import get_db
from aiogram.fsm.context import FSMContext

router = Router()

async def _build_root_menu():
    db = await get_db()
    # корень: parent_id = 0 ИЛИ name='catalog'
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

    buttons.append([InlineKeyboardButton(text="🔍 Поиск товара", callback_data="search_help")])
    # Объединяем в одну строку
    buttons.append([
        InlineKeyboardButton(text="🗂️ История заказов", callback_data="history_orders"),
        InlineKeyboardButton(text="🛒 Корзина", callback_data="view_cart")
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

@router.message(F.text == "/s")
async def open_catalog(message: Message):
    kb = await _build_root_menu()
    if not kb:
        await message.answer("❌ Корневая категория не найдена.")
        return
    await message.answer("📦 Выберите категорию:", reply_markup=kb)

@router.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    kb = await _build_root_menu()
    if not kb:
        await callback.message.edit_text("❌ Корневая категория не найдена.")
        await callback.answer()
        return
    await callback.message.edit_text("📦 Выберите категорию:", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "popular")
async def show_popular(callback: CallbackQuery):
    user_id = callback.from_user.id
    await callback.answer()  # сразу гасим "крутилку"

    try:
        db = await get_db()
        # Берем ТОП-8 по сумме заказанного количества
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
            await callback.message.edit_text(
                "🔥 Популярное пусто.\nСделайте несколько заказов — и здесь появятся ваши самые частые позиции."
            )
            return

        # Кнопки: каждый товар — отдельной строкой
        buttons = [
            [InlineKeyboardButton(
                text=f"{name} • {total_qty}",
                callback_data=f"item_{item_id}:{cat_id}:0:0"   # вернемся в товар напрямую
            )]
            for (item_id, name, cat_id, total_qty) in rows
        ]

        # Низ: назад и корзина в ОДНОЙ строке
        buttons.append([
            InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu"),
            InlineKeyboardButton(text="🛒 Корзина", callback_data="view_cart"),
        ])

        await callback.message.edit_text(
            "🔥 Ваше популярное (топ-8):",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
        )

    except Exception as e:
        # Логи в консоль, чтобы понять, если что-то падает
        print("POPULAR ERROR:", repr(e))
        try:
            await callback.message.edit_text("❌ Не удалось загрузить популярное. Попробуйте позже.")
        except:
            pass