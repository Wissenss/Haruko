import discord 
from discord.ext import commands

import environment
import constants
import database

class Forg(commands.Bot):
    def __init__(self, *args, **kwargs):
        database.ConnectionPool.init()
        super().__init__(*args, **kwargs)

    async def close(self):
        database.ConnectionPool.finish()
        await super().close()

# this is the entry point of the bot

intents =  discord.Intents.default()
intents.message_content = True
intents.messages = True
intents.members = True

bot = Forg(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print("ready!")

@bot.event
async def setup_hook():
    print("  loading cogs ... ")

    await bot.load_extension("cogs.adminCog")
    await bot.load_extension("cogs.generalCog")
    await bot.load_extension("cogs.wordCounterCog")
    await bot.load_extension("cogs.triviaCog")
    await bot.load_extension("cogs.economyCog")
    await bot.load_extension("cogs.listCog")
    await bot.load_extension("cogs.wissensCog")

    print("  syncing guilds ... ")
    for guild_id in [constants.DEV_GUILD_ID, constants.KUVA_GUILD_ID, constants.BUTTHOLE_LOVERS_GUILD_ID, constants.ROLLING_WAVES_REPUBLIC_GUILD_ID, constants.THE_SERVER_GUILD_ID, constants.DEV2_GUILD_ID]:
        try:
            await bot.tree.sync(guild=discord.Object(id=guild_id))
            print(f"    guild {guild_id}: Success")
        except Exception as e:
            print(f"    guild {guild_id}: {repr(e)}")

    await bot.tree.sync()

    print("setup finished!")

bot.run(environment.DISCORD_TOKEN)