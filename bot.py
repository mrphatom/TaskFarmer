import os
import re
import datetime
import time
import requests
import telebot
from telebot import types
from flask import Flask, request, abort
import database

# --- KEEP-ALIVE WEB SERVER FOR RENDER ---
app = Flask(__name__)

# --- BOT CONFIGURATION ---
API_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID_STR = os.environ.get("ADMIN_ID")
SOLANA_PAY_KEY = os.environ.get("SOLANA_PAY_KEY") 
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL")

if not API_TOKEN or not ADMIN_ID_STR:
    raise ValueError("Missing BOT_TOKEN or ADMIN_ID variables.")

try:
    ADMIN_ID = int(ADMIN_ID_STR)
except ValueError:
    raise ValueError("ADMIN_ID must be a valid numeric Telegram ID.")

# Strip colon from bot token for safe, error-free Flask URL routing
SAFE_ROUTE = API_TOKEN.replace(":", "_")

bot = telebot.TeleBot(API_TOKEN)
database.init_db()

pending_tasks = {}

# --- HELPER FUNCTIONS ---
def is_admin(user_id):
    return user_id == ADMIN_ID

def is_valid_solana_address(address):
    pattern = r"^[1-9A-HJ-NP-Za-km-z]{32,44}$"
    return bool(re.match(pattern, address))

def check_telegram_membership(chat_id_or_username, user_id):
    try:
        member = bot.get_chat_member(chat_id_or_username, user_id)
        if member.status in ['member', 'creator', 'administrator']:
            return True
        return False
    except Exception as e:
        print(f"Error checking membership: {e}")
        return False

def send_solana_usdc_payout(wallet_address, amount_usdc):
    print(f"[SOLANA PAYOUT] Sending {amount_usdc} USDC to {wallet_address}")
    return True, "Solana TX Hash: Simulated"

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
                f"<code>+{ref_reward:.2f} USDC (Solana)</code>",
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"Failed to notify referrer: {e}")

# --- KEYBOARDS ---
def main_keyboard(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("💎 Explore Quests", "💼 Web3 Wallet")
    markup.add("⚡ Daily Claim", "🔗 Referral Hub")
    markup.add("💳 Set Solana Wallet", "📤 Withdraw USDC")
    markup.add("💬 Support Desk")
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

# --- FLASK WEBHOOK ROUTE (SAFE CONTEXT) ---
@app.route(f"/webhook/{SAFE_ROUTE}", methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    else:
        abort(403)

@app.route('/')
def home():
    return "TaskFarmer Core is active and operational."

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
        f"⚡ <b>TaskFarmer Web3 Portal (Solana)</b> ⚡\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Maximize your earnings by participating in crypto quests, "
        f"completing daily claims, and growing your network.\n\n"
        f"💎 <b>Instant Settlements:</b> Paid in USDC "
        f"directly to your <b>Solana (SPL)</b> wallet.\n"
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
        "• Tap <b>📤 Withdraw USDC</b> to claim directly to "
        "your Solana wallet.\n"
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
            f"💰 <b>Allocation:</b> <code>{reward:.2f} USDC</code>\n"
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
        "SELECT balance, wallet_address FROM users WHERE user_id = ?", (user_id,)
    )
    if user:
        balance, wallet = user[0]
        wallet_str = wallet if wallet else "Not Set"
        wallet_card = (
            f"💼 <b>TaskFarmer Dashboard</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 <b>Available Balance:</b> <code>{balance:.2f} USDC</code>\n"
            f"💳 <b>Solana Wallet:</b> <code>{wallet_str}</code>\n\n"
            f"🔐 <i>All withdrawals are settled directly "
            f"on the Solana blockchain.</i>"
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
        f"💰 <b>Credit:</b> <code>+{reward:.2f} USDC</code>"
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
        f"💰 <b>Partner Fee:</b> <code>0.16 USDC</code> per user\n\n"
        f"🔗 <b>Your Partner Link:</b>\n<code>{ref_link}</code>"
    )
    
    bot.send_message(
        message.chat.id,
        ref_card,
        parse_mode="HTML"
    )

# --- SOLANA WALLET SETUP ---
@bot.message_handler(func=lambda message: message.text == "💳 Set Solana Wallet")
def prompt_solana_wallet(message):
    bot.send_message(
        message.chat.id, 
        "💳 <b>Configure Solana Wallet</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        "Please enter your Solana (SPL) wallet address:",
        parse_mode="HTML"
    )
    bot.register_next_step_handler(message, save_solana_wallet)

def save_solana_wallet(message):
    user_id = message.from_user.id
    address = message.text.strip()
    
    if not is_valid_solana_address(address):
        bot.send_message(
            message.chat.id, 
            "❌ <b>Invalid Solana Address</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            "The address provided does not match base58 Solana format. "
            "Please select 'Set Solana Wallet' to try again.",
            parse_mode="HTML"
        )
        return
        
    database.execute_query(
        "UPDATE users SET wallet_address = ? WHERE user_id = ?", 
        (address, user_id)
    )
    bot.send_message(
        message.chat.id, 
        f"✅ <b>Solana Wallet Configured!</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        f"Address saved: <code>{address}</code>",
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
    bot.answer_callback_query(call.id)
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
                f"<code>{reward:.2f} USDC</code> added to your wallet.",
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

# --- SECURE ON-CHAIN SOLANA WITHDRAWAL ---
@bot.message_handler(func=lambda message: message.text == "📤 Withdraw USDC")
def withdraw_request(message):
    user_id = message.from_user.id
    user = database.fetch_query(
        "SELECT balance, wallet_address FROM users WHERE user_id = ?", (user_id,)
    )
    
    if not user:
        return
        
    balance, wallet = user[0]
    
    if not wallet:
        bot.send_message(
            message.chat.id, 
            "❌ <b>Wallet Not Configured</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            "Please click 'Set Solana Wallet' first.",
            parse_mode="HTML"
        )
        return
        
    if balance <= 0:
        bot.send_message(
            message.chat.id, "❌ Balance insufficient."
        )
        return
        
    bot.send_message(
        message.chat.id, 
        f"⚡ <b>Broadcasting on-chain Solana transaction...</b>",
        parse_mode="HTML"
    )
    
    database.execute_query(
        "UPDATE users SET balance = 0.0 WHERE user_id = ?", (user_id,)
    )
    
    success, reason = send_solana_usdc_payout(wallet, balance)
    
    if success:
        bot.send_message(
            message.chat.id, 
            f"✅ <b>USDC Withdrawal Confirmed!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>Transferred:</b> <code>{balance:.4f} USDC</code>\n"
            f"<b>Destination:</b> <code>{wallet}</code>\n\n"
            f"🔓 <i>Transaction fully settled on Solana network.</i>",
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
    bot.answer_callback_query(call.id)  # Dismiss loading spinner
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
        "Enter reward amount (in USDC, numbers only):"
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
        "• <b>One-time Claim:</b> Users can complete this task on