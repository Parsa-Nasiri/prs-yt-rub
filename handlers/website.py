"""
Website Download Handler
Two modes:
  1. Offline download  — saves full HTML+CSS+JS+images as a ZIP
  2. Direct file download — downloads a file URL and sends it to user
"""

import os
import re
import uuid
import asyncio
import shutil
import zipfile
import urllib.parse
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from config import TEMP_DIR, MAX_FILE_SIZE_MB, WEBSITE_DOWNLOAD_TIMEOUT
from keyboards import cancel_menu, main_menu, website_download_menu, BTN

os.makedirs(TEMP_DIR, exist_ok=True)

STATE_WAIT_MODE       = "web_wait_mode"
STATE_WAIT_OFFLINE    = "web_wait_offline_url"
STATE_WAIT_FILE       = "web_wait_file_url"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

ASK_OFFLINE_URL = (
    "🌐 **دانلود آفلاین سایت**\n\n"
    "آدرس URL وب‌سایت را ارسال کنید:\n"
    "📝 `https://example.com`\n\n"
    "📦 تمام HTML، CSS، JS و تصاویر دانلود و در یک فایل ZIP برای شما ارسال می‌شود."
)

ASK_FILE_URL = (
    "📦 **دانلود فایل مستقیم**\n\n"
    "لینک مستقیم فایل را ارسال کنید:\n"
    "📝 مثال: `https://example.com/file.pdf`\n\n"
    f"⚠️ حداکثر حجم: **{MAX_FILE_SIZE_MB} مگابایت**"
)


# ─── Offline downloader ───────────────────────────────────────────────────────

def _absolute_url(base: str, href: str) -> str | None:
    if not href or href.startswith("data:") or href.startswith("#"):
        return None
    return urllib.parse.urljoin(base, href)


def _safe_filename(url: str) -> str:
    name = re.sub(r"[^\w\-.]", "_", urllib.parse.urlparse(url).path.split("/")[-1] or "index")
    return name[:80] or "file"


def _download_offline(page_url: str, dest_dir: str) -> str:
    """Download page + assets, return path to ZIP."""
    if not page_url.startswith("http"):
        page_url = "https://" + page_url

    os.makedirs(dest_dir, exist_ok=True)

    # 1. Fetch main HTML
    resp = requests.get(page_url, headers=HEADERS, timeout=WEBSITE_DOWNLOAD_TIMEOUT)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    asset_map: dict[str, str] = {}  # original url → local path

    def _fetch_asset(url: str, subdir: str) -> str | None:
        if url in asset_map:
            return asset_map[url]
        try:
            r = requests.get(url, headers=HEADERS, timeout=15, stream=True)
            r.raise_for_status()
            fname   = _safe_filename(url)
            local   = os.path.join(dest_dir, subdir, fname)
            os.makedirs(os.path.dirname(local), exist_ok=True)
            with open(local, "wb") as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)
            rel = f"{subdir}/{fname}"
            asset_map[url] = rel
            return rel
        except Exception:
            return None

    # 2. CSS
    for tag in soup.find_all("link", rel="stylesheet"):
        href = _absolute_url(page_url, tag.get("href"))
        if href:
            local = _fetch_asset(href, "css")
            if local:
                tag["href"] = local

    # 3. JS
    for tag in soup.find_all("script", src=True):
        src = _absolute_url(page_url, tag.get("src"))
        if src:
            local = _fetch_asset(src, "js")
            if local:
                tag["src"] = local

    # 4. Images
    for tag in soup.find_all("img", src=True):
        src = _absolute_url(page_url, tag.get("src"))
        if src:
            local = _fetch_asset(src, "images")
            if local:
                tag["src"] = local

    # 5. Write modified HTML
    html_path = os.path.join(dest_dir, "index.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(str(soup))

    # 6. ZIP everything
    zip_path = dest_dir + ".zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(dest_dir):
            for fname in files:
                fpath = os.path.join(root, fname)
                zf.write(fpath, os.path.relpath(fpath, dest_dir))

    shutil.rmtree(dest_dir, ignore_errors=True)
    return zip_path


def _download_file_direct(file_url: str, dest_dir: str) -> str:
    """Download a raw file URL, return its local path."""
    os.makedirs(dest_dir, exist_ok=True)
    r = requests.get(file_url, headers=HEADERS, stream=True, timeout=WEBSITE_DOWNLOAD_TIMEOUT)
    r.raise_for_status()

    # Determine filename
    cd = r.headers.get("Content-Disposition", "")
    fname_match = re.search(r'filename="?([^";]+)"?', cd)
    if fname_match:
        fname = fname_match.group(1).strip()
    else:
        fname = _safe_filename(file_url) or "downloaded_file"

    filepath = os.path.join(dest_dir, fname)
    with open(filepath, "wb") as f:
        for chunk in r.iter_content(8192):
            f.write(chunk)
    return filepath


# ─── Handlers ─────────────────────────────────────────────────────────────────

async def on_website_start(update, bot):
    from database import set_state
    await set_state(update.chat_id, STATE_WAIT_MODE)
    await update.reply(
        "💾 **دانلود از وب‌سایت**\n\nنوع دانلود را انتخاب کنید:",
        chat_keypad=website_download_menu(),
    )


async def on_website_mode_select(update, bot):
    from database import set_state
    text = (update.new_message.text or "").strip()
    if text == BTN.WEB_OFFLINE:
        await set_state(update.chat_id, STATE_WAIT_OFFLINE)
        await update.reply(ASK_OFFLINE_URL, chat_keypad=cancel_menu())
    elif text == BTN.WEB_FILE:
        await set_state(update.chat_id, STATE_WAIT_FILE)
        await update.reply(ASK_FILE_URL, chat_keypad=cancel_menu())


async def on_offline_url(update, bot):
    from database import reset_state, log_action

    chat_id = update.chat_id
    url     = (update.new_message.text or "").strip()

    status = await bot.send_message(
        chat_id,
        f"⏳ در حال دانلود سایت:\n🌐 `{url}`\nاین عملیات ممکن است چند دقیقه طول بکشد...",
    )

    dest   = os.path.join(TEMP_DIR, f"web_{chat_id}_{uuid.uuid4().hex[:6]}")
    zip_path = None
    try:
        loop     = asyncio.get_event_loop()
        zip_path = await loop.run_in_executor(None, _download_offline, url, dest)
        size_mb  = os.path.getsize(zip_path) / (1024 * 1024)

        if size_mb > MAX_FILE_SIZE_MB:
            raise ValueError(f"فایل ZIP خیلی بزرگ است ({size_mb:.1f} MB)")

        await bot.edit_message_text(chat_id, status.message_id, "📤 در حال ارسال فایل ZIP...")
        await bot.send_file(
            chat_id   = chat_id,
            file      = zip_path,
            type      = "File",
            file_name = "website_offline.zip",
            text      = (
                f"🌐 **وب‌سایت آفلاین**\n"
                f"🔗 {url}\n"
                f"📦 حجم: {size_mb:.1f} MB\n\n"
                "💡 فایل ZIP را باز کنید و `index.html` را در مرورگر باز کنید."
            ),
        )
        await log_action(chat_id, "website_offline_download")

    except Exception as exc:
        await bot.edit_message_text(chat_id, status.message_id,
                                    f"❌ خطا:\n`{str(exc)[:300]}`")
    finally:
        if zip_path and os.path.exists(zip_path):
            os.remove(zip_path)
        shutil.rmtree(dest, ignore_errors=True)
        await reset_state(chat_id)
        await bot.send_message(chat_id, "🏠 به منوی اصلی بازگشتید:", chat_keypad=main_menu())


async def on_file_url(update, bot):
    from database import reset_state, log_action

    chat_id = update.chat_id
    url     = (update.new_message.text or "").strip()

    status   = await bot.send_message(chat_id, f"⏳ در حال دانلود فایل:\n🔗 `{url}`")
    dest     = os.path.join(TEMP_DIR, f"file_{chat_id}_{uuid.uuid4().hex[:6]}")
    filepath = None

    try:
        loop     = asyncio.get_event_loop()
        filepath = await loop.run_in_executor(None, _download_file_direct, url, dest)
        size_mb  = os.path.getsize(filepath) / (1024 * 1024)

        if size_mb > MAX_FILE_SIZE_MB:
            raise ValueError(f"فایل بزرگتر از حد مجاز است ({size_mb:.1f} MB)")

        fname = os.path.basename(filepath)
        await bot.edit_message_text(chat_id, status.message_id, "📤 در حال ارسال فایل...")
        await bot.send_file(
            chat_id   = chat_id,
            file      = filepath,
            type      = "File",
            file_name = fname,
            text      = f"📦 **فایل دانلود شده**\n🔗 {url}\n📏 حجم: {size_mb:.1f} MB",
        )
        await log_action(chat_id, "file_download")

    except Exception as exc:
        await bot.edit_message_text(chat_id, status.message_id,
                                    f"❌ خطا:\n`{str(exc)[:300]}`")
    finally:
        if filepath and os.path.exists(filepath):
            os.remove(filepath)
        shutil.rmtree(dest, ignore_errors=True)
        await reset_state(chat_id)
        await bot.send_message(chat_id, "🏠 به منوی اصلی بازگشتید:", chat_keypad=main_menu())
