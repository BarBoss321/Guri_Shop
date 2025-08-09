from aiogram.fsm.state import State, StatesGroup

class MyStates(StatesGroup):
    waiting_for_input = State()