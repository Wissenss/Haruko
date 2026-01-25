import datetime
import re
from typing import Optional

import discord
import discord.ext
import discord.ext.commands

import constants
import database
import security

from cogs.customCog import CustomCog
import settings

class WordCounterCog(CustomCog):
    def __init__(self, bot):
        super().__init__(bot)

        self.ongoing_scan_message_id : int = 0
        self.ongoing_scan_channel_id : int = 0
        self.ongoing_scan : bool = False

        self.nword_variations = [
            "nigga", "niga", 
            "negro", 
            "nigger", "niger",
            "nword",
        ]

    def clean_message_content(self, content : str) -> str:
        cleaned = content.strip().lower() 

        # Remove punctuation and symbols (keep letters, digits, underscores)
        cleaned = re.sub(r"[^\w\s]", "", cleaned)

        # Remove all linefeeds
        cleaned = cleaned.replace("\n", " ").replace("\r", " ")

        # Replace multiple spaces/tabs/newlines with a single space
        text = re.sub(r"\s+", " ", cleaned)

        return cleaned
    
    def save_message(self, message : discord.Message):
        con = database.ConnectionPool.get()
        cur = con.cursor()

        sql = "INSERT INTO messages(discord_message_id, discord_guild_id, discord_channel_id, discord_created_at, discord_user_id, content, content_clean) VALUES(?, ?, ?, ?, ?, ?, ?);"

        cur.execute(sql, [message.id, message.guild.id, message.channel.id, message.created_at.strftime("%Y-%m-%d %H:%M:%S"), message.author.id, message.content, self.clean_message_content(message.content)])
        con.commit()

        database.ConnectionPool.release(con)

    def save_message_word_count(self, message : discord.Message):
        con = database.ConnectionPool.get()
        cur = con.cursor()
        
        tokens = self.clean_message_content(message.content).split(" ")

        sql = """
        INSERT INTO messages_word_count(word, discord_guild_id, discord_channel_id, discord_user_id, count)
        VALUES (?, ?, ?, ?, 1)
        ON CONFLICT(word, discord_guild_id, discord_channel_id, discord_user_id) DO UPDATE SET
            count = count + 1;
        """
        
        for t in tokens:
            cur.execute(sql, [t, message.guild.id, message.channel.id, message.author.id])

        con.commit()

        database.ConnectionPool.release(con)

    def is_message_saved(self, message : discord.Message):
        con = database.ConnectionPool.get()
        cur = con.cursor()

        message_found = False

        cur.execute("SELECT * FROM messages WHERE discord_message_id = ?", [message.id])

        if cur.fetchone():
            message_found = True
        
        database.ConnectionPool.release(con)
        
        return message_found

    def process_message(self, message : discord.Message):
        self.save_message(message)
        self.save_message_word_count(message)

    @discord.ext.commands.Cog.listener()
    async def on_message(self, message : discord.Message):

        if message.author.id == self.bot.user.id:
            return

        self.process_message(message)

    @discord.app_commands.command(name="wordscan")
    async def wordscan(self, interaction : discord.Interaction):
        
        em = discord.Embed(title="scanner log", description="")

        # check caller has permissions for this command
        if not security.account_has_permision(interaction.user.id, interaction.guild.id, constants.Permission.WORD_COUNT_COG_SCAN):
            em.description = "You're not allowed to use this!"
            return await interaction.response.send_message(embed=em, ephemeral=True)

        # check there is no other scan happening
        if self.ongoing_scan:
            ongoing_scan_channel = await interaction.guild.fetch_channel(self.ongoing_scan_channel_id)
            ongoing_scan_message = await ongoing_scan_channel.fetch_message(self.ongoing_scan_message_id)

            em.title = ""
            em.description += f"another scann is allready in progress at {ongoing_scan_message.jump_url}"

            return await interaction.response.send_message(embed=em, ephemeral=True)

        # start the scan
        scan_logs = []
        scan_logs_update_interval = 14

        scan_logs.append("starting message scan...")
        em.description = "\n".join(scan_logs)
        await interaction.response.send_message(embed=em)

        try:
            # fetch original message to bypass 15 min interaction limit imposed by discord
            #interaction_message = await interaction.original_response()
            #interaction_message = await interaction.channel.fetch_message(interaction_message.id)
            interaction_message = await interaction.original_response()

            # mark the scan as started
            self.ongoing_scan = True
            self.ongoing_scan_channel_id = interaction_message.channel.id
            self.ongoing_scan_message_id = interaction_message.id

            # fetch channels in the guild
            scan_logs.append("fetching channels...")
            em.description = "\n".join(scan_logs)
            await interaction.followup.edit_message(message_id=interaction_message.id, embed=em)

            guild_channels = interaction.guild.text_channels + interaction.guild.voice_channels

            scan_logs[-1] = f"fetching channels... {len(guild_channels)} found"
            em.description = "\n".join(scan_logs)
            await interaction.followup.edit_message(message_id=interaction_message.id, embed=em)

            # got through every channel in the guild

            for channel in guild_channels:
                
                scan_logs.append(f"processing channel \"{channel.name}\"... ")
                em.description = "\n".join(scan_logs)
                await interaction.followup.edit_message(message_id=interaction_message.id, embed=em)
                
                # check the bot has permissions for this channel

                permissions = channel.permissions_for(interaction.guild.me)

                if not (permissions.read_messages and permissions.read_message_history and permissions.view_channel):
                    scan_logs[-1] = f"processing channel \"{channel.name}\"... lacking permisions"
                    em.description = "\n".join(scan_logs)
                    await interaction.followup.edit_message(message_id=interaction_message.id, embed=em)
                    continue

                # go through every message on the channel 

                progress = 0

                first_message_created_at = constants.DISCORD_EPOCH # this is needed to more accurately calculate percentage completion
                async for message in channel.history(limit=1, oldest_first=True):
                    first_message_created_at = message.created_at
                
                after = datetime.datetime.strptime(settings.get_value("latest_scan_message_created_at", 0, interaction.guild.id, channel.id, constants.DISCORD_EPOCH.strftime("%Y-%m-%d %H:%M:%S")), "%Y-%m-%d %H:%M:%S").replace(tzinfo=datetime.timezone.utc) # only messages after the last stored scan time will be considered

                async for message in channel.history(limit=None, oldest_first=True, after=after):
                    
                    if not self.is_message_saved(message) and message.author.id != self.bot.user.id:
                        self.process_message(message)

                    progress += 1

                    # register progress every <scan_logs_update_interval> 

                    if progress % scan_logs_update_interval:
                        now = datetime.datetime.now(datetime.timezone.utc)
                        
                        # update the progress message
                        completion_rate = (message.created_at - first_message_created_at).total_seconds() / (now - first_message_created_at).total_seconds()
                        scan_logs[-1] = f"processing channel \"{channel.name}\"... {completion_rate:.2%}"
                        em.description = "\n".join(scan_logs)
                        em.timestamp = now
                        em.set_footer(text="last update")
                        await interaction.followup.edit_message(message_id=interaction_message.id, embed=em)

                        # save the last scan message creation time
                        settings.set_value("latest_scan_message_created_at",  0, interaction.guild.id, channel.id, message.created_at.strftime("%Y-%m-%d %H:%M:%S"))
                
                scan_logs[-1] = f"processing channel \"{channel.name}\"... 100.00%"
                em.description = "\n".join(scan_logs)
                await interaction.followup.edit_message(message_id=interaction_message.id, embed=em)

        except Exception as e:
            scan_logs.append(f"unexpected failure!")
            scan_logs.append(f"```\n{repr(e)}\n```")

        # mark the scan as finished
        self.ongoing_scan = False
        self.ongoing_scan_channel_id = 0
        self.ongoing_scan_message_id = 0

        scan_logs.append("finished!")
        em.description = "\n".join(scan_logs)
        await interaction.followup.edit_message(message_id=interaction_message.id, embed=em)

    # general command handlers
    
    async def __wordquote(self, interaction : discord.Interaction, words : list[str], member : Optional[discord.Member] = None):
        if member == None:
            member = interaction.user
        
        cleanned_words = [self.clean_message_content(w) for w in words]

        em = discord.Embed(title="", description=f"searching **{", ".join(cleanned_words)}** mentions...")

        await interaction.response.send_message(embed=em)
        
        con = database.ConnectionPool.get()
        cur = con.cursor()

        # this is the (somewhat) ineficient way of doing things
        # it may be worth it to take a look at https://www.sqlite.org/fts5.html if performance
        # becomes an issue

        search_condition = "FALSE"

        for w in cleanned_words:
            search_condition += " OR content_clean LIKE ?"

        sql = f"""
        SELECT * 
        FROM messages 
        WHERE deleted = False AND discord_user_id = ? AND discord_guild_id = ? AND 
        (
            {search_condition}
        ) 
        ORDER BY RANDOM()
        LIMIT 1
        """

        result = cur.execute(sql, [member.id, interaction.guild.id] + [f"%{w}%" for w in cleanned_words])
        message = result.fetchone()

        database.ConnectionPool.release(con)

        if not message:
            em.description = f"no mention of **{", ".join(cleanned_words)}** found for member **{member.display_name}**"
            return await interaction.edit_original_response(embed=em)

        discord_message_channel = interaction.guild.get_channel(message[2])
        
        if not discord_message_channel:
            em.description = "channel not found"
            return await interaction.edit_original_response(embed=em)

        try:
            discord_message = await discord_message_channel.fetch_message(message[0])

            if not discord_message:
                em.description = "message not found"
                return await interaction.edit_original_response(embed=em)

            em.description = f"_\"{discord_message.content}\"_"

            if discord_message.author:
                em.set_author(name=discord_message.author.display_name, icon_url=discord_message.author.avatar.url, url=discord_message.jump_url)
            
            em.timestamp = discord_message.created_at

            return await interaction.edit_original_response(embed=em) 
        
        except discord.NotFound:
            
            # if the message is not found we mark it as deleted so it wont be shown again

            cur = database.ConnectionPool.get().cursor()

            cur.execute("UPDATE messages SET deleted = True WHERE discord_message_id = ?;", [message[0]])

            cur.connection.commit()

            database.ConnectionPool.release(cur.connection)

            em.description = "message deleted"

            return await interaction.edit_original_response(embed=em)

    async def __wordcount(self, interaction : discord.Interaction, words : list[str], member : Optional[discord.Member] = None):
        cleanned_words = []

        for w in words:
            cleanned_words.append(self.clean_message_content(w))

        em = discord.Embed(title="", description=f"searching **{", ".join(cleanned_words)}** mentions...")

        await interaction.response.send_message(embed=em)

        con = database.ConnectionPool.get()
        cur = con.cursor()

        sql = f"""
        SELECT SUM(count) 
        FROM messages_word_count 
        WHERE word IN ({','.join('?' for _ in cleanned_words)}) AND discord_guild_id = ? {"AND discord_user_id = ?" if member != None else ""} 
        GROUP BY word, discord_guild_id, discord_user_id;
        """

        params = cleanned_words + [interaction.guild.id]

        if member != None:
            params.append(member.id)

        cur.execute(sql, params)

        # TODO: show graph (maybe...)

        result = cur.fetchone()

        if result == None:
            if member:
                em.description = f"**{member.display_name}** has never mention **{", ".join(cleanned_words)}** before"
            else:
                em.description = f"members of **{interaction.guild.name}** have never mention **{", ".join(cleanned_words)}** before"
        else:
            count = result[0]

            if member:
                em.description = f"**{member.display_name}** has mention **{", ".join(cleanned_words)}** **{count} {"time" if count == 1 else "times"}**"
            else:
                em.description = f"members of **{interaction.guild.name}** have mention **{", ".join(cleanned_words)}** **{count} {"time" if count == 1 else "times"}**"

        await interaction.edit_original_response(embed=em)
    
    async def __wordtop(self, interaction : discord.Interaction, words : Optional[list[str]] = []):
        cleanned_words = [self.clean_message_content(w) for w  in words]

        em = discord.Embed(title="", description=f"searching **{", ".join(cleanned_words)}** mentions...")

        await interaction.response.send_message(embed=em)

        # get top members
        con = database.ConnectionPool.get()
        cur = con.cursor()

        search_condition = "FALSE" if words else "TRUE"

        for _ in cleanned_words:
            search_condition += " OR word = ?"

        sql = f"""
        SELECT 
            discord_guild_id, 
            discord_user_id,
            word, 
            SUM(count) as total_count 
        FROM 
            messages_word_count 
        WHERE 
            (
                {search_condition}
            )
            AND discord_guild_id = ? 
        GROUP BY 
            discord_guild_id, { "discord_user_id" if words else "word" } 
        ORDER BY 
            total_count DESC 
        LIMIT 10;
        """

        cur.execute(sql, cleanned_words + [interaction.guild.id])

        top_counts = cur.fetchall()

        if words:
            # create table
            table = ""
            table += f"#  | Member            |   Mentions\n"
            table += f"{"".ljust(35, "-")}\n"

            for i, count in enumerate(top_counts):
                discord_guild_id = count[0]
                discord_user_id  = count[1]
                word = count[2]
                total_count = count[3]

                author = interaction.guild.get_member(discord_user_id)

                table += f"{str(i+1).zfill(2)} | {str(author.display_name if author else "unknown").ljust(17)} | {str(total_count).zfill(5).rjust(10)}\n"

            em.description = ""
            em.add_field(name=f"Top members that have mention {", ".join(cleanned_words)}", value=f"```{table}```", inline=False)
        else:
            # create table
            table = ""
            table += f"#  | Word              |   Mentions\n"
            table += f"{"".ljust(35, "-")}\n"

            for i, count in enumerate(top_counts):
                discord_guild_id = count[0]
                discord_user_id  = count[1]
                word = count[2]
                total_count = count[3]

                author = interaction.guild.get_member(discord_user_id)

                table += f"{str(i+1).zfill(2)} | {word.ljust(17)} | {str(total_count).zfill(5).rjust(10)}\n"

            em.description = ""
            em.add_field(name=f"Top words mention by **{interaction.guild.name}** members", value=f"```{table}```", inline=False)

        await interaction.edit_original_response(embed=em)
    
    # normal word commands

    @discord.app_commands.command(name="wordquote")
    @discord.app_commands.describe(word="the word to look for", member="the member to look for (optional), if none the quote is from a random member")
    @discord.app_commands.guilds(constants.DEV_GUILD_ID, constants.KUVA_GUILD_ID, constants.BUTTHOLE_LOVERS_GUILD_ID, constants.THE_SERVER_GUILD_ID)
    async def wordquote(self, interaction : discord.Interaction, word : str, member : Optional[discord.Member] = None):
       return await self.__wordquote(interaction, word.split(","), member)

    @discord.app_commands.command(name="wordcount", description="counts how many times a word was mention")
    @discord.app_commands.describe(word="the word to look for", member="the memeber to look mentions for (optional), if none the count is global")
    @discord.app_commands.guilds(constants.DEV_GUILD_ID, constants.KUVA_GUILD_ID, constants.BUTTHOLE_LOVERS_GUILD_ID, constants.THE_SERVER_GUILD_ID)
    async def wordcount(self, interaction : discord.Interaction, word : str, member : Optional[discord.Member] = None):
        return await self.__wordcount(interaction, word.split(","), member)

    @discord.app_commands.command(name="wordtop")
    @discord.app_commands.describe(word="the word to look for (optional), if none the command retrieves the top words mention")
    @discord.app_commands.guilds(constants.DEV_GUILD_ID, constants.KUVA_GUILD_ID, constants.BUTTHOLE_LOVERS_GUILD_ID, )
    async def wordtop(self, interaction : discord.Interaction, word : str = None):
        if word == None:
            word_list = []
        else:
            word_list = word.split(",")
            
        return await self.__wordtop(interaction, word_list)

    # n-word commands

    @discord.app_commands.command(name="nwordquote", description="gets a random quote from someone that said the nword")
    @discord.app_commands.describe(member="the member to look for (optional), if none the quote is from a random member")
    @discord.app_commands.guilds(constants.DEV_GUILD_ID, constants.ROLLING_WAVES_REPUBLIC_GUILD_ID)
    async def nwordquote(self, interaction : discord.Interaction, member : Optional[discord.Member] = None):
        return await self.__wordquote(interaction, self.nword_variations, member)

    @discord.app_commands.command(name="nwordcount", description="count how many times the nword was mention")
    @discord.app_commands.describe(member="the member to look mentions for (optional), if none the count is global")
    @discord.app_commands.guilds(constants.DEV_GUILD_ID, constants.ROLLING_WAVES_REPUBLIC_GUILD_ID)
    async def nwordcount(self, interaction : discord.Interaction, member : Optional[discord.Member] = None):
        return await self.__wordcount(interaction, self.nword_variations, member)

    @discord.app_commands.command(name="nwordtop", description="get the top members that have mention the nword")
    @discord.app_commands.guilds(constants.DEV_GUILD_ID, constants.ROLLING_WAVES_REPUBLIC_GUILD_ID)
    async def nwordtop(self, interaction : discord.Interaction):
        return await self.__wordtop(interaction, self.nword_variations)

async def setup(bot):
    await bot.add_cog(WordCounterCog(bot))