"""
Instagram Download Handler
Uses instaloader — works for public profiles, no API key needed.
"""

import os
import re
import asyncio
import glob
import shutil

import instaloader

from config import TEMP_DIR, MAX_FILE_SIZE_MB
from keyboards import cancel_menu, main_menu, BTN

os.makedirs(TEMP_DIR, exist_ok=True)

STATE_WAIT_URL  = "ig_wait_url"
STATE_WAIT_TYPE = "ig_wait_type"

ASK_URL = (
    "📸 **دانلود از اینستاگرام**\n\n"
    "لینک پست، ریلز یا استوری را ارسال کنید:\n\n"
    "📝 مثال:\n"
    "`https://www.instagram.com/p/ABC123/`\n"
    "`https://www.instagram.com/reel/ABC123/`\n\n"
    "⚠️ فقط پروفایل‌های **عمومی** پشتیبانی می‌شود."
)

# ─── Shortcode extractor ──────────────────────────────────────────────────────

def _extract_shortcode(url: str) -> str | None:
    patterns = [
        r"instagram\.com/p/([A-Za-z0-9_-]+)",
        r"instagram\.com/reel/([A-Za-z0-9_-]+)",
        r"instagram\.com/tv/([A-Za-z0-9_-]+)",
        r"instagram\.com/stories/[^/]+/(\d+)",
    ]
    for pat in patterns:
        m = re.search(pat, url)
        if m:
            return m.group(1)
    return None


def _download_post(shortcode: str, target_dir: str) -> list[str]:
    """Download a single post and return list of downloaded file paths."""
    L = instaloader.Instaloader(
        download_pictures=True,
        download_videos=True,
        download_video_thumbnails=False,
        save_metadata=False,
        compress_json=False,
        post_metadata_txt_pattern="",
        quiet=True,
    )
    post   = instaloader.Post.from_shortcode(L.context, shortcode)
    L.download_post(post, target=target_dir)

    files = []
    for ext in ("mp4", "jpg", "jpeg", "png", "webp"):
        files.extend(glob.glob(os.path.join(target_dir, f"*.{ext}")))
    return sorted(files)


# ─── Handlers ─────────────────────────────────────────────────────────────────

async def on_instagram_start(update, bot):
    from database import set_state
    await set_state(update.chat_id, STATE_WAIT_URL)
    await update.reply(ASK_URL, chat_keypad=cancel_menu())


async def on_instagram_url(update, bot):
    from database import set_state, reset_state, log_action

    chat_id = update.chat_id
    url     = (update.new_message.text or "").strip()

    shortcode = _extract_shortcode(url)
    if not shortcode:
        await update.reply(
            "❌ لینک معتبر نیست.\n\nلینک پست، ریلز یا استوری اینستاگرام را ارسال کنید.",
            chat_keypad=cancel_menu(),
        )
        return

    status = await bot.send_message(chat_id, "⏳ در حال دانلود از اینستاگرام...\nلطفاً صبر کنید.")

    target_dir = os.path.join(TEMP_DIR, f"ig_{chat_id}_{shortcode}")
    os.makedirs(target_dir, exist_ok=True)

    try:
        loop  = asyncio.get_event_loop()
        files = await loop.run_in_executor(None, _download_post, shortcode, target_dir)

        if not files:
            raise FileNotFoundError("هیچ فایلی دانلود نشد. احتمالاً پروفایل خصوصی است.")

        await bot.edit_message_text(chat_id, status.message_id,
                                    f"📤 در حال ارسال {len(files)} فایل...")

        for filepath in files:
            size_mb = os.path.getsize(filepath) / (1024 * 1024)
            if size_mb > MAX_FILE_SIZE_MB:
                continue

            ext   = os.path.splitext(filepath)[1].lower()
            ftype = "Video" if ext == ".mp4" else "Image"
            fname = os.path.basename(filepath)

            await bot.send_file(
                chat_id   = chat_id,
                file      = filepath,
                type      = ftype,
                file_name = fname,
                text      = f"📸 دانلود اینستاگرام\n🔗 {url}",
            )
            await asyncio.sleep(0.5)  # avoid flood

        await log_action(chat_id, "instagram_download")

    except instaloader.exceptions.LoginRequiredException:
        await bot.edit_message_text(chat_id, status.message_id,
                                    "🔒 این پست نیاز به ورود دارد. فقط پروفایل‌های عمومی پشتیبانی می‌شود.")
    except instaloader.exceptions.ProfileNotExistsException:
        await bot.edit_message_text(chat_id, status.message_id,
                                    "❌ پروفایل پیدا نشد. لینک را بررسی کنید.")
    except Exception as exc:
        await bot.edit_message_text(chat_id, status.message_id,
                                    f"❌ خطا:\n`{str(exc)[:300]}`")
    finally:
        shutil.rmtree(target_dir, ignore_errors=True)
        await reset_state(chat_id)
        await bot.send_message(chat_id, "🏠 به منوی اصلی بازگشتید:", chat_keypad=main_menu())
