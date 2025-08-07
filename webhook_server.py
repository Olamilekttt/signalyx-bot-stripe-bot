import os
import stripe
import sqlite3
from flask import Flask, request, jsonify
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

# === LOAD ENV VARS ===
load_dotenv()

# === CONFIG ===
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
endpoint_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
BOT_TOKEN = os.getenv("BOT_TOKEN")
VIP_GROUP_ID = os.getenv("VIP_GROUP_ID")
DB_PATH = "subscriptions.db"
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

app = Flask(__name__)

# === DB UTIL ===
def find_user_by_email(email):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT telegram_id, expiry FROM users WHERE email = ?", (email,))
    result = cursor.fetchone()
    conn.close()
    return result if result else (None, None)

def set_plan(telegram_id, plan, expiry):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET plan = ?, expiry = ?, status = ? WHERE telegram_id = ?", (plan, expiry, "active", telegram_id))
    conn.commit()
    conn.close()

def extend_user_vip(telegram_id, days=30):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Get current expiry
        cursor.execute("SELECT expiry FROM users WHERE telegram_id = ?", (telegram_id,))
        result = cursor.fetchone()

        if result:
            current_expiry_str = result[0]

            # Convert string to datetime object
            current_expiry = datetime.strptime(current_expiry_str, "%Y-%m-%d")

            # If expired, start from today
            today = datetime.now()
            base_date = max(current_expiry, today)

            # Add days
            new_expiry = base_date + timedelta(days=days)
            new_expiry_str = new_expiry.strftime("%Y-%m-%d")

            # Update DB
            cursor.execute("UPDATE users SET expiry = ? WHERE telegram_id = ?", (new_expiry_str, telegram_id))
            conn.commit()

            print(f"✅ VIP access extended for user {telegram_id} until {new_expiry_str}")
        else:
            print(f"⚠️ No user found with telegram_id: {telegram_id}")
    except Exception as e:
        print("❌ Error extending user:", e)
    finally:
        conn.close()

def downgrade_user(telegram_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET plan = ?, expiry = ?, status = ? WHERE telegram_id = ?", ("Free", None, "expired", telegram_id))
    conn.commit()
    conn.close()

    send_message(telegram_id, "⚠️ Your subscription has ended.\nYou’ve been moved to the Free plan.\n\nTo restore VIP access, subscribe again:\n/upgrade")

# === TELEGRAM ACTIONS ===
def send_message(chat_id, text):
    requests.post(f"{API_URL}/sendMessage", json={
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    })

def send_invite_link(telegram_id, expiry):
    expire_time = int((datetime.now() + timedelta(minutes=30)).timestamp())
    payload = {
        "chat_id": VIP_GROUP_ID,
        "expire_date": expire_time,
        "member_limit": 1
    }

    r = requests.post(f"{API_URL}/createChatInviteLink", json=payload)
    res = r.json()

    if res.get("ok"):
        invite = res["result"]["invite_link"]
        send_message(telegram_id, f"🎉 Payment received! You've been upgraded to VIP until *{expiry}*.\n\n🔗 Your private group link (valid 30 min):\n{invite}")
    else:
        send_message(telegram_id, "✅ Payment received, but failed to generate group link. Contact support.")

# === STRIPE WEBHOOK HANDLER ===
@app.route("/webhook", methods=["POST"])
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except stripe.error.SignatureVerificationError:
        return jsonify({"error": "Invalid signature"}), 400

    event_type = event["type"]

    if event_type == "checkout.session.completed":
        session = event["data"]["object"]
        telegram_id = session["metadata"].get("telegram_id")
        email = session.get("customer_email")

        if telegram_id:
            expiry = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
            set_plan(telegram_id, "VIP", expiry)
            send_invite_link(telegram_id, expiry)
        return jsonify({"status": "ok"}), 200

    elif event_type in ["customer.subscription.deleted", "customer.subscription.cancelled"]:
        session = event["data"]["object"]
        customer_id = session.get("customer")
        if customer_id:
            customer = stripe.Customer.retrieve(customer_id)
            email = customer.get("email")
            if email:
                telegram_id, _ = find_user_by_email(email)
                if telegram_id:
                    downgrade_user(telegram_id)
    
    elif event_type == "customer.subscription.updated":
        print("Got updated event")
        session = event["data"]["object"]
        if session.get("cancel_at_period_end"):
            customer_id = session.get("customer")
            if customer_id:
                customer = stripe.Customer.retrieve(customer_id)
                email = customer.get("email")
                current_period_end = datetime.fromtimestamp(session["current_period_end"]).strftime('%Y-%m-%d')
                if email:
                    telegram_id, _ = find_user_by_email(email)
                    if telegram_id:
                        # Optional: mark them as 'cancelled', or notify them
                        send_message(telegram_id, f"⚠️ Your subscription will end on *{current_period_end}*.\nYou’ll be moved to Free tier then.")
    
    elif event_type == "invoice.paid":
        session = event["data"]["object"]
        customer_id = session.get("customer")

        if customer_id:
            customer = stripe.Customer.retrieve(customer_id)
            email = customer.get("email")

            if email:
                telegram_id, _ = find_user_by_email(email)

                if telegram_id:
                    # Extend their expiry by 30 days (or your logic)
                    extend_user_vip(telegram_id, days=30)
                    send_message(
                        telegram_id,
                        "🔁 Your subscription has renewed!\nYour VIP access has been extended by 30 days."

                    )
                    

    elif event_type == "invoice.payment_failed":
        session = event["data"]["object"]
        email = session.get("customer_email")
        if email:
            telegram_id, _ = find_user_by_email(email)
            if telegram_id:
                send_message(telegram_id, "⚠️ Payment failed!\nPlease update your card to avoid losing VIP access.")

    return jsonify({"status": "ok"}), 200

@app.route("/")
def health():
    return "Webhook server running", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
