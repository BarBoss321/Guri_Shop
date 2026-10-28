from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from states.cart_states import CartStates
from services.db import get_db
from collections import defaultdict
import asyncio
from config import ADMIN_ID
from handlers.cart_view import back_to_menu_kb
# 👉 вынеси в config.py и импортируй оттуда

router = Router()

@router.callback_query(F.data.startswith("item_"))
async def handle_item_click(callback: CallbackQuery, state: FSMContext):
    data = callback.data.replace("item_", "")
    parts = data.split(":")
    item_id = int(parts[0])
    category_id = int(parts[1])
    parent_id = int(parts[2]) if len(parts) > 2 else 0
    grand_parent_id = int(parts[3]) if len(parts) > 3 else 0

    db = await get_db()
    cursor = await db.execute("SELECT name FROM items WHERE id = ?", (item_id,))
    row = await cursor.fetchone()
    await db.close()

    if not row:
        await callback.answer("❌ Товар не найден.")
        return

    item_name = row[0]

    await state.update_data(
        item_id=item_id,
        item_name=item_name,
        category_id=category_id,
        parent_id=parent_id,
        grand_parent_id=grand_parent_id,
        message_id=callback.message.message_id
    )
    await state.set_state(CartStates.awaiting_quantity)

    await callback.message.edit_text(
        f"✏️ Введите количество для товара: <b>{item_name}</b>",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(CartStates.awaiting_quantity)
async def process_quantity(message: Message, state: FSMContext):
    # стикер/фото вместо числа: text = None
    if not message.text or not message.text.isdigit() or int(message.text) <= 0:
        await message.delete()
        return

    data = await state.get_data()
    if "item_id" not in data:
        # состояние потеряно (например, после перезапуска Redis)
        await state.clear()
        await message.answer("⚠️ Выберите товар заново: /s")
        return
    item_id = data["item_id"]
    item_name = data["item_name"]
    category_id = data["category_id"]
    parent_id = data["parent_id"]
    grand_parent_id = data["grand_parent_id"]
    msg_id = data["message_id"]

    quantity = int(message.text)
    user_id = message.from_user.id

    # Добавляем в корзину
    db = await get_db()
    await db.execute("""
        INSERT INTO cart (user_id, item_id, quantity)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id, item_id) DO UPDATE SET quantity = quantity + excluded.quantity
    """, (user_id, item_id, quantity))
    await db.commit()

    # Получаем подкатегории и товары
    subcats = await db.execute("SELECT id, name FROM categories WHERE parent_id = ?", (category_id,))
    subcats = await subcats.fetchall()

    items = await db.execute("SELECT id, name FROM items WHERE category_id = ?", (category_id,))
    items = await items.fetchall()
    await db.close()

    # Генерация кнопок
    buttons = []

    # Сначала подкатегории
    for cid, name in subcats:
        buttons.append([
            InlineKeyboardButton(
                text=name,
                callback_data=f"cat_{cid}:{category_id}:{parent_id}"
            )
        ])

    # Потом товары
    for iid, name in items:
        buttons.append([
            InlineKeyboardButton(
                text=name,
                callback_data=f"item_{iid}:{category_id}:{parent_id}:{grand_parent_id}"
            )
        ])

    # Кнопка Назад (если не корень)
    if parent_id or grand_parent_id:
        buttons.append([
            InlineKeyboardButton(
                text="🔙 Назад",
                callback_data=f"cat_{parent_id}:{grand_parent_id}:0"
            )
        ])

    # Кнопки Корзина и Популярное на одной линии
    buttons.append([
        InlineKeyboardButton(text="🛒 Корзина", callback_data="view_cart"),
        InlineKeyboardButton(text="🗂️ История заказов", callback_data="history_orders")
    ])

    # Обновляем предыдущее сообщение
    await message.bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=msg_id,
        text="📦 Выберите товар или категорию:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )

    # Уведомление о добавлении
    notify_msg = await message.bot.send_message(
        chat_id=message.chat.id,
        text=f"✅ <b>{item_name}</b> — {quantity} шт. добавлено в корзину.",
        parse_mode="HTML"
    )

    await message.delete()

    await asyncio.sleep(2)
    try:
        await notify_msg.delete()
    except:
        pass

    await state.clear()

# ✅ выбор компании (перенос в orders). Без фильтра по state: если состояние потерялось,
# заявка всё равно должна попасть в историю, а не уйти в дубль-обработчик без сохранения
@router.callback_query(F.data.startswith("company_"))
async def handle_company_selection(callback: CallbackQuery, state: FSMContext):
    company_name = callback.data.replace("company_", "")
    user_id = callback.from_user.id

    db = await get_db()

    # содержимое корзины
    cur = await db.execute("""
        SELECT i.id, i.name, c.quantity, i.supplier
        FROM cart c
        JOIN items i ON c.item_id = i.id
        WHERE c.user_id = ?
    """, (user_id,))
    rows = await cur.fetchall()

    if not rows:
        await db.close()
        await state.clear()
        await callback.message.edit_text("🛒 Корзина пуста.", reply_markup=back_to_menu_kb())
        await callback.answer()
        return

    # группировка для админа
    grouped = defaultdict(list)
    for item_id, item_name, qty, supplier in rows:
        grouped[(supplier or "❓ Без поставщика")].append(f"{item_name} — {qty} шт.")

    text = (
        f"🧑‍💼Новая заявка от <b><code>{user_id}</code></b>\n"
        f"📦<b>ООО {company_name}</b>\n\n"
    )
    for supplier, goods in grouped.items():
        text += f"<b>{supplier}</b>:\n" + "\n".join(f"▪️ {g}" for g in goods) + "\n\n"

    # отправляем админу ОДИН раз
    await callback.bot.send_message(chat_id=ADMIN_ID, text=text, parse_mode="HTML")

    # 👉 перенос позиций в историю заказов (orders)
    await db.execute("""
        INSERT INTO orders(user_id, item_id, quantity)
        SELECT c.user_id, c.item_id, c.quantity
        FROM cart c
        WHERE c.user_id = ?
    """, (user_id,))
    await db.commit()

    # (опционально) самопроверка: сколько записей у пользователя за сегодня
    cur = await db.execute(
        "SELECT COUNT(*) FROM orders WHERE user_id = ? AND DATE(order_date)=DATE('now')",
        (user_id,)
    )
    print("orders inserted today for", user_id, "=", (await cur.fetchone())[0])

    # чистим корзину
    await db.execute("DELETE FROM cart WHERE user_id = ?", (user_id,))
    await db.commit()
    await db.close()

    await callback.message.edit_text("✅ Заявка отправлена администратору. Корзина очищена.", reply_markup=back_to_menu_kb())
    await state.clear()
    await callback.answer()


# ❌ УДАЛИ/ЗАКОММЕНТЬ ЭТОТ ХЕНДЛЕР (он ломал всё, JOIN suppliers не нужен)
# @router.callback_query(F.data.startswith("choose_company_"))
# async def handle_company_choice(...):
#     ...



@router.callback_query(F.data == "submit_cart")
async def submit_cart(callback: CallbackQuery, state: FSMContext):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="ООО «АНИКО»", callback_data="company_АНИКО")],
        [InlineKeyboardButton(text="ООО «СФЕРА»", callback_data="company_СФЕРА")],
        [InlineKeyboardButton(text="ООО «КЕЛЬТ»", callback_data="company_КЕЛЬТ")],
        [InlineKeyboardButton(text="ООО «ПРИВИЛЕГИЯ»", callback_data="company_ПРИВИЛЕГИЯ")],
        [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_menu")],
    ])

    # 👇 именно это состояние
    await state.set_state(CartStates.choosing_company)

    await callback.message.edit_text(
        "🏢 Выберите компанию, от имени которой оформляется заявка:",
        reply_markup=keyboard
    )
    await callback.answer()