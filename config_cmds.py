import asyncio
import datetime
import io

import aiohttp
import discord
from discord.ext import commands

import cache
import database
from checks import is_owner_or_botowner
from constants import MODULES, PUNISHMENTS
from cogs.events import activate_lockdown, deactivate_lockdown


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _overwrite_to_dict(overwrite: discord.PermissionOverwrite) -> dict:
    """Serializa un PermissionOverwrite a dict {perm: allow|deny|None}."""
    result = {}
    for perm, value in overwrite:
        result[perm] = value  # True / False / None
    return result


def _dict_to_overwrite(data: dict) -> discord.PermissionOverwrite:
    return discord.PermissionOverwrite(**{k: v for k, v in data.items()})


async def _fetch_image_bytes(url: str) -> bytes | None:
    if not url:
        return None
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url) as r:
                if r.status == 200:
                    return await r.read()
    except Exception:
        pass
    return None


# ─────────────────────────────────────────────────────────────────────────────
#  Lockdown con snapshot exacto
# ─────────────────────────────────────────────────────────────────────────────

async def activate_lockdown_exact(guild: discord.Guild):
    """Guarda los permisos actuales canal por canal y bloquea send_messages."""
    snapshot = {}
    for channel in guild.text_channels:
        ch_snap = {}
        for target, overwrite in channel.overwrites.items():
            kind = "role" if isinstance(target, discord.Role) else "member"
            ch_snap[str(target.id)] = {
                "kind": kind,
                "overwrite": _overwrite_to_dict(overwrite),
            }
        snapshot[str(channel.id)] = ch_snap
        try:
            ow = channel.overwrites_for(guild.default_role)
            ow.send_messages = False
            await channel.set_permissions(guild.default_role, overwrite=ow, reason="Antinuke: lockdown")
        except discord.Forbidden:
            continue

    await database.save_lockdown_snapshot(guild.id, snapshot)
    await database.set_lockdown(guild.id, True)


async def deactivate_lockdown_exact(guild: discord.Guild):
    """Restaura los permisos exactos guardados antes del lockdown."""
    snapshot = await database.get_lockdown_snapshot(guild.id)
    await database.set_lockdown(guild.id, False)

    if not snapshot:
        # Sin snapshot: solo quitar la restricción de send_messages
        for channel in guild.text_channels:
            try:
                ow = channel.overwrites_for(guild.default_role)
                ow.send_messages = None
                await channel.set_permissions(guild.default_role, overwrite=ow, reason="Antinuke: fin de lockdown")
            except discord.Forbidden:
                continue
        return

    for channel in guild.text_channels:
        ch_snap = snapshot.get(str(channel.id))
        if ch_snap is None:
            continue
        try:
            # Primero limpiar overwrites actuales del @everyone
            ow_default = channel.overwrites_for(guild.default_role)
            ow_default.send_messages = None
            await channel.set_permissions(guild.default_role, overwrite=ow_default, reason="Antinuke: fin lockdown")

            # Restaurar cada overwrite guardado
            for target_id_str, info in ch_snap.items():
                target_id = int(target_id_str)
                if info["kind"] == "role":
                    target = guild.get_role(target_id)
                else:
                    target = guild.get_member(target_id)
                if target is None:
                    continue
                ow = _dict_to_overwrite(info["overwrite"])
                await channel.set_permissions(target, overwrite=ow, reason="Antinuke: fin lockdown restaurado")
        except discord.Forbidden:
            continue

    await database.clear_lockdown_snapshot(guild.id)


# ─────────────────────────────────────────────────────────────────────────────
#  Cog principal
# ─────────────────────────────────────────────────────────────────────────────

class AntinukeConfig(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── Panel antinuke ────────────────────────────────────────────────────────

    @commands.group(invoke_without_command=True)
    @is_owner_or_botowner()
    async def antinuke(self, ctx: commands.Context):
        guild_modules = cache.modules_cache.get(ctx.guild.id, {})
        activos, inactivos = [], []
        for key, name in MODULES.items():
            data = guild_modules.get(key, {})
            lim  = data.get("limit", 3)
            cast = data.get("punishment", "kick")
            if data.get("enabled"):
                activos.append(f"✅ `{key}` — límite: **{lim}** | castigo: **{cast}**")
            else:
                inactivos.append(f"`{key}`")

        embed = discord.Embed(title="🛡️ Panel de Antinuke", color=discord.Color.blurple())
        if activos:
            embed.add_field(name=f"🟢 Activos ({len(activos)})", value="\n".join(activos), inline=False)
        if inactivos:
            embed.add_field(name=f"🔴 Inactivos ({len(inactivos)})", value="  ".join(inactivos), inline=False)
        embed.add_field(
            name="⚙️ Comandos",
            value=(
                f"`{ctx.prefix}antinuke on/off` — todos\n"
                f"`{ctx.prefix}antinuke on/off <módulo>` — uno\n"
                f"`{ctx.prefix}antinuke limite all/módulo <n>`\n"
                f"`{ctx.prefix}antinuke castigo all/módulo <kick/ban/quarantine>`"
            ),
            inline=False,
        )
        embed.set_footer(text="Solo el dueño del servidor y el dueño del bot pueden usar estos comandos.")
        await ctx.send(embed=embed)

    @antinuke.command(name="on")
    @is_owner_or_botowner()
    async def antinuke_on(self, ctx: commands.Context, module: str = None):
        if module is None:
            for key in MODULES:
                await database.set_module_enabled(ctx.guild.id, key, True)
            await cache.load_guild(ctx.guild.id)
            embed = discord.Embed(title="✅ Antinuke activado", description=f"Todos los **{len(MODULES)} módulos** activados.", color=discord.Color.green())
            embed.set_footer(text=f"Usa {ctx.prefix}antinuke para ver el estado.")
            await ctx.send(embed=embed)
        else:
            module = module.lower()
            if module not in MODULES:
                await ctx.send(f"⚠️ Módulo inválido. Usa `{ctx.prefix}antinuke` para ver la lista.")
                return
            await database.set_module_enabled(ctx.guild.id, module, True)
            await cache.load_guild(ctx.guild.id)
            await ctx.send(f"✅ Módulo **{MODULES[module]}** activado.")

    @antinuke.command(name="off")
    @is_owner_or_botowner()
    async def antinuke_off(self, ctx: commands.Context, module: str = None):
        if module is None:
            for key in MODULES:
                await database.set_module_enabled(ctx.guild.id, key, False)
            await cache.load_guild(ctx.guild.id)
            embed = discord.Embed(title="❌ Antinuke desactivado", description=f"Todos los **{len(MODULES)} módulos** desactivados.", color=discord.Color.red())
            await ctx.send(embed=embed)
        else:
            module = module.lower()
            if module not in MODULES:
                await ctx.send(f"⚠️ Módulo inválido. Usa `{ctx.prefix}antinuke` para ver la lista.")
                return
            await database.set_module_enabled(ctx.guild.id, module, False)
            await cache.load_guild(ctx.guild.id)
            await ctx.send(f"❌ Módulo **{MODULES[module]}** desactivado.")

    @antinuke.command(name="limite")
    @is_owner_or_botowner()
    async def antinuke_limit(self, ctx: commands.Context, module: str, cantidad: int):
        if cantidad < 1:
            await ctx.send("⚠️ El límite debe ser ≥ 1.")
            return
        module = module.lower()
        if module == "all":
            for key in MODULES:
                await database.set_module_limit(ctx.guild.id, key, cantidad)
            await cache.load_guild(ctx.guild.id)
            await ctx.send(f"📊 Límite de **todos los módulos** → **{cantidad}**.")
        elif module not in MODULES:
            await ctx.send(f"⚠️ Módulo inválido.")
        else:
            await database.set_module_limit(ctx.guild.id, module, cantidad)
            await cache.load_guild(ctx.guild.id)
            await ctx.send(f"📊 Límite de **{MODULES[module]}** → **{cantidad}**.")

    @antinuke.command(name="castigo")
    @is_owner_or_botowner()
    async def antinuke_punishment(self, ctx: commands.Context, module: str, castigo: str):
        castigo = castigo.lower()
        if castigo not in PUNISHMENTS:
            await ctx.send(f"⚠️ Castigo inválido. Opciones: `{'`, `'.join(PUNISHMENTS)}`")
            return
        module = module.lower()
        if module == "all":
            for key in MODULES:
                await database.set_module_punishment(ctx.guild.id, key, castigo)
            await cache.load_guild(ctx.guild.id)
            await ctx.send(f"⚖️ Castigo de **todos los módulos** → `{castigo}`.")
        elif module not in MODULES:
            await ctx.send(f"⚠️ Módulo inválido.")
        else:
            await database.set_module_punishment(ctx.guild.id, module, castigo)
            await cache.load_guild(ctx.guild.id)
            await ctx.send(f"⚖️ Castigo de **{MODULES[module]}** → `{castigo}`.")

    # ── Whitelist ─────────────────────────────────────────────────────────────

    @commands.group(invoke_without_command=True)
    @is_owner_or_botowner()
    async def whitelist(self, ctx: commands.Context):
        ids = cache.whitelist_cache.get(ctx.guild.id, set())
        if not ids:
            await ctx.send("📋 La whitelist está vacía.")
            return
        embed = discord.Embed(title="📋 Whitelist", color=discord.Color.blurple())
        embed.description = "\n".join(f"• <@{i}> (`{i}`)" for i in ids)
        embed.set_footer(text=f"{len(ids)} entradas")
        await ctx.send(embed=embed)

    @whitelist.command(name="add")
    @is_owner_or_botowner()
    async def whitelist_add(self, ctx: commands.Context, member: discord.Member):
        await database.add_whitelist(ctx.guild.id, member.id)
        await cache.load_guild(ctx.guild.id)
        await ctx.send(f"✅ {member.mention} añadido a la whitelist.")

    @whitelist.command(name="remove")
    @is_owner_or_botowner()
    async def whitelist_remove(self, ctx: commands.Context, member: discord.Member):
        await database.remove_whitelist(ctx.guild.id, member.id)
        await cache.load_guild(ctx.guild.id)
        await ctx.send(f"❌ {member.mention} eliminado de la whitelist.")

    # ── Logs ──────────────────────────────────────────────────────────────────

    @commands.command(name="logs")
    @is_owner_or_botowner()
    async def set_logs(self, ctx: commands.Context, canal: discord.TextChannel):
        await database.set_log_channel(ctx.guild.id, canal.id)
        await cache.load_guild(ctx.guild.id)
        await ctx.send(f"📝 Canal de logs → {canal.mention}.")

    # ── Lockdown con permisos exactos ─────────────────────────────────────────

    @commands.command(name="lockdown")
    @is_owner_or_botowner()
    async def lockdown(self, ctx: commands.Context, estado: str):
        estado = estado.lower()
        if estado == "on":
            msg = await ctx.send("🔒 Activando lockdown y guardando permisos…")
            await activate_lockdown_exact(ctx.guild)
            await msg.edit(content="🔒 Servidor bloqueado. Los permisos exactos han sido guardados.")
        elif estado == "off":
            msg = await ctx.send("🔓 Restaurando permisos previos…")
            await deactivate_lockdown_exact(ctx.guild)
            await msg.edit(content="🔓 Servidor desbloqueado. Permisos restaurados exactamente como estaban.")
        else:
            await ctx.send(f"Uso: `{ctx.prefix}lockdown on` / `{ctx.prefix}lockdown off`")

    # ── Backup completo ───────────────────────────────────────────────────────

    @commands.group(invoke_without_command=True)
    @is_owner_or_botowner()
    async def backup(self, ctx: commands.Context):
        data, created_at = await database.get_backup(ctx.guild.id)
        embed = discord.Embed(title="💾 Backup del servidor", color=discord.Color.blurple())
        if data:
            ts = int(created_at.timestamp()) if created_at else 0
            embed.description = (
                f"📅 Último backup: <t:{ts}:F>\n\n"
                f"• **{len(data.get('roles', []))}** roles\n"
                f"• **{len(data.get('categories', []))}** categorías\n"
                f"• **{len(data.get('text_channels', []))}** canales de texto\n"
                f"• **{len(data.get('voice_channels', []))}** canales de voz\n"
                f"• **{len(data.get('members', []))}** miembros registrados\n"
                f"• **{len(data.get('bans', []))}** bans guardados\n"
                f"• Icono: {'✅' if data.get('icon_url') else '❌'} | "
                f"Banner: {'✅' if data.get('banner_url') else '❌'}"
            )
        else:
            embed.description = "No hay ningún backup guardado."
        embed.add_field(
            name="Comandos",
            value=(
                f"`{ctx.prefix}backup create` — Crear backup completo\n"
                f"`{ctx.prefix}backup restore` — Restaurar todo\n"
                f"`{ctx.prefix}recover` — Invitar a miembros que faltan"
            ),
            inline=False,
        )
        await ctx.send(embed=embed)

    @backup.command(name="create")
    @is_owner_or_botowner()
    async def backup_create(self, ctx: commands.Context):
        msg = await ctx.send("💾 Creando backup completo del servidor…")
        guild = ctx.guild

        # ── Roles (ordenados por posición) ────────────────────────────────
        roles_data = []
        for role in sorted(guild.roles, key=lambda r: r.position):
            if role == guild.default_role:
                continue
            roles_data.append({
                "id": role.id,
                "name": role.name,
                "color": role.color.value,
                "permissions": role.permissions.value,
                "position": role.position,
                "hoist": role.hoist,
                "mentionable": role.mentionable,
            })

        # ── Categorías ────────────────────────────────────────────────────
        cats_data = []
        for cat in sorted(guild.categories, key=lambda c: c.position):
            overwrites = {}
            for target, ow in cat.overwrites.items():
                overwrites[str(target.id)] = {
                    "kind": "role" if isinstance(target, discord.Role) else "member",
                    "overwrite": _overwrite_to_dict(ow),
                }
            cats_data.append({
                "id": cat.id,
                "name": cat.name,
                "position": cat.position,
                "overwrites": overwrites,
            })

        # ── Canales de texto ──────────────────────────────────────────────
        text_data = []
        for ch in sorted(guild.text_channels, key=lambda c: c.position):
            overwrites = {}
            for target, ow in ch.overwrites.items():
                overwrites[str(target.id)] = {
                    "kind": "role" if isinstance(target, discord.Role) else "member",
                    "overwrite": _overwrite_to_dict(ow),
                }
            text_data.append({
                "id": ch.id,
                "name": ch.name,
                "topic": ch.topic,
                "slowmode": ch.slowmode_delay,
                "nsfw": ch.is_nsfw(),
                "position": ch.position,
                "category_id": ch.category_id,
                "overwrites": overwrites,
            })

        # ── Canales de voz ────────────────────────────────────────────────
        voice_data = []
        for ch in sorted(guild.voice_channels, key=lambda c: c.position):
            overwrites = {}
            for target, ow in ch.overwrites.items():
                overwrites[str(target.id)] = {
                    "kind": "role" if isinstance(target, discord.Role) else "member",
                    "overwrite": _overwrite_to_dict(ow),
                }
            voice_data.append({
                "id": ch.id,
                "name": ch.name,
                "bitrate": ch.bitrate,
                "user_limit": ch.user_limit,
                "position": ch.position,
                "category_id": ch.category_id,
                "overwrites": overwrites,
            })

        # ── Miembros y sus roles ──────────────────────────────────────────
        members_data = []
        for member in guild.members:
            if member.bot:
                continue
            members_data.append({
                "id": member.id,
                "name": str(member),
                "roles": [r.id for r in member.roles if r != guild.default_role],
            })

        # ── Bans ──────────────────────────────────────────────────────────
        bans_data = []
        try:
            async for ban_entry in guild.bans():
                bans_data.append({
                    "id": ban_entry.user.id,
                    "name": str(ban_entry.user),
                    "reason": ban_entry.reason,
                })
        except discord.Forbidden:
            pass

        # ── Info del servidor ─────────────────────────────────────────────
        data = {
            "name": guild.name,
            "description": guild.description,
            "icon_url": str(guild.icon.url) if guild.icon else None,
            "banner_url": str(guild.banner.url) if guild.banner else None,
            "roles": roles_data,
            "categories": cats_data,
            "text_channels": text_data,
            "voice_channels": voice_data,
            "members": members_data,
            "bans": bans_data,
        }

        await database.save_backup(guild.id, data)

        embed = discord.Embed(title="💾 Backup creado", color=discord.Color.green())
        embed.description = (
            f"✅ Backup completo guardado.\n\n"
            f"• **{len(roles_data)}** roles\n"
            f"• **{len(cats_data)}** categorías\n"
            f"• **{len(text_data)}** canales de texto\n"
            f"• **{len(voice_data)}** canales de voz\n"
            f"• **{len(members_data)}** miembros\n"
            f"• **{len(bans_data)}** bans\n"
            f"• Icono: {'✅' if data['icon_url'] else '❌'} | "
            f"Banner: {'✅' if data['banner_url'] else '❌'}"
        )
        await msg.edit(content=None, embed=embed)

    @backup.command(name="restore")
    @is_owner_or_botowner()
    async def backup_restore(self, ctx: commands.Context):
        data, created_at = await database.get_backup(ctx.guild.id)
        if not data:
            await ctx.send("⚠️ No hay ningún backup guardado. Usa `.backup create` primero.")
            return

        guild = ctx.guild
        msg = await ctx.send("♻️ Restaurando backup… esto puede tardar un momento.")
        report = []

        # ── Descripción del servidor ──────────────────────────────────────
        try:
            if data.get("description") is not None:
                await guild.edit(description=data["description"], reason="Backup restore")
            report.append("✅ Descripción restaurada")
        except Exception as e:
            report.append(f"⚠️ Descripción: {e}")

        # ── Icono ─────────────────────────────────────────────────────────
        if data.get("icon_url"):
            icon_bytes = await _fetch_image_bytes(data["icon_url"])
            if icon_bytes:
                try:
                    await guild.edit(icon=icon_bytes, reason="Backup restore")
                    report.append("✅ Icono restaurado")
                except Exception as e:
                    report.append(f"⚠️ Icono: {e}")

        # ── Banner ────────────────────────────────────────────────────────
        if data.get("banner_url"):
            banner_bytes = await _fetch_image_bytes(data["banner_url"])
            if banner_bytes:
                try:
                    await guild.edit(banner=banner_bytes, reason="Backup restore")
                    report.append("✅ Banner restaurado")
                except Exception as e:
                    report.append(f"⚠️ Banner: {e}")

        # ── Roles ─────────────────────────────────────────────────────────
        roles_created = 0
        role_id_map = {}  # old_id -> new discord.Role
        existing_roles = {r.name: r for r in guild.roles}

        for role_data in sorted(data.get("roles", []), key=lambda r: r["position"]):
            existing = existing_roles.get(role_data["name"])
            if existing:
                try:
                    await existing.edit(
                        permissions=discord.Permissions(role_data["permissions"]),
                        color=discord.Color(role_data["color"]),
                        hoist=role_data.get("hoist", False),
                        mentionable=role_data.get("mentionable", False),
                        reason="Backup restore",
                    )
                    role_id_map[role_data["id"]] = existing
                except Exception:
                    role_id_map[role_data["id"]] = existing
            else:
                try:
                    new_role = await guild.create_role(
                        name=role_data["name"],
                        permissions=discord.Permissions(role_data["permissions"]),
                        color=discord.Color(role_data["color"]),
                        hoist=role_data.get("hoist", False),
                        mentionable=role_data.get("mentionable", False),
                        reason="Backup restore",
                    )
                    role_id_map[role_data["id"]] = new_role
                    roles_created += 1
                except Exception:
                    pass
            await asyncio.sleep(0.3)

        report.append(f"✅ Roles: {roles_created} creados, {len(role_id_map) - roles_created} actualizados")

        # ── Roles de miembros ─────────────────────────────────────────────
        roles_restored = 0
        for member_data in data.get("members", []):
            member = guild.get_member(member_data["id"])
            if member is None:
                continue
            current_role_ids = {r.id for r in member.roles}
            for old_role_id in member_data.get("roles", []):
                new_role = role_id_map.get(old_role_id)
                if new_role and new_role.id not in current_role_ids:
                    try:
                        await member.add_roles(new_role, reason="Backup restore: roles de miembro")
                        roles_restored += 1
                    except Exception:
                        pass
            await asyncio.sleep(0.1)

        report.append(f"✅ Roles de miembros: {roles_restored} asignaciones restauradas")

        # ── Categorías ────────────────────────────────────────────────────
        cats_created = 0
        cat_id_map = {}
        existing_cats = {c.name: c for c in guild.categories}

        for cat_data in sorted(data.get("categories", []), key=lambda c: c["position"]):
            cat = existing_cats.get(cat_data["name"])
            if cat is None:
                try:
                    overwrites = _build_overwrites(guild, role_id_map, cat_data.get("overwrites", {}))
                    cat = await guild.create_category(
                        name=cat_data["name"],
                        overwrites=overwrites,
                        reason="Backup restore",
                    )
                    cats_created += 1
                except Exception:
                    pass
            cat_id_map[cat_data["id"]] = cat
            await asyncio.sleep(0.3)

        report.append(f"✅ Categorías: {cats_created} creadas")

        # ── Canales de texto ──────────────────────────────────────────────
        text_created = 0
        existing_text = {c.name: c for c in guild.text_channels}

        for ch_data in sorted(data.get("text_channels", []), key=lambda c: c["position"]):
            ch = existing_text.get(ch_data["name"])
            category = cat_id_map.get(ch_data.get("category_id"))
            if ch is None:
                try:
                    overwrites = _build_overwrites(guild, role_id_map, ch_data.get("overwrites", {}))
                    await guild.create_text_channel(
                        name=ch_data["name"],
                        topic=ch_data.get("topic"),
                        slowmode_delay=ch_data.get("slowmode", 0),
                        nsfw=ch_data.get("nsfw", False),
                        category=category,
                        overwrites=overwrites,
                        reason="Backup restore",
                    )
                    text_created += 1
                except Exception:
                    pass
            else:
                try:
                    overwrites = _build_overwrites(guild, role_id_map, ch_data.get("overwrites", {}))
                    await ch.edit(
                        topic=ch_data.get("topic"),
                        slowmode_delay=ch_data.get("slowmode", 0),
                        nsfw=ch_data.get("nsfw", False),
                        category=category,
                        reason="Backup restore",
                    )
                    for target, ow in overwrites.items():
                        await ch.set_permissions(target, overwrite=ow, reason="Backup restore")
                except Exception:
                    pass
            await asyncio.sleep(0.3)

        report.append(f"✅ Canales de texto: {text_created} creados")

        # ── Canales de voz ────────────────────────────────────────────────
        voice_created = 0
        existing_voice = {c.name: c for c in guild.voice_channels}

        for ch_data in sorted(data.get("voice_channels", []), key=lambda c: c["position"]):
            ch = existing_voice.get(ch_data["name"])
            category = cat_id_map.get(ch_data.get("category_id"))
            if ch is None:
                try:
                    overwrites = _build_overwrites(guild, role_id_map, ch_data.get("overwrites", {}))
                    await guild.create_voice_channel(
                        name=ch_data["name"],
                        bitrate=min(ch_data.get("bitrate", 64000), guild.bitrate_limit),
                        user_limit=ch_data.get("user_limit", 0),
                        category=category,
                        overwrites=overwrites,
                        reason="Backup restore",
                    )
                    voice_created += 1
                except Exception:
                    pass
            await asyncio.sleep(0.3)

        report.append(f"✅ Canales de voz: {voice_created} creados")

        # ── Bans ──────────────────────────────────────────────────────────
        unbanned = 0
        try:
            current_bans = {entry.user.id async for entry in guild.bans()}
            saved_ban_ids = {b["id"] for b in data.get("bans", [])}
            # Desbanear a quien no debería estar baneado (no estaba en la lista)
            for user_id in current_bans - saved_ban_ids:
                try:
                    user = await ctx.bot.fetch_user(user_id)
                    await guild.unban(user, reason="Backup restore: no estaba en lista de bans")
                    unbanned += 1
                    await asyncio.sleep(0.3)
                except Exception:
                    pass
            report.append(f"✅ Bans: {unbanned} usuarios desbaneados")
        except discord.Forbidden:
            report.append("⚠️ Bans: sin permisos para ver/gestionar bans")

        # ── Resultado ─────────────────────────────────────────────────────
        embed = discord.Embed(title="♻️ Restore completado", color=discord.Color.green())
        embed.description = "\n".join(report)
        embed.set_footer(text="Algunas acciones pueden haber fallado si el bot no tenía permisos suficientes.")
        await msg.edit(content=None, embed=embed)

    # ── Recover: invitar miembros que faltan ──────────────────────────────────

    @commands.command(name="recover")
    @is_owner_or_botowner()
    async def recover(self, ctx: commands.Context):
        """Compara el backup con los miembros actuales y envía DM de invitación a los que faltan."""
        data, created_at = await database.get_backup(ctx.guild.id)
        if not data:
            await ctx.send("⚠️ No hay backup guardado. Usa `.backup create` primero.")
            return

        current_ids = {m.id for m in ctx.guild.members if not m.bot}
        saved_members = data.get("members", [])
        missing = [m for m in saved_members if m["id"] not in current_ids]

        if not missing:
            await ctx.send("✅ No falta ningún miembro del backup en el servidor.")
            return

        # Crear invitación
        try:
            invite = await ctx.channel.create_invite(max_age=86400, max_uses=0, reason="Recover: invitar miembros")
        except discord.Forbidden:
            await ctx.send("⚠️ No tengo permisos para crear invitaciones en este canal.")
            return

        msg = await ctx.send(
            f"📨 Encontré **{len(missing)}** miembros que no están en el servidor. "
            f"Enviando invitaciones por DM…"
        )

        sent, failed = 0, 0
        for member_data in missing:
            try:
                user = await ctx.bot.fetch_user(member_data["id"])
                embed = discord.Embed(
                    title=f"👋 ¡Te invitamos de vuelta a {ctx.guild.name}!",
                    description=(
                        f"Notamos que ya no estás en el servidor **{ctx.guild.name}**.\n\n"
                        f"Si quieres volver, usa el enlace de abajo. ¡Te esperamos!\n\n"
                        f"🔗 {invite.url}"
                    ),
                    color=discord.Color.blurple(),
                )
                if ctx.guild.icon:
                    embed.set_thumbnail(url=ctx.guild.icon.url)
                await user.send(embed=embed)
                sent += 1
            except Exception:
                failed += 1
            await asyncio.sleep(0.5)

        embed = discord.Embed(title="📨 Recover completado", color=discord.Color.green())
        embed.description = (
            f"• **{sent}** invitaciones enviadas por DM\n"
            f"• **{failed}** fallaron (usuarios con DMs cerrados)\n"
            f"• Enlace de invitación: {invite.url}"
        )
        await msg.edit(content=None, embed=embed)


def _build_overwrites(guild, role_id_map, raw_overwrites):
    """Construye un dict de overwrites a partir del snapshot guardado."""
    result = {}
    for target_id_str, info in raw_overwrites.items():
        target_id = int(target_id_str)
        if info["kind"] == "role":
            target = role_id_map.get(target_id) or guild.get_role(target_id)
        else:
            target = guild.get_member(target_id)
        if target is None:
            continue
        result[target] = _dict_to_overwrite(info["overwrite"])
    return result


async def setup(bot: commands.Bot):
    await bot.add_cog(AntinukeConfig(bot))
