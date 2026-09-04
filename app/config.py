import os
from dotenv import load_dotenv
from dataclasses import dataclass
from urllib.parse import urlparse

load_dotenv()
DEFAULT_BLOCKED_EXTENSIONS = {
    ".exe",
    ".bat",
    ".vbs",
    ".ps1",
    ".sh",
    ".msi",
    ".scr",
}


def get_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)

    if value is None:
        return default

    return value.strip().lower() in {
        "1",
        "true",
        "yes",
        "y",
        "on",
    }


def get_int(name: str, default: int) -> int:
    value = os.getenv(name)

    if value is None:
        return default

    try:
        return int(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    bot_token: str
    database_url: str

    admin_ids: tuple[int, ...]

    dashboard_token: str
    webhook_secret: str

    render_external_url: str

    port: int

    environment: str

    delete_enabled: bool
    alert_admins: bool

    max_connections: int

    blocked_extensions: frozenset[str]


def load_settings() -> Settings:

    bot_token = os.getenv("BOT_TOKEN", "").strip()
    database_url = os.getenv("DATABASE_URL", "").strip()

    dashboard_token = os.getenv("DASHBOARD_TOKEN", "").strip()
    webhook_secret = os.getenv("WEBHOOK_SECRET", "").strip()

    render_external_url = os.getenv(
        "RENDER_EXTERNAL_URL",
        "",
    ).strip().rstrip("/")

    if not bot_token:
        raise RuntimeError("BOT_TOKEN is missing.")

    if not database_url:
        raise RuntimeError("DATABASE_URL is missing.")

    if not dashboard_token:
        raise RuntimeError("DASHBOARD_TOKEN is missing.")

    if not webhook_secret:
        raise RuntimeError("WEBHOOK_SECRET is missing.")

    admin_ids_raw = os.getenv("ADMIN_IDS", "")

    admin_ids = []

    for item in admin_ids_raw.split(","):
        item = item.strip()

        if not item:
            continue

        try:
            admin_ids.append(int(item))
        except ValueError:
            raise RuntimeError(
                f"Invalid ADMIN_IDS value: {item}"
            )

    if not admin_ids:
        raise RuntimeError(
            "ADMIN_IDS is missing or empty."
        )

    blocked_raw = os.getenv(
        "BLOCKED_EXTENSIONS",
        "",
    ).strip()

    if blocked_raw:
        blocked_extensions = {
            ext.strip().lower()
            if ext.strip().startswith(".")
            else f".{ext.strip().lower()}"
            for ext in blocked_raw.split(",")
            if ext.strip()
        }
    else:
        blocked_extensions = DEFAULT_BLOCKED_EXTENSIONS

    return Settings(
        bot_token=bot_token,
        database_url=database_url,
        admin_ids=tuple(admin_ids),
        dashboard_token=dashboard_token,
        webhook_secret=webhook_secret,
        render_external_url=render_external_url,
        port=get_int("PORT", 10000),
        environment=os.getenv(
            "ENVIRONMENT",
            "production",
        ),
        delete_enabled=get_bool(
            "DELETE_ENABLED",
            True,
        ),
        alert_admins=get_bool(
            "ALERT_ADMINS",
            True,
        ),
        max_connections=get_int(
            "WEBHOOK_MAX_CONNECTIONS",
            40,
        ),
        blocked_extensions=frozenset(
            blocked_extensions
        ),
    )


settings = load_settings()