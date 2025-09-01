import aiosqlite
import os
import sqlite3
from pathlib import Path

DB_PATH = "shop_bot.db"

def connect():
    return sqlite3.connect("shop_bot.db")

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


async def fetch_last_orders(user_id: int, limit: int = 3):
    db = await get_db()
    cur = await db.execute("""
        SELECT id, created_at
        FROM orders
        WHERE user_id = ?
        ORDER BY datetime(created_at) DESC, id DESC
        LIMIT ?
    """, (user_id, limit))
    rows = await cur.fetchall()
    await db.close()
    return rows

async def fetch_order_items(order_id: int):
    db = await get_db()
    cur = await db.execute("""
        SELECT i.name AS title, oi.quantity AS qty
        FROM order_items oi
        JOIN items i ON i.id = oi.item_id
        WHERE oi.order_id = ?
        ORDER BY oi.id ASC
    """, (order_id,))
    rows = await cur.fetchall()
    await db.close()
    return rows


BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "shop_bot.db"))

def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # чтобы по именам колонок брать
    return conn


# --- ИСТОРИЯ ЗАКАЗОВ: последние N записей из orders (без order_items) ---
def get_last_orders(user_id: int, limit: int = 3):
    """
    Возвращает строки формата:
      (order_id, created_at, item_name, qty)
    по последним N записям из orders данного пользователя.
    В этой схеме каждая запись orders = одна позиция (item_id, quantity).
    """
    conn = connect()
    cur = conn.cursor()
    cur.execute("""
        SELECT
            o.id                                AS order_id,
            COALESCE(o.created_at, o.order_date, '') AS created_at,
            i.name                              AS item_name,
            o.quantity                          AS qty
        FROM orders o
        JOIN items  i ON i.id = o.item_id
        WHERE o.user_id = ?
        ORDER BY
            CASE
              WHEN o.created_at IS NOT NULL AND o.created_at <> '' THEN datetime(o.created_at)
              WHEN o.order_date IS NOT NULL  AND o.order_date  <> '' THEN datetime(o.order_date)
              ELSE datetime('now')
            END DESC,
            o.id DESC
        LIMIT ?
    """, (user_id, limit))
    rows = cur.fetchall()
    conn.close()
    return rows

# на всякий случай, если где-то вызывалась «старая» функция
def get_last_orders_with_items(user_id: int, limit: int = 3):
    return get_last_orders(user_id, limit)