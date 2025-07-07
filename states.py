from aiogram.dispatcher.filters.state import State, StatesGroup

class OrderState(StatesGroup):
    choosing_category = State()
    choosing_subcategory = State()
    choosing_product = State()
    entering_quantity = State()