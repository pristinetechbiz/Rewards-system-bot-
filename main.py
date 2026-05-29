import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage

from config.settings import settings
from db.repository import create_pool
from bot.middlewares.auth import UserMiddleware
from bot.handlers import registration, points, support, redemption, admin

logger = logging.getLogger(__name__)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # --- Database ---
    logger.info("Connecting to database...")
    await create_pool(settings.DATABASE_URL)
    logger.info("Database pool ready.")

    # --- Bot & Dispatcher ---
    bot = Bot(token=settings.BOT_TOKEN)
    storage = RedisStorage.from_url(settings.REDIS_URL)
    dp = Dispatcher(storage=storage)

    # --- Global middleware (runs for all updates) ---
    dp.message.middleware(UserMiddleware())
    dp.callback_query.middleware(UserMiddleware())

    # --- Include routers ---
    # Order matters: admin router has its own AdminMiddleware on the router level
    dp.include_router(admin.router)
    dp.include_router(registration.router)
    dp.include_router(points.router)
    dp.include_router(support.router)
    dp.include_router(redemption.router)

    # --- Start polling ---
    logger.info("Starting polling...")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
