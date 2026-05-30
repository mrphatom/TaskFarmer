# 🌾 TaskFarmer Telegram Bot

TaskFarmer is a premium, automated task-to-earn Telegram bot designed to manage and verify user micro-tasks, distribute rewards securely in USDT, and foster organic growth through daily check-ins and referral networks.

This system is built using Python, SQLite, and the `pyTelegramBotAPI` library, and is optimized for persistent deployment on platforms like [Railway](https://railway.app/).

---

## ✨ Features

- **🌾 Harvest Tasks:** Display active tasks dynamically. Supports both automated validation and manual file/text proof audits.
- **🛡️ Instant Auto-Verification:** Instantly verifies Telegram Channel/Group memberships using native Telegram Bot API check-ins.
- **🚀 Automated Cash Out:** Connected directly to Telegram's `@CryptoBot` (via Crypto Pay API) for instant, gas-free off-chain USDT transfers directly to users' Telegram IDs.
- **🌱 Daily Cultivation program:** A retention mechanism giving users $0.10 USDT per day for their first 5 active days.
- **🤝 Share the Yield:** A custom deep-linking referral system rewarding inviters $0.16 USDT per active user who registers.
- **💬 Support Helpdesk:** Integrated user support. Users can submit tickets directly inside the bot, and admins can reply instantly using `/reply <user_id> <message>`.
- **⚙️ Admin Dashboard:** Complete control to create new tasks, set global claim limits, audit user submissions manually, and broadcast announcement messages to all registered members.
- **💾 Persistent Database:** Tailored to utilize Railway Persistent Volumes to protect user balances and active tasks against server restarts.

---

## 📁 Repository Structure

```text
├── Procfile             # Tells Railway how to run the application (worker service)
├── requirements.txt     # Python package dependencies
├── database.py          # SQLite database wrapper with persistent path validation
├── bot.py               # Main bot execution file containing commands & UX logic
└── README.md            # Repository documentation