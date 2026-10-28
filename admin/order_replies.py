import html

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from config import ADMIN_ID

router = Router()
router.message.filter(F.from_user.id == ADMIN_ID)
router.callback_query.filter(F.from_user.id == ADMIN_ID)


class OrderReply(StatesGroup):
    waiting_note = State()


def order_reply_kb(user_id: int, order_no: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Принят полностью", callback_data=f"ordok_{user_id}_{order_no}")],
        [InlineKeyboardButton(text="📝 Принят с замечаниями", callback_data=f"ordnote_{user_id}_{order_no}")],
    ])


def _parse(data: str) -> tuple[int, int]:
    _, user_id, order_no = data.split("_")
    return int(user_id), int(order_no)


async def _notify_user(bot, user_id: int, text: str) -> bool:
    try:
        await bot.send_message(user_id, text)
        return True
    except Exception:
        # пользователь заблокировал бота или удалил чат
        return False


async def _close_order(bot, chat_id: int, message_id: int, order_html: str, status: str):
    """Дописывает решение в заявку у админа и убирает кнопки, чтобы не ответить дважды."""
    try:
        await bot.edit_message_text(
            chat_id=chat_id, message_id=message_id,
            text=f"{order_html}\n\n{status}", reply_markup=None
        )
    except Exception:
        await bot.send_message(chat_id, status)


@router.callback_query(F.data.startswith("ordok_"))
async def order_accepted(callback: CallbackQuery, state: FSMContext):
    user_id, order_no = _parse(callback.data)
    await state.clear()
    delivered = await _notify_user(
        callback.bot, user_id, f"✅ Ваша заявка №{order_no} принята полностью."
    )
    status = "✅ <b>Принят полностью</b>"
    if not delivered:
        status += "\n⚠️ Пользователь не получил уведомление (заблокировал бота)."
    # html_text сохраняет жирный шрифт и прочую разметку исходной заявки
    await _close_order(callback.bot, callback.message.chat.id, callback.message.message_id,
                       callback.message.html_text, status)
    await callback.answer("Пользователь уведомлён" if delivered else "Не удалось уведомить")


@router.callback_query(F.data.startswith("ordnote_") & (F.data != "ordnote_cancel"))
async def order_note_start(callback: CallbackQuery, state: FSMContext):
    user_id, order_no = _parse(callback.data)
    await state.set_state(OrderReply.waiting_note)
    # текст заявки — в FSM (Redis), чтобы пережил перезапуск бота, пока админ пишет замечание
    await state.update_data(
        note_user_id=user_id, note_order_no=order_no,
        note_message_id=callback.message.message_id, note_order_html=callback.message.html_text
    )
    await callback.message.answer(
        f"📝 Напишите замечание к заявке №{order_no} одним сообщением.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✖️ Отмена", callback_data="ordnote_cancel")]
        ])
    )
    await callback.answer()


@router.callback_query(F.data == "ordnote_cancel")
async def order_note_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Отменено. Кнопки под заявкой остались — можно ответить позже.")
    await callback.answer()


@router.message(OrderReply.waiting_note, F.text)
async def order_note_text(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    user_id, order_no = data["note_user_id"], data["note_order_no"]
    note = html.escape(message.text)

    delivered = await _notify_user(
        message.bot, user_id,
        f"⚠️ Ваша заявка №{order_no} принята с замечаниями:\n\n<i>{note}</i>"
    )
    status = f"📝 <b>Принят с замечаниями:</b>\n<i>{note}</i>"
    if not delivered:
        status += "\n⚠️ Пользователь не получил уведомление (заблокировал бота)."
    await _close_order(message.bot, message.chat.id, data["note_message_id"], data["note_order_html"], status)
    await message.answer(
        f"✅ Замечание к заявке №{order_no} отправлено." if delivered
        else "⚠️ Замечание сохранено в заявке, но пользователь его не получил."
    )
