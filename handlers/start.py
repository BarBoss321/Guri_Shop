from aiogram import Router
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.filters import CommandStart

from filters.access import is_user_allowed
from states.example_state import MyStates
from keyboards.inline import get_main_keyboard

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    if not is_user_allowed(message.from_user.id):
        await message.answer("⛔️ Доступ запрещён.")
        return

    await message.answer("Привет! Я бот на aiogram 3 🚀", reply_markup=get_main_keyboard())
    await state.set_state(MyStates.waiting_for_input)


