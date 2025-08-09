from aiogram import Dispatcher
from . import start, callbacks, fsm_example

def register_routers(dp: Dispatcher):
    dp.include_router(start.router)
    dp.include_router(callbacks.router)
    dp.include_router(fsm_example.router)