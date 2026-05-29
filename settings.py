from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # --- Required ---
    BOT_TOKEN: str
    ADMIN_IDS: str          # comma-separated Telegram user IDs
    DATABASE_URL: str
    REDIS_URL: str

    # --- eBills Africa ---
    EBILLS_USERNAME: str
    EBILLS_PASSWORD: str
    EBILLS_USER_PIN: str
    EBILLS_BASE_URL: str = "https://ebills.africa/wp-json/api/v2"
    EBILLS_AUTH_URL: str = "https://ebills.africa/wp-json/jwt-auth/v1/token"

    # --- Points Economy (all configurable) ---
    POINTS_REGISTRATION: int = 100
    POINTS_SUPPORT_TICKET: int = 50
    POINTS_SUPPORT_RESOLVED: int = 150
    POINTS_CONTRIBUTION_BASE: int = 10
    AIRTIME_RATE: int = 10     # points per NGN 1
    DATA_RATE: int = 8         # points per NGN 1 value

    @property
    def admin_ids_list(self) -> List[int]:
        return [int(x.strip()) for x in self.ADMIN_IDS.split(",") if x.strip()]

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
