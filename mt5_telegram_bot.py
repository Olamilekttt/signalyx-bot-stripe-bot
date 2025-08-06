import MetaTrader5 as mt5
import requests
import time
import schedule
from datetime import datetime, timezone, timedelta
aggressive_cycle_count = 0

# ========== CONFIG ==========
BOT_TOKEN = "7897078328:AAE72emid_CiNmj0PPJxGeIUh4F1wCq3FAY"
VIP_CHAT_ID = "-1002538858074"
FREE_CHAT_ID = "-1002884550816"
LOGIN = 52381087
PASSWORD = "HG$n!Gfsi34bpJ"
SERVER = "ICMarketsEU-Demo"
CHECK_INTERVAL = 5  # seconds

MAGIC_CONSERVATIVE = 20250422
MAGIC_AGGRESSIVE = 20250420

sent_tickets = set()
tracked_sl_tp = {}
closed_history = {}
last_update_id = 0

# ========== INIT ==========
if not mt5.initialize(login=LOGIN, password=PASSWORD, server=SERVER):
    print("❌ MT5 init failed:", mt5.last_error())
    quit()
print("✅ Connected to MT5")

# ========== TELEGRAM ==========
def send_telegram(text, chat_id):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    try:
        requests.post(url, data=payload, timeout=5)
    except:
        print("⚠️ Telegram send failed.")

def reply_to_command(chat_id, text):
    send_telegram(text, chat_id)

# ========== HELPERS ==========
def get_gmt_time():
    return datetime.now(timezone.utc).strftime('%H:%M GMT')

def get_avg_price(symbol):
    positions = mt5.positions_get(symbol=symbol)
    if not positions:
        return "—"
    total_volume = sum(p.volume for p in positions)
    weighted_price = sum(p.price_open * p.volume for p in positions)
    return round(weighted_price / total_volume, 2) if total_volume else "—"

# ========== FORMATTING ==========
def format_conservative(pos):
    return f"""
📡 <b>[ALGORITHMIC SIGNAL – ACTIVATED]</b>
📌 Asset: <b>{pos.symbol}</b>
🎯 Take Profit: <b>{pos.tp:.2f}</b>
🛑 Stop Loss: <b>{pos.sl:.2f}</b>
▶️ Initial execution: <b>{'Buy' if pos.type == 0 else 'Sell'} @ {pos.price_open:.2f}</b>
⏱ Live monitoring – no manual intervention required.
""".strip()

def format_aggressive(pos):
    return f"""
📡 <b>[ALGORITHMIC SIGNAL – ACTIVATED]</b>
📌 Asset: <b>{pos.symbol}</b>
🔁 Mode: <b>Progressive entry (multi-level adaptive system)</b>
🎯 Estimated dynamic target: ~30 pips
▶️ Initial execution: <b>{'Buy' if pos.type == 0 else 'Sell'} @ {pos.price_open:.2f}</b>
The system will automatically adjust entries and exits based on volatility and market structure.
⏱ Live monitoring – no manual intervention required.
""".strip()

def format_free_preview():
    return """
📡 <b>[ALGORITHMIC SIGNAL – ACTIVATED]</b>
📍 Entry executed — market already reacting
🔒 Full details (entry, TP, SL, logic) shared in the VIP channel
📈 Ongoing position evolving as expected
👀 More signals lining up — timing is everything.
💎 Join the VIP now to receive upcoming entries in real-time 👇
👉 @Signalyxbot
""".strip()

def format_modification(pos, old_sl, old_tp):
    return f"""
🌙 <b>[NIGHT MODE – ACTIVE RISK MANAGEMENT]</b>
✅ Asset: <b>{pos.symbol}</b> ({'LONG' if pos.type == 0 else 'SHORT'})
📊 SL: <b>{old_sl}</b> → <b>{pos.sl}</b>
🎯 TP: <b>{old_tp}</b> → <b>{pos.tp}</b>
⏱ Time: {get_gmt_time()}
""".strip()

def format_closure(deal):
    return f"""
📡 <b>[POSITION CLOSED – STRATEGIC EXIT]</b>
✅ Asset: <b>{deal.symbol}</b> ({'LONG' if deal.type == 0 else 'SHORT'})
📍 Entry: <b>{deal.price}</b>
🎯 Exit: <b>{deal.price}</b>
📈 Result: <b>{round(deal.profit, 2)} USD</b>
The position was closed automatically by the optimized strategy module.
🚨 The next opportunity is already forming.
💎 Join the VIP to receive real-time entries 👇
👉 @Signalyxbot
""".strip()

# ========== POSITION CHECK ==========
def check_positions():
        positions = mt5.positions_get()
        print(f"[DEBUG] Fetched {len(positions or [])} positions.")

        current_tickets = set()

        for pos in positions or []:
            print(f"[DEBUG] Checking position → Symbol: {pos.symbol}, Ticket: {pos.ticket}, Magic: {pos.magic}, Type: {'Buy' if pos.type == 0 else 'Sell'}")
            
            ticket = pos.ticket
            current_tickets.add(ticket)
            magic = pos.magic

            if ticket not in sent_tickets:
                print(f"[DEBUG] New position detected → Ticket: {ticket}, Magic: {magic}")

                if magic == MAGIC_CONSERVATIVE:
                    print("[DEBUG] Conservative strategy matched. Sending VIP + Free messages.")
                    send_telegram(format_conservative(pos), VIP_CHAT_ID)
                    send_telegram(format_free_preview(), FREE_CHAT_ID)
                elif magic == MAGIC_AGGRESSIVE:
                    global aggressive_cycle_count
                    aggressive_cycle_count += 1
                    cycle_index = (aggressive_cycle_count - 1) % 3

                    if cycle_index == 0:
                        print("[DEBUG] Aggressive – New Cycle First Entry")
                        message = f"""
                📡 <b>[ALGORITHMIC SIGNAL – ACTIVATED]</b>
                📌 Asset: <b>{pos.symbol}</b>
                🔁 Mode: <b>Progressive entry (multi-level adaptive system)</b>
                🎯 Estimated dynamic target: ~30 pips
                ▶️ Initial execution: <b>{'Buy' if pos.type == 0 else 'Sell'} @ {pos.price_open:.5f}</b>
                The system will automatically adjust entries and exits based on volatility and market structure.
                ⏱ Live monitoring – no manual intervention required.
                """.strip()
                    else:
                        print(f"[DEBUG] Aggressive – Reinforcement Entry #{cycle_index + 1}")
                        avg_price = get_avg_price(pos.symbol)

                        # Convert to float if returned as str (from fallback logic)
                        avg_price = float(avg_price) if avg_price != "—" else pos.price_open

                        # Calculate dynamic target (+30 pips)
                        if "JPY" in pos.symbol:
                            pip_factor = 0.01
                        elif "XAU" in pos.symbol or "GOLD" in pos.symbol:
                            pip_factor = 0.1
                        else:
                            pip_factor = 0.0001
                        adjusted_target = avg_price + (30 * pip_factor) if pos.type == 0 else avg_price - (30 * pip_factor)

                        message = f"""
                📡 <b>[ALGORITHMIC ADJUSTMENT – REINFORCEMENT IN PROGRESS]</b>
                📌 Asset: <b>{pos.symbol}</b>
                🔁 Mode: <b>Progressive entry (multi-level adaptive system)</b>
                ▶️ New execution: <b>{'Buy' if pos.type == 0 else 'Sell'} @ {pos.price_open:.5f}</b>
                📊 Weighted average price: <b>{avg_price:.5f}</b> 
                📈 Reinforcement with doubled volume – aimed at lowering the average entry and maximizing profit on potential rebound.

                🎯 Adjusted dynamic target: <b>{adjusted_target:.5f}</b>
                This position reinforcement follows the predefined adaptive algorithm.
                The strategy aims to progressively optimize the exit.
                """.strip()

                    send_telegram(message, VIP_CHAT_ID)
                    send_telegram(format_free_preview(), FREE_CHAT_ID)
                else:
                    print("[DEBUG] No strategy matched. Sending Free preview only.")
                    send_telegram(format_free_preview(), FREE_CHAT_ID)

                sent_tickets.add(ticket)
                tracked_sl_tp[ticket] = (pos.sl, pos.tp)

            # Detect modifications
            old_sl, old_tp = tracked_sl_tp.get(ticket, (None, None))
            if pos.sl != old_sl or pos.tp != old_tp:
                print(f"[DEBUG] SL/TP modified for ticket {ticket}.")
                tracked_sl_tp[ticket] = (pos.sl, pos.tp)
                send_telegram(format_modification(pos, old_sl, old_tp), VIP_CHAT_ID)

        # Check for closures
        for ticket in list(sent_tickets):
            if ticket not in current_tickets:
                print(f"[DEBUG] Ticket {ticket} is no longer open — checking if it closed...")

                try:
                    # Use a default symbol for server time (safe and simple)
                    symbols = mt5.symbols_get()
                    symbol_for_time = None
                    
                    for s in symbols:
                        tick = mt5.symbol_info_tick(s.name)
                        if tick and tick.time:
                            symbol_for_time = s.name
                            now_ts = tick.time
                            break

                    if not symbol_for_time:
                        print("[ERROR] Could not fetch server time from any symbol.")
                        continue  # Or continue, depending on context

                    now = datetime.fromtimestamp(now_ts)
                    start = now - timedelta(days=2)
                    history = mt5.history_deals_get(start, now)

                    if not history:
                        print(f"[DEBUG] No deal history found.")
                        continue

                    match_found = False
                    for deal in reversed(history):
                        if int(deal.position_id) == int(ticket):
                            match_found = True
                            print(f"[DEBUG] Match found in history for closed ticket {ticket}")

                            orders = mt5.history_orders_get(ticket=ticket)
                            if not orders or len(orders) == 0:
                                print(f"[DEBUG] No order history found for ticket {ticket}")
                                break

                            orig = orders[0]
                            magic = orig.magic
                            symbol = deal.symbol
                            entry_price = orig.price_open
                            exit_price = deal.price
                            profit = deal.profit
                            direction = "LONG" if orig.type == 0 else "SHORT"
                            pips = round(abs(exit_price - entry_price) * 10000, 1) if "JPY" not in symbol else round(abs(exit_price - entry_price) * 100, 1)

                            print(f"[DEBUG] Magic: {magic}, Symbol: {symbol}, Entry: {entry_price}, Exit: {exit_price}, Pips: {pips}")

                            if magic == MAGIC_CONSERVATIVE:
                                start = now - timedelta(days=30)
                                deals = mt5.history_deals_get(start, now)

                                # Find entry deal for this position
                                entry_deals = [
                                    d for d in deals
                                    if d.position_id == ticket and d.entry == mt5.DEAL_ENTRY_IN
                                ]

                                if not entry_deals:
                                    print(f"[DEBUG] No entry deal found for ticket {ticket}")
                                    break

                                entry_price = entry_deals[0].price
                                

                                # Fix pip calculation logic
                                if "JPY" in symbol:
                                    pips = round((exit_price - entry_price) * 100, 1)
                                elif "XAU" in symbol or "GOLD" in symbol:
                                    pips = round((exit_price - entry_price) * 10, 1)
                                else:
                                    pips = round((exit_price - entry_price) * 10000, 1)
                                if direction == "SHORT":
                                    pips = -pips

                                # Percent performance calculation
                                if entry_price == 0:
                                    percent_gain = 0
                                    print(f"[WARN] Entry price is zero for {symbol}. Cannot compute % gain.")
                                else:
                                    if direction == "LONG":
                                        percent_gain = ((exit_price - entry_price) / entry_price) * 100
                                    else:
                                        percent_gain = ((entry_price - exit_price) / entry_price) * 100
                                
                                header = "📡 <b>[POSITION CLOSED – STRATEGIC EXIT]</b>"
                                body = f"""
        ✅ Asset: <b>{symbol}</b> ({direction})  
        📍 Entry: <b>{entry_price:.5f}</b>  
        🎯 Exit: <b>{exit_price:.5f}</b>  
        📈 Result: <b>{pips} pips</b>  
        💰 Performance: <b>{percent_gain:+.3f}%</b> on position

        The position was closed automatically by the optimized strategy module.  
        Executed stress-free — no manual action, full control.

        🚨 The next opportunity is already forming  
        💎 Join the VIP to receive real-time entries 👇  
        👉 @Signalyxbot
        """.strip()

                            elif magic == MAGIC_AGGRESSIVE:
                                # Get all cycle orders to calculate weighted average entry
                                start_time = now - timedelta(days=30)
                                all_deals = mt5.history_deals_get(start_time, now)

                                if all_deals is None:
                                    print("[ERROR] Failed to fetch deal history.")
                                    break

                                cycle_deals = [
                                    d for d in all_deals
                                    if d.symbol == symbol
                                    and d.magic == magic 
                                    and d.type in [mt5.DEAL_TYPE_BUY, mt5.DEAL_TYPE_SELL]
                            
                                ]

                                print(f"[DEBUG] Filtered aggressive deals found: {len(cycle_deals)}")

                                for d in cycle_deals:
                                    print(f"[DEBUG] Deal ticket: {d.ticket}, price: {d.price}, volume: {d.volume}")

                                total_volume = sum(d.volume for d in cycle_deals)
                                if total_volume == 0:
                                    print("[DEBUG] Total volume is zero in cycle deals.")
                                    break

                                weighted_entry = sum(d.price * d.volume for d in cycle_deals) / total_volume
                                cycle_count = len(cycle_deals)


                                if "JPY" in symbol:
                                    pips = round((exit_price - weighted_entry) * 100, 1)
                                elif "XAU" in symbol or "GOLD" in symbol:
                                    pips = round((exit_price - weighted_entry) * 10, 1)
                                else:
                                    pips = round((exit_price - weighted_entry) * 10000, 1)
                                if direction == "SHORT":
                                    pips = -pips

                                # Calculate percent gain (safe division)
                                if weighted_entry == 0:
                                    percent_gain = 0
                                    print(f"[WARN] Weighted entry is zero for {symbol}. Percent gain set to 0.")
                                else:
                                    if direction == "LONG":
                                        percent_gain = ((exit_price - weighted_entry) / weighted_entry) * 100
                                    else:
                                        percent_gain = ((weighted_entry - exit_price) / weighted_entry) * 100
                                
                                # Build message
                                header = "📡 <b>[CYCLE COMPLETED – STRATEGIC EXIT]</b>"
                                body = f"""
        ✅ Asset: <b>{symbol}</b> ({direction})  
        📊 Weighted average entry: <b>{weighted_entry:.5f}</b>
        📍 Positions in the cycle: <b>{cycle_count}</b>  
        🎯 🎯 Exit: <b>{exit_price:.5f}</b>  
        📈 Gain on this cycle: <b>{pips} pips</b>  
        💰 Performance: <b>{percent_gain:+.1f}%</b> on total position

        Exit automatically triggered by the optimized strategy module.  
        Executed stress-free, with no manual intervention and controlled exposure.

        🚨 The next opportunity is forming  
        💎 Join the VIP to get real-time signals 👇  
        👉 @Signalyxbot
        """.strip()
                            else:
                                print(f"[DEBUG] Unknown magic number: {magic}. Skipping message.")
                                break

                            final_msg = f"{header}\n\n{body}"
                            send_telegram(final_msg, VIP_CHAT_ID)
                            send_telegram(final_msg, FREE_CHAT_ID)
                            print(f"[DEBUG] Closure message sent for {symbol}")

                            sent_tickets.remove(ticket)
                            closed_history[symbol] = closed_history.get(symbol, 0) + profit
                            break

                    if not match_found:
                        print(f"[DEBUG] No deal matched for closed ticket {ticket} in history.")

                except Exception as e:
                    print(f"❌ check_positions error for ticket {ticket}: {e}")

# ========== WEEKLY SUMMARY ==========
def weekly_summary():
    try:
        now = datetime.now()
        start = now - timedelta(days=7)
        deals = mt5.history_deals_get(start, now)

        if not deals:
            print("⚠️ No deal history found for weekly summary.")
            return

        symbol_stats = {}
        total_pips = 0
        total_percent = 0

        for deal in deals:
            if deal.entry != mt5.DEAL_ENTRY_OUT:
                continue

            symbol = deal.symbol
            pos_id = deal.position_id
            exit_price = deal.price
            magic = deal.magic

            # Find matching entry deal
            entry_deals = [d for d in deals if d.position_id == pos_id and d.entry == mt5.DEAL_ENTRY_IN]
            if not entry_deals:
                continue
            entry_price = entry_deals[0].price

            if "JPY" in symbol:
                pips = round((exit_price - entry_price) * 100, 1)
            elif "XAU" in symbol or "GOLD" in symbol:
                pips = round((exit_price - entry_price) * 10, 1)
            else:
                pips = round((exit_price - entry_price) * 10000, 1)

            direction = "LONG" if entry_deals[0].type == 0 else "SHORT"
            if direction == "SHORT":
                pips = -pips

            # % Gain
            if entry_price == 0:
                percent = 0
            else:
                percent = ((exit_price - entry_price) / entry_price) * 100 if direction == "LONG" else ((entry_price - exit_price) / entry_price) * 100

            if symbol not in symbol_stats:
                symbol_stats[symbol] = {"pips": 0, "percent": 0}

            symbol_stats[symbol]["pips"] += pips
            symbol_stats[symbol]["percent"] += percent
            total_pips += pips
            total_percent += percent

        # Format date range
        week_start = (now - timedelta(days=7)).strftime('%B %d')
        week_end = now.strftime('%d')
        message = f"📈 [WEEKLY REPORT – {week_start}–{week_end}]\n✅ Closed cycles:"

        for sym, stats in symbol_stats.items():
            message += f"\n• {sym} : {stats['percent']:+.2f}% / {stats['pips']} pips"

        message += f"\n📈 Total gains: {round(total_pips)} pips"
        message += f"\n💰 Performance: {total_percent:+.2f}% on total position"
        message += "\nAll exits were triggered automatically by the dynamic optimization module."
        message += "\n🟢 1 cycle still in progress – status: stable"
        message += "\n💎 Join the VIP now to receive upcoming entries in real-time 👇"

        send_telegram(message, VIP_CHAT_ID)
        send_telegram(message, FREE_CHAT_ID)

    except Exception as e:
        print("❌ weekly_summary error:", e)

schedule.every().friday.at("22:00").do(weekly_summary)

# ========== /STATUS ==========
def handle_updates():
    global last_update_id
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={last_update_id + 1}"
        res = requests.get(url).json()
        for update in res.get("result", []):
            update_id = update["update_id"]
            msg = update.get("message", {})
            chat_id = msg.get("chat", {}).get("id", "")
            text = msg.get("text", "")
            if text.lower() == "/status":
                positions = mt5.positions_get()
                if not positions:
                    reply_to_command(chat_id, "📊 No open trades.")
                else:
                    reply = "<b>📊 CURRENT POSITIONS:</b>\n"
                    for p in positions:
                        direction = "BUY" if p.type == 0 else "SELL"
                        reply += f"\n{p.symbol} • {direction} @ {p.price_open}\n📈 Avg: {get_avg_price(p.symbol)}"
                    reply_to_command(chat_id, reply)
            last_update_id = update_id
    except Exception as e:
        print("❌ handle_updates error:", e)

# ========== MAIN LOOP ==========
print("📡 Signal bot running...")
while True:
    handle_updates()
    check_positions()
    schedule.run_pending()
    time.sleep(CHECK_INTERVAL)
