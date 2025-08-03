import requests
import time
import sqlite3
from datetime import datetime, timedelta
import threading
import csv
import stripe
import os
from dotenv import load_dotenv

# === LOAD ENV VARS ===
load_dotenv()  # Load from .env file if present


# === CONFIGURATION ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/"
VIP_GROUP_LINK = os.getenv("VIP_GROUP_LINK")
VIP_GROUP_ID = os.getenv("VIP_GROUP_ID")
ADMINS = ["MrAlexis21", "Chankfcx"]
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

# === DATABASE SETUP ===
conn = sqlite3.connect("users.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""CREATE TABLE IF NOT EXISTS users (
    telegram_id INTEGER PRIMARY KEY,
    username TEXT,
    plan TEXT,
    expiry TEXT
)""")
conn.commit()

# === Add 'email' column if not exists ===
try:
    cursor.execute("ALTER TABLE users ADD COLUMN email TEXT")
    conn.commit()
except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e).lower():
        pass  # Column already exists, skip
    else:
        raise  # Raise unexpected errors


# === UTILITY FUNCTIONS ===
def send_message(chat_id, text):
    requests.post(API_URL + "sendMessage", json={"chat_id": chat_id, "text": text})

def get_updates(offset=None):
    url = API_URL + "getUpdates"
    if offset:
        url += f"?offset={offset}"
    response = requests.get(url)
    return response.json()

def is_admin(username):
    return username.lstrip("@") in ADMINS

def format_date(date_str):
    return datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y-%m-%d")

def check_expired_users():
    now = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("SELECT telegram_id, username FROM users WHERE expiry <= ?", (now,))
    expired_users = cursor.fetchall()
    for user_id, username in expired_users:
        try:
            # Silently remove user by ban + unban
            requests.post(f"{API_URL}/banChatMember", data={
                "chat_id": VIP_GROUP_ID,
                "user_id": user_id
            })
            requests.post(f"{API_URL}/unbanChatMember", data={
                "chat_id": VIP_GROUP_ID,
                "user_id": user_id
            })
            # Mark plan as expired
            cursor.execute("UPDATE users SET plan = 'Expired' WHERE telegram_id = ?", (user_id,))
            conn.commit()
            print(f"✅ Auto-removed expired user @{username}")
        except Exception as e:
            print(f"❌ Failed to auto-remove @{username}: {e}")


def alert_expiring_users():
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    cursor.execute("SELECT telegram_id FROM users WHERE expiry = ?", (tomorrow,))
    for row in cursor.fetchall():
        send_message(row[0], "⚠️ Your VIP access expires *tomorrow*. Renew now to avoid interruption:\n/renewal")

def start_expiry_checker():
    while True:
        check_expired_users()
        time.sleep(60)

threading.Thread(target=start_expiry_checker, daemon=True).start()

def export_users(chat_id):
    try:
        print("[DEBUG] Starting export_users")

        export_path = "users_export.csv"
        cursor.execute("SELECT telegram_id, username, plan, expiry FROM users")
        rows = cursor.fetchall()

        if not rows:
            send_message(chat_id, "ℹ️ No users found in the database.")
            return
        
            with open(export_path, "w", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)
                writer.writerow(["telegram_id", "username", "plan", "expiry"])
                for row in rows:
                    writer.writerow(row)

            print("[DEBUG] CSV written, attempting to send file...")

            with open(export_path, "rb") as doc:
                response = requests.post(
                    f"{API_URL}sendDocument",
                    data={"chat_id": chat_id},
                    files={"document": ("users_export.csv", doc)}
                )
            print("[DEBUG] Telegram API Response:", response.json())

            if response.status_code == 200 and response.json().get("ok"):
                print("✅ Export sent successfully.")
            else:
                print("❌ Failed to send export.")
                send_message(chat_id, "❌ Telegram error: failed to send document.")

    except Exception as e:
        print(f"❌ Error exporting users: {e}")
        send_message(chat_id, "❌ Something went wrong during export.")


def handle_add_user(username_to_add):
    # Remove @ from username if present
    username_to_add = username_to_add.lstrip("@")

    cursor.execute("SELECT telegram_id FROM users WHERE username = ?", (username_to_add,))
    row = cursor.fetchone()

    if not row:
        send_message(chat_id, f"❌ @{username_to_add} has not started the bot yet.")
        return

    telegram_id = row[0]
    plan = "Edge"
    expiry = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")

    # Update DB with VIP access
    cursor.execute("UPDATE users SET plan = ?, expiry = ? WHERE telegram_id = ?", (plan, expiry, telegram_id))
    conn.commit()

    # Generate 1-time group invite link (valid 30 mins, 1 user only)
    expire_time = int(time.time()) + 1800  # 30 minutes
    payload = {
        "chat_id": VIP_GROUP_ID,
        "member_limit": 1,
        "expire_date": expire_time
    }
    r = requests.post(API_URL + "createChatInviteLink", json=payload)
    result = r.json()

    if result.get("ok"):
        invite_link = result["result"]["invite_link"]
        send_message(telegram_id, f"🚪 Welcome to SignalyX VIP!\n\nHere is your private group access link (valid for 30 minutes, single-use):\n{invite_link}")
        send_message(chat_id, f"✅ @{username_to_add} has been added with full access.\nDefault expiry: 30 days from today.")
    else:
        send_message(chat_id, f"⚠️ Failed to create invite link.\nReason: {result.get('description')}")

def export_users(chat_id):
    try:
        print("[DEBUG] Starting export_users")
        export_path = "users_export.csv"
        cursor.execute("SELECT telegram_id, username, plan, expiry FROM users")
        rows = cursor.fetchall()
        print(f"[DEBUG] Rows fetched: {len(rows)}")

        if not rows:
            send_message(chat_id, "ℹ️ No users found in the database.")
            return

        # Write to CSV
        with open(export_path, "w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(["telegram_id", "username", "plan", "expiry"])
            for row in rows:
                writer.writerow(row)

        print("[DEBUG] CSV written, attempting to send file...")

        
        # Send CSV to Telegram
        with open(export_path, "rb") as file:
            response = requests.post(
                API_URL + "sendDocument",
                data={"chat_id": chat_id},
                files={"document": file}
            )
        print("[DEBUG] Telegram API Response:", response.json())
        if not response.ok:
            send_message(chat_id, "❌ Failed to send CSV file.")

    except Exception as e:
        print(f"❌ Error exporting users: {e}")
        send_message(chat_id, "❌ Something went wrong during export.")

def get_user_info(username):
    cursor.execute("SELECT telegram_id, plan, expiry FROM users WHERE username = ?", (username,))
    return cursor.fetchone()

# === INTERACTIVE STATE ===
pending_action = {}
broadcast_messages = {}

# === MAIN BOT LOOP ===
def poll():
    print("✅ Bot running...")
    offset = None
    while True:
        updates = get_updates(offset)
        if "result" in updates:
            for update in updates["result"]:
                offset = update["update_id"] + 1
                handle_update(update)
        time.sleep(1)

def handle_subscribe(chat_id):
    # 1. Get email from DB
    cursor.execute("SELECT email FROM users WHERE telegram_id = ?", (chat_id,))
    row = cursor.fetchone()

    if not row or not row[0]:
        send_message(chat_id, "❗ Please set your email first using:\n`/setemail your@email.com`")
        return

    email = row[0]

    # 2. Create Stripe Checkout Session
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="subscription",
            line_items=[{
                "price": "price_1Rqz7f2fvumDIDcnXaQx7Dfl",  # 🔁 Replace with your real price ID
                "quantity": 1
            }],
            customer_email=email,
            success_url="https://t.me/Signalyxbot?start=success",
            cancel_url="https://t.me/Signalyxbot?start=cancel",
            metadata={
                "telegram_id": chat_id
            }
        )
    except Exception as e:
        send_message(chat_id, f"❌ Stripe error: {str(e)}")
        return

    # 3. Send to user
    message = """💎 *SignalyX – Launch Offer* 
Trade smarter. Grow faster. One plan. All access.
🚀 Only €89/month *(instead of €139)* 
🔓 Full VIP Access — Limited Time

✅ All Shield & Edge signals (20–35+/month)  
✅ Precise entries, SL/TP, MT5-ready  
✅ Private VIP Telegram Channel  
✅ Weekly/Monthly performance report   
✅ Smart strategy switching (conservative ↔️ aggressive)  
✅ VIP priority support

📆 Early Access offer — available until 01/10!  
🔐 Secure your access now. Limited spots available.

👇 Tap below to activate your VIP account:"""

    button = {
        "inline_keyboard": [[{
            "text": "💎 Subscribe Now – €89/month",
            "url": session.url
        }]]
    }

    requests.post(API_URL + "sendMessage", json={
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown",
        "reply_markup": button
    })


# === HANDLE MESSAGES ===
def handle_update(update):
    if "message" not in update:
        return

    message = update["message"]
    chat_id = message["chat"]["id"]
    user = message["from"]
    text = message.get("text", "").strip().lower()
    username = user.get("username", "")

    # REGISTER USER ON /start
    if text == "/start":
        cursor.execute("INSERT OR IGNORE INTO users (telegram_id, username, plan, expiry) VALUES (?, ?, ?, ?)",
                       (user["id"], username, "Free", None))
        conn.commit()
        send_message(chat_id, f"👋 Welcome, @{username} to SignalyX by JX Capital — your algorithmic edge in the markets.\n\n📡 You’re now registered on our bot. You’ll receive: \n– Access to performance reports 📊\n– Early access to premium plans 💎\n\nType /menu or /help to begin")

        send_message(chat_id, "✉️ To complete your registration, please enter your *email address* so we can link your Stripe payment.")

        pending_action[chat_id] = "collect_email"
        return

    if chat_id in pending_action and pending_action[chat_id] == "collect_email":
        email = text.strip()

        if "@" not in email or "." not in email:
            send_message(chat_id, "❌ Invalid email. Please try again.")
            return

        cursor.execute("UPDATE users SET email = ? WHERE telegram_id = ?", (email, chat_id))
        conn.commit()

        send_message(chat_id, "✅ Email saved successfully. You’re now fully registered!\n\nType /menu or /help to continue.")
        del pending_action[chat_id]
        return

    elif text == "/help":
        help_text = (
            "📖 Available Commands:\n\n"
            "👥 User Commands:\n"
            "/start – Start bot  \n"
            "/menu – Main menu  \n"
            "/setemail – Update your email address  \n"
            "/upgrade – View upgrade options  \n"
            "/plans – View available plans  \n"
            "/subscribe – Start subscription  \n"
            "/my_plan – Check your plan  \n"
            "/account – View account  \n"
            "/cancel – Cancel subscription  \n"
            "/performance – View results  \n"
            "/support – Contact support  \n"
            "/about – About SignalyX  \n"
            "/faq – Frequently Asked Questions"

        )

        if is_admin(username):
           help_text += (
                "\n\n🔐 Admin Only:\n"
                "/set_expiry – Set user's expiry  \n"
                "/export_users – Export all users  \n"
                "/check_access – Check user status  \n"
                "/add_user – Add user to VIP  \n"
                "/remove_user – Remove VIP user  \n"
                "/broadcast – Send message to all  \n"
                "/check_status – Bot usage metrics"
         )

        send_message(chat_id, help_text)
        return


    if text == "/menu":
        menu_text = """📍 <b>Main Menu</b> – What do you want to do?
📊 /performance – View recent results  
💎 /plans – Explore subscription options 
🧾 /my_plan – Check your subscription  
🔁 /renewal – Extend or upgrade  
❌ /cancel – Cancel your subscription
❓ /faq – Frequently Asked Questions  
📩 /support – Ask a question or get support
📖 /about – About SignalyX
"""
        requests.post(API_URL + "sendMessage", json={
            "chat_id": chat_id,
            "text": menu_text,
            "parse_mode": "HTML"
        })
        return

    if text in ["/upgrade", "/plans"]:
        message = """💎 *SignalyX – Launch Offer*  
Trade smarter. Grow faster. One plan. All access.  
🚀 Only €89/month *(instead of €139)*  
🔓 Full VIP Access — Limited Time  
  
✅ All Shield & Edge signals (20–35+/month)  
✅ Precise entries, SL/TP, MT5-ready  
✅ Private VIP Telegram Channel  
✅ Weekly/Monthly performance report  
✅ Smart strategy switching (conservative ↔️ aggressive)  
✅ VIP priority support  
  
📆 Early Access offer — available until 01/10!  
🔐 Secure your access now. Limited spots available.  
  
👉 To activate, type /subscribe
"""

        requests.post(API_URL + "sendMessage", json={
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown"
        })
        return

    if text == "/renewal":
        send_message(chat_id, "🔄 To extend your access, just type /subscribe again. Your new plan will begin once payment is confirmed.")
        return

    if text == "/subscribe":
        handle_subscribe(chat_id)
        return

    if text == "/performance":
        send_message(chat_id, """📊 monthly Performance – Edge Strategy

✅ Trades: 18
📈 Win Rate: 87.2%
📉 Avg Return: +9.4%
📅 Period: July 15–22
🤖 Strategy: Edge

🧠 Built by data, not emotions.""")
        return

    if text == "/support":
        send_message(chat_id, """🆘 Need help?

You can use these commands:
– /plans – View subscription options
– /performance – See trading results
– /my_plan – View your current plan
– /cancel – Cancel or pause access

💬 Still stuck? Message us anytime""")
        return

    if text == "/setemail":
        pending_action[chat_id] = "collect_email"
        send_message(chat_id, "✉️ Please send your email address:")
        return

    if text == "/about":
        send_message(chat_id, """📖 About SignalyX

SignalyX is an algorithmic trading solution developed by JX Capital, delivering data-driven signals across XAU/USD, EUR/USD and major pairs.

Why SignalyX?
✅ Built over 2 years of R&D
✅ Avg. 84.68% accuracy
✅ +292% backtested growth
✅ Trusted by numerous traders

⚙️ It doesn’t sleep. It doesn’t fear. It just executes.

Join the movement.""")
        return


    if text == "/faq":
        faq_text = """<b>✅ Frequently Asked Questions – SignalyX</b>

🔹 <b>What’s included in my subscription?</b>
Your subscription includes:
– Premium trading signals (Dual Core)  
– Professional-grade strategies  
– Live trade alerts via Telegram  
– Priority support  
– Transparent performance reports

🔹 <b>Will other users see me in the channel?</b>
No. Telegram channels are anonymous:  
– Only admins see the member list  
– Other users don’t see your name, picture, or number  
– Perfect for discreet business use

🔹 <b>I subscribed but didn’t get access – what should I do?</b>
First, try <code>/myplan</code> to sync your access.  
If the issue persists, contact us via <code>/help</code> — we’ll resolve it fast.

🔹 <b>How do I make sure I receive all signals on time?</b>
– Go to the premium channel  
– Tap its name → Notifications → Enable “All messages”  
– Make sure Telegram can notify you on your device  
📈 Signals are delivered in real time — notification settings are key.

🔹 <b>Is my payment secure?</b>
Absolutely. All payments are handled via:
– Stripe (PCI-DSS certified)  
– Apple Pay / Google Pay  
– 3D Secure verification  
We never store or see your card details. Subscriptions are encrypted and secure.

🔹 <b>Can I cancel anytime?</b>
Yes. Use <code>/cancel</code> at any moment.  
You retain full access until the end of your billing period.  
Subscriptions renew monthly unless canceled.  
All subscriptions are non-refundable once access is granted.

🔹 <b>Can I try before subscribing?</b>
Currently, there’s no free trial.  
You can join our free channel where we share sample signals.  
Our signal performance is transparently verified and accessible anytime.

🔹 <b>What are Forex Signals?</b>
Real-time trading recommendations that include:
– Instrument (e.g., XAUUSD, EURUSD)  
– Trade direction (Buy/Sell)  
– Entry price, SL, and TP  
– Risk management guidance  
Signals help traders:  
– Save time on analysis  
– Execute high-probability trades  
– Leverage professional strategies  
SignalyX is powered by high-performance trading algorithms for precision and consistency.

🔹 <b>How does it work?</b>
1. Subscribe to a plan  
2. Join our private Telegram channel  
3. Receive real-time signals including:  
– Asset (e.g., XAUUSD, GBPUSD)  
– Direction (Buy/Sell)  
– Entry zone  
– SL/TP  
– Strategic notes or confidence level  
Generated by an advanced algorithm using:  
– Technical models  
– Momentum breakout patterns  
– Volatility filters  
– Risk optimization  
You execute trades at your discretion via your broker.

🔹 <b>Are your results verified?</b>
Yes. Our results are tracked and authenticated on:
– MyFXBook  
– MQL5  
Links are shared in this bot and in the VIP channel description.

🔹 <b>Need help for another subject?</b>
Type <code>/help</code> to contact us directly  
Or email:  contact@signalyx.io  
We respond within a few hours on business days.
"""
        requests.post(API_URL + "sendMessage", json={
            "chat_id": chat_id,
            "text": faq_text,
            "parse_mode": "HTML"
        })
        return


    if text.startswith("/start success"):
        send_message(chat_id, "🎉 Payment successful! You'll receive your VIP invite shortly.")

    if text.startswith("/start cancel"):
        send_message(chat_id, "❌ Payment cancelled. You can try again with /subscribe.")

    if text == "/my_plan":
        cursor.execute("SELECT plan, expiry FROM users WHERE telegram_id = ?", (chat_id,))
        row = cursor.fetchone()
        if row:
            plan, expiry = row
            if plan != "Free":
                send_message(chat_id, f"📄 Your Current Plan:\nPlan: {plan}\nAccess: ✅ Full\nExpiry: {expiry}\n\nYou're all set! 🚀")
            else:
                send_message(chat_id, "📄 Your Current Plan:\nPlan: Free\nAccess: Limited\nExpiry: ❌ No expiry (free tier)\n\nWant full access?\n🔐 Upgrade now for full-time signals and analytics. /upgrade")
        return

    if text == "/account":
        cursor.execute("SELECT plan FROM users WHERE telegram_id = ?", (chat_id,))
        plan = cursor.fetchone()[0]
        send_message(chat_id, f"👤 Account Summary\nUsername: @{username}\nCurrent Plan: {plan}\nStatus: Active\n\n💼 Manage options:\n/my_plan – Check your plan\n/upgrade - Change plan\n/cancel – Cancel plan")
        return

    if text == "/cancel":
        send_message(chat_id, "⚠️ We're sorry to see you go.\n\nBefore you cancel, remember:\n– Premium members get signals with 84.68% win rate\n– +292% strategy growth in 18 months\n– Real traders. Real returns.\n\nType /confirm_cancel to proceed, or /upgrade to stay with us.")
        return

    if text == "/confirm_cancel":
        cursor.execute("UPDATE users SET plan = ?, expiry = ? WHERE telegram_id = ?", ("Free", None, chat_id))
        conn.commit()
         
        # Remove from VIP group
        try:
            requests.post(API_URL + "/banChatMember", data={
                "chat_id": VIP_GROUP_ID,
                "user_id": chat_id
            })
            time.sleep(1)
            requests.post(API_URL + "/unbanChatMember", data={
                "chat_id": VIP_GROUP_ID,
                "user_id": chat_id
            })
        except Exception as e:
            print(f"[ERROR] Failed to remove user from group: {e}")

        send_message(chat_id, "❌ You have been downgraded to Free Plan. VIP access revoked.")
        return

    # === ADMIN COMMANDS ===
    if not is_admin(username):
        return

    if text == "/check_status":
        cursor.execute("SELECT COUNT(*) FROM users")
        total = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM users WHERE plan != 'Free'")
        premium = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM users WHERE expiry IS NOT NULL AND DATE(expiry) > DATE('now') AND DATE(expiry) <= DATE('now', '+7 day')")
        expiring = cursor.fetchone()[0]
        send_message(chat_id, f"📊 Bot Status Overview\n\n👥 Total Users: {total}\n💎 Premium Users: {premium}\n⏳ Expiring Soon (7 days): {expiring}")
        return

    if text == "/check_access":
        pending_action[chat_id] = "check_access"
        send_message(chat_id, "🔍 Send @username to check:")
        return

    if text == "/add_user":
        pending_action[chat_id] = "add_user"
        send_message(chat_id, "➕ Send @username to add:")
        return

    if text == "/remove_user":
        pending_action[chat_id] = "remove_user"
        send_message(chat_id, "🗑️ Send @username to remove:")
        return

    if text == "/set_expiry":
        pending_action[chat_id] = "set_expiry_user"
        send_message(chat_id, "📆 Send @username to set expiry:")
        return
    
    if text == "/export_users":
        print("[DEBUG] /export_users command triggered")
        if not is_admin(username):
            send_message(chat_id, "⛔ You are not authorized to use this command.")
        else:
            export_users(chat_id)
        return


    if text == "/broadcast":
        pending_action[chat_id] = "broadcast"
        send_message(chat_id, "📣 Send message to broadcast:")
        return

    # === HANDLE PENDING ACTIONS ===
    if chat_id in pending_action:
        action = pending_action.pop(chat_id)
        if action == "check_access":
            username = text.lstrip("@")
            user = get_user_info(username)
            if user:
                _, plan, expiry = user
                send_message(chat_id, f"Plan: {plan}\nAccess: ✅ Active\nExpiry: {expiry}\nStatus: Premium")
            else:
                send_message(chat_id, "❌ User not found.")
        elif action == "add_user":
             username = text.lstrip("@")
             cursor.execute("SELECT telegram_id FROM users WHERE username = ?", (username,))
             row = cursor.fetchone()

             if row:
                 telegram_id = row[0]
                 expiry_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")

                 # Update user to VIP
                 cursor.execute("UPDATE users SET plan = ?, expiry = ? WHERE telegram_id = ?", ("Edge", expiry_date, telegram_id))
                 conn.commit()

                 # Create a one-time, 30-minute invite link
                 expire_time = int(time.time()) + 1800  # 30 mins from now
                 payload = {
                     "chat_id": VIP_GROUP_ID,              # Make sure this is defined globally
                     "member_limit": 1,
                     "expire_date": expire_time
                 }
                 r = requests.post(API_URL + "createChatInviteLink", json=payload)
                 result = r.json()

                 if result.get("ok"):
                    invite_link = result["result"]["invite_link"]
                    send_message(telegram_id, f"✅ You’ve been granted full VIP access!\n\n🔗 Here is your private group link (valid 30 mins, single use):\n{invite_link}")
                    send_message(chat_id, f"✅ @{username} has been added with VIP access.\nDefault expiry: {expiry_date}")
                 else:
                    send_message(chat_id, f"⚠️ Failed to generate group link.\nError: {result.get('description')}")
             else:
                 send_message(chat_id, "❌ User not found. Ask them to run /start first.")

        elif action == "remove_user":
             username = text.lstrip("@")
             cursor.execute("SELECT telegram_id FROM users WHERE username = ?", (username,))
             row = cursor.fetchone()

             if row:
                 telegram_id = row[0]

                 # Remove user from database
                 cursor.execute("DELETE FROM users WHERE telegram_id = ?", (telegram_id,))
                 conn.commit()

                 # Kick user from group (ban then unban)
                 kick_payload = {
                     "chat_id": VIP_GROUP_ID,
                     "user_id": telegram_id
                 }
                 unban_payload = {
                      "chat_id": VIP_GROUP_ID,
                      "user_id": telegram_id
                 }

                 # Ban (kick)
                 requests.post(API_URL + "banChatMember", json=kick_payload)
                 time.sleep(1)  # wait a moment
                 # Unban to allow future joining
                 requests.post(API_URL + "unbanChatMember", json=unban_payload)

                 send_message(telegram_id, "❌ Your VIP access has been revoked.\nYou’ve been removed from the group.")
                 send_message(chat_id, f"✅ @{username} has been removed from premium access and kicked from the VIP group.")
             else:
                 send_message(chat_id, "❌ User not found in database.")

        elif action == "set_expiry_user":
            pending_action[chat_id] = f"set_expiry_date:{text.lstrip('@')}"
            send_message(chat_id, "📅 Send expiry date in YYYY-MM-DD:")
        elif action.startswith("set_expiry_date:"):
            username = action.split(":")[1]
            expiry = text.strip()
            try:
                datetime.strptime(expiry, "%Y-%m-%d")
                cursor.execute("UPDATE users SET expiry = ? WHERE username = ?", (expiry, username))
                conn.commit()
                send_message(chat_id, f"✅ Access expiry date updated for @{username}\n🔒 Expires on: {expiry}")
            except:
                send_message(chat_id, "❌ Invalid date format. Use YYYY-MM-DD.")

        elif action == "broadcast":
            message = text.strip()
            cursor.execute("SELECT telegram_id FROM users")
            for row in cursor.fetchall():
                try:
                    send_message(row[0], message)
                except:
                    pass
            send_message(chat_id, "📤 Message broadcasted to all users.")
        return

    send_message(chat_id, "❓ Unknown command. Use /help to see available options.")

# === START POLLING ===
if __name__ == "__main__":
    poll()
