import aiosqlite
import os
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "shop_bot.db"))

def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # чтобы по именам колонок брать
    return conn

# --- ИСТОРИЯ ЗАКАЗОВ: последние N записей из orders (без order_items) ---
def get_last_grouped_orders(user_id: int, limit: int = 3):
    """
    Возвращает последние 'limit' заказов пользователя, где заказ — это
    все строки из orders с одинаковым временем (created_at ИЛИ order_date).
    Поле времени выбираем: сначала created_at, если его нет — order_date.
    """
    conn = sqlite3.connect("shop_bot.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        WITH o AS (
            SELECT
                id,
                user_id,
                item_id,
                quantity,
                COALESCE(created_at, order_date) AS ts
            FROM orders
            WHERE user_id = ?
        )
        SELECT
            MIN(o.id)                        AS order_no,           -- номер группы (минимальный id)
            ts                                AS created_at,         -- время заказа
            GROUP_CONCAT(i.name  ' × '  o.quantity, '||') AS items_join
        FROM o
        JOIN items i ON i.id = o.item_id
        GROUP BY ts
        ORDER BY datetime(ts) DESC
        LIMIT ?
    """, (user_id, limit))

    rows = cur.fetchall()
    conn.close()
    return rows

# если где-то вызывают старое имя:
def get_last_orders(user_id: int, limit: int = 3):
    return get_last_grouped_orders(user_id, limit)

# на всякий случай, если где-то вызывалась «старая» функция
def get_last_orders_with_items(user_id: int, limit: int = 3):
    return get_last_orders(user_id, limit)

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



