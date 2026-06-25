import discord
from discord.ext import commands

from constants import MODULES


class Help(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="help")
    async def help_command(self, ctx: commands.Context):
        prefix = ctx.prefix
        embed = discord.Embed(
            title="📖 Panel de Ayuda",
            description="Comandos disponibles, organizados por categoría.",
            color=discord.Color.blurple(),
        )
        embed.add_field(
            name="🛡️ Antinuke",
            value=(
                f"`{prefix}antinuke` — Ver panel\n"
                f"`{prefix}antinuke on <módulo>` — Activar módulo\n"
                f"`{prefix}antinuke off <módulo>` — Desactivar módulo\n"
                f"`{prefix}antinuke limite <módulo> <n>` — Límite de acciones\n"
                f"`{prefix}antinuke castigo <módulo> <kick/ban/quarantine>`\n"
                f"`{prefix}whitelist` / `add` / `remove`\n"
                f"`{prefix}logs <#canal>`\n"
                f"`{prefix}lockdown on/off`\n"
                f"`{prefix}backup create/restore`"
            ),
            inline=False,
        )
        embed.add_field(
            name="🔨 Moderación",
            value=(
                f"`{prefix}kick` `{prefix}ban` `{prefix}unban` `{prefix}mute` `{prefix}unmute`\n"
                f"`{prefix}warn` `{prefix}clear` `{prefix}lock` `{prefix}unlock`\n"
                f"`{prefix}slowmode` `{prefix}nick` `{prefix}addrole` `{prefix}removerole`"
            ),
            inline=False,
        )
        embed.add_field(
            name="ℹ️ Módulos de Antinuke disponibles",
            value=", ".join(f"`{m}`" for m in MODULES.keys()),
            inline=False,
        )
        embed.set_footer(text="Solo el dueño del servidor y el dueño del bot pueden usar los comandos de Antinuke.")
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Help(bot))
