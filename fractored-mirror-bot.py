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

import success_overlay

load_dotenv()


BOT_TOKEN = os.getenv("DISCORD_TOKEN")
####################################################
# MAIN SERVER (Original Channel Buttons)
TARGET_CHANNEL_ID = int(os.getenv("TARGET"))
MAJOR_ID = int(os.getenv("MAJOR"))
MINOR_ID = int(os.getenv("MINOR"))
MEMBER_ID = int(os.getenv("MEMBER"))
FOOD_ID = int(os.getenv("FOOD"))
SUCCESS_ID = int(os.getenv("SUCCESS"))

# NEW FLIP CHANNELS
ONLINE_FLIPS_ID = int(os.getenv("ONLINE_FLIPS_ID"))
SEASONAL_FLIPS_ID = int(os.getenv("SEASONAL_FLIPS_ID"))
TARGET_FLIPS_ID = int(os.getenv("TARGET_FLIPS_ID"))
THRIFT_FLIPS_ID = int(os.getenv("THRIFT_FLIPS_ID"))
WALMART_FLIPS_ID = int(os.getenv("WALMART_FLIPS_ID"))
FLIGHT_DEALS_ID = int(os.getenv("FLIGHT_DEALS_ID"))
CHIPOTLE_ID = int(os.getenv("CHIPOTLE_ID"))
FOOD_ANNOUNCEMENT_ID = int(os.getenv("FOOD_ANNOUNCEMENT_ID"))

###################################################
# FORWARDING SERVER (Original)
MAJOR_FID = int(os.getenv("F_MAJOR"))
MINOR_FID = int(os.getenv("F_MINOR"))
MEMBER_FID = int(os.getenv("F_MEMBER"))
DEALS_FID = int(os.getenv("F_DEALS"))
FOOD_FID = int(os.getenv("F_FOOD"))
CHIPOTLE_FID = int(os.getenv("F_CHIPOTLE"))
TEST_CHANNEL = int(os.getenv("TEST_CHANNEL"))

# NEW FORWARDING SERVER CHANNELS
ONLINE_FLIPS_FID = int(os.getenv("ONLINE_FLIPS_FID"))
TARGET_FLIPS_FID = int(os.getenv("TARGET_FLIPS_FID"))
WALMART_FLIPS_FID = int(os.getenv("WALMART_FLIPS_FID"))
SEASONAL_FLIPS_FID = int(os.getenv("SEASONAL_FLIPS_FID"))
THRIFT_FLIPS_FID = int(os.getenv("THRIFT_FLIPS_FID"))
FLIGHT_FLIPS_FID = int(os.getenv("FLIGHT_FLIPS_FID"))
SMALL_PRICE_ERRORS_FID = int(os.getenv("SMALL_PRICE_ERRORS_FID"))
CHIPOTLE_FID = int(os.getenv("CHIPOTLE_FID"))
FOOD_FID = int(os.getenv("FOOD_FID"))

# Original source channels (for channel buttons)
ORIGINAL_SOURCE_CHANNEL_IDS = {MAJOR_FID, MINOR_FID, MEMBER_FID, DEALS_FID, FOOD_FID, CHIPOTLE_FID}

# Direct mapping from forwarding to main server (for new flip channels)
FORWARDING_TO_MAIN_MAP = {
    ONLINE_FLIPS_FID: ONLINE_FLIPS_ID,
    TARGET_FLIPS_FID: TARGET_FLIPS_ID,
    WALMART_FLIPS_FID: WALMART_FLIPS_ID,
    SEASONAL_FLIPS_FID: SEASONAL_FLIPS_ID,
    THRIFT_FLIPS_FID: THRIFT_FLIPS_ID,
    FLIGHT_FLIPS_FID: FLIGHT_DEALS_ID,  # Map to flight deals
    SMALL_PRICE_ERRORS_FID: ONLINE_FLIPS_ID,  # Map to online flips
    CHIPOTLE_FID: CHIPOTLE_ID,  # Map to chipotle
    FOOD_FID: FOOD_ANNOUNCEMENT_ID,  # Map to food announcements
}

# Combined source channels (both original and new)
SOURCE_CHANNEL_IDS = ORIGINAL_SOURCE_CHANNEL_IDS.union(set(FORWARDING_TO_MAIN_MAP.keys()))

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.messages = True
intents.reactions = True

bot = commands.Bot(command_prefix="!", intents=intents)

owner_message_id = {}

# Category color helper (source preview color only; routing recolor handled in embed_system)
CHANNEL_COLOR_MAP = {
    # Original channels
    "major": discord.Color.red(),
    "minor": discord.Color.orange(),
    "member": discord.Color.green(),
    "food": discord.Color.gold(),
    
    # New flip channels
    "online": discord.Color.blue(),
    "target": discord.Color.red(),
    "walmart": discord.Color.green(),
    "seasonal": discord.Color.orange(),
    "thrift": discord.Color.purple(),
    "flight-deals": discord.Color.gold(),
    "small-price-errors": discord.Color.dark_red(),
    "chipotle": discord.Color.teal(),
    "food": discord.Color.dark_gold(),
}


@bot.event
async def on_reaction_add(reaction, user):
    if user.bot:
        return
    
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
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    
    if message.content.strip().lower().startswith(';'):
        return

    # SUCCESS watermark flow
    if message.channel.id == SUCCESS_ID and message.attachments:
        # filter images
        atts = [a for a in message.attachments
                if a.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))]

        if not atts:
            return

        owner_id = message.author.id

        for att in atts:
            try:
                img_data = await att.read()
                # run PIL in a worker thread so we don't block the event loop
                watermarked = await asyncio.to_thread(
                    success_overlay.add_image_watermark,
                    img_data,
                    'watermark.png'
                )
                file = discord.File(watermarked, filename="watermarked.jpg")
                sent_message = await message.channel.send(f"{message.author.mention}", file=file)
                await sent_message.add_reaction("🗑️")
                owner_message_id[sent_message.id] = owner_id
                await asyncio.sleep(0.15)  # gentle on rate limits
            except Exception as e:
                await message.channel.send(f"⚠️ Failed `{att.filename}`: `{e}`")

        # delete AFTER sending
        try:
            await message.delete()
        except Exception:
            pass

        return


    # Check if message is from forwarding server
    if message.channel.id in SOURCE_CHANNEL_IDS:
        print(f"Processing message from forwarding server: {message.channel.name} ({message.channel.id})")
        
        # Check if this is a new flip channel (direct forwarding)
        if message.channel.id in FORWARDING_TO_MAIN_MAP:
            # Handle new flip channels - direct forwarding
            main_channel_id = FORWARDING_TO_MAIN_MAP.get(message.channel.id)
            main_channel = bot.get_channel(main_channel_id) or await bot.fetch_channel(main_channel_id)
            if not main_channel:
                print(f"Could not find main server channel {main_channel_id}")
                return

            # Wait for previews if needed
            if embed_generator.URL_RE.search(message.content) and not message.attachments:
                msg = await embed_generator.wait_a_bit_for_embeds(message, delay=1.2)
            else:
                msg = message

            parsed_data = embed_generator.parse_extracted_text(msg.content, message=msg)

            if not parsed_data.get("thumbnail_url"):
                thumb_from_embed = embed_generator.first_embed_image_url(msg)
                if thumb_from_embed:
                    parsed_data["thumbnail_url"] = thumb_from_embed
                    print("DING DONG")

            # Determine category based on source channel
            category = None
            if message.channel.id == ONLINE_FLIPS_FID:
                category = "online"
            elif message.channel.id == TARGET_FLIPS_FID:
                category = "target"
            elif message.channel.id == WALMART_FLIPS_FID:
                category = "walmart"
            elif message.channel.id == SEASONAL_FLIPS_FID:
                category = "seasonal"
            elif message.channel.id == THRIFT_FLIPS_FID:
                category = "thrift"
            elif message.channel.id == FLIGHT_FLIPS_FID:
                category = "flight-deals"
            elif message.channel.id == SMALL_PRICE_ERRORS_FID:
                category = "small-price-errors"
            elif message.channel.id == CHIPOTLE_FID:
                category = "chipotle"
            elif message.channel.id == FOOD_FID:
                category = "food"

            # Create embeds with multiple image support
            embeds, view = embed_generator.create_multiple_image_embeds(
                parsed_data,
                category=category,
                allow_edit=True,
                editor_user_ids={610239586454601763},  # <-- your admin IDs
                include_channel_buttons=False,  # No routing buttons needed for direct forwarding
                channel_buttons=[],
                channel_buttons_disable_after_send=False
            )

            if not embeds or not hasattr(embeds[0], "to_dict"):
                print("DEBUG: embeds is not valid. Type:", type(embeds))
                return

            # Send directly to main server channel
            try:
                file = discord.File("logo.png", filename="logo.png")
                # Add footer to all embeds
                for embed in embeds:
                    embed.set_footer(text="Pricehub", icon_url="attachment://logo.png")
                
                # Send multiple embeds to main server
                await main_channel.send(embeds=embeds, file=file)
                print(f"Successfully forwarded to main server channel: {main_channel.name}")
                
            except Exception as e:
                print(f"Error forwarding to main server: {e}")
                # Fallback: send original message content
                await main_channel.send(content=f"**Forwarded from {message.channel.name}:**\n{message.content}")
        
        else:
            # Handle original channels - with channel buttons
            target_channel = message.channel

            # Wait for previews if needed
            if embed_generator.URL_RE.search(message.content) and not message.attachments:
                msg = await embed_generator.wait_a_bit_for_embeds(message, delay=1.2)
            else:
                msg = message

            parsed_data = embed_generator.parse_extracted_text(msg.content, message=msg)

            if not parsed_data.get("thumbnail_url"):
                thumb_from_embed = embed_generator.first_embed_image_url(msg)
                if thumb_from_embed:
                    parsed_data["thumbnail_url"] = thumb_from_embed
                    print("DING DONG")

            # Source channel category (for initial preview color)
            category = message.channel.name.lower() if message.channel.name.lower() in CHANNEL_COLOR_MAP else None

            # Build embed + a composite view that already includes:
            # - link buttons
            # - Edit / Advanced buttons
            # - routing buttons (major/minor/member/food)
            channel_buttons = [
                {"label": "major",    "dest_id": MAJOR_ID,    "mention_everyone": True, "role_id": "1407983913581936712"},
                {"label": "minor",    "dest_id": MINOR_ID,    "mention_everyone": False, "role_id": "1407984094255644722"},
                {"label": "member",   "dest_id": MEMBER_ID,   "mention_everyone": False, "role_id": "1407984234127294546"},
                {"label": "food",     "dest_id": FOOD_ID,     "mention_everyone": False, "role_id": "1407984369733210204"},
            ]

            # Use multiple embeds for multiple images (quadrant layout)
            embeds, view = embed_generator.create_multiple_image_embeds(
                parsed_data,
                category=category,
                allow_edit=True,
                editor_user_ids={610239586454601763},  # <-- your admin IDs
                include_channel_buttons=True,
                channel_buttons=channel_buttons,
                channel_buttons_disable_after_send=True  # allow sending to multiple channels after edits
            )

            if not embeds or not hasattr(embeds[0], "to_dict"):
                print("DEBUG: embeds is not valid. Type:", type(embeds))
                return

            # Send preview in source channel
            if target_channel:
                file = discord.File("logo.png", filename="logo.png")
                # Add footer to all embeds
                for embed in embeds:
                    embed.set_footer(text="Pricehub", icon_url="attachment://logo.png")
                
                # Send multiple embeds (Discord will display them in a grid-like layout)
                await target_channel.send(embeds=embeds, view=view, file=file)

            # Send to test channel
            test_channel = bot.get_channel(TEST_CHANNEL) or await bot.fetch_channel(TEST_CHANNEL)
            test_embeds = [embed.copy() for embed in embeds]
            for embed in test_embeds:
                embed.set_footer(text="PriceHub", icon_url="attachment://logo.png")
            file2 = discord.File("logo.png", filename="logo.png")
            await test_channel.send(content="<@&1405692608747143219>", embeds=test_embeds, file=file2)


    await bot.process_commands(message)


bot.run(BOT_TOKEN)
