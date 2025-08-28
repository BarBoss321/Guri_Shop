from aiogram import Router, F
from aiogram.types import CallbackQuery
from services.db import toggle_item_received, order_with_items, all_items_received, close_followup
from .bot_refs import bot  # или получите bot из контекста, если у вас так принято

router = Router()

@router.callback_query(F.data.startswith("fu:toggle:"))
async def fu_toggle(c: CallbackQuery):
    _, _, order_id, item_id = c.data.split(":")
    toggle_item_received(int(item_id))
    order, items = order_with_items(int(order_id))
    await c.message.edit_text(followup_text(order, items), reply_markup=followup_kb(items, int(order_id)))
    await c.answer("Обновлено")

@router.callback_query(F.data.startswith("fu:done:"))
async def fu_done(c: CallbackQuery):
    order_id = int(c.data.split(":")[2])
    if all_items_received(order_id):
        close_followup(order_id)
        await c.message.edit_text("🎉 Отлично! Все позиции по заявке получены. Закрываю контроль.")
    else:
        await c.answer("Есть позиции в статусе «⏳ Не пришло». Отметьте все полученные.", show_alert=True)