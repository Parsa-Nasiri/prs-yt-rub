import os
import re
import asyncio
import yt_dlp
from pathlib import Path
from rubpy.bot import BotClient, filters

# ─── Config from environment variables ───────────────────────────────────────
BOT_TOKEN = os.environ["RUBIKA_BOT_TOKEN"]

# ─── Bot init ─────────────────────────────────────────────────────────────────
app = BotClient(BOT_TOKEN)

# ─── Helpers ──────────────────────────────────────────────────────────────────
YOUTUBE_PATTERN = re.compile(
    r"(https?://)?(www\.)?"
    r"(youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)"
    r"[\w\-]+"
)

DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)


def is_youtube_url(text: str) -> bool:
    return bool(YOUTUBE_PATTERN.search(text))


def extract_youtube_url(text: str) -> str | None:
    match = YOUTUBE_PATTERN.search(text)
    return match.group(0) if match else None


def download_video(url: str) -> str | None:
    """Download YouTube video, return file path or None on failure."""
    ydl_opts = {
        "format": "bestvideo[ext=mp4][filesize<50M]+bestaudio[ext=m4a]/best[ext=mp4][filesize<50M]/best",
        "outtmpl": str(DOWNLOAD_DIR / "%(title)s.%(ext)s"),
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
        # Limit file size to avoid memory issues on GitHub Actions
        "max_filesize": 50 * 1024 * 1024,  # 50MB
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        # Ensure .mp4 extension
        if not filename.endswith(".mp4"):
            filename = str(Path(filename).with_suffix(".mp4"))
        return filename if Path(filename).exists() else None


# ─── Handlers ─────────────────────────────────────────────────────────────────
@app.on_update(filters.private)
async def handle_message(client, message):
    text = getattr(message, "text", "") or ""

    # /start command
    if text.strip() == "/start":
        await message.reply(
            "👋 سلام! من ربات دانلود یوتیوب هستم.\n\n"
            "📎 لینک یوتیوب بفرست، ویدیو رو برات آپلود می‌کنم!\n"
            "⚠️ حداکثر حجم: 50 مگابایت"
        )
        return

    # YouTube URL detection
    if not is_youtube_url(text):
        await message.reply(
            "❌ لینک یوتیوب معتبر نیست!\n"
            "مثال: https://youtu.be/dQw4w9WgXcQ"
        )
        return

    url = extract_youtube_url(text)
    await message.reply("⏳ در حال دانلود... لطفاً صبر کن!")

    loop = asyncio.get_event_loop()
    try:
        # Run blocking download in executor to not block bot
        file_path = await loop.run_in_executor(None, download_video, url)

        if not file_path or not Path(file_path).exists():
            await message.reply(
                "❌ دانلود ناموفق بود!\n"
                "ممکنه ویدیو خصوصی، حذف شده یا بیشتر از 50MB باشه."
            )
            return

        file_size_mb = Path(file_path).stat().st_size / (1024 * 1024)
        await message.reply(f"✅ دانلود شد ({file_size_mb:.1f}MB) — در حال آپلود...")

        # Send video to user
        await client.send_video(
            object_guid=message.object_guid,
            video=file_path,
        )

    except yt_dlp.utils.DownloadError as e:
        await message.reply(f"❌ خطا در دانلود:\n`{str(e)[:200]}`")

    except Exception as e:
        await message.reply(f"❌ خطای غیرمنتظره:\n`{str(e)[:200]}`")

    finally:
        # Cleanup downloaded file
        if "file_path" in locals() and file_path and Path(file_path).exists():
            Path(file_path).unlink(missing_ok=True)


# ─── Run ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🤖 Rubika YouTube Downloader Bot is running...")
    app.run()
