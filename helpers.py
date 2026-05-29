import re
from datetime import datetime


NIGERIAN_PHONE_RE = re.compile(r"^(0|\+234)(7|8|9)\d{9}$")


def validate_nigerian_phone(phone: str) -> bool:
    return bool(NIGERIAN_PHONE_RE.match(phone.strip()))


def normalise_phone(phone: str) -> str:
    """Convert 0803... to 0803... (keep local format for VTU APIs)."""
    phone = phone.strip().replace(" ", "").replace("-", "")
    if phone.startswith("+234"):
        phone = "0" + phone[4:]
    return phone


def format_points(points: int) -> str:
    return f"{points:,} pts"


def format_naira(amount: int) -> str:
    return f"₦{amount:,}"


def detect_network(phone: str) -> str | None:
    """Guess Nigerian network from phone prefix."""
    phone = normalise_phone(phone)
    mtn = {"0803", "0806", "0813", "0816", "0810", "0814", "0903", "0906", "0913"}
    airtel = {"0802", "0808", "0812", "0701", "0708", "0902", "0901", "0904", "0907"}
    glo = {"0805", "0807", "0815", "0811", "0905", "0915"}
    nine_mobile = {"0809", "0818", "0817", "0819", "0909", "0908"}
    prefix = phone[:4]
    if prefix in mtn:
        return "mtn"
    if prefix in airtel:
        return "airtel"
    if prefix in glo:
        return "glo"
    if prefix in nine_mobile:
        return "9mobile"
    return None


def tx_emoji(tx_type: str) -> str:
    mapping = {
        "earned_registration": "🎉",
        "earned_support": "🎫",
        "earned_contribution": "🤝",
        "earned_admin_bonus": "⭐",
        "redeemed_airtime": "📞",
        "redeemed_data": "📶",
        "refunded": "↩️",
    }
    return mapping.get(tx_type, "💰")


def fmt_datetime(dt: datetime) -> str:
    return dt.strftime("%d %b %Y %H:%M")
