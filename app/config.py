import os

from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


# ============================================================
# DEFAULT BLOCKED EXTENSIONS
# ============================================================

DEFAULT_BLOCKED_EXTENSIONS = frozenset({

    # Windows executables
    ".exe",
    ".com",
    ".scr",
    ".pif",
    ".cpl",
    ".dll",
    ".sys",
    ".ocx",
    ".ax",

    # Windows scripts
    ".bat",
    ".cmd",
    ".vbs",
    ".vbe",
    ".js",
    ".jse",
    ".wsf",
    ".wsh",
    ".hta",
    ".ps1",
    ".psm1",
    ".psd1",
    ".ps1xml",
    ".psc1",

    # Shell scripts
    ".sh",
    ".bash",
    ".zsh",
    ".fish",
    ".csh",
    ".ksh",
    ".command",

    # Windows installers
    ".msi",
    ".msp",
    ".mst",
    ".appx",
    ".appxbundle",
    ".msix",
    ".msixbundle",

    # Windows dangerous files
    ".reg",
    ".inf",
    ".ins",
    ".isp",
    ".gadget",
    ".application",
    ".diagcab",
    ".diagpkg",

    # Android / Java
    ".apk",
    ".xapk",
    ".apks",
    ".aab",
    ".jar",

    # macOS
    ".dmg",
    ".pkg",
    ".app",

    # Linux
    ".deb",
    ".rpm",
    ".run",
    ".bin",

    # Archives
    ".zip",
    ".z",
    ".rar",
    ".7z",
    ".tar",
    ".gz",
    ".tgz",
    ".bz2",
    ".tbz",
    ".tbz2",
    ".xz",
    ".txz",
    ".lz",
    ".lz4",
    ".lzh",
    ".cab",
    ".arj",
    ".ace",

    # Disk images
    ".iso",
    ".img",
    ".vhd",
    ".vhdx",

    # Shortcuts / links
    ".lnk",
    ".url",
    ".scf",
    ".search-ms",
    ".website",

    # Macro-enabled Office
    ".docm",
    ".dotm",
    ".xlsm",
    ".xltm",
    ".xlam",
    ".pptm",
    ".potm",
    ".ppsm",
    ".ppam",

    # HTML / web payloads
    ".html",
    ".htm",
    ".mht",
    ".mhtml",

    # Other scripts / payloads
    ".ws",
    ".wsc",
    ".workflow",
    ".action",

    # Native binaries
    ".elf",
    ".out",
    ".so",
    ".dylib",

    # Requested
    ".txt",
})


# ============================================================
# HELPERS
# ============================================================

def get_bool(
    name: str,
    default: bool = False,
) -> bool:

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


def get_int(
    name: str,
    default: int,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:

    value = os.getenv(name)

    try:
        result = (
            int(value)
            if value is not None
            else default
        )

    except ValueError:
        result = default

    if minimum is not None:
        result = max(
            minimum,
            result,
        )

    if maximum is not None:
        result = min(
            maximum,
            result,
        )

    return result


# ============================================================
# EXTENSIONS
# ============================================================

def parse_extensions() -> frozenset[str]:

    raw = os.getenv(
        "BLOCKED_EXTENSIONS",
        "",
    ).strip()

    if not raw:
        return DEFAULT_BLOCKED_EXTENSIONS

    result = set()

    for item in raw.split(","):

        item = item.strip().lower()

        if not item:
            continue

        if not item.startswith("."):
            item = "." + item

        result.add(item)

    return frozenset(result)


# ============================================================
# ADMIN IDS
# ============================================================

def parse_admin_ids() -> tuple[int, ...]:

    raw = os.getenv(
        "ADMIN_IDS",
        "",
    ).strip()

    if not raw:
        return tuple()

    result = []

    for item in raw.split(","):

        item = item.strip()

        if not item:
            continue

        # Ignore accidental placeholders.
        if item.upper() in {
            "YOUR_REAL_TELEGRAM_ID",
            "YOUR_TELEGRAM_ID",
            "YOUR_TELEGRAM_USER_ID",
            "YOUR_ADMIN_ID",
        }:
            continue

        try:
            result.append(
                int(item)
            )

        except ValueError as exc:
            raise RuntimeError(
                "ADMIN_IDS must contain "
                "numeric Telegram IDs. "
                f"Invalid value: {item}"
            ) from exc

    return tuple(
        dict.fromkeys(result)
    )


# ============================================================
# SETTINGS
# ============================================================

@dataclass(frozen=True)
class Settings:

    bot_token: str

    database_url: str

    admin_ids: tuple[int, ...]

    dashboard_token: str

    webhook_secret: str

    render_external_url: str

    environment: str

    port: int

    delete_enabled: bool

    dry_run: bool

    alert_admins: bool

    webhook_max_connections: int

    blocked_extensions: frozenset[str]


# ============================================================
# LOAD SETTINGS
# ============================================================

def load_settings() -> Settings:

    bot_token = os.getenv(
        "BOT_TOKEN",
        "",
    ).strip()

    database_url = os.getenv(
        "DATABASE_URL",
        "",
    ).strip()

    dashboard_token = os.getenv(
        "DASHBOARD_TOKEN",
        "",
    ).strip()

    webhook_secret = os.getenv(
        "WEBHOOK_SECRET",
        "",
    ).strip()

    admin_ids = parse_admin_ids()

    environment = os.getenv(
        "ENVIRONMENT",
        "local",
    ).strip().lower()

    render_external_url = (
        os.getenv(
            "RENDER_EXTERNAL_URL",
            "",
        )
        .strip()
        .rstrip("/")
    )

    # ========================================================
    # REQUIRED SETTINGS
    # ========================================================

    if not bot_token:
        raise RuntimeError(
            "BOT_TOKEN is missing."
        )

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is missing."
        )

    if not dashboard_token:
        raise RuntimeError(
            "DASHBOARD_TOKEN is missing."
        )

    if not admin_ids:
        raise RuntimeError(
            "ADMIN_IDS is missing or empty."
        )

    # Webhook settings are required only in production.
    if environment == "production":

        if not webhook_secret:
            raise RuntimeError(
                "WEBHOOK_SECRET is required "
                "in production."
            )

        if not render_external_url:
            raise RuntimeError(
                "RENDER_EXTERNAL_URL is required "
                "in production."
            )

    # ========================================================
    # CREATE SETTINGS
    # ========================================================

    return Settings(

        bot_token=bot_token,

        database_url=database_url,

        admin_ids=admin_ids,

        dashboard_token=dashboard_token,

        webhook_secret=webhook_secret,

        render_external_url=render_external_url,

        environment=environment,

        port=get_int(
            "PORT",
            8000,
            1,
            65535,
        ),

        delete_enabled=get_bool(
            "DELETE_ENABLED",
            True,
        ),

        dry_run=get_bool(
            "DRY_RUN",
            False,
        ),

        alert_admins=get_bool(
            "ALERT_ADMINS",
            True,
        ),

        webhook_max_connections=get_int(
            "WEBHOOK_MAX_CONNECTIONS",
            40,
            1,
            100,
        ),

        blocked_extensions=parse_extensions(),
    )


# ============================================================
# GLOBAL SETTINGS INSTANCE
# ============================================================

settings = load_settings()