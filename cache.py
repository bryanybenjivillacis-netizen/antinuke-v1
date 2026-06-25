import time

import database
from constants import MODULES, DEFAULT_LIMIT, DEFAULT_WINDOW, DEFAULT_PUNISHMENT

# guild_id -> { module: {"enabled": bool, "limit": int, "window": int, "punishment": str} }
modules_cache: dict = {}

# guild_id -> set(ids en whitelist)
whitelist_cache: dict = {}

# guild_id -> log_channel_id | None
log_channel_cache: dict = {}

# (guild_id, user_id, module) -> [timestamps]
action_tracker: dict = {}

# guild_id -> [timestamps de ingreso] (para antiraid)
join_tracker: dict = {}


async def load_guild(guild_id: int):
    """Carga la configuración de un servidor desde la base de datos a memoria."""
    rows = await database.get_all_modules(guild_id)
    modules_cache[guild_id] = {}
    configured = {r["module"] for r in rows}
    for r in rows:
        modules_cache[guild_id][r["module"]] = {
            "enabled": r["enabled"],
            "limit": r["limit_count"],
            "window": r["time_window"],
            "punishment": r["punishment"],
        }
    for module in MODULES:
        if module not in configured:
            modules_cache[guild_id][module] = {
                "enabled": False,
                "limit": DEFAULT_LIMIT,
                "window": DEFAULT_WINDOW,
                "punishment": DEFAULT_PUNISHMENT,
            }

    whitelist_cache[guild_id] = set(await database.get_whitelist(guild_id))

    settings = await database.get_guild_settings(guild_id)
    log_channel_cache[guild_id] = settings["log_channel_id"] if settings else None


async def load_all(bot):
    for guild in bot.guilds:
        await database.ensure_guild(guild.id)
        await load_guild(guild.id)


def register_action(guild_id: int, user_id: int, module: str, window: int) -> int:
    """Registra una acción y devuelve cuántas van dentro de la ventana de tiempo."""
    key = (guild_id, user_id, module)
    now = time.time()
    timestamps = [t for t in action_tracker.get(key, []) if now - t <= window]
    timestamps.append(now)
    action_tracker[key] = timestamps
    return len(timestamps)


def clear_action(guild_id: int, user_id: int, module: str):
    action_tracker.pop((guild_id, user_id, module), None)


def register_join(guild_id: int, window: int) -> int:
    now = time.time()
    timestamps = [t for t in join_tracker.get(guild_id, []) if now - t <= window]
    timestamps.append(now)
    join_tracker[guild_id] = timestamps
    return len(timestamps)
