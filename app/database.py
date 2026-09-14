import logging
from typing import Any

import asyncpg


logger = logging.getLogger(__name__)


class Database:
    def __init__(
        self,
        database_url: str,
    ):
        self.database_url = database_url
        self.pool: asyncpg.Pool | None = None

    # ========================================================
    # CONNECTION
    # ========================================================

    async def connect(self):
        self.pool = await asyncpg.create_pool(
            dsn=self.database_url,
            min_size=1,
            max_size=5,
            command_timeout=30,
        )

        logger.info(
            "Connected to PostgreSQL."
        )

    async def close(self):
        if self.pool:
            await self.pool.close()
            self.pool = None

            logger.info(
                "Database connection closed."
            )

    def _require_pool(self):
        if not self.pool:
            raise RuntimeError(
                "Database pool is not connected."
            )

        return self.pool

    # ========================================================
    # TABLES
    # ========================================================

    async def create_tables(self):
        pool = self._require_pool()

        async with pool.acquire() as conn:

            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS protected_groups (
                    chat_id BIGINT PRIMARY KEY,
                    title TEXT NOT NULL,
                    username TEXT,
                    chat_type TEXT NOT NULL,
                    active BOOLEAN NOT NULL DEFAULT TRUE,
                    first_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    last_activity TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )

            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS deletion_events (
                    id BIGSERIAL PRIMARY KEY,

                    message_id BIGINT NOT NULL,
                    chat_id BIGINT NOT NULL,

                    group_title TEXT,
                    group_username TEXT,

                    user_id BIGINT,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,

                    file_name TEXT NOT NULL,
                    file_extension TEXT NOT NULL,

                    reason TEXT,

                    deleted_successfully BOOLEAN NOT NULL DEFAULT FALSE,

                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )

            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_deletion_events_chat_id
                ON deletion_events(chat_id);
                """
            )

            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_deletion_events_created_at
                ON deletion_events(created_at);
                """
            )

            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_deletion_events_extension
                ON deletion_events(file_extension);
                """
            )

        logger.info(
            "Database tables ready."
        )

    # ========================================================
    # GROUP TRACKING
    # ========================================================

    async def upsert_group(
        self,
        chat_id: int,
        title: str,
        username: str | None,
        chat_type: str,
    ):
        pool = self._require_pool()

        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO protected_groups (
                    chat_id,
                    title,
                    username,
                    chat_type,
                    active,
                    first_seen,
                    last_activity,
                    updated_at
                )
                VALUES (
                    $1,
                    $2,
                    $3,
                    $4,
                    TRUE,
                    NOW(),
                    NOW(),
                    NOW()
                )
                ON CONFLICT (chat_id)
                DO UPDATE SET
                    title = EXCLUDED.title,
                    username = EXCLUDED.username,
                    chat_type = EXCLUDED.chat_type,
                    active = TRUE,
                    last_activity = NOW(),
                    updated_at = NOW();
                """,
                chat_id,
                title,
                username,
                chat_type,
            )

    async def touch_group(
        self,
        chat_id: int,
    ):
        pool = self._require_pool()

        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE protected_groups
                SET
                    last_activity = NOW(),
                    updated_at = NOW(),
                    active = TRUE
                WHERE chat_id = $1
                """,
                chat_id,
            )

    async def deactivate_group(
        self,
        chat_id: int,
    ):
        pool = self._require_pool()

        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE protected_groups
                SET
                    active = FALSE,
                    updated_at = NOW()
                WHERE chat_id = $1
                """,
                chat_id,
            )

    async def delete_group(
        self,
        chat_id: int,
    ):
        pool = self._require_pool()

        async with pool.acquire() as conn:
            await conn.execute(
                """
                DELETE FROM protected_groups
                WHERE chat_id = $1
                """,
                chat_id,
            )

    async def get_groups(
        self,
    ) -> list[dict[str, Any]]:
        pool = self._require_pool()

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    chat_id,
                    title,
                    username,
                    chat_type,
                    first_seen,
                    last_activity
                FROM protected_groups
                WHERE active = TRUE
                ORDER BY title ASC
                """
            )

        return [
            dict(row)
            for row in rows
        ]

    # ========================================================
    # DELETION LOG
    # ========================================================

    async def record_deletion(
        self,
        *,
        message_id: int,
        chat_id: int,
        group_title: str,
        group_username: str | None,
        user_id: int | None,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
        file_name: str,
        file_extension: str,
        reason: str,
        deleted_successfully: bool,
    ):
        pool = self._require_pool()

        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO deletion_events (
                    message_id,
                    chat_id,
                    group_title,
                    group_username,
                    user_id,
                    username,
                    first_name,
                    last_name,
                    file_name,
                    file_extension,
                    reason,
                    deleted_successfully
                )
                VALUES (
                    $1,
                    $2,
                    $3,
                    $4,
                    $5,
                    $6,
                    $7,
                    $8,
                    $9,
                    $10,
                    $11,
                    $12
                )
                """,
                message_id,
                chat_id,
                group_title,
                group_username,
                user_id,
                username,
                first_name,
                last_name,
                file_name,
                file_extension,
                reason,
                deleted_successfully,
            )

    # ========================================================
    # STATISTICS
    # ========================================================

    async def get_stats(
        self,
    ) -> dict[str, int]:

        pool = self._require_pool()

        async with pool.acquire() as conn:

            total = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM deletion_events
                """
            )

            successful = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM deletion_events
                WHERE deleted_successfully = TRUE
                """
            )

            failed = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM deletion_events
                WHERE deleted_successfully = FALSE
                """
            )

            groups = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM protected_groups
                WHERE active = TRUE
                """
            )

            users = await conn.fetchval(
                """
                SELECT COUNT(DISTINCT user_id)
                FROM deletion_events
                WHERE user_id IS NOT NULL
                """
            )

            today = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM deletion_events
                WHERE created_at >= CURRENT_DATE
                """
            )

        return {
            "total": int(total or 0),
            "successful": int(successful or 0),
            "failed": int(failed or 0),
            "groups": int(groups or 0),
            "users": int(users or 0),
            "today": int(today or 0),
        }

    # ========================================================
    # CLEAR STATISTICS
    # ========================================================

    async def clear_statistics(self) -> int:
        """
        Delete all deletion history.

        IMPORTANT:
        - deletion_events WILL be cleared.
        - protected_groups WILL NOT be touched.
        - Bot group tracking will remain intact.

        Returns:
            Number of deletion records removed.
        """

        pool = self._require_pool()

        async with pool.acquire() as conn:

            deleted_count = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM deletion_events
                """
            )

            await conn.execute(
                """
                TRUNCATE TABLE deletion_events
                RESTART IDENTITY
                """
            )

        logger.warning(
            "Statistics cleared. %s deletion events removed.",
            deleted_count,
        )

        return int(deleted_count or 0)