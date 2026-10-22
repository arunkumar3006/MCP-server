"""
Configuration loader for Email MCP Server.
Loads environment variables dynamically so changes in .env are picked up immediately.
"""

import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

# Base directory for the MCP server
BASE_DIR = Path(__file__).resolve().parent

# Configure logging to write to stderr and email_mcp.log (never stdout!)
LOG_FILE = BASE_DIR / "email_mcp.log"
logger = logging.getLogger("email_mcp")
logger.setLevel(logging.INFO)

# Formatter
log_formatter = logging.Formatter(
    "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# StreamHandler writing strictly to sys.stderr (MCP protocol requires clean sys.stdout)
stderr_handler = logging.StreamHandler(sys.stderr)
stderr_handler.setFormatter(log_formatter)
logger.addHandler(stderr_handler)

# FileHandler for audit and debugging
file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
file_handler.setFormatter(log_formatter)
logger.addHandler(file_handler)


class _ConfigMeta(type):
    """Metaclass that reloads .env dynamically on every property access."""

    def _refresh(cls):
        load_dotenv(BASE_DIR / ".env", override=True)

    @property
    def DATABASE_PATH(cls) -> Path:
        cls._refresh()
        return BASE_DIR / os.getenv("DATABASE_PATH", "emails.db")

    @property
    def DEFAULT_PROVIDER(cls) -> str:
        cls._refresh()
        return os.getenv("DEFAULT_PROVIDER", "auto").strip().lower()

    @property
    def EMAIL_DRY_RUN(cls) -> bool:
        cls._refresh()
        return os.getenv("EMAIL_DRY_RUN", "false").strip().lower() in ("true", "1", "yes")

    @property
    def POLL_INTERVAL_SECONDS(cls) -> int:
        cls._refresh()
        return int(os.getenv("POLL_INTERVAL_SECONDS", "5"))

    @property
    def TIMEZONE(cls) -> str:
        cls._refresh()
        return os.getenv("TIMEZONE", "").strip()

    # SMTP Settings
    @property
    def SMTP_HOST(cls) -> str:
        cls._refresh()
        return os.getenv("SMTP_HOST", "").strip()

    @property
    def SMTP_PORT(cls) -> int:
        cls._refresh()
        return int(os.getenv("SMTP_PORT", "587") or "587")

    @property
    def SMTP_USER(cls) -> str:
        cls._refresh()
        return os.getenv("SMTP_USER", "").strip()

    @property
    def SMTP_PASSWORD(cls) -> str:
        cls._refresh()
        return os.getenv("SMTP_PASSWORD", "").strip().replace(" ", "")

    @property
    def SMTP_USE_TLS(cls) -> bool:
        cls._refresh()
        return os.getenv("SMTP_USE_TLS", "true").strip().lower() in ("true", "1", "yes")

    @property
    def SMTP_USE_SSL(cls) -> bool:
        cls._refresh()
        return os.getenv("SMTP_USE_SSL", "false").strip().lower() in ("true", "1", "yes")

    @property
    def SMTP_DEFAULT_FROM(cls) -> str:
        cls._refresh()
        return os.getenv("SMTP_DEFAULT_FROM", "").strip() or cls.SMTP_USER

    # Resend Settings
    @property
    def RESEND_API_KEY(cls) -> str:
        cls._refresh()
        return os.getenv("RESEND_API_KEY", "").strip()

    @property
    def RESEND_DEFAULT_FROM(cls) -> str:
        cls._refresh()
        return os.getenv("RESEND_DEFAULT_FROM", "").strip()

    # SendGrid Settings
    @property
    def SENDGRID_API_KEY(cls) -> str:
        cls._refresh()
        return os.getenv("SENDGRID_API_KEY", "").strip()

    @property
    def SENDGRID_DEFAULT_FROM(cls) -> str:
        cls._refresh()
        return os.getenv("SENDGRID_DEFAULT_FROM", "").strip()


class Config(metaclass=_ConfigMeta):
    """Access settings with auto-reload from .env."""

    @classmethod
    def is_smtp_configured(cls) -> bool:
        return bool(cls.SMTP_HOST and cls.SMTP_USER and cls.SMTP_PASSWORD)

    @classmethod
    def is_resend_configured(cls) -> bool:
        return bool(cls.RESEND_API_KEY)

    @classmethod
    def is_sendgrid_configured(cls) -> bool:
        return bool(cls.SENDGRID_API_KEY)

    @classmethod
    def get_effective_provider(cls, requested: str = "auto") -> str:
        req = (requested or "auto").strip().lower()
        if req != "auto":
            return req

        if cls.DEFAULT_PROVIDER != "auto":
            return cls.DEFAULT_PROVIDER

        # Auto-detect best available provider
        if cls.is_smtp_configured():
            return "smtp"
        if cls.is_resend_configured():
            return "resend"
        if cls.is_sendgrid_configured():
            return "sendgrid"

        # Default fallback is mock/dry-run mode
        return "mock"
