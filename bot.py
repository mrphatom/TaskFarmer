import os
import datetime
import requests
import telebot
from telebot import types
import database

# Retrieve configuration from environment variables
API_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID_STR = os.environ.get("ADMIN_ID")
CRYPTO_PAY_TOKEN = os.environ.get("CRYPTO_PAY_TOKEN")

if not API_TOKEN or not ADMIN_ID_STR:
    raise ValueError("Missing BOT_TOKEN or ADMIN_ID environment variables.")

try:
    ADMIN_ID = int(ADMIN_ID_STR)
except ValueError:
    raise ValueError("ADMIN_ID must be a valid numeric Telegram user ID.")

bot = telebot.TeleBot(API_TOKEN)
database.init_db()

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
    """
    Sends off-chain USDT directly to a user's Telegram ID via Crypto Pay.
    Returns (True, "Success details") or (False, "Error message")
    """
    if not CRYPTO_PAY_TOKEN:
        return False, "Crypto Pay API token is not configured."

    # For testing, you can use: https://testnet-pay.cryptoboot.ru/api/transfer
    # For live mainnet, use: https://pay.cryptoboot.ru/api/transfer
    url = "https://pay.cryptoboot.ru/api/transfer"
    
    headers = {
        "Crypto-Pay-API-Token": CRYPTO_PAY_TOKEN,
        "Content-Type": "application/json"
    }
    
    # Generate a unique spend ID to prevent duplicate requests
    spend_id = f"withdraw_{target_user_id}_{int(datetime.datetime.now().timestamp())}"
    
    data = {
        "user_id": target_user_id,
        "asset": "USDT",
        "amount": str(round(amount_usdt, 4)),
        "spend_id": spend_id
    }
    
    try:
        response = requests.post(url, json=data, headers=headers, timeout=10)
        res_data = response.json()
        
        if response.status_code == 200 and res_data.get("ok"):
            return True, "Payment sent successfully."
        else:
            error_msg = res_data.get("error", {}).get("name", "Unknown Error")
            return False, error_msg
    except Exception as e:
        return False, str(e)

# --- KEYBOARDS ---
def main_keyboard(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("📋 View Tasks", "💰 My Balance")
    markup.add("🎁 Daily Bonus", "🔗 Referral Link")
    markup.add("📤 Withdraw")
    markup.add("💬 Contact Support")
    if is_admin(user_id):
        markup.add("🛠 Admin Panel")
    return markup

def admin_keyboard():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("➕ Add Task", callback_data="admin_add_task"))
    markup.add(types.InlineKeyboardButton("📥 Review Submissions", callback_data="admin_review_submissions"))
    markup.add(types.InlineKeyboardButton("📢 Broadcast Message", callback_data="admin_broadcast"))
    return markup

# --- USER COMMANDS ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    user = database.fetch_query("SELECT * FROM users WHERE user_id = ?", (user_id,))
    
    if not user:
        referred_by = None
        parts = message.text.split()
        if len(parts) > 1:
            try:
                ref_id = int(parts[1])
                if ref_id != user_id:
                    referrer = database.fetch_query("SELECT user_id FROM users WHERE user_id = ?", (ref_id,))
                    if referrer:
                        referred_by = ref_id
            except ValueError:
                pass
        
        database.execute_query(
            "INSERT INTO users (user_id, username, referred_by) VALUES (?, ?, ?)", 
            (user_id, username, referred_by)
        )
        
        if referred_by:
            ref_reward = 0.16
            database.execute_query(
                "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                (ref_reward, referred_by)
            )
            try:
                bot.send_message(
                    referred_by, 
                    f"👥 **New Referral!**\n\n@{username} joined using your link.\n**+{ref_reward} USDT** has been credited to your balance.",
                    parse_mode="Markdown"
                )
            except Exception as e:
                print(f"Failed to notify referrer: {e}")
    
    bot.send_message(
        message.chat.id, 
        "Welcome! Complete tasks, invite friends, and check in daily to earn USDT.", 
        reply_markup=main_keyboard(user_id)
    )

@bot.message_handler(func=lambda message: message.text == "📋 View Tasks")
def view_tasks(message):
    tasks = database.fetch_query(
        "SELECT id, description, reward, max_claims, claims_count FROM tasks WHERE is_active = 1 AND claims_count < max_claims"
    )
    if not tasks:
        bot.send_message(message.chat.id, "No active tasks available at the moment.")
        return
    
    for task in tasks:
        task_id, desc, reward, max_claims, claims_count = task
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Submit Proof", callback_data=f"submit_{task_id}"))
        bot.send_message(
            message.chat.id, 
            f"**Task #{task_id}**\n\n{desc}\n\n**Reward:** {reward} USDT\n**Limit:** {claims_count}/{max_claims} completed", 
            parse_mode="Markdown",
            reply_markup=markup
        )

@bot.message_handler(func=lambda message: message.text == "💰 My Balance")
def check_balance(message):
    user_id = message.from_user.id
    user = database.fetch_query("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    if user:
        balance = user[0][0]
        bot.send_message(
            message.chat.id, 
            f"**Your Balance:** {balance:.2f} USDT\n\nPayments are processed instantly directly to your Telegram `@CryptoBot` wallet.",
            parse_mode="Markdown"
        )

# --- DAILY CHECK-IN SYSTEM ---
@bot.message_handler(func=lambda message: message.text == "🎁 Daily Bonus")
def claim_daily_bonus(message):
    user_id = message.from_user.id
    user = database.fetch_query("SELECT check_in_count, last_check_in FROM users WHERE user_id = ?", (user_id,))
    
    if not user:
        return
        
    check_in_count, last_check_in = user[0]
    
    if check_in_count >= 5:
        bot.send_message(message.chat.id, "❌ You have already completed your 5-day check-in bonus program.")
        return
        
    today_str = datetime.date.today().isoformat()
    
    if last_check_in == today_str:
        bot.send_message(message.chat.id, "❌ You have already claimed today's bonus. Come back tomorrow!")
        return
        
    reward = 0.10
    new_count = check_in_count + 1
    
    database.execute_query(
        "UPDATE users SET check_in_count = ?, last_check_in = ?, balance = balance + ? WHERE user_id = ?",
        (new_count, today_str, reward, user_id)
    )
    
    bot.send_message(
        message.chat.id, 
        f"🎁 **Day {new_count}/5 Check-in Successful!**\n\nYou have received **+{reward:.2f} USDT**.",
        parse_mode="Markdown"
    )

# --- REFERRAL SYSTEM ---
@bot.message_handler(func=lambda message: message.text == "🔗 Referral Link")
def send_referral_link(message):
    user_id = message.from_user.id
    bot_info = bot.get_me()
    bot_username = bot_info.username
    ref_link = f"https://t.me/{bot_username}?start={user_id}"
    
    bot.send_message(
        message.chat.id,
        f"👥 **Referral Program**\n\nInvite your friends and earn rewards when they join!\n\n"
        f"💰 **Reward:** 0.16 USDT per user referred.\n\n"
        f"🔗 **Your Referral Link:**\n`{ref_link}`",
        parse_mode="Markdown"
    )

# --- SUPPORT SYSTEM ---
@bot.message_handler(func=lambda message: message.text == "💬 Contact Support")
def prompt_support_message(message):
    bot.send_message(message.chat.id, "Please write your message or issue for the support team:")
    bot.register_next_step_handler(message, send_support_message_to_admin)

def send_support_message_to_admin(message):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    text = message.text
    
    if not text:
        bot.send_message(message.chat.id, "Invalid text. Support request canceled.")
        return

    bot.send_message(
        ADMIN_ID,
        f"📩 **New Support Ticket**\n\n"
        f"**From User:** @{username} (`{user_id}`)\n"
        f"**Message:** {text}\n\n"
        f"To reply, use: `/reply {user_id} <your message>`",
        parse_mode="Markdown"
    )
    bot.send_message(message.chat.id, "Your message has been sent to our support team.")

@bot.message_handler(commands=['reply'])
def admin_reply_support(message):
    if not is_admin(message.from_user.id):
        return
        
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        bot.send_message(message.chat.id, "Format error. Use: `/reply <user_id> <message>`", parse_mode="Markdown")
        return
        
    try:
        target_user_id = int(parts[1])
        reply_text = parts[2]
        
        bot.send_message(
            target_user_id,
            f"💬 **Support Team Reply:**\n\n{reply_text}"
        )
        bot.send_message(message.chat.id, f"Reply sent successfully to user `{target_user_id}`.")
    except Exception as e:
        bot.send_message(message.chat.id, f"Could not send message: {e}")

# --- SUBMISSION FLOW (AUTO & MANUAL) ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("submit_"))
def handle_submit_request(call):
    task_id = int(call.data.split("_")[1])
    user_id = call.message.chat.id
    
    task = database.fetch_query(
        "SELECT description, reward, max_claims, claims_count FROM tasks WHERE id = ?", (task_id,)
    )
    if not task:
        bot.send_message(user_id, "Task not found.")
        return
        
    description, reward, max_claims, claims_count = task[0]
    
    if claims_count >= max_claims:
        bot.send_message(user_id, "❌ Sorry, this task has already reached its maximum claims limit.")
        return
    
    if description.strip().upper().startswith("JOIN:"):
        target_channel = description.replace("JOIN:", "").strip()
        bot.send_message(user_id, f"Verifying membership for {target_channel}...")
        
        is_member = check_telegram_membership(target_channel, user_id)
        
        if is_member:
            already_done = database.fetch_query(
                "SELECT id FROM submissions WHERE user_id = ? AND task_id = ? AND status = 'APPROVED'",
                (user_id, task_id)
            )
            if already_done:
                bot.send_message(user_id, "You have already completed this task.")
                return
                
            database.execute_query(
                "INSERT INTO submissions (user_id, task_id, proof, status) VALUES (?, ?, 'Auto-verified', 'APPROVED')",
                (user_id, task_id)
            )
            database.execute_query(
                "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                (reward, user_id)
            )
            database.execute_query(
                "UPDATE tasks SET claims_count = claims_count + 1 WHERE id = ?",
                (task_id,)
            )
            bot.send_message(user_id, f"✅ Verified! {reward:.2f} USDT has been credited to your balance.")
        else:
            bot.send_message(
                user_id, 
                f"❌ Verification failed. Please make sure you have joined {target_channel} and try again."
            )
            
    else:
        bot.send_message(user_id, f"Please send proof for Task #{task_id} (e.g., screenshot link, username, or text proof):")
        bot.register_next_step_handler(call.message, process_submission, task_id)

def process_submission(message, task_id):
    user_id = message.from_user.id
    proof = message.text if message.text else "Attachment/Non-text submitted"
    
    database.execute_query(
        "INSERT INTO submissions (user_id, task_id, proof) VALUES (?, ?, ?)",
        (user_id, task_id, proof)
    )
    bot.send_message(message.chat.id, "Submission received. An admin will review it shortly.")

# --- AUTOMATED WITHDRAWAL ---
@bot.message_handler(func=lambda message: message.text == "📤 Withdraw")
def withdraw_request(message):
    user_id = message.from_user.id
    user = database.fetch_query("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    
    if not user:
        return
        
    balance = user[0][0]
    
    if balance <= 0:
        bot.send_message(message.chat.id, "❌ Your balance is insufficient for withdrawal.")
        return
        
    bot.send_message(message.chat.id, f"Sending {balance:.4f} USDT directly to your Telegram @CryptoBot account...")
    
    # Process the transaction through Crypto Bot API
    success, reason = send_crypto_pay_transfer(user_id, balance)
    
    if success:
        # Deduct balance on database only if transaction succeeds
        database.execute_query("UPDATE users SET balance = 0.0 WHERE user_id = ?", (user_id,))
        bot.send_message(
            message.chat.id, 
            f"✅ **Withdrawal Successful!**\n\n{balance:.4f} USDT has been credited to your @CryptoBot account. Open the app to view your balance.",
            parse_mode="Markdown"
        )
    else:
        bot.send_message(
            message.chat.id, 
            f"❌ **Withdrawal Failed.**\n\nReason: `{reason}`\n\nPlease try again later or contact support.",
            parse_mode="Markdown"
        )

# --- ADMIN PANEL ---
@bot.message_handler(func=lambda message: message.text == "🛠 Admin Panel" and is_admin(message.from_user.id))
def admin_panel(message):
    bot.send_message(message.chat.id, "Admin Controls:", reply_markup=admin_keyboard())

# Add Task Flow
@bot.callback_query_handler(func=lambda call: call.data == "admin_add_task")
def admin_add_task_start(call):
    bot.send_message(call.message.chat.id, "Enter task description (use 'JOIN: @username' for automated Telegram checks):")
    bot.register_next_step_handler(call.message, admin_add_task_desc)

def admin_add_task_desc(message):
    desc = message.text
    bot.send_message(message.chat.id, "Enter reward amount (in USDT, numbers only):")
    bot.register_next_step_handler(message, admin_add_task_reward, desc)

def admin_add_task_reward(message, desc):
    try:
        reward = float(message.text)
        bot.send_message(message.chat.id, "Enter maximum claim limit (number of times this task can be completed globally):")
        bot.register_next_step_handler(message, admin_add_task_limit, desc, reward)
    except ValueError:
        bot.send_message(message.chat.id, "Invalid reward amount. Task creation canceled.")

def admin_add_task_limit(message, desc, reward):
    try:
        limit = int(message.text)
        database.execute_query(
            "INSERT INTO tasks (description, reward, max_claims) VALUES (?, ?, ?)", 
            (desc, reward, limit)
        )
        bot.send_message(message.chat.id, "Task added successfully.")
    except ValueError:
        bot.send_message(message.chat.id, "Invalid limit number. Task creation canceled.")

# Admin Broadcast Flow
@bot.callback_query_handler(func=lambda call: call.data == "admin_broadcast")
def admin_broadcast_start(call):
    bot.send_message(call.message.chat.id, "Enter message to broadcast to ALL users:")
    bot.register_next_step_handler(call.message, admin_broadcast_process)

def admin_broadcast_process(message):
    broadcast_text = message.text
    if not broadcast_text:
        bot.send_message(message.chat.id, "Broadcast message cannot be empty.")
        return
        
    users = database.fetch_query("SELECT user_id FROM users")
    success_count = 0
    fail_count = 0
    
    bot.send_message(message.chat.id, f"Broadcasting message to {len(users)} users. Please wait...")
    
    for u in users:
        target_id = u[0]
        try:
            bot.send_message(target_id, f"📢 **Announcement**\n\n{broadcast_text}", parse_mode="Markdown")
            success_count += 1
        except Exception:
            fail_count += 1
            
    bot.send_message(message.chat.id, f"Broadcast complete.\n\nSent: {success_count}\nFailed: {fail_count}")

# Review Submissions Flow
@bot.callback_query_handler(func=lambda call: call.data == "admin_review_submissions")
def admin_review_submissions(call):
    submissions = database.fetch_query(
        """SELECT s.id, s.user_id, s.proof, t.reward, t.description, t.id 
           FROM submissions s 
           JOIN tasks t ON s.task_id = t.id 
           WHERE s.status = 'PENDING' LIMIT 5"""
    )
    
    if not submissions:
        bot.send_message(call.message.chat.id, "No pending submissions.")
        return
        
    for sub in submissions:
        sub_id, user_id, proof, reward, desc, task_id = sub
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("✅ Approve", callback_data=f"approve_{sub_id}_{user_id}_{reward}_{task_id}"),
            types.InlineKeyboardButton("❌ Reject", callback_data=f"reject_{sub_id}")
        )
        bot.send_message(
            call.message.chat.id,
            f"**Submission ID:** {sub_id}\n**User ID:** {user_id}\n**Task:** {desc}\n**Proof:** {proof}\n**Reward:** {reward:.2f} USDT",
            parse_mode="Markdown",
            reply_markup=markup
        )

@bot.callback_query_handler(func=lambda call: call.data.startswith("approve_") or call.data.startswith("reject_"))
def handle_review_decision(call):
    parts = call.data.split("_")
    action = parts[0]
    sub_id = parts[1]
    
    if action == "approve":
        user_id = parts[2]
        reward = float(parts[3])
        task_id = int(parts[4])
        
        task = database.fetch_query("SELECT max_claims, claims_count FROM tasks WHERE id = ?", (task_id,))
        if task:
            max_claims, claims_count = task[0]
            if claims_count >= max_claims:
                bot.send_message(call.message.chat.id, "Cannot approve. This task has reached its global limit.")
                return
        
        database.execute_query("UPDATE users SET balance = balance + ? WHERE user_id = ?", (reward, user_id))
        database.execute_query("UPDATE submissions SET status = 'APPROVED' WHERE id = ?", (sub_id,))
        database.execute_query("UPDATE tasks SET claims_count = claims_count + 1 WHERE id = ?", (task_id,))
        
        try:
            bot.send_message(user_id, f"🎉 Your submission #{sub_id} has been approved! {reward:.2f} USDT has been credited.")
        except Exception as e:
            print(f"Could not notify user {user_id}: {e}")
            
        bot.edit_message_text("Approved ✅", chat_id=call.message.chat.id, message_id=call.message.message_id)
        
    elif action == "reject":
        database.execute_query("UPDATE submissions SET status = 'REJECTED' WHERE id = ?", (sub_id,))
        bot.edit_message_text("Rejected ❌", chat_id=call.message.chat.id, message_id=call.message.message_id)

# --- START BOT ---
if __name__ == "__main__":
    print("Bot is starting...")
    bot.infinity_polling()