import json
import asyncpg

import config

pool: asyncpg.Pool = None


async def init_db():
    global pool
    pool = await asyncpg.create_pool(config.DATABASE_URL)
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id BIGINT PRIMARY KEY,
                log_channel_id BIGINT,
                lockdown BOOLEAN NOT NULL DEFAULT FALSE
            );
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS antinuke_modules (
                guild_id BIGINT NOT NULL,
                module TEXT NOT NULL,
                enabled BOOLEAN NOT NULL DEFAULT FALSE,
                limit_count INT NOT NULL DEFAULT 3,
                time_window INT NOT NULL DEFAULT 10,
                punishment TEXT NOT NULL DEFAULT 'kick',
                PRIMARY KEY (guild_id, module)
            );
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS whitelist (
                guild_id BIGINT NOT NULL,
                entity_id BIGINT NOT NULL,
                PRIMARY KEY (guild_id, entity_id)
            );
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS backups (
                guild_id BIGINT PRIMARY KEY,
                data JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );
        """)


async def ensure_guild(guild_id: int):
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO guild_settings (guild_id) VALUES ($1) ON CONFLICT DO NOTHING",
            guild_id,
        )


async def get_guild_settings(guild_id: int):
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT * FROM guild_settings WHERE guild_id = $1", guild_id
        )


async def set_log_channel(guild_id: int, channel_id: int):
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO guild_settings (guild_id, log_channel_id) VALUES ($1, $2)
               ON CONFLICT (guild_id) DO UPDATE SET log_channel_id = $2""",
            guild_id, channel_id,
        )


async def set_lockdown(guild_id: int, value: bool):
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO guild_settings (guild_id, lockdown) VALUES ($1, $2)
               ON CONFLICT (guild_id) DO UPDATE SET lockdown = $2""",
            guild_id, value,
        )


async def get_all_modules(guild_id: int):
    async with pool.acquire() as conn:
        return await conn.fetch(
            "SELECT * FROM antinuke_modules WHERE guild_id = $1", guild_id
        )


async def set_module_enabled(guild_id: int, module: str, enabled: bool):
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO antinuke_modules (guild_id, module, enabled) VALUES ($1, $2, $3)
               ON CONFLICT (guild_id, module) DO UPDATE SET enabled = $3""",
            guild_id, module, enabled,
        )


async def set_module_limit(guild_id: int, module: str, limit_count: int):
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO antinuke_modules (guild_id, module, limit_count) VALUES ($1, $2, $3)
               ON CONFLICT (guild_id, module) DO UPDATE SET limit_count = $3""",
            guild_id, module, limit_count,
        )


async def set_module_punishment(guild_id: int, module: str, punishment: str):
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO antinuke_modules (guild_id, module, punishment) VALUES ($1, $2, $3)
               ON CONFLICT (guild_id, module) DO UPDATE SET punishment = $3""",
            guild_id, module, punishment,
        )


async def get_whitelist(guild_id: int):
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT entity_id FROM whitelist WHERE guild_id = $1", guild_id
        )
        return [r["entity_id"] for r in rows]


async def add_whitelist(guild_id: int, entity_id: int):
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO whitelist (guild_id, entity_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
            guild_id, entity_id,
        )


async def remove_whitelist(guild_id: int, entity_id: int):
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM whitelist WHERE guild_id = $1 AND entity_id = $2",
            guild_id, entity_id,
        )


async def save_backup(guild_id: int, data: dict):
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO backups (guild_id, data, created_at) VALUES ($1, $2, now())
               ON CONFLICT (guild_id) DO UPDATE SET data = $2, created_at = now()""",
            guild_id, json.dumps(data),
        )


async def get_backup(guild_id: int):
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT data FROM backups WHERE guild_id = $1", guild_id
        )
        return json.loads(row["data"]) if row else None
