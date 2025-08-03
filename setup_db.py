import sqlite3

conn = sqlite3.connect("subscriptions.db")
cursor = conn.cursor()

# Create users table
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    telegram_id TEXT PRIMARY KEY,
    email TEXT UNIQUE,
    plan TEXT,
    expiry TEXT,
    status TEXT
)
""")

conn.commit()
conn.close()

print("✅ Database initialized with 'users' table.")
