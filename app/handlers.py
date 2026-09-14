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


# ============================================================
# HELPERS
# ============================================================

def get_database(
    context: ContextTypes.DEFAULT_TYPE,
) -> Database:

    database = (
        context.application.bot_data.get(
            "database"
        )
    )

    if database is None:

        raise RuntimeError(
            "Database is not available."
        )

    return database


def get_settings(
    context: ContextTypes.DEFAULT_TYPE,
) -> Settings:

    settings = (
        context.application.bot_data.get(
            "settings"
        )
    )

    if settings is None:

        raise RuntimeError(
            "Settings are not available."
        )

    return settings


def is_admin(
    user_id: int | None,
    settings: Settings,
) -> bool:

    if user_id is None:
        return False

    return user_id in settings.admin_ids


# ============================================================
# ADMIN ALERT
# ============================================================

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

    settings = get_settings(
        context
    )

    if not settings.alert_admins:

        logger.info(
            "ADMIN ALERTS DISABLED."
        )

        return

    status = (
        "DELETED"
        if deleted
        else "FAILED TO DELETE"
    )

    message = (
        "🚨 SECURITY ALERT\n\n"

        f"📄 File: {filename}\n"

        f"🔴 Extension: {extension}\n"

        f"📌 Status: {status}\n\n"

        f"👥 Group: {group_title}\n"

        f"🆔 Group ID: {group_id}\n\n"

        f"👤 User: {username}\n"

        f"🆔 User ID: "
        f"{user_id if user_id else 'Unknown'}"
    )

    for admin_id in settings.admin_ids:

        try:

            await context.bot.send_message(
                chat_id=admin_id,
                text=message,
            )

            logger.info(
                "ADMIN ALERT SENT | "
                "Admin=%s | File=%s",
                admin_id,
                filename,
            )

        except Exception:

            logger.exception(
                "ADMIN ALERT FAILED | "
                "Admin=%s | File=%s",
                admin_id,
                filename,
            )


# ============================================================
# /START
# ============================================================

async def start_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.effective_chat:
        return

    await update.effective_chat.send_message(
        "🛡️ Telegram File Guard is active."
    )


# ============================================================
# /HELP
# ============================================================

async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.effective_chat:
        return

    settings = get_settings(
        context
    )

    user_id = (
        update.effective_user.id
        if update.effective_user
        else None
    )

    # Hide admin help inside groups
    # from normal members.
    if (
        update.effective_chat.type
        in {"group", "supergroup"}
        and not is_admin(
            user_id,
            settings,
        )
    ):

        return

    text = (
        "🛡️ FILE GUARD HELP\n\n"

        "The bot automatically removes "
        "blocked file types from protected "
        "groups.\n\n"

        "Admin commands:\n"

        "/stats - View security statistics\n"

        "/groups - View protected groups\n"

        "/clearstats - Clear deletion statistics\n"

        "/id - Show your Telegram ID\n"

        "/help - Show this help"
    )

    await update.effective_chat.send_message(
        text
    )


# ============================================================
# /ID
# ============================================================

async def id_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if (
        not update.effective_user
        or not update.effective_chat
    ):

        return

    await update.effective_chat.send_message(
        f"🆔 Your Telegram ID:\n"
        f"`{update.effective_user.id}`",
        parse_mode="Markdown",
    )


# ============================================================
# /STATS
# ============================================================

async def stats_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if (
        not update.effective_user
        or not update.effective_chat
    ):

        return

    settings = get_settings(
        context
    )

    if not is_admin(
        update.effective_user.id,
        settings,
    ):

        logger.warning(
            "UNAUTHORIZED /stats | "
            "User=%s",
            update.effective_user.id,
        )

        return

    try:

        database = get_database(
            context
        )

        stats = await database.get_stats()

        text = (
            "📊 SECURITY STATISTICS\n\n"

            f"🗑️ Total detections: "
            f"{stats['total']}\n"

            f"✅ Successfully deleted: "
            f"{stats['successful']}\n"

            f"❌ Failed deletions: "
            f"{stats['failed']}\n"

            f"👥 Protected groups: "
            f"{stats['groups']}\n"

            f"👤 Unique users: "
            f"{stats['users']}\n"

            f"📅 Today: "
            f"{stats['today']}"
        )

        await update.effective_chat.send_message(
            text
        )

    except Exception:

        logger.exception(
            "FAILED /stats"
        )

        await update.effective_chat.send_message(
            "❌ Failed to load statistics."
        )


# ============================================================
# /GROUPS
# ============================================================

async def groups_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if (
        not update.effective_user
        or not update.effective_chat
    ):

        return

    settings = get_settings(
        context
    )

    if not is_admin(
        update.effective_user.id,
        settings,
    ):

        logger.warning(
            "UNAUTHORIZED /groups | "
            "User=%s",
            update.effective_user.id,
        )

        return

    try:

        database = get_database(
            context
        )

        groups = await database.get_groups()

        if not groups:

            await update.effective_chat.send_message(
                "📭 No protected groups found."
            )

            return

        lines = [
            "🛡️ PROTECTED GROUPS",
            "",
        ]

        for index, group in enumerate(
            groups,
            start=1,
        ):

            title = (
                group["title"]
                or "Unknown Group"
            )

            chat_id = group["chat_id"]

            username = group["username"]

            if username:

                group_name = (
                    f"{title} (@{username})"
                )

            else:

                group_name = title

            lines.append(
                f"{index}. {group_name}"
            )

            lines.append(
                f"   🆔 {chat_id}"
            )

        await update.effective_chat.send_message(
            "\n".join(lines)
        )

    except Exception:

        logger.exception(
            "FAILED /groups"
        )

        await update.effective_chat.send_message(
            "❌ Failed to load protected groups."
        )


# ============================================================
# /CLEARSTATS
# ============================================================

async def clear_stats_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if (
        not update.effective_user
        or not update.effective_chat
    ):

        return

    settings = get_settings(
        context
    )

    if not is_admin(
        update.effective_user.id,
        settings,
    ):

        logger.warning(
            "UNAUTHORIZED /clearstats | "
            "User=%s",
            update.effective_user.id,
        )

        return

    try:

        database = get_database(
            context
        )

        deleted_count = (
            await database.clear_statistics()
        )

        await update.effective_chat.send_message(
            "🧹 Statistics cleared successfully.\n\n"

            f"🗑️ Deleted records: "
            f"{deleted_count}"
        )

        logger.warning(
            "ADMIN CLEARED STATISTICS | "
            "Admin=%s | Records=%s",
            update.effective_user.id,
            deleted_count,
        )

    except Exception:

        logger.exception(
            "FAILED /clearstats"
        )

        await update.effective_chat.send_message(
            "❌ Failed to clear statistics."
        )


# ============================================================
# DOCUMENT HANDLER
# ============================================================

async def document_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    logger.warning(
        "🔥 DOCUMENT HANDLER TRIGGERED | "
        "update_id=%s",
        update.update_id,
    )

    # ========================================================
    # MESSAGE CHECK
    # ========================================================

    if not update.message:

        logger.warning(
            "DOCUMENT HANDLER EXIT | "
            "No message."
        )

        return

    message = update.message

    if not message.document:

        logger.warning(
            "DOCUMENT HANDLER EXIT | "
            "No document."
        )

        return

    chat = message.chat

    # ========================================================
    # GROUP ONLY
    # ========================================================

    if chat.type not in {
        "group",
        "supergroup",
    }:

        logger.info(
            "FILE IGNORED | "
            "Chat type=%s",
            chat.type,
        )

        return

    document = message.document

    filename = (
        document.file_name
        or ""
    )

    logger.warning(
        "📄 DOCUMENT FOUND | "
        "filename=%s | "
        "mime=%s | "
        "group=%s | "
        "group_id=%s",

        filename,

        document.mime_type,

        chat.title,

        chat.id,
    )

    # ========================================================
    # SETTINGS + DATABASE
    # ========================================================

    settings = get_settings(
        context
    )

    database = get_database(
        context
    )

    # ========================================================
    # BLOCK CHECK
    # ========================================================

    is_blocked = is_blocked_filename(
        filename,
        settings.blocked_extensions,
    )

    if not is_blocked:

        logger.info(
            "FILE ALLOWED | "
            "File=%s",
            filename,
        )

        return

    # ========================================================
    # EXTENSION
    # ========================================================

    extension = get_extension(
        filename
    )

    logger.warning(
        "🚨 BLOCKED FILE DETECTED | "
        "File=%s | "
        "Extension=%s | "
        "Group=%s",
        filename,
        extension,
        chat.title,
    )

    # ========================================================
    # USER
    # ========================================================

    user = message.from_user

    if user:

        display_username = (
            f"@{user.username}"
            if user.username
            else (
                user.first_name
                or "Unknown"
            )
        )

        user_id = user.id

        username = user.username

        first_name = user.first_name

        last_name = user.last_name

    else:

        display_username = "Unknown"

        user_id = None

        username = None

        first_name = None

        last_name = None

    # ========================================================
    # REGISTER GROUP
    # ========================================================

    try:

        await database.upsert_group(
            chat_id=chat.id,

            title=(
                chat.title
                or "Unknown Group"
            ),

            username=chat.username,

            chat_type=chat.type,
        )

    except Exception:

        logger.exception(
            "❌ GROUP UPSERT FAILED | "
            "Group=%s | ID=%s",
            chat.title,
            chat.id,
        )

    # ========================================================
    # DELETE FILE
    # ========================================================

    deleted = False

    if settings.dry_run:

        logger.warning(
            "⚠️ DRY RUN ENABLED | "
            "File will NOT be deleted."
        )

    elif not settings.delete_enabled:

        logger.warning(
            "⚠️ DELETE_ENABLED=false | "
            "File will NOT be deleted."
        )

    else:

        try:

            await message.delete()

            deleted = True

            logger.warning(
                "🗑️ FILE DELETED SUCCESSFULLY | "
                "File=%s | "
                "Group=%s | "
                "GroupID=%s",
                filename,
                chat.title,
                chat.id,
            )

        except Exception as delete_error:

            logger.error(
                "❌ FILE DELETE FAILED | "
                "File=%s | "
                "Group=%s | "
                "Error=%s",
                filename,
                chat.title,
                delete_error,
            )

    # ========================================================
    # RECORD EVENT
    #
    # IMPORTANT:
    # This happens whether deletion succeeded OR failed.
    # ========================================================

    try:

        record_id = (
            await database.record_deletion(

                message_id=(
                    message.message_id
                ),

                chat_id=chat.id,

                group_title=(
                    chat.title
                    or "Unknown Group"
                ),

                group_username=(
                    chat.username
                ),

                user_id=user_id,

                username=username,

                first_name=first_name,

                last_name=last_name,

                file_name=filename,

                file_extension=extension,

                reason=(
                    f"Blocked extension: "
                    f"{extension}"
                ),

                deleted_successfully=deleted,
            )
        )

        logger.warning(
            "📊 DELETION EVENT RECORDED | "
            "ID=%s | "
            "File=%s | "
            "Deleted=%s",
            record_id,
            filename,
            deleted,
        )

    except Exception as database_error:

        logger.error(
            "❌ DELETION EVENT DATABASE ERROR | "
            "File=%s | "
            "Group=%s | "
            "Error=%s",
            filename,
            chat.title,
            database_error,
        )

        logger.exception(
            "FULL DATABASE ERROR TRACE"
        )

    # ========================================================
    # ADMIN ALERT
    # ========================================================

    try:

        await send_admin_alert(

            context,

            filename=filename,

            extension=extension,

            group_title=(
                chat.title
                or "Unknown Group"
            ),

            group_id=chat.id,

            username=display_username,

            user_id=user_id,

            deleted=deleted,
        )

    except Exception:

        logger.exception(
            "❌ ADMIN ALERT ERROR | "
            "File=%s",
            filename,
        )


# ============================================================
# DEBUG UPDATE HANDLER
# ============================================================

async def debug_update_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

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


# ============================================================
# REGISTER HANDLERS
# ============================================================

def register_handlers(
    application,
):

    # ========================================================
    # DOCUMENT HANDLER
    # ========================================================

    application.add_handler(
        MessageHandler(
            filters.Document.ALL,
            document_handler,
        ),
        group=0,
    )

    # ========================================================
    # COMMANDS
    # ========================================================

    application.add_handler(
        CommandHandler(
            "start",
            start_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "help",
            help_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "id",
            id_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "stats",
            stats_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "groups",
            groups_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "clearstats",
            clear_stats_command,
        )
    )

    # ========================================================
    # DEBUG
    # ========================================================

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
        "📄 Document handler registered."
    )

    logger.info(
        "🔎 Debug handler registered."
    )