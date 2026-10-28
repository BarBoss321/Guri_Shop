from aiogram import Router, F
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import ADMIN_ID
from filters.access import add_user, remove_user, list_users

router = Router()
# все команды этого роутера — только для админа, остальным они просто не отвечают
router.message.filter(F.from_user.id == ADMIN_ID)
router.callback_query.filter(F.from_user.id == ADMIN_ID)

@router.message(F.text == "/admin")
async def admin_panel(message: Message, state: FSMContext):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="📦 Импорт товаров", callback_data="admin_import")],
    ])
    await message.answer(
        "Админ-панель\n\n"
        "/add @login — дать доступ\n"
        "/rem @login — забрать доступ\n"
        "/list — кто имеет доступ\n"
        "/catalog — ассортимент в Excel (поправить и прислать обратно)",
        reply_markup=keyboard
    )


@router.message(Command("add"))
async def cmd_add(message: Message, command: CommandObject):
    if not command.args:
        await message.answer("Напишите так: /add @login (или /add 123456789 — по ID)")
        return
    await message.answer("\n".join(add_user(arg) for arg in command.args.split()))


@router.message(Command("rem"))
async def cmd_rem(message: Message, command: CommandObject):
    if not command.args:
        await message.answer("Напишите так: /rem @login (или /rem 123456789 — по ID)")
        return
    await message.answer("\n".join(remove_user(arg) for arg in command.args.split()))


@router.message(Command("list"))
async def cmd_list(message: Message):
    await message.answer(await list_users(message.bot))


@router.callback_query(F.data == "admin_users")
async def admin_users(callback: CallbackQuery):
    await callback.message.answer(await list_users(callback.bot))
    await callback.answer()
