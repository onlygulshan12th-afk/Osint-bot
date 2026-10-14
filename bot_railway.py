# ============================================================
#  👽 Leon v2 OSINT Bot — FINAL
#  Bot: @Leonv2osintbot | Admin: 8626080388 | Owner: @roushanog
# ============================================================

import re
import html
import time
import sqlite3
import asyncio
import logging
import os
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode, ChatAction
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters,
)

# ================== CONFIG ==================
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = 8626080388
BOT_LINK = "https://t.me/Leonv2osintbot"
OWNER_USERNAME = "@roushanog"
OWNER_LINK = "https://t.me/roushanog"
API_BASE = "https://infoapi.sahaditya7543.workers.dev"
DB_FILE = os.getenv("DB_FILE", "leon_osint.db").strip() or "leon_osint.db"
REQUIRED_CHANNELS = [
    {"username": "sterniterspro", "title": "Sterniters Pro", "url": "https://t.me/sterniterspro"},
]

CREDIT_START = 10
REFERRAL_REWARD = 15
REFERRAL_BONUS_NEW = 5
CREDIT_PER_LOOKUP = 1

START_TIME = time.time()

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)


# ================== FONTS ==================
def b(text):
    out = []
    for c in str(text):
        if 'A' <= c <= 'Z': out.append(chr(0x1D400 + ord(c) - 65))
        elif 'a' <= c <= 'z': out.append(chr(0x1D41A + ord(c) - 97))
        elif '0' <= c <= '9': out.append(chr(0x1D7CE + ord(c) - 48))
        else: out.append(c)
    return "".join(out)


def sc(text):
    m = {'a':'ᴀ','b':'ʙ','c':'ᴄ','d':'ᴅ','e':'ᴇ','f':'ꜰ','g':'ɢ','h':'ʜ','i':'ɪ',
         'j':'ᴊ','k':'ᴋ','l':'ʟ','m':'ᴍ','n':'ɴ','o':'ᴏ','p':'ᴘ','q':'ǫ','r':'ʀ',
         's':'ꜱ','t':'ᴛ','u':'ᴜ','v':'ᴠ','w':'ᴡ','x':'x','y':'ʏ','z':'ᴢ'}
    return "".join(m.get(c.lower(), c) for c in str(text))


def clean_value(v):
    if v is None: return None
    if isinstance(v, (int, float)): return str(v)
    if isinstance(v, bool): return "Yes" if v else "No"
    if isinstance(v, list):
        parts = []
        for item in v:
            if isinstance(item, dict):
                if "value" in item:
                    val = str(item["value"]).strip()
                    if val and val.lower() not in ("none", "null", ""):
                        parts.append(val)
                elif "name" in item:
                    parts.append(str(item["name"]).strip())
                else:
                    cv = clean_value(item)
                    if cv: parts.append(cv)
            elif isinstance(item, (str, int, float)):
                val = str(item).strip()
                if val and val.lower() not in ("none", "null"):
                    parts.append(val)
        seen = set()
        unique = []
        for p in parts:
            if p and p not in seen:
                seen.add(p)
                unique.append(p)
        return ", ".join(unique) if unique else None
    if isinstance(v, dict):
        parts = []
        for kk, vv in v.items():
            cv = clean_value(vv)
            if cv: parts.append(f"{kk}: {cv}")
        return ", ".join(parts) if parts else None
    s = str(v).strip()
    if not s or s.lower() in ("null", "none"): return None
    s = s.rstrip(",.;: ")
    s = re.sub(r"\s+", " ", s)
    return s


def H(value):
    if value is None: return "—"
    s = str(value).strip()
    if not s or s.lower() in ("null", "none"): return "—"
    s = html.escape(s, quote=False)
    return s.replace("<", "‹").replace(">", "›")[:400]


def H_code(value):
    if value is None: return "—"
    s = str(value).strip()
    if not s or s.lower() in ("null", "none"): return "—"
    s = s.replace("<", "").replace(">", "").replace("&", "and")
    return html.escape(s, quote=False)[:120]


# ================== ANIMATION ==================
LOADING_BARS = [
    "▱▱▱▱▱▱▱▱▱▱", "▰▱▱▱▱▱▱▱▱▱", "▰▰▱▱▱▱▱▱▱▱",
    "▰▰▰▱▱▱▱▱▱▱", "▰▰▰▰▱▱▱▱▱▱", "▰▰▰▰▰▱▱▱▱▱",
    "▰▰▰▰▰▰▱▱▱▱", "▰▰▰▰▰▰▰▱▱▱", "▰▰▰▰▰▰▰▰▱▱",
    "▰▰▰▰▰▰▰▰▰▱", "▰▰▰▰▰▰▰▰▰▰",
]

def progress_bar(pct):
    return LOADING_BARS[min(int(pct / 10), 10)]


# ================== DATABASE ==================
def db_init():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
        credits INTEGER DEFAULT 0, referred_by INTEGER,
        referral_count INTEGER DEFAULT 0, total_lookups INTEGER DEFAULT 0,
        joined_at INTEGER, last_seen INTEGER)""")
    c.execute("""CREATE TABLE IF NOT EXISTS channels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE, title TEXT, added_at INTEGER)""")
    c.execute("""CREATE TABLE IF NOT EXISTS redeem_codes (
        code TEXT PRIMARY KEY, credits INTEGER, max_uses INTEGER,
        used_count INTEGER DEFAULT 0, created_by INTEGER, created_at INTEGER)""")
    c.execute("""CREATE TABLE IF NOT EXISTS code_usage (
        code TEXT, user_id INTEGER, used_at INTEGER,
        PRIMARY KEY (code, user_id))""")
    c.execute("""CREATE TABLE IF NOT EXISTS join_verified (
        user_id INTEGER PRIMARY KEY, verified_at INTEGER)""")
    conn.commit()
    conn.close()

db_init()

def db_exec(sql, params=()):
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute(sql, params); conn.commit(); conn.close()

def db_fetch(sql, params=()):
    conn = sqlite3.connect(DB_FILE); conn.row_factory = sqlite3.Row
    c = conn.cursor(); c.execute(sql, params); rows = c.fetchall(); conn.close()
    return [dict(r) for r in rows]

def db_one(sql, params=()):
    rows = db_fetch(sql, params)
    return rows[0] if rows else None

def get_user(uid): return db_one("SELECT * FROM users WHERE user_id=?", (uid,))

def create_user(uid, uname, fname, referred_by=None):
    now = int(time.time())
    db_exec("""INSERT OR IGNORE INTO users
               (user_id, username, first_name, credits, referred_by, joined_at, last_seen)
               VALUES (?,?,?,?,?,?,?)""",
            (uid, uname, fname, CREDIT_START, referred_by, now, now))

def add_credits(uid, amount):
    db_exec("UPDATE users SET credits = credits + ? WHERE user_id=?", (amount, uid))

def use_credits(uid, amount):
    u = get_user(uid)
    if not u or u["credits"] < amount: return False
    db_exec("UPDATE users SET credits = credits - ? WHERE user_id=?", (amount, uid))
    return True

def inc_lookup(uid):
    db_exec("UPDATE users SET total_lookups = total_lookups + 1, last_seen = ? WHERE user_id=?",
            (int(time.time()), uid))

def inc_referral(uid):
    db_exec("UPDATE users SET referral_count = referral_count + 1 WHERE user_id=?", (uid,))

def get_admin_channels():
    return db_fetch("SELECT * FROM channels ORDER BY id")

def add_channel(uname, title):
    uname = uname.lower().replace("@", "").strip()
    db_exec("INSERT OR IGNORE INTO channels (username, title, added_at) VALUES (?,?,?)",
            (uname, title, int(time.time())))

def remove_channel(uname):
    db_exec("DELETE FROM channels WHERE username=?", (uname.lower().replace("@", ""),))

def create_code(code, credits, max_uses, created_by):
    try:
        db_exec("""INSERT INTO redeem_codes
                   (code, credits, max_uses, created_by, created_at)
                   VALUES (?,?,?,?,?)""",
                (code.upper(), credits, max_uses, created_by, int(time.time())))
        return True
    except: return False

def get_code(code): return db_one("SELECT * FROM redeem_codes WHERE code=?", (code.upper(),))

def use_code(code, uid):
    c = get_code(code)
    if not c: return "invalid"
    if c["used_count"] >= c["max_uses"]: return "full"
    used = db_one("SELECT * FROM code_usage WHERE code=? AND user_id=?", (code.upper(), uid))
    if used: return "already"
    db_exec("INSERT INTO code_usage (code, user_id, used_at) VALUES (?,?,?)",
            (code.upper(), uid, int(time.time())))
    db_exec("UPDATE redeem_codes SET used_count = used_count + 1 WHERE code=?", (code.upper(),))
    add_credits(uid, c["credits"])
    return c["credits"]

def delete_code(code):
    db_exec("DELETE FROM redeem_codes WHERE code=?", (code.upper(),))
    db_exec("DELETE FROM code_usage WHERE code=?", (code.upper(),))

def list_codes(): return db_fetch("SELECT * FROM redeem_codes ORDER BY created_at DESC")

def total_users():
    r = db_one("SELECT COUNT(*) as n FROM users")
    return r["n"] if r else 0

def mark_join_verified(uid):
    db_exec("INSERT OR REPLACE INTO join_verified (user_id, verified_at) VALUES (?, ?)",
            (uid, int(time.time())))

def is_join_verified(uid):
    """Verified in last 1 hour."""
    r = db_one("SELECT * FROM join_verified WHERE user_id=?", (uid,))
    if not r: return False
    return (int(time.time()) - r["verified_at"]) < 3600

def clear_join_verified(uid):
    db_exec("DELETE FROM join_verified WHERE user_id=?", (uid,))


# ================== FORCE JOIN ==================
async def get_missing_channels(bot, uid):
    """Returns list of channels user hasn't joined."""
    missing = []
    for ch in REQUIRED_CHANNELS:
        try:
            m = await bot.get_chat_member(chat_id=f"@{ch['username']}", user_id=uid)
            status = m.status
            if status not in ("member", "administrator", "creator"):
                missing.append(ch)
        except Exception as e:
            err = str(e).lower()
            logger.warning(f"Channel check @{ch['username']} for {uid}: {e}")
            # Any error → block user (force join)
            missing.append(ch)
    return missing


def force_join_kb():
    rows = []
    for ch in REQUIRED_CHANNELS:
        rows.append([InlineKeyboardButton(
            f"📢 Join {ch['title']}",
            url=ch["url"],
            style="primary"
        )])
    rows.append([InlineKeyboardButton(
        "✅ I Joined All",
        callback_data="check_join_now",
        style="success"
    )])
    return InlineKeyboardMarkup(rows)


def force_join_msg():
    return (
        f"🔒  <b>{b('Join Required')}</b>  🔒\n\n"
        f"👋 Bot use karne se pehle\n"
        f"channel join karna zaroori hai\n\n"
        f"📢 <b>{b('Required Channel')}</b> :\n"
        f"  🔗 @sterniterspro\n\n"
        f"👇 Neeche button se join karo\n"
        f"Phir ✅ <b>I Joined All</b> dabao"
    )


# ================== BUTTONS ==================
def btn(text, **kw):
    return InlineKeyboardButton(text, **kw)

def main_menu_kb():
    return InlineKeyboardMarkup([
        [btn("📱 " + sc("Num2Info"), callback_data="hlp_num", style="success"),
         btn("🆔 " + sc("Aadhar2Info"), callback_data="hlp_aadhar", style="primary")],
        [btn("📸 " + sc("Tg2Info"), callback_data="hlp_tg", style="primary"),
         btn("🔍 " + sc("Search"), callback_data="hlp_search", style="primary")],
        [btn("💎 " + sc("My Credits"), callback_data="my_credits", style="success"),
         btn("🎁 " + sc("Referral"), callback_data="my_referral", style="primary")],
        [btn("🎟️ " + sc("Redeem Code"), callback_data="redeem_prompt", style="success"),
         btn("📖 " + sc("Help"), callback_data="menu_help", style="primary")],
        [btn("👑 " + sc("Owner"), url=OWNER_LINK, style="primary"),
         btn("❌ " + sc("Close"), callback_data="close_menu", style="danger")],
    ])

def back_kb():
    return InlineKeyboardMarkup([
        [btn("⬅️ " + sc("Back"), callback_data="main_menu", style="primary")]])

def result_kb():
    return InlineKeyboardMarkup([
        [btn("🔍 " + sc("New Lookup"), callback_data="new_lookup", style="success"),
         btn("🏠 " + sc("Menu"), callback_data="main_menu", style="primary")],
        [btn("👑 " + sc("Owner"), url=OWNER_LINK, style="primary")]])

def admin_kb():
    return InlineKeyboardMarkup([
        [btn("📊 " + sc("Stats"), callback_data="a_stats", style="success"),
         btn("📢 " + sc("Channels"), callback_data="a_channels", style="primary")],
        [btn("🎟️ " + sc("Create Code"), callback_data="a_code_create", style="success"),
         btn("📋 " + sc("List Codes"), callback_data="a_code_list", style="primary")],
        [btn("🗑️ " + sc("Delete Code"), callback_data="a_code_del", style="danger"),
         btn("📣 " + sc("Broadcast"), callback_data="a_broadcast", style="primary")],
        [btn("❌ " + sc("Close"), callback_data="a_close", style="danger")]])

def channels_kb():
    return InlineKeyboardMarkup([
        [btn("➕ " + sc("Add Channel"), callback_data="a_ch_add", style="success"),
         btn("➖ " + sc("Remove Channel"), callback_data="a_ch_remove", style="danger")],
        [btn("📋 " + sc("List Channels"), callback_data="a_ch_list", style="primary"),
         btn("⬅️ " + sc("Back"), callback_data="a_back", style="primary")]])


def owner_footer():
    return (f"\n\n━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👑 <b>{b('Owner')}</b> : {OWNER_USERNAME}\n"
            f"🤖 <b>{b('Bot')}</b> : @Leonv2osintbot")


# ================== MESSAGES ==================
def welcome_msg(uid):
    u = get_user(uid) or {}
    return (
        f"👽  <b>{b('Leon v2 OSINT')}</b>  👽\n\n"
        f"👋 <b>{b('Namaste')}</b>, <b>{H(u.get('first_name') or 'Dost')}</b>!\n\n"
        f"Main ek advanced OSINT bot hoon.\n"
        f"Number, Aadhar aur Telegram user ki\n"
        f"full information nikal sakta hoon.\n\n"
        f"💎 <b>{b('Credits')}</b> : <b>{u.get('credits', 0)}</b>\n"
        f"🎁 <b>{b('Referrals')}</b> : <b>{u.get('referral_count', 0)}</b>\n\n"
        f"✨ <b>{b('Features')}</b> :\n"
        f"  📱 {sc('Num2Info')}\n"
        f"  🆔 {sc('Aadhar2Info')}\n"
        f"  📸 {sc('Tg2Info')}\n"
        f"  🔍 {sc('Multi Search')}\n\n"
        f"👇 Neeche buttons se select karo{owner_footer()}")


def help_msg():
    return (
        f"📖  <b>{b('Help Menu')}</b>  📖\n\n"
        f"📱 <b>{b('NUM2INFO')}</b>\n<code>/num 9876543210</code>\nPhone number info.\n\n"
        f"🆔 <b>{b('AADHAR2INFO')}</b>\n<code>/aadhar 123456789012</code>\n12-digit Aadhar record.\n\n"
        f"📸 <b>{b('TG2INFO')}</b>\n<code>/tg 6910286881</code>\nTelegram user info.\n\n"
        f"🔍 <b>{b('SEARCH')}</b>\n<code>/search keyword</code>\nMulti-index search.\n\n"
        f"🎟️ <b>{b('REDEEM')}</b> : <code>/redeem CODE</code>\n"
        f"🎁 <b>{b('REFERRAL')}</b> : <code>/refer</code>\n"
        f"💎 <b>{b('CREDITS')}</b> : <code>/credits</code>\n\n"
        f"💡 Seedha number bhi bhej sakta hai!{owner_footer()}")


def credits_msg(uid):
    u = get_user(uid) or {}
    return (
        f"💎  <b>{b('My Credits')}</b>  💎\n\n"
        f"💎 <b>{b('Balance')}</b> : <b>{u.get('credits', 0)}</b>\n"
        f"📊 <b>{b('Total Lookups')}</b> : {u.get('total_lookups', 0)}\n"
        f"🎁 <b>{b('Referrals')}</b> : {u.get('referral_count', 0)}\n\n"
        f"Har lookup me 1 credit lagta hai.\n"
        f"Referral se 15 credits milte hain.{owner_footer()}")


def referral_msg(uid, bot_username):
    u = get_user(uid) or {}
    link = f"https://t.me/{bot_username}?start=ref_{uid}"
    return (
        f"🎁  <b>{b('Referral Program')}</b>  🎁\n\n"
        f"🔗 <b>{b('Your Link')}</b> :\n"
        f"<code>{H_code(link)}</code>\n\n"
        f"💰 <b>{b('Rewards')}</b> :\n"
        f"  Naye user ko : +{REFERRAL_BONUS_NEW}\n"
        f"  Tumhe : +{REFERRAL_REWARD}\n\n"
        f"🎁 <b>{b('Your Referrals')}</b> : {u.get('referral_count', 0)}\n\n"
        f"Link share karo aur credits kamao!{owner_footer()}")


def thinking_msg(step=0):
    frames = [f"🔍 {b('Searching')}...", f"📡 {b('Connecting')}...",
              f"⬇️ {b('Fetching data')}...", f"🎨 {b('Formatting')}...",
              f"📤 {b('Almost done')}..."]
    pct = min(int((step % 5) * 20), 95)
    return (f"👽  <b>{b('Processing')}</b>  👽\n\n"
            f"{frames[min(step, len(frames) - 1)]}\n\n"
            f"<code>[{progress_bar(pct)}] {pct}%</code>\n\n⏳ Please wait...")


def error_msg(reason=""):
    r = f"\n💡 {H(reason)}" if reason else ""
    return (f"❌  <b>{b('Oops! Kuch galat ho gaya')}</b>  ❌{r}\n\n"
            f"🔁 Dubara try karo.{owner_footer()}")


def no_credits_msg():
    return (f"💔  <b>{b('Insufficient Credits')}</b>  💔\n\n"
            f"Tumhare paas <b>0 credits</b> bache hain.\n\n"
            f"🎁 <b>{b('Credits kaise payein:')}</b>\n"
            f"  🎟️ Redeem code use karo\n"
            f"  🎁 Referral share karo (+15)\n"
            f"  👑 Admin se contact karo{owner_footer()}")


# ================== API ==================
def api_call(endpoint, query):
    try:
        r = requests.get(f"{API_BASE}{endpoint}", params={"q": query}, timeout=30,
                          headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200: return None
        return r.json()
    except Exception as e:
        logger.error(f"API error: {e}")
        return None


# ================== RESULT FORMATTER ==================
def format_result(data, kind, query, uid):
    u = get_user(uid) or {}
    credits = u.get("credits", 0)
    if not data: return error_msg("API se data nahi mila")

    headers = {
        "num": f"📱  <b>{b('Num2Info Result')}</b>  📱",
        "aadhar": f"🆔  <b>{b('Aadhar2Info Result')}</b>  🆔",
        "tg": f"📸  <b>{b('Tg2Info Result')}</b>  📸",
        "search": f"🔍  <b>{b('Search Result')}</b>  🔍",
    }
    header = headers.get(kind, f"📊  <b>{b('Result')}</b>")

    result = data
    if isinstance(data, dict):
        for key in ("result", "data", "results", "info"):
            if key in data and data[key]:
                result = data[key]
                break

    PRIORITY = ["name", "full_name", "father_name", "fathersname", "mother_name",
                "address", "phone_number", "phonenumber", "mobile", "aadhar_number",
                "aadharnumber", "aadhar", "other_number", "othernumber",
                "email", "dob", "gender", "circle", "operator",
                "state", "district", "pincode", "village", "city",
                "source", "connected_numbers", "username", "first_name",
                "last_name", "user_id", "id", "photo"]

    LABELS = {"fathersname": "Father's Name", "phonenumber": "Phone Number",
              "aadharnumber": "Aadhar Number", "othernumber": "Other Number",
              "connected_numbers": "Connected Numbers", "full_name": "Full Name",
              "first_name": "First Name", "last_name": "Last Name",
              "user_id": "User ID"}

    def pretty_label(k):
        key = k.lower().replace("_", "")
        if key in LABELS: return LABELS[key]
        return str(k).replace("_", " ").title()

    lines = []

    def add_line(label, value):
        if value is None or value == "" or str(value).lower() in ("none", "null"):
            return
        lines.append(f"  ├─ <b>{H(pretty_label(label))}</b> : {H(value)}")

    if isinstance(result, dict):
        used = set()
        for key in PRIORITY:
            for rk in list(result.keys()):
                if rk in used: continue
                if rk.lower().replace("_", "") == key.lower().replace("_", ""):
                    v = result[rk]
                    cv = clean_value(v)
                    if cv:
                        add_line(rk, cv)
                        used.add(rk)
        for rk, v in result.items():
            if rk in used: continue
            if isinstance(v, (str, int, float, bool)) and str(v).lower() not in ("none", "", "null"):
                cv = clean_value(v)
                if cv: add_line(rk, cv)
        for rk, v in result.items():
            if rk in used: continue
            if isinstance(v, (dict, list)) and v:
                cv = clean_value(v)
                if cv: add_line(rk, cv)
    elif isinstance(result, list):
        for idx, item in enumerate(result[:5], 1):
            if idx > 1: lines.append("")
            lines.append(f"  ✦ <b>{b('Result #' + str(idx))}</b>")
            if isinstance(item, dict):
                for k, v in item.items():
                    cv = clean_value(v)
                    if cv: add_line(k, cv)
            else:
                cv = clean_value(item)
                if cv: lines.append(f"  ├─ {H(cv)}")
    else:
        cv = clean_value(result)
        if cv: lines.append(f"  ├─ {H(cv)}")

    body = "\n".join(lines) if lines else "  No data available"

    return (f"{header}\n\n"
            f"🎯 <b>{b('Query')}</b> : <code>{H_code(query)}</code>\n\n"
            f"<b>{b('Result')}</b> :\n{body}\n\n"
            f"💎 <b>{b('Credits Left')}</b> : <b>{credits}</b>{owner_footer()}")


# ================== SAFE SEND/EDIT ==================
def plain_strip(text):
    return re.sub(r"<[^>]+>", "", str(text))

async def send_html(bot, chat_id, text, **kwargs):
    try:
        return await bot.send_message(chat_id, text, parse_mode=ParseMode.HTML, **kwargs)
    except Exception as e:
        logger.warning(f"HTML send failed: {e}")
        try:
            return await bot.send_message(chat_id, plain_strip(text), **kwargs)
        except Exception as e2:
            logger.error(f"Plain send failed: {e2}")
            return None

async def edit_q(q, text, **kwargs):
    try:
        return await q.edit_message_text(text=text, parse_mode=ParseMode.HTML, **kwargs)
    except Exception as e:
        logger.warning(f"q.edit failed: {e}")
        try:
            return await q.edit_message_text(text=plain_strip(text), **kwargs)
        except Exception as e2:
            logger.error(f"q plain edit failed: {e2}")
            return None

async def edit_message_html(bot, chat_id, message_id, text, **kwargs):
    try:
        return await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                            text=text, parse_mode=ParseMode.HTML, **kwargs)
    except Exception as e:
        logger.warning(f"HTML edit failed: {e}")
        try:
            return await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                                text=plain_strip(text), **kwargs)
        except Exception as e2:
            logger.error(f"Plain edit failed: {e2}")
            return None


# ================== /start ==================
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    user = update.effective_user

    referred_by = None
    if context.args and context.args[0].startswith("ref_"):
        try:
            ref_id = int(context.args[0][4:])
            if ref_id != user.id: referred_by = ref_id
        except: pass

    existing = get_user(user.id)
    is_new = existing is None

    if is_new:
        create_user(user.id, user.username or "", user.first_name or "", referred_by)
        if referred_by:
            add_credits(referred_by, REFERRAL_REWARD)
            inc_referral(referred_by)
            add_credits(user.id, REFERRAL_BONUS_NEW)
            try:
                await context.bot.send_message(referred_by,
                    f"🎁 <b>{b('New Referral!')}</b>\n\n"
                    f"👤 {H(user.first_name)} ne tumhara link use kiya\n"
                    f"💰 Tumhe <b>+{REFERRAL_REWARD}</b> credits mile! 🎉",
                    parse_mode=ParseMode.HTML)
            except: pass
    else:
        db_exec("UPDATE users SET last_seen=?, username=?, first_name=? WHERE user_id=?",
                (int(time.time()), user.username or "", user.first_name or "", user.id))

    # FORCE JOIN (admin skip)
    if user.id != ADMIN_ID:
        missing = await get_missing_channels(context.bot, user.id)
        if missing:
            await send_html(context.bot, msg.chat_id, force_join_msg(),
                             reply_markup=force_join_kb())
            return

    if is_new:
        u = get_user(user.id)
        text = (f"🎉  <b>{b('Welcome!')}</b>  🎉\n\n"
                f"👋 <b>{b('Namaste')}</b> {H(user.first_name)}!\n\n"
                f"✅ <b>{b('Account created!')}</b>\n\n"
                f"💎 <b>{b('Starting Credits')}</b> : {CREDIT_START}\n")
        if referred_by:
            text += f"🎁 <b>{b('Referral Bonus')}</b> : +{REFERRAL_BONUS_NEW}\n"
        text += (f"\n🎯 <b>{b('Total Credits')}</b> : {u.get('credits', CREDIT_START)}\n\n"
                 f"Ab bot use kar sakte ho!{owner_footer()}")
        await send_html(context.bot, msg.chat_id, text, reply_markup=main_menu_kb(),
                         disable_web_page_preview=True)
    else:
        await send_html(context.bot, msg.chat_id, welcome_msg(user.id),
                         reply_markup=main_menu_kb(), disable_web_page_preview=True)


# ================== LOOKUP ==================
async def num_cmd(u, c): await do_lookup(u, c, "num")
async def aadhar_cmd(u, c): await do_lookup(u, c, "aadhar")
async def tg_cmd(u, c): await do_lookup(u, c, "tg")
async def search_cmd(u, c): await do_lookup(u, c, "search")

async def do_lookup(update, context, kind):
    msg = update.message
    user = update.effective_user

    if not get_user(user.id):
        create_user(user.id, user.username or "", user.first_name or "")

    # FORCE JOIN (admin skip)
    if user.id != ADMIN_ID:
        missing = await get_missing_channels(context.bot, user.id)
        if missing:
            await send_html(context.bot, msg.chat_id, force_join_msg(),
                             reply_markup=force_join_kb())
            return

    if not context.args:
        examples = {"num": "/num 9876543210", "aadhar": "/aadhar 123456789012",
                    "tg": "/tg 6910286881", "search": "/search keyword"}
        await send_html(context.bot, msg.chat_id,
                         f"⚠️ <b>{b('Usage')}</b>\n\n<code>{examples[kind]}</code>")
        return

    query = " ".join(context.args).strip()

    if not use_credits(user.id, CREDIT_PER_LOOKUP):
        await send_html(context.bot, msg.chat_id, no_credits_msg())
        return

    inc_lookup(user.id)

    try:
        await context.bot.send_chat_action(chat_id=msg.chat_id, action=ChatAction.TYPING)
    except: pass

    status = await send_html(context.bot, msg.chat_id, thinking_msg(0))
    if not status: return

    endpoint = {"num": "/num", "aadhar": "/aadhar", "tg": "/tg", "search": "/search"}[kind]
    data = None
    try:
        data = await asyncio.to_thread(api_call, endpoint, query)
    except Exception as e:
        logger.error(f"API error: {e}")

    for step in range(5):
        try: await status.edit_text(thinking_msg(step), parse_mode=ParseMode.HTML)
        except: pass
        await asyncio.sleep(0.3)

    if not data:
        add_credits(user.id, CREDIT_PER_LOOKUP)
        await edit_message_html(context.bot, msg.chat_id, status.message_id,
                                 error_msg("API se response nahi mila. Credit refunded."),
                                 reply_markup=result_kb())
        return

    try: result_text = format_result(data, kind, query, user.id)
    except Exception as e:
        logger.error(f"Format error: {e}")
        result_text = error_msg("Data format error")

    await edit_message_html(context.bot, msg.chat_id, status.message_id, result_text,
                             reply_markup=result_kb(), disable_web_page_preview=True)


# ================== REDEEM ==================
async def redeem_cmd(update, context):
    msg = update.message
    user = update.effective_user
    if not get_user(user.id):
        create_user(user.id, user.username or "", user.first_name or "")

    if user.id != ADMIN_ID:
        missing = await get_missing_channels(context.bot, user.id)
        if missing:
            await send_html(context.bot, msg.chat_id, force_join_msg(),
                             reply_markup=force_join_kb())
            return

    if not context.args:
        await send_html(context.bot, msg.chat_id,
                         f"🎟️ <b>{b('Redeem Code')}</b>\n\nUsage : <code>/redeem YOURCODE</code>")
        return

    code = context.args[0].strip().upper()
    status = await send_html(context.bot, msg.chat_id,
                              f"🎟️ <b>{b('Checking code')}...</b>\n\n"
                              f"<code>[{progress_bar(30)}] 30%</code>")
    if status:
        await asyncio.sleep(0.5)
        try:
            await status.edit_text(
                f"🎟️ <b>{b('Validating')}...</b>\n\n<code>[{progress_bar(60)}] 60%</code>",
                parse_mode=ParseMode.HTML)
        except: pass
        await asyncio.sleep(0.5)

    result = use_code(code, user.id)
    if result == "invalid":
        text = f"❌ <b>{b('Invalid Code')}</b>\n\nYe code exist nahi karta.{owner_footer()}"
    elif result == "already":
        text = f"⚠️ <b>{b('Already Used')}</b>\n\nTum ye code pehle use kar chuke ho.{owner_footer()}"
    elif result == "full":
        text = f"❌ <b>{b('Code Expired')}</b>\n\nIs code ke saare uses khatam.{owner_footer()}"
    else:
        u = get_user(user.id)
        text = (f"🎉  <b>{b('Code Redeemed!')}</b>  🎉\n\n"
                f"🎟️ <b>{b('Code')}</b> : <code>{H_code(code)}</code>\n"
                f"💰 <b>{b('Credits Added')}</b> : +{result}\n"
                f"💎 <b>{b('New Balance')}</b> : {u.get('credits', 0)}\n\n"
                f"Ab bot use karo!{owner_footer()}")

    if status:
        await edit_message_html(context.bot, msg.chat_id, status.message_id, text,
                                 reply_markup=result_kb())
    else:
        await send_html(context.bot, msg.chat_id, text, reply_markup=result_kb())


# ================== REFERRAL / CREDITS ==================
async def refer_cmd(update, context):
    msg = update.message
    user = update.effective_user
    if not get_user(user.id):
        create_user(user.id, user.username or "", user.first_name or "")
    bot_info = await context.bot.get_me()
    await send_html(context.bot, msg.chat_id, referral_msg(user.id, bot_info.username),
                     reply_markup=back_kb())

async def credits_cmd(update, context):
    user = update.effective_user
    if not get_user(user.id):
        create_user(user.id, user.username or "", user.first_name or "")
    await send_html(context.bot, update.message.chat_id, credits_msg(user.id),
                     reply_markup=back_kb())


# ================== ADMIN ==================
async def admin_cmd(update, context):
    uid = update.effective_user.id
    logger.info(f"[ADMIN] User {uid} tried /admin")
    if uid != ADMIN_ID:
        await send_html(context.bot, update.message.chat_id,
                         f"❌ <b>{b('Access Denied')}</b>\n\n"
                         f"Tum admin nahi ho.")
        return
    await send_html(context.bot, update.message.chat_id,
                     f"👑  <b>{b('Admin Panel')}</b>  👑\n\nSelect option below:",
                     reply_markup=admin_kb())

async def broadcast_cmd(update, context):
    if update.effective_user.id != ADMIN_ID: return
    if not context.args:
        await send_html(context.bot, update.message.chat_id, "Usage: /broadcast <message>")
        return
    m = " ".join(context.args)
    users = db_fetch("SELECT user_id FROM users")
    sent = fail = 0
    st = await send_html(context.bot, update.message.chat_id,
                          f"📢 Broadcasting to {len(users)}...")
    for idx, u in enumerate(users):
        try:
            await context.bot.send_message(u["user_id"],
                                            f"📢 <b>{b('Broadcast')}</b>\n\n{H(m)}",
                                            parse_mode=ParseMode.HTML)
            sent += 1
        except: fail += 1
        if (idx + 1) % 10 == 0 and st:
            try: await st.edit_text(f"📢 {idx+1}/{len(users)}")
            except: pass
        await asyncio.sleep(0.05)
    if st:
        try: await st.edit_text(f"✅ Sent: {sent}\n❌ Failed: {fail}")
        except: pass


# ================== CALLBACK HANDLER ==================
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    d = q.data
    uid = q.from_user.id
    try: await q.answer()
    except: pass

    if d.startswith("a_"):
        if uid != ADMIN_ID:
            try: await q.answer("Access denied.", show_alert=True)
            except: pass
            return
        await handle_admin_callback(q, context, d)
        return

    if not get_user(uid):
        create_user(uid, q.from_user.username or "", q.from_user.first_name or "")

    # Special: verify join
    if d == "check_join_now":
        missing = await get_missing_channels(context.bot, uid)
        if missing:
            await edit_q(q, force_join_msg(), reply_markup=force_join_kb())
            try: await q.answer("Pehle channel join karo!", show_alert=True)
            except: pass
        else:
            mark_join_verified(uid)
            await edit_q(q,
                f"✅  <b>{b('Verified!')}</b>  ✅\n\n"
                f"Ab bot use kar sakte ho.\n\nNeeche se start karo 👇",
                reply_markup=main_menu_kb())
        return

    # Force join for other buttons (admin skip)
    if uid != ADMIN_ID and d != "main_menu":
        missing = await get_missing_channels(context.bot, uid)
        if missing:
            await edit_q(q, force_join_msg(), reply_markup=force_join_kb())
            return

    if d == "main_menu":
        await edit_q(q, welcome_msg(uid), reply_markup=main_menu_kb(),
                      disable_web_page_preview=True)
    elif d == "menu_help":
        await edit_q(q, help_msg(), reply_markup=back_kb())
    elif d == "my_credits":
        await edit_q(q, credits_msg(uid), reply_markup=back_kb())
    elif d == "my_referral":
        bot_info = await context.bot.get_me()
        await edit_q(q, referral_msg(uid, bot_info.username), reply_markup=back_kb())
    elif d == "redeem_prompt":
        await edit_q(q, f"🎟️ <b>{b('Redeem Code')}</b>\n\nBhejo : <code>/redeem YOURCODE</code>",
                      reply_markup=back_kb())
    elif d == "close_menu":
        await edit_q(q, f"❌ <b>{b('Menu Closed')}</b>")
    elif d == "new_lookup":
        await edit_q(q,
            f"🔍 <b>{b('New Lookup')}</b>\n\nCommands:\n"
            f"<code>/num 9876543210</code>\n<code>/aadhar 123456789012</code>\n"
            f"<code>/tg 6910286881</code>\n<code>/search keyword</code>",
            reply_markup=back_kb())
    elif d == "hlp_num":
        await edit_q(q, f"📱 <b>{b('NUM2INFO')}</b>\n\n<code>/num 9876543210</code>\n\n"
                        f"Phone number info.\n💰 Cost : {CREDIT_PER_LOOKUP} credit",
                      reply_markup=back_kb())
    elif d == "hlp_aadhar":
        await edit_q(q, f"🆔 <b>{b('AADHAR2INFO')}</b>\n\n<code>/aadhar 123456789012</code>\n\n"
                        f"12-digit Aadhar.\n💰 Cost : {CREDIT_PER_LOOKUP} credit",
                      reply_markup=back_kb())
    elif d == "hlp_tg":
        await edit_q(q, f"📸 <b>{b('TG2INFO')}</b>\n\n<code>/tg 6910286881</code>\n\n"
                        f"Telegram user info.\n💰 Cost : {CREDIT_PER_LOOKUP} credit",
                      reply_markup=back_kb())
    elif d == "hlp_search":
        await edit_q(q, f"🔍 <b>{b('SEARCH')}</b>\n\n<code>/search keyword</code>\n\n"
                        f"Multi-index search.\n💰 Cost : {CREDIT_PER_LOOKUP} credit",
                      reply_markup=back_kb())


async def handle_admin_callback(q, context, d):
    if d == "a_stats":
        users = total_users()
        chs = len(get_admin_channels()) + len(REQUIRED_CHANNELS)
        codes = len(list_codes())
        up = int(time.time() - START_TIME)
        h, r = divmod(up, 3600); m, s = divmod(r, 60)
        text = (f"📊  <b>{b('Bot Statistics')}</b>  📊\n\n"
                f"👥 <b>{b('Users')}</b> : {users}\n"
                f"📢 <b>{b('Channels')}</b> : {chs}\n"
                f"🎟️ <b>{b('Active Codes')}</b> : {codes}\n"
                f"⏱️ <b>{b('Uptime')}</b> : {h}h {m}m {s}s\n\n"
                f"💎 <b>{b('Credit Economy')}</b> :\n"
                f"  Start : {CREDIT_START}\n"
                f"  Referrer : +{REFERRAL_REWARD}\n"
                f"  Referred : +{REFERRAL_BONUS_NEW}\n"
                f"  Cost : {CREDIT_PER_LOOKUP}{owner_footer()}")
        await edit_q(q, text, reply_markup=admin_kb())
    elif d == "a_channels":
        chs_admin = get_admin_channels()
        txt = f"📢  <b>{b('Force Join Channels')}</b>  📢\n\n"
        txt += f"<b>🔒 Default (Locked)</b> :\n"
        for c in REQUIRED_CHANNELS:
            txt += f"  @{H_code(c['username'])} — {H(c['title'])}\n"
        txt += f"\n<b>➕ Admin Added</b> :\n"
        if chs_admin:
            for c in chs_admin:
                txt += f"  @{H_code(c['username'])} — {H(c.get('title') or 'N/A')}\n"
        else:
            txt += f"  None\n"
        txt += f"\nChoose action:"
        await edit_q(q, txt, reply_markup=channels_kb())
    elif d == "a_ch_add":
        context.user_data["awaiting"] = "ch_add"
        await edit_q(q, f"➕ <b>{b('Add Channel')}</b>\n\n"
                        f"Bhejo : <code>@username Title</code>\n\n"
                        f"Example:\n<code>@mychannel My Channel</code>\n\nYa /cancel")
    elif d == "a_ch_remove":
        context.user_data["awaiting"] = "ch_remove"
        await edit_q(q, f"➖ <b>{b('Remove Channel')}</b>\n\n"
                        f"Bhejo : <code>@username</code>\n\n"
                        f"⚠️ Default channel remove nahi hoga.\n\nYa /cancel")
    elif d == "a_ch_list":
        chs = get_admin_channels()
        if not chs:
            await edit_q(q, f"📢 No extra channels.", reply_markup=channels_kb())
        else:
            txt = f"📢 <b>{b('Admin Channels')}</b>\n\n"
            for c in chs:
                txt += f"  @{H_code(c['username'])} — {H(c.get('title') or 'N/A')}\n"
            await edit_q(q, txt, reply_markup=channels_kb())
    elif d == "a_back":
        await edit_q(q, f"👑  <b>{b('Admin Panel')}</b>  👑\n\nSelect option:",
                      reply_markup=admin_kb())
    elif d == "a_code_create":
        context.user_data["awaiting"] = "code_create"
        await edit_q(q, f"🎟️ <b>{b('Create Code')}</b>\n\n"
                        f"Bhejo : <code>CODE CREDITS USES</code>\n\n"
                        f"Example:\n<code>LEON50 50 10</code>\n\nYa /cancel")
    elif d == "a_code_list":
        codes = list_codes()
        if not codes:
            await edit_q(q, f"🎟️ No codes.", reply_markup=admin_kb())
            return
        txt = f"🎟️  <b>{b('Redeem Codes')}</b>  🎟️\n\n"
        for c in codes[:30]:
            txt += (f"  <code>{H_code(c['code'])}</code>\n"
                    f"     💰 {c['credits']} | 📊 {c['used_count']}/{c['max_uses']}\n")
        await edit_q(q, txt, reply_markup=admin_kb())
    elif d == "a_code_del":
        context.user_data["awaiting"] = "code_del"
        await edit_q(q, f"🗑️ <b>{b('Delete Code')}</b>\n\n"
                        f"Bhejo : <code>CODE</code>\n\nYa /cancel")
    elif d == "a_broadcast":
        await edit_q(q, f"📣 <b>{b('Broadcast')}</b>\n\n"
                        f"Command : <code>/broadcast Your message</code>")
    elif d == "a_close":
        await edit_q(q, f"❌ <b>{b('Admin Panel Closed')}</b>")


# ================== ADMIN TEXT ==================
async def handle_admin_text(update, context):
    if update.effective_user.id != ADMIN_ID: return False
    awaiting = context.user_data.get("awaiting")
    if not awaiting: return False

    text = (update.message.text or "").strip()
    if text == "/cancel":
        context.user_data.pop("awaiting", None)
        await send_html(context.bot, update.message.chat_id, "✅ Cancelled.")
        return True
    if not text or text.startswith("/"): return False

    if awaiting == "ch_add":
        parts = text.split(maxsplit=1)
        uname = parts[0].lstrip("@")
        title = parts[1] if len(parts) > 1 else uname
        add_channel(uname, title)
        context.user_data.pop("awaiting", None)
        await send_html(context.bot, update.message.chat_id,
                         f"✅ <b>{b('Channel Added')}</b>\n\n  @{H(uname)} — {H(title)}",
                         reply_markup=admin_kb())
        return True
    if awaiting == "ch_remove":
        uname = text.lstrip("@")
        remove_channel(uname)
        context.user_data.pop("awaiting", None)
        await send_html(context.bot, update.message.chat_id,
                         f"✅ <b>{b('Channel Removed')}</b>\n\n  @{H(uname)}",
                         reply_markup=admin_kb())
        return True
    if awaiting == "code_create":
        parts = text.split()
        if len(parts) < 3:
            await send_html(context.bot, update.message.chat_id, "Format: CODE CREDITS USES")
            return True
        try:
            code = parts[0].upper(); credits = int(parts[1]); uses = int(parts[2])
        except:
            await send_html(context.bot, update.message.chat_id, "Invalid numbers.")
            return True
        if create_code(code, credits, uses, update.effective_user.id):
            await send_html(context.bot, update.message.chat_id,
                             f"✅ <b>{b('Code Created')}</b>\n\n"
                             f"🎟️ <code>{H_code(code)}</code>\n💰 {credits}\n📊 {uses}",
                             reply_markup=admin_kb())
        else:
            await send_html(context.bot, update.message.chat_id, "❌ Code already exists.")
        context.user_data.pop("awaiting", None)
        return True
    if awaiting == "code_del":
        delete_code(text.upper())
        context.user_data.pop("awaiting", None)
        await send_html(context.bot, update.message.chat_id,
                         f"✅ <b>{b('Code Deleted')}</b>\n\n  <code>{H_code(text.upper())}</code>",
                         reply_markup=admin_kb())
        return True
    return False


# ================== MESSAGE HANDLER ==================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.text: return
    user = msg.from_user
    text = msg.text.strip()
    if text.startswith("/"): return

    if user.id == ADMIN_ID:
        handled = await handle_admin_text(update, context)
        if handled: return

    if not get_user(user.id):
        create_user(user.id, user.username or "", user.first_name or "")

    if user.id != ADMIN_ID:
        missing = await get_missing_channels(context.bot, user.id)
        if missing:
            await send_html(context.bot, msg.chat_id, force_join_msg(),
                             reply_markup=force_join_kb())
            return

    if re.fullmatch(r"\d{12}", text):
        context.args = [text]; await do_lookup(update, context, "aadhar"); return
    if re.fullmatch(r"\+?\d{10,13}", text):
        context.args = [text]; await do_lookup(update, context, "num"); return
    if re.fullmatch(r"\d{7,10}", text):
        context.args = [text]; await do_lookup(update, context, "tg"); return

    context.args = text.split()
    await do_lookup(update, context, "search")


# ================== MAIN ==================
def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is missing. Add it in Railway → Variables.")
    print("=" * 60)
    print("👽 Leon v2 OSINT Bot starting...")
    print("=" * 60)
    print(f"Admin ID: {ADMIN_ID}")
    print("⚠️  Bot ko @sterniterspro ka ADMIN banao!")
    print("=" * 60)
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", lambda u, c: send_html(c.bot, u.message.chat_id, help_msg(), reply_markup=back_kb())))
    app.add_handler(CommandHandler("num", num_cmd))
    app.add_handler(CommandHandler("aadhar", aadhar_cmd))
    app.add_handler(CommandHandler("tg", tg_cmd))
    app.add_handler(CommandHandler("search", search_cmd))
    app.add_handler(CommandHandler("redeem", redeem_cmd))
    app.add_handler(CommandHandler("refer", refer_cmd))
    app.add_handler(CommandHandler("credits", credits_cmd))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CommandHandler("broadcast", broadcast_cmd))

    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("✅ Bot live!")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()