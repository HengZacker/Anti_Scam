import logging

from telegram import Update
from telegram.ext import (
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.config import Settings
from app.database import Database
from app.filters import (
    get_extension,
    is_blocked_filename,
)

logger = logging.getLogger(__name__)


def get_database(context: ContextTypes.DEFAULT_TYPE) -> Database:
    database = context.application.bot_data.get("database")

    if database is None:
        raise RuntimeError("Database is not available.")

    return database


def get_settings(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    settings = context.application.bot_data.get("settings")

    if settings is None:
        raise RuntimeError("Settings are not available.")

    return settings


def is_admin(user_id: int | None, settings: Settings) -> bool:
    if user_id is None:
        return False

    return user_id in settings.admin_ids


async def send_admin_alert(
    context: ContextTypes.DEFAULT_TYPE,
    *,
    filename: str,
    extension: str,
    group_title: str,
    group_id: int,
    username: str,
    user_id: int | None,
    deleted: bool,
):
    settings = get_settings(context)

    if not settings.alert_admins:
        logger.info("ADMIN ALERT DISABLED")
        return

    status = "DELETED" if deleted else "FAILED TO DELETE"

    message = (
        "🚨 SECURITY ALERT\n\n"
        f"📄 File: {filename}\n"
        f"🔴 Extension: {extension}\n"
        f"📌 Status: {status}\n\n"
        f"👥 Group: {group_title}\n"
        f"🆔 Group ID: {group_id}\n\n"
        f"👤 User: {username}\n"
        f"🆔 User ID: {user_id if user_id else 'Unknown'}"
    )

    for admin_id in settings.admin_ids:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=message,
            )

            logger.info(
                "Security alert sent successfully | "
                "Admin: %s | File: %s | Group: %s",
                admin_id,
                filename,
                group_title,
            )

        except Exception:
            logger.exception(
                "Failed to send security alert | "
                "Admin: %s | File: %s",
                admin_id,
                filename,
            )


async def start_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not update.effective_chat:
        return

    await update.effective_chat.send_message(
        "🛡️ Telegram File Guard is active."
    )


async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not update.effective_chat:
        return

    settings = get_settings(context)

    user_id = update.effective_user.id if update.effective_user else None

    # Hide admin commands from normal group members.
    if (
        update.effective_chat.type in {"group", "supergroup"}
        and not is_admin(user_id, settings)
    ):
        return

    text = (
        "🛡️ FILE GUARD HELP\n\n"
        "The bot automatically removes blocked file types from protected groups.\n\n"
        "Admin commands:\n"
        "/stats - View security statistics\n"
        "/groups - View protected groups\n"
        "/clearstats - Clear deletion statistics\n"
        "/id - Show your Telegram ID\n"
        "/help - Show this help\n"
    )

    await update.effective_chat.send_message(text)


async def id_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not update.effective_user or not update.effective_chat:
        return

    await update.effective_chat.send_message(
        f"🆔 Your Telegram ID:\n`{update.effective_user.id}`",
        parse_mode="Markdown",
    )


async def stats_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not update.effective_user or not update.effective_chat:
        return

    settings = get_settings(context)

    if not is_admin(update.effective_user.id, settings):
        logger.warning(
            "Unauthorized /stats attempt | User=%s",
            update.effective_user.id,
        )
        return

    try:
        database = get_database(context)

        stats = await database.get_stats()

        logger.info(
            "STATISTICS COMMAND | %s",
            stats,
        )

        text = (
            "📊 SECURITY STATISTICS\n\n"
            f"🗑️ Total detections: {stats['total']}\n"
            f"✅ Successfully deleted: {stats['successful']}\n"
            f"❌ Failed deletions: {stats['failed']}\n"
            f"👥 Protected groups: {stats['groups']}\n"
            f"👤 Unique users: {stats['users']}\n"
            f"📅 Today: {stats['today']}"
        )

        await update.effective_chat.send_message(text)

    except Exception:
        logger.exception("Failed to process /stats command")

        await update.effective_chat.send_message(
            "❌ Failed to load statistics."
        )


async def groups_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not update.effective_user or not update.effective_chat:
        return

    settings = get_settings(context)

    if not is_admin(update.effective_user.id, settings):
        logger.warning(
            "Unauthorized /groups attempt | User=%s",
            update.effective_user.id,
        )
        return

    try:
        database = get_database(context)

        groups = await database.get_groups()

        if not groups:
            await update.effective_chat.send_message(
                "📭 No protected groups found."
            )
            return

        lines = ["🛡️ PROTECTED GROUPS\n"]

        for index, group in enumerate(groups, start=1):
            title = group["title"] or "Unknown Group"
            chat_id = group["chat_id"]
            username = group["username"]

            if username:
                group_name = f"{title} (@{username})"
            else:
                group_name = title

            lines.append(
                f"{index}. {group_name}\n"
                f"   🆔 {chat_id}"
            )

        await update.effective_chat.send_message(
            "\n".join(lines)
        )

    except Exception:
        logger.exception("Failed to process /groups command")

        await update.effective_chat.send_message(
            "❌ Failed to load protected groups."
        )


async def clear_stats_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not update.effective_user or not update.effective_chat:
        return

    settings = get_settings(context)

    if not is_admin(update.effective_user.id, settings):
        logger.warning(
            "Unauthorized /clearstats attempt | User=%s",
            update.effective_user.id,
        )
        return

    try:
        database = get_database(context)

        deleted_count = await database.clear_statistics()

        logger.warning(
            "ADMIN CLEARED STATISTICS | "
            "Admin=%s | DeletedEvents=%s",
            update.effective_user.id,
            deleted_count,
        )

        await update.effective_chat.send_message(
            "🧹 Statistics cleared successfully.\n\n"
            f"🗑️ Deleted records: {deleted_count}"
        )

    except Exception:
        logger.exception(
            "Failed to clear statistics | Admin=%s",
            update.effective_user.id,
        )

        await update.effective_chat.send_message(
            "❌ Failed to clear statistics."
        )


async def document_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    logger.warning(
        "🔥 DOCUMENT HANDLER TRIGGERED | update_id=%s",
        update.update_id,
    )

    if not update.message:
        logger.warning(
            "DOCUMENT HANDLER EXIT | update.message is None"
        )
        return

    message = update.message

    if not message.document:
        logger.warning(
            "DOCUMENT HANDLER EXIT | message.document is None"
        )
        return

    chat = message.chat

    # Only protect groups and supergroups.
    if chat.type not in {"group", "supergroup"}:
        logger.info(
            "FILE IGNORED | Chat type=%s",
            chat.type,
        )
        return

    document = message.document

    filename = document.file_name or ""

    logger.warning(
        "📄 DOCUMENT FOUND | "
        "filename=%s | mime_type=%s | chat=%s",
        filename,
        document.mime_type,
        chat.title,
    )

    settings = get_settings(context)
    database = get_database(context)

    blocked_extensions = is_blocked_filename(
        filename,
        settings.blocked_extensions,
    )

    if not blocked_extensions:
        logger.info(
            "FILE ALLOWED | File=%s",
            filename,
        )
        return

    extension = get_extension(filename)

    logger.warning(
        "🚨 BLOCKED FILE DETECTED | "
        "File=%s | Extension=%s | Blocked=%s | Group=%s",
        filename,
        extension,
        blocked_extensions,
        chat.title,
    )

    # Register/update protected group.
    try:
        await database.upsert_group(
            chat_id=chat.id,
            title=chat.title or "Unknown Group",
            username=chat.username,
            chat_type=chat.type,
        )

        logger.info(
            "GROUP REGISTERED | "
            "Group=%s | ID=%s",
            chat.title,
            chat.id,
        )

    except Exception:
        logger.exception(
            "GROUP UPSERT FAILED | "
            "Group=%s | ID=%s",
            chat.title,
            chat.id,
        )

    deleted = False

    # Delete the suspicious message.
    if settings.delete_enabled and not settings.dry_run:
        try:
            await message.delete()

            deleted = True

            logger.warning(
                "🗑️ FILE DELETED | "
                "File=%s | Group=%s | GroupID=%s",
                filename,
                chat.title,
                chat.id,
            )

        except Exception:
            logger.exception(
                "❌ FILE DELETE FAILED | "
                "File=%s | Group=%s | GroupID=%s",
                filename,
                chat.title,
                chat.id,
            )

    else:
        logger.warning(
            "⚠️ DELETE SKIPPED | "
            "delete_enabled=%s | dry_run=%s",
            settings.delete_enabled,
            settings.dry_run,
        )

    # Record statistics.
    logger.warning(
        "📊 RECORDING DELETION STAT | "
        "File=%s | Group=%s | Deleted=%s",
        filename,
        chat.title,
        deleted,
    )

    user = message.from_user

    username = (
        f"@{user.username}"
        if user and user.username
        else (
            user.first_name
            if user and user.first_name
            else "Unknown"
        )
    )

    try:
        await database.record_deletion(
            message_id=message.message_id,
            chat_id=chat.id,
            group_title=chat.title or "Unknown Group",
            group_username=chat.username,
            user_id=user.id if user else None,
            username=user.username if user else None,
            first_name=user.first_name if user else None,
            last_name=user.last_name if user else None,
            file_name=filename,
            file_extension=extension,
            reason=f"Blocked extension: {extension}",
            deleted_successfully=deleted,
        )

        logger.warning(
            "✅ STAT RECORDED SUCCESSFULLY | "
            "File=%s | Group=%s | Deleted=%s",
            filename,
            chat.title,
            deleted,
        )

    except Exception:
        logger.exception(
            "❌ STAT RECORDING FAILED | "
            "File=%s | Group=%s",
            filename,
            chat.title,
        )

    # Send admin alert.
    try:
        await send_admin_alert(
            context,
            filename=filename,
            extension=extension,
            group_title=chat.title or "Unknown Group",
            group_id=chat.id,
            username=username,
            user_id=user.id if user else None,
            deleted=deleted,
        )

        logger.info(
            "ADMIN ALERT SENT | File=%s",
            filename,
        )

    except Exception:
        logger.exception(
            "ADMIN ALERT FAILED | File=%s",
            filename,
        )


async def debug_update_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """
    Debug handler used to confirm Telegram updates
    are reaching the bot.
    """

    logger.info(
        "🔎 UPDATE DEBUG | "
        "update_id=%s | "
        "message=%s | "
        "edited_message=%s | "
        "channel_post=%s | "
        "edited_channel_post=%s | "
        "callback_query=%s | "
        "my_chat_member=%s",
        update.update_id,
        bool(update.message),
        bool(update.edited_message),
        bool(update.channel_post),
        bool(update.edited_channel_post),
        bool(update.callback_query),
        bool(update.my_chat_member),
    )


def register_handlers(application):
    """
    Register all Telegram handlers.
    """

    # File/document handler.
    application.add_handler(
        MessageHandler(
            filters.Document.ALL,
            document_handler,
        ),
        group=0,
    )

    # Commands.
    application.add_handler(
        CommandHandler("start", start_command)
    )

    application.add_handler(
        CommandHandler("help", help_command)
    )

    application.add_handler(
        CommandHandler("id", id_command)
    )

    application.add_handler(
        CommandHandler("stats", stats_command)
    )

    application.add_handler(
        CommandHandler("groups", groups_command)
    )

    application.add_handler(
        CommandHandler("clearstats", clear_stats_command)
    )

    # Debug handler.
    application.add_handler(
        MessageHandler(
            filters.ALL,
            debug_update_handler,
        ),
        group=99,
    )

    logger.info(
        "Telegram handlers registered successfully."
    )

    logger.info(
        "📋 Document handler registered with filters.Document.ALL"
    )

    logger.info(
        "🔎 Debug update handler registered in group 99"
    )