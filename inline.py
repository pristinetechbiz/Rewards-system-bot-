from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="💰 My Points", callback_data="my_points"),
        InlineKeyboardButton(text="🏆 Leaderboard", callback_data="leaderboard"),
    )
    builder.row(
        InlineKeyboardButton(text="🎁 Redeem", callback_data="redeem_menu"),
        InlineKeyboardButton(text="🎫 Support", callback_data="support_menu"),
    )
    builder.row(
        InlineKeyboardButton(text="📋 History", callback_data="tx_history"),
    )
    return builder.as_markup()


def redeem_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📞 Airtime", callback_data="redeem_airtime"),
        InlineKeyboardButton(text="📶 Data Bundle", callback_data="redeem_data"),
    )
    builder.row(
        InlineKeyboardButton(text="⬅️ Back", callback_data="main_menu"),
    )
    return builder.as_markup()


def network_keyboard(callback_prefix: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    networks = [("MTN", "mtn"), ("Airtel", "airtel"), ("Glo", "glo"), ("9mobile", "9mobile")]
    for label, code in networks:
        builder.button(text=label, callback_data=f"{callback_prefix}:{code}")
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="⬅️ Back", callback_data="redeem_menu"))
    return builder.as_markup()


def confirm_keyboard(confirm_data: str, cancel_data: str = "redeem_menu") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Confirm", callback_data=confirm_data),
        InlineKeyboardButton(text="❌ Cancel", callback_data=cancel_data),
    )
    return builder.as_markup()


def data_plans_keyboard(plans: list, network: str) -> InlineKeyboardMarkup:
    """Render a list of data plans as buttons. Max 10 shown."""
    builder = InlineKeyboardBuilder()
    for plan in plans[:10]:
        variation_id = plan.get("variation_id", "")
        name = plan.get("name", variation_id)
        amount = plan.get("variation_amount", "?")
        builder.button(
            text=f"{name} — ₦{amount}",
            callback_data=f"data_plan:{network}:{variation_id}:{amount}",
        )
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="⬅️ Back", callback_data="redeem_data"))
    return builder.as_markup()


def admin_resolve_ticket(ticket_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✅ Resolve Ticket",
        callback_data=f"admin_resolve:{ticket_id}",
    )
    return builder.as_markup()


def back_to_main() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Main Menu", callback_data="main_menu")
    return builder.as_markup()


def share_phone_keyboard() -> InlineKeyboardMarkup:
    from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
    # Handled separately as a ReplyKeyboard — returned here for convenience
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Share My Phone Number", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
