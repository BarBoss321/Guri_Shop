from aiogram.fsm.state import State, StatesGroup

class CartStates(StatesGroup):
    waiting_for_quantity = State()
    editing_quantity = State()
    awaiting_quantity = State()
    choosing_company = State()
