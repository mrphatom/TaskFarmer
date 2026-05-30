import os
import datetime
import requests
import telebot
from telebot import types
import database

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
    url = "https://pay.cryptoboot.ru/api/transfer"
    headers = {
        "Crypto-Pay-API-Token": CRYPTO_PAY_TOKEN,
        "Content-Type": "application/json"
    }
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
            return True, "Payment completed."
        else:
            error_msg = res_data.get("error", {}).get("name", "Unknown Error")
            return False, error_msg
    except Exception as e:
        return False, str(e)

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
    markup.add(types.InlineKeyboardButton("➕ Create Quest", callback_data="admin_add_task"))
    markup.add(types.InlineKeyboardButton("📥 Verify Submissions", callback_data="admin_review_submissions"))
    markup.add(types.InlineKeyboardButton("📢 Global Announcement", callback_data="admin_broadcast"))
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
                    f"🤝 **New Referral Partner!**\n━━━━━━━━━━━━━━━━━━━━\n"
                    f"@{username} has joined via your referral link.\n"
                    f"💰 **Token Allocation:** `+{ref_reward:.2f} USDT`",
                    parse_mode="Markdown"
                )
            except Exception as e:
                print(f"Failed to notify referrer: {e}")
    
    welcome_text = (
        f"⚡ **TaskFarmer Web3 Portal** ⚡\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Maximize your earnings by participating in crypto quests, "
        f"completing interactive daily claims, and growing your referral network.\n\n"
        f"💎 **Instant Settlements:** Earned yields are settled instantly in USDT "
        f"directly to your `@CryptoBot` wallet on Telegram.\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Access the options below to initialize your dashboard."
    )
    
    bot.send_message(
        message.chat.id, 
        welcome_text, 
        reply_markup=main_keyboard(user_id),
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda message: message.text == "💎 Explore Quests")
def view_tasks(message):
    tasks = database.fetch_query(
        "SELECT id, description, reward, max_claims, claims_count FROM tasks WHERE is_active = 1 AND claims_count < max_claims"
    )
    if not tasks:
        bot.send_message(
            message.chat.id, 
            "🌐 **No Quests Available**\n━━━━━━━━━━━━━━━━━━━━\nAll standard pools are currently filled. Check back shortly for new contract deployments."
        )
        return
    
    bot.send_message(message.chat.id, "📊 **Active Decentralized Quests**\n━━━━━━━━━━━━━━━━━━━━")
    
    for task in tasks:
        task_id, desc, reward, max_claims, claims_count = task
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Submit Proof", callback_data=f"submit_{task_id}"))
        
        task_card = (
            f"📋 **Quest ID: #{task_id}**\n\n"
            f"📝 **Requirements:**\n{desc}\n\n"
            f"💰 **Allocation:** `{reward:.2f} USDT`\n"
            f"👥 **Pool Status:** {claims_count} / {max_claims} spots filled"
        )
        
        bot.send_message(
            message.chat.id, 
            task_card, 
            parse_mode="Markdown",
            reply_markup=markup
        )

@bot.message_handler(func=lambda message: message.text == "💼 Web3 Wallet")
def check_balance(message):
    user_id = message.from_user.id
    user = database.fetch_query("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    if user:
        balance = user[0][0]
        wallet_card = (
            f"💼 **TaskFarmer Dashboard**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 **Available Balance:** `{balance:.2f} USDT`\n\n"
            f"🔐 *Secure off-chain execution allows seamless transfers straight "
            f"into your `@CryptoBot` account.*"
        )
        bot.send_message(
            message.chat.id, 
            wallet_card,
            parse_mode="Markdown"
        )

# --- DAILY CHECK-IN SYSTEM ---
@bot.message_handler(func=lambda message: message.text == "⚡ Daily Claim")
def claim_daily_bonus(message):
    user_id = message.from_user.id
    user = database.fetch_query("SELECT check_in_count, last_check_in FROM users WHERE user_id = ?", (user_id,))
    
    if not user:
        return
        
    check_in_count, last_check_in = user[0]
    
    if check_in_count >= 5:
        bot.send_message(
            message.chat.id, 
            "🔒 **Allocation Exceeded**\n━━━━━━━━━━━━━━━━━━━━\nYou have completed all 5 allocations of your early supporter program."
        )
        return
        
    today_str = datetime.date.today().isoformat()
    
    if last_check_in == today_str:
        bot.send_message(
            message.chat.id, 
            "⏳ **Cooldown Active**\n━━━━━━━━━━━━━━━━━━━━\nYour daily reward allocation resets in 24 hours. Check back tomorrow."
        )
        return
        
    reward = 0.10
    new_count = check_in_count + 1
    
    database.execute_query(
        "UPDATE users SET check_in_count = ?, last_check_in = ?, balance = balance + ? WHERE user_id = ?",
        (new_count, today_str, reward, user_id)
    )
    
    success_text = (
        f"⚡ **Daily Reward Claimed!**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📈 **Milestone:** Day {new_count} / 5\n"
        f"💰 **Credit:** `+{reward:.2f} USDT`"
    )
    
    bot.send_message(
        message.chat.id, 
        success_text,
        parse_mode="Markdown"
    )

# --- REFERRAL SYSTEM ---
@bot.message_handler(func=lambda message: message.text == "🔗 Referral Hub")
def send_referral_link(message):
    user_id = message.from_user.id
    bot_info = bot.get_me()
    bot_username = bot_info.username
    ref_link = f"https://t.me/{bot_username}?start={user_id}"
    
    ref_card = (
        f"👥 **Web3 Referral Network**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Expand the TaskFarmer ecosystem and earn rewards whenever new users "
        f"register using your partner link.\n\n"
        f"💰 **Partner Fee:** `0.16 USDT` per user\n\n"
        f"🔗 **Your Partner Link:**\n`{ref_link}`"
    )
    
    bot.send_message(
        message.chat.id,
        ref_card,
        parse_mode="Markdown"
    )

# --- SUPPORT SYSTEM ---
@bot.message_handler(func=lambda message: message.text == "💬 Support Desk")
def prompt_support_message(message):
    bot.send_message(
        message.chat.id, 
        "💬 **Helpdesk Terminal**\n━━━━━━━━━━━━━━━━━━━━\n"
        "State your issue or inquiry below. A support technician will review your submission."
    )
    bot.register_next_step_handler(message, send_support_message_to_admin)

def send_support_message_to_admin(message):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    text = message.text
    
    if not text:
        bot.send_message(message.chat.id, "Inquiry invalid. Ticket creation terminated.")
        return

    bot.send_message(
        ADMIN_ID,
        f"📩 **New Ticket Received**\n━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 **User:** @{username} (`{user_id}`)\n"
        f"📝 **Details:** {text}\n━━━━━━━━━━━━━━━━━━━━\n"
        f"Reply using: `/reply {user_id} <message>`",
        parse_mode="Markdown"
    )
    bot.send_message(
        message.chat.id, 
        "✅ **Ticket Created**\n━━━━━━━━━━━━━━━━━━━━\n"
        "Your inquiry has been logged. An administrator will reply to your inbox directly."
    )

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
            f"💬 **Inbound Support Dispatch:**\n━━━━━━━━━━━━━━━━━━━━\n{reply_text}"
        )
        bot.send_message(message.chat.id, f"Reply transmitted to user `{target_user_id}`.")
    except Exception as e:
        bot.send_message(message.chat.id, f"Failed to deliver message: {e}")

# --- SUBMISSION FLOW ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("submit_"))
def handle_submit_request(call):
    task_id = int(call.data.split("_")[1])
    user_id = call.message.chat.id
    
    task = database.fetch_query(
        "SELECT description, reward, max_claims, claims_count FROM tasks WHERE id = ?", (task_id,)
    )
    if not task:
        bot.send_message(user_id, "Quest not found.")
        return
        
    description, reward, max_claims, claims_count = task[0]
    
    if claims_count >= max_claims:
        bot.send_message(user_id, "❌ This pool limit has been reached.")
        return
    
    # Auto Telegram join logic
    if description.strip().upper().startswith("JOIN:"):
        target_channel = description.replace("JOIN:", "").strip()
        bot.send_message(user_id, f"Parsing metadata for {target_channel}...")
        
        is_member = check_telegram_membership(target_channel, user_id)
        
        if is_member:
            already_done = database.fetch_query(
                "SELECT id FROM submissions WHERE user_id = ? AND task_id = ? AND status = 'APPROVED'",
                (user_id, task_id)
            )
            if already_done:
                bot.send_message(user_id, "❌ Address already verified for this pool.")
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
            bot.send_message(
                user_id, 
                f"✅ **Quest Verification Successful!**\n━━━━━━━━━━━━━━━━━━━━\n"
                f"`{reward:.2f} USDT` has been settled in your Web3 Wallet."
            )
        else:
            bot.send_message(
                user_id, 
                f"❌ **Identity Unverified**\n━━━━━━━━━━━━━━━━━━━━\n"
                f"Verification failed for {target_channel}. Join the target space, then retry."
            )
            
    else:
        bot.send_message(
            user_id, 
            f"ℹ️ **Manual Proof Required**\n━━━━━━━━━━━━━━━━━━━━\n"
            f"Please submit the verification proof (screenshot link, transaction hash, or username) below:"
        )
        bot.register_next_step_handler(call.message, process_submission, task_id)

def process_submission(message, task_id):
    user_id = message.from_user.id
    proof = message.text if message.text else "Binary proof submitted"
    
    database.execute_query(
        "INSERT INTO submissions (user_id, task_id, proof) VALUES (?, ?, ?)",
        (user_id, task_id, proof)
    )
    bot.send_message(
        message.chat.id, 
        "✅ **Proof Registered**\n━━━━━━━━━━━━━━━━━━━━\n"
        "Your quest proof is queued. Auditors will process it shortly."
    )

# --- WITHDRAWAL ---
@bot.message_handler(func=lambda message: message.text == "📤 Withdraw USDT")
def withdraw_request(message):
    user_id = message.from_user.id
    user = database.fetch_query("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    
    if not user:
        return
        
    balance = user[0][0]
    
    if balance <= 0:
        bot.send_message(message.chat.id, "❌ Insufficient balance for withdrawal. Complete active quests to earn.")
        return
        
    bot.send_message(message.chat.id, f"⚡ **Broadcasting transaction to send {balance:.4f} USDT...**")
    
    success, reason = send_crypto_pay_transfer(user_id, balance)
    
    if success:
        database.execute_query("UPDATE users SET balance = 0.0 WHERE user_id = ?", (user_id,))
        bot.send_message(
            message.chat.id, 
            f"✅ **Withdrawal Confirmed!**\n━━━━━━━━━━━━━━━━━━━━\n"
            f"**Transferred:** `{balance:.4f} USDT`\n"
            f"Your funds are settled. Open `@CryptoBot` to interact with your balance.",
            parse_mode="Markdown"
        )
    else:
        bot.send_message(
            message.chat.id, 
            f"❌ **Transaction Rejected**\n━━━━━━━━━━━━━━━━━━━━\n"
            f"The network returned an execution error:\n`{reason}`\n\n"
            f"Review your settings or submit a helpdesk ticket.",
            parse_mode="Markdown"
        )

# --- ADMIN PANEL ---
@bot.message_handler(func=lambda message: message.text == "⚙️ Admin Console" and is_admin(message.from_user.id))
def admin_panel(message):
    bot.send_message(
        message.chat.id, 
        "⚙️ **TaskFarmer Administration Console**\n━━━━━━━━━━━━━━━━━━━━\n"
        "Deploy contracts, audit quest entries, and broadcast global system notifications.", 
        reply_markup=admin_keyboard()
    )

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
            bot.send_message(target_id, f"📢 **System Broadcast**\n━━━━━━━━━━━━━━━━━━━━\n{broadcast_text}", parse_mode="Markdown")
            success_count += 1
        except Exception:
            fail_count += 1
            
    bot.send_message(message.chat.id, f"Broadcast complete.\n\nSent: {success_count}\nFailed: {fail_count}")

@bot.callback_query_handler(func=lambda call: call.data == "admin_review_submissions")
def admin_review_submissions(call):
    submissions = database.fetch_query(
        """SELECT s.id, s.user_id, s.proof, t.reward, t.description, t.id 
           FROM submissions s 
           JOIN tasks t ON s.task_id = t.id 
           WHERE s.status = 'PENDING' LIMIT 5"""
    )
    
    if not submissions:
        bot.send_message(call.message.chat.id, "No pending quest audits.")
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
            f"**Verification Ticket #{sub_id}**\n━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 **User ID:** `{user_id}`\n"
            f"📋 **Quest Details:** {desc}\n"
            f"📝 **Client Proof:** {proof}\n"
            f"💰 **Pool Allocation:** `{reward:.2f} USDT`",
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
                bot.send_message(call.message.chat.id, "Approval error: Pool is exhausted.")
                return
        
        database.execute_query("UPDATE users SET balance = balance + ? WHERE user_id = ?", (reward, user_id))
        database.execute_query("UPDATE submissions SET status = 'APPROVED' WHERE id = ?", (sub_id,))
        database.execute_query("UPDATE tasks SET claims_count = claims_count + 1 WHERE id = ?", (task_id,))
        
        try:
            bot.send_message(
                user_id, 
                f"🎉 **Quest Approved!**\n━━━━━━━━━━━━━━━━━━━━\n"
                f"Ticket #{sub_id} passed validation.\n"
                f"💰 **Token Credit:** `{reward:.2f} USDT`"
            )
        except Exception as e:
            print(f"Could not notify user {user_id}: {e}")
            
        bot.edit_message_text("Audit Result: APPROVED ✅", chat_id=call.message.chat.id, message_id=call.message.message_id)
        
    elif action == "reject":
        database.execute_query("UPDATE submissions SET status = 'REJECTED' WHERE id = ?", (sub_id,))
        bot.edit_message_text("Audit Result: REJECTED ❌", chat_id=call.message.chat.id, message_id=call.message.message_id)

# --- START BOT ---
if __name__ == "__main__":
    print("TaskFarmer decentralized core active...")
    bot.infinity_polling()