# Módulos de Antinuke: clave interna -> nombre para mostrar en el panel
MODULES = {
    "role_create": "Creación de roles",
    "role_delete": "Eliminación de roles",
    "role_update": "Edición de permisos de roles",
    "channel_create": "Creación de canales",
    "channel_delete": "Eliminación de canales",
    "channel_update": "Edición de permisos de canales",
    "ban": "Bans masivos",
    "kick": "Kicks masivos",
    "mute": "Timeouts masivos",
    "webhook": "Webhooks (crear/eliminar)",
    "bot_add": "Bots añadidos sin autorización",
    "guild_name": "Cambio de nombre del servidor",
    "guild_icon": "Cambio de ícono/banner del servidor",
    "invite_create": "Creación de invitaciones",
    "invite_delete": "Eliminación de invitaciones",
    "emoji": "Emojis/Stickers (crear/eliminar)",
    "voice_kick": "Desconexión/movimiento masivo en voz",
    "antiraid": "Anti-raid (uniones masivas)",
}

PUNISHMENTS = ("kick", "ban", "quarantine")

DEFAULT_LIMIT = 3
DEFAULT_WINDOW = 10  # segundos, fijo (no expuesto como comando)
DEFAULT_PUNISHMENT = "kick"

RAID_JOIN_LIMIT = 5
RAID_WINDOW = 10  # segundos
