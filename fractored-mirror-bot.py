import discord
import embed_generator
import success_overlay
import os
import asyncio
from discord.ext import commands
from discord.ui import Button, View
from uuid import uuid4
from dotenv import load_dotenv
# from deal_bot import client, TOKEN

load_dotenv()

BOT_TOKEN = os.getenv("DISCORD_TOKEN")
####################################################
# MAIN SERVER
TARGET_CHANNEL_ID = int(os.getenv("TARGET"))
# SOURCE_CHANNEL_ID = int(os.getenv("SOURCE")) 
MAJOR_ID = int(os.getenv("MAJOR"))
MINOR_ID = int(os.getenv("MINOR"))
MEMBER_ID = int(os.getenv("MEMBER"))
PERSONAL_ID = int(os.getenv("PERSONAL"))
FOOD_ID = int(os.getenv("FOOD"))
SUCCESS_ID = int(os.getenv("SUCCESS"))
###################################################
# FORWARDING SERVER
MAJOR_FID = int(os.getenv("F_MAJOR"))
MINOR_FID = int(os.getenv("F_MINOR"))
MEMBER_FID = int(os.getenv("F_MEMBER"))
DEALS_FID = int(os.getenv("F_DEALS"))
FOOD_FID = int(os.getenv("F_FOOD"))
CHIPOTLE_FID = int(os.getenv("F_CHIPOTLE"))

SOURCE_CHANNEL_IDS = {MAJOR_FID,MINOR_FID,MEMBER_FID,DEALS_FID,FOOD_FID,CHIPOTLE_FID}


intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.messages = True
intents.reactions = True

bot = commands.Bot(command_prefix="!", intents=intents)  

owner_message_id = {}

# Event that deletes images based on owner's message

@bot.event
async def on_reaction_add(reaction, user):
    # ignore bot reactions
    if user.bot:
        return

    # only act on trashcan emoji
    if str(reaction.emoji) != "🗑️":
        return

    msg = reaction.message

    if msg.guild:
        try:
            msg = await msg.channel.fetch_message(msg.id)
        except discord.NotFound:
            return
        
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
    
    # Add watermark overlay w/ server logo
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

    # Only source channel list
    if message.channel.id in SOURCE_CHANNEL_IDS:
        target_channel = message.channel

        view = View()

        # unparsed_content = f"{message.content}"   

        msg = await embed_generator.wait_a_bit_for_embeds(message, delay=0.5)  # try 0.8–1.5s
        unparsed_content = msg.content
        thumb_from_embed = embed_generator.first_embed_image_url(msg)


        res = embed_generator.parse_extracted_text(unparsed_content)

        parsed_data = embed_generator.parse_extracted_text(unparsed_content)

        thumb_from_embed = embed_generator.first_embed_image_url(message)

        if thumb_from_embed and not parsed_data.get("thumbnail_url"):
            parsed_data["thumbnail_url"] = thumb_from_embed
            print("DING DONG")
        # Try to pull out both a dict (parsed data) and a real Embed object from whatever was returned.
        embed, link_view = embed_generator.embed_from_parsed(parsed_data)

        if isinstance(res, tuple):
            parsed_data = next((x for x in res if isinstance(x, dict)), None)
            embed = next((x for x in res if hasattr(x, "to_dict")), None)  # discord.Embed has to_dict()
        elif isinstance(res, dict):
            parsed_data = res
        elif hasattr(res, "to_dict"):
            embed = res

        # If we still don't have an Embed, build one from parsed_data
        if embed is None:
            embed = embed_generator.embed_from_parsed(parsed_data)

        # If the embed builder ALSO returned a tuple (oops), extract the real Embed
        if isinstance(embed, tuple):
            embed = next((x for x in embed if hasattr(x, "to_dict")), None)

        if not hasattr(embed, "to_dict"):
            print("DEBUG: embed is not a discord.Embed. Type:", type(embed))
            return


        # view = View()

        button_major = Button(label="major",  style=discord.ButtonStyle.success, custom_id=f"major:{message.id}:{uuid4().hex}")
        button_minor = Button(label="minor",  style=discord.ButtonStyle.success, custom_id=f"minor:{message.id}:{uuid4().hex}")
        button_member   = Button(label="member",   style=discord.ButtonStyle.success, custom_id=f"member:{message.id}:{uuid4().hex}")
        button_personal = Button(label="personal", style=discord.ButtonStyle.success, custom_id=f"personal:{message.id}:{uuid4().hex}")
        button_food     = Button(label="food",     style=discord.ButtonStyle.success, custom_id=f"food:{message.id}:{uuid4().hex}")



        async def disable_all_buttons(interaction: discord.Interaction):
            for item in view.children:
                item.disabled = True
            await interaction.message.edit(view=view)

        # --- Major ---
        async def button_major_callback(interaction: discord.Interaction):
            dest = bot.get_channel(MAJOR_ID) or await bot.fetch_channel(MAJOR_ID)
            if not dest:
                return await interaction.response.send_message("Major channel not found.", ephemeral=True)
            await dest.send(content="@everyone", embed=embed)
            await disable_all_buttons(interaction)
            await interaction.response.send_message("Sent to Major.", ephemeral=True)
        button_major.callback = button_major_callback

        # --- Minor ---
        async def button_minor_callback(interaction: discord.Interaction):
            dest = bot.get_channel(MINOR_ID) or await bot.fetch_channel(MINOR_ID)
            if not dest:
                return await interaction.response.send_message("Minor channel not found.", ephemeral=True)
            await dest.send(content="@everyone", embed=embed)
            await disable_all_buttons(interaction)
            await interaction.response.send_message("Sent to Minor.", ephemeral=True)
        button_minor.callback = button_minor_callback

        # --- Member ---
        async def button_member_callback(interaction: discord.Interaction):
            dest = bot.get_channel(MEMBER_ID) or await bot.fetch_channel(MEMBER_ID)
            if not dest:
                return await interaction.response.send_message("Member channel not found.", ephemeral=True)
            await dest.send(content="@everyone", embed=embed)
            await disable_all_buttons(interaction)
            await interaction.response.send_message("Sent to Member.", ephemeral=True)
        button_member.callback = button_member_callback

        # --- Personal ---
        async def button_personal_callback(interaction: discord.Interaction):
            dest = bot.get_channel(PERSONAL_ID) or await bot.fetch_channel(PERSONAL_ID)
            if not dest:
                return await interaction.response.send_message("Personal channel not found.", ephemeral=True)
            await dest.send(content="@everyone", embed=embed)
            await disable_all_buttons(interaction)
            await interaction.response.send_message("Sent to Personal.", ephemeral=True)
        button_personal.callback = button_personal_callback

        # --- Food ---
        async def button_food_callback(interaction: discord.Interaction):
            dest = bot.get_channel(FOOD_ID) or await bot.fetch_channel(FOOD_ID)
            if not dest:
                return await interaction.response.send_message("Food channel not found.", ephemeral=True)
            await dest.send(content="@everyone", embed=embed)
            await disable_all_buttons(interaction)
            await interaction.response.send_message("Sent to Food.", ephemeral=True)
        button_food.callback = button_food_callback

        # Add all buttons
        view.add_item(button_major)
        view.add_item(button_minor)
        view.add_item(button_member)
        view.add_item(button_personal)
        view.add_item(button_food)


        if target_channel:
            await target_channel.send(
                content="@everyone",
                embed=embed,
                view=view)

    await bot.process_commands(message)

bot.run(BOT_TOKEN)
