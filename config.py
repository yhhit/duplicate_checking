# config.py
import datetime
import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv
import pathlib
BASE_DIR = pathlib.Path(__file__).resolve().parent
load_dotenv() # Load variables from .env file if it exists

class Settings(BaseSettings):
    # --- Database Configuration ---
    # Example for SQLite (adjust for Postgres/MySQL if needed)
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite://data/db.sqlite3")

    # Define database models location for Tortoise
    DB_MODELS: list[str] = ["model"] # Refers to the models.py file

    MAX_CONCURRENT_PROJECTS: int = os.getenv("MAX_CONCURRENT_PROJECTS", "10")  # Max projects generated simultaneously
    # 影响第一批次不生成注释功能
    MAX_CONCURRENT_FEATURES_PER_PROJECT: int = os.getenv("MAX_CONCURRENT_FEATURES_PER_PROJECT", "3")  # Max features per project
    LOG_FILENAME: str = f"./logs/ai_interaction_log_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    MODEL: str = os.getenv("MODEL", "gemini-3-pro-preview")  # Default model

settings = Settings()
(BASE_DIR / 'data').mkdir(parents=True, exist_ok=True)
(BASE_DIR / 'logs').mkdir(parents=True, exist_ok=True)