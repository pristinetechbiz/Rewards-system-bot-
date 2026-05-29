from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

from config.settings import settings
from db import repository
from bot.middlewares.auth import AdminMiddleware
from bot.utils.helpers import format_points

router = Router()
router.message.middleware(AdminMiddleware())
router.callback_query.middleware(AdminMiddleware())


# ---------------------------------------------------------------------------
# /admin — help panel
# ---------------------------------------------------------------------------
@router.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    await message.answer(
        "🔧 <b>Admin Panel</b>\n\n"
        "/award_points {user_id} {amount} {reason}\n"
        "   — Directly award bonus points\n\n"
        "/resolve_ticket {ticket_id} {points}\n"
        "   — Resolve a support ticket and award points\n\n"
        "/verify_contribution {user_id} {score 1-10} {description}\n"
        "   — Verify a contribution (score × 10 = points)\n\n"
        "/stats — System statistics\n\n"
        "/ebills_balance — Check eBills wallet balance",
        parse_mode="HTML",
    )


# ---------------------------------------------------------------------------
# /award_points
# ---------------------------------------------------------------------------
@router.message(Command("award_points"))
async def cmd_award_points(message: Message, bot: Bot) -> None:
    parts = message.text.split(None, 3)
    if len(parts) < 4:
        await message.answer(
            "Usage: /award_points {user_id} {amount} {reason}\n"
            "Example: /award_points 123456789 500 Contest winner"
        )
        return

    try:
        user_id = int(parts[1])
        amount = int(parts[2])
        reason = parts[3]
    except ValueError:
        await message.answer("❌ user_id and amount must be numbers.")
        return

    if amount <= 0:
        await message.answer("❌ Amount must be positive.")
        return

    user = await repository.get_user(user_id)
    if not user:
        await message.answer(f"❌ User {user_id} not found.")
        return

    new_balance = await repository.award_points(
        user_id=user_id,
        amount=amount,
        tx_type="earned_admin_bonus",
        description=reason,
        related_id=str(message.from_user.id),
    )

    await message.answer(
        f"✅ Awarded <b>{format_points(amount)}</b> to {user.first_name} (ID: {user_id})\n"
        f"Reason: {reason}\nNew balance: <b>{format_points(new_balance)}</b>",
        parse_mode="HTML",
    )

    # Notify user
    try:
        await bot.send_message(
            user_id,
            f"⭐ You've been awarded <b>{format_points(amount)}</b>!\n"
            f"Reason: {reason}\nNew balance: <b>{format_points(new_balance)}</b>",
            parse_mode="HTML",
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# /resolve_ticket
# ---------------------------------------------------------------------------
@router.message(Command("resolve_ticket"))
async def cmd_resolve_ticket(message: Message, bot: Bot) -> None:
    parts = message.text.split()
    if len(parts) < 3:
        await message.answer("Usage: /resolve_ticket {ticket_id} {points}")
        return

    try:
        ticket_id = int(parts[1])
        bonus_points = int(parts[2])
    except ValueError:
        await message.answer("❌ ticket_id and points must be numbers.")
        return

    ticket = await repository.get_ticket(ticket_id)
    if not ticket:
        await message.answer(f"❌ Ticket #{ticket_id} not found.")
        return
    if ticket.status == "resolved":
        await message.answer(f"⚠️ Ticket #{ticket_id} is already resolved.")
        return

    await repository.resolve_ticket(ticket_id, bonus_points)

    if bonus_points > 0:
        new_balance = await repository.award_points(
            user_id=ticket.user_id,
            amount=bonus_points,
            tx_type="earned_support",
            description=f"Support ticket #{ticket_id} resolved",
            related_id=str(ticket_id),
        )
        notify_text = (
            f"🎫 Your support ticket <b>#{ticket_id}</b> has been resolved!\n"
            f"You earned <b>{format_points(bonus_points)}</b>.\n"
            f"New balance: <b>{format_points(new_balance)}</b>"
        )
    else:
        notify_text = f"🎫 Your support ticket <b>#{ticket_id}</b> has been resolved!"

    await message.answer(
        f"✅ Ticket #{ticket_id} resolved. Awarded {format_points(bonus_points)} to user {ticket.user_id}."
    )

    try:
        await bot.send_message(ticket.user_id, notify_text, parse_mode="HTML")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Resolve ticket via inline button (callback)
# ---------------------------------------------------------------------------
class ResolveTicketStates(StatesGroup):
    waiting_for_points = State()


@router.callback_query(F.data.startswith("admin_resolve:"))
async def cb_admin_resolve(callback: CallbackQuery, state: FSMContext) -> None:
    ticket_id = int(callback.data.split(":")[1])
    await state.update_data(resolving_ticket_id=ticket_id)
    await callback.message.answer(
        f"Enter bonus points to award for Ticket #{ticket_id} (0 for none):"
    )
    await state.set_state(ResolveTicketStates.waiting_for_points)
    await callback.answer()


@router.message(ResolveTicketStates.waiting_for_points, F.text)
async def inline_resolve_points(message: Message, state: FSMContext, bot: Bot) -> None:
    try:
        bonus_points = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Please enter a valid number.")
        return

    data = await state.get_data()
    ticket_id = data.get("resolving_ticket_id")
    await state.clear()

    ticket = await repository.get_ticket(ticket_id)
    if not ticket or ticket.status == "resolved":
        await message.answer(f"⚠️ Ticket #{ticket_id} not found or already resolved.")
        return

    await repository.resolve_ticket(ticket_id, bonus_points)

    if bonus_points > 0:
        new_balance = await repository.award_points(
            user_id=ticket.user_id,
            amount=bonus_points,
            tx_type="earned_support",
            description=f"Support ticket #{ticket_id} resolved",
            related_id=str(ticket_id),
        )
        user_msg = (
            f"🎫 Your support ticket <b>#{ticket_id}</b> has been resolved!\n"
            f"You earned <b>{format_points(bonus_points)}</b>.\n"
            f"New balance: <b>{format_points(new_balance)}</b>"
        )
    else:
        user_msg = f"🎫 Your support ticket <b>#{ticket_id}</b> has been resolved."

    await message.answer(f"✅ Ticket #{ticket_id} resolved. {format_points(bonus_points)} awarded.")

    try:
        await bot.send_message(ticket.user_id, user_msg, parse_mode="HTML")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# /verify_contribution
# ---------------------------------------------------------------------------
@router.message(Command("verify_contribution"))
async def cmd_verify_contribution(message: Message, bot: Bot) -> None:
    parts = message.text.split(None, 3)
    if len(parts) < 4:
        await message.answer(
            'Usage: /verify_contribution {user_id} {score 1-10} {description}\n'
            'Example: /verify_contribution 123456789 5 "Helped 5 new members"'
        )
        return

    try:
        user_id = int(parts[1])
        score = int(parts[2])
        description = parts[3].strip('"').strip("'")
    except ValueError:
        await message.answer("❌ user_id must be a number and score must be 1-10.")
        return

    if not 1 <= score <= 10:
        await message.answer("❌ Value score must be between 1 and 10.")
        return

    user = await repository.get_user(user_id)
    if not user:
        await message.answer(f"❌ User {user_id} not found.")
        return

    points_earned = score * settings.POINTS_CONTRIBUTION_BASE

    contribution = await repository.create_contribution(
        user_id=user_id,
        description=description,
        value_score=score,
        points_earned=points_earned,
        verified_by=message.from_user.id,
    )
    new_balance = await repository.award_points(
        user_id=user_id,
        amount=points_earned,
        tx_type="earned_contribution",
        description=description,
        related_id=str(contribution.id),
    )

    await message.answer(
        f"✅ Contribution verified!\n"
        f"User: {user.first_name} (ID: {user_id})\n"
        f"Score: {score}/10 → <b>{format_points(points_earned)}</b>\n"
        f"Description: {description}\n"
        f"New balance: <b>{format_points(new_balance)}</b>",
        parse_mode="HTML",
    )

    try:
        await bot.send_message(
            user_id,
            f"🤝 Your contribution has been verified!\n\n"
            f"<b>{description}</b>\n\n"
            f"You earned <b>{format_points(points_earned)}</b> (score {score}/10).\n"
            f"New balance: <b>{format_points(new_balance)}</b>",
            parse_mode="HTML",
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# /stats
# ---------------------------------------------------------------------------
@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    stats = await repository.get_stats()
    open_tickets = await repository.get_open_tickets()

    await message.answer(
        f"📊 <b>System Statistics</b>\n\n"
        f"👥 Total Users:           <b>{stats['total_users']:,}</b>\n"
        f"💰 Points in Circulation: <b>{stats['points_in_circulation']:,}</b>\n"
        f"📈 Total Points Ever Earned: <b>{stats['total_earned']:,}</b>\n"
        f"🎁 Total Points Redeemed: <b>{stats['total_redeemed']:,}</b>\n"
        f"🎫 Open Support Tickets:  <b>{len(open_tickets)}</b>",
        parse_mode="HTML",
    )


# ---------------------------------------------------------------------------
# /ebills_balance
# ---------------------------------------------------------------------------
@router.message(Command("ebills_balance"))
async def cmd_ebills_balance(message: Message) -> None:
    try:
        from bot.utils.ebills import get_balance
        data = await get_balance()
        balance = data.get("balance", "N/A")
        await message.answer(
            f"💳 <b>eBills Wallet Balance</b>\n\n₦{balance:,}" if isinstance(balance, (int, float))
            else f"💳 Balance: {balance}",
            parse_mode="HTML",
        )
    except Exception as e:
        await message.answer(f"❌ Could not fetch balance: {e}")
