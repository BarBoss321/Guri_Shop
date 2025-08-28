import aiosqlite

DB_PATH = "shop_bot.db"

async def get_db():
    return await aiosqlite.connect(DB_PATH)

async def create_companies_table():
    db = await get_db()
    await db.execute("""
        CREATE TABLE IF NOT EXISTS companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL
        );
    """)
    await db.commit()
    await db.close()
async def get_db():
    return await aiosqlite.connect(DB_PATH)

async def insert_test_company(user_id: int, name: str):
    db = await get_db()
    await db.execute("INSERT INTO companies (user_id, name) VALUES (?, ?)", (user_id, name))
    await db.commit()
    await db.close()

import asyncio
import os
from pathlib import Path
from services.db import create_companies_table, insert_test_company

# Абсолютный путь: файл лежит в корне проекта рядом с bot.py
DB_PATH = Path(__file__).resolve().parent.parent / "shop_bot.db"

async def ensure_schema():
    db = await get_db()
    await db.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id   INTEGER NOT NULL,
            item_id   INTEGER NOT NULL,
            quantity  INTEGER NOT NULL,
            order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id);")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_orders_item ON orders(item_id);")
    await db.commit()

    # Диагностика: покажем, какие таблицы реально есть
    cur = await db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
    names = [row[0] for row in await cur.fetchall()]
    print("DB file:", DB_PATH)
    print("Tables:", names)

    await db.close()

def abs_db_path() -> str:
    return DB_PATH.as_posix()



