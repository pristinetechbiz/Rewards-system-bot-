from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove

from config.settings import settings
from db import repository
from bot.keyboards.inline import main_menu, share_phone_keyboard
from bot.utils.helpers import normalise_phone, validate_nigerian_phone, format_points

router = Router()


class RegStates(StatesGroup):
    waiting_for_phone = State()


# ---------------------------------------------------------------------------
# /start
# ---------------------------------------------------------------------------
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    tg = message.from_user
    existing = await repository.get_user(tg.id)

    if existing:
        await message.answer(
            f"👋 Welcome back, <b>{tg.first_name}</b>!\n\n"
            f"💰 Balance: <b>{format_points(existing.points_balance)}</b>",
            parse_mode="HTML",
            reply_markup=main_menu(),
        )
        return

    # New user — create account
    user = await repository.create_user(
        user_id=tg.id,
        username=tg.username,
        first_name=tg.first_name,
        last_name=tg.last_name,
        registration_points=settings.POINTS_REGISTRATION,
    )
    await message.answer(
        f"🎉 <b>Welcome to the Community Rewards Bot, {tg.first_name}!</b>\n\n"
        f"You've been awarded <b>{format_points(settings.POINTS_REGISTRATION)}</b> just for joining.\n\n"
        f"📱 Share your phone number so you can redeem airtime & data later.",
        parse_mode="HTML",
        reply_markup=share_phone_keyboard(),
    )
    await state.set_state(RegStates.waiting_for_phone)


# ---------------------------------------------------------------------------
# Phone via contact button
# ---------------------------------------------------------------------------
@router.message(RegStates.waiting_for_phone, F.contact)
async def receive_phone_contact(message: Message, state: FSMContext) -> None:
    phone = normalise_phone(message.contact.phone_number)
    await repository.update_user_phone(message.from_user.id, phone)
    await state.clear()
    await message.answer(
        f"✅ Phone <b>{phone}</b> saved!\n\nHere's your dashboard 👇",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove(),
    )
    await message.answer("🏠 <b>Main Menu</b>", parse_mode="HTML", reply_markup=main_menu())


# ---------------------------------------------------------------------------
# Phone typed manually
# ---------------------------------------------------------------------------
@router.message(RegStates.waiting_for_phone, F.text)
async def receive_phone_text(message: Message, state: FSMContext) -> None:
    phone = message.text.strip()
    if not validate_nigerian_phone(phone):
        await message.answer(
            "❌ Invalid phone number. Please enter a valid Nigerian number (e.g. 08012345678)."
        )
        return
    phone = normalise_phone(phone)
    await repository.update_user_phone(message.from_user.id, phone)
    await state.clear()
    await message.answer(
        f"✅ Phone <b>{phone}</b> saved!",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove(),
    )
    await message.answer("🏠 <b>Main Menu</b>", parse_mode="HTML", reply_markup=main_menu())


# ---------------------------------------------------------------------------
# Skip phone
# ---------------------------------------------------------------------------
@router.message(RegStates.waiting_for_phone)
async def skip_phone(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "⚠️ Phone skipped. You can add it later via settings.\nYou won't be able to redeem without a phone number.",
        reply_markup=ReplyKeyboardRemove(),
    )
    await message.answer("🏠 <b>Main Menu</b>", parse_mode="HTML", reply_markup=main_menu())


# ---------------------------------------------------------------------------
# Main menu callback (back button)
# ---------------------------------------------------------------------------
@router.callback_query(F.data == "main_menu")
async def cb_main_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(
        "🏠 <b>Main Menu</b>", parse_mode="HTML", reply_markup=main_menu()
    )
    await callback.answer()
