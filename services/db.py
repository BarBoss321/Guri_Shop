import aiosqlite
import os
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
# Абсолютный путь: по умолчанию файл лежит в корне проекта рядом с bot.py
DB_PATH = Path(os.getenv("DB_PATH") or "shop_bot.db")
if not DB_PATH.is_absolute():
    DB_PATH = BASE_DIR / DB_PATH

def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # чтобы по именам колонок брать
    return conn

# --- ИСТОРИЯ ЗАКАЗОВ: последние N заявок из orders ---
def get_last_grouped_orders(user_id: int, limit: int = 3):
    """
    Возвращает список заявок, где товары внутри каждой заявки уже сгруппированы:
    (order_no, created_at, items_join)
    items_join вида: "Товар1 : 5 || Товар2 : 3"
    """
    conn = connect()
    cur = conn.cursor()

    # одна заявка = все позиции, перенесённые из корзины одним INSERT (одинаковый order_date)
    cur.execute("""
        SELECT
            MIN(o.id)  AS order_no,
            o.order_date AS created_at,
            GROUP_CONCAT(i.name || ' : ' || o.quantity, '||') AS items_join
        FROM orders o
        JOIN items i ON i.id = o.item_id
        WHERE o.user_id = ?
        GROUP BY o.order_date
        ORDER BY datetime(o.order_date) DESC
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
    # индексы для каталога: без них каждое нажатие кнопки — полный перебор таблиц
    await db.execute("CREATE INDEX IF NOT EXISTS idx_categories_parent ON categories(parent_id);")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_items_category ON items(category_id);")
    # какие мемы уже отправлялись админу — чтобы не повторяться
    await db.execute("""
        CREATE TABLE IF NOT EXISTS sent_memes (
            key     TEXT PRIMARY KEY,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    await db.commit()

    # Диагностика: покажем, какие таблицы реально есть
    cur = await db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
    names = [row[0] for row in await cur.fetchall()]
    print("DB file:", DB_PATH)
    print("Tables:", names)

    await db.close()

def abs_db_path() -> str:
    return DB_PATH.as_posix()
