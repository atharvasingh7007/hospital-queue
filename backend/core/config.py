"""
Hospital Queue AI — Core Configuration
Loads environment variables and provides app-wide settings.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from backend directory
_backend_dir = Path(__file__).resolve().parent.parent
_env_path = _backend_dir / ".env"
if _env_path.exists():
    load_dotenv(_env_path)


class AppConfig:
    PROJECT_ID = os.getenv("GCP_PROJECT", os.getenv("GOOGLE_CLOUD_PROJECT", ""))
    LOCATION = os.getenv("LOCATION", os.getenv("VERTEX_AI_LOCATION", "us-central1"))
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    DEBUG = os.getenv("DEBUG", "true").lower() == "true"
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-in-production")

    CORS_ORIGINS = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:3000,http://localhost:3001,http://localhost:3002"
        ).split(",")
    ]

    @classmethod
    def requires_gcp(cls) -> bool:
        """Check if running on Google Cloud Run."""
        return os.getenv("K_SERVICE") is not None

    @classmethod
    def has_gcp_credentials(cls) -> bool:
        """Check if GCP credentials are likely available."""
        if cls.requires_gcp():
            return True
        if not cls.PROJECT_ID:
            return False
        try:
            from google.auth import default as google_auth_default
            credentials, _ = google_auth_default()
            return credentials is not None
        except Exception:
            return False
