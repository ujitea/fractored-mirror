import discord
import embed_generator
import success_overlay
import os
from discord.ext import commands
from discord.ui import Button, View
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("DISCORD_TOKEN")
TARGET_CHANNEL_ID = int(os.getenv("TARGET"))
SOURCE_CHANNEL_ID = int(os.getenv("SOURCE"))
ANNOUNCEMENTS_ID = int(os.getenv("ANNOUNCEMENTS"))
MINOR_ID = int(os.getenv("MINOR"))
SUCCESS_ID = int(os.getenv("SUCCESS"))

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.messages = True
intents.reactions = True

bot = commands.Bot(command_prefix="!", intents=intents)  

owner_message_id = {}

@bot.event
async def on_reaction_add(reaction, user):
    # ignore bot reactions
    if user.bot:
        return

    # only act on trashcan emoji
    if str(reaction.emoji) != "🗑️":
        return

    msg = reaction.message
    # only allow the recorded owner to delete
    owner_id = owner_message_id.get(msg.id)

    if owner_id is None:
        return  

    if user.id == owner_id:
        try:
            await msg.delete()
            owner_message_id.pop(msg.id, None)
        except discord.Forbidden:
            pass

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    # Watermark logic: If there's an image attachment in the TARGET_CHANNEL
    if message.channel.id == SUCCESS_ID and message.attachments:
        for attachment in message.attachments:
            if attachment.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                img_data = await attachment.read()
                watermarked = success_overlay.add_image_watermark(img_data, 'watermark.png')
                await message.delete()
                file = discord.File(watermarked, filename="watermarked.jpg")
                sent_message = await message.channel.send(
                    f"{message.author.mention}",
                    file=file
                )
                await sent_message.add_reaction("🗑️")
                owner_message_id[sent_message.id] = message.author.id


        # Return early if image watermarking logic ran (optional, if you don't want other logic to execute)
        return

    # Only relay messages from the specific source channel
    if message.channel.id == SOURCE_CHANNEL_ID:
        unparsed_content = f"{message.content}"
        parsed_data = embed_generator.parse_extracted_text(unparsed_content)
        embed = embed_generator.embed_from_parsed(parsed_data)

        view = View()

        button1 = Button(label="channel-1", style=discord.ButtonStyle.green)
        button2 = Button(label="channel-2", style=discord.ButtonStyle.green)

        async def disable_all_buttons(interaction):
            for item in view.children:
                item.disabled = True
            await interaction.message.edit(view=view)

        async def button1_callback(interaction):
            target_channel = bot.get_channel(ANNOUNCEMENTS_ID)
            if target_channel:
                await target_channel.send(embed=embed)
                await disable_all_buttons(interaction)
                await interaction.response.send_message("Success!", ephemeral=True)
            else:
                await interaction.response.send_message("channel 1 not found.", ephemeral=True)
        button1.callback = button1_callback
        view.add_item(button1)

        async def button2_callback(interaction):
            target_channel = bot.get_channel(MINOR_ID)
            if target_channel:
                await target_channel.send(embed=embed)
                await disable_all_buttons(interaction)
                await interaction.response.send_message("Success!", ephemeral=True)
            else:
                await interaction.response.send_message("channel 2 not found.", ephemeral=True)
        button2.callback = button2_callback
        view.add_item(button2)

        target_channel = bot.get_channel(TARGET_CHANNEL_ID)
        if target_channel:
            await target_channel.send(
                content="at everyone",
                embed=embed,
                view=view)

    await bot.process_commands(message)

bot.run(BOT_TOKEN)
