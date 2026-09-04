from datetime import datetime, timezone
from typing import Any

from psycopg_pool import AsyncConnectionPool


class Database:

    def __init__(self, database_url: str):
        self.database_url = database_url

        self.pool: AsyncConnectionPool | None = None

    async def connect(self):

        self.pool = AsyncConnectionPool(
            conninfo=self.database_url,
            min_size=1,
            max_size=5,
            open=False,
        )

        await self.pool.open()

        await self.create_tables()

    async def close(self):

        if self.pool:
            await self.pool.close()

    async def create_tables(self):

        if not self.pool:
            raise RuntimeError("Database not connected.")

        async with self.pool.connection() as conn:

            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS deletion_events (
                    id BIGSERIAL PRIMARY KEY,

                    telegram_message_id BIGINT,
                    telegram_chat_id BIGINT NOT NULL,

                    group_title TEXT,
                    group_username TEXT,

                    user_id BIGINT,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,

                    file_name TEXT NOT NULL,
                    file_extension TEXT NOT NULL,

                    reason TEXT NOT NULL,

                    deleted_successfully BOOLEAN NOT NULL DEFAULT FALSE,

                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
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
                idx_deletion_events_chat_id
                ON deletion_events(telegram_chat_id);
                """
            )

            await conn.commit()

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

        if not self.pool:
            raise RuntimeError("Database not connected.")

        async with self.pool.connection() as conn:

            await conn.execute(
                """
                INSERT INTO deletion_events (
                    telegram_message_id,
                    telegram_chat_id,
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
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s
                )
                """,
                (
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
                ),
            )

            await conn.commit()

    async def get_stats(self) -> dict[str, Any]:

        if not self.pool:
            raise RuntimeError("Database not connected.")

        async with self.pool.connection() as conn:

            total = await conn.execute(
                """
                SELECT COUNT(*)
                FROM deletion_events
                """
            )

            total_row = await total.fetchone()

            successful = await conn.execute(
                """
                SELECT COUNT(*)
                FROM deletion_events
                WHERE deleted_successfully = TRUE
                """
            )

            successful_row = await successful.fetchone()

            failed = await conn.execute(
                """
                SELECT COUNT(*)
                FROM deletion_events
                WHERE deleted_successfully = FALSE
                """
            )

            failed_row = await failed.fetchone()

            groups = await conn.execute(
                """
                SELECT COUNT(DISTINCT telegram_chat_id)
                FROM deletion_events
                """
            )

            groups_row = await groups.fetchone()

            users = await conn.execute(
                """
                SELECT COUNT(DISTINCT user_id)
                FROM deletion_events
                WHERE user_id IS NOT NULL
                """
            )

            users_row = await users.fetchone()

            today = await conn.execute(
                """
                SELECT COUNT(*)
                FROM deletion_events
                WHERE created_at >= CURRENT_DATE
                """
            )

            today_row = await today.fetchone()

            return {
                "total": total_row[0],
                "successful": successful_row[0],
                "failed": failed_row[0],
                "groups": groups_row[0],
                "users": users_row[0],
                "today": today_row[0],
            }

    async def get_recent_events(
        self,
        limit: int = 50,
    ):

        if not self.pool:
            raise RuntimeError("Database not connected.")

        limit = max(
            1,
            min(limit, 200),
        )

        async with self.pool.connection() as conn:

            cursor = await conn.execute(
                """
                SELECT
                    id,
                    telegram_message_id,
                    telegram_chat_id,
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
                    created_at
                FROM deletion_events
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (limit,),
            )

            rows = await cursor.fetchall()

            columns = [
                "id",
                "telegram_message_id",
                "telegram_chat_id",
                "group_title",
                "group_username",
                "user_id",
                "username",
                "first_name",
                "last_name",
                "file_name",
                "file_extension",
                "reason",
                "deleted_successfully",
                "created_at",
            ]

            return [
                dict(zip(columns, row))
                for row in rows
            ]