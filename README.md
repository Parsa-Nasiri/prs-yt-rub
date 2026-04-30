# 🤖 Rubika Multi-Tool Bot

A fully-featured Rubika (روبیکا) bot with powerful tools — runs 24/7 on GitHub Actions.

---

## ✨ Features

| Feature | Description |
|---|---|
| 📥 YouTube Downloader | Download videos & audio, choose quality |
| 📸 Instagram Downloader | Posts, Reels (public profiles only) |
| 📌 Pinterest Downloader | Public pins — images & videos |
| 🖥️ Website Screenshot | Full-page screenshot of any URL |
| 💾 Website Downloader | Offline HTML+CSS+JS (ZIP) or direct file download |
| 📢 Telegram Monitor | Watch any public Telegram channel, get alerts on new messages |
| 🔗 New Configs | Fetch latest VPN configs from pre-defined channels |
| ⚙️ Auto-Restart | Watchdog restarts the bot before GitHub's 6-hour limit |

---

## 🚀 Quick Setup

### 1. Fork / Clone this repo

```bash
git clone https://github.com/YOUR_USERNAME/rubika-bot.git
cd rubika-bot
```

### 2. Get your Rubika Bot Token

Open Rubika → search for **RubikaBot** → create a new bot → copy the token.

### 3. Set GitHub Secrets

Go to **Settings → Secrets → Actions** and add:

| Secret | Value |
|---|---|
| `BOT_TOKEN` | Your Rubika bot token |
| `GITHUB_TOKEN` | A Personal Access Token with `workflow` scope |
| `ADMIN_IDS` | Your Rubika chat ID(s), comma-separated |
| `CONFIG_CHANNELS` | Telegram channel usernames, comma-separated |

### 4. Enable GitHub Actions

Push to `main` or go to **Actions → Run workflow**.

That's it! The bot will start automatically. ✅

---

## 🏗️ Project Structure

```
rubika-bot/
├── .github/
│   └── workflows/
│       └── bot.yml          # GitHub Actions — runs & restarts the bot
├── handlers/
│   ├── youtube.py           # YouTube download logic
│   ├── instagram.py         # Instagram download logic
│   ├── pinterest.py         # Pinterest scraper
│   ├── screenshot.py        # Playwright-based screenshot
│   ├── website.py           # Website offline download & file DL
│   └── telegram_monitor.py  # Telegram channel scraper & alert loop
├── utils/
│   └── restart.py           # GitHub Actions watchdog / self-restart
├── config.py                # All configuration (env vars)
├── database.py              # SQLite state machine & channel subscriptions
├── keyboards.py             # All Rubika keyboard layouts
├── main.py                  # Bot entry point & message router
├── requirements.txt
└── .env.example
```

---

## ⚙️ How the 24/7 Loop Works

```
GitHub Actions starts bot
        │
        ▼
   Bot runs (~5h 40m)
        │
        ▼
  Watchdog detects time limit
        │
        ├──▶ Triggers new GitHub Actions workflow via API
        │
        └──▶ Current instance gracefully shuts down
                    │
                    ▼
             New instance starts
             (cycle repeats ♻️)
```

The **SQLite database is cached** between runs using `actions/cache`, so user states and channel subscriptions persist across restarts.

---

## 📦 Libraries Used

| Library | Purpose | API Key? |
|---|---|---|
| `rubpy` | Rubika bot client | No (Bot Token) |
| `yt-dlp` | YouTube download | ❌ No |
| `instaloader` | Instagram download | ❌ No |
| `requests` + `beautifulsoup4` | Pinterest & Telegram scraping | ❌ No |
| `playwright` | Website screenshots | ❌ No |
| `aiosqlite` | Async SQLite database | ❌ No |

---

## 🔧 Local Development

```bash
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium

cp .env.example .env
# Edit .env with your values

python main.py
```

---

## 📜 License

MIT — free to use, fork, and modify.
