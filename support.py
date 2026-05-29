from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

from config.settings import settings
from db import repository
from bot.keyboards.inline import back_to_main, admin_resolve_ticket
from bot.utils.helpers import format_points

router = Router()


class SupportStates(StatesGroup):
    waiting_for_message = State()


# ---------------------------------------------------------------------------
# Support menu entry
# ---------------------------------------------------------------------------
@router.callback_query(F.data == "support_menu")
async def cb_support_menu(callback: CallbackQuery, state: FSMContext, db_user) -> None:
    if not db_user:
        await callback.answer("Please /start first.", show_alert=True)
        return

    await callback.message.edit_text(
        "🎫 <b>Support</b>\n\n"
        "Describe your issue or question. Our admins will respond as soon as possible.\n\n"
        f"✨ You earn <b>{settings.POINTS_SUPPORT_TICKET} pts</b> just for submitting a ticket!",
        parse_mode="HTML",
        reply_markup=back_to_main(),
    )
    await state.set_state(SupportStates.waiting_for_message)
    await callback.answer()


# ---------------------------------------------------------------------------
# Receive ticket message
# ---------------------------------------------------------------------------
@router.message(SupportStates.waiting_for_message, F.text)
async def receive_ticket(message: Message, state: FSMContext, db_user, bot: Bot) -> None:
    if not db_user:
        await message.answer("Please /start first.")
        await state.clear()
        return

    # Create ticket
    ticket = await repository.create_ticket(message.from_user.id, message.text)

    # Award points
    new_balance = await repository.award_points(
        user_id=message.from_user.id,
        amount=settings.POINTS_SUPPORT_TICKET,
        tx_type="earned_support",
        description=f"Support ticket #{ticket.id} opened",
        related_id=str(ticket.id),
    )

    await message.answer(
        f"✅ <b>Ticket #{ticket.id} submitted!</b>\n\n"
        f"You earned <b>{format_points(settings.POINTS_SUPPORT_TICKET)}</b>.\n"
        f"New balance: <b>{format_points(new_balance)}</b>\n\n"
        "An admin will respond to you shortly.",
        parse_mode="HTML",
        reply_markup=back_to_main(),
    )
    await state.clear()

    # Notify all admins
    tg = message.from_user
    name = f"@{tg.username}" if tg.username else tg.first_name
    preview = message.text[:400]
    admin_text = (
        f"🎫 <b>New Support Ticket #{ticket.id}</b>\n\n"
        f"From: {name} (ID: <code>{tg.id}</code>)\n\n"
        f"<b>Message:</b>\n{preview}"
    )
    for admin_id in settings.admin_ids_list:
        try:
            await bot.send_message(
                admin_id,
                admin_text,
                parse_mode="HTML",
                reply_markup=admin_resolve_ticket(ticket.id),
            )
        except Exception:
            pass  # Admin may not have started the bot
