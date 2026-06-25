import discord
from discord.ext import commands

import cache
import database
from checks import is_owner_or_botowner
from constants import MODULES, PUNISHMENTS
from cogs.events import activate_lockdown, deactivate_lockdown


class AntinukeConfig(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.group(invoke_without_command=True)
    @is_owner_or_botowner()
    async def antinuke(self, ctx: commands.Context):
        """Muestra el panel de antinuke del servidor."""
        guild_modules = cache.modules_cache.get(ctx.guild.id, {})

        activos = []
        inactivos = []
        for key, name in MODULES.items():
            data = guild_modules.get(key, {})
            lim = data.get("limit", 3)
            cast = data.get("punishment", "kick")
            if data.get("enabled"):
                activos.append(f"✅ `{key}` — límite: **{lim}** | castigo: **{cast}**")
            else:
                inactivos.append(f"❌ `{key}`")

        embed = discord.Embed(
            title="🛡️ Panel de Antinuke",
            color=discord.Color.blurple(),
        )

        if activos:
            embed.add_field(
                name=f"🟢 Módulos activos ({len(activos)})",
                value="\n".join(activos),
                inline=False,
            )
        if inactivos:
            embed.add_field(
                name=f"🔴 Módulos inactivos ({len(inactivos)})",
                value="  ".join(f"`{k}`" for k in [i.split("`")[1] for i in inactivos]),
                inline=False,
            )

        embed.add_field(
            name="⚙️ Comandos rápidos",
            value=(
                f"`{ctx.prefix}antinuke on` — Activar **todos**\n"
                f"`{ctx.prefix}antinuke off` — Desactivar **todos**\n"
                f"`{ctx.prefix}antinuke on <módulo>` — Activar uno\n"
                f"`{ctx.prefix}antinuke off <módulo>` — Desactivar uno\n"
                f"`{ctx.prefix}antinuke limite all <n>` — Límite a todos\n"
                f"`{ctx.prefix}antinuke limite <módulo> <n>` — Límite a uno\n"
                f"`{ctx.prefix}antinuke castigo all <kick/ban/quarantine>` — Castigo a todos\n"
                f"`{ctx.prefix}antinuke castigo <módulo> <kick/ban/quarantine>` — Castigo a uno"
            ),
            inline=False,
        )
        embed.set_footer(text="Solo el dueño del servidor y el dueño del bot pueden usar estos comandos.")
        await ctx.send(embed=embed)

    @antinuke.command(name="on")
    @is_owner_or_botowner()
    async def antinuke_on(self, ctx: commands.Context, module: str = None):
        if module is None:
            # Activar todos
            for key in MODULES:
                await database.set_module_enabled(ctx.guild.id, key, True)
            await cache.load_guild(ctx.guild.id)
            embed = discord.Embed(
                title="✅ Antinuke activado",
                description=f"Todos los **{len(MODULES)} módulos** han sido activados.",
                color=discord.Color.green(),
            )
            embed.set_footer(text=f"Usa {ctx.prefix}antinuke para ver el estado actual.")
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
            # Desactivar todos
            for key in MODULES:
                await database.set_module_enabled(ctx.guild.id, key, False)
            await cache.load_guild(ctx.guild.id)
            embed = discord.Embed(
                title="❌ Antinuke desactivado",
                description=f"Todos los **{len(MODULES)} módulos** han sido desactivados.",
                color=discord.Color.red(),
            )
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
        module = module.lower()
        if cantidad < 1:
            await ctx.send("⚠️ El límite debe ser mayor o igual a 1.")
            return
        if module == "all":
            for key in MODULES:
                await database.set_module_limit(ctx.guild.id, key, cantidad)
            await cache.load_guild(ctx.guild.id)
            await ctx.send(f"📊 Límite de **todos los módulos** establecido en **{cantidad}**.")
        elif module not in MODULES:
            await ctx.send(f"⚠️ Módulo inválido. Usa `{ctx.prefix}antinuke` para ver la lista.")
        else:
            await database.set_module_limit(ctx.guild.id, module, cantidad)
            await cache.load_guild(ctx.guild.id)
            await ctx.send(f"📊 Límite de **{MODULES[module]}** establecido en **{cantidad}**.")

    @antinuke.command(name="castigo")
    @is_owner_or_botowner()
    async def antinuke_punishment(self, ctx: commands.Context, module: str, castigo: str):
        module = module.lower()
        castigo = castigo.lower()
        if castigo not in PUNISHMENTS:
            await ctx.send(f"⚠️ Castigo inválido. Opciones: `{'`, `'.join(PUNISHMENTS)}`")
            return
        if module == "all":
            for key in MODULES:
                await database.set_module_punishment(ctx.guild.id, key, castigo)
            await cache.load_guild(ctx.guild.id)
            await ctx.send(f"⚖️ Castigo de **todos los módulos** establecido en `{castigo}`.")
        elif module not in MODULES:
            await ctx.send(f"⚠️ Módulo inválido. Usa `{ctx.prefix}antinuke` para ver la lista.")
        else:
            await database.set_module_punishment(ctx.guild.id, module, castigo)
            await cache.load_guild(ctx.guild.id)
            await ctx.send(f"⚖️ Castigo de **{MODULES[module]}** establecido en `{castigo}`.")

    # ── Whitelist ──────────────────────────────────────────────────────────

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

    # ── Logs / Lockdown / Backup ───────────────────────────────────────────

    @commands.command(name="logs")
    @is_owner_or_botowner()
    async def set_logs(self, ctx: commands.Context, canal: discord.TextChannel):
        await database.set_log_channel(ctx.guild.id, canal.id)
        await cache.load_guild(ctx.guild.id)
        await ctx.send(f"📝 Canal de logs establecido en {canal.mention}.")

    @commands.command(name="lockdown")
    @is_owner_or_botowner()
    async def lockdown(self, ctx: commands.Context, estado: str):
        estado = estado.lower()
        if estado == "on":
            await activate_lockdown(ctx.guild)
            await ctx.send("🔒 Servidor bloqueado.")
        elif estado == "off":
            await deactivate_lockdown(ctx.guild)
            await ctx.send("🔓 Servidor desbloqueado.")
        else:
            await ctx.send(f"Uso: `{ctx.prefix}lockdown on` / `{ctx.prefix}lockdown off`")

    @commands.group(invoke_without_command=True)
    @is_owner_or_botowner()
    async def backup(self, ctx: commands.Context):
        embed = discord.Embed(title="💾 Backup", color=discord.Color.blurple())
        embed.description = (
            f"`{ctx.prefix}backup create` — Crear backup de roles y canales\n"
            f"`{ctx.prefix}backup restore` — Restaurar roles desde el backup"
        )
        await ctx.send(embed=embed)

    @backup.command(name="create")
    @is_owner_or_botowner()
    async def backup_create(self, ctx: commands.Context):
        data = {
            "roles": [
                {"name": r.name, "permissions": r.permissions.value, "color": r.color.value}
                for r in ctx.guild.roles if r != ctx.guild.default_role
            ],
            "channels": [
                {"name": c.name, "type": str(c.type), "category": c.category.name if c.category else None}
                for c in ctx.guild.channels
            ],
        }
        await database.save_backup(ctx.guild.id, data)
        embed = discord.Embed(
            title="💾 Backup creado",
            description=f"Se guardaron **{len(data['roles'])} roles** y **{len(data['channels'])} canales**.",
            color=discord.Color.green(),
        )
        await ctx.send(embed=embed)

    @backup.command(name="restore")
    @is_owner_or_botowner()
    async def backup_restore(self, ctx: commands.Context):
        data = await database.get_backup(ctx.guild.id)
        if not data:
            await ctx.send("⚠️ No hay ningún backup guardado.")
            return
        creados = 0
        for role_data in data["roles"]:
            if not any(r.name == role_data["name"] for r in ctx.guild.roles):
                await ctx.guild.create_role(
                    name=role_data["name"],
                    permissions=discord.Permissions(role_data["permissions"]),
                    color=discord.Color(role_data["color"]),
                    reason="Antinuke: restauración de backup",
                )
                creados += 1
        embed = discord.Embed(
            title="♻️ Backup restaurado",
            description=f"Se recrearon **{creados} roles** nuevos.",
            color=discord.Color.green(),
        )
        embed.set_footer(text="Los canales deben recrearse manualmente.")
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(AntinukeConfig(bot))
