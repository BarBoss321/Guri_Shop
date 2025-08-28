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

from dataclasses import dataclass
from datetime import datetime, timedelta
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / os.getenv("DB_PATH", "shop_bot.db")

def abs_db_path():
    return str(DB_PATH.resolve())

def connect():
    conn = sqlite3.connect(abs_db_path())
    conn.row_factory = sqlite3.Row
    return conn

async def ensure_schema():
    conn = connect()
    cur = conn.cursor()
    # заявки (если у вас уже есть — пропустите)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS orders(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        chat_id INTEGER NOT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        status TEXT NOT NULL DEFAULT 'OPEN'
    )""")
    # позиции заявки
    cur.execute("""
    CREATE TABLE IF NOT EXISTS order_items(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        qty REAL NOT NULL,
        received INTEGER NOT NULL DEFAULT 0,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE
    )""")
    # задачи на пост-контроль
    cur.execute("""
    CREATE TABLE IF NOT EXISTS followups(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL UNIQUE,
        user_id INTEGER NOT NULL,
        chat_id INTEGER NOT NULL,
        due_at TIMESTAMP NOT NULL,     -- когда слать проверку в следующий раз
        sent_at TIMESTAMP,             -- когда реально отправили (последний раз)
        repeats_left INTEGER NOT NULL DEFAULT 3, -- сколько ещё напоминаний
        is_closed INTEGER NOT NULL DEFAULT 0,    -- 1 = всё ок, больше не слать
        message_id INTEGER,            -- последнее сообщение с кнопками
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE
    )""")
    conn.commit()
    conn.close()

def create_followup(order_id:int, user_id:int, chat_id:int, delay_days:int=1):
    conn = connect(); cur = conn.cursor()
    cur.execute("""
        INSERT OR IGNORE INTO followups(order_id,user_id,chat_id,due_at,repeats_left,is_closed)
        VALUES(?,?,?,?,3,0)
    """, (order_id, user_id, chat_id, (datetime.utcnow()+timedelta(days=delay_days)).isoformat()))
    conn.commit(); conn.close()

def get_due_followups(limit=20):
    conn = connect(); cur = conn.cursor()
    cur.execute("""
      SELECT * FROM followups
      WHERE is_closed=0 AND datetime(due_at) <= datetime('now')
      ORDER BY due_at ASC LIMIT ?
    """, (limit,))
    rows = cur.fetchall(); conn.close(); return rows

def mark_followup_sent(fu_id:int, chat_id:int, msg_id:int):
    conn = connect(); cur = conn.cursor()
    cur.execute("UPDATE followups SET sent_at=datetime('now'), message_id=?, due_at=datetime('now','+1 day'), repeats_left = CASE WHEN repeats_left>0 THEN repeats_left-1 ELSE 0 END WHERE id=?",
                (msg_id, fu_id))
    conn.commit(); conn.close()

def close_followup(order_id:int):
    conn = connect(); cur = conn.cursor()
    cur.execute("UPDATE followups SET is_closed=1 WHERE order_id=?", (order_id,))
    conn.commit(); conn.close()

def order_with_items(order_id:int):
    conn = connect(); cur = conn.cursor()
    cur.execute("SELECT * FROM orders WHERE id=?", (order_id,))
    order = cur.fetchone()
    cur.execute("SELECT * FROM order_items WHERE order_id=? ORDER BY id", (order_id,))
    items = cur.fetchall()
    conn.close()
    return order, items

def toggle_item_received(item_id:int):
    conn = connect(); cur = conn.cursor()
    cur.execute("UPDATE order_items SET received = CASE received WHEN 1 THEN 0 ELSE 1 END, updated_at=datetime('now') WHERE id=?", (item_id,))
    conn.commit(); conn.close()

def all_items_received(order_id:int) -> bool:
    conn = connect(); cur = conn.cursor()
    cur.execute("SELECT COUNT(*)=SUM(received) FROM order_items WHERE order_id=?", (order_id,))
    ok = cur.fetchone()[0] == 1
    conn.close(); return ok

