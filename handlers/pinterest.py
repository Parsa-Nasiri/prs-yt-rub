"""
Pinterest Download Handler
Scrapes public Pinterest pins — no API key needed.
"""

import os
import re
import asyncio
import uuid

import requests
from bs4 import BeautifulSoup

from config import TEMP_DIR, MAX_FILE_SIZE_MB
from keyboards import cancel_menu, main_menu

os.makedirs(TEMP_DIR, exist_ok=True)

STATE_WAIT_URL = "pin_wait_url"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

ASK_URL = (
    "📌 **دانلود از پینترست**\n\n"
    "لینک پین مورد نظر را ارسال کنید:\n\n"
    "📝 مثال:\n"
    "`https://www.pinterest.com/pin/123456789/`\n"
    "`https://pin.it/ABCDEF`\n\n"
    "⚠️ فقط پین‌های **عمومی** پشتیبانی می‌شود."
)


# ─── Scraper ──────────────────────────────────────────────────────────────────

def _resolve_short_url(url: str) -> str:
    """Follow pin.it short redirects."""
    if "pin.it" in url:
        r = requests.head(url, headers=HEADERS, allow_redirects=True, timeout=15)
        return r.url
    return url


def _extract_media(pin_url: str) -> dict:
    """Extract highest-res image/video URL from a Pinterest pin page."""
    url  = _resolve_short_url(pin_url)
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    result = {"type": None, "url": None, "title": "Pinterest"}

    # Try og:video first (video pins)
    og_video = soup.find("meta", property="og:video")
    if og_video and og_video.get("content"):
        result["type"] = "video"
        result["url"]  = og_video["content"]

    # Fallback: og:image
    if not result["url"]:
        og_image = soup.find("meta", property="og:image")
        if og_image and og_image.get("content"):
            img_url = og_image["content"]
            # Pinterest serves thumbnails; try to get originals
            img_url = re.sub(r"/\d+x/", "/originals/", img_url)
            result["type"] = "image"
            result["url"]  = img_url

    # og:title
    og_title = soup.find("meta", property="og:title")
    if og_title:
        result["title"] = og_title.get("content", "Pinterest")[:100]

    return result


def _download_media(media_info: dict, dest: str) -> str:
    """Download media to dest folder; returns file path."""
    media_url = media_info["url"]
    ext       = "mp4" if media_info["type"] == "video" else "jpg"
    filename  = f"pinterest_{uuid.uuid4().hex[:8]}.{ext}"
    filepath  = os.path.join(dest, filename)

    with requests.get(media_url, headers=HEADERS, stream=True, timeout=30) as r:
        r.raise_for_status()
        with open(filepath, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
    return filepath


# ─── Handlers ─────────────────────────────────────────────────────────────────

async def on_pinterest_start(update, bot):
    from database import set_state
    await set_state(update.chat_id, STATE_WAIT_URL)
    await update.reply(ASK_URL, chat_keypad=cancel_menu())


async def on_pinterest_url(update, bot):
    from database import reset_state, log_action

    chat_id = update.chat_id
    url     = (update.new_message.text or "").strip()

    if "pinterest" not in url and "pin.it" not in url:
        await update.reply(
            "❌ لینک وارد شده معتبر نیست. لطفاً یک لینک Pinterest ارسال کنید.",
            chat_keypad=cancel_menu(),
        )
        return

    status = await bot.send_message(chat_id, "⏳ در حال دانلود از Pinterest...")
    dest   = os.path.join(TEMP_DIR, f"pin_{chat_id}")
    os.makedirs(dest, exist_ok=True)

    try:
        loop       = asyncio.get_event_loop()
        media_info = await loop.run_in_executor(None, _extract_media, url)

        if not media_info["url"]:
            raise ValueError("نتوانستم رسانه‌ای از این پین استخراج کنم.")

        filepath   = await loop.run_in_executor(None, _download_media, media_info, dest)
        size_mb    = os.path.getsize(filepath) / (1024 * 1024)

        if size_mb > MAX_FILE_SIZE_MB:
            raise ValueError(f"فایل بزرگتر از حد مجاز است ({size_mb:.1f} MB)")

        ftype   = "Video" if media_info["type"] == "video" else "Image"
        caption = f"📌 **{media_info['title']}**\n🔗 {url}"

        await bot.edit_message_text(chat_id, status.message_id, "📤 در حال ارسال...")
        await bot.send_file(
            chat_id   = chat_id,
            file      = filepath,
            type      = ftype,
            file_name = os.path.basename(filepath),
            text      = caption,
        )
        os.remove(filepath)
        await log_action(chat_id, "pinterest_download")

    except Exception as exc:
        await bot.edit_message_text(chat_id, status.message_id,
                                    f"❌ خطا:\n`{str(exc)[:300]}`")
    finally:
        import shutil
        shutil.rmtree(dest, ignore_errors=True)
        await reset_state(chat_id)
        await bot.send_message(chat_id, "🏠 به منوی اصلی بازگشتید:", chat_keypad=main_menu())
