import asyncio

import discord
from discord.ext import commands

import cache
import config
import database

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.bans = True
intents.voice_states = True
intents.emojis_and_stickers = True
intents.webhooks = True
intents.invites = True

bot = commands.Bot(command_prefix=config.PREFIX, intents=intents, help_command=None)
bot.owner_id = config.OWNER_ID


@bot.event
async def on_ready():
    print(f"Conectado como {bot.user} ({bot.user.id})")
    await cache.load_all(bot)


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.send(f"⛔ {error}")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("⛔ No tienes permisos para usar este comando.")
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("⚠️ No encontré a ese miembro.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"⚠️ Falta un argumento: `{error.param.name}`")
    elif isinstance(error, commands.CommandNotFound):
        return
    else:
        raise error


async def main():
    await database.init_db()
    async with bot:
        await bot.load_extension("cogs.events")
        await bot.load_extension("cogs.config_cmds")
        await bot.load_extension("cogs.moderation")
        await bot.load_extension("cogs.help")
        await bot.start(config.TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
