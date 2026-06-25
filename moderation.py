import datetime

import discord
from discord.ext import commands


class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command()
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx: commands.Context, member: discord.Member, *, razon: str = "Sin razón"):
        await member.kick(reason=razon)
        await ctx.send(f"👋 {member} fue expulsado. Razón: {razon}")

    @commands.command()
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx: commands.Context, member: discord.Member, *, razon: str = "Sin razón"):
        await member.ban(reason=razon)
        await ctx.send(f"🔨 {member} fue banneado. Razón: {razon}")

    @commands.command()
    @commands.has_permissions(ban_members=True)
    async def unban(self, ctx: commands.Context, user_id: int):
        user = await self.bot.fetch_user(user_id)
        await ctx.guild.unban(user)
        await ctx.send(f"✅ {user} fue desbanneado.")

    @commands.command()
    @commands.has_permissions(moderate_members=True)
    async def mute(self, ctx: commands.Context, member: discord.Member, minutos: int, *, razon: str = "Sin razón"):
        await member.timeout(datetime.timedelta(minutes=minutos), reason=razon)
        await ctx.send(f"🔇 {member} fue silenciado por {minutos} minutos.")

    @commands.command()
    @commands.has_permissions(moderate_members=True)
    async def unmute(self, ctx: commands.Context, member: discord.Member):
        await member.timeout(None)
        await ctx.send(f"🔊 {member} ya no está silenciado.")

    @commands.command()
    @commands.has_permissions(manage_messages=True)
    async def warn(self, ctx: commands.Context, member: discord.Member, *, razon: str = "Sin razón"):
        await ctx.send(f"⚠️ {member.mention} ha sido advertido. Razón: {razon}")

    @commands.command(aliases=["purge"])
    @commands.has_permissions(manage_messages=True)
    async def clear(self, ctx: commands.Context, cantidad: int):
        await ctx.channel.purge(limit=cantidad + 1)
        await ctx.send(f"🧹 Se eliminaron {cantidad} mensajes.", delete_after=3)

    @commands.command()
    @commands.has_permissions(manage_channels=True)
    async def lock(self, ctx: commands.Context):
        await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=False)
        await ctx.send("🔒 Canal bloqueado.")

    @commands.command()
    @commands.has_permissions(manage_channels=True)
    async def unlock(self, ctx: commands.Context):
        await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=None)
        await ctx.send("🔓 Canal desbloqueado.")

    @commands.command()
    @commands.has_permissions(manage_channels=True)
    async def slowmode(self, ctx: commands.Context, segundos: int):
        await ctx.channel.edit(slowmode_delay=segundos)
        await ctx.send(f"⏱️ Slowmode establecido en {segundos} segundos.")

    @commands.command()
    @commands.has_permissions(manage_nicknames=True)
    async def nick(self, ctx: commands.Context, member: discord.Member, *, apodo: str = None):
        await member.edit(nick=apodo)
        await ctx.send(f"✏️ Apodo de {member} cambiado.")

    @commands.command(name="addrole")
    @commands.has_permissions(manage_roles=True)
    async def add_role(self, ctx: commands.Context, member: discord.Member, role: discord.Role):
        await member.add_roles(role)
        await ctx.send(f"✅ Rol {role.name} añadido a {member}.")

    @commands.command(name="removerole")
    @commands.has_permissions(manage_roles=True)
    async def remove_role(self, ctx: commands.Context, member: discord.Member, role: discord.Role):
        await member.remove_roles(role)
        await ctx.send(f"❌ Rol {role.name} quitado de {member}.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))
