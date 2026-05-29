from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class User:
    user_id: int
    username: Optional[str]
    first_name: str
    last_name: Optional[str]
    phone: Optional[str]
    points_balance: int
    total_earned: int
    total_redeemed: int
    status: str
    registered_at: datetime
    last_active: datetime


@dataclass
class PointsTransaction:
    id: int
    user_id: int
    type: str
    amount: int
    description: Optional[str]
    related_id: Optional[str]
    created_at: datetime


@dataclass
class SupportTicket:
    id: int
    user_id: int
    message: str
    status: str
    assigned_to: Optional[int]
    points_awarded: int
    created_at: datetime
    resolved_at: Optional[datetime]


@dataclass
class Contribution:
    id: int
    user_id: int
    description: str
    value_score: int
    points_earned: int
    verified_by: int
    created_at: datetime


@dataclass
class Redemption:
    id: int
    user_id: int
    type: str
    phone: str
    network: str
    amount_ngn: int
    points_cost: int
    variation_id: Optional[str]
    status: str
    request_id: Optional[str]
    ebills_order_id: Optional[int]
    completed_at: Optional[datetime]
    created_at: datetime
