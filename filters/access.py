import json
from aiogram.types import Message, CallbackQuery
from config import ALLOWED_USERS_FILE

def load_allowed_users():
    try:
        with open(ALLOWED_USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print("Ошибка при загрузке allowed_users.json:", e)
        return {}

def is_user_allowed(user_id: int) -> bool:
    allowed = load_allowed_users()
    return str(user_id) in allowed