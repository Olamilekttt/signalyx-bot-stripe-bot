# 💼 SignalyX Telegram Bot System

This system automates MT5 signal delivery and subscription management via Telegram and Stripe. It includes a full admin panel via Telegram, auto Stripe webhook integration, and VIP access management.

---

## 📁 Project Structure

| File                  | Purpose                                                                 |
|-----------------------|-------------------------------------------------------------------------|
| `subscription_bot.py` | Core bot logic: handles plans, payments, expiry, and admin commands     |
| `mt5_telegram_bot.py` | Detects and sends MT5 signals to VIP users                              |
| `webhook_server.py`   | Stripe webhook listener (hosted via Render)                             |
| `setup_db.py`         | Optional: Initializes `users.db` database if not created yet            |
| `requirements.txt`    | Required Python packages                                                 |
| `.env.example`        | Example environment variables (copy and rename to `.env`)               |

---

## ⚙️ Setup Instructions

### 1. Install Dependencies

Ensure Python is installed. Then run:

```bash
pip install -r requirements.txt


2. Create a .env File
Create a .env file in the project root with the following values:

env
Copy
Edit
BOT_TOKEN=your_telegram_bot_token
VIP_GROUP_ID=-100xxxxxxxxxx
VIP_GROUP_LINK=https://t.me/+xxxxxxxxxxx
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
You can copy .env.example and rename it to .env



3. Run the Bots
Start the subscription bot:

bash
Copy
Edit
python subscription_bot.py
Start the MT5 signal bot (after opening MT5 terminal):

bash
Copy
Edit
python mt5_telegram_bot.py
🌐 Stripe Webhook Deployment
Deploy webhook_server.py to Render or any Flask-compatible server.

Configure Stripe to send checkout.session.completed events to:

arduino
Copy
Edit
https://your-app.onrender.com
Add the webhook secret (e.g. whsec_xxxx) to your .env file.

🧠 Admin Commands (Telegram)
Command	Description
/add_user @user	Give user VIP access (30 days by default)
/remove_user @user	Remove user from DB and VIP group
/set_expiry @user	Set custom expiry date
/check_access	Check a user’s plan, expiry and status
/export_users	Export all users to CSV
/broadcast	Broadcast message to all users
/check_status	Show stats: total, active, VIP, expired

⚠️ Only admin usernames listed in the script can use these commands.

🖥 VPS Auto Start Setup (Windows)
Use Task Scheduler to auto-start bots:

Create a task named SignalyX Subscription Bot

Trigger: At system startup

Action: Start python

Arguments: C:\full\path\to\subscription_bot.py

Start in: C:\full\path\to\your\project

Create a second task for mt5_telegram_bot.py

Ensure Python and your scripts are fully installed on the VPS.

🧾 Stripe Integration Notes
When a user pays through Stripe:

A checkout session is created

The webhook is triggered

The Telegram ID is extracted and user gets added to the DB

If user had used /start, they get sent the VIP group invite

🛠 Troubleshooting
Ensure .env is correctly set and not pushed to GitHub

Bot must be running continuously (use VPS or server)

Telegram usernames must be valid and active

MT5 must be open for signal detection to work

📜 License & Ownership
This bot system is built exclusively for SignalyX. Ownership, updates, and management rights belong to the SignalyX team. 