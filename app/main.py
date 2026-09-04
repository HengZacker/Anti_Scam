import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from telegram import Update
from telegram.ext import Application

from .config import settings
from .database import Database
from .dashboard import router as dashboard_router
from .handlers import register_handlers


# ============================================================
# Telegram Application
# ============================================================

telegram_app: Application = (
    Application.builder()
    .token(settings.bot_token)
    .build()
)

register_handlers(telegram_app)


# ============================================================
# Helper: Determine Running Mode
# ============================================================

def is_production() -> bool:
    """
    Production mode is used on Render.

    ENVIRONMENT=production
    or
    ENVIRONMENT is not explicitly set and Render provides
    RENDER_EXTERNAL_URL.
    """

    environment = os.getenv("ENVIRONMENT", "").strip().lower()

    if environment == "production":
        return True

    if environment == "local":
        return False

    return bool(os.getenv("RENDER_EXTERNAL_URL"))


# ============================================================
# Lifespan
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):

    database = Database(settings.database_url)

    # --------------------------------------------------------
    # Connect to Neon PostgreSQL
    # --------------------------------------------------------

    await database.connect()

    app.state.database = database

    # Make database available to Telegram handlers
    telegram_app.bot_data["database"] = database

    # --------------------------------------------------------
    # Initialize Telegram Application
    # --------------------------------------------------------

    await telegram_app.initialize()
    await telegram_app.start()

    # ========================================================
    # LOCAL MODE
    # ========================================================

    if not is_production():

        print("========================================")
        print(" Telegram File Guard")
        print(" MODE: LOCAL / POLLING")
        print(" Database: Neon PostgreSQL")
        print("========================================")

        # Remove any existing webhook so polling can work
        await telegram_app.bot.delete_webhook(
            drop_pending_updates=True
        )

        # Start polling
        await telegram_app.updater.start_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
        )

        print("Telegram polling started.")
        print("Bot is ready.")

    # ========================================================
    # PRODUCTION MODE
    # ========================================================

    else:

        render_url = settings.render_external_url

        if not render_url:
            hostname = os.getenv(
                "RENDER_EXTERNAL_HOSTNAME",
                ""
            ).strip()

            if hostname:
                render_url = f"https://{hostname}"

        if not render_url:
            raise RuntimeError(
                "RENDER_EXTERNAL_URL or "
                "RENDER_EXTERNAL_HOSTNAME is required "
                "in production."
            )

        webhook_url = (
            f"{render_url.rstrip('/')}"
            "/telegram/webhook"
        )

        print("========================================")
        print(" Telegram File Guard")
        print(" MODE: PRODUCTION / WEBHOOK")
        print(" Database: Neon PostgreSQL")
        print(f" Webhook: {webhook_url}")
        print("========================================")

        await telegram_app.bot.set_webhook(
            url=webhook_url,
            secret_token=settings.webhook_secret,
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=False,
            max_connections=settings.max_connections,
        )

        print("Telegram webhook configured.")
        print("Bot is ready.")

    # --------------------------------------------------------
    # Application Running
    # --------------------------------------------------------

    try:
        yield

    finally:

        print("Shutting down Telegram File Guard...")

        # ====================================================
        # LOCAL MODE SHUTDOWN
        # ====================================================

        if not is_production():

            if telegram_app.updater.running:
                await telegram_app.updater.stop()

        # ====================================================
        # IMPORTANT:
        #
        # We intentionally DO NOT delete the webhook here
        # in production.
        #
        # During a Render deployment, deleting the webhook
        # from the old instance could interfere with the new
        # instance.
        # ====================================================

        await telegram_app.stop()
        await telegram_app.shutdown()

        await database.close()

        print("Shutdown complete.")


# ============================================================
# FastAPI Application
# ============================================================

app = FastAPI(
    title="Telegram File Guard",
    description="Telegram group file security and moderation bot",
    version="2.0.0",
    lifespan=lifespan,
)


# ============================================================
# Dashboard Routes
# ============================================================

app.include_router(dashboard_router)


# ============================================================
# Root
# ============================================================

@app.get("/")
async def root():
    return {
        "name": "Telegram File Guard",
        "version": "2.0.0",
        "status": "running",
        "mode": (
            "production"
            if is_production()
            else "local"
        ),
    }


# ============================================================
# Health Check
# ============================================================

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "telegram-file-guard",
    }


# ============================================================
# Telegram Webhook
# ============================================================

@app.post("/telegram/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(
        default=None
    ),
):

    # --------------------------------------------------------
    # Webhook should only be used in production
    # --------------------------------------------------------

    if not is_production():
        raise HTTPException(
            status_code=404,
            detail="Webhook is disabled in local mode.",
        )

    # --------------------------------------------------------
    # Verify Telegram Webhook Secret
    # --------------------------------------------------------

    if (
        not x_telegram_bot_api_secret_token
        or x_telegram_bot_api_secret_token
        != settings.webhook_secret
    ):
        raise HTTPException(
            status_code=403,
            detail="Invalid webhook secret.",
        )

    # --------------------------------------------------------
    # Read Telegram Update
    # --------------------------------------------------------

    try:
        data = await request.json()

        update = Update.de_json(
            data,
            telegram_app.bot,
        )

    except Exception as exc:
        print(
            f"Failed to parse Telegram update: {exc}"
        )

        raise HTTPException(
            status_code=400,
            detail="Invalid Telegram update.",
        )

    # --------------------------------------------------------
    # Send Update to Telegram Application
    # --------------------------------------------------------

    await telegram_app.update_queue.put(update)

    return JSONResponse(
        {
            "ok": True
        }
    )