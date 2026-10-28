import asyncio
import logging
import os
from pathlib import Path
from dotenv import load_dotenv

# --- Загружаем .env (до импорта хендлеров: они читают переменные при импорте) ---
BASE_DIR = Path(__file__).parent
ENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True, encoding="utf-8")

from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage, DefaultKeyBuilder
import redis.asyncio as aioredis
from handlers import history_handlers
from handlers import user_handlers, catalog_handlers, cart_handlers, cart_view
from admin import admin_handlers
from filters.access import AccessMiddleware
from services.db import ensure_schema, abs_db_path

print("ENV PATH =", ENV_PATH)
print("BOT_TOKEN prefix =", (os.getenv("BOT_TOKEN") or "")[:8])

# --- Переменные ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0") or 0)
DB_PATH = os.getenv("DB_PATH", "shop_bot.db")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
# Необязательно: http-прокси до api.telegram.org, если с сервера Telegram тормозит
PROXY_URL = os.getenv("PROXY_URL") or None

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
        session=AiohttpSession(proxy=PROXY_URL) if PROXY_URL else None,
        default=DefaultBotProperties(parse_mode="HTML")
    )

    # FSM-хранилище в Redis
    redis = aioredis.from_url(REDIS_URL)
    storage = RedisStorage(
        redis=redis,
        key_builder=DefaultKeyBuilder(with_bot_id=True, prefix="guri_shop2")
    )
    dp = Dispatcher(storage=storage)

    # доступ только для тех, кого админ добавил через /add
    dp.message.outer_middleware(AccessMiddleware())
    dp.callback_query.outer_middleware(AccessMiddleware())

    # Роутеры
    dp.include_router(user_handlers.router)
    dp.include_router(admin_handlers.router)
    dp.include_router(catalog_handlers.router)
    dp.include_router(cart_handlers.router)
    dp.include_router(cart_view.router)
    dp.include_router(history_handlers.router)

    dp.startup.register(on_startup)

    await bot.delete_webhook(drop_pending_updates=False)
    await dp.start_polling(bot, polling_timeout=60)

if __name__ == "__main__":
    asyncio.run(main())