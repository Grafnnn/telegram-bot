"""FSM states."""

from aiogram.fsm.state import State, StatesGroup


class PickFabricStates(StatesGroup):
    waiting_for_description = State()
