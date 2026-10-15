"""
Centralized application configuration, loaded from environment variables / .env.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ENVIRONMENT: str = "development"
    SECRET_KEY: str = "dev-secret-change-me"

    DATABASE_URL: str = "postgresql+asyncpg://btc_user:btc_password@localhost:5432/btc_trading"
    REDIS_URL: str = "redis://localhost:6379/0"

    BINANCE_WS_URL: str = "wss://stream.binance.com:9443/ws/btcusdt@kline_1m"
    BINANCE_REST_URL: str = "https://api.binance.com"

    EXCHANGE_API_KEY: str = ""
    EXCHANGE_API_SECRET: str = ""

    RETRAIN_CRON: str = "0 3 * * 1"  # Monday 03:00
    MODEL_ARTIFACT_DIR: str = "/app/artifacts"

    SYMBOL: str = "BTCUSDT"
    PREDICTION_HORIZON_MINUTES: int = 15  # how far ahead the model predicts up/down

    # Safety: outputs are always clamped away from absolute certainty
    PROB_CLAMP_EPSILON: float = 0.01  # probabilities are clamped to [eps, 1-eps]


settings = Settings()
