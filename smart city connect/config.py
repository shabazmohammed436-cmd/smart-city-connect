import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _bool(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-insecure-secret-change-me")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", f"sqlite:///{BASE_DIR / 'instance' / 'smartcity.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_TIME_LIMIT = None

    SESSION_COOKIE_HTTPONLY = _bool("SESSION_COOKIE_HTTPONLY", "1")
    SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
    SESSION_COOKIE_SECURE = _bool("SESSION_COOKIE_SECURE", "0")
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 24 * 7

    MAX_CONTENT_LENGTH = 6 * 1024 * 1024
    ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
    UPLOAD_FOLDER = BASE_DIR / "uploads"

    MAIL_SERVER = os.getenv("MAIL_SERVER", "").strip()
    MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))
    MAIL_USE_TLS = _bool("MAIL_USE_TLS", "1")
    MAIL_USERNAME = os.getenv("MAIL_USERNAME", "").strip()
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "").strip()
    MAIL_FROM = os.getenv("MAIL_FROM", "SmartCity Connect <noreply@localhost>")

    DEMO_ADMIN_EMAIL = os.getenv("DEMO_ADMIN_EMAIL", "admin@smartcity.local")
    DEMO_ADMIN_PASSWORD = os.getenv("DEMO_ADMIN_PASSWORD", "ChangeThisAdmin123!")
    DEMO_WORKER_EMAIL = os.getenv("DEMO_WORKER_EMAIL", "worker@smartcity.local")
    DEMO_WORKER_PASSWORD = os.getenv("DEMO_WORKER_PASSWORD", "ChangeThisWorker123!")
    DEMO_CITIZEN_EMAIL = os.getenv("DEMO_CITIZEN_EMAIL", "citizen@smartcity.local")
    DEMO_CITIZEN_PASSWORD = os.getenv("DEMO_CITIZEN_PASSWORD", "ChangeThisCitizen123!")

    NOMINATIM_ENABLED = _bool("NOMINATIM_ENABLED", "0")
    NOMINATIM_USER_AGENT = os.getenv(
        "NOMINATIM_USER_AGENT",
        "SmartCityConnectHackathon/1.0 (local-demo)",
    )

    AI_PROVIDER = os.getenv("AI_PROVIDER", "").strip()
    AI_API_KEY = os.getenv("AI_API_KEY", "").strip()
    AI_API_URL = os.getenv("AI_API_URL", "").strip()

    @property
    def mail_configured(self) -> bool:
        return bool(self.MAIL_SERVER and self.MAIL_USERNAME and self.MAIL_PASSWORD)

    @property
    def ai_configured(self) -> bool:
        return bool(self.AI_PROVIDER and self.AI_API_KEY)
