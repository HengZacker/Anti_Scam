import logging

from telegram import Update
from telegram.constants import ChatType
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


def get_filename(update: Update) -> str | None:
    message = update.effective_message

    if not message:
        return None

    if message.document:
        return message.document.file_name

    return None


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
    status = "✅ DELETED" if deleted else "❌ DELETE FAILED"

    text = (
        "🛡️ <b>Telegram File Guard Alert</b>\n\n"
        f"<b>Status:</b> {status}\n"
        f"<b>File:</b> <code>{filename}</code>\n"
        f"<b>Extension:</b> <code>{extension}</code>\n\n"
        f"<b>Group:</b> {group_title}\n"
        f"<b>Group ID:</b> <code>{group_id}</code>\n\n"
        f"<b>User:</b> {username}\n"
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

        except Exception:
            logger.exception(
                "Could not send admin alert to %s",
                admin_id,
            )


async def start_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.effective_message

    if not message:
        return

    await message.reply_text(
        "🛡️ <b>Telegram File Guard</b>\n\n"
        "ខ្ញុំជួយការពារ Group ពី File ដែលអាចមានគ្រោះថ្នាក់។\n\n"
        "🚫 File ដែលត្រូវបាន Block:\n"
        "• .exe\n"
        "• .bat\n"
        "• .vbs\n"
        "• .ps1\n"
        "• .sh\n"
        "• .msi\n"
        "• .scr\n\n"
        "សូមបន្ថែម Bot ជា Admin "
        "ដើម្បីឲ្យខ្ញុំអាចលុប File បាន។",
        parse_mode="HTML",
    )


async def stats_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.effective_message

    if not message:
        return

    user = update.effective_user

    if not user:
        return

    if user.id not in settings.admin_ids:
        await message.reply_text(
            "❌ អ្នកមិនមានសិទ្ធិប្រើ Command នេះទេ។"
        )
        return

    database: Database = context.application.bot_data["database"]

    stats = await database.get_stats()

    await message.reply_text(
        "📊 <b>Telegram File Guard Statistics</b>\n\n"
        f"🗑️ Total detected: <b>{stats['total']}</b>\n"
        f"✅ Deleted: <b>{stats['successful']}</b>\n"
        f"❌ Failed: <b>{stats['failed']}</b>\n"
        f"👥 Groups: <b>{stats['groups']}</b>\n"
        f"👤 Users: <b>{stats['users']}</b>\n"
        f"📅 Today: <b>{stats['today']}</b>",
        parse_mode="HTML",
    )


async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.effective_message

    if not message:
        return

    await message.reply_text(
        "🛡️ <b>Telegram File Guard Help</b>\n\n"
        "/start - Bot information\n"
        "/help - Help\n"
        "/stats - Admin statistics\n\n"
        "Bot នឹងពិនិត្យ Document ក្នុង Group "
        "ហើយលុប File ដែលមាន Extension "
        "ត្រូវបាន Block។",
        parse_mode="HTML",
    )


async def document_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.effective_message

    if not message:
        return

    chat = update.effective_chat

    if not chat:
        return

    # Only monitor groups and supergroups.
    if chat.type not in {
        ChatType.GROUP,
        ChatType.SUPERGROUP,
    }:
        return

    filename = get_filename(update)

    if not filename:
        return

    if not is_blocked_filename(
        filename,
        settings.blocked_extensions,
    ):
        return

    extension = get_extension(filename)

    user = update.effective_user

    user_id = user.id if user else None

    if user:
        username = (
            f"@{user.username}"
            if user.username
            else user.full_name
        )
    else:
        username = "Unknown"

    group_title = chat.title or "Unknown Group"

    group_username = getattr(
        chat,
        "username",
        None,
    )

    deleted = False

    if settings.delete_enabled:
        try:
            deleted = await message.delete()

            logger.warning(
                "Deleted blocked file: %s | Group: %s",
                filename,
                group_title,
            )

        except Exception:
            logger.exception(
                "Failed to delete file %s",
                filename,
            )

    database: Database = context.application.bot_data["database"]

    await database.record_deletion(
        message_id=message.message_id,
        chat_id=chat.id,
        group_title=group_title,
        group_username=group_username,
        user_id=user_id,
        username=user.username if user else None,
        first_name=user.first_name if user else None,
        last_name=user.last_name if user else None,
        file_name=filename,
        file_extension=extension,
        reason="Blocked file extension",
        deleted_successfully=deleted,
    )

    if settings.alert_admins:
        await send_admin_alert(
            context,
            filename=filename,
            extension=extension,
            group_title=group_title,
            group_id=chat.id,
            username=username,
            user_id=user_id,
            deleted=deleted,
        )


def register_handlers(application):
    application.add_handler(
        MessageHandler(
            filters.Document.ALL & ~filters.COMMAND,
            document_handler,
        )
    )

    application.add_handler(
        CommandHandler("start", start_command)
    )

    application.add_handler(
        CommandHandler("help", help_command)
    )

    application.add_handler(
        CommandHandler("stats", stats_command)
    )