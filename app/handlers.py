import logging
from html import escape

from telegram import Update
from telegram.constants import ChatMemberStatus, ChatType
from telegram.error import TelegramError
from telegram.ext import (
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from .config import settings
from .database import Database
from .filters import (
    get_extension,
    is_blocked_filename,
)

logger = logging.getLogger(__name__)


# ============================================================
# HELPERS
# ============================================================

def get_filename(update: Update) -> str | None:
    message = update.effective_message

    if not message:
        return None

    if message.document:
        return message.document.file_name

    return None


def is_admin(update: Update) -> bool:
    user = update.effective_user

    if not user:
        return False

    return user.id in settings.admin_ids


def get_database(context: ContextTypes.DEFAULT_TYPE) -> Database:
    database = context.application.bot_data.get("database")

    if not database:
        raise RuntimeError(
            "Database is not available in bot_data."
        )

    return database


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
    """
    Send a security alert to every configured admin.
    """

    if not settings.alert_admins:
        logger.warning(
            "Admin alerts are disabled because ALERT_ADMINS is false."
        )
        return

    if not settings.admin_ids:
        logger.error(
            "ADMIN_IDS is empty. Cannot send admin security alert."
        )
        return

    status = (
        "✅ DELETED SUCCESSFULLY"
        if deleted
        else "❌ DELETE FAILED"
    )

    text = (
        "🛡️ <b>Telegram File Guard Alert</b>\n\n"
        f"<b>Status:</b> {status}\n"
        f"<b>File:</b> <code>{escape(filename)}</code>\n"
        f"<b>Extension:</b> <code>{escape(extension)}</code>\n\n"
        f"<b>Group:</b> {escape(group_title)}\n"
        f"<b>Group ID:</b> <code>{group_id}</code>\n\n"
        f"<b>User:</b> {escape(username)}\n"
        f"<b>User ID:</b> "
        f"<code>{user_id if user_id else 'Unknown'}</code>\n\n"
        "⚠️ This file type is blocked by the security policy."
    )

    for admin_id in settings.admin_ids:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=text,
                parse_mode="HTML",
            )

            logger.info(
                "Security alert sent successfully | "
                "Admin: %s | File: %s | Group: %s",
                admin_id,
                filename,
                group_title,
            )

        except TelegramError as exc:
            logger.error(
                "FAILED to send security alert | "
                "Admin: %s | File: %s | Error: %s",
                admin_id,
                filename,
                exc,
            )

        except Exception:
            logger.exception(
                "Unexpected error while sending security alert "
                "to admin %s",
                admin_id,
            )

# ============================================================
# GROUP TRACKING
# ============================================================

async def track_group_activity(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """
    Automatically register/update groups where the bot receives
    messages.
    """

    chat = update.effective_chat

    if not chat:
        return

    if chat.type not in {
        ChatType.GROUP,
        ChatType.SUPERGROUP,
    }:
        return

    try:
        database = get_database(context)

        await database.upsert_group(
            chat_id=chat.id,
            title=chat.title or "Unknown Group",
            username=chat.username,
            chat_type=chat.type,
        )

        logger.debug(
            "Tracked group activity: %s (%s)",
            chat.title,
            chat.id,
        )

    except Exception:
        logger.exception(
            "Failed to track group activity for %s",
            chat.id,
        )


# ============================================================
# START
# ============================================================

async def start_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user = update.effective_user

    if not user:
        return

    if update.effective_chat.type == ChatType.PRIVATE:
        await update.effective_message.reply_text(
            "🛡️ Telegram File Guard\n\n"
            "I protect Telegram groups by automatically "
            "deleting blocked file types.\n\n"
            "🔐 Security features:\n"
            "• Automatic blocked-file deletion\n"
            "• Admin security alerts\n"
            "• Deletion statistics\n"
            "• Group monitoring\n\n"
            "Use /help to see available commands."
        )

    else:
        await update.effective_message.reply_text(
            "🛡️ Telegram File Guard is active in this group."
        )


# ============================================================
# ID COMMAND
# ============================================================

async def id_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user = update.effective_user
    chat = update.effective_chat

    if not user or not chat:
        return

    username = (
        f"@{user.username}"
        if user.username
        else "No username"
    )

    text = (
        "🆔 <b>Your Telegram Information</b>\n\n"
        f"<b>User ID:</b> <code>{user.id}</code>\n"
        f"<b>Username:</b> {escape(username)}\n\n"
        f"<b>Chat ID:</b> <code>{chat.id}</code>\n"
        f"<b>Chat Type:</b> <code>{chat.type}</code>"
    )

    if chat.title:
        text += (
            f"\n<b>Chat Title:</b> "
            f"{escape(chat.title)}"
        )

    await update.effective_message.reply_text(
        text,
        parse_mode="HTML",
    )


# ============================================================
# STATS COMMAND
# ============================================================

async def stats_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not is_admin(update):
        await update.effective_message.reply_text(
            "⛔ This command is only available to the bot admin."
        )
        return

    try:
        database = get_database(context)
        stats = await database.get_stats()

        text = (
            "📊 <b>Telegram File Guard Statistics</b>\n\n"
            f"📁 Total blocked files: "
            f"<b>{stats['total']}</b>\n"
            f"✅ Successfully deleted: "
            f"<b>{stats['successful']}</b>\n"
            f"❌ Failed to delete: "
            f"<b>{stats['failed']}</b>\n"
            f"👥 Protected groups: "
            f"<b>{stats['groups']}</b>\n"
            f"👤 Users detected: "
            f"<b>{stats['users']}</b>\n"
            f"📅 Blocked today: "
            f"<b>{stats['today']}</b>"
        )

        await update.effective_message.reply_text(
            text,
            parse_mode="HTML",
        )

    except Exception:
        logger.exception("Failed to get statistics.")

        await update.effective_message.reply_text(
            "❌ Failed to retrieve statistics."
        )


# ============================================================
# GROUPS COMMAND
# ============================================================

async def groups_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """
    Show all groups where the bot is currently active.

    Admin only.
    """

    if not is_admin(update):
        await update.effective_message.reply_text(
            "⛔ This command is only available to the bot admin."
        )
        return

    try:
        database = get_database(context)

        groups = await database.get_groups()

        if not groups:
            await update.effective_message.reply_text(
                "📋 <b>Protected Groups</b>\n\n"
                "No active groups are currently registered.",
                parse_mode="HTML",
            )
            return

        active_groups = []
        removed_groups = 0

        # Get the bot's own Telegram account
        bot_user = await context.bot.get_me()

        for group in groups:
            chat_id = group["chat_id"]

            try:
                member = await context.bot.get_chat_member(
                    chat_id=chat_id,
                    user_id=bot_user.id,
                )

                # Bot is no longer inside the group
                if member.status in {
                    ChatMemberStatus.LEFT,
                    ChatMemberStatus.BANNED,
                }:
                    await database.delete_group(chat_id)

                    removed_groups += 1

                    logger.info(
                        "Removed inactive group from database: "
                        "%s (%s)",
                        group["title"],
                        chat_id,
                    )

                    continue

                active_groups.append(group)

            except TelegramError as exc:
                error_text = str(exc).lower()

                # These errors normally mean the bot cannot access
                # the group anymore.
                if (
                    "chat not found" in error_text
                    or "kicked" in error_text
                    or "not a member" in error_text
                    or "user not found" in error_text
                ):
                    await database.delete_group(chat_id)

                    removed_groups += 1

                    logger.info(
                        "Removed inaccessible group from database: "
                        "%s (%s)",
                        group["title"],
                        chat_id,
                    )

                    continue

                # For temporary/API errors, don't delete the group.
                logger.warning(
                    "Could not verify group %s (%s): %s",
                    group["title"],
                    chat_id,
                    exc,
                )

                active_groups.append(group)

            except Exception:
                logger.exception(
                    "Unexpected error checking group %s",
                    chat_id,
                )

                # Don't delete on unknown errors.
                active_groups.append(group)

        if not active_groups:
            text = (
                "📋 <b>Protected Groups</b>\n\n"
                "No active groups found."
            )

            if removed_groups:
                text += (
                    f"\n\n🧹 Removed "
                    f"<b>{removed_groups}</b> inactive group(s)."
                )

            await update.effective_message.reply_text(
                text,
                parse_mode="HTML",
            )
            return

        lines = [
            "📋 <b>Protected Groups</b>",
            "",
            f"🛡️ Active groups: <b>{len(active_groups)}</b>",
            "",
        ]

        for index, group in enumerate(active_groups, start=1):
            title = escape(
                group["title"] or "Unknown Group"
            )

            chat_type = escape(
                group["chat_type"] or "unknown"
            )

            username = group["username"]

            if username:
                username_text = f"@{escape(username)}"
            else:
                username_text = "Private group"

            lines.extend(
                [
                    f"<b>{index}. {title}</b>",
                    f"   🆔 <code>{group['chat_id']}</code>",
                    f"   💬 {username_text}",
                    f"   📌 Type: <code>{chat_type}</code>",
                    "",
                ]
            )

        if removed_groups:
            lines.append(
                f"🧹 Removed "
                f"<b>{removed_groups}</b> inactive group(s)."
            )

        await update.effective_message.reply_text(
            "\n".join(lines),
            parse_mode="HTML",
        )

    except Exception:
        logger.exception(
            "Failed to retrieve protected groups."
        )

        await update.effective_message.reply_text(
            "❌ Failed to retrieve protected groups."
        )


# ============================================================
# CLEAR STATISTICS
# ============================================================

async def clear_stats_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not is_admin(update):
        await update.effective_message.reply_text(
            "⛔ This command is only available to the bot admin."
        )
        return

    if not context.args or context.args[0].lower() != "confirm":
        await update.effective_message.reply_text(
            "⚠️ <b>Warning</b>\n\n"
            "This will permanently delete all deletion statistics.\n\n"
            "Your protected groups will NOT be deleted.\n\n"
            "To continue, use:\n"
            "<code>/clearstats confirm</code>",
            parse_mode="HTML",
        )
        return

    try:
        database = get_database(context)

        deleted_count = await database.clear_statistics()

        await update.effective_message.reply_text(
            "🧹 <b>Statistics Cleared</b>\n\n"
            f"Deleted records: <b>{deleted_count}</b>\n\n"
            "✅ Protected group tracking was kept.",
            parse_mode="HTML",
        )

        logger.warning(
            "Admin %s cleared statistics. "
            "%s records removed.",
            update.effective_user.id,
            deleted_count,
        )

    except Exception:
        logger.exception(
            "Failed to clear statistics."
        )

        await update.effective_message.reply_text(
            "❌ Failed to clear statistics."
        )


# ============================================================
# HELP COMMAND
# ============================================================

async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user_is_admin = is_admin(update)

    text = (
        "🛡️ <b>Telegram File Guard</b>\n\n"
        "I automatically detect and delete blocked "
        "file types in protected groups.\n\n"
        "<b>Available commands:</b>\n"
        "/start - Start the bot\n"
        "/help - Show this help message\n"
        "/id - Show your Telegram ID"
    )

    if user_is_admin:
        text += (
            "\n\n<b>🔐 Admin Commands:</b>\n"
            "/stats - View deletion statistics\n"
            "/groups - View protected groups\n"
            "/clearstats - Clear deletion statistics"
        )

    await update.effective_message.reply_text(
        text,
        parse_mode="HTML",
    )


# ============================================================
# DOCUMENT HANDLER
# ============================================================
async def document_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if not message or not chat:
        return

    # Only monitor groups
    if chat.type not in {"group", "supergroup"}:
        return

    filename = get_filename(update)

    if not filename:
        return

    # Check blocked extension
    if not is_blocked_filename(
        filename,
        settings.blocked_extensions,
    ):
        return

    extension = get_extension(filename)

    group_title = chat.title or "Unknown Group"
    group_username = chat.username

    user_id = user.id if user else None

    database = get_database(context)

    # --------------------------------------------------
    # 1. SAVE / UPDATE GROUP
    # --------------------------------------------------
    try:
        await database.upsert_group(
            chat_id=chat.id,
            title=group_title,
            username=group_username,
            chat_type=chat.type,
        )

        logger.info(
            "GROUP TRACKED | %s | %s",
            group_title,
            chat.id,
        )

    except Exception:
        logger.exception(
            "GROUP TRACKING FAILED | %s",
            group_title,
        )

    # --------------------------------------------------
    # 2. DELETE FILE
    # --------------------------------------------------
    deleted = False

    if settings.delete_enabled:
        try:
            await message.delete()

            deleted = True

            logger.warning(
                "FILE DELETED | File=%s | Extension=%s | Group=%s",
                filename,
                extension,
                group_title,
            )

        except Exception:
            logger.exception(
                "FILE DELETE FAILED | File=%s | Group=%s",
                filename,
                group_title,
            )

    else:
        logger.warning(
            "DELETE DISABLED | File=%s",
            filename,
        )

    # --------------------------------------------------
    # 3. RECORD STATISTICS
    # --------------------------------------------------
    try:
        logger.info(
            "RECORDING STAT | File=%s | Deleted=%s",
            filename,
            deleted,
        )

        record_id = await database.record_deletion(
            message_id=message.message_id,
            chat_id=chat.id,
            group_title=group_title,
            group_username=group_username,
            user_id=user.id if user else None,
            username=user.username if user else None,
            first_name=user.first_name if user else None,
            last_name=user.last_name if user else None,
            file_name=filename,
            file_extension=extension,
            reason="Blocked file extension",
            deleted_successfully=deleted,
        )

        logger.info(
            "STAT RECORDED SUCCESSFULLY | "
            "Record ID=%s | File=%s | Deleted=%s",
            record_id,
            filename,
            deleted,
        )

    except Exception as exc:
        logger.exception(
            "STAT RECORDING FAILED | "
            "File=%s | Group=%s | Error=%s",
            filename,
            group_title,
            exc,
        )

    # --------------------------------------------------
    # 4. SEND ADMIN ALERT
    # --------------------------------------------------
    if deleted and settings.alert_admins:
        try:
            logger.info(
                "SENDING ADMIN ALERT | File=%s | Group=%s",
                filename,
                group_title,
            )

            await send_admin_alert(
                context,
                filename=filename,
                extension=extension,
                group_title=group_title,
                group_id=chat.id,
                username=(
                    f"@{user.username}"
                    if user and user.username
                    else (
                        user.first_name
                    if user and user.first_name
                    else "Unknown"
                    )
                ),
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
# ============================================================
# REGISTER HANDLERS
# ============================================================

def register_handlers(application):
    application.add_handler(
        MessageHandler(
            filters.Document.ALL & ~filters.COMMAND,
            document_handler,
        )
    )

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

    logger.info(
        "Telegram handlers registered successfully."
    )