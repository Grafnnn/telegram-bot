from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class PickFabricStates(StatesGroup):
    waiting_for_description = State()
