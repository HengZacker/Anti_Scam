import logging

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
    Update,
)

from telegram.ext import Application

from app.config import settings

from app.database import Database

from app.handlers import register_handlers


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

logger = logging.getLogger(
    "telegram-file-guard"
)


# ============================================================
# SETTINGS
# ============================================================

# IMPORTANT:
# Do NOT use:
#
#     settings = Settings()
#
# Settings are already loaded by app.config.
settings = settings


# ============================================================
# DATABASE
# ============================================================

database = Database(
    settings.database_url
)


# ============================================================
# TELEGRAM APPLICATION
# ============================================================

telegram_app = (
    Application
    .builder()
    .token(settings.bot_token)
    .build()
)


# Make settings available to handlers.
telegram_app.bot_data[
    "settings"
] = settings


# Make database available to handlers.
telegram_app.bot_data[
    "database"
] = database


# Register Telegram handlers.
register_handlers(
    telegram_app
)


# ============================================================
# ENVIRONMENT
# ============================================================

def is_production() -> bool:

    return (
        settings.environment.lower()
        == "production"
    )


# ============================================================
# LIFESPAN
# ============================================================

@asynccontextmanager
async def lifespan(
    app: FastAPI,
):

    logger.info(
        "🚀 Starting Telegram File Guard..."
    )

    # ========================================================
    # DATABASE
    # ========================================================

    try:

        await database.connect()

        await database.create_tables()

        app.state.database = database

        logger.info(
            "✅ Database initialized successfully."
        )

    except Exception:

        logger.exception(
            "❌ Database initialization failed."
        )

        raise

    # ========================================================
    # TELEGRAM APPLICATION
    # ========================================================

    try:

        await telegram_app.initialize()

        await telegram_app.start()

        logger.info(
            "✅ Telegram application started."
        )

    except Exception:

        logger.exception(
            "❌ Telegram application startup failed."
        )

        raise

    # ========================================================
    # BOT COMMANDS
    # ========================================================

    try:

        await telegram_app.bot.set_my_commands(
            [
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

                BotCommand(
                    "stats",
                    "View statistics",
                ),

                BotCommand(
                    "groups",
                    "View protected groups",
                ),

                BotCommand(
                    "clearstats",
                    "Clear statistics",
                ),
            ]
        )

        logger.info(
            "✅ Bot commands configured."
        )

    except Exception:

        logger.exception(
            "⚠️ Failed to configure bot commands."
        )

    # ========================================================
    # WEBHOOK / LOCAL POLLING
    # ========================================================

    if is_production():

        webhook_url = (
            f"{settings.render_external_url}"
            "/telegram/webhook"
        )

        logger.warning(
            "🌐 PRODUCTION MODE"
        )

        logger.warning(
            "🔗 Webhook URL: %s",
            webhook_url,
        )

        # ====================================================
        # SET TELEGRAM WEBHOOK
        # ====================================================

        try:

            await telegram_app.bot.set_webhook(

                url=webhook_url,

                secret_token=(
                    settings.webhook_secret
                ),

                allowed_updates=(
                    Update.ALL_TYPES
                ),

                max_connections=(
                    settings.webhook_max_connections
                ),

                drop_pending_updates=False,
            )

            logger.info(
                "✅ Telegram webhook configured."
            )

        except Exception:

            logger.exception(
                "❌ Failed to configure "
                "Telegram webhook."
            )

            raise

        # ====================================================
        # WEBHOOK INFORMATION
        # ====================================================

        try:

            webhook_info = (
                await telegram_app.bot
                .get_webhook_info()
            )

            logger.info(
                "📡 WEBHOOK INFO | "
                "url=%s | "
                "pending=%s | "
                "last_error=%s | "
                "last_error_date=%s",

                webhook_info.url,

                webhook_info.pending_update_count,

                webhook_info.last_error_message,

                webhook_info.last_error_date,
            )

        except Exception:

            logger.exception(
                "⚠️ Failed to retrieve "
                "webhook information."
            )

    else:

        logger.warning(
            "💻 LOCAL MODE"
        )

        # ====================================================
        # REMOVE EXISTING WEBHOOK
        # ====================================================

        try:

            await telegram_app.bot.delete_webhook(
                drop_pending_updates=True
            )

            logger.info(
                "🧹 Existing webhook removed "
                "for local mode."
            )

        except Exception:

            logger.exception(
                "⚠️ Failed to remove webhook."
            )

        # ====================================================
        # START POLLING
        # ====================================================

        try:

            if telegram_app.updater is None:

                raise RuntimeError(
                    "Telegram updater is not available."
                )

            await telegram_app.updater.start_polling(

                allowed_updates=(
                    Update.ALL_TYPES
                ),

                drop_pending_updates=True,
            )

            logger.info(
                "✅ Telegram polling started."
            )

        except Exception:

            logger.exception(
                "❌ Failed to start Telegram polling."
            )

            raise

    # ========================================================
    # READY
    # ========================================================

    logger.info(
        "🛡️ Telegram File Guard is ready."
    )

    try:

        yield

    finally:

        logger.info(
            "🛑 Shutting down "
            "Telegram File Guard..."
        )

        # ====================================================
        # LOCAL POLLING SHUTDOWN
        # ====================================================

        if not is_production():

            try:

                if telegram_app.updater:

                    await telegram_app.updater.stop()

                    logger.info(
                        "✅ Telegram polling stopped."
                    )

            except Exception:

                logger.exception(
                    "⚠️ Failed to stop "
                    "Telegram polling."
                )

        # ====================================================
        # TELEGRAM APPLICATION SHUTDOWN
        # ====================================================

        try:

            await telegram_app.stop()

            logger.info(
                "✅ Telegram application stopped."
            )

        except Exception:

            logger.exception(
                "⚠️ Failed to stop "
                "Telegram application."
            )

        try:

            await telegram_app.shutdown()

            logger.info(
                "✅ Telegram application "
                "shutdown complete."
            )

        except Exception:

            logger.exception(
                "⚠️ Failed to shutdown "
                "Telegram application."
            )

        # ====================================================
        # DATABASE SHUTDOWN
        # ====================================================

        try:

            await database.close()

            logger.info(
                "✅ Database connection closed."
            )

        except Exception:

            logger.exception(
                "⚠️ Failed to close "
                "database connection."
            )

        logger.info(
            "👋 Telegram File Guard "
            "shutdown complete."
        )


# ============================================================
# FASTAPI
# ============================================================

app = FastAPI(
    title="Telegram File Guard",
    version="1.0.0",
    lifespan=lifespan,
)


# ============================================================
# HEALTH CHECK
# ============================================================

@app.api_route(
    "/health",
    methods=["GET", "HEAD"],
)
async def health():

    try:

        pool = database.pool

        if pool is None:

            return JSONResponse(
                status_code=503,
                content={
                    "status": "unhealthy",
                    "database": "not_connected",
                },
            )

        async with pool.acquire() as connection:

            await connection.execute(
                "SELECT 1"
            )

        return {
            "status": "ok",
            "database": "connected",
        }

    except Exception:

        logger.exception(
            "❌ Health check failed."
        )

        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "database": "error",
            },
        )


# ============================================================
# TELEGRAM WEBHOOK
# ============================================================

@app.post(
    "/telegram/webhook"
)
async def telegram_webhook(

    request: Request,

    x_telegram_bot_api_secret_token: (
        str | None
    ) = Header(
        default=None
    ),
):

    logger.warning(
        "🔥 TELEGRAM WEBHOOK RECEIVED"
    )

    # ========================================================
    # PRODUCTION CHECK
    # ========================================================

    if not is_production():

        raise HTTPException(
            status_code=404,
            detail=(
                "Webhook is disabled "
                "in local mode."
            ),
        )

    # ========================================================
    # SECRET CHECK
    # ========================================================

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

    # ========================================================
    # READ JSON
    # ========================================================

    try:

        data = await request.json()

        logger.info(
            "📦 TELEGRAM UPDATE RECEIVED | "
            "update_id=%s",
            data.get("update_id"),
        )

    except Exception:

        logger.exception(
            "❌ FAILED TO READ TELEGRAM JSON"
        )

        raise HTTPException(
            status_code=400,
            detail="Invalid Telegram JSON.",
        )

    # ========================================================
    # PARSE TELEGRAM UPDATE
    # ========================================================

    try:

        update = Update.de_json(
            data,
            telegram_app.bot,
        )

        if update is None:

            raise ValueError(
                "Telegram returned an empty update."
            )

        logger.info(
            "✅ TELEGRAM UPDATE PARSED | "
            "update_id=%s",
            update.update_id,
        )

    except Exception:

        logger.exception(
            "❌ FAILED TO PARSE "
            "TELEGRAM UPDATE"
        )

        raise HTTPException(
            status_code=400,
            detail="Invalid Telegram update.",
        )

    # ========================================================
    # RAW UPDATE DIAGNOSTICS
    # ========================================================

    logger.warning(
        "🔍 RAW UPDATE TYPES | "
        "message=%s | "
        "edited_message=%s | "
        "channel_post=%s | "
        "edited_channel_post=%s | "
        "callback_query=%s | "
        "my_chat_member=%s",

        bool(update.message),

        bool(update.edited_message),

        bool(update.channel_post),

        bool(update.edited_channel_post),

        bool(update.callback_query),

        bool(update.my_chat_member),
    )

    # ========================================================
    # MESSAGE DIAGNOSTICS
    # ========================================================

    if update.message:

        logger.warning(
            "🔍 MESSAGE CONTENT | "
            "document=%s | "
            "photo=%s | "
            "video=%s | "
            "audio=%s | "
            "text=%s",

            bool(update.message.document),

            bool(update.message.photo),

            bool(update.message.video),

            bool(update.message.audio),

            bool(update.message.text),
        )

        if update.message.document:

            logger.warning(
                "📄 DOCUMENT FOUND | "
                "filename=%s | "
                "mime_type=%s",

                update.message.document.file_name,

                update.message.document.mime_type,
            )

    # ========================================================
    # PROCESS UPDATE DIRECTLY
    # ========================================================

    try:

        logger.warning(
            "🚀 PROCESSING TELEGRAM UPDATE | "
            "update_id=%s",
            update.update_id,
        )

        await telegram_app.process_update(
            update
        )

        logger.warning(
            "✅ TELEGRAM UPDATE PROCESSED | "
            "update_id=%s",
            update.update_id,
        )

    except Exception:

        logger.exception(
            "❌ FAILED TO PROCESS "
            "TELEGRAM UPDATE | "
            "update_id=%s",
            update.update_id,
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to process "
                "Telegram update."
            ),
        )

    return JSONResponse(
        content={
            "ok": True
        }
    )


# ============================================================
# ROOT
# ============================================================

@app.get("/")
async def root():

    return {
        "name": "Telegram File Guard",
        "status": "running",
    }