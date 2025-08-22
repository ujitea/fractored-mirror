# embed_system.py (aka embed_generator.py)
# Parsing + enrichments + embed builder + edit/advanced modals
# Composite view includes: link buttons + Edit/Advanced + channel routing buttons (recreated after edits)

import os
import re
import html
import asyncio
from urllib.parse import unquote, urlparse
from typing import Optional, Iterable, List, Dict, Any

import discord
from discord.ext import commands  # noqa: F401

DISCORD_FIELD_LIMIT = 1024

# ------------ Channel color map ------------
CHANNEL_COLOR_MAP = {
    "major": discord.Color.red(),
    "minor": discord.Color.orange(),
    "member": discord.Color.green(),
    "food": discord.Color.gold(),
}

# ------------ Parsing helpers & regexes ------------
FIELD_KEYS = {
    "price": "price",
    "discount": "discount",
    "status": "status",
    "stock": "stock",
    "sku": "sku",
    "seller": "seller",
    "promotion": "promotion",
    "business required": "business_required",
    "offer id": "offer_id",
}

KNOWN_LINK_LABELS = {"ATC", "KEEPA", "SAS", "EBAY", "GOOGLE", "CHECK STOCK", "WALMART", "TARGET", "BESTBUY"}

URL_RE = re.compile(r"(https?://\S+)")
BOLD_FIELD_RE = re.compile(r"\*\*(.+?)\*\*:\s*(.+)")
BOLD_LINE_RE = re.compile(r"^\*\*(.+?)\*\*$")
MD_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^\s)]+)\)")
MD_IMAGE_RE = re.compile(r"!\[[^\]]*\]\((https?://[^\s)]+)\)")
IMG_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".webp")

# Promotions / metadata
CODE_RE = re.compile(r"(?:code|coupon)\s*[:\-]?\s*([A-Z0-9]{3,15})\b", re.I)
TODAY_ONLY_RE = re.compile(r"\b(today only)\b", re.I)
THRU_RE = re.compile(r"\b(?:through|thru)\s+([A-Za-z]{3,9})\s+(\d{1,2})\b", re.I)
WHILE_SUPPLIES_RE = re.compile(r"while supplies last", re.I)
BOGO_RE = re.compile(r"\bBOGO\b|\bbuy\s+one,\s*get\s+one\b", re.I)
FREE_WP_RE = re.compile(r"\bfree\b.*\b(with|w\/)\s*purchase\b", re.I)
GLITCH_RE = re.compile(r"\b(glitch|price\s+glitched)\b", re.I)
VCC_RE = re.compile(r"\bVCC\b", re.I)
BIRTHDAY_RE = re.compile(r"\bbirthday\b", re.I)

WAS_NOW_RE = re.compile(r"was[:\s]*\$\s*([\d\.xX]+).*?now[:\s]*\$\s*([\d\.xX]+)", re.I)
DOLLAR_ANY_RE = re.compile(r"\$\s*[\d]+(?:\.[\dxX]{1,2})?")

NOISE_TOKENS = {"a", "ddd", "m", "so weird"}

DOMAIN_SELLERS = {
    "amazon.com": "Amazon",
    "electronics.woot.com": "Woot",
    "woot.com": "Woot",
    "meh.com": "Meh",
    "costco.com": "Costco",
    "target.com": "Target",
    "walmart.com": "Walmart",
    "mavely.app": "Mavely",
    "bit.ly": None,
}

MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug",
     "Sep", "Oct", "Nov", "Dec"], start=1)
}

# ------------ Utility helpers ------------

async def wait_a_bit_for_embeds(message: discord.Message, delay: float) -> discord.Message:
    await asyncio.sleep(delay)
    try:
        return await message.channel.fetch_message(message.id)
    except Exception:
        return message


def first_embed_image_url(msg: discord.Message) -> Optional[str]:
    for emb in getattr(msg, "embeds", []) or []:
        if getattr(emb, "thumbnail", None):
            if getattr(emb.thumbnail, "url", None):
                return emb.thumbnail.url
            if getattr(emb.thumbnail, "proxy_url", None):
                return emb.thumbnail.proxy_url
        if getattr(emb, "image", None):
            if getattr(emb.image, "url", None):
                return emb.image.url
            if getattr(emb.image, "proxy_url", None):
                return emb.image.proxy_url
    return None


def harvest_images_from_message(msg: discord.Message) -> list[str]:
    imgs: list[str] = []
    
    # Get images from attachments
    for att in getattr(msg, "attachments", []) or []:
        try:
            if att.content_type and att.content_type.startswith("image/"):
                imgs.append(att.url)
            else:
                url = (att.url or "").lower()
                if url.split("?", 1)[0].endswith(IMG_EXTS):
                    imgs.append(att.url)
        except Exception:
            pass
    
    # Get images from embeds
    for emb in getattr(msg, "embeds", []) or []:
        for part in (getattr(emb, "thumbnail", None), getattr(emb, "image", None)):
            if part and getattr(part, "url", None):
                imgs.append(part.url)
            elif part and getattr(part, "proxy_url", None):
                imgs.append(part.proxy_url)
    
    # Get images from message content (markdown images and image URLs)
    if msg.content:
        # Markdown images: ![alt](url)
        md_images = MD_IMAGE_RE.findall(msg.content)
        for img_url in md_images:
            imgs.append(unquote(img_url))
        
        # Direct image URLs
        all_urls = URL_RE.findall(msg.content)
        for url in all_urls:
            url = unquote(url.rstrip(')'))
            if looks_like_image_url(url):
                imgs.append(url)
    
    # Remove duplicates while preserving order
    out, seen = [], set()
    for u in imgs:
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    return out


def looks_like_image_url(url: str) -> bool:
    """Check if a URL looks like an image URL"""
    try:
        bare_url = url.split("?", 1)[0].lower()
        return (bare_url.endswith(IMG_EXTS) or 
                "cdn.discordapp.com" in url or
                "media.discordapp.net" in url or
                any(domain in url.lower() for domain in ["imgur.com", "i.imgur.com", "images.unsplash.com", "picsum.photos"]))
    except:
        return False


def _clean(s: str) -> str:
    s = html.unescape(s or "").strip()
    return s.rstrip(".,;")


def looks_like_deal_post(text: str) -> bool:
    t = html.unescape(text or "").strip()
    if "Deal Info:" in t:
        return True
    if BOLD_FIELD_RE.search(t):
        return True
    has_price = re.search(r"\$\d", t) or re.search(r"\bprice\b", t, re.I)
    has_url = URL_RE.search(t) or MD_LINK_RE.search(t)
    if has_price and has_url:
        return True
    if any(lbl in t.upper() for lbl in ("ATC", "KEEPA", "SAS", "SKU", "IN-STOCK", "OUT OF STOCK")) and has_url:
        return True
    return False


def normalize_price_token(tok: str) -> str:
    tok = tok.replace(" ", "")
    return tok.upper()


def infer_seller_from_urls(urls: list[str]) -> Optional[str]:
    for u in urls:
        try:
            host = urlparse(u).netloc.lower()
            for dom, name in DOMAIN_SELLERS.items():
                if host.endswith(dom):
                    return name
        except Exception:
            pass
    return None


def enrich_promos(parsed: dict, text: str, message_date_iso: Optional[str] = None):
    t = text
    tags = set(parsed.get("tags", []))
    risk = set(parsed.get("risk", []))
    validity = parsed.get("validity", {}) or {}

    m = CODE_RE.search(t)
    if m:
        parsed["code"] = m.group(1)
        tags.add("has-code")

    if TODAY_ONLY_RE.search(t) and message_date_iso:
        validity["type"] = "date"
        validity["end"] = message_date_iso
        tags.add("today-only")

    m = THRU_RE.search(t)
    if m and message_date_iso:
        mon, day = m.group(1)[:3].title(), int(m.group(2))
        year = int(message_date_iso[:4])
        mon_num = MONTHS.get(mon, None)
        if mon_num:
            validity["type"] = "date"
            validity["end"] = f"{year:04d}-{mon_num:02d}-{day:02d}"

    if WHILE_SUPPLIES_RE.search(t):
        validity["disclaimer"] = "while-supplies-last"

    if BOGO_RE.search(t):
        tags.update(("promo", "bogo"))
    if FREE_WP_RE.search(t):
        tags.update(("promo", "free-with-purchase"))
    if GLITCH_RE.search(t):
        tags.update(("glitch", "YMMV"))
        risk.add("pricing-glitch")
    if VCC_RE.search(t):
        tags.add("VCC-recommended")
        risk.add("payment-caution")
    if BIRTHDAY_RE.search(t):
        tags.update(("freebies", "birthday"))
    if "DYOR" in t.upper():
        tags.add("DYOR")
        risk.add("needs-research")

    if tags:
        parsed["tags"] = sorted(tags)
    if risk:
        parsed["risk"] = sorted(risk)
    if validity:
        parsed["validity"] = validity


def add_prices(parsed: dict, text: str):
    if "old_price" not in parsed and "new_price" not in parsed:
        m = WAS_NOW_RE.search(text)
        if m:
            parsed["old_price"] = normalize_price_token("$" + m.group(1))
            parsed["new_price"] = normalize_price_token("$" + m.group(2))
    if "price" not in parsed:
        m = DOLLAR_ANY_RE.search(text)
        if m:
            parsed["price"] = normalize_price_token(m.group(0))


def classify_quality(parsed: dict, raw_text: str) -> None:
    t = raw_text.strip().lower()
    only_everyone = (t.replace("@everyone", "").strip() == "")
    is_noise_token = t in NOISE_TOKENS
    no_title = parsed.get("title", "").strip().lower() == "no title"
    if only_everyone or is_noise_token or no_title:
        parsed["quality"] = "noise"
    else:
        if ("glitch" in (parsed.get("tags") or [])) and not parsed.get("price") and not parsed.get("new_price"):
            parsed["quality"] = "unknown"
        else:
            parsed.setdefault("quality", "deal")


def pick_color_for(data: dict, category: Optional[str] = None) -> discord.Color:
    if category and category in CHANNEL_COLOR_MAP:
        return CHANNEL_COLOR_MAP[category]
    for tag in (data.get("tags") or []):
        if tag in CHANNEL_COLOR_MAP:
            return CHANNEL_COLOR_MAP[tag]
    return discord.Color.blurple()

# ----- Embed recolor helper for routing -----
def recolor_embed(src_embed: discord.Embed, color: discord.Color) -> discord.Embed:
    # Base embed
    e = discord.Embed(
        title=src_embed.title,
        url=src_embed.url,
        description=src_embed.description,
        color=color,
        timestamp=getattr(src_embed, "timestamp", None),
    )

    # Fields
    for f in src_embed.fields:
        e.add_field(name=f.name, value=f.value, inline=f.inline)

    # Images
    if src_embed.image and src_embed.image.url:
        e.set_image(url=src_embed.image.url)
    # Keep thumbnail if present (only used when no image—optional)
    if src_embed.thumbnail and src_embed.thumbnail.url:
        e.set_thumbnail(url=src_embed.thumbnail.url)

    # Footer
    footer = getattr(src_embed, "footer", None)
    if footer and getattr(footer, "text", None):
        icon = getattr(footer, "icon_url", None) or None
        e.set_footer(text=footer.text, icon_url=icon)

    # Author
    author = getattr(src_embed, "author", None)
    if author and getattr(author, "name", None):
        e.set_author(
            name=author.name,
            url=getattr(author, "url", None) or None,
            icon_url=getattr(author, "icon_url", None) or None,
        )

    return e


# ------------ Core parse + embed build ------------

def parse_extracted_text(raw_text: str, message: Optional[discord.Message] = None) -> dict:
    text = html.unescape(raw_text or "")
    parsed: dict = {"links": {}}
    parsed["raw_text"] = raw_text  # <-- Add this line
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    parsed["images"] = []
    if message:
        parsed["images"] = harvest_images_from_message(message)

    # Title detection
    title = None
    if lines:
        m = re.match(r"^Deal\s*Info\s*:\s*(.+)$", lines[0], flags=re.I)
        if m:
            title = _clean(m.group(1)); lines = lines[1:]
        else:
            first = lines[0]
            m2 = BOLD_LINE_RE.match(first)
            if m2 and not BOLD_FIELD_RE.match(first):
                title = _clean(m2.group(1)); lines = lines[1:]
    if not title:
        for i, ln in enumerate(list(lines)):
            if not BOLD_FIELD_RE.match(ln) and not URL_RE.match(ln) and not MD_LINK_RE.search(ln):
                title = _clean(ln.strip("* ")); del lines[i]; break
    parsed["title"] = title or "No Title"

    # **Field**: value lines
    for ln in list(lines):
        m = BOLD_FIELD_RE.match(ln)
        if not m:
            continue
        key_raw, value_raw = m.group(1).strip(), m.group(2).strip()
        key = FIELD_KEYS.get(key_raw.lower())
        val = _clean(value_raw)
        if key:
            parsed[key] = val
        else:
            if key_raw.lower() in ("other", "add to cart", "add to cart links"):
                for lbl, href in MD_LINK_RE.findall(ln):
                    parsed["links"][lbl.upper()] = unquote(href)
                for href in URL_RE.findall(ln):
                    parsed["links"].setdefault("URL", unquote(href))
            else:
                parsed[key_raw.lower().replace(" ", "_")] = val

    # MD links / URLs
    for lbl, href in MD_LINK_RE.findall(text):
        parsed["links"][lbl.upper()] = unquote(href)
    seen, urls = set(), []
    for u in URL_RE.findall(text):
        u = unquote(u.rstrip(')'))
        if u not in seen:
            seen.add(u); urls.append(u)

    # Enhanced image handling - capture multiple images from text
    if not parsed["images"]:
        # Look for markdown images in text
        md_imgs = [unquote(u) for u in MD_IMAGE_RE.findall(text)]
        # Look for direct image URLs in text
        image_urls = [u for u in urls if looks_like_image_url(u)]
        
        # Combine all found images
        all_images = md_imgs + image_urls
        if all_images:
            parsed["images"] = all_images
    
    # Set thumbnail if not already set
    if not parsed.get("thumbnail_url") and parsed["images"]:
        parsed["thumbnail_url"] = parsed["images"][0]

    # Choose product url (prefer non-cart)
    if "url" not in parsed:
        candidates = [u for u in urls if not any(tag in u.lower() for tag in ("submit.buy-now", "handle-buy-box", "add-to-cart", "cart", "checkout"))]
        parsed["url"] = candidates[-1] if candidates else (urls[-1] if urls else None)

    # ATC
    atc = None
    for k in ("ATC", "ADD TO CART", "BUY", "CHECK STOCK"):
        if k in parsed["links"]:
            atc = parsed["links"][k]; break
    if not atc:
        for u in urls:
            if any(tag in u.lower() for tag in ("submit.buy-now", "handle-buy-box", "add-to-cart", "cart")):
                atc = u; break
    if atc:
        parsed["atc_url"] = atc
        parsed["links"].setdefault("ATC", atc)

    # Seller fallback
    if not parsed.get("seller") and urls:
        seller = infer_seller_from_urls(urls)
        if seller:
            parsed["seller"] = seller

    # Normalize booleans as strings
    for b in ("promotion", "business_required"):
        if b in parsed:
            parsed[b] = str(parsed[b]).strip().lower()

    add_prices(parsed, text)
    msg_iso = None
    if message and getattr(message, "created_at", None):
        try:
            msg_iso = message.created_at.replace(tzinfo=None).isoformat()[:10]
        except Exception:
            msg_iso = None
    enrich_promos(parsed, text, message_date_iso=msg_iso or os.getenv("MSG_DATE_ISO"))
    classify_quality(parsed, text)
    return parsed

# ------------ Embed + Buttons + Modals ------------

def clamp(s: str, n: int = DISCORD_FIELD_LIMIT) -> str:
    s = str(s)
    return s if len(s) <= n else s[: n - 1] + "…"


class DealEditModal(discord.ui.Modal, title="Edit Deal"):
    def __init__(
        self,
        data,
        category=None,
        editor_user_ids=None,
        channel_buttons=None,  # <-- Correct!
        channel_buttons_disable_after_send=False,
        *args, **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.data = data
        self.category = category
        self.editor_user_ids = editor_user_ids
        self.channel_buttons = channel_buttons or []
        self.channel_buttons_disable_after_send = channel_buttons_disable_after_send
        # Add a field for description/message
        self.description = discord.ui.TextInput(
            label="Description",
            style=discord.TextStyle.paragraph,
            default=data.get("description") or data.get("raw_text") or "",
            required=False,
            max_length=1024
        )
        self.add_item(self.description)
        # ...add other fields as needed...

    async def on_submit(self, interaction: discord.Interaction):
        self.data["description"] = self.description.value
        embed, view = embed_from_parsed(
            self.data,
            category=self.category,
            allow_edit=True,
            editor_user_ids=self.editor_user_ids,
            include_channel_buttons=True,
            channel_buttons=self.channel_buttons,
            channel_buttons_disable_after_send=self.channel_buttons_disable_after_send,
        )
        embed.set_footer(text="pricehub", icon_url="attachment://logo.png")
        await interaction.response.edit_message(embed=embed, view=view)

class DealAdvancedModal(discord.ui.Modal, title="Advanced Edit"):
    seller_input = discord.ui.TextInput(label="Seller (optional)", required=False, max_length=64, placeholder="Amazon / Woot / Target ...")
    image_url_input = discord.ui.TextInput(label="Image URL (optional)", required=False, max_length=400, placeholder="https://...")

    def __init__(self, data: dict, category: Optional[str], editor_ids: Optional[Iterable[int]],
                 channel_buttons: Optional[List[Dict[str, Any]]] = None,
                 channel_buttons_disable_after_send: bool = False):
        super().__init__()
        self.data = dict(data)
        self.category = category
        self.editor_ids = set(editor_ids or [])
        self.channel_buttons = channel_buttons or []
        self.channel_buttons_disable_after_send = channel_buttons_disable_after_send
        self.seller_input.default = self.data.get("seller") or ""
        self.image_url_input.default = self.data.get("thumbnail_url") or (self.data.get("images") or [None])[0] or ""

    async def on_submit(self, interaction: discord.Interaction) -> None:
        can_edit = False
        if interaction.user:
            if self.editor_ids and interaction.user.id in self.editor_ids:
                can_edit = True
            elif interaction.user.guild_permissions.manage_messages:
                can_edit = True
        if not can_edit:
            await interaction.response.send_message("You don't have permission to edit this embed.", ephemeral=True)
            return

        if self.seller_input.value is not None:
            s = self.seller_input.value.strip()
            if s:
                self.data["seller"] = s
            elif "seller" in self.data:
                del self.data["seller"]
        if self.image_url_input.value is not None:
            img = self.image_url_input.value.strip()
            if img:
                self.data["thumbnail_url"] = img
                imgs = self.data.get("images") or []
                if img not in imgs:
                    self.data["images"] = [img] + imgs
            elif "thumbnail_url" in self.data:
                del self.data["thumbnail_url"]

        embed, view = embed_from_parsed(
            self.data,
            category=self.category,
            allow_edit=True,
            editor_user_ids=self.editor_ids,
            include_channel_buttons=True,
            channel_buttons=self.channel_buttons,
            channel_buttons_disable_after_send=self.channel_buttons_disable_after_send,
        )
        file = discord.File("logo.png", filename="logo.png")
        embed.set_footer(text="pricehub", icon_url="attachment://logo.png")
        await interaction.response.edit_message(embed=embed, view=view)



class DealLinkView(discord.ui.View):
    """Composite View: link buttons + optional Edit/Advanced + optional channel routing buttons."""
    def __init__(self, links: Optional[dict], data: dict,
                 category: Optional[str] = None,
                 allow_edit: bool = False,
                 editor_user_ids: Optional[Iterable[int]] = None,
                 channel_buttons: Optional[List[Dict[str, Any]]] = None,
                 channel_buttons_disable_after_send: bool = False,
                 timeout: Optional[float] = None):
        super().__init__(timeout=timeout)
        self.data = data
        self.category = category
        self.editor_user_ids = set(editor_user_ids or [])
        self.channel_buttons = channel_buttons or []
        self.channel_buttons_disable_after_send = channel_buttons_disable_after_send

        order = ["ATC", "KEEPA", "SAS", "EBAY", "GOOGLE", "CHECK STOCK", "WALMART", "TARGET", "BESTBUY"]
        added = 0

        links = links or {}
        # Leave space: max 25 components total.
        # Reserve 2 for Edit/Advanced, and up to 5 for channel buttons => cap link buttons to 18.
        LINK_CAP = max(0, 25 - 2 - len(self.channel_buttons))
        LINK_CAP = min(LINK_CAP, 18)  # hard cap

        for lbl in order:
            if added >= LINK_CAP:
                break
            url = links.get(lbl)
            if url:
                self.add_item(discord.ui.Button(label=lbl.title()[:80], url=url))
                added += 1

        if added < LINK_CAP:
            for lbl, url in links.items():
                if added >= LINK_CAP:
                    break
                U = lbl.upper()
                if U not in order and url:
                    self.add_item(discord.ui.Button(label=lbl[:80], url=url))
                    added += 1

        # Edit / Advanced
        if allow_edit:
            self.add_item(self.EditButton(self))
            self.add_item(self.AdvancedButton(self))

        # Channel routing buttons
        for cfg in self.channel_buttons:
            label = str(cfg.get("label", "send"))[:80]
            dest_id = int(cfg["dest_id"])
            mention_everyone = bool(cfg.get("mention_everyone", False))
            role_id = cfg.get("role_id")
            self.add_item(self.RouteButton(self, label, dest_id, mention_everyone, role_id))

    class EditButton(discord.ui.Button):
        def __init__(self, parent_view: "DealLinkView"):
            super().__init__(label="Edit", style=discord.ButtonStyle.primary)
            self.parent_view = parent_view

        async def callback(self, interaction: discord.Interaction):
            user_ok = False
            if interaction.user:
                if self.parent_view.editor_user_ids and interaction.user.id in self.parent_view.editor_user_ids:
                    user_ok = True
                elif interaction.user.guild_permissions.manage_messages:
                    user_ok = True
            if not user_ok:
                await interaction.response.send_message("You don't have permission to edit this embed.", ephemeral=True)
                return
            modal = DealEditModal(
                self.parent_view.data,
                self.parent_view.category,
                self.parent_view.editor_user_ids,
                channel_buttons=self.parent_view.channel_buttons,
                channel_buttons_disable_after_send=self.parent_view.channel_buttons_disable_after_send
            )
            await interaction.response.send_modal(modal)

    class AdvancedButton(discord.ui.Button):
        def __init__(self, parent_view: "DealLinkView"):
            super().__init__(label="Advanced", style=discord.ButtonStyle.secondary)
            self.parent_view = parent_view

        async def callback(self, interaction: discord.Interaction):
            user_ok = False
            if interaction.user:
                if self.parent_view.editor_user_ids and interaction.user.id in self.parent_view.editor_user_ids:
                    user_ok = True
                elif interaction.user.guild_permissions.manage_messages:
                    user_ok = True
            if not user_ok:
                await interaction.response.send_message("You don't have permission to edit this embed.", ephemeral=True)
                return
            modal = DealAdvancedModal(
                self.parent_view.data,
                self.parent_view.category,
                self.parent_view.editor_user_ids,
                channel_buttons=self.parent_view.channel_buttons,
                channel_buttons_disable_after_send=self.parent_view.channel_buttons_disable_after_send
            )
            await interaction.response.send_modal(modal)

    class RouteButton(discord.ui.Button):
        def __init__(self, parent_view: "DealLinkView", label: str, dest_id: int, mention_everyone: bool, role_id: str = None):
            super().__init__(label=label, style=discord.ButtonStyle.success)
            self.parent_view = parent_view
            self.dest_id = dest_id
            self.mention_everyone = mention_everyone
            self.role_id = role_id
            self.label_lower = label.lower()

        async def callback(self, interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            # Use interaction.client as the Bot
            bot = interaction.client
            dest = bot.get_channel(self.dest_id) or await bot.fetch_channel(self.dest_id)
            if not dest:
                await interaction.followup.send(f"{self.label} channel not found.", ephemeral=True)
                return

            # Build content with mentions
            content_parts = []
            if self.mention_everyone:
                content_parts.append("@everyone")
            if self.role_id:
                content_parts.append(f"<@&{self.role_id}>")
            
            content = " ".join(content_parts) if content_parts else None
            
            # Handle multiple embeds (quadrant layout)
            if len(interaction.message.embeds) > 1:
                # Recolor all embeds
                recolored_embeds = []
                color = CHANNEL_COLOR_MAP.get(self.label_lower, discord.Color.blurple())
                for embed in interaction.message.embeds:
                    recolored_embeds.append(recolor_embed(embed, color))
                await dest.send(content=content, embeds=recolored_embeds)
            else:
                # Single embed (fallback)
                color = CHANNEL_COLOR_MAP.get(self.label_lower, discord.Color.blurple())
                e = recolor_embed(interaction.message.embeds[0], color) if interaction.message.embeds else None
                if e:
                    await dest.send(content=content, embed=e)
                else:
                    await dest.send(content=content or "Forwarded message")

            # Optionally disable routing buttons after send
            if self.parent_view.channel_buttons_disable_after_send:
                for item in self.parent_view.children:
                    if isinstance(item, discord.ui.Button) and isinstance(item, self.__class__):
                        item.disabled = True
                try:
                    await interaction.message.edit(view=self.parent_view)
                except Exception:
                    pass

            await interaction.followup.send(f"Sent to {self.label}.", ephemeral=True)



def embed_from_parsed(
    data: dict,
    *,
    category: Optional[str] = None,
    allow_edit: bool = False,
    editor_user_ids: Optional[Iterable[int]] = None,
    include_channel_buttons: bool = True,
    channel_buttons: Optional[List[Dict[str, Any]]] = None,
    channel_buttons_disable_after_send: bool = False,
) -> tuple[discord.Embed, Optional[discord.ui.View]]:
    color = pick_color_for(data, category)
    embed = discord.Embed(
        title=None,
        url=None,
        color=color,
        description=None
    )

   
    # 2. Code field (if present)
    code = data.get("code")
    if code:
        embed.add_field(name="Code", value=f"`{code}`", inline=False)

    # 3. Description (original message content, or parsed description)
    desc = data.get("description") or data.get("raw_text") or ""
    if not desc:
        desc = data.get("title", "")
    if desc:
        embed.add_field(name="Description", value=clamp(desc), inline=False)

    # Handle multiple images
    images = data.get("images", [])
    thumbnail_url = data.get("thumbnail_url")
    
    if images:
        # Set main image to first image
        embed.set_image(url=images[0])
        
        # If there are additional images, add them as a field
        if len(images) > 1:
            additional_images = images[1:]
            image_links = []
            for i, img_url in enumerate(additional_images, 2):
                image_links.append(f"[Image {i}]({img_url})")
            
            if image_links:
                embed.add_field(
                    name="Additional Images", 
                    value=" | ".join(image_links), 
                    inline=False
                )
    elif thumbnail_url:
        embed.set_image(url=thumbnail_url)

    view = DealLinkView(
        links=data.get("links") or {},
        data=data,
        category=category,
        allow_edit=allow_edit,
        editor_user_ids=editor_user_ids,
        channel_buttons=(channel_buttons or []) if include_channel_buttons else [],
        channel_buttons_disable_after_send=channel_buttons_disable_after_send,
        timeout=None,
    )
    return embed, view


def create_multiple_image_embeds(
    data: dict,
    *,
    category: Optional[str] = None,
    allow_edit: bool = False,
    editor_user_ids: Optional[Iterable[int]] = None,
    include_channel_buttons: bool = True,
    channel_buttons: Optional[List[Dict[str, Any]]] = None,
    channel_buttons_disable_after_send: bool = False,
) -> tuple[List[discord.Embed], Optional[discord.ui.View]]:
    """Create multiple embeds for multiple images in a grid-like layout"""
    images = data.get("images", [])
    if len(images) <= 1:
        # If only one or no images, use the regular single embed
        embed, view = embed_from_parsed(
            data, category=category, allow_edit=allow_edit,
            editor_user_ids=editor_user_ids, include_channel_buttons=include_channel_buttons,
            channel_buttons=channel_buttons, channel_buttons_disable_after_send=channel_buttons_disable_after_send
        )
        return [embed], view
    
    # Create multiple embeds for multiple images
    embeds = []
    color = pick_color_for(data, category)
    
    # Main embed with info and first image
    main_embed = discord.Embed(
        title=None,
        url=None,
        color=color,
        description=None
    )
    
    # Add code field
    code = data.get("code")
    if code:
        main_embed.add_field(name="Code", value=f"`{code}`", inline=False)
    
    # Add description
    desc = data.get("description") or data.get("raw_text") or ""
    if not desc:
        desc = data.get("title", "")
    if desc:
        main_embed.add_field(name="Description", value=clamp(desc), inline=False)
    
    # Set first image
    main_embed.set_image(url=images[0])
    embeds.append(main_embed)
    
    # Create additional embeds for remaining images (up to 3 more for grid layout)
    for i, img_url in enumerate(images[1:4], 2):  # Limit to 4 total images
        img_embed = discord.Embed(color=color)
        img_embed.set_image(url=img_url)
        embeds.append(img_embed)
    
    # Create view (only on the first embed)
    view = DealLinkView(
        links=data.get("links") or {},
        data=data,
        category=category,
        allow_edit=allow_edit,
        editor_user_ids=editor_user_ids,
        channel_buttons=(channel_buttons or []) if include_channel_buttons else [],
        channel_buttons_disable_after_send=channel_buttons_disable_after_send,
        timeout=None,
    )
    
    return embeds, view

# ------------ Example usage (optional) ------------
async def handle_message_example(message: discord.Message, *, category: Optional[str] = None,
                                 allow_edit: bool = False, editor_user_ids: Optional[Iterable[int]] = None):
    if URL_RE.search(message.content) and not message.attachments:
        message = await wait_a_bit_for_embeds(message, 1.2)

    parsed = parse_extracted_text(message.content, message)
    if not parsed.get("thumbnail_url"):
        if (thumb := first_embed_image_url(message)):
            parsed["thumbnail_url"] = thumb

    embed, view = embed_from_parsed(
        parsed,
        category=category,
        allow_edit=allow_edit,
        editor_user_ids=editor_user_ids
    )
    await message.channel.send(embed=embed, view=view)
