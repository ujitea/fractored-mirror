import re
import discord

def parse_extracted_text(raw_text):
    """
    Parses a text block for a Discord embed.
    Returns a dict with keys like: title, url, price, atc_url, seller, thumbnail_url, image_url, etc.
    """

    parsed = {}
    lines = [line.strip() for line in raw_text.strip().split('\n') if line.strip()]

    # 1. Detect if the first line is bold and treat as title
    if lines and re.match(r"\*\*(.+)\*\*", lines[0]) and ":" not in lines[0]:
        parsed["title"] = re.sub(r"\*\*", "", lines[0])
        lines = lines[1:]
    else:
        parsed["title"] = "No Title"

    # 2. Extract **Field**: value pairs
    field_re = re.compile(r"\*\*(.+?)\*\*:\s*(.+)")
    for line in lines:
        m = field_re.match(line)
        if m:
            key, value = m.group(1).strip().lower(), m.group(2).strip()
            if key in ["price", "status", "sku", "offer id", "seller"]:
                parsed[key.replace(" ", "_")] = value
            elif key in ["atc", "other"]:
                # Check if value is a markdown link
                link_match = re.search(r"\[(.*?)\]\((.*?)\)", value)
                if link_match:
                    parsed["atc_url"] = link_match.group(2)
                else:
                    # Fallback to URL if present in the value
                    url_match = re.search(r"(https?://\S+)", value)
                    if url_match:
                        parsed["atc_url"] = url_match.group(1)
            else:
                # General catch-all for other fields
                parsed[key.replace(" ", "_")] = value

    # 3. Find any URLs not in fields
    url_pattern = re.compile(r"(https?://\S+)")
    all_urls = url_pattern.findall(raw_text)
    # Use the last URL as main url if not set by ATC/Other
    if all_urls:
        if "atc_url" not in parsed and len(all_urls) > 1:
            parsed["atc_url"] = all_urls[-2]
        if "url" not in parsed:
            parsed["url"] = all_urls[-1]
        # If there's an image url (png/jpg), set it
        for u in all_urls:
            if u.lower().endswith((".jpg", ".jpeg", ".png", ".gif")):
                parsed["thumbnail_url"] = u

    return parsed

def embed_from_parsed(data):
    embed = discord.Embed(
        title=data.get("title", "No Title"),
        url=data.get("url"),
        color=discord.Color.blue()
    )
    # Thumbnail image (top right)
    if "thumbnail_url" in data:
        embed.set_thumbnail(url=data["thumbnail_url"])
    # Price fields
    if "new_price" in data:
        embed.add_field(name="New Price", value=data["new_price"], inline=True)
    if "old_price" in data:
        embed.add_field(name="Old Price", value=data["old_price"], inline=True)
    if "price" in data:
        embed.add_field(name="Price", value=data["price"], inline=True)
    if "discount" in data:
        embed.add_field(name="Discount", value=data["discount"], inline=True)
    if "seller" in data:
        embed.add_field(name="Seller", value=data["seller"], inline=True)
    if "promotion" in data:
        embed.add_field(name="Promotion", value=data["promotion"], inline=True)
    if "add_to_cart" in data:
        embed.add_field(name="Add To Cart", value=data["add_to_cart"], inline=False)
    if "atc_url" in data:
        embed.add_field(name="ATC", value=f"[ATC]({data['atc_url']})", inline=False)
    if "google_it" in data:
        embed.add_field(name="Google it", value=data["google_it"], inline=False)
    if "business_required" in data:
        embed.add_field(name="Business Required", value=data["business_required"], inline=True)
    return embed