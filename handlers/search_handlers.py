import html

from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from services.db import get_db
from services.search import search_items

router = Router()

MAX_RESULTS = 20


async def _load_items():
    db = await get_db()
    cur = await db.execute("SELECT id, COALESCE(parent_id, 0), name FROM categories")
    cats = {cid: (parent, name) for cid, parent, name in await cur.fetchall()}
    cur = await db.execute("SELECT id, name, category_id FROM items WHERE active = 1")
    rows = await cur.fetchall()
    await db.close()

    items = []
    for item_id, name, cat_id in rows:
        # путь категорий вверх: для поиска по «вино» и для кнопки «Назад» из товара
        path, cid = [], cat_id
        while cid in cats and len(path) < 5:
            parent, cat_name = cats[cid]
            path.append(cat_name)
            cid = parent
        parent_id = cats.get(cat_id, (0, ""))[0]
        grand_id = cats.get(parent_id, (0, ""))[0]
        items.append((item_id, name, " ".join(path), cat_id, parent_id, grand_id))
    return items


@router.callback_query(F.data == "search_help")
async def search_help(callback: CallbackQuery):
    await callback.message.edit_text(
        "🔍 Напишите название товара в чат, например: <i>самбука</i>, <i>сок яблочный</i>, <i>вино белое</i>.\n"
        "Можно с опечатками и русскими буквами вместо английских.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_menu")]
        ])
    )
    await callback.answer()


# любой текст вне ввода количества — это поиск
@router.message(StateFilter(None), F.text, ~F.text.startswith("/"))
async def search(message: Message):
    query = message.text.strip()
    if len(query) < 2:
        await message.answer("🔍 Напишите хотя бы 2 буквы названия.")
        return

    found, exact = search_items(await _load_items(), query)
    back_row = [
        InlineKeyboardButton(text="🔙 В меню", callback_data="back_to_menu"),
        InlineKeyboardButton(text="🛒 Корзина", callback_data="view_cart"),
    ]

    if not found:
        await message.answer(
            f"😔 По запросу «{html.escape(query)}» ничего не нашлось.\nПопробуйте написать иначе или выберите из каталога.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[back_row])
        )
        return

    buttons = [
        [InlineKeyboardButton(
            text=name,
            callback_data=f"item_{item_id}:{cat_id}:{parent_id}:{grand_id}"
        )]
        for item_id, name, _, cat_id, parent_id, grand_id in found[:MAX_RESULTS]
    ]
    buttons.append(back_row)

    title = "🔍 Найдено" if exact else "🤔 Точных совпадений нет. Возможно, вы искали"
    text = f"{title} по запросу «{html.escape(query)}»:"
    if len(found) > MAX_RESULTS:
        text += f"\n\nПоказаны первые {MAX_RESULTS} из {len(found)} — уточните запрос."
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
