from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject

from config.settings import settings
from db import repository


class UserMiddleware(BaseMiddleware):
    """
    Runs before every update.
    - Upserts the user record (first time creates via create_user logic, subsequent times
      just fetches and updates last_active).
    - Injects `user` into handler data.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        # Extract the Telegram user from Message or CallbackQuery
        tg_user = None
        if isinstance(event, Message):
            tg_user = event.from_user
        elif isinstance(event, CallbackQuery):
            tg_user = event.from_user

        if tg_user:
            user = await repository.get_user(tg_user.id)
            if user:
                await repository.update_last_active(tg_user.id)
            data["db_user"] = user  # None if not registered yet

        return await handler(event, data)


class AdminMiddleware(BaseMiddleware):
    """
    Rejects non-admin users from admin-only routers.
    Attach this to the admin router only.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        tg_user = None
        if isinstance(event, Message):
            tg_user = event.from_user
        elif isinstance(event, CallbackQuery):
            tg_user = event.from_user

        if not tg_user or tg_user.id not in settings.admin_ids_list:
            if isinstance(event, Message):
                await event.answer("⛔ Admin access required.")
            elif isinstance(event, CallbackQuery):
                await event.answer("⛔ Admin access required.", show_alert=True)
            return

        return await handler(event, data)
