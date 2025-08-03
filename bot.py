import os
import json
import logging
import json
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from functools import wraps
from aiogram.types import Message, CallbackQuery

from aiogram import types
import json

with open("allowed_users.json", "r", encoding="utf-8") as f:
    ALLOWED_USERS = json.load(f)

print("Загруженные пользователи:", ALLOWED_USERS)  # отладка

def user_allowed(handler):
    @wraps(handler)
    async def wrapper(event, *args, **kwargs):
        user_id = event.from_user.id
        print(f"[Проверка доступа] user_id: {user_id}")

        try:
            with open("allowed_users.json", "r", encoding="utf-8") as f:
                allowed_users = json.load(f)
        except Exception as e:
            print("Ошибка при чтении allowed_users.json:", e)
            allowed_users = []

        if user_id in allowed_users:
            return await handler(event, *args, **kwargs)
        else:
            if isinstance(event, Message):
                await event.answer("❌ У вас нет доступа к этому боту.")
            elif isinstance(event, CallbackQuery):
                await event.answer("🚫 Доступ запрещён.", show_alert=True)

    return wrapper


# === CONFIG ===
API_TOKEN = '7624412290:AAGokkVMcvIWXl-jizLsG9vgoP2RYLvinZI'
ADMIN_ID = 1297005050
ALLOWED_USERS_PATH = "allowed_users.json"
USER_IDS_PATH = "users_ids.json"
LEGAL_ENTITIES = ["ООО АНИКО", "ООО СФЕРА", "ООО КЕЛЬТ", "ООО ПРИВИЛЕГИЯ"]
USER_IDS_PATH = "user_ids.json"
CATALOG_PATH = 'catalog'

# === INIT ===
logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())


# === FSM: ADMIN ===
class AdminState(StatesGroup):
    adding_category = State()
    adding_subcategory = State()
    adding_product_name = State()
    adding_supplier = State()

    deleting_select_category = State()
    deleting_select_subcategory = State()
    deleting_select_product = State()

    adding_user = State()
    deleting_user = State()

    broadcasting = State()


# === HELPER FUNCTIONS ===
def user_allowed(handler):
    @wraps(handler)
    async def wrapper(event, *args, **kwargs):
        user_id = event.from_user.id
        if user_id in ALLOWED_USERS:
            return await handler(event, *args, **kwargs)
        else:
            if isinstance(event, Message):
                await event.answer("⛔️ У вас нет доступа к этому боту.")
            elif isinstance(event, CallbackQuery):
                await event.answer("⛔️ Доступ запрещён.", show_alert=True)
    return wrapper

def load_allowed_users():
    if os.path.exists(ALLOWED_USERS_PATH):
        with open(ALLOWED_USERS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_allowed_users(users):
    with open(ALLOWED_USERS_PATH, "w", encoding="utf-8") as f:
        json.dump(users, f)


def load_user_ids():
    if os.path.exists(USER_IDS_PATH):
        with open(USER_IDS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_user_ids(user_ids):
    with open(USER_IDS_PATH, "w", encoding="utf-8") as f:
        json.dump(user_ids, f)


# === /a ADMIN PANEL ===
@dp.message_handler(commands=['a'], state='*')
@user_allowed
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("У вас нет доступа.")

    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("➕ Добавить товар", callback_data="admin_add_product"),
        InlineKeyboardButton("➖ Удалить товар", callback_data="admin_del_product"),
        InlineKeyboardButton("👤 Добавить юзера", callback_data="admin_add_user"),
        InlineKeyboardButton("🚫 Удалить юзера", callback_data="admin_del_user"),
        InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast")
    )
    await message.answer("📋 Панель администратора:", reply_markup=kb)

# === ➕ Добавление товара: start ===
@dp.callback_query_handler(lambda c: c.data == "admin_add_product", state='*')
@user_allowed
async def admin_add_product_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите категорию для нового товара:")
    await AdminState.adding_category.set()

@dp.message_handler(state=AdminState.adding_category)
@user_allowed
async def admin_add_category(message: types.Message, state: FSMContext):
    await state.update_data(new_category=message.text.strip())
    await message.answer("Введите подкатегорию:")
    await AdminState.adding_subcategory.set()

@dp.message_handler(state=AdminState.adding_subcategory)
@user_allowed
async def admin_add_subcategory(message: types.Message, state: FSMContext):
    await state.update_data(new_subcategory=message.text.strip())
    await message.answer("Введите название товара:")
    await AdminState.adding_product_name.set()

@dp.message_handler(state=AdminState.adding_product_name)
@user_allowed
async def admin_add_product_name(message: types.Message, state: FSMContext):
    await state.update_data(new_product=message.text.strip())
    await message.answer("Введите поставщика товара:")
    await AdminState.adding_supplier.set()

@dp.message_handler(state=AdminState.adding_supplier)
@user_allowed
async def admin_add_supplier(message: types.Message, state: FSMContext):
    data = await state.get_data()
    category = data["new_category"]
    subcategory = data["new_subcategory"]
    product = data["new_product"]
    supplier = message.text.strip()

    product_data = {
        "name": product,
        "supplier": supplier,
        "description": "",
        "price": 0
    }

    # Создание директорий и файла
    dir_path = os.path.join(CATALOG_PATH, category, subcategory)
    os.makedirs(dir_path, exist_ok=True)
    file_path = os.path.join(dir_path, f"{product}.json")

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(product_data, f, ensure_ascii=False, indent=2)

    await message.answer(f"✅ Товар '{product}' успешно добавлен в каталог.")
    await state.finish()

# === ➖ Удалить товар: Старт ===
@dp.callback_query_handler(lambda c: c.data == "admin_del_product", state='*')
@user_allowed
async def admin_del_start(callback: types.CallbackQuery, state: FSMContext):
    if not os.path.exists(CATALOG_PATH):
        await callback.message.answer("Каталог пуст.")
        return

    keyboard = InlineKeyboardMarkup(row_width=1)
    for cat in os.listdir(CATALOG_PATH):
        keyboard.add(InlineKeyboardButton(cat, callback_data=f"delcat:{cat}"))
    await callback.message.answer("Выберите категорию:", reply_markup=keyboard)
    await AdminState.deleting_select_category.set()

@dp.callback_query_handler(lambda c: c.data.startswith("delcat:"), state=AdminState.deleting_select_category)
async def admin_del_subcat(callback: types.CallbackQuery, state: FSMContext):
    category = callback.data.split(":", 1)[1]
    path = os.path.join(CATALOG_PATH, category)
    subcats = os.listdir(path)

    await state.update_data(del_category=category)

    keyboard = InlineKeyboardMarkup(row_width=1)
    for sub in subcats:
        keyboard.add(InlineKeyboardButton(sub, callback_data=f"delsub:{sub}"))
    await callback.message.answer("Выберите подкатегорию:", reply_markup=keyboard)
    await AdminState.deleting_select_subcategory.set()

@dp.callback_query_handler(lambda c: c.data.startswith("delsub:"), state=AdminState.deleting_select_subcategory)
async def admin_del_product(callback: types.CallbackQuery, state: FSMContext):
    subcategory = callback.data.split(":", 1)[1]
    data = await state.get_data()
    category = data['del_category']
    product_path = os.path.join(CATALOG_PATH, category, subcategory)

    await state.update_data(del_subcategory=subcategory)

    files = [f for f in os.listdir(product_path) if f.endswith(".json")]
    if not files:
        await callback.message.answer("В этой подкатегории нет товаров.")
        return

    keyboard = InlineKeyboardMarkup(row_width=1)
    for f in files:
        product = f.replace(".json", "")
        keyboard.add(InlineKeyboardButton(f"🗑 {product}", callback_data=f"delfile:{product}"))
    await callback.message.answer("Выберите товар для удаления:", reply_markup=keyboard)
    await AdminState.deleting_select_product.set()

@dp.callback_query_handler(lambda c: c.data.startswith("delfile:"), state=AdminState.deleting_select_product)
async def admin_delete_product(callback: types.CallbackQuery, state: FSMContext):
    product_name = callback.data.split(":", 1)[1]
    data = await state.get_data()
    category = data['del_category']
    subcategory = data['del_subcategory']
    filepath = os.path.join(CATALOG_PATH, category, subcategory, f"{product_name}.json")

    if os.path.exists(filepath):
        os.remove(filepath)
        await callback.message.answer(f"✅ Товар '{product_name}' удалён.")
    else:
        await callback.message.answer("Файл не найден.")

    await state.finish()

# === 👤 Добавить юзера ===
@dp.callback_query_handler(lambda c: c.data == "admin_add_user", state='*')
@user_allowed
async def admin_add_user_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите Telegram ID пользователя, которого хотите добавить:")
    await AdminState.adding_user.set()

@dp.message_handler(lambda m: m.text.isdigit(), state=AdminState.adding_user)
async def admin_add_user_finish(message: types.Message, state: FSMContext):
    user_id = int(message.text.strip())
    users = load_allowed_users()
    if user_id not in users:
        users.append(user_id)
        save_allowed_users(users)
        await message.answer(f"✅ Пользователь {user_id} добавлен.")
    else:
        await message.answer("Пользователь уже добавлен.")
    await state.finish()

@dp.message_handler(state=AdminState.adding_user)
@user_allowed
async def invalid_user_id_add(message: types.Message, state: FSMContext):
    await message.answer("Введите корректный числовой ID.")

# === 🚫 Удалить юзера ===
@dp.callback_query_handler(lambda c: c.data == "admin_del_user", state='*')
@user_allowed
async def admin_del_user_start(callback: types.CallbackQuery, state: FSMContext):
    users = load_allowed_users()
    if not users:
        await callback.message.answer("Список пользователей пуст.")
        return

    keyboard = InlineKeyboardMarkup(row_width=1)
    for uid in users:
        keyboard.add(InlineKeyboardButton(f"Удалить {uid}", callback_data=f"rmuid:{uid}"))
    await callback.message.answer("Выберите ID для удаления:", reply_markup=keyboard)
    await AdminState.deleting_user.set()

@dp.callback_query_handler(lambda c: c.data.startswith("rmuid:"), state=AdminState.deleting_user)
async def admin_del_user_finish(callback: types.CallbackQuery, state: FSMContext):
    uid = int(callback.data.split(":")[1])
    users = load_allowed_users()
    if uid in users:
        users.remove(uid)
        save_allowed_users(users)
        await callback.message.answer(f"✅ Пользователь {uid} удалён.")
    else:
        await callback.message.answer("Пользователь не найден.")
    await state.finish()

# === 📢 Рассылка ===
@dp.callback_query_handler(lambda c: c.data == "admin_broadcast", state='*')
@user_allowed
async def admin_broadcast_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите сообщение для рассылки всем пользователям:")
    await AdminState.broadcasting.set()

@dp.message_handler(state=AdminState.broadcasting)
@user_allowed
async def admin_broadcast_send(message: types.Message, state: FSMContext):
    text = message.text.strip()
    user_ids = load_user_ids()
    if not user_ids:
        await message.answer("⚠️ Нет пользователей для рассылки.")
        await state.finish()
        return

    success, failed = 0, 0
    for uid in user_ids:
        try:
            await bot.send_message(uid, text)
            success += 1
        except:
            failed += 1

    await message.answer(f"✅ Рассылка завершена.\nУспешно: {success}\nНе доставлено: {failed}")
    await state.finish()

# === STATES ===
class OrderState(StatesGroup):
    choosing_category = State()
    choosing_subcategory = State()
    choosing_product = State()
    entering_quantity = State()
    editing_cart = State()
    updating_quantity = State()
    choosing_legal = State()
    confirming = State()

# === LOAD CATALOG ===
def load_catalog():
    catalog = {}
    for cat in os.listdir(CATALOG_PATH):
        cat_path = os.path.join(CATALOG_PATH, cat)
        if os.path.isdir(cat_path):
            catalog[cat] = {}
            for subcat in os.listdir(cat_path):
                sub_path = os.path.join(cat_path, subcat)
                if os.path.isdir(sub_path):
                    products = [f[:-5] for f in os.listdir(sub_path) if f.endswith('.json')]
                    catalog[cat][subcat] = products
    return catalog

catalog_data = load_catalog()

# === /s Command ===
@dp.message_handler(commands=['s'])
@user_allowed
async def start_order(message: types.Message, state: FSMContext):
    if message.from_user.id not in ALLOWED_USERS:
        await message.answer("У вас нет доступа к боту.")
        return

    await state.finish()
    await state.update_data(cart=[])  # пустая корзина
    await send_categories(message)

async def send_categories(message_or_cb, edit=False):
    keyboard = InlineKeyboardMarkup(row_width=2)
    for cat in catalog_data:
        keyboard.add(InlineKeyboardButton(cat, callback_data=f"cat:{cat}"))
    keyboard.add(InlineKeyboardButton("♻️ Моя корзина", callback_data="view_cart"))
    if isinstance(message_or_cb, types.CallbackQuery):
        if edit:
            await message_or_cb.message.edit_text("Выберите категорию:", reply_markup=keyboard)
        else:
            await message_or_cb.message.answer("Выберите категорию:", reply_markup=keyboard)
    else:
        await message_or_cb.answer("Выберите категорию:", reply_markup=keyboard)
    await OrderState.choosing_category.set()

# === Category Selection ===
@dp.callback_query_handler(lambda c: c.data.startswith("cat:"), state=OrderState.choosing_category)
@user_allowed
async def choose_category(callback: types.CallbackQuery, state: FSMContext):
    cat = callback.data.split(":", 1)[1]
    await state.update_data(current_category=cat)
    keyboard = InlineKeyboardMarkup(row_width=2)
    for subcat in catalog_data[cat]:
        keyboard.add(InlineKeyboardButton(subcat, callback_data=f"sub:{subcat}"))
    keyboard.add(
        InlineKeyboardButton("🔙 Назад", callback_data="back_to_categories"),
        InlineKeyboardButton("♻️ Моя корзина", callback_data="view_cart")
    )
    await callback.message.edit_text(f"Категория: {cat}\nВыберите подкатегорию:", reply_markup=keyboard)
    await OrderState.choosing_subcategory.set()

@dp.callback_query_handler(lambda c: c.data == "back_to_categories", state=OrderState.choosing_subcategory)
@user_allowed
async def back_to_categories(callback: types.CallbackQuery, state: FSMContext):
    await send_categories(callback, edit=True)

# === Subcategory Selection ===
@dp.callback_query_handler(lambda c: c.data.startswith("sub:"), state=OrderState.choosing_subcategory)
@user_allowed
async def choose_subcategory(callback: types.CallbackQuery, state: FSMContext):
    subcat = callback.data.split(":", 1)[1]
    data = await state.get_data()
    cat = data.get("current_category")
    await state.update_data(current_subcategory=subcat)

    keyboard = InlineKeyboardMarkup(row_width=2)
    for product in catalog_data[cat][subcat]:
        keyboard.add(InlineKeyboardButton(product, callback_data=f"prod:{product}"))
    keyboard.add(
        InlineKeyboardButton("🔙 Назад", callback_data="back_to_subcats"),
        InlineKeyboardButton("♻️ Моя корзина", callback_data="view_cart"),
        InlineKeyboardButton("✅ Завершить заявку", callback_data="complete_order")
    )
    await callback.message.edit_text(f"Подкатегория: {subcat}\nВыберите товар:", reply_markup=keyboard)
    await OrderState.choosing_product.set()

@dp.callback_query_handler(lambda c: c.data == "back_to_subcats", state=OrderState.choosing_product)
@user_allowed
async def back_to_subcats(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    cat = data.get("current_category")
    keyboard = InlineKeyboardMarkup(row_width=2)
    for subcat in catalog_data[cat]:
        keyboard.add(InlineKeyboardButton(subcat, callback_data=f"sub:{subcat}"))
    keyboard.add(
        InlineKeyboardButton("🔙 Назад", callback_data="back_to_categories"),
        InlineKeyboardButton("♻️ Моя корзина", callback_data="view_cart")
    )
    await callback.message.edit_text(f"Категория: {cat}\nВыберите подкатегорию:", reply_markup=keyboard)
    await OrderState.choosing_subcategory.set()

# === Product Selection ===
@dp.callback_query_handler(lambda c: c.data.startswith("prod:"), state=OrderState.choosing_product)
@user_allowed
async def choose_product(callback: types.CallbackQuery, state: FSMContext):
    product = callback.data.split(":", 1)[1]
    data = await state.get_data()
    category = data.get("current_category")
    subcategory = data.get("current_subcategory")

    import_path = os.path.join(CATALOG_PATH, category, subcategory, f"{product}.json")

    try:
        with open(import_path, "r", encoding="utf-8") as f:
            product_data = json.load(f)
            supplier = product_data.get("supplier", "Неизвестный поставщик")
    except Exception as e:
        supplier = "Неизвестный поставщик"

    await state.update_data(selected_product=product, selected_supplier=supplier)
    await callback.message.answer(f"Введите количество для товара: {product}")
    await OrderState.entering_quantity.set()

# === Quantity Input ===
@dp.message_handler(lambda m: m.text.isdigit(), state=OrderState.entering_quantity)
@user_allowed
async def enter_quantity(message: types.Message, state: FSMContext):
    qty = int(message.text)
    data = await state.get_data()
    product = data.get("selected_product")
    supplier = data.get("selected_supplier")
    cart = data.get("cart", [])
    # Проверяем: уже есть такой товар от этого же поставщика?
    for item in cart:
        if item["product"] == product and item["supplier"] == supplier:
            item["quantity"] += qty
            break
    else:
        cart.append({"product": product, "quantity": qty, "supplier": supplier})
    await state.update_data(cart=cart)

    # ✅ Уведомление
    await message.answer(f"✅ {product} — {qty} шт. добавлен в корзину")

    # Вернуться в выбор товаров
    cat = data.get("current_category")
    sub = data.get("current_subcategory")
    keyboard = InlineKeyboardMarkup(row_width=2)
    for prod in catalog_data[cat][sub]:
        keyboard.add(InlineKeyboardButton(prod, callback_data=f"prod:{prod}"))
    keyboard.add(
        InlineKeyboardButton("🔙 Назад", callback_data="back_to_subcats"),
        InlineKeyboardButton("♻️ Моя корзина", callback_data="view_cart"),
        InlineKeyboardButton("✅ Завершить заявку", callback_data="complete_order")
    )
    await message.answer("Выберите следующий товар или завершите заявку:", reply_markup=keyboard)
    await OrderState.choosing_product.set()

@dp.message_handler(state=OrderState.entering_quantity)
@user_allowed
async def invalid_quantity(message: types.Message, state: FSMContext):
    await message.answer("Пожалуйста, введите целое число.")

# === View Cart ===
@dp.callback_query_handler(lambda c: c.data == "view_cart", state='*')
@user_allowed
async def view_cart(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    cart = data.get("cart", [])
    if not cart:
        await callback.message.answer("🛒 Ваша корзина пуста.")
        return

    text = "🛒 *Ваша корзина:*\n\n"
    for idx, item in enumerate(cart, start=1):
        text += f"{idx}. {item['product']} — {item['quantity']} шт.\n"

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("✏️ Редактировать", callback_data="edit_cart"))
    keyboard.add(InlineKeyboardButton("✅ Завершить заявку", callback_data="complete_order"))
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="back_to_catalog"))

    await callback.message.answer(text, parse_mode="Markdown", reply_markup=keyboard)

# === Back from cart to catalog ===
@dp.callback_query_handler(lambda c: c.data == "back_to_catalog", state='*')
@user_allowed
async def back_to_catalog(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    cat = data.get("current_category")
    sub = data.get("current_subcategory")

    keyboard = InlineKeyboardMarkup(row_width=2)
    for prod in catalog_data[cat][sub]:
        keyboard.add(InlineKeyboardButton(prod, callback_data=f"prod:{prod}"))
    keyboard.add(
        InlineKeyboardButton("🔙 Назад", callback_data="back_to_subcats"),
        InlineKeyboardButton("♻️ Моя корзина", callback_data="view_cart"),
        InlineKeyboardButton("✅ Завершить заявку", callback_data="complete_order")
    )
    await callback.message.answer("Продолжайте выбирать товары:", reply_markup=keyboard)
    await OrderState.choosing_product.set()


# === Edit Cart ===
@dp.callback_query_handler(lambda c: c.data == "edit_cart", state='*')
@user_allowed
async def edit_cart(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    cart = data.get("cart", [])
    if not cart:
        await callback.message.answer("Корзина пуста.")
        return

    keyboard = InlineKeyboardMarkup(row_width=1)
    for idx, item in enumerate(cart):
        btn_text = f"{item['product']} — {item['quantity']} шт."
        keyboard.add(
            InlineKeyboardButton(f"🗑 Удалить: {btn_text}", callback_data=f"del_item:{idx}"),
            InlineKeyboardButton(f"🔄 Изменить: {btn_text}", callback_data=f"edit_item:{idx}")
        )
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="view_cart"))
    await callback.message.answer("✏️ Редактирование корзины:", reply_markup=keyboard)
    await OrderState.editing_cart.set()

# === Delete Item ===
@dp.callback_query_handler(lambda c: c.data.startswith("del_item:"), state=OrderState.editing_cart)
@user_allowed
async def delete_item(callback: types.CallbackQuery, state: FSMContext):
    index = int(callback.data.split(":")[1])
    data = await state.get_data()
    cart = data.get("cart", [])
    if 0 <= index < len(cart):
        removed = cart.pop(index)
        await state.update_data(cart=cart)
        await callback.message.answer(f"🗑 {removed['product']} удалён из корзины.")
    await edit_cart(callback, state)

# === Edit Quantity ===
@dp.callback_query_handler(lambda c: c.data.startswith("edit_item:"), state=OrderState.editing_cart)
@user_allowed
async def prompt_quantity_edit(callback: types.CallbackQuery, state: FSMContext):
    index = int(callback.data.split(":")[1])
    await state.update_data(editing_index=index)
    await callback.message.answer("Введите новое количество:")
    await OrderState.updating_quantity.set()

@dp.message_handler(lambda m: m.text.isdigit(), state=OrderState.updating_quantity)
@user_allowed
async def apply_quantity_edit(message: types.Message, state: FSMContext):
    qty = int(message.text)
    data = await state.get_data()
    cart = data.get("cart", [])
    idx = data.get("editing_index")

    if 0 <= idx < len(cart):
        cart[idx]["quantity"] = qty
        await state.update_data(cart=cart)
        await message.answer(f"🔄 Количество обновлено: {cart[idx]['product']} — {qty} шт.")

    await edit_cart(message, state)

@dp.message_handler(state=OrderState.updating_quantity)
@user_allowed
async def invalid_quantity_update(message: types.Message, state: FSMContext):
    await message.answer("Пожалуйста, введите корректное число.")

# === Complete Order: choose legal entity ===
@dp.callback_query_handler(lambda c: c.data == "complete_order", state='*')
@user_allowed
async def complete_order(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    cart = data.get("cart", [])
    if not cart:
        await callback.message.answer("Корзина пуста. Добавьте хотя бы один товар.")
        return

    keyboard = InlineKeyboardMarkup(row_width=1)
    for legal in LEGAL_ENTITIES:
        keyboard.add(InlineKeyboardButton(legal, callback_data=f"legal:{legal}"))
    await callback.message.answer("Выберите юридическое лицо для заявки:", reply_markup=keyboard)
    await OrderState.choosing_legal.set()

# === Legal Entity Selected ===
@dp.callback_query_handler(lambda c: c.data.startswith("legal:"), state=OrderState.choosing_legal)
@user_allowed
async def confirm_submission(callback: types.CallbackQuery, state: FSMContext):
    legal = callback.data.split(":", 1)[1]
    await state.update_data(selected_legal=legal)
    data = await state.get_data()
    cart = data.get("cart", [])

    summary = f"📦 *Подтверждение заказа:*\n\nЮр. лицо: {legal}\n\n"
    for idx, item in enumerate(cart, 1):
        summary += f"{idx}. {item['product']} — {item['quantity']} шт.\n"

    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("✅ Подтвердить", callback_data="send_order"),
        InlineKeyboardButton("🔙 Назад", callback_data="view_cart")
    )

    await callback.message.answer(summary, parse_mode="Markdown", reply_markup=keyboard)
    await OrderState.confirming.set()

# === Final Confirmation ===
@dp.callback_query_handler(lambda c: c.data == "send_order", state=OrderState.confirming)
@user_allowed
async def send_order(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    cart = data.get("cart", [])
    legal = data.get("selected_legal")

    grouped = {}
    for item in cart:
        supplier = item['supplier']
        grouped.setdefault(supplier, []).append(item)

    text = f"🆕 Новый заказ от @{callback.from_user.username}:\nЮр. лицо: {legal}\n\n"
    for supplier, items in grouped.items():
        text += f"Поставщик: {supplier}\n"
        for it in items:
            text += f"- {it['product']} — {it['quantity']} шт.\n"
        text += "\n"

    await bot.send_message(ADMIN_ID, text)
    await callback.message.answer("✅ Заказ отправлен администратору.")
    await state.finish()

# === START BOT ===
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
