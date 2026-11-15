import datetime, time

import discord
import discord.ext
import discord.ext.commands

import database
from cogs.customCog import CustomCog

class GeneralCog(CustomCog):
    def __init__(self, bot):
        super().__init__(bot)

        self.wakeup_time : datetime = discord.utils.utcnow()

    @discord.ext.commands.Cog.listener()
    async def on_ready(self):
        pass

    @discord.app_commands.command(name="ping")
    async def ping(self, interaction : discord.Interaction):
        em = discord.Embed(title="pong!", description="")

        uptime = ( discord.utils.utcnow() - self.wakeup_time )

        em.description += f"\n**latency:**   {self.bot.latency * 1000:.0f} ms"
        em.description += f"\n**uptime:**    {uptime}"
        em.description += f"\n**pool size:** {database.ConnectionPool.get_pool_size()}" # ({database.ConnectionPool.get_pool_occupied_connections()} busy)

        return await interaction.response.send_message(embed=em)

    @discord.app_commands.command(name="about")
    async def about(self, interaction : discord.Interaction):
        em = discord.Embed(title="Haruko", description="")

        #em.description += "\nRolling Waves Republic Humble Assistant"

        em.description += "\nThis bot is developed for free. If you would like to contribute [here is how](https://ko-fi.com/wissens/?widget=true&hidefeed=true)."

        return await interaction.response.send_message(embed=em)
    
    # TODO: help command
    @discord.app_commands.command(name="help")
    async def help(self, interaction : discord.Interaction):
        em = discord.Embed(title="", description="")

        em.description += "TODO"

        return await interaction.response.send_message(embed=em)
    
async def setup(bot):
    await bot.add_cog(GeneralCog(bot))