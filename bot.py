import os
import sqlite3
import threading
import time
import requests
from flask import Flask
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, 
    CallbackQueryHandler, ContextTypes, filters
)

# ---------------- 1. ENVIRONMENT VARIABLES ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")  # የቴሌግራም ID (በቁጥር)
RENDER_URL = os.getenv("RENDER_URL")        # Render ላይ የሚሰጥህ የዌብሳይት ሊንክ (ተማራጭ)

# ---------------- 2. KEEP-ALIVE SERVER (SLEEP እንዳያደርግ) ----------------
web_app = Flask('')

@web_app.route('/')
def home():
    return "Gondar Bot is Active and Running!"

def run_flask():
    web_app.run(host='0.0.0.0', port=8080)

def keep_alive():
    # Flask Web Server በ background ይጀምራል
    server_thread = threading.Thread(target=run_flask)
    server_thread.daemon = True
    server_thread.start()
    
    # ራሱን በራሱ በየ 10 ደቂቃው Ping በማድረግ Sleep እንዳያደርግ ይከላከላል
    def ping_self():
        while True:
            time.sleep(600) # 10 ደቂቃ (600 ሰከንድ)
            if RENDER_URL:
                try:
                    requests.get(RENDER_URL)
                    print("Self-ping sent successfully!")
                except Exception as e:
                    print(f"Ping Error: {e}")

    ping_thread = threading.Thread(target=ping_self)
    ping_thread.daemon = True
    ping_thread.start()

# ---------------- 3. DATABASE SETUP ----------------
def init_db():
    conn = sqlite3.connect("gondar_market.db")
    cursor = conn.cursor()
    # 1. የዕቃዎች ሰንጠረዥ
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT, price REAL, category TEXT, description TEXT
        )
    ''')
    # 2. የደላላ እና የትራንስፖርት ጥያቄዎች
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER, type TEXT, details TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# ---------------- 4. BOT CORE FUNCTIONS ----------------

# A. Start Command (/start)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    
    # ዋና ዋና የሜኑ ቁልፎች
    keyboard = [
        ["🛍️ እቃዎች መግዛት", "➕ እቃ ለመሸጥ (Broker)"],
        ["🚚 የጭነት/ትራንስፖርት አገልግሎት", "💳 የክፍያ አማራጮች"]
    ]
    
    # አድሚን ከሆነ ተጨማሪ Admin Panel ቁልፍ ይታየዋል
    if ADMIN_CHAT_ID and user_id == str(ADMIN_CHAT_ID):
        keyboard.append(["⚙️ Admin Panel"])

    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        f"ሰላም {update.effective_user.first_name}!\n"
        "እንኳን ወደ **ጎንደር ኦንላይን ገበያ እና የደላላ ቦት** በሰላም መጡ።\n"
        "እባክዎን ከታች ካሉት አማራጮች አንዱን ይምረጡ፡",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

# B. Main Message Handler
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user = update.effective_user
    user_id = str(user.id)

    # 1. እቃዎች መግዛት (E-commerce Categories)
    if text == "🛍️ እቃዎች መግዛት":
        inline_kb = [
            [InlineKeyboardButton("📱 ኤሌክትሮኒክስ", callback_data="cat_electronics")],
            [InlineKeyboardButton("🛋️ የቤት እቃዎች", callback_data="cat_furniture")],
            [InlineKeyboardButton("💄 ኮስሞቲክስ", callback_data="cat_cosmetics")]
        ]
        await update.message.reply_text(
            "የሚፈልጉትን የዕቃ ምድብ ይምረጡ፡", 
            reply_markup=InlineKeyboardMarkup(inline_kb)
        )

    # 2. እቃ ለመሸጥ (Broker System)
    elif text == "➕ እቃ ለመሸጥ (Broker)":
        await update.message.reply_text(
            "📝 **የመሸጫ ቅፅ**\n\n"
            "የሚሸጡትን እቃ መረጃ በሚከተለው አፃፃፍ ይላኩልን፡\n"
            "1. የዕቃው ስም\n2. የሚፈልጉት ዋጋ\n3. የስልክ ቁጥር\n4. የዕቃው ሁኔታ/መግለጫ"
        )

    # 3. የጭነት/ትራንስፖርት አገልግሎት
    elif text == "🚚 የጭነት/ትራንስፖርት አገልግሎት":
        await update.message.reply_text(
            "🚚 **የጭነት አገልግሎት ጥያቄ**\n\n"
            "የሚዛወረውን እቃ፣ የመነሻ ቦታ እና የመድረሻ ቦታ ይፃፉልን።\n"
            "ምሳሌ: *ከቀበሌ 18 ወደ አዳራሽ 2 ሶፋ እና አልጋ*"
        )

    # 4. የክፍያ አማራጮች
    elif text == "💳 የክፍያ አማራጮች":
        payment_msg = (
            "💳 **የክፍያ አማራጮች (Payment Methods)**\n\n"
            "1. **Telebirr:** 09XXXXXXXX\n"
            "2. **CBE Birr:** 1000XXXXXXXX\n"
            "3. **Cash on Delivery:** እቃው አድራሻዎ ደርሶ ሲረከቡ የሚከፈል"
        )
        await update.message.reply_text(payment_msg, parse_mode="Markdown")

    # 5. Admin Panel (ለአድሚን ብቻ)
    elif text == "⚙️ Admin Panel" and ADMIN_CHAT_ID and user_id == str(ADMIN_CHAT_ID):
        admin_kb = [
            [InlineKeyboardButton("➕ እቃ መመዝገብ", callback_data="admin_add")],
            [InlineKeyboardButton("📋 የጥያቄዎች ዝርዝር", callback_data="admin_requests")]
        ]
        await update.message.reply_text(
            "⚙️ **Admin Control Panel**", 
            reply_markup=InlineKeyboardMarkup(admin_kb)
        )

    # 6. ሌሎች መልዕክቶች እና ጥያቄዎች (ወደ አድሚን የማስተላለፊያ)
    else:
        await update.message.reply_text("ጥያቄዎ ደርሶናል! በፍጥነት ምላሽ እንሰጣለን።")
        
        # መረጃውን ወደ አድሚን ቻት ማስተላለፍ
        if ADMIN_CHAT_ID:
            try:
                forward_msg = f"📩 **አዲስ መልዕክት/ጥያቄ:**\n\nከ: {user.full_name} (@{user.username})\nመልዕክት: {text}"
                await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=forward_msg, parse_mode="Markdown")
            except Exception as e:
                print(f"Forward error: {e}")

# C. Inline Buttons Callback Handler
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data.startswith("cat_"):
        category = query.data.split("_")[1].upper()
        await query.message.reply_text(f"የመረጡት ምድብ: **{category}**\n\nበዚህ ምድብ ያሉ እቃዎች ዝርዝር በመጫን ላይ ነው...")
    elif query.data == "admin_add":
        await query.message.reply_text("አዲስ እቃ ለመጨመር የዕቃውን ስም፣ ዋጋ እና መግለጫ ያስገቡ።")

# ---------------- 5. MAIN RUNNER ----------------
if __name__ == '__main__':
    if not BOT_TOKEN:
        print("Error: BOT_TOKEN አልተገኘም! Environment variable-ን ያረጋግጡ።")
        exit(1)

    # Sleep እንዳያደርግ Keep-Alive አገልግቱን ማስነሳት
    keep_alive()

    # ቦቱን መገንባት
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Handlers ማገናኘት
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_callback))

    print("🚀 ጎንደር ገበያ ቦት በስኬት ስራ ጀምሯል...")
    app.run_polling()
