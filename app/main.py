import logging
import os
from contextlib import asynccontextmanager

from fastapi import (
    FastAPI,
    Header,
    HTTPException,
    Request,
)
from fastapi.responses import JSONResponse

from telegram import (
    BotCommand,
    BotCommandScopeAllChatAdministrators,
    BotCommandScopeAllPrivateChats,
    Update,
)
from telegram.ext import Application

from .config import settings
from .database import Database
from .dashboard import router as dashboard_router
from .handlers import register_handlers


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s | "
        "%(levelname)s | "
        "%(name)s | "
        "%(message)s"
    ),
)

logger = logging.getLogger("telegram-file-guard")


# ============================================================
# TELEGRAM APPLICATION
# ============================================================

telegram_app = (
    Application
    .builder()
    .token(settings.bot_token)
    .build()
)

register_handlers(telegram_app)


# ============================================================
# ENVIRONMENT
# ============================================================

def is_production() -> bool:
    return settings.environment in {
        "production",
        "render",
    }


def get_external_url() -> str:
    if settings.render_external_url:
        return settings.render_external_url.rstrip("/")

    hostname = os.getenv(
        "RENDER_EXTERNAL_HOSTNAME",
        "",
    ).strip()

    if hostname:
        return f"https://{hostname}"

    return ""


# ============================================================
# COMMAND MENU
# ============================================================

async def setup_commands():
    private_commands = [
        BotCommand(
            "start",
            "Start File Guard",
        ),
        BotCommand(
            "help",
            "Show help",
        ),
        BotCommand(
            "stats",
            "Admin statistics",
        ),
        BotCommand(
            "groups",
            "Protected groups",
        ),
        BotCommand(
            "id",
            "Show Telegram ID",
        ),
    ]

    group_admin_commands = [
        BotCommand(
            "start",
            "Start File Guard",
        ),
        BotCommand(
            "help",
            "Show help",
        ),
        BotCommand(
            "id",
            "Show Telegram ID",
        ),
    ]

    await telegram_app.bot.set_my_commands(
        private_commands,
        scope=BotCommandScopeAllPrivateChats(),
    )

    await telegram_app.bot.set_my_commands(
        group_admin_commands,
        scope=BotCommandScopeAllChatAdministrators(),
    )

    logger.info(
        "Telegram command menus configured."
    )


# ============================================================
# LIFESPAN
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):

    logger.info(
        "Starting Telegram File Guard..."
    )

    # --------------------------------------------------------
    # DATABASE
    # --------------------------------------------------------

    database = Database(
        settings.database_url
    )

    await database.connect()

    await database.create_tables()

    app.state.database = database

    telegram_app.bot_data["database"] = database

    logger.info(
        "Database connected and attached to Telegram application."
    )

    # --------------------------------------------------------
    # TELEGRAM
    # --------------------------------------------------------

    await telegram_app.initialize()

    logger.info(
        "Telegram application initialized."
    )

    await telegram_app.start()

    logger.info(
        "Telegram application started."
    )

    await setup_commands()

    # ========================================================
    # LOCAL POLLING
    # ========================================================

    if not is_production():

        logger.info(
            "Running in LOCAL POLLING mode."
        )

        await telegram_app.bot.delete_webhook(
            drop_pending_updates=True
        )

        await telegram_app.updater.start_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
        )

        logger.info(
            "Local polling started."
        )

    # ========================================================
    # RENDER WEBHOOK
    # ========================================================

    else:

        logger.info(
            "Running in WEBHOOK mode."
        )

        external_url = get_external_url()

        if not external_url:
            raise RuntimeError(
                "Set RENDER_EXTERNAL_URL "
                "or use Render's "
                "RENDER_EXTERNAL_HOSTNAME."
            )

        webhook_url = (
            f"{external_url}"
            "/telegram/webhook"
        )

        webhook_result = (
            await telegram_app.bot.set_webhook(
                url=webhook_url,
                secret_token=settings.webhook_secret,
                allowed_updates=Update.ALL_TYPES,
                max_connections=(
                    settings.webhook_max_connections
                ),
                drop_pending_updates=False,
            )
        )

        logger.info(
            "Telegram webhook configured: "
            "%s | result=%s",
            webhook_url,
            webhook_result,
        )

        webhook_info = (
            await telegram_app.bot.get_webhook_info()
        )

        logger.info(
            "Telegram webhook status: "
            "url=%s | pending_updates=%s",
            webhook_info.url,
            webhook_info.pending_update_count,
        )

    try:
        yield

    finally:

        logger.info(
            "Shutting down Telegram File Guard..."
        )

        # ----------------------------------------------------
        # LOCAL SHUTDOWN
        # ----------------------------------------------------

        if not is_production():

            try:
                if (
                    telegram_app.updater
                    and telegram_app.updater.running
                ):
                    await (
                        telegram_app
                        .updater
                        .stop()
                    )

            except Exception:
                logger.exception(
                    "Error stopping polling."
                )

        # ----------------------------------------------------
        # WEBHOOK SHUTDOWN
        # ----------------------------------------------------

        else:

            logger.info(
                "Keeping Telegram webhook configured "
                "during shutdown."
            )

        # ----------------------------------------------------
        # TELEGRAM SHUTDOWN
        # ----------------------------------------------------

        try:
            if telegram_app.running:
                await telegram_app.stop()

        except Exception:
            logger.exception(
                "Error stopping Telegram application."
            )

        try:
            await telegram_app.shutdown()

        except Exception:
            logger.exception(
                "Error shutting down Telegram application."
            )

        # ----------------------------------------------------
        # DATABASE SHUTDOWN
        # ----------------------------------------------------

        try:
            await database.close()

        except Exception:
            logger.exception(
                "Error closing database."
            )

        logger.info(
            "Shutdown complete."
        )


# ============================================================
# FASTAPI
# ============================================================

app = FastAPI(
    title="Telegram File Guard",
    version="4.0.0",
    lifespan=lifespan,
)


# ============================================================
# ROOT
# ============================================================

@app.get("/")
async def root():
    return {
        "name": "Telegram File Guard",
        "version": "4.0.0",
        "status": "running",
        "environment": settings.environment,
    }


# ============================================================
# HEALTH
# ============================================================

@app.api_route(
    "/health",
    methods=["GET", "HEAD"],
)
async def health(request: Request):

    database = getattr(
        request.app.state,
        "database",
        None,
    )

    if database is None:
        return JSONResponse(
            status_code=503,
            content={
                "status": "degraded",
                "database": "not_initialized",
                "telegram": "unknown",
            },
        )

    # --------------------------------------------------------
    # CHECK DATABASE
    # --------------------------------------------------------

    try:

        pool = getattr(
            database,
            "pool",
            None,
        )

        if pool is None:

            logger.error(
                "Database pool is not available."
            )

            return JSONResponse(
                status_code=503,
                content={
                    "status": "degraded",
                    "database": "pool_unavailable",
                    "telegram": (
                        "running"
                        if telegram_app.running
                        else "stopped"
                    ),
                },
            )

        async with pool.acquire() as connection:

            await connection.fetchval(
                "SELECT 1"
            )

        db_ok = True

    except Exception:

        logger.exception(
            "Health check failed."
        )

        db_ok = False

    # --------------------------------------------------------
    # DATABASE UNAVAILABLE
    # --------------------------------------------------------

    if not db_ok:

        return JSONResponse(
            status_code=503,
            content={
                "status": "degraded",
                "database": "offline",
                "telegram": (
                    "running"
                    if telegram_app.running
                    else "stopped"
                ),
            },
        )

    # --------------------------------------------------------
    # EVERYTHING HEALTHY
    # --------------------------------------------------------

    return {
        "status": "ok",
        "database": "connected",
        "telegram": (
            "running"
            if telegram_app.running
            else "stopped"
        ),
    }


# ============================================================
# WEBHOOK
# ============================================================

@app.post("/telegram/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(
        default=None
    ),
):

    logger.warning(
        "🔥 TELEGRAM WEBHOOK RECEIVED"
    )

    # --------------------------------------------------------
    # PRODUCTION CHECK
    # --------------------------------------------------------

    if not is_production():

        raise HTTPException(
            status_code=404,
            detail=(
                "Webhook is disabled "
                "in local mode."
            ),
        )

    # --------------------------------------------------------
    # SECRET TOKEN CHECK
    # --------------------------------------------------------

    if (
        x_telegram_bot_api_secret_token
        != settings.webhook_secret
    ):

        logger.error(
            "❌ INVALID TELEGRAM WEBHOOK SECRET"
        )

        raise HTTPException(
            status_code=403,
            detail="Invalid webhook secret.",
        )

    # --------------------------------------------------------
    # READ TELEGRAM UPDATE
    # --------------------------------------------------------

    try:

        data = await request.json()

        logger.info(
            "📦 TELEGRAM UPDATE RECEIVED | "
            "update_id=%s",
            data.get("update_id"),
        )

        update = Update.de_json(
            data,
            telegram_app.bot,
        )

        logger.info(
            "✅ TELEGRAM UPDATE PARSED | "
            "update_id=%s",
            update.update_id,
        )

    except Exception:

        logger.exception(
            "❌ FAILED TO PARSE TELEGRAM UPDATE"
        )

        raise HTTPException(
            status_code=400,
            detail="Invalid Telegram update.",
        )

    # --------------------------------------------------------
    # DIRECTLY PROCESS UPDATE
    # --------------------------------------------------------

    try:

        logger.info(
            "🚀 PROCESSING TELEGRAM UPDATE | "
            "update_id=%s",
            update.update_id,
        )

        await telegram_app.process_update(
            update
        )

        logger.info(
            "✅ TELEGRAM UPDATE PROCESSED | "
            "update_id=%s",
            update.update_id,
        )

    except Exception:

        logger.exception(
            "❌ FAILED TO PROCESS TELEGRAM UPDATE | "
            "update_id=%s",
            update.update_id,
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to process Telegram update.",
        )

    return JSONResponse(
        {
            "ok": True,
        }
    )


# ============================================================
# DASHBOARD
# ============================================================

app.include_router(
    dashboard_router
)