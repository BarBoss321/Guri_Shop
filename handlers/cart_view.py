from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from services.db import get_db
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from states.cart_states import CartStates
from aiogram.exceptions import TelegramBadRequest
from collections import defaultdict
from aiogram import Bot
from filters import access

router = Router()

@router.message(F.text.lower() == "корзина")
async def view_cart(message: Message):
    db = await get_db()
    cursor = await db.execute(
        """
        SELECT items.name, cart.quantity, items.price
        FROM cart
        JOIN items ON cart.item_id = items.id
        WHERE cart.user_id = ?
        """, (message.from_user.id,)
    )
    items = await cursor.fetchall()
    await cursor.close()
    await db.close()

    if not items:
        await message.answer("🛒 Ваша корзина пуста.")
        return

    text = "<b>🛒 Ваша корзина:</b>\n\n"
    total = 0
    for name, qty, price in items:
        subtotal = qty * price
        total += subtotal
        parse_mode="HTML"
        text += f"🔹 {name} — {qty} шт. × {price} = <b>{subtotal}</b>\n"

    text += f"\n<b>Итого: {total}</b>"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Оформить заказ", callback_data="submit_order")],
        [InlineKeyboardButton(text="🗑 Очистить корзину", callback_data="clear_cart")]
    ])

    await message.answer(text, reply_markup=keyboard)

@router.callback_query(F.data == "clear_cart")
async def clear_cart(callback: Message):
    db = await get_db()
    await db.execute("DELETE FROM cart WHERE user_id = ?", (callback.from_user.id,))
    await db.commit()
    await db.close()
    await callback.message.edit_text("🗑 Корзина очищена.")
    await callback.answer()

@router.callback_query(F.data == "submit_order")
async def submit_order(callback: Message):
    db = await get_db()
    cursor = await db.execute(
        """
        SELECT items.name, cart.quantity
        FROM cart
        JOIN items ON cart.item_id = items.id
        WHERE cart.user_id = ?
        """, (callback.from_user.id,)
    )
    items = await cursor.fetchall()
    await cursor.close()
    await db.execute("DELETE FROM cart WHERE user_id = ?", (callback.from_user.id,))
    await db.commit()
    await db.close()

    if not items:
        await callback.message.edit_text("🛒 Корзина пуста.")
        await callback.answer()
        return

    text = f"<b>📦 Новый заказ от @{callback.from_user.username or callback.from_user.id}:</b>"
    parse_mode = "HTML"
    for name, qty in items:
        text += f"🔹 {name} — {qty} шт."

    # Отправка админу (здесь ID админа можно будет подгрузить из настроек)
    admin_id = 1297005050
    await callback.bot.send_message(chat_id=admin_id, text=text)

    await callback.message.edit_text("✅ Заказ отправлен!")
    await callback.answer()

@router.callback_query(F.data == "view_cart")
async def view_cart(callback: CallbackQuery, state: FSMContext):
    db = await get_db()
    cursor = await db.execute("""
        SELECT items.id, items.name, cart.quantity
        FROM cart
        JOIN items ON cart.item_id = items.id
        WHERE cart.user_id = ?
    """, (callback.from_user.id,))
    items = await cursor.fetchall()
    await db.close()

    if not items:
        await callback.message.edit_text("🛒 Ваша корзина пуста.")
        await callback.answer()
        return

    # Собираем текст корзины
    text = "<b>🛒 Ваша корзина:</b>\n\n"
    parse_mode = "HTML"
    for _, name, qty in items:
        text += f"🔹 {name} — {qty} шт.\n"

    keyboard_buttons = [
        [InlineKeyboardButton(text="✏️ Изменить количество", callback_data="edit_mode")],
        [InlineKeyboardButton(text="❌ Удалить позицию", callback_data="remove_mode")],
        [InlineKeyboardButton(text="✅ Подтвердить заказ", callback_data="submit_cart")],
        [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_menu")]
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.message(CartStates.editing_quantity)
async def update_quantity(message: Message, state: FSMContext):
    try:
        await message.delete()
    except:
        pass  # если сообщение уже удалено — не падаем

    if not message.text.isdigit() or int(message.text) <= 0:
        await message.answer("❌ Введите положительное число.")
        return

    data = await state.get_data()
    item_id = data.get("edit_item_id")
    msg_id = data.get("message_id")
    quantity = int(message.text)
    user_id = message.from_user.id

    print(f"🟡 USER: {user_id}, ITEM: {item_id}, QTY: {quantity}, MSG_ID: {msg_id}")

    db = await get_db()
    print("🟢 DB connected")

    await db.execute(
        "UPDATE cart SET quantity = ? WHERE user_id = ? AND item_id = ?",
        (quantity, user_id, item_id)
    )

    cursor = await db.execute("""
        SELECT items.id, items.name, cart.quantity
        FROM cart
        JOIN items ON cart.item_id = items.id
        WHERE cart.user_id = ?
    """, (user_id,))
    items = await cursor.fetchall()
    await db.commit()
    await db.close()

    if not items:
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=msg_id,
                text="🛒 Корзина пуста.",
                parse_mode="HTML"
            )

            msg = await message.bot.send_message(
                chat_id=message.chat.id,
                text=f"✅ Позиция <b>{item_name}</b> удалена, корзина пуста.",
                parse_mode="HTML"
            )
            await asyncio.sleep(2)
            await msg.delete()

        except TelegramBadRequest as e:
            if "message is not modified" in str(e):
                pass
            else:
                raise

        await state.clear()
        return


    # Формируем корзину
    cart_text = "<b>🛒 Ваша корзина:</b>\n\n"
    for iid, name, qty in items:
        cart_text += f"🔹 {name} — {qty} шт.\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Изменить количество", callback_data="edit_mode")],
        [InlineKeyboardButton(text="❌ Удалить позицию", callback_data="remove_mode")],
        [InlineKeyboardButton(text="✅ Подтвердить заказ", callback_data="submit_cart")],
        [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_menu")]
    ])

    try:
        await message.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=msg_id,
            text=cart_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )
        print("✅ Сообщение обновлено")
    except Exception as e:
        print("❌ Ошибка при обновлении сообщения:", e)

    # Уведомление
    try:
        db = await get_db()
        cursor = await db.execute("SELECT name FROM items WHERE id = ?", (item_id,))
        row = await cursor.fetchone()
        await db.close()
        item_name = row[0] if row else "товар"
    except Exception as e:
        print("❌ Ошибка при получении названия:", e)
        item_name = "товар"

    cart_text = "<b>🛒 Ваша корзина:</b>\n\n"
    for iid, name, qty in items:
        cart_text += f"🔹 {name} — {qty} шт.\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Изменить количество", callback_data="edit_mode")],
        [InlineKeyboardButton(text="❌ Удалить позицию", callback_data="remove_mode")],
        [InlineKeyboardButton(text="✅ Подтвердить заказ", callback_data="submit_cart")],
        [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_menu")]
    ])

    try:
        await message.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=msg_id,
            text=cart_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            pass  # Ничего не делаем, если сообщение не изменилось
        else:
            raise

    await state.clear()

@router.callback_query(F.data.startswith("edititem_"))
async def ask_new_quantity(callback: CallbackQuery, state: FSMContext):
    item_id = int(callback.data.replace("edititem_", ""))

    db = await get_db()
    cursor = await db.execute("SELECT name FROM items WHERE id = ?", (item_id,))
    row = await cursor.fetchone()
    await db.close()

    if not row:
        await callback.answer("❌ Товар не найден.")
        return

    name = row[0]

    # Сохраняем состояние и данные
    await state.update_data(edit_item_id=item_id, message_id=callback.message.message_id)
    await state.set_state(CartStates.editing_quantity)

    # ❗️ ОБНОВЛЯЕМ СУЩЕСТВУЮЩЕЕ СООБЩЕНИЕ
    # Получаем текущее количество
    db = await get_db()
    cursor = await db.execute(
        "SELECT items.name, cart.quantity FROM cart JOIN items ON cart.item_id = items.id WHERE cart.item_id = ? AND cart.user_id = ?",
        (item_id, callback.from_user.id)
    )
    row = await cursor.fetchone()
    await db.close()

    if not row:
        await callback.answer("❌ Товар не найден.")
        return

    name, qty = row

    # Сохраняем состояние
    await state.update_data(edit_item_id=item_id, message_id=callback.message.message_id)
    await state.set_state(CartStates.editing_quantity)

    # Показываем с текущим количеством
    await callback.message.edit_text(
        text=f"✏️ <b>{name}</b>\nТекущее количество: <b>{qty}</b>\n\nВведите новое:",
        parse_mode="HTML"
    )

    await callback.answer()

    await callback.answer()

@router.callback_query(F.data == "edit_mode")
async def choose_item_to_edit(callback: CallbackQuery, state: FSMContext):
    db = await get_db()
    cursor = await db.execute("""
        SELECT items.id, items.name
        FROM cart
        JOIN items ON cart.item_id = items.id
        WHERE cart.user_id = ?
    """, (callback.from_user.id,))
    items = await cursor.fetchall()
    await db.close()

    if not items:
        await callback.answer("❌ Корзина пуста.")
        return

    # Генерируем кнопки по каждому товару
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=name, callback_data=f"edititem_{iid}")]
        for iid, name in items
    ])

    await callback.message.edit_text("Выберите товар, который хотите изменить:", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("edititem_"))
async def ask_new_qty(callback: CallbackQuery, state: FSMContext):
    item_id = int(callback.data.replace("edititem_", ""))
    await state.update_data(edit_item_id=item_id, message_id=callback.message.message_id)
    await state.set_state(CartStates.editing_quantity)

    await callback.message.answer("✏️ Введите новое количество:")
    await callback.answer()


@router.callback_query(F.data.startswith("removeitem_"))
async def remove_selected_item(callback: CallbackQuery):
    item_id = int(callback.data.replace("removeitem_", ""))
    user_id = callback.from_user.id

    db = await get_db()
    # Удаляем выбранный товар из корзины
    await db.execute("DELETE FROM cart WHERE user_id = ? AND item_id = ?", (user_id, item_id))
    await db.commit()

    # Получаем обновлённую корзину
    cursor = await db.execute("""
        SELECT items.id, items.name, cart.quantity
        FROM cart
        JOIN items ON cart.item_id = items.id
        WHERE cart.user_id = ?
    """, (user_id,))
    items = await cursor.fetchall()
    await db.close()

    if not items:
        await callback.message.edit_text("🛒 Корзина пуста.")
        await callback.answer("✅ Товар удалён.")
        return

    # Формируем обновлённый текст корзины
    text = "<b>🛒 Ваша корзина:</b>\n\n"
    for iid, name, qty in items:
        text += f"🔹 {name} — {qty} шт.\n"

    # Кнопки управления корзиной
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Изменить количество", callback_data="edit_mode")],
        [InlineKeyboardButton(text="❌ Удалить позицию", callback_data="remove_mode")],
        [InlineKeyboardButton(text="✅ Подтвердить заказ", callback_data="submit_cart")],
        [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_menu")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer("✅ Товар удалён.")

@router.callback_query(F.data == "remove_mode")
async def choose_item_to_remove(callback: CallbackQuery):
    db = await get_db()
    cursor = await db.execute("""
        SELECT items.id, items.name
        FROM cart
        JOIN items ON cart.item_id = items.id
        WHERE cart.user_id = ?
    """, (callback.from_user.id,))
    items = await cursor.fetchall()
    await db.close()

    if not items:
        await callback.answer("❌ Корзина пуста.")
        return

    # Генерируем кнопки для каждого товара
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=name, callback_data=f"removeitem_{iid}")]
        for iid, name in items
    ])

    await callback.message.edit_text("Выберите товар, который хотите удалить:", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()  # очищаем состояние, если есть

    db = await get_db()

    # ищем корень (parent_id = 0 или имя 'catalog')
    cur = await db.execute("""
        SELECT id FROM categories
        WHERE parent_id = 0
        ORDER BY id LIMIT 1
    """)
    root = await cur.fetchone()
    if not root:
        cur = await db.execute("""
            SELECT id FROM categories
            WHERE LOWER(name) = 'catalog'
            ORDER BY id LIMIT 1
        """)
        root = await cur.fetchone()

    if not root:
        await db.close()
        await callback.message.edit_text("Категории не найдены.")
        await callback.answer()
        return

    root_id = root[0]

    # дети корня
    cur = await db.execute("""
        SELECT id, name FROM categories
        WHERE parent_id = ?
        ORDER BY id
    """, (root_id,))
    categories = await cur.fetchall()
    await db.close()

    if not categories:
        await callback.message.edit_text("Каталог пуст.")
        await callback.answer()
        return

    # клавиатура: список детей + универсальные кнопки
    rows = [
        [InlineKeyboardButton(text=name, callback_data=f"cat_{cid}:{root_id}:0")]
        for cid, name in categories
    ]
    # универсальные
    rows.append([
        InlineKeyboardButton(text="🛒 Корзина", callback_data="view_cart"),
        InlineKeyboardButton(text="🔥 Популярное", callback_data="history_orders"),
        InlineKeyboardButton(text="🗂️ История заказов", callback_data="history_orders")
    ])
    # На корне кнопки «Назад» нет — это и нужно

    keyboard = InlineKeyboardMarkup(inline_keyboard=rows)

    await callback.message.edit_text(
        "📦 Выберите категорию:",
        reply_markup=keyboard
    )
    await callback.answer()

ADMIN_ID = 1297005050

async def send_order_to_admin(bot: Bot, user_id: int, company_name: str):
    db = await get_db()

    # Получаем товары пользователя
    cursor = await db.execute("""
        SELECT c.quantity, i.name, i.supplier
        FROM cart c
        JOIN items i ON c.item_id = i.id
        WHERE c.user_id = ?
    """, (user_id,))
    rows = await cursor.fetchall()

    if not rows:
        await db.close()
        return

    # Группируем по поставщикам
    grouped = defaultdict(list)
    for quantity, item_name, supplier in rows:
        supplier = supplier or "❓ Без поставщика"
        grouped[supplier].append(f"{item_name} — {quantity} шт.")

    # Подготовка текста
    message = f"🧑‍💼 Новая заявка от <b><code>{user_id}</code></b>\n"
    message += f"🏢 <b>{'ООО ' if not company_name.startswith('ООО') else ''}{company_name}</b>\n\n"

    for supplier, items_list in grouped.items():
        message += f"<b>{supplier}</b>:\n"
        message += "\n".join(f"▪️ {item}" for item in items_list)
        message += "\n\n"

    # Отправка администратору
    await bot.send_message(
        chat_id=ADMIN_ID,  # не забудь импортировать или указать ID
        text=message,
        parse_mode="HTML"
    )

    # Очистка корзины
    await db.execute("DELETE FROM cart WHERE user_id = ?", (user_id,))
    await db.commit()
    await db.close()

@router.callback_query(lambda c: c.data.startswith("company_"))
async def handle_company_choice(callback: CallbackQuery, state: FSMContext, bot):
    company_name = callback.data.split("company_")[1]
    user_id = callback.from_user.id

    await send_order_to_admin(bot, user_id=user_id, company_name=company_name)

    await callback.message.edit_text("✅ Заявка отправлена администратору.")
    await state.clear()
    await callback.answer()