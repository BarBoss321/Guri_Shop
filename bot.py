import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from handlers import user_handlers, catalog_handlers, cart_handlers, cart_view
from admin import admin_handlers

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
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    # хендлеры
    dp.include_router(user_handlers.router)
    dp.include_router(admin_handlers.router)
    dp.include_router(catalog_handlers.router)
    dp.include_router(cart_handlers.router)
    dp.include_router(cart_view.router)

    # регистрируем стартовый хук
    dp.startup.register(on_startup)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)




if __name__ == "__main__":
    asyncio.run(main())
