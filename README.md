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
```

## 🚀 Deployment Guide (Railway)

### 1. Prerequisites
Before deploying, make sure you have:
1. A **Telegram Bot Token** from [@BotFather](https://t.me/BotFather).
2. Your **Telegram User ID** (retrieve it from `@userinfobot`).
3. An **API Token** from `@CryptoBot` (send `/pay` to `@CryptoBot` to generate an app token).

### 2. Configure Railway Variables
When setting up your service on Railway, add the following three environment variables:

| Variable Name | Required | Description |
| :--- | :--- | :--- |
| `BOT_TOKEN` | Yes | Your Telegram Bot token from `@BotFather`. |
| `ADMIN_ID` | Yes | Your numerical Telegram user ID. |
| `CRYPTO_PAY_TOKEN` | Yes | Your API key from `@CryptoBot` to authorize USDT transfers. |

### 3. Attach a Persistent Volume (Critical for Database)
Because Railway's file system is ephemeral, you must configure a volume to prevent database resets:
1. In the Railway dashboard, open your **TaskFarmer** service settings.
2. Scroll to **Volumes** and click **Add Volume**.
3. Configure the **Mount Path** exactly to: `/app/data`
4. Click **Save**. Railway will automatically reboot and start saving the SQLite files on persistent disk.

---

## 🛠️ Admin Instructions

### How to Create an Automated Task
When using the **⚙️ Farm Command** -> **Create Task** option, you can choose two ways to configure the task description:

* **Automated Telegram Task:** Type `JOIN: @channel_username` (e.g., `JOIN: @taskfarmer_news`). Ensure your bot is an Administrator in that channel so it can verify the membership.
* **Manual Review Task:** Write any standard description (e.g., *Follow @account on Twitter and submit your profile link*). The user will be requested to send text proof, which you can approve/reject inside the audit menu.

### Replying to Support Tickets
When users submit support requests, you will receive a message with a reply instruction. Use the following slash command format in your private chat with the bot to respond:
```text
/reply <user_id> Your response message goes here.
