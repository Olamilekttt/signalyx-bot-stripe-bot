import os
import stripe
import sqlite3
from flask import Flask, request, jsonify
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv  # ✅ load from .env

# === LOAD ENV VARS ===
load_dotenv()  # Load from .env file if present

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
    cursor.execute("SELECT telegram_id FROM users WHERE email = ?", (email,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def set_plan(telegram_id, plan, expiry):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET plan = ?, expiry = ?, status = ? WHERE telegram_id = ?", (plan, expiry, "active", telegram_id))
    conn.commit()
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
print("[DEBUG] Webhook received")
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

        print(f"[DEBUG] Telegram ID from metadata: {telegram_id}")
        print(f"[DEBUG] Stripe email: {email}")

        if telegram_id:
            expiry = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
            set_plan(telegram_id, "VIP", expiry)
            send_invite_link(telegram_id, expiry)
        else:
            print("[WARN] No telegram_id found in metadata")


        # Handle other events...
        return jsonify({"status": "ok"}), 200


    elif event_type == "invoice.paid":
        session = event["data"]["object"]
        email = session["customer_email"]
        if email:
            telegram_id = find_user_by_email(email)
            if telegram_id:
                new_expiry = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
                set_plan(telegram_id, "VIP", new_expiry)
                send_message(telegram_id, f"🔁 Your subscription has renewed!\nAccess extended until *{new_expiry}*.")

    elif event_type == "customer.subscription.deleted":
        session = event["data"]["object"]
        email = session["customer_email"]
        if email:
            telegram_id = find_user_by_email(email)
            if telegram_id:
                downgrade_user(telegram_id)

    return jsonify({"status": "ok"}), 200

@app.route("/")
def health():
    return "Webhook server running", 200

if __name__ == "__main__":
    app.run(port=4242)
