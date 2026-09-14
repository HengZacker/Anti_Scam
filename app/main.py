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

    # Private chat menu
    await telegram_app.bot.set_my_commands(
        private_commands,
        scope=BotCommandScopeAllPrivateChats(),
    )

    # Telegram shows this menu only to
    # administrators of the group.
    await telegram_app.bot.set_my_commands(
        group_admin_commands,
        scope=BotCommandScopeAllChatAdministrators(),
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

    # --------------------------------------------------------
    # TELEGRAM
    # --------------------------------------------------------

    await telegram_app.initialize()
    await telegram_app.start()
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

        await telegram_app.bot.set_webhook(
            url=webhook_url,
            secret_token=settings.webhook_secret,
            allowed_updates=Update.ALL_TYPES,
            max_connections=(
                settings.webhook_max_connections
            ),
            drop_pending_updates=False,
        )

        logger.info(
            "Telegram webhook configured: %s",
            webhook_url,
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

            try:

                await telegram_app.bot.delete_webhook(
                    drop_pending_updates=False
                )

            except Exception:

                logger.exception(
                    "Error deleting webhook."
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

@app.get("/health")
async def health(request: Request):

    database = getattr(
        request.app.state,
        "database",
        None,
    )

    # Database was never initialized
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
    # Check database connection
    # --------------------------------------------------------

    try:

        # The Database class in this project does not
        # currently expose a ping() method.
        #
        # Instead, check the underlying asyncpg pool.
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

        # Execute a lightweight PostgreSQL query.
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
    # Database unavailable
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
    # Everything is healthy
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

    if not is_production():

        raise HTTPException(
            status_code=404,
            detail=(
                "Webhook is disabled "
                "in local mode."
            ),
        )

    if (
        x_telegram_bot_api_secret_token
        != settings.webhook_secret
    ):

        raise HTTPException(
            status_code=403,
            detail=(
                "Invalid webhook secret."
            ),
        )

    try:

        data = await request.json()

        update = Update.de_json(
            data,
            telegram_app.bot,
        )

        await telegram_app.update_queue.put(
            update
        )

    except Exception:

        logger.exception(
            "Failed to process webhook update."
        )

        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid Telegram update."
            ),
        )

    return JSONResponse(
        {
            "ok": True
        }
    )


# ============================================================
# DASHBOARD
# ============================================================

app.include_router(
    dashboard_router
)
