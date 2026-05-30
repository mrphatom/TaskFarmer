import os
import datetime
import threading
import time
import requests
import telebot
from telebot import types
from flask import Flask
import database

# --- KEEP-ALIVE WEB SERVER FOR RENDER ---
app = Flask(__name__)

@app.route('/')
def home():
    return "TaskFarmer Core is active and operational."

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# --- BOT CONFIGURATION ---
API_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID_STR = os.environ.get("ADMIN_ID")
CRYPTO_PAY_TOKEN = os.environ.get("CRYPTO_PAY_TOKEN")

if not API_TOKEN or not ADMIN_ID_STR:
    raise ValueError(
        "Missing BOT_TOKEN or ADMIN_ID variables."
    )

try:
    ADMIN_ID = int(ADMIN_ID_STR)
except ValueError:
    raise ValueError(
        "ADMIN_ID must be a valid numeric Telegram ID."
    )

bot = telebot.TeleBot(API_TOKEN)
database.init_db()

# In-memory store for incomplete task creation flows
# Keyed by admin's chat_id to prevent database pollution
pending_tasks = {}

# --- HELPER FUNCTIONS ---
def is_admin(user_id):
    return user_id == ADMIN_ID

def check_telegram_membership(chat_id_or_username, user_id):
    try:
        member = bot.get_chat_member(chat_id_or_username, user_id)
        if member.status in ['member', 'creator', 'administrator']:
            return True
        return False
    except Exception as e:
        print(f"Error checking membership: {e}")
        return False

def send_crypto_pay_transfer(target_user_id, amount_usdt):
    url = "https://pay.crypt.bot/api/transfer"
    headers = {
        "Crypto-Pay-API-Token": CRYPTO_PAY_TOKEN,
        "Content-Type": "application/json"
    }
    spend_id = (
        f"withdraw_{target_user_id}_"
        f"{int(datetime.datetime.now().timestamp())}"
    )
    data = {
        "user_id": target_user_id,
        "asset": "USDT",
        "amount": str(round(amount_usdt, 4)),
        "spend_id": spend_id
    }
    try:
        response = requests.post(
            url, json=data, headers=headers, timeout=10
        )
        res_data = response.json()
        if response.status_code == 200 and res_data.get("ok"):
            return True, "Payment completed."
        else:
            error_msg = (
                res_data.get("error", {})
                .get("name", "Unknown Error")
            )
            return False, error_msg
    except Exception as e:
        return False, str(e)

def handle_referral_credit(referred_user_id, username):
    user_info = database.fetch_query(
        "SELECT referred_by, referral_credited "
        "FROM users WHERE user_id = ?", 
        (referred_user_id,)
    )
    if not user_info:
        return
        
    referred_by, referral_credited = user_info[0]
    
    if referred_by and referral_credited == 0:
        ref_reward = 0.16
        database.execute_query(
            "UPDATE users SET referral_credited = 1 "
            "WHERE user_id = ?", 
            (referred_user_id,)
        )
        database.execute_query(
            "UPDATE users SET balance = balance + ? "
            "WHERE user_id = ?",
            (ref_reward, referred_by)
        )
        try:
            bot.send_message(
                referred_by, 
                f"🤝 <b>New Referral Partner!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"@{username} completed their first quest.\n"
                f"💰 <b>Bonus Credited:</b> "
                f"<code>+{ref_reward:.2f} USDT</code>",
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"Failed to notify referrer: {e}")

# --- KEYBOARDS ---
def main_keyboard(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("💎 Explore Quests", "💼 Web3 Wallet")
    markup.add("⚡ Daily Claim", "🔗 Referral Hub")
    markup.add("📤 Withdraw USDT", "💬 Support Desk")
    if is_admin(user_id):
        markup.add("⚙️ Admin Console")
    return markup

def admin_keyboard():
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton(
            "➕ Create Quest", callback_data="admin_add_task"
        )
    )
    markup.add(
        types.InlineKeyboardButton(
            "📥 Verify Submissions", 
            callback_data="admin_review_submissions"
        )
    )
    markup.add(
        types.InlineKeyboardButton(
            "📢 Global Announcement", callback_data="admin_broadcast"
        )
    )
    return markup

# --- USER COMMANDS ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    user = database.fetch_query(
        "SELECT * FROM users WHERE user_id = ?", (user_id,)
    )
    
    if not user:
        referred_by = None
        parts = message.text.split()
        if len(parts) > 1:
            try:
                ref_id = int(parts[1])
                if ref_id != user_id:
                    referrer = database.fetch_query(
                        "SELECT user_id FROM users WHERE user_id = ?", 
                        (ref_id,)
                    )
                    if referrer:
                        referred_by = ref_id
            except ValueError:
                pass
        
        database.execute_query(
            "INSERT INTO users (user_id, username, referred_by) "
            "VALUES (?, ?, ?)", 
            (user_id, username, referred_by)
        )
    
    welcome_text = (
        f"⚡ <b>TaskFarmer Web3 Portal</b> ⚡\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Maximize your earnings by participating in crypto quests, "
        f"completing daily claims, and growing your network.\n\n"
        f"💎 <b>Instant Settlements:</b> Paid in USDT "
        f"directly to your <code>@CryptoBot</code> wallet.\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Access the options below to initialize your dashboard."
    )
    
    bot.send_message(
        message.chat.id, 
        welcome_text, 
        reply_markup=main_keyboard(user_id),
        parse_mode="HTML"
    )

@bot.message_handler(commands=['help'])
def send_help_info(message):
    help_text = (
        "ℹ️ <b>TaskFarmer Help Guide</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        "• Tap <b>💎 Explore Quests</b> to find active contract pools.\n"
        "• Tap <b>📤 Withdraw USDT</b> to claim directly to "
        "<code>@CryptoBot</code>.\n"
        "• Tap <b>💬 Support Desk</b> to reach the team."
    )
    bot.send_message(message.chat.id, help_text, parse_mode="HTML")

@bot.message_handler(func=lambda message: message.text == "💎 Explore Quests")
def view_tasks(message):
    user_id = message.from_user.id
    tasks = database.fetch_query(
        "SELECT id, description, reward, max_claims, "
        "claims_count, max_user_claims FROM tasks "
        "WHERE is_active = 1 AND claims_count < max_claims"
    )
    if not tasks:
        bot.send_message(
            message.chat.id, 
            "🌐 <b>No Quests Available</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            "All pools are filled. Check back shortly.",
            parse_mode="HTML"
        )
        return
    
    bot.send_message(
        message.chat.id, 
        "📊 <b>Active Decentralized Quests</b>\n━━━━━━━━━━━━━━━━━━━━",
        parse_mode="HTML"
    )
    
    for task in tasks:
        task_id, desc, reward, max_claims, claims_count, max_user_claims = task
        
        user_submissions_count = database.fetch_query(
            "SELECT COUNT(*) FROM submissions "
            "WHERE user_id = ? AND task_id = ? AND status != 'REJECTED'",
            (user_id, task_id)
        )[0][0]
        
        if user_submissions_count >= max_user_claims:
            continue
            
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton(
                "Submit Proof", callback_data=f"submit_{task_id}"
            )
        )
        
        claim_limit_type = (
            "One-time" if max_user_claims == 1 
            else f"Max {max_user_claims} per user"
        )
        
        task_card = (
            f"📋 <b>Quest ID: #{task_id}</b>\n\n"
            f"📝 <b>Requirements:</b>\n{desc}\n\n"
            f"💰 <b>Allocation:</b> <code>{reward:.2f} USDT</code>\n"
            f"👥 <b>Pool Status:</b> {claims_count}/{max_claims} spots filled\n"
            f"🔒 <b>Limit Type:</b> {claim_limit_type} "
            f"({user_submissions_count}/{max_user_claims} claimed)"
        )
        
        try:
            bot.send_message(
                message.chat.id, 
                task_card, 
                parse_mode="HTML",
                reply_markup=markup
            )
        except Exception as e:
            print(f"Failed to send task card: {e}")

@bot.message_handler(func=lambda message: message.text == "💼 Web3 Wallet")
def check_balance(message):
    user_id = message.from_user.id
    user = database.fetch_query(
        "SELECT balance FROM users WHERE user_id = ?", (user_id,)
    )
    if user:
        balance = user[0][0]
        wallet_card = (
            f"💼 <b>TaskFarmer Dashboard</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 <b>Available Balance:</b> <code>{balance:.2f} USDT</code>\n\n"
            f"🔐 <i>Secure off-chain execution allows seamless "
            f"transfers straight into your @CryptoBot account.</i>"
        )
        bot.send_message(
            message.chat.id, 
            wallet_card,
            parse_mode="HTML"
        )

# --- DAILY CHECK-IN SYSTEM ---
@bot.message_handler(func=lambda message: message.text == "⚡ Daily Claim")
def claim_daily_bonus(message):
    user_id = message.from_user.id
    user = database.fetch_query(
        "SELECT check_in_count, last_check_in "
        "FROM users WHERE user_id = ?", (user_id,)
    )
    
    if not user:
        return
        
    check_in_count, last_check_in = user[0]
    
    if check_in_count >= 5:
        bot.send_message(
            message.chat.id, 
            "🔒 <b>Allocation Exceeded</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            "You have completed your 5-day welcome check-in program.",
            parse_mode="HTML"
        )
        return
        
    today_str = datetime.date.today().isoformat()
    
    if last_check_in == today_str:
        bot.send_message(
            message.chat.id, 
            "⏳ <b>Cooldown Active</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            "Your allocation resets in 24 hours. Check back tomorrow.",
            parse_mode="HTML"
        )
        return
        
    reward = 0.10
    new_count = check_in_count + 1
    
    database.execute_query(
        "UPDATE users SET check_in_count = ?, last_check_in = ?, "
        "balance = balance + ? WHERE user_id = ?",
        (new_count, today_str, reward, user_id)
    )
    
    success_text = (
        f"⚡ <b>Daily Reward Claimed!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📈 <b>Milestone:</b> Day {new_count} / 5\n"
        f"💰 <b>Credit:</b> <code>+{reward:.2f} USDT</code>"
    )
    
    bot.send_message(
        message.chat.id, 
        success_text,
        parse_mode="HTML"
    )

# --- REFERRAL SYSTEM ---
@bot.message_handler(func=lambda message: message.text == "🔗 Referral Hub")
def send_referral_link(message):
    user_id = message.from_user.id
    bot_info = bot.get_me()
    bot_username = bot_info.username
    ref_link = f"https://t.me/{bot_username}?start={user_id}"
    
    ref_card = (
        f"👥 <b>Web3 Referral Network</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Expand the TaskFarmer ecosystem and earn rewards whenever "
        f"new users register using your partner link.\n\n"
        f"💰 <b>Partner Fee:</b> <code>0.16 USDT</code> per user\n\n"
        f"🔗 <b>Your Partner Link:</b>\n<code>{ref_link}</code>"
    )
    
    bot.send_message(
        message.chat.id,
        ref_card,
        parse_mode="HTML"
    )

# --- SUPPORT SYSTEM ---
@bot.message_handler(func=lambda message: message.text == "💬 Support Desk")
def prompt_support_message(message):
    bot.send_message(
        message.chat.id, 
        "💬 <b>Helpdesk Terminal</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        "State your inquiry below. A technician will review it.",
        parse_mode="HTML"
    )
    bot.register_next_step_handler(
        message, send_support_message_to_admin
    )

def send_support_message_to_admin(message):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    text = message.text
    
    if not text:
        bot.send_message(
            message.chat.id, "Inquiry invalid. Canceled."
        )
        return

    safe_text = text.replace("<", "&lt;").replace(">", "&gt;")

    bot.send_message(
        ADMIN_ID,
        f"📩 <b>New Ticket Received</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>User:</b> @{username} (<code>{user_id}</code>)\n"
        f"📝 <b>Details:</b> {safe_text}\n━━━━━━━━━━━━━━━━━━━━\n"
        f"Reply: <code>/reply {user_id} &lt;message&gt;</code>",
        parse_mode="HTML"
    )
    bot.send_message(
        message.chat.id, 
        "✅ <b>Ticket Created</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        "Your inquiry has been logged. Admin will reply directly.",
        parse_mode="HTML"
    )

@bot.message_handler(commands=['reply'])
def admin_reply_support(message):
    if not is_admin(message.from_user.id):
        return
        
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        bot.send_message(
            message.chat.id, 
            "Format error. Use: <code>/reply ID &lt;message&gt;</code>", 
            parse_mode="HTML"
        )
        return
        
    try:
        target_user_id = int(parts[1])
        reply_text = parts[2]
        
        bot.send_message(
            target_user_id,
            f"💬 <b>Inbound Support Dispatch:</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n{reply_text}"
        )
        bot.send_message(
            message.chat.id, 
            f"Reply sent to user <code>{target_user_id}</code>.", 
            parse_mode="HTML"
        )
    except Exception as e:
        bot.send_message(message.chat.id, f"Failed to deliver: {e}")

# --- SUBMISSION FLOW ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("submit_"))
def handle_submit_request(call):
    bot.answer_callback_query(call.id) # Dismiss spinner instantly
    task_id = int(call.data.split("_")[1])
    user_id = call.message.chat.id
    
    task = database.fetch_query(
        "SELECT description, reward, max_claims, claims_count, "
        "max_user_claims FROM tasks WHERE id = ?", (task_id,)
    )
    if not task:
        bot.send_message(user_id, "Quest not found.")
        return
        
    description, reward, max_claims, claims_count, max_user_claims = task[0]
    
    if claims_count >= max_claims:
        bot.send_message(user_id, "❌ This pool limit has been reached.")
        return
        
    user_submissions_count = database.fetch_query(
        "SELECT COUNT(*) FROM submissions "
        "WHERE user_id = ? AND task_id = ? AND status != 'REJECTED'",
        (user_id, task_id)
    )[0][0]
    
    if user_submissions_count >= max_user_claims:
        bot.send_message(
            user_id, 
            f"❌ You have reached your limit of {max_user_claims}."
        )
        return
    
    if description.strip().upper().startswith("JOIN:"):
        target_channel = description.replace("JOIN:", "").strip()
        bot.send_message(
            user_id, f"Parsing metadata for {target_channel}..."
        )
        
        is_member = check_telegram_membership(target_channel, user_id)
        
        if is_member:
            database.execute_query(
                "INSERT INTO submissions (user_id, task_id, proof, status) "
                "VALUES (?, ?, 'Auto-verified', 'APPROVED')",
                (user_id, task_id)
            )
            database.execute_query(
                "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                (reward, user_id)
            )
            database.execute_query(
                "UPDATE tasks SET claims_count = claims_count + 1 "
                "WHERE id = ?", (task_id,)
            )
            bot.send_message(
                user_id, 
                f"✅ <b>Quest Verification Successful!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"<code>{reward:.2f} USDT</code> added to your wallet.",
                parse_mode="HTML"
            )
            user_info = database.fetch_query(
                "SELECT username FROM users WHERE user_id = ?", (user_id,)
            )
            username = user_info[0][0] if user_info else "Unknown"
            handle_referral_credit(user_id, username)
        else:
            bot.send_message(
                user_id, 
                f"❌ <b>Identity Unverified</b>\n━━━━━━━━━━━━━━━━━━━━\n"
                f"Please join {target_channel} and retry.",
                parse_mode="HTML"
            )
            
    else:
        bot.send_message(
            user_id, 
            f"ℹ️ <b>Manual Proof Required</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            f"Please upload a screenshot or send text proof:",
            parse_mode="HTML"
        )
        bot.register_next_step_handler(
            call.message, process_submission, task_id
        )

def process_submission(message, task_id):
    user_id = message.from_user.id
    
    if message.photo:
        file_id = message.photo[-1].file_id
        proof = f"PHOTO:{file_id}"
    elif message.text:
        proof = message.text.replace("<", "&lt;").replace(">", "&gt;")
    else:
        bot.send_message(
            message.chat.id, "Please upload an image or text proof."
        )
        return

    database.execute_query(
        "INSERT INTO submissions (user_id, task_id, proof) "
        "VALUES (?, ?, ?)", (user_id, task_id, proof)
    )
    bot.send_message(
        message.chat.id, 
        "✅ <b>Proof Registered</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        "Your quest proof is queued. Auditors will process it.",
        parse_mode="HTML"
    )

# --- SECURE WITHDRAWAL ---
@bot.message_handler(func=lambda message: message.text == "📤 Withdraw USDT")
def withdraw_request(message):
    user_id = message.from_user.id
    user = database.fetch_query(
        "SELECT balance FROM users WHERE user_id = ?", (user_id,)
    )
    
    if not user:
        return
        
    balance = user[0][0]
    
    if balance <= 0:
        bot.send_message(
            message.chat.id, "❌ Balance insufficient."
        )
        return
        
    bot.send_message(
        message.chat.id, 
        f"⚡ <b>Broadcasting transaction...</b>",
        parse_mode="HTML"
    )
    
    database.execute_query(
        "UPDATE users SET balance = 0.0 WHERE user_id = ?", (user_id,)
    )
    
    success, reason = send_crypto_pay_transfer(user_id, balance)
    
    if success:
        bot.send_message(
            message.chat.id, 
            f"✅ <b>Withdrawal Confirmed!</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            f"**Transferred:** <code>{balance:.4f} USDT</code>\n"
            f"Claim completed directly to your @CryptoBot wallet.",
            parse_mode="HTML"
        )
    else:
        database.execute_query(
            "UPDATE users SET balance = balance + ? WHERE user_id = ?", 
            (balance, user_id)
        )
        bot.send_message(
            message.chat.id, 
            f"❌ <b>Transaction Rejected</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            f"Error: <code>{reason}</code>\n\n"
            f"Funds have been refunded safely to your balance.",
            parse_mode="HTML"
        )

# --- ADMIN PANEL ---
@bot.message_handler(
    func=lambda message: message.text == "⚙️ Admin Console" 
    and is_admin(message.from_user.id)
)
def admin_panel(message):
    bot.send_message(
        message.chat.id, 
        "⚙️ <b>TaskFarmer Administration Console</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        "Audit quest entries, and broadcast system notifications.", 
        reply_markup=admin_keyboard(),
        parse_mode="HTML"
    )

# --- ADMIN: CREATE QUEST FLOW ---

@bot.callback_query_handler(func=lambda call: call.data == "admin_add_task")
def admin_add_task_start(call):
    bot.answer_callback_query(call.id)  # Answer callback to dismiss loading spinner
    bot.send_message(
        call.message.chat.id, 
        "Enter task description (use 'JOIN: @username' for automated Telegram checks):"
    )
    bot.register_next_step_handler(call.message, admin_add_task_desc)

def admin_add_task_desc(message):
    desc = message.text
    if not desc or not desc.strip():
        bot.send_message(
            message.chat.id, 
            "❌ Description cannot be empty. Task creation canceled."
        )
        return
    bot.send_message(
        message.chat.id, 
        "Enter reward amount (in USDT, numbers only):"
    )
    bot.register_next_step_handler(message, admin_add_task_reward, desc)

def admin_add_task_reward(message, desc):
    try:
        reward = float(message.text)
        if reward <= 0:
            bot.send_message(
                message.chat.id, 
                "❌ Reward must be greater than 0. Task creation canceled."
            )
            return
    except ValueError:
        bot.send_message(
            message.chat.id, 
            "❌ Invalid reward amount. Task creation canceled."
        )
        return
    bot.send_message(
        message.chat.id, 
        "Enter maximum global claim limit (total times this task can be completed):"
    )
    bot.register_next_step_handler(message, admin_add_task_limit, desc, reward)

def admin_add_task_limit(message, desc, reward):
    try:
        limit = int(message.text)
        if limit <= 0:
            bot.send_message(
                message.chat.id, 
                "❌ Limit must be greater than 0. Task creation canceled."
            )
            return
    except ValueError:
        bot.send_message(
            message.chat.id, 
            "❌ Invalid limit number. Task creation canceled."
        )
        return

    markup = types.InlineKeyboardMarkup()
    # Save parameters in state memory cleanly without pre-database pollution
    pending_tasks[message.chat.id] = {
        "desc": desc, "reward": reward, "limit": limit
    }

    markup.add(
        types.InlineKeyboardButton(
            "🔒 One-time Claim",  callback_data="setclaim_single"
        ),
        types.InlineKeyboardButton(
            "🔄 Multiple Claims", callback_data="setclaim_multi"
        )
    )
    bot.send_message(
        message.chat.id,
        "Configure user submission limits:\n\n"
        "• <b>One-time Claim:</b> Users can complete this task only once.\n"
        "• <b>Multiple Claims:</b> Users can submit proof multiple times.",
        reply_markup=markup,
        parse_mode="HTML"
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("setclaim_"))
def handle_claimtype_selection(call):
    bot.answer_callback_query(call.id)  # Dismiss Telegram's loading spinner

    action = call.data.split("_")[1]  # "single" or "multi"
    admin_chat_id = call.message.chat.id

    task_data = pending_tasks.get(admin_chat_id)
    if not task_data:
        bot.send_message(
            admin_chat_id, 
            "❌ Session expired. Please create the task again."
        )
        return

    if action == "single":
        _finalize_task(admin_chat_id, task_data, max_user_claims=1, call=call)

    elif action == "multi":
        bot.send_message(
            admin_chat_id, 
            "Enter maximum allowed submissions per individual user (numbers only):"
        )
        bot.register_next_step_handler(
            call.message, admin_add_task_user_limit, task_data, call
        )

def admin_add_task_user_limit(message, task_data, call):
    try:
        user_limit = int(message.text)
        if user_limit <= 0:
            bot.send_message(
                message.chat.id, "❌ Must be greater than 0. Try again:"
            )
            bot.register_next_step_handler(
                message, admin_add_task_user_limit, task_data, call
            )
            return
    except ValueError:
        bot.send_message(message.chat.id, "❌ Invalid number. Try again:")
        bot.register_next_step_handler(
            message, admin_add_task_user_limit, task_data, call
        )
        return

    _finalize_task(
        message.chat.id, task_data, max_user_claims=user_limit, call=call
    )

def _finalize_task(chat_id, task_data, max_user_claims, call=None):
    try:
        # Atomic secure insert returning generated ID
        task_id = database.execute_query(
            "INSERT INTO tasks "
            "(description, reward, max_claims, max_user_claims, is_active) "
            "VALUES (?, ?, ?, ?, 1)",
            (task_data["desc"], task_data["reward"], 
             task_data["limit"], max_user_claims)
        )
        if not task_id:
            raise Exception("Database transaction failed.")

        # Clean up pending state memory
        pending_tasks.pop(chat_id, None)

        if call:
            try:
                bot.edit_message_text(
                    f"✅ <b>Quest #{task_id} activated!</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"📝 {task_data['desc']}\n"
                    f"💰 {task_data['reward']:.2f} USDT | "
                    f"👥 Max {task_data['limit']} global | "
                    f"🔒 {'One-time' if max_user_claims == 1 else f'Up to {max_user_claims} per user'}",
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    parse_mode="HTML"
                )
            except Exception:
                bot.send_message(
                    chat_id,
                    f"✅ <b>Quest #{task_id} activated successfully!</b>",
                    parse_mode="HTML"
                )
        else:
            bot.send_message(
                chat_id,
                f"✅ <b>Quest #{task_id} activated successfully!</b>",
                parse_mode="HTML"
            )

    except Exception as e:
        print(f"Task creation error: {e}")
        bot.send_message(
            chat_id, 
            f"❌ Task creation failed: <code>{e}</code>", 
            parse_mode="HTML"
        )

# Admin Broadcast Flow
@bot.callback_query_handler(func=lambda call: call.data == "admin_broadcast")
def admin_broadcast_start(call):
    bot.answer_callback_query(call.id)
    bot.send_message(
        call.message.chat.id, "Enter message to broadcast:"
    )
    bot.register_next_step_handler(
        call.message, admin_broadcast_process
    )

def admin_broadcast_process(message):
    broadcast_text = message.text
    if not broadcast_text:
        bot.send_message(
            message.chat.id, "Message cannot be empty."
        )
        return
        
    users = database.fetch_query("SELECT user_id FROM users")
    success_count = 0
    fail_count = 0
    
    bot.send_message(
        message.chat.id, "Broadcasting. Please wait..."
    )
    
    for u in users:
        target_id = u[0]
        try:
            bot.send_message(
                target_id, 
                f"📢 <b>System Broadcast</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n{broadcast_text}", 
                parse_mode="HTML"
            )
            success_count += 1
            time.sleep(0.05)
        except Exception:
            fail_count += 1
            
    bot.send_message(
        message.chat.id, 
        f"Broadcast complete.\n\n"
        f"Sent: {success_count}\nFailed: {fail_count}"
    )

# Verify Submissions Flow
@bot.callback_query_handler(
    func=lambda call: call.data == "admin_review_submissions"
)
def admin_review_submissions(call):
    bot.answer_callback_query(call.id)
    submissions = database.fetch_query(
        "SELECT s.id, s.user_id, s.proof, t.reward, "
        "t.description, t.id "
        "FROM submissions s "
        "JOIN tasks t ON s.task_id = t.id "
        "WHERE s.status = 'PENDING' LIMIT 5"
    )
    
    if not submissions:
        bot.send_message(
            call.message.chat.id, "No pending quest audits."
        )
        return
        
    for sub in submissions:
        sub_id, user_id, proof, reward, desc, task_id = sub
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton(
                "✅ Approve", callback_data=f"approve_{sub_id}"
            ),
            types.InlineKeyboardButton(
                "❌ Reject", callback_data=f"reject_{sub_id}"
            )
        )
        
        info_header = (
            f"<b>Verification Ticket #{sub_id}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>User ID:</b> <code>{user_id}</code>\n"
            f"📋 <b>Quest Details:</b> {desc}\n"
            f"💰 <b>Pool Allocation:</b> <code>{reward:.2f} USDT</code>"
        )
        
        try:
            if str(proof).startswith("PHOTO:"):
                file_id = str(proof).replace("PHOTO:", "")
                bot.send_photo(
                    call.message.chat.id,
                    file_id,
                    caption=info_header,
                    parse_mode="HTML",
                    reply_markup=markup
                )
            else:
                bot.send_message(
                    call.message.chat.id,
                    f"{info_header}\n📝 <b>Text Proof:</b> {proof}",
                    parse_mode="HTML",
                    reply_markup=markup
                )
        except Exception as e:
            print(f"Failed to send submission card: {e}")

@bot.callback_query_handler(
    func=lambda call: call.data.startswith("approve_") 
    or call.data.startswith("reject_")
)
def handle_review_decision(call):
    bot.answer_callback_query(call.id)
    parts = call.data.split("_")
    action = parts[0]
    sub_id = int(parts[1])
    
    sub_data = database.fetch_query(
        "SELECT s.user_id, t.reward, t.id, s.status, u.username "
        "FROM submissions s "
        "JOIN tasks t ON s.task_id = t.id "
        "JOIN users u ON s.user_id = u.user_id "
        "WHERE s.id = ?",
        (sub_id,)
    )
    
    if not sub_data or sub_data[0][3] != 'PENDING':
        return
        
    user_id, reward, task_id, status, username = sub_data[0]
    
    if action == "approve":
        task = database.fetch_query(
            "SELECT max_claims, claims_count FROM tasks WHERE id = ?", 
            (task_id,)
        )
        if task:
            max_claims, claims_count = task[0]
            if claims_count >= max_claims:
                bot.send_message(
                    call.message.chat.id, 
                    "Approval error: Pool is exhausted."
                )
                return
        
        database.execute_query(
            "UPDATE users SET balance = balance + ? WHERE user_id = ?", 
            (reward, user_id)
        )
        database.execute_query(
            "UPDATE submissions SET status = 'APPROVED' WHERE id = ?", 
            (sub_id,)
        )
        database.execute_query(
            "UPDATE tasks SET claims_count = claims_count + 1 "
            "WHERE id = ?", (task_id,)
        )
        
        try:
            bot.send_message(
                user_id, 
                f"🎉 <b>Quest Approved!</b>\n━━━━━━━━━━━━━━━━━━━━\n"
                f"Ticket #{sub_id} passed validation.\n"
                f"💰 <b>Token Credit:</b> <code>{reward:.2f} USDT</code>",
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"Could not notify user {user_id}: {e}")
            
        handle_referral_credit(user_id, username)
        
        if call.message.photo:
            bot.edit_message_caption(
                "Audit Result: APPROVED ✅", 
                chat_id=call.message.chat.id, 
                message_id=call.message.message_id
            )
        else:
            bot.edit_message_text(
                "Audit Result: APPROVED ✅", 
                chat_id=call.message.chat.id, 
                message_id=call.message.message_id
            )
        
    elif action == "reject":
        database.execute_query(
            "UPDATE submissions SET status = 'REJECTED' WHERE id = ?", 
            (sub_id,)
        )
        if call.message.photo:
            bot.edit_message_caption(
                "Audit Result: REJECTED ❌", 
                chat_id=call.message.chat.id, 
                message_id=call.message.message_id
            )
        else:
            bot.edit_message_text(
                "Audit Result: REJECTED ❌", 
                chat_id=call.message.chat.id, 
                message_id=call.message.message_id
            )


# --- START THREADS (SAFE CONTEXT RUNNER) ---
if __name__ == "__main__":
    bot_thread = threading.Thread(
        target=lambda: bot.infinity_polling()
    )
    bot_thread.daemon = True
    bot_thread.start()
    
    print("TaskFarmer decentralized core active...")
    run_web_server()