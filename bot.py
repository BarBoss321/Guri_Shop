import asyncio
import logging
import os
from pathlib import Path
from aiogram.client.default import DefaultBotProperties
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage, DefaultKeyBuilder
import redis.asyncio as aioredis
from dotenv import load_dotenv
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram import F
from services.db import get_due_followups, order_with_items, mark_followup_sent, toggle_item_received, all_items_received, close_followup
from handlers import user_handlers, catalog_handlers, cart_handlers, cart_view
from admin import admin_handlers
from services.db import ensure_schema, abs_db_path
import handlers.followup_handlers as followup_handlers


# --- Загружаем .env ---
BASE_DIR = Path(__file__).parent
ENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True, encoding="utf-8")

print("ENV PATH =", ENV_PATH)
print("BOT_TOKEN prefix =", (os.getenv("BOT_TOKEN") or "")[:8])

# --- Переменные ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0") or 0)
DB_PATH = os.getenv("DB_PATH", "shop_bot.db")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

assert BOT_TOKEN, "BOT_TOKEN is empty (set it in .env)"

# --- on_startup ---
async def on_startup(bot: Bot):
    print("Preparing DB at:", abs_db_path())
    await ensure_schema()

# --- main ---
async def main():
    logging.basicConfig(level=logging.INFO)

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode="HTML")
    )

    # FSM-хранилище в Redis
    redis = aioredis.from_url(REDIS_URL)
    storage = RedisStorage(
        redis=redis,
        key_builder=DefaultKeyBuilder(with_bot_id=True, prefix="guri_shop2")
    )
    dp = Dispatcher(storage=storage)

    # Роутеры
    dp.include_router(user_handlers.router)
    dp.include_router(admin_handlers.router)
    dp.include_router(catalog_handlers.router)
    dp.include_router(cart_handlers.router)
    dp.include_router(cart_view.router)
    dp.include_router(followup_handlers.router)  # где вы разместили хэндлеры

    dp.startup.register(on_startup)
    dp.startup.register(on_startup)

    # стартуем фонового работника после запуска
    async def _run_worker():
        # даём Телеграму подключиться
        await asyncio.sleep(2)
        asyncio.create_task(followup_worker(bot))

    dp.startup.register(lambda *_: _run_worker())

    await bot.delete_webhook(drop_pending_updates=False)
    await dp.start_polling(bot, polling_timeout=60)

    def followup_text(order, items):
        lines = [f"📦 Контроль поставки по заявке #{order['id']} от {order['created_at']}:"]
        for it in items:
            mark = "✅" if it["received"] else "⏳"
            lines.append(f"{mark} {it['title']} × {it['qty']}")
        lines.append("\nНажимайте по позициям чтобы отметить получение.")
        return "\n".join(lines)

    def followup_kb(items, order_id):
        kb = InlineKeyboardBuilder()
        for it in items:
            txt = ("✅ " if it["received"] else "⏳ ") + it["title"]
            kb.button(text=txt, callback_data=f"fu:toggle:{order_id}:{it['id']}")
        kb.button(text="Все получено", callback_data=f"fu:done:{order_id}")
        kb.adjust(1)
        return kb.as_markup()

    async def send_followup(bot: Bot, fu_row):
        order_id = fu_row["order_id"]
        order, items = order_with_items(order_id)
        if not order or not items:
            close_followup(order_id);
            return
        text = followup_text(order, items)
        kb = followup_kb(items, order_id)
        msg = await bot.send_message(fu_row["chat_id"], text, reply_markup=kb)
        mark_followup_sent(fu_row["id"], fu_row["chat_id"], msg.message_id)

    async def followup_worker(bot: Bot):
        while True:
            try:
                for fu in get_due_followups():
                    await send_followup(bot, fu)
            except Exception as e:
                logging.exception("followup_worker error: %s", e)
            await asyncio.sleep(60)  # раз в минуту

if __name__ == "__main__":
    asyncio.run(main())