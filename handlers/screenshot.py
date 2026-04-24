"""
Website Screenshot Handler
Uses Playwright with headless Chromium — no API key needed.
"""

import os
import asyncio
import uuid

from config import TEMP_DIR, SCREENSHOT_TIMEOUT
from keyboards import cancel_menu, main_menu

os.makedirs(TEMP_DIR, exist_ok=True)

STATE_WAIT_URL = "ss_wait_url"

ASK_URL = (
    "🖥️ **اسکرین‌شات از وب‌سایت**\n\n"
    "آدرس URL وب‌سایت مورد نظر را ارسال کنید:\n\n"
    "📝 مثال:\n"
    "`https://example.com`\n"
    "`https://github.com`\n\n"
    "📸 یک اسکرین‌شات کامل از صفحه برای شما می‌گیرم!"
)


# ─── Screenshot function ──────────────────────────────────────────────────────

async def _take_screenshot(url: str) -> str:
    """
    Uses Playwright to capture a full-page screenshot.
    Returns path to the PNG file.
    """
    from playwright.async_api import async_playwright

    # Ensure URL has scheme
    if not url.startswith("http"):
        url = "https://" + url

    out_path = os.path.join(TEMP_DIR, f"ss_{uuid.uuid4().hex[:10]}.png")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )
        page = await browser.new_page(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        try:
            await page.goto(url, wait_until="networkidle", timeout=SCREENSHOT_TIMEOUT * 1000)
            await asyncio.sleep(2)  # let dynamic content render
            await page.screenshot(path=out_path, full_page=True)
        finally:
            await browser.close()

    return out_path


# ─── Handlers ─────────────────────────────────────────────────────────────────

async def on_screenshot_start(update, bot):
    from database import set_state
    await set_state(update.chat_id, STATE_WAIT_URL)
    await update.reply(ASK_URL, chat_keypad=cancel_menu())


async def on_screenshot_url(update, bot):
    from database import reset_state, log_action

    chat_id = update.chat_id
    url     = (update.new_message.text or "").strip()

    if not url or len(url) < 4:
        await update.reply("❌ آدرس وارد شده معتبر نیست.", chat_keypad=cancel_menu())
        return

    status = await bot.send_message(
        chat_id,
        f"⏳ در حال گرفتن اسکرین‌شات از:\n🌐 `{url}`\nلطفاً صبر کنید...",
    )

    filepath = None
    try:
        filepath = await _take_screenshot(url)
        size_mb  = os.path.getsize(filepath) / (1024 * 1024)

        await bot.edit_message_text(chat_id, status.message_id, "📤 در حال ارسال تصویر...")
        await bot.send_file(
            chat_id   = chat_id,
            file      = filepath,
            type      = "Image",
            file_name = "screenshot.png",
            text      = f"🖥️ **اسکرین‌شات**\n🌐 {url}\n📦 حجم: {size_mb:.1f} MB",
        )
        await log_action(chat_id, "screenshot")

    except Exception as exc:
        err = str(exc)[:300]
        await bot.edit_message_text(
            chat_id, status.message_id,
            f"❌ خطا در گرفتن اسکرین‌شات:\n`{err}`\n\n"
            "💡 مطمئن شوید سایت قابل دسترسی است.",
        )
    finally:
        if filepath and os.path.exists(filepath):
            os.remove(filepath)
        await reset_state(chat_id)
        await bot.send_message(chat_id, "🏠 به منوی اصلی بازگشتید:", chat_keypad=main_menu())
