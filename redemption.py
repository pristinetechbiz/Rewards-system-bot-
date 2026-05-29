from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

from config.settings import settings
from db import repository
from bot.keyboards.inline import (
    redeem_menu, network_keyboard, data_plans_keyboard,
    confirm_keyboard, back_to_main,
)
from bot.utils import ebills
from bot.utils.helpers import (
    validate_nigerian_phone, normalise_phone,
    format_points, format_naira,
)

router = Router()


# ---------------------------------------------------------------------------
# FSM States
# ---------------------------------------------------------------------------
class AirtimeStates(StatesGroup):
    selecting_network = State()
    entering_amount = State()
    entering_phone = State()
    confirming = State()


class DataStates(StatesGroup):
    selecting_network = State()
    selecting_plan = State()
    entering_phone = State()
    confirming = State()


# ===========================================================================
# REDEEM MENU
# ===========================================================================
@router.callback_query(F.data == "redeem_menu")
async def cb_redeem_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(
        "🎁 <b>Redeem Points</b>\n\nChoose what you'd like:",
        parse_mode="HTML",
        reply_markup=redeem_menu(),
    )
    await callback.answer()


# ===========================================================================
# AIRTIME FLOW
# ===========================================================================
@router.callback_query(F.data == "redeem_airtime")
async def cb_airtime_start(callback: CallbackQuery, state: FSMContext, db_user) -> None:
    if not db_user:
        await callback.answer("Please /start first.", show_alert=True)
        return
    if not db_user.phone:
        await callback.answer(
            "⚠️ You need to save a phone number first. Send /start and share your contact.",
            show_alert=True,
        )
        return

    await callback.message.edit_text(
        f"📞 <b>Airtime Redemption</b>\n\n"
        f"Rate: <b>10 pts = ₦1</b>\nMinimum: ₦50 (500 pts)\n\nSelect your network:",
        parse_mode="HTML",
        reply_markup=network_keyboard("airtime_net"),
    )
    await state.set_state(AirtimeStates.selecting_network)
    await callback.answer()


@router.callback_query(AirtimeStates.selecting_network, F.data.startswith("airtime_net:"))
async def cb_airtime_network(callback: CallbackQuery, state: FSMContext) -> None:
    network = callback.data.split(":")[1]
    await state.update_data(network=network)
    await callback.message.edit_text(
        f"📞 Network: <b>{network.upper()}</b>\n\n"
        "Enter airtime amount in NGN (minimum ₦50):",
        parse_mode="HTML",
        reply_markup=back_to_main(),
    )
    await state.set_state(AirtimeStates.entering_amount)
    await callback.answer()


@router.message(AirtimeStates.entering_amount, F.text)
async def airtime_amount(message: Message, state: FSMContext, db_user) -> None:
    try:
        amount = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Please enter a valid number (e.g. 200).")
        return

    if amount < 50:
        await message.answer("❌ Minimum airtime is ₦50.")
        return

    points_cost = amount * settings.AIRTIME_RATE
    if db_user.points_balance < points_cost:
        await message.answer(
            f"❌ Insufficient points.\n"
            f"You need <b>{format_points(points_cost)}</b> but have <b>{format_points(db_user.points_balance)}</b>.",
            parse_mode="HTML",
        )
        return

    await state.update_data(amount_ngn=amount, points_cost=points_cost)
    await message.answer(
        f"📱 Enter the phone number to top up\n"
        f"(or press Enter to use your saved number: {db_user.phone}):"
    )
    await state.set_state(AirtimeStates.entering_phone)


@router.message(AirtimeStates.entering_phone, F.text)
async def airtime_phone(message: Message, state: FSMContext, db_user) -> None:
    text = message.text.strip()
    # Allow user to press "." or "skip" to use saved number
    if text.lower() in (".", "skip", "-") and db_user.phone:
        phone = db_user.phone
    elif validate_nigerian_phone(text):
        phone = normalise_phone(text)
    else:
        await message.answer("❌ Invalid phone. Enter a valid Nigerian number or '.' to use your saved number.")
        return

    data = await state.get_data()
    await state.update_data(phone=phone)
    await message.answer(
        f"📞 <b>Confirm Airtime Top-Up</b>\n\n"
        f"Network:  <b>{data['network'].upper()}</b>\n"
        f"Amount:   <b>{format_naira(data['amount_ngn'])}</b>\n"
        f"Phone:    <b>{phone}</b>\n"
        f"Cost:     <b>{format_points(data['points_cost'])}</b>\n\n"
        "Proceed?",
        parse_mode="HTML",
        reply_markup=confirm_keyboard("airtime_confirm"),
    )
    await state.set_state(AirtimeStates.confirming)


@router.callback_query(AirtimeStates.confirming, F.data == "airtime_confirm")
async def airtime_confirm(callback: CallbackQuery, state: FSMContext, db_user, bot: Bot) -> None:
    data = await state.get_data()
    await state.clear()

    await callback.message.edit_text("⏳ Processing your airtime... please wait.")
    await callback.answer()

    # Deduct points and create redemption record
    redemption = await repository.begin_redemption(
        user_id=db_user.user_id,
        rtype="airtime",
        phone=data["phone"],
        network=data["network"],
        amount_ngn=data["amount_ngn"],
        points_cost=data["points_cost"],
        request_id=f"rwd_{db_user.user_id}_{data['network']}",
    )

    if not redemption:
        await callback.message.edit_text(
            "❌ Insufficient points. Please try a smaller amount.",
            reply_markup=back_to_main(),
        )
        return

    # Call eBills API
    try:
        result = await ebills.purchase_airtime(
            phone=data["phone"],
            network=data["network"],
            amount=data["amount_ngn"],
            redemption_id=redemption.id,
        )
        success = result.get("status") in ("success", "delivered", "successful", True)
    except Exception as e:
        success = False
        result = {"error": str(e)}

    if success:
        await repository.complete_redemption(
            redemption.id, ebills_order_id=result.get("order_id")
        )
        await callback.message.edit_text(
            f"✅ <b>Airtime Delivered!</b>\n\n"
            f"₦{data['amount_ngn']} sent to <b>{data['phone']}</b>\n"
            f"Remaining balance: <b>{format_points(db_user.points_balance - data['points_cost'])}</b>",
            parse_mode="HTML",
            reply_markup=back_to_main(),
        )
    else:
        await repository.fail_and_refund_redemption(
            redemption.id, db_user.user_id, data["points_cost"]
        )
        await callback.message.edit_text(
            f"❌ <b>Delivery failed.</b>\n\n"
            f"Your <b>{format_points(data['points_cost'])}</b> have been refunded.\n"
            f"Please try again later.",
            parse_mode="HTML",
            reply_markup=back_to_main(),
        )


# ===========================================================================
# DATA BUNDLE FLOW
# ===========================================================================
@router.callback_query(F.data == "redeem_data")
async def cb_data_start(callback: CallbackQuery, state: FSMContext, db_user) -> None:
    if not db_user:
        await callback.answer("Please /start first.", show_alert=True)
        return
    if not db_user.phone:
        await callback.answer(
            "⚠️ You need to save a phone number first. Send /start and share your contact.",
            show_alert=True,
        )
        return

    await callback.message.edit_text(
        "📶 <b>Data Bundle Redemption</b>\n\n"
        "Rate: <b>8 pts = ₦1 value</b>\n\nSelect your network:",
        parse_mode="HTML",
        reply_markup=network_keyboard("data_net"),
    )
    await state.set_state(DataStates.selecting_network)
    await callback.answer()


@router.callback_query(DataStates.selecting_network, F.data.startswith("data_net:"))
async def cb_data_network(callback: CallbackQuery, state: FSMContext) -> None:
    network = callback.data.split(":")[1]
    await state.update_data(network=network)

    await callback.message.edit_text(f"⏳ Fetching {network.upper()} data plans...")
    await callback.answer()

    try:
        plans = await ebills.get_data_plans(network)
    except Exception:
        plans = []

    if not plans:
        await callback.message.edit_text(
            f"❌ Could not load {network.upper()} plans. Try again later.",
            reply_markup=back_to_main(),
        )
        return

    await state.update_data(plans=plans)
    await callback.message.edit_text(
        f"📶 <b>{network.upper()} Data Plans</b>\n\nSelect a plan:",
        parse_mode="HTML",
        reply_markup=data_plans_keyboard(plans, network),
    )
    await state.set_state(DataStates.selecting_plan)


@router.callback_query(DataStates.selecting_plan, F.data.startswith("data_plan:"))
async def cb_data_plan(callback: CallbackQuery, state: FSMContext, db_user) -> None:
    # data_plan:{network}:{variation_id}:{amount}
    parts = callback.data.split(":")
    network = parts[1]
    variation_id = parts[2]
    try:
        amount_ngn = int(float(parts[3]))
    except (ValueError, IndexError):
        await callback.answer("❌ Invalid plan.", show_alert=True)
        return

    points_cost = amount_ngn * settings.DATA_RATE

    if db_user.points_balance < points_cost:
        await callback.answer(
            f"❌ Need {format_points(points_cost)}, you have {format_points(db_user.points_balance)}.",
            show_alert=True,
        )
        return

    await state.update_data(
        variation_id=variation_id,
        amount_ngn=amount_ngn,
        points_cost=points_cost,
    )
    await callback.message.edit_text(
        f"📱 Enter the phone number to receive data\n"
        f"(or '.' to use your saved number: {db_user.phone}):"
    )
    await state.set_state(DataStates.entering_phone)
    await callback.answer()


@router.message(DataStates.entering_phone, F.text)
async def data_phone(message: Message, state: FSMContext, db_user) -> None:
    text = message.text.strip()
    if text.lower() in (".", "skip", "-") and db_user.phone:
        phone = db_user.phone
    elif validate_nigerian_phone(text):
        phone = normalise_phone(text)
    else:
        await message.answer("❌ Invalid phone. Enter a valid Nigerian number or '.' to use saved.")
        return

    data = await state.get_data()
    await state.update_data(phone=phone)

    await message.answer(
        f"📶 <b>Confirm Data Bundle</b>\n\n"
        f"Network:    <b>{data['network'].upper()}</b>\n"
        f"Plan ID:    <b>{data['variation_id']}</b>\n"
        f"Value:      <b>{format_naira(data['amount_ngn'])}</b>\n"
        f"Phone:      <b>{phone}</b>\n"
        f"Cost:       <b>{format_points(data['points_cost'])}</b>\n\n"
        "Proceed?",
        parse_mode="HTML",
        reply_markup=confirm_keyboard("data_confirm"),
    )
    await state.set_state(DataStates.confirming)


@router.callback_query(DataStates.confirming, F.data == "data_confirm")
async def data_confirm(callback: CallbackQuery, state: FSMContext, db_user, bot: Bot) -> None:
    data = await state.get_data()
    await state.clear()

    await callback.message.edit_text("⏳ Processing your data bundle... please wait.")
    await callback.answer()

    redemption = await repository.begin_redemption(
        user_id=db_user.user_id,
        rtype="data",
        phone=data["phone"],
        network=data["network"],
        amount_ngn=data["amount_ngn"],
        points_cost=data["points_cost"],
        request_id=f"rwd_{db_user.user_id}_data",
        variation_id=data["variation_id"],
    )

    if not redemption:
        await callback.message.edit_text(
            "❌ Insufficient points.", reply_markup=back_to_main()
        )
        return

    try:
        result = await ebills.purchase_data(
            phone=data["phone"],
            network=data["network"],
            variation_id=data["variation_id"],
            redemption_id=redemption.id,
        )
        success = result.get("status") in ("success", "delivered", "successful", True)
    except Exception as e:
        success = False
        result = {"error": str(e)}

    if success:
        await repository.complete_redemption(
            redemption.id, ebills_order_id=result.get("order_id")
        )
        await callback.message.edit_text(
            f"✅ <b>Data Bundle Delivered!</b>\n\n"
            f"Sent to <b>{data['phone']}</b>\n"
            f"Remaining balance: <b>{format_points(db_user.points_balance - data['points_cost'])}</b>",
            parse_mode="HTML",
            reply_markup=back_to_main(),
        )
    else:
        await repository.fail_and_refund_redemption(
            redemption.id, db_user.user_id, data["points_cost"]
        )
        await callback.message.edit_text(
            f"❌ <b>Delivery failed.</b>\n\n"
            f"Your <b>{format_points(data['points_cost'])}</b> have been refunded.",
            parse_mode="HTML",
            reply_markup=back_to_main(),
        )
