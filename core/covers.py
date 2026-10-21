"""
Lógica de carátulas de UmuLauncher: descargas, búsqueda en Steam/SteamGridDB
y generación de placeholders.
"""

import json, os
import urllib.request, urllib.parse
from pathlib import Path
from typing import Optional, Dict, List, Any

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from core.config import COVERS_DIR, PLACEHOLDER_SIZE, C_ACCENT, C_TEXT, log

# ==================== Cover fetch ====================
def _download_bytes(url: str, timeout=12) -> Optional[bytes]:
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (UmuLauncher/1.0)"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except Exception:
        return None


def _save_image(data: bytes, suffix=".jpg") -> Optional[Path]:
    if not data or len(data) < 512:
        return None
    dest = COVERS_DIR / f"auto_{os.urandom(4).hex()}{suffix}"
    try:
        dest.write_bytes(data)
        Image.open(dest).verify()
        return dest
    except Exception:
        try:
            dest.unlink(missing_ok=True)
        except Exception:
            log.exception("_save_image: no se pudo borrar imagen corrupta %s",
                          dest)
        return None


def steam_search(query: str, limit: int = 8) -> List[Dict[str, Any]]:
    if not query.strip():
        return []
    url = ("https://store.steampowered.com/api/storesearch/"
           f"?term={urllib.parse.quote(query)}&cc=US&l=spanish")
    data = _download_bytes(url)
    if not data:
        return []
    try:
        j = json.loads(data)
        return [{
            "id": str(it["id"]),
            "name": it.get("name", ""),
            "tiny_image": it.get("tiny_image", ""),
            "source": "steam",
        } for it in j.get("items", [])[:limit]]
    except Exception:
        return []


_STEAM_COVER_URLS = [
    "https://cdn.cloudflare.steamstatic.com/steam/apps/{id}/library_600x900.jpg",
    "https://cdn.cloudflare.steamstatic.com/steam/apps/{id}/library_600x900_2x.jpg",
    "https://cdn.cloudflare.steamstatic.com/steam/apps/{id}/header.jpg",
    "https://cdn.cloudflare.steamstatic.com/steam/apps/{id}/capsule_616x353.jpg",
]


def fetch_steam_cover(appid: str) -> Optional[Path]:
    if not str(appid).isdigit():
        return None
    for tpl in _STEAM_COVER_URLS:
        cover = _save_image(_download_bytes(tpl.format(id=appid)))
        if cover:
            return cover
    return None


def fetch_sgdb_cover(name: str, api_key: str) -> Optional[Path]:
    if not api_key or not name.strip():
        return None
    base = "https://www.steamgriddb.com/api/v2"
    headers = {"Authorization": f"Bearer {api_key}",
               "User-Agent": "Mozilla/5.0 (UmuLauncher/1.0)"}
    try:
        req = urllib.request.Request(
            f"{base}/search/autocomplete/{urllib.parse.quote(name)}",
            headers=headers)
        with urllib.request.urlopen(req, timeout=10) as r:
            j = json.loads(r.read())
        if not j.get("success") or not j.get("data"):
            return None
        game_id = j["data"][0]["id"]
    except Exception:
        return None
    try:
        req = urllib.request.Request(
            f"{base}/grids/game/{game_id}?dimensions=600x900"
            f"&mimes=image/png,image/jpeg,image/webp",
            headers=headers)
        with urllib.request.urlopen(req, timeout=10) as r:
            j = json.loads(r.read())
        if not j.get("success") or not j.get("data"):
            return None
    except Exception:
        return None
    for entry in j["data"][:3]:
        url = entry.get("url")
        if not url:
            continue
        ext = Path(urllib.parse.urlparse(url).path).suffix or ".jpg"
        cover = _save_image(_download_bytes(url), suffix=ext)
        if cover:
            return cover
    return None


# ==================== Placeholder ====================
_placeholder_cache: Dict[str, Image.Image] = {}


def create_placeholder(name: str) -> Image.Image:
    key = name[:40]
    if key in _placeholder_cache:
        return _placeholder_cache[key]

    w, h = PLACEHOLDER_SIZE
    img = Image.new("RGB", (w, h), (15, 14, 23))
    draw = ImageDraw.Draw(img)

    for y in range(h):
        t = y / h
        draw.line([(0, y), (w, y)],
                  fill=(int(20 + t * 45), int(18 + t * 25), int(45 + t * 70)))

    glow = Image.new("L", (w, h), 0)
    gd = ImageDraw.Draw(glow)
    gd.ellipse([-40, -140, w + 40, 90], fill=90)
    glow = glow.filter(ImageFilter.GaussianBlur(30))
    accent = Image.new("RGB", (w, h), (255, 193, 7))
    img = Image.composite(accent, img, glow.point(lambda p: int(p * 0.28)))
    draw = ImageDraw.Draw(img)

    draw.rectangle([8, 8, w - 9, h - 9], outline=(120, 120, 180), width=1)
    cx, cy = w // 2, 110
    draw.rounded_rectangle([cx - 44, cy - 22, cx + 44, cy + 22],
                           radius=20, outline=C_ACCENT, width=3)
    draw.rectangle([cx - 30, cy - 3, cx - 14, cy + 3], fill=C_ACCENT)
    draw.rectangle([cx - 25, cy - 8, cx - 19, cy + 8], fill=C_ACCENT)
    draw.ellipse([cx + 14, cy - 8, cx + 22, cy], fill=C_ACCENT)
    draw.ellipse([cx + 22, cy + 2, cx + 30, cy + 10], fill=C_ACCENT)

    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf", 15)
    except Exception:
        try:
            font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 15)
        except Exception:
            font = ImageFont.load_default()

    words = name.split() or ["Sin nombre"]
    lines, current = [], ""
    for word in words:
        test = (current + " " + word).strip()
        if draw.textlength(test, font=font) < w - 32:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)

    shown = lines[:3]
    line_h = 20
    start_y = h - 24 - len(shown) * line_h
    for i, line in enumerate(shown):
        bbox = draw.textbbox((0, 0), line, font=font)
        x = (w - (bbox[2] - bbox[0])) // 2
        draw.text((x + 1, start_y + i * line_h + 1), line,
                  fill=(0, 0, 0), font=font)
        draw.text((x, start_y + i * line_h), line,
                  fill=C_TEXT, font=font)

    _placeholder_cache[key] = img
    return img


_cover_cache: Dict[str, ctk.CTkImage] = {}


def invalidate_cover_cache(name: Optional[str] = None,
                           cover: Optional[str] = None) -> None:
    if name is None and cover is None:
        _cover_cache.clear()
        _placeholder_cache.clear()
        return
    for key in list(_cover_cache.keys()):
        if (name and name in key) or (cover and cover in key):
            _cover_cache.pop(key, None)
    if name:
        _placeholder_cache.pop(name[:40], None)


def get_cover_image(game: Dict[str, Any], size=PLACEHOLDER_SIZE) -> ctk.CTkImage:
    key = f"{game.get('cover', '')}|{game.get('name', '')}|{size}"
    if key in _cover_cache:
        return _cover_cache[key]

    cover_path = game.get("cover")
    img = None
    if cover_path and Path(cover_path).exists():
        try:
            img = Image.open(cover_path).convert("RGB")
            iw, ih = img.size
            tw, th = size
            scale = max(tw / iw, th / ih)
            new = (int(iw * scale), int(ih * scale))
            img = img.resize(new, Image.Resampling.LANCZOS)
            left = (new[0] - tw) // 2
            top = (new[1] - th) // 2
            img = img.crop((left, top, left + tw, top + th))
        except Exception:
            img = None

    if img is None:
        img = create_placeholder(game.get("name", "Game"))

    ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=size)
    _cover_cache[key] = ctk_img
    return ctk_img
