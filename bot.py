import asyncio
import logging
import os
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramNetworkError
from aiogram.fsm.storage.redis import RedisStorage, DefaultKeyBuilder
import redis.asyncio as aioredis
from dotenv import load_dotenv

from handlers import history_handlers
from handlers import user_handlers, catalog_handlers, cart_handlers, cart_view
from admin import admin_handlers
from services.db import ensure_schema, abs_db_path


BASE_DIR = Path(__file__).parent
ENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True, encoding="utf-8")

print("ENV PATH =", ENV_PATH)
print("BOT_TOKEN prefix =", (os.getenv("BOT_TOKEN") or "")[:8])

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0") or 0)
DB_PATH = os.getenv("DB_PATH", "shop_bot.db")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

assert BOT_TOKEN, "BOT_TOKEN is empty (set it in .env)"


async def on_startup(bot: Bot):
    print("Preparing DB at:", abs_db_path())
    await ensure_schema()


def build_dispatcher(storage: RedisStorage) -> Dispatcher:
    dp = Dispatcher(storage=storage)

    dp.include_router(user_handlers.router)
    dp.include_router(admin_handlers.router)
    dp.include_router(catalog_handlers.router)
    dp.include_router(cart_handlers.router)
    dp.include_router(cart_view.router)
    dp.include_router(history_handlers.router)

    dp.startup.register(on_startup)
    return dp


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )

    redis = aioredis.from_url(REDIS_URL)

    storage = RedisStorage(
        redis=redis,
        key_builder=DefaultKeyBuilder(with_bot_id=True, prefix="guri_shop2")
    )

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode="HTML")
    )

    dp = build_dispatcher(storage)

    try:
        await bot.delete_webhook(drop_pending_updates=False)

        while True:
            try:
                logging.info("Start polling")
                await dp.start_polling(bot, polling_timeout=60)
            except TelegramNetworkError:
                logging.exception("Telegram network error, retry in 5 sec")
                await asyncio.sleep(5)
            except Exception:
                logging.exception("Bot crashed, retry in 5 sec")
                await asyncio.sleep(5)

    finally:
        await bot.session.close()
        await storage.close()
        await redis.aclose()


if __name__ == "__main__":
    asyncio.run(main())
