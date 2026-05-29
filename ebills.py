import hashlib
import hmac
import uuid
from typing import Optional

import aiohttp

from config.settings import settings

_token: Optional[str] = None


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
async def _get_token(session: aiohttp.ClientSession) -> str:
    global _token
    if _token:
        return _token
    async with session.post(
        settings.EBILLS_AUTH_URL,
        json={
            "username": settings.EBILLS_USERNAME,
            "password": settings.EBILLS_PASSWORD,
        },
    ) as resp:
        data = await resp.json()
        _token = data["token"]
        return _token


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _new_request_id(prefix: str) -> str:
    return f"rwd_{prefix}_{uuid.uuid4().hex[:10]}"


# ---------------------------------------------------------------------------
# Wallet balance
# ---------------------------------------------------------------------------
async def get_balance() -> dict:
    async with aiohttp.ClientSession() as session:
        token = await _get_token(session)
        async with session.get(
            f"{settings.EBILLS_BASE_URL}/balance", headers=_headers(token)
        ) as resp:
            return await resp.json()


# ---------------------------------------------------------------------------
# Data variations
# ---------------------------------------------------------------------------
async def get_data_plans(network: str) -> list:
    """Return list of data plans for a network (mtn, airtel, glo, 9mobile)."""
    async with aiohttp.ClientSession() as session:
        token = await _get_token(session)
        async with session.get(
            f"{settings.EBILLS_BASE_URL}/variations/data",
            headers=_headers(token),
            params={"service_id": network},
        ) as resp:
            data = await resp.json()
            return data if isinstance(data, list) else data.get("variations", [])


# ---------------------------------------------------------------------------
# Airtime VTU
# ---------------------------------------------------------------------------
async def purchase_airtime(
    phone: str, network: str, amount: int, redemption_id: int
) -> dict:
    request_id = _new_request_id(str(redemption_id))
    async with aiohttp.ClientSession() as session:
        token = await _get_token(session)
        async with session.post(
            f"{settings.EBILLS_BASE_URL}/airtime",
            headers=_headers(token),
            json={
                "request_id": request_id,
                "phone": phone,
                "service_id": network,
                "amount": amount,
            },
        ) as resp:
            result = await resp.json()
            result["_request_id"] = request_id
            return result


# ---------------------------------------------------------------------------
# Data bundle
# ---------------------------------------------------------------------------
async def purchase_data(
    phone: str, network: str, variation_id: str, redemption_id: int
) -> dict:
    request_id = _new_request_id(str(redemption_id))
    async with aiohttp.ClientSession() as session:
        token = await _get_token(session)
        async with session.post(
            f"{settings.EBILLS_BASE_URL}/data",
            headers=_headers(token),
            json={
                "request_id": request_id,
                "phone": phone,
                "service_id": network,
                "variation_id": variation_id,
            },
        ) as resp:
            result = await resp.json()
            result["_request_id"] = request_id
            return result


# ---------------------------------------------------------------------------
# Requery (check order status)
# ---------------------------------------------------------------------------
async def requery_order(request_id: str) -> dict:
    async with aiohttp.ClientSession() as session:
        token = await _get_token(session)
        async with session.post(
            f"{settings.EBILLS_BASE_URL}/requery",
            headers=_headers(token),
            json={"request_id": request_id},
        ) as resp:
            return await resp.json()


# ---------------------------------------------------------------------------
# Webhook signature verification
# ---------------------------------------------------------------------------
def verify_webhook_signature(payload: bytes, provided_sig: str) -> bool:
    expected = hmac.new(
        settings.EBILLS_USER_PIN.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, provided_sig)
