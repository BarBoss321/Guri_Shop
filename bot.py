import asyncio
import logging
from aiogram import Bot, Dispatcher
from handlers import user_handlers, catalog_handlers, cart_handlers, cart_view
from admin import admin_handlers
from pathlib import Path
from aiogram.fsm.storage.sqlite import SQLiteStorage


# ✅ это важно
from services.db import ensure_schema, abs_db_path
from dotenv import load_dotenv
import os

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0") or 0)
DB_PATH = os.getenv("DB_PATH", "shop_bot.db")
assert BOT_TOKEN, "BOT_TOKEN is empty (set it in .env)"
# 👇 добавляем on_startup
async def on_startup(bot: Bot):
    print("Preparing DB at:", abs_db_path())
    await ensure_schema()  # создаём таблицы (orders и т.д.)

async def main():
    logging.basicConfig(level=logging.INFO)

    bot = Bot(token=BOT_TOKEN)  # можно добавить parse_mode, если нужно
    # --- FSM в файле рядом с bot.py ---
    base_dir = Path(__file__).parent
    fsm_path = base_dir / "fsm.sqlite"
    storage = SQLiteStorage(path=str(fsm_path))
    dp = Dispatcher(storage=storage)

    # хендлеры
    dp.include_router(user_handlers.router)
    dp.include_router(admin_handlers.router)
    dp.include_router(catalog_handlers.router)
    dp.include_router(cart_handlers.router)
    dp.include_router(cart_view.router)

    # стартовый хук
    dp.startup.register(on_startup)

    # НЕ сбрасываем накопившиеся апдейты при переходе с вебхука на пуллинг
    await bot.delete_webhook(drop_pending_updates=False)

    # увеличим таймаут long-polling — устойчивее к обрывам
    await dp.start_polling(bot, polling_timeout=60)




if __name__ == "__main__":
    asyncio.run(main())
