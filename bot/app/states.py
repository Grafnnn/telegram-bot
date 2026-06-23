"""FSM states."""

from aiogram.fsm.state import State, StatesGroup


class PickFabricStates(StatesGroup):
    waiting_for_description = State()


class TryOnPhotoStates(StatesGroup):
    waiting_for_photo = State()
    waiting_for_mask_preset = State()
    waiting_for_garment_crop = State()
    photo_ready = State()
