import discord
from discord.ext import commands

import cache
import config
import database
from constants import MODULES, RAID_WINDOW


def is_protected(guild: discord.Guild, user_id: int) -> bool:
    """El dueño del servidor y el dueño del bot nunca son castigados."""
    if user_id == config.OWNER_ID:
        return True
    if guild and user_id == guild.owner_id:
        return True
    return user_id in cache.whitelist_cache.get(guild.id, set())


async def get_recent_executor(guild: discord.Guild, action: discord.AuditLogAction, target_id: int = None):
    """Busca en el audit log quién ejecutó la acción más reciente (últimos 5 segundos)."""
    try:
        async for entry in guild.audit_logs(limit=5, action=action):
            if target_id is not None and (not entry.target or entry.target.id != target_id):
                continue
            age = (discord.utils.utcnow() - entry.created_at).total_seconds()
            if age <= 5:
                return entry.user
    except discord.Forbidden:
        return None
    return None


async def send_log(guild: discord.Guild, message: str):
    channel_id = cache.log_channel_cache.get(guild.id)
    if not channel_id:
        return
    channel = guild.get_channel(channel_id)
    if channel:
        try:
            await channel.send(message)
        except discord.Forbidden:
            pass


async def apply_punishment(guild: discord.Guild, member: discord.Member, punishment: str, reason: str):
    try:
        if punishment == "kick":
            await guild.kick(member, reason=reason)
        elif punishment == "ban":
            await guild.ban(member, reason=reason)
        elif punishment == "quarantine":
            roles = [r for r in member.roles if r != guild.default_role]
            if roles:
                await member.remove_roles(*roles, reason=reason)
    except discord.Forbidden:
        pass


async def handle_violation(guild: discord.Guild, module: str, executor, reason: str):
    if executor is None or guild is None:
        return
    if is_protected(guild, executor.id):
        return

    settings = cache.modules_cache.get(guild.id, {}).get(module)
    if not settings or not settings["enabled"]:
        return

    count = cache.register_action(guild.id, executor.id, module, settings["window"])
    if count < settings["limit"]:
        return

    cache.clear_action(guild.id, executor.id, module)
    member = guild.get_member(executor.id)
    if member is None:
        return

    await apply_punishment(guild, member, settings["punishment"], reason)
    await send_log(
        guild,
        f"🛡️ **Antinuke** — Módulo `{MODULES[module]}`\n"
        f"Usuario: {member} (`{member.id}`)\n"
        f"Acción: {reason}\n"
        f"Castigo aplicado: **{settings['punishment']}**",
    )


async def activate_lockdown(guild: discord.Guild):
    await database.set_lockdown(guild.id, True)
    for channel in guild.text_channels:
        try:
            overwrite = channel.overwrites_for(guild.default_role)
            overwrite.send_messages = False
            await channel.set_permissions(guild.default_role, overwrite=overwrite, reason="Antinuke: lockdown")
        except discord.Forbidden:
            continue


async def deactivate_lockdown(guild: discord.Guild):
    await database.set_lockdown(guild.id, False)
    for channel in guild.text_channels:
        try:
            overwrite = channel.overwrites_for(guild.default_role)
            overwrite.send_messages = None
            await channel.set_permissions(guild.default_role, overwrite=overwrite, reason="Antinuke: fin de lockdown")
        except discord.Forbidden:
            continue


class AntinukeEvents(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        await database.ensure_guild(guild.id)
        await cache.load_guild(guild.id)

    # ---------- Roles ----------

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        executor = await get_recent_executor(role.guild, discord.AuditLogAction.role_create, role.id)
        await handle_violation(role.guild, "role_create", executor, "Creó un rol")

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        executor = await get_recent_executor(role.guild, discord.AuditLogAction.role_delete, role.id)
        await handle_violation(role.guild, "role_delete", executor, "Eliminó un rol")

    @commands.Cog.listener()
    async def on_guild_role_update(self, before: discord.Role, after: discord.Role):
        if before.permissions == after.permissions:
            return
        executor = await get_recent_executor(after.guild, discord.AuditLogAction.role_update, after.id)
        await handle_violation(after.guild, "role_update", executor, f"Editó los permisos del rol {after.name}")

    # ---------- Canales ----------

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        executor = await get_recent_executor(channel.guild, discord.AuditLogAction.channel_create, channel.id)
        await handle_violation(channel.guild, "channel_create", executor, "Creó un canal")

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        executor = await get_recent_executor(channel.guild, discord.AuditLogAction.channel_delete, channel.id)
        await handle_violation(channel.guild, "channel_delete", executor, "Eliminó un canal")

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel):
        if before.overwrites == after.overwrites:
            return
        executor = await get_recent_executor(after.guild, discord.AuditLogAction.channel_update, after.id)
        await handle_violation(after.guild, "channel_update", executor, f"Editó permisos del canal {after.name}")

    # ---------- Bans / Kicks / Mutes ----------

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        executor = await get_recent_executor(guild, discord.AuditLogAction.ban, user.id)
        await handle_violation(guild, "ban", executor, f"Baneó a {user}")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        executor = await get_recent_executor(member.guild, discord.AuditLogAction.kick, member.id)
        if executor:
            await handle_violation(member.guild, "kick", executor, f"Expulsó a {member}")

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.timed_out_until == after.timed_out_until or after.timed_out_until is None:
            return
        executor = await get_recent_executor(after.guild, discord.AuditLogAction.member_update, after.id)
        await handle_violation(after.guild, "mute", executor, f"Silenció a {after}")

    # ---------- Webhooks ----------

    @commands.Cog.listener()
    async def on_webhooks_update(self, channel: discord.abc.GuildChannel):
        for action in (discord.AuditLogAction.webhook_create, discord.AuditLogAction.webhook_delete):
            executor = await get_recent_executor(channel.guild, action)
            if executor:
                await handle_violation(channel.guild, "webhook", executor, "Modificó webhooks")
                break

    # ---------- Bots / Anti-raid ----------

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot:
            executor = await get_recent_executor(member.guild, discord.AuditLogAction.bot_add, member.id)
            await handle_violation(member.guild, "bot_add", executor, f"Añadió al bot {member}")
            return

        settings = cache.modules_cache.get(member.guild.id, {}).get("antiraid")
        if not settings or not settings["enabled"]:
            return
        count = cache.register_join(member.guild.id, RAID_WINDOW)
        if count >= settings["limit"]:
            await activate_lockdown(member.guild)
            await send_log(
                member.guild,
                f"🛡️ **Antinuke** — Módulo `Anti-raid`\n"
                f"Se detectaron {count} ingresos en {RAID_WINDOW}s. Servidor bloqueado automáticamente.",
            )

    # ---------- Servidor ----------

    @commands.Cog.listener()
    async def on_guild_update(self, before: discord.Guild, after: discord.Guild):
        if before.name != after.name:
            executor = await get_recent_executor(after, discord.AuditLogAction.guild_update)
            await handle_violation(after, "guild_name", executor, "Cambió el nombre del servidor")
        if before.icon != after.icon:
            executor = await get_recent_executor(after, discord.AuditLogAction.guild_update)
            await handle_violation(after, "guild_icon", executor, "Cambió el ícono del servidor")

    # ---------- Invitaciones ----------

    @commands.Cog.listener()
    async def on_invite_create(self, invite: discord.Invite):
        if invite.inviter:
            await handle_violation(invite.guild, "invite_create", invite.inviter, "Creó una invitación")

    @commands.Cog.listener()
    async def on_invite_delete(self, invite: discord.Invite):
        executor = await get_recent_executor(invite.guild, discord.AuditLogAction.invite_delete)
        await handle_violation(invite.guild, "invite_delete", executor, "Eliminó una invitación")

    # ---------- Emojis / Stickers ----------

    @commands.Cog.listener()
    async def on_guild_emojis_update(self, guild: discord.Guild, before, after):
        action = (
            discord.AuditLogAction.emoji_create
            if len(after) > len(before)
            else discord.AuditLogAction.emoji_delete
        )
        executor = await get_recent_executor(guild, action)
        await handle_violation(guild, "emoji", executor, "Modificó emojis/stickers")

    # ---------- Voz ----------

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if before.channel is None or after.channel is not None:
            return
        for action in (discord.AuditLogAction.member_disconnect, discord.AuditLogAction.member_move):
            executor = await get_recent_executor(member.guild, action)
            if executor and executor.id != member.id:
                await handle_violation(member.guild, "voice_kick", executor, f"Desconectó a {member} de voz")
                break


async def setup(bot: commands.Bot):
    await bot.add_cog(AntinukeEvents(bot))
