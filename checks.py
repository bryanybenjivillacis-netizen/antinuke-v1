from discord.ext import commands

import config


def is_owner_or_botowner():
    """Solo el dueño del servidor o el dueño del bot pueden usar el comando."""
    async def predicate(ctx):
        if ctx.author.id == config.OWNER_ID:
            return True
        if ctx.guild and ctx.author.id == ctx.guild.owner_id:
            return True
        raise commands.CheckFailure(
            "Solo el dueño del servidor o el dueño del bot pueden usar este comando."
        )
    return commands.check(predicate)
