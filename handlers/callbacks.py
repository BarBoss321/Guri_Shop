from aiogram import Router, F
from aiogram.types import CallbackQuery

from filters.access import is_user_allowed

router = Router()

@router.callback_query(F.data == "example_action")
async def handle_callback(callback: CallbackQuery):
    if not is_user_allowed(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещён.", show_alert=True)
        return

    await callback.message.answer("✅ Вы нажали на кнопку.")
    await callback.answer()