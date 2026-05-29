import asyncpg
from typing import Optional, List
from datetime import datetime
from .models import User, PointsTransaction, SupportTicket, Contribution, Redemption


# ---------------------------------------------------------------------------
# Pool holder — set once at startup from bot/main.py
# ---------------------------------------------------------------------------
_pool: Optional[asyncpg.Pool] = None


async def create_pool(dsn: str) -> asyncpg.Pool:
    global _pool
    _pool = await asyncpg.create_pool(dsn, min_size=5, max_size=20)
    return _pool


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("DB pool not initialised — call create_pool() first")
    return _pool


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------
async def get_user(user_id: int) -> Optional[User]:
    row = await get_pool().fetchrow(
        "SELECT * FROM users WHERE user_id = $1", user_id
    )
    return User(**dict(row)) if row else None


async def create_user(
    user_id: int,
    username: Optional[str],
    first_name: str,
    last_name: Optional[str],
    registration_points: int,
) -> User:
    """
    Insert a new user and credit registration points atomically.
    Returns the created User. If the user already exists, returns existing.
    """
    async with get_pool().acquire() as conn:
        async with conn.transaction():
            existing = await conn.fetchrow(
                "SELECT * FROM users WHERE user_id = $1", user_id
            )
            if existing:
                return User(**dict(existing))

            row = await conn.fetchrow(
                """
                INSERT INTO users (user_id, username, first_name, last_name,
                                   points_balance, total_earned)
                VALUES ($1, $2, $3, $4, $5, $5)
                RETURNING *
                """,
                user_id, username, first_name, last_name, registration_points,
            )
            await conn.execute(
                """
                INSERT INTO points_transactions (user_id, type, amount, description)
                VALUES ($1, 'earned_registration', $2, 'Welcome bonus')
                """,
                user_id, registration_points,
            )
            return User(**dict(row))


async def update_user_phone(user_id: int, phone: str) -> None:
    await get_pool().execute(
        "UPDATE users SET phone = $1 WHERE user_id = $2", phone, user_id
    )


async def update_last_active(user_id: int) -> None:
    await get_pool().execute(
        "UPDATE users SET last_active = NOW() WHERE user_id = $1", user_id
    )


async def get_leaderboard(limit: int = 10) -> List[dict]:
    rows = await get_pool().fetch(
        """
        SELECT user_id, username, first_name, total_earned
        FROM users
        WHERE status = 'active'
        ORDER BY total_earned DESC
        LIMIT $1
        """,
        limit,
    )
    return [dict(r) for r in rows]


async def get_stats() -> dict:
    row = await get_pool().fetchrow(
        """
        SELECT
            COUNT(*)                       AS total_users,
            COALESCE(SUM(total_earned), 0) AS total_earned,
            COALESCE(SUM(total_redeemed),0)AS total_redeemed,
            COALESCE(SUM(points_balance),0)AS points_in_circulation
        FROM users
        """
    )
    return dict(row)


async def suspend_user(user_id: int) -> None:
    await get_pool().execute(
        "UPDATE users SET status = 'suspended' WHERE user_id = $1", user_id
    )


# ---------------------------------------------------------------------------
# Points — raw award (no deduction; deduction is part of redemption flow)
# ---------------------------------------------------------------------------
async def award_points(
    user_id: int,
    amount: int,
    tx_type: str,
    description: str,
    related_id: Optional[str] = None,
) -> int:
    """Award points and return new balance."""
    async with get_pool().acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                UPDATE users
                SET points_balance = points_balance + $1,
                    total_earned   = total_earned   + $1,
                    last_active    = NOW()
                WHERE user_id = $2
                RETURNING points_balance
                """,
                amount, user_id,
            )
            await conn.execute(
                """
                INSERT INTO points_transactions
                    (user_id, type, amount, description, related_id)
                VALUES ($1, $2, $3, $4, $5)
                """,
                user_id, tx_type, amount, description, related_id,
            )
            return row["points_balance"]


async def get_transaction_history(user_id: int, limit: int = 10) -> List[dict]:
    rows = await get_pool().fetch(
        """
        SELECT type, amount, description, created_at
        FROM points_transactions
        WHERE user_id = $1
        ORDER BY created_at DESC
        LIMIT $2
        """,
        user_id, limit,
    )
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Support Tickets
# ---------------------------------------------------------------------------
async def create_ticket(user_id: int, message: str) -> SupportTicket:
    row = await get_pool().fetchrow(
        """
        INSERT INTO support_tickets (user_id, message)
        VALUES ($1, $2)
        RETURNING *
        """,
        user_id, message,
    )
    return SupportTicket(**dict(row))


async def get_ticket(ticket_id: int) -> Optional[SupportTicket]:
    row = await get_pool().fetchrow(
        "SELECT * FROM support_tickets WHERE id = $1", ticket_id
    )
    return SupportTicket(**dict(row)) if row else None


async def resolve_ticket(ticket_id: int, points: int) -> Optional[SupportTicket]:
    row = await get_pool().fetchrow(
        """
        UPDATE support_tickets
        SET status = 'resolved', points_awarded = $1, resolved_at = NOW()
        WHERE id = $2
        RETURNING *
        """,
        points, ticket_id,
    )
    return SupportTicket(**dict(row)) if row else None


async def get_open_tickets() -> List[dict]:
    rows = await get_pool().fetch(
        """
        SELECT t.*, u.first_name, u.username
        FROM support_tickets t
        JOIN users u ON t.user_id = u.user_id
        WHERE t.status IN ('open','in_progress')
        ORDER BY t.created_at ASC
        """
    )
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Contributions
# ---------------------------------------------------------------------------
async def create_contribution(
    user_id: int,
    description: str,
    value_score: int,
    points_earned: int,
    verified_by: int,
) -> Contribution:
    row = await get_pool().fetchrow(
        """
        INSERT INTO contributions
            (user_id, description, value_score, points_earned, verified_by)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING *
        """,
        user_id, description, value_score, points_earned, verified_by,
    )
    return Contribution(**dict(row))


# ---------------------------------------------------------------------------
# Redemptions — atomic point deduction + record creation
# ---------------------------------------------------------------------------
async def begin_redemption(
    user_id: int,
    rtype: str,
    phone: str,
    network: str,
    amount_ngn: int,
    points_cost: int,
    request_id: str,
    variation_id: Optional[str] = None,
) -> Optional[Redemption]:
    """
    Deduct points and create a pending redemption record atomically.
    Returns None if the user has insufficient balance.
    """
    async with get_pool().acquire() as conn:
        async with conn.transaction():
            # Lock the row to prevent concurrent deductions
            user_row = await conn.fetchrow(
                "SELECT points_balance FROM users WHERE user_id = $1 FOR UPDATE",
                user_id,
            )
            if not user_row or user_row["points_balance"] < points_cost:
                return None

            await conn.execute(
                """
                UPDATE users
                SET points_balance = points_balance - $1,
                    total_redeemed = total_redeemed + $1
                WHERE user_id = $2
                """,
                points_cost, user_id,
            )
            await conn.execute(
                """
                INSERT INTO points_transactions
                    (user_id, type, amount, description, related_id)
                VALUES ($1, $2, $3, $4, $5)
                """,
                user_id,
                f"redeemed_{rtype}",
                -points_cost,
                f"{rtype.capitalize()} redemption — {amount_ngn} NGN",
                request_id,
            )
            row = await conn.fetchrow(
                """
                INSERT INTO redemptions
                    (user_id, type, phone, network, amount_ngn, points_cost,
                     request_id, variation_id, status)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,'pending')
                RETURNING *
                """,
                user_id, rtype, phone, network, amount_ngn,
                points_cost, request_id, variation_id,
            )
            return Redemption(**dict(row))


async def complete_redemption(
    redemption_id: int, ebills_order_id: Optional[int] = None
) -> None:
    await get_pool().execute(
        """
        UPDATE redemptions
        SET status = 'completed', ebills_order_id = $1, completed_at = NOW()
        WHERE id = $2
        """,
        ebills_order_id, redemption_id,
    )


async def fail_and_refund_redemption(
    redemption_id: int, user_id: int, points_cost: int
) -> None:
    async with get_pool().acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "UPDATE redemptions SET status = 'refunded' WHERE id = $1",
                redemption_id,
            )
            await conn.execute(
                """
                UPDATE users
                SET points_balance = points_balance + $1,
                    total_redeemed = total_redeemed - $1
                WHERE user_id = $2
                """,
                points_cost, user_id,
            )
            await conn.execute(
                """
                INSERT INTO points_transactions
                    (user_id, type, amount, description, related_id)
                VALUES ($1, 'refunded', $2, 'Redemption refunded — delivery failed',
                        $3::TEXT)
                """,
                user_id, points_cost, redemption_id,
            )


async def get_redemption(redemption_id: int) -> Optional[Redemption]:
    row = await get_pool().fetchrow(
        "SELECT * FROM redemptions WHERE id = $1", redemption_id
    )
    return Redemption(**dict(row)) if row else None


async def get_redemption_by_request(request_id: str) -> Optional[Redemption]:
    row = await get_pool().fetchrow(
        "SELECT * FROM redemptions WHERE request_id = $1", request_id
    )
    return Redemption(**dict(row)) if row else None
