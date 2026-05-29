from aiogram import Router, F
from aiogram.types import Message, CallbackQuery

from db import repository
from bot.keyboards.inline import main_menu, back_to_main
from bot.utils.helpers import format_points, fmt_datetime, tx_emoji

router = Router()


def _require_user(db_user, callback_or_message):
    return db_user is not None


# ---------------------------------------------------------------------------
# My Points
# ---------------------------------------------------------------------------
@router.callback_query(F.data == "my_points")
async def cb_my_points(callback: CallbackQuery, db_user) -> None:
    if not db_user:
        await callback.answer("Please /start first.", show_alert=True)
        return
    text = (
        f"💰 <b>Your Points</b>\n\n"
        f"Current Balance:  <b>{format_points(db_user.points_balance)}</b>\n"
        f"Total Earned:     <b>{format_points(db_user.total_earned)}</b>\n"
        f"Total Redeemed:   <b>{format_points(db_user.total_redeemed)}</b>\n\n"
        f"Member since: {fmt_datetime(db_user.registered_at)}"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=back_to_main())
    await callback.answer()


# ---------------------------------------------------------------------------
# Leaderboard
# ---------------------------------------------------------------------------
@router.callback_query(F.data == "leaderboard")
async def cb_leaderboard(callback: CallbackQuery) -> None:
    rows = await repository.get_leaderboard(limit=10)
    if not rows:
        await callback.answer("No data yet.", show_alert=True)
        return

    lines = ["🏆 <b>Top 10 — All-Time Earners</b>\n"]
    medals = ["🥇", "🥈", "🥉"]
    for i, row in enumerate(rows):
        medal = medals[i] if i < 3 else f"{i + 1}."
        name = row["first_name"]
        if row["username"]:
            name = f"@{row['username']}"
        lines.append(f"{medal} {name} — {format_points(row['total_earned'])}")

    await callback.message.edit_text(
        "\n".join(lines), parse_mode="HTML", reply_markup=back_to_main()
    )
    await callback.answer()


# ---------------------------------------------------------------------------
# Transaction history
# ---------------------------------------------------------------------------
@router.callback_query(F.data == "tx_history")
async def cb_tx_history(callback: CallbackQuery, db_user) -> None:
    if not db_user:
        await callback.answer("Please /start first.", show_alert=True)
        return

    txs = await repository.get_transaction_history(db_user.user_id, limit=10)
    if not txs:
        await callback.message.edit_text(
            "📋 No transactions yet.", reply_markup=back_to_main()
        )
        await callback.answer()
        return

    lines = ["📋 <b>Last 10 Transactions</b>\n"]
    for tx in txs:
        sign = "+" if tx["amount"] > 0 else ""
        emoji = tx_emoji(tx["type"])
        lines.append(
            f"{emoji} {sign}{tx['amount']:,} pts — {tx['description'] or tx['type']}\n"
            f"   <i>{fmt_datetime(tx['created_at'])}</i>"
        )

    await callback.message.edit_text(
        "\n".join(lines), parse_mode="HTML", reply_markup=back_to_main()
    )
    await callback.answer()
