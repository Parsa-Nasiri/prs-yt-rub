import os
import re
import asyncio
import yt_dlp
from pathlib import Path
from rubpy.bot import BotClient, filters

# ─── Config ───────────────────────────────────────────────────────────────────
BOT_TOKEN = os.environ["RUBIKA_BOT_TOKEN"]
app = BotClient(BOT_TOKEN)

DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

# ─── YouTube URL Pattern ──────────────────────────────────────────────────────
YOUTUBE_PATTERN = re.compile(
    r"(https?://)?"
    r"(www\.|m\.)?"
    r"("
    r"youtube\.com/watch\?[^\s]*v=[\w\-]+"
    r"|youtube\.com/shorts/[\w\-]+"
    r"|youtube\.com/live/[\w\-]+"
    r"|youtu\.be/[\w\-]+"
    r"|youtube\.com/embed/[\w\-]+"
    r")",
    re.IGNORECASE
)


def get_text(message) -> str:
    """Extract text from rubpy message — tries all known fields."""
    for field in ["text", "message", "caption", "raw_text"]:
        val = getattr(message, field, None)
        if val and isinstance(val, str) and val.strip():
            return val.strip()

    # rubpy sometimes nests text inside message_update or new_message
    for wrapper in ["message_update", "new_message"]:
        obj = getattr(message, wrapper, None)
        if obj:
            for field in ["text", "message", "caption"]:
                val = getattr(obj, field, None)
                if val and isinstance(val, str) and val.strip():
                    return val.strip()

    return ""


def is_youtube_url(text: str) -> bool:
    return bool(YOUTUBE_PATTERN.search(text))


def extract_youtube_url(text: str) -> str | None:
    match = YOUTUBE_PATTERN.search(text)
    if not match:
        return None
    url = match.group(0)
    if not url.startswith("http"):
        url = "https://" + url
    url = url.replace("m.youtube.com", "www.youtube.com")
    return url


def download_video(url: str) -> str | None:
    ydl_opts = {
        "format": "bestvideo[ext=mp4][filesize<50M]+bestaudio[ext=m4a]/best[ext=mp4][filesize<50M]/best",
        "outtmpl": str(DOWNLOAD_DIR / "%(title)s.%(ext)s"),
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
        "max_filesize": 50 * 1024 * 1024,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        if not filename.endswith(".mp4"):
            filename = str(Path(filename).with_suffix(".mp4"))
        return filename if Path(filename).exists() else None


# ─── Handler ──────────────────────────────────────────────────────────────────
@app.on_update(filters.private)
async def handle_message(client, message):
    text = get_text(message)

    # DEBUG — لاگ کامل برای فهمیدن ساختار message
    print(f"[DEBUG] text='{text}'")
    print(f"[DEBUG] message type: {type(message)}")
    print(f"[DEBUG] message fields: {[a for a in dir(message) if not a.startswith('_')]}")

    if text == "/start":
        await message.reply(
            "👋 سلام! من ربات دانلود یوتیوب هستم.\n\n"
            "📎 لینک یوتیوب بفرست، ویدیو رو برات آپلود می‌کنم!\n"
            "⚠️ حداکثر حجم: 50 مگابایت"
        )
        return

    if not text:
        return

    if not is_youtube_url(text):
        await message.reply(
            f"❌ لینک یوتیوب معتبر نیست!\n"
            f"متن دریافتی: `{text}`\n\n"
            f"مثال صحیح:\n"
            f"https://youtu.be/dQw4w9WgXcQ"
        )
        return

    url = extract_youtube_url(text)
    await message.reply("⏳ در حال دانلود... لطفاً صبر کن!")

    loop = asyncio.get_event_loop()
    file_path = None
    try:
        file_path = await loop.run_in_executor(None, download_video, url)

        if not file_path or not Path(file_path).exists():
            await message.reply(
                "❌ دانلود ناموفق بود!\n"
                "ممکنه ویدیو خصوصی، حذف شده یا بیشتر از 50MB باشه."
            )
            return

        file_size_mb = Path(file_path).stat().st_size / (1024 * 1024)
        await message.reply(f"✅ دانلود شد ({file_size_mb:.1f}MB) — در حال آپلود...")

        await client.send_video(
            object_guid=message.object_guid,
            video=file_path,
        )

    except yt_dlp.utils.DownloadError as e:
        await message.reply(f"❌ خطا در دانلود:\n`{str(e)[:200]}`")

    except Exception as e:
        await message.reply(f"❌ خطای غیرمنتظره:\n`{str(e)[:200]}`")

    finally:
        if file_path and Path(file_path).exists():
            Path(file_path).unlink(missing_ok=True)


# ─── Run ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🤖 Rubika YouTube Downloader Bot is running...")
    app.run()
