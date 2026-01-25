from typing import Literal
import random
import html

import discord
import discord.ext
import discord.ext.commands

import requests

import constants
import database
from cogs.customCog import CustomCog
from cogs.economyCog import EconomyCog
import security

class TriviaView(discord.ui.View):
  def __init__(self, options: list[str], correct_answer: str, difficulty : str, original_embed : discord.Embed):
    super().__init__(timeout=180)

    self.response : discord.InteractionCallbackResponse = None
    self.correct_answer = correct_answer
    self.original_embed = original_embed
    self.difficulty = difficulty

    for o in options:
        self.add_item(TriviaButton(o, self.correct_answer, difficulty, original_embed))

  def disable_all_items(self):
     for item in self.children:
        item.disabled = True

  async def on_timeout(self):
    self.disable_all_items()

    self.original_embed.description += "\n\n ⏱️ Time runed out."

    await self.response.resource.edit(view=self, embed=self.original_embed)

class TriviaButton(discord.ui.Button):
  def __init__(self, option: str, correct_answer: str, difficulty : str, original_embed : discord.Embed):
    super().__init__(label=option, style=discord.ButtonStyle.secondary)

    self.option = option
    self.correct_answer = correct_answer
    self.embed = original_embed
    self.difficulty = difficulty

  async def callback(self, interaction: discord.Interaction):
    # TODO: check the responder is the same as the creator
    
    if self.option == self.correct_answer:
      self.embed.description += f"\n\n ✅ Correct. **{interaction.user.display_name}** choosed **{self.option}**."

      # reward correct answers

      reward = 10

      if self.difficulty == "hard":
        reward *= 2
      elif self.difficulty == "medium":
        reward *= 1.5
      
      EconomyCog.create_transaction_autocommit(constants.TransactionKind.REWARD_TRIVIA, interaction.user.id, interaction.guild.id, reward)

      #

      self.embed.set_footer(text=self.embed.footer.text + f" | Reward: ${reward:.2f}") 

    else:
      self.embed.description += f"\n\n ❌ Incorrect. **{interaction.user.display_name}** choosed **{self.option}**."

    self.view.disable_all_items()
    self.view.stop()

    await interaction.response.edit_message(view=self.view, embed=self.embed)     

class TriviaCog(CustomCog):
    def __init__(self, bot):
        super().__init__(bot)

    @discord.app_commands.command(name="trivia")
    async def trivia(self, interaction : discord.Interaction, 
      difficulty: Literal[
        constants.OpenTDBDifficulty.Any.display, # type: ignore
        constants.OpenTDBDifficulty.Easy.display, # type: ignore
        constants.OpenTDBDifficulty.Medium.display, # type: ignore
        constants.OpenTDBDifficulty.Hard.display # type: ignore
      ] = constants.OpenTDBDifficulty.Any.display, 

      category: Literal[
        constants.OpenTDBCategory.Any.display, # type: ignore
        constants.OpenTDBCategory.GeneralKnowledge.display, # type: ignore
        constants.OpenTDBCategory.History.display, # type: ignore
        constants.OpenTDBCategory.EntertainmentBooks.display, # type: ignore
        constants.OpenTDBCategory.EntertainmentVideoGames.display, # type: ignore
        constants.OpenTDBCategory.EntertainmentFilm.display, # type: ignore
        constants.OpenTDBCategory.EntertainmentJapaneseAnimeAndManga.display, # type: ignore
        constants.OpenTDBCategory.EntertainmentMusic.display, # type: ignore
        constants.OpenTDBCategory.ScienceMathematics.display, # type: ignore
        constants.OpenTDBCategory.ScienceComputers.display # type: ignore
      ] = constants.OpenTDBCategory.Any.display               
    ):
      self.log.info(f"/trivia called. (user.id={interaction.user.id}, difficulty={difficulty}, cateogry={category})")

      em = discord.Embed()

      params = { "amount" : 1}
    
      if constants.OpenTDBCategory.from_str(category) != constants.OpenTDBCategory.Any:
        params["category"] = constants.OpenTDBCategory.from_str(category).id

      if constants.OpenTDBDifficulty.from_str(difficulty) != constants.OpenTDBDifficulty.Any:
        params["difficulty"] = constants.OpenTDBDifficulty.from_str(difficulty).display.lower()

      response = requests.get("https://opentdb.com/api.php", params)

      if response.status_code != 200:
        em.description = f"/trivia database endpoint could not be reached, status code: `{response.status_code}`"
        return await interaction.response.send_message(embed=em)

      data = response.json()

      self.log.debug(f"opentdb (at \"{response.url}\") returned: {data}")

      _response_code     = constants.OpenTDBResponseCode.from_int(int(data["response_code"]))

      if _response_code != constants.OpenTDBResponseCode.Success:
        em.description = f"open trivia database responded with code: `{_response_code.id}:{_response_code.display}`"
        return await interaction.response.send_message(embed=em)

      _difficulty        = data["results"][0]["difficulty"]
      _type              = data["results"][0]["type"]
      _category          = data["results"][0]["category"]
      _question          = data["results"][0]["question"]
      _correct_answer    = data["results"][0]["correct_answer"]
      _incorrect_answers = data["results"][0]["incorrect_answers"]

      # cleanup incoming html encoded characters

      _question = html.unescape(_question)
      _category = html.unescape(_category)
      _correct_answer = html.unescape(_correct_answer)
      _incorrect_answers = [html.unescape(answer) for answer in _incorrect_answers]
      
      #

      em.description = _question
      em.set_footer(text=f"{_category}: {_difficulty}")

      _options : list[str] = _incorrect_answers
      _options.append(_correct_answer)
      
      random.shuffle(_options)

      vi = TriviaView(options=_options, correct_answer=_correct_answer, difficulty=_difficulty, original_embed=em)
      vi.response = await interaction.response.send_message(view=vi, embed=em)

async def setup(bot):
    await bot.add_cog(TriviaCog(bot))