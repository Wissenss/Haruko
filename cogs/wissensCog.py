import discord
import constants
import environment
import requests
from cogs.customCog import CustomCog

class WissensCog(CustomCog):
  def __init__(self, bot):
    super().__init__(bot)

  @discord.app_commands.command(name="gym_log")
  @discord.app_commands.guilds(constants.DEV_GUILD_ID)
  async def gym_log(self, interaction : discord.Interaction):
    em = discord.Embed(title="", description="")
    
    url = f"{environment.TAKKUN_ADDR}/training-sessions?api_key={environment.TAKKUN_KEY}"
    
    print(url)

    request = requests.post(url, headers={"content-type": "application/json"}, json={})

    if request.status_code != 200:
      em.description = f"error: {request.status_code}"
      return await interaction.response.send_message(embed=em, ephemeral=True)
    
    em.description = "training session logged!"

    return await interaction.response.send_message(embed=em, ephemeral=True)

async def setup(bot):
  await bot.add_cog(WissensCog(bot))