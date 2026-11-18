from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_PATH = BASE_DIR / "gradesense.db"

class Settings:
    APP_NAME = "GradeSense AI"
    DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATABASE_PATH}")
    DEBUG = os.getenv("DEBUG", "true").lower() == "true"
    AI_MODE = os.getenv("AI_MODE", "demo")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    DEFAULT_LANGUAGE = "English"

settings = Settings()
