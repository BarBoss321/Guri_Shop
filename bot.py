import asyncio
import logging
import os
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.sqlite import SQLiteStorage
from dotenv import load_dotenv

from handlers import user_handlers, catalog_handlers, cart_handlers, cart_view
from admin import admin_handlers
from services.db import ensure_schema, abs_db_path


# --- Загружаем .env ---
BASE_DIR = Path(__file__).parent
ENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True, encoding="utf-8")

# Диагностика (оставьте на время)
print("ENV PATH =", ENV_PATH)
print("BOT_TOKEN prefix =", (os.getenv('BOT_TOKEN') or '')[:8])

# --- Читаем переменные ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0") or 0)
DB_PATH = os.getenv("DB_PATH", "shop_bot.db")

assert BOT_TOKEN, "BOT_TOKEN is empty (set it in .env)"


# --- on_startup ---
async def on_startup(bot: Bot):
    print("Preparing DB at:", abs_db_path())
    await ensure_schema()


# --- main ---
async def main():
    logging.basicConfig(level=logging.INFO)

    bot = Bot(token=BOT_TOKEN, parse_mode="HTML")

    # FSM-хранилище в SQLite
    fsm_path = BASE_DIR / "fsm.sqlite"
    storage = SQLiteStorage(path=str(fsm_path))

    dp = Dispatcher(storage=storage)

    # Роутеры
    dp.include_router(user_handlers.router)
    dp.include_router(admin_handlers.router)
    dp.include_router(catalog_handlers.router)
    dp.include_router(cart_handlers.router)
    dp.include_router(cart_view.router)

    dp.startup.register(on_startup)

    # не сбрасываем апдейты
    await bot.delete_webhook(drop_pending_updates=False)

    # polling
    await dp.start_polling(bot, polling_timeout=60)


if __name__ == "__main__":
    asyncio.run(main())
