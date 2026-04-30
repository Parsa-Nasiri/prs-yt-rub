"""
YouTube Download Handler
Uses yt-dlp — no API key needed.
"""

import os
import asyncio
from pathlib import Path

import yt_dlp

from config import TEMP_DIR, MAX_VIDEO_SIZE_MB
from keyboards import cancel_menu, main_menu, BTN


os.makedirs(TEMP_DIR, exist_ok=True)

# ─── State names ──────────────────────────────────────────────────────────────
STATE_WAIT_URL     = "yt_wait_url"
STATE_WAIT_QUALITY = "yt_wait_quality"


# ─── Texts ────────────────────────────────────────────────────────────────────
ASK_URL = (
    "🎬 **دانلود از یوتیوب**\n\n"
    "لینک ویدیو را ارسال کنید:\n\n"
    "📝 مثال:\n"
    "`https://youtu.be/dQw4w9WgXcQ`\n\n"
    f"⚠️ حجم مجاز: تا **{MAX_VIDEO_SIZE_MB} مگابایت**"
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _ydl_opts(output_template: str, quality: str) -> dict:
    fmt_map = {
        BTN.YT_BEST:  f"bestvideo[ext=mp4][filesize<{MAX_VIDEO_SIZE_MB}M]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        BTN.YT_AUDIO: "bestaudio/best",
        BTN.YT_LOW:   "worst[ext=mp4]/worst",
    }
    opts = {
        "format":              fmt_map.get(quality, "best"),
        "outtmpl":             output_template,
        "noplaylist":          True,
        "quiet":               True,
        "no_warnings":         True,
        "merge_output_format": "mp4",
    }
    if quality == BTN.YT_AUDIO:
        opts["postprocessors"] = [{
            "key":            "FFmpegExtractAudio",
            "preferredcodec": "mp3",
        }]
    return opts


def _find_file(base: str) -> str | None:
    for ext in ("mp4", "mp3", "mkv", "webm", "m4a", "ogg"):
        p = f"{base}.{ext}"
        if os.path.exists(p):
            return p
    return None


# ─── Handler functions (called from main router) ──────────────────────────────

async def on_youtube_start(update, bot):
    """User pressed the YouTube button → ask for URL."""
    from database import set_state
    from keyboards import youtube_quality_menu
    await set_state(update.chat_id, STATE_WAIT_URL)
    await update.reply(ASK_URL, chat_keypad=cancel_menu())


async def on_youtube_url(update, bot):
    """User sent a URL → ask quality."""
    from database import set_state, get_state
    from keyboards import youtube_quality_menu

    url = (update.new_message.text or "").strip()
    if not url.startswith("http"):
        await update.reply("❌ لینک وارد شده معتبر نیست. لطفاً یک لینک یوتیوب ارسال کنید.",
                           chat_keypad=cancel_menu())
        return

    await set_state(update.chat_id, STATE_WAIT_QUALITY, {"url": url})
    await update.reply(
        "✅ لینک دریافت شد!\n\nکیفیت مورد نظر را انتخاب کنید:",
        chat_keypad=youtube_quality_menu(),
    )


async def on_youtube_quality(update, bot):
    """User chose quality → download & send."""
    from database import set_state, get_state, reset_state, log_action

    chat_id  = update.chat_id
    quality  = (update.new_message.text or "").strip()
    state    = await get_state(chat_id)
    url      = state["data"].get("url", "")

    if not url:
        await reset_state(chat_id)
        await update.reply("⚠️ جلسه منقضی شد. لطفاً دوباره شروع کنید.", chat_keypad=main_menu())
        return

    status = await bot.send_message(chat_id, "⏳ در حال دریافت اطلاعات ویدیو از یوتیوب...")

    base_path = os.path.join(TEMP_DIR, f"yt_{chat_id}")
    opts      = _ydl_opts(base_path + ".%(ext)s", quality)

    try:
        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(None, _run_ydl, opts, url)

        title    = info.get("title", "video")[:80]
        duration = info.get("duration", 0) or 0
        duration_str = f"{duration // 60}:{duration % 60:02d}"

        filepath = _find_file(base_path)
        if not filepath:
            raise FileNotFoundError("فایل دانلود شده پیدا نشد.")

        size_mb = os.path.getsize(filepath) / (1024 * 1024)
        if size_mb > MAX_VIDEO_SIZE_MB:
            os.remove(filepath)
            raise ValueError(f"فایل بزرگتر از حد مجاز است ({size_mb:.1f} MB > {MAX_VIDEO_SIZE_MB} MB)")

        await bot.edit_message_text(chat_id, status.message_id,
                                    f"📤 در حال آپلود...\n🎬 {title}")

        ext      = Path(filepath).suffix.lower()
        ftype    = "Music" if ext == ".mp3" else "Video"
        caption  = f"🎬 **{title}**\n⏱ مدت زمان: {duration_str}\n🎞 کیفیت: {quality}"

        await bot.send_file(
            chat_id   = chat_id,
            file      = filepath,
            text      = caption,
            type      = ftype,
            file_name = f"{title}{ext}",
        )
        os.remove(filepath)
        await log_action(chat_id, "youtube_download")

    except Exception as exc:
        err_text = str(exc)[:300]
        await bot.edit_message_text(chat_id, status.message_id,
                                    f"❌ خطا در دانلود:\n`{err_text}`")
    finally:
        await reset_state(chat_id)
        await bot.send_message(chat_id, "🏠 به منوی اصلی بازگشتید:", chat_keypad=main_menu())


def _run_ydl(opts: dict, url: str) -> dict:
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=True)
