from aiogram import Router
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from filters.access import is_user_allowed
from states.example_state import MyStates

router = Router()

@router.message(MyStates.waiting_for_input)
async def handle_user_input(message: Message, state: FSMContext):
    if not is_user_allowed(message.from_user.id):
        await message.answer("⛔️ Доступ запрещён.")
        return

    await message.answer(f"Вы написали: {message.text}")
    await state.clear()