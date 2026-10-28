import logging
import os
import random
from pathlib import Path

import aiohttp
from aiogram import Bot
from aiogram.types import FSInputFile
from aiohttp_socks import ProxyConnector

from services.db import get_db, BASE_DIR

logger = logging.getLogger(__name__)

# свои картинки на случай, если интернет-источник недоступен
MEMES_DIR = BASE_DIR / "memes"
SUBREDDITS = [s.strip() for s in os.getenv("MEME_SUBREDDITS", "Pikabu,wholesomememes,memes").split(",") if s.strip()]
PHOTO_EXT = {".jpg", ".jpeg", ".png", ".webp"}
ANIMATION_EXT = {".gif", ".mp4"}
MEMES_KEEP_MONTHS = 6


async def _is_sent(db, key: str) -> bool:
    cur = await db.execute("SELECT 1 FROM sent_memes WHERE key = ?", (key,))
    return await cur.fetchone() is not None


async def _mark_sent(db, key: str):
    await db.execute(
        "INSERT OR REPLACE INTO sent_memes (key, sent_at) VALUES (?, CURRENT_TIMESTAMP)",
        (key,)
    )
    await db.commit()


async def _send(bot: Bot, chat_ids: list[int], media, ext: str, caption: str | None = None):
    # parse_mode=None: в заголовках мемов бывают < и &, а у бота по умолчанию HTML
    send = bot.send_animation if ext in ANIMATION_EXT else bot.send_photo
    first, *rest = chat_ids
    msg = await send(first, media, caption=caption, parse_mode=None)
    # остальным — уже загруженный в Telegram файл: быстрее и без повторного скачивания
    file_id = msg.animation.file_id if msg.animation else msg.photo[-1].file_id
    for chat_id in rest:
        try:
            await send(chat_id, file_id, caption=caption, parse_mode=None)
        except Exception as e:
            logger.warning("мем не дошёл до %s: %r", chat_id, e)


async def _fetch_online(subreddit: str) -> list[dict]:
    proxy = os.getenv("PROXY_URL") or None
    connector = ProxyConnector.from_url(proxy) if proxy else None
    timeout = aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        async with session.get(f"https://meme-api.com/gimme/{subreddit}/50") as resp:
            data = await resp.json()
    return [
        m for m in data.get("memes", [])
        if not m.get("nsfw") and not m.get("spoiler")
        and Path(m.get("url", "")).suffix.lower() in PHOTO_EXT | ANIMATION_EXT
    ]


async def _send_online(bot: Bot, chat_ids: list[int], db) -> bool:
    attempts = 5  # не перебирать сотни мемов, если, например, получатель заблокировал бота
    for subreddit in random.sample(SUBREDDITS, len(SUBREDDITS)):
        try:
            memes = await _fetch_online(subreddit)
        except Exception as e:
            logger.warning("meme-api %s недоступен: %r", subreddit, e)
            continue

        random.shuffle(memes)
        for meme in memes:
            key = meme.get("postLink") or meme["url"]
            if await _is_sent(db, key):
                continue
            if attempts == 0:
                return False
            attempts -= 1
            try:
                await _send(bot, chat_ids, meme["url"], Path(meme["url"]).suffix.lower(), meme.get("title"))
            except Exception as e:
                # Telegram иногда не может скачать картинку по ссылке — берём следующую
                logger.warning("мем %s не отправился: %r", meme["url"], e)
                continue
            await _mark_sent(db, key)
            return True
    return False


async def _send_local(bot: Bot, chat_ids: list[int], db) -> bool:
    files = [p for p in MEMES_DIR.glob("*") if p.suffix.lower() in PHOTO_EXT | ANIMATION_EXT]
    if not files:
        return False

    unsent = [p for p in files if not await _is_sent(db, f"file:{p.name}")]
    if unsent:
        path = random.choice(unsent)
    else:
        # все уже были — берём тот, что показывали давнее всего
        cur = await db.execute(
            "SELECT key FROM sent_memes WHERE key LIKE 'file:%' ORDER BY sent_at LIMIT 1"
        )
        row = await cur.fetchone()
        by_name = {f"file:{p.name}": p for p in files}
        path = by_name.get(row[0]) if row else None
        path = path or random.choice(files)

    await _send(bot, chat_ids, FSInputFile(path), path.suffix.lower())
    await _mark_sent(db, f"file:{path.name}")
    return True


async def send_random_meme(bot: Bot, chat_ids: list[int]):
    """Один и тот же мем пользователю и админу после заявки. Никогда не роняет обработку заказа."""
    chat_ids = list(dict.fromkeys(chat_ids))  # если заказ оформил сам админ — один раз
    db = await get_db()
    try:
        # история мемов живёт полгода: старые записи стираются, и эти мемы снова могут попасться
        await db.execute(f"DELETE FROM sent_memes WHERE sent_at < datetime('now', '-{MEMES_KEEP_MONTHS} months')")
        await db.commit()
        if not await _send_online(bot, chat_ids, db):
            await _send_local(bot, chat_ids, db)
    except Exception:
        logger.exception("не удалось отправить мем")
    finally:
        await db.close()
