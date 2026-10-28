import asyncio
import html
import shutil
from datetime import datetime

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from config import ADMIN_ID
from services.db import DB_PATH, BASE_DIR
from services.catalog_io import export_catalog, plan_import, parse_workbook, apply_import

router = Router()
router.message.filter(F.from_user.id == ADMIN_ID)
router.callback_query.filter(F.from_user.id == ADMIN_ID)

DATA_DIR = BASE_DIR / "data"
PENDING = DATA_DIR / "catalog_pending.xlsx"
BACKUPS = BASE_DIR / "backups"
LIST_LIMIT = 10


async def _send_catalog(message: Message):
    DATA_DIR.mkdir(exist_ok=True)
    path = DATA_DIR / f"Ассортимент {datetime.now():%Y-%m-%d}.xlsx"
    await asyncio.to_thread(export_catalog, DB_PATH, path)
    await message.answer_document(
        FSInputFile(path),
        caption=(
            "📦 Текущий ассортимент.\n\n"
            "Поправьте файл в Excel и отправьте его сюда — я покажу, что изменится, "
            "и попрошу подтвердить. Подсказки — на листе «Как заполнять»."
        )
    )


@router.message(Command("catalog"))
async def cmd_catalog(message: Message):
    await _send_catalog(message)


@router.callback_query(F.data == "admin_import")
async def admin_import(callback: CallbackQuery):
    await _send_catalog(callback.message)
    await callback.answer()


def _block(title: str, lines: list[str]) -> str:
    if not lines:
        return ""
    shown = "\n".join(f"  • {html.escape(x)}" for x in lines[:LIST_LIMIT])
    more = f"\n  … и ещё {len(lines) - LIST_LIMIT}" if len(lines) > LIST_LIMIT else ""
    return f"\n\n<b>{title} ({len(lines)}):</b>\n{shown}{more}"


@router.message(F.document)
async def catalog_upload(message: Message):
    name = (message.document.file_name or "").lower()
    if not name.endswith(".xlsx"):
        await message.answer("Пришлите файл ассортимента в формате Excel (.xlsx).")
        return

    DATA_DIR.mkdir(exist_ok=True)
    await message.bot.download(message.document, destination=PENDING)
    plan = await asyncio.to_thread(plan_import, DB_PATH, PENDING)

    if plan.errors:
        PENDING.unlink(missing_ok=True)
        await message.answer(
            "❌ В файле есть ошибки, ничего не изменено. Исправьте и пришлите снова."
            + _block("Ошибки", plan.errors)
        )
        return
    if not plan.has_changes:
        PENDING.unlink(missing_ok=True)
        await message.answer("✅ Файл совпадает с текущим ассортиментом — менять нечего.")
        return

    text = (
        f"📋 <b>Проверьте изменения</b> (товаров в файле: {len(plan.rows)})"
        + _block("➕ Новые товары", plan.new_items)
        + _block("✏️ Изменения", plan.changed)
        + _block("🙈 Будут скрыты", plan.hidden)
        + _block("📁 Новые разделы", plan.new_categories)
        + _block("🗑 Пропадут разделы", plan.removed_categories)
    )
    if plan.hidden:
        text += "\n\n<i>Скрытые товары остаются в истории заказов. Вернуть — добавить строку обратно с тем же ID.</i>"
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Применить", callback_data="catimp_apply"),
         InlineKeyboardButton(text="✖️ Отмена", callback_data="catimp_cancel")]
    ]))


@router.callback_query(F.data == "catimp_apply")
async def catalog_apply(callback: CallbackQuery):
    if not PENDING.exists():
        await callback.answer("Файл уже применён или отменён. Пришлите его заново.", show_alert=True)
        return
    # перепроверяем: между загрузкой и нажатием каталог мог поменяться
    rows, errors = await asyncio.to_thread(parse_workbook, PENDING)
    if errors:
        await callback.message.edit_text("❌ Файл больше не проходит проверку — пришлите его заново.")
        PENDING.unlink(missing_ok=True)
        await callback.answer()
        return

    BACKUPS.mkdir(exist_ok=True)
    backup = BACKUPS / f"shop_bot.{datetime.now():%Y%m%d-%H%M%S}.before-catalog.db"
    await asyncio.to_thread(shutil.copy2, DB_PATH, backup)
    try:
        await asyncio.to_thread(apply_import, DB_PATH, rows)
    except Exception as e:
        await callback.message.edit_text(
            f"❌ Не получилось применить, каталог не изменён.\n<code>{html.escape(repr(e))}</code>"
        )
        await callback.answer()
        return
    PENDING.unlink(missing_ok=True)

    await callback.message.edit_text(
        callback.message.html_text
        + f"\n\n✅ <b>Применено.</b> Копия базы до изменений: <code>backups/{backup.name}</code>"
    )
    await callback.answer("Ассортимент обновлён")


@router.callback_query(F.data == "catimp_cancel")
async def catalog_cancel(callback: CallbackQuery):
    PENDING.unlink(missing_ok=True)
    await callback.message.edit_text(callback.message.html_text + "\n\n✖️ <b>Отменено</b>, ничего не изменено.")
    await callback.answer()
