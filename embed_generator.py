import os
import re
import html
from urllib.parse import unquote

import discord
from discord.ext import commands

DISCORD_FIELD_LIMIT = 1024

# ------------ Parsing helpers ------------

FIELD_KEYS = {
    "price": "price",
    "new price": "new_price",
    "old price": "old_price",
    "discount": "discount",
    "status": "status",
    "stock": "stock",
    "sku": "sku",
    "seller": "seller",
    "promotion": "promotion",
    "business required": "business_required",
    "offer id": "offer_id",
}

KNOWN_LINK_LABELS = {"ATC","KEEPA","SAS","EBAY","GOOGLE","CHECK STOCK","WALMART","TARGET","BESTBUY"}

URL_RE = re.compile(r"(https?://\S+)")
BOLD_FIELD_RE = re.compile(r"\*\*(.+?)\*\*:\s*(.+)")
BOLD_LINE_RE = re.compile(r"^\*\*(.+?)\*\*$")
MD_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^\s)]+)\)")
MD_IMAGE_RE = re.compile(r"!\[[^\]]*\]\((https?://[^\s)]+)\)")
IMG_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".webp")


def first_embed_image_url(msg: discord.Message) -> str | None:
    for emb in msg.embeds:
        # Thumbnail (upper-right) from the preview
        if getattr(emb, "thumbnail", None):
            if getattr(emb.thumbnail, "url", None):
                return emb.thumbnail.url
            if getattr(emb.thumbnail, "proxy_url", None):
                return emb.thumbnail.proxy_url
        # Full image (sometimes providers use this instead)
        if getattr(emb, "image", None):
            if getattr(emb.image, "url", None):
                return emb.image.url
            if getattr(emb.image, "proxy_url", None):
                return emb.image.proxy_url
    return None



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
    if any(lbl in t.upper() for lbl in ("ATC","KEEPA","SAS","SKU","IN-STOCK","OUT OF STOCK")) and has_url:
        return True
    return False

def parse_extracted_text(raw_text: str) -> dict:
    text = html.unescape(raw_text or "")
    parsed = {"links": {}}
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    # --- Title detection (allow colons; avoid "**Field**: value") ---
    title = None
    if lines:
        m = re.match(r"^Deal\s*Info\s*:\s*(.+)$", lines[0], flags=re.I)
        if m:
            title = _clean(m.group(1)); lines = lines[1:]
        else:
            first = lines[0]
            m2 = BOLD_LINE_RE.match(first)  # r"^\*\*(.+?)\*\*$"
            # accept fully bold line as title unless it's a "**Field**: value" pattern
            if m2 and not BOLD_FIELD_RE.match(first):  # r"\*\*(.+?)\*\*:\s*(.+)"
                title = _clean(m2.group(1)); lines = lines[1:]

    # Fallback: take the first non-field, non-URL line as title
    if not title:
        for i, ln in enumerate(lines):
            if not BOLD_FIELD_RE.match(ln) and not URL_RE.match(ln) and not MD_LINK_RE.search(ln):
                title = _clean(ln.strip("* "))
                del lines[i]
                break

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

    # Collect markdown links / naked URLs across the whole text
    for lbl, href in MD_LINK_RE.findall(text):
        parsed["links"][lbl.upper()] = unquote(href)

    seen, urls = set(), []
    for u in URL_RE.findall(text):
        u = unquote(u.rstrip(')'))
        if u not in seen:
            seen.add(u); urls.append(u)

        # If no explicit thumbnail, try to extract one from text
    if not parsed.get("thumbnail_url"):
        # 1) Prefer markdown image syntax ![alt](url)
        md_imgs = [unquote(u) for u in MD_IMAGE_RE.findall(text)]

        # 2) Fall back to any URLs we found
        candidates = md_imgs + urls

        def looks_like_image(u: str) -> bool:
            bare = u.split("?", 1)[0].lower()
            if bare.endswith(IMG_EXTS):
                return True
            # Accept Discord CDN attachments even if extension is hidden by query params
            return "cdn.discordapp.com" in u and "/attachments/" in u

        thumb = next((u for u in candidates if looks_like_image(u)), None)
        if thumb:
            parsed["thumbnail_url"] = thumb


    # Choose product url (prefer non-cart)
    if "url" not in parsed:
        candidates = [u for u in urls if not any(tag in u.lower() for tag in ("submit.buy-now","handle-buy-box","add-to-cart","cart","checkout"))]
        parsed["url"] = candidates[-1] if candidates else (urls[-1] if urls else None)

    # ATC (explicit first, fallback by pattern)
    atc = None
    for k in ("ATC","ADD TO CART","BUY","CHECK STOCK"):
        if k in parsed["links"]:
            atc = parsed["links"][k]; break
    if not atc:
        for u in urls:
            if any(tag in u.lower() for tag in ("submit.buy-now","handle-buy-box","add-to-cart","cart")):
                atc = u; break
    if atc:
        parsed["atc_url"] = atc
        parsed["links"].setdefault("ATC", atc)

    # Thumbnail guess
    for u in urls:
        if u.lower().split("?")[0].endswith((".jpg",".jpeg",".png",".gif",".webp")):
            parsed["thumbnail_url"] = u
            break

    # Normalize booleans as strings (discord fields expect str)
    for b in ("promotion","business_required"):
        if b in parsed:
            parsed[b] = str(parsed[b]).strip().lower()

    return parsed

# ------------ Embed + Buttons ------------

def clamp(s: str, n: int = DISCORD_FIELD_LIMIT) -> str:
    s = str(s)
    return s if len(s) <= n else s[: n - 1] + "…"

def build_link_view(links: dict | None) -> discord.ui.View | None:
    if not links:
        return None
    view = discord.ui.View(timeout=None)
    order = ["ATC","KEEPA","SAS","EBAY","GOOGLE","CHECK STOCK","WALMART","TARGET","BESTBUY"]
    added = 0

    for lbl in order:
        url = links.get(lbl)
        if url:
            view.add_item(discord.ui.Button(label=lbl.title()[:80], url=url))
            added += 1
            if added >= 25:
                return view
    for lbl, url in links.items():
        U = lbl.upper()
        if U not in order:
            view.add_item(discord.ui.Button(label=lbl[:80], url=url))
            added += 1
            if added >= 25:
                break
    return view if added else None

def embed_from_parsed(data: dict) -> tuple[discord.Embed, discord.ui.View | None]:
    embed = discord.Embed(
        title=data.get("title", "No Title"),
        url=data.get("url"),
        color=discord.Color.blurple()
    )
    if thumb := data.get("thumbnail_url"):
        embed.set_thumbnail(url=thumb)

    for key, label in (
        ("new_price","New Price"),
        ("old_price","Old Price"),
        ("price","Price"),
        ("discount","Discount"),
        ("status","Status"),
        ("stock","Stock"),
        ("sku","SKU"),
        ("seller","Seller"),
        ("promotion","Promotion"),
        ("business_required","Business Required"),
        ("offer_id","Offer ID"),
    ):
        if val := data.get(key):
            embed.add_field(name=label, value=clamp(val), inline=True)

    # NEW: add a clickable ATC field in the embed body
    # --- Compact "Add To Cart" row + separate Google field ---
    links = data.get("links") or {}

    row = []
    atc = data.get("atc_url") or links.get("ATC")
    if atc:
        row.append(f"[ATC]({atc})")

    for key in ("KEEPA", "SAS", "EBAY"):
        url = links.get(key)
        if url:
            row.append(f"[{key}]({url})")

    if row:
        # inline=True gives you the single-line look; Discord may wrap if it's too long
        embed.add_field(name="Add To Cart", value=" | ".join(row), inline=True)

    if links.get("GOOGLE"):
        embed.add_field(name="Google it", value=f"[GOOGLE]({links['GOOGLE']})", inline=True)


    view = build_link_view(data.get("links"))
    return embed, view
