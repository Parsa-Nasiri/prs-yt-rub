"""
Keyboard factory — builds Rubika chat keypads using rubpy models.
"""

import uuid
from rubpy.bot.models import Keypad, KeypadRow, Button
from rubpy.bot.enums import ButtonTypeEnum, ChatKeypadTypeEnum


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _btn(text: str, btn_id: str = None) -> Button:
    return Button(
        id=btn_id or str(uuid.uuid4())[:8],
        type=ButtonTypeEnum.SIMPLE,
        button_text=text,
    )


def _row(*texts_or_tuples) -> KeypadRow:
    """
    _row("A", "B")          → two buttons in one row
    _row(("A", "id1"))      → button with custom id
    """
    buttons = []
    for item in texts_or_tuples:
        if isinstance(item, tuple):
            buttons.append(_btn(item[0], item[1]))
        else:
            buttons.append(_btn(item))
    return KeypadRow(buttons=buttons)


# ─── Keyboards ────────────────────────────────────────────────────────────────

def main_menu() -> Keypad:
    return Keypad(rows=[
        _row("📥 دانلود یوتیوب",   "📸 دانلود اینستاگرام"),
        _row("📌 دانلود پینترست",  "💾 دانلود فایل سایت"),
        _row("🖥️ اسکرین‌شات سایت", "📢 مانیتور تلگرام"),
        _row("🔗 کانفیگ‌های جدید"),
        _row("ℹ️ راهنما",           "📊 آمار"),
    ])


def cancel_menu() -> Keypad:
    return Keypad(rows=[_row("❌ لغو و بازگشت به منو")])


def back_menu() -> Keypad:
    return Keypad(rows=[_row("🔙 بازگشت به منوی اصلی")])


def youtube_quality_menu() -> Keypad:
    return Keypad(rows=[
        _row("🎬 بهترین کیفیت (MP4)", "🎵 فقط صدا (MP3)"),
        _row("📱 کیفیت پایین (360p)"),
        _row("❌ لغو و بازگشت به منو"),
    ])


def instagram_type_menu() -> Keypad:
    return Keypad(rows=[
        _row("🖼️ پست / عکس", "🎬 ریلز / ویدیو"),
        _row("📖 استوری"),
        _row("❌ لغو و بازگشت به منو"),
    ])


def telegram_monitor_menu() -> Keypad:
    return Keypad(rows=[
        _row("➕ اضافه کردن کانال"),
        _row("📋 کانال‌های من",  "🔔 مدیریت هشدارها"),
        _row("❌ لغو و بازگشت به منو"),
    ])


def website_download_menu() -> Keypad:
    return Keypad(rows=[
        _row("🌐 دانلود HTML+CSS+JS (آفلاین)"),
        _row("📦 دانلود فایل مستقیم (URL فایل)"),
        _row("❌ لغو و بازگشت به منو"),
    ])


def channel_actions_menu(channel: str, alert_on: bool) -> Keypad:
    alert_label = "🔕 خاموش کردن هشدار" if alert_on else "🔔 روشن کردن هشدار"
    return Keypad(rows=[
        _row(f"📨 دریافت پیام‌های اخیر"),
        _row(alert_label),
        _row("🗑️ حذف این کانال"),
        _row("🔙 بازگشت به منوی اصلی"),
    ])


def config_channels_menu(channels: list) -> Keypad:
    rows = [_row(f"📡 @{ch}") for ch in channels]
    rows.append(_row("🔙 بازگشت به منوی اصلی"))
    return Keypad(rows=rows)


# ─── Label Constants (used for routing in main handler) ───────────────────────
class BTN:
    # Main menu
    YOUTUBE          = "📥 دانلود یوتیوب"
    INSTAGRAM        = "📸 دانلود اینستاگرام"
    PINTEREST        = "📌 دانلود پینترست"
    WEBSITE_DL       = "💾 دانلود فایل سایت"
    SCREENSHOT       = "🖥️ اسکرین‌شات سایت"
    TELEGRAM_MON     = "📢 مانیتور تلگرام"
    NEW_CONFIGS      = "🔗 کانفیگ‌های جدید"
    HELP             = "ℹ️ راهنما"
    STATS            = "📊 آمار"
    CANCEL           = "❌ لغو و بازگشت به منو"
    BACK             = "🔙 بازگشت به منوی اصلی"
    # YouTube
    YT_BEST          = "🎬 بهترین کیفیت (MP4)"
    YT_AUDIO         = "🎵 فقط صدا (MP3)"
    YT_LOW           = "📱 کیفیت پایین (360p)"
    # Instagram
    IG_POST          = "🖼️ پست / عکس"
    IG_REEL          = "🎬 ریلز / ویدیو"
    IG_STORY         = "📖 استوری"
    # Telegram Monitor
    TG_ADD           = "➕ اضافه کردن کانال"
    TG_LIST          = "📋 کانال‌های من"
    TG_ALERTS        = "🔔 مدیریت هشدارها"
    TG_GET_MSGS      = "📨 دریافت پیام‌های اخیر"
    TG_TOGGLE_ON     = "🔔 روشن کردن هشدار"
    TG_TOGGLE_OFF    = "🔕 خاموش کردن هشدار"
    TG_REMOVE        = "🗑️ حذف این کانال"
    # Website
    WEB_OFFLINE      = "🌐 دانلود HTML+CSS+JS (آفلاین)"
    WEB_FILE         = "📦 دانلود فایل مستقیم (URL فایل)"
