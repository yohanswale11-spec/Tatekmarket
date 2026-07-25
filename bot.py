import os
import sqlite3
import threading
import time
import requests
from flask import Flask
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, 
    CallbackQueryHandler, ContextTypes, filters
)

# ---------------- 1. ENVIRONMENT VARIABLES ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")  # የአድሚን Telegram ID
RENDER_URL = os.getenv("RENDER_URL")

# ---------------- 2. KEEP-ALIVE SERVER (Prevent Sleep) ----------------
web_app = Flask('')

@web_app.route('/')
def home():
    return "Gondar Pro Bot is Active!"

def run_flask():
    web_app.run(host='0.0.0.0', port=8080)

def keep_alive():
    server_thread = threading.Thread(target=run_flask)
    server_thread.daemon = True
    server_thread.start()
    
    def ping_self():
        while True:
            time.sleep(600)
            if RENDER_URL:
                try:
                    requests.get(RENDER_URL)
                except Exception as e:
                    print(f"Ping Error: {e}")

    ping_thread = threading.Thread(target=ping_self)
    ping_thread.daemon = True
    ping_thread.start()

# ---------------- 3. DATABASE SETUP ----------------
def init_db():
    conn = sqlite3.connect("gondar_market.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT, price REAL, category TEXT, description TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# ---------------- 4. HELPER FUNCTIONS ----------------
# ቻቱ ንጹህ እንዲሆን የቀደመውን መልዕክት የማጥፋት ረዳት
async def delete_previous_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        if query and query.message:
            await query.message.delete()
    except Exception as e:
        print(f"Delete Error: {e}")

# ዋናው የሜኑ ቁልፍ
def main_menu_keyboard(user_id):
    keyboard = [
        ["🛍️ እቃዎች መግዛት", "🏪 እቃ ለመሸጥ / መመዝገብ"],
        ["🚚 የጭነት / Delivery አገልግሎት"]
    ]
    if ADMIN_CHAT_ID and str(user_id) == str(ADMIN_CHAT_ID):
        keyboard.append(["⚙️ Admin Panel"])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ---------------- 5. BOT CORE HANDLERS ----------------

# A. Start Command (/start)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.reply_text(
        f"ሰላም {update.effective_user.first_name}!\n"
        "እንኳን ወደ **ጎንደር ፕሮፌሽናል ገበያ እና ዴሊቨሪ** በሰላም መጡ።\n\n"
        "እባክዎን ከታች ካሉት አማራጮች አንዱን ይምረጡ፡",
        reply_markup=main_menu_keyboard(user_id),
        parse_mode="Markdown"
    )

# B. Inline Navigation Handlers
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    # 1. ወደ ዋና ገጽ (Home / Back)
    if query.data == "nav_home":
        await delete_previous_msg(update, context)
        await context.bot.send_message(
            chat_id=user_id,
            text="🏠 ወደ ዋና ገጽ ተመልሰዋል፡",
            reply_markup=main_menu_keyboard(user_id)
        )

    # 2. የምድብ መምረጫ
    elif query.data.startswith("cat_"):
        await delete_previous_msg(update, context)
        category = query.data.split("_")[1].upper()
        
        # የዕቃዎች ዝርዝር ናሙና (ከዳታቤዝ የሚመጣ)
        inline_kb = [
            [InlineKeyboardButton("📱 ስማርት ፎን - 15,000 Birr", callback_data="buy_prod_1")],
            [InlineKeyboardButton("🛋️ ሶፋ ሴት - 45,000 Birr", callback_data="buy_prod_2")],
            [InlineKeyboardButton("⬅️ ተመለስ (Home)", callback_data="nav_home")]
        ]
        await context.bot.send_message(
            chat_id=user_id,
            text=f"📂 የምድብ ስም: **{category}**\n\nለመግዛት የሚፈልጉትን እቃ ይምረጡ፡",
            reply_markup=InlineKeyboardMarkup(inline_kb),
            parse_mode="Markdown"
        )

    # 3. እቃ መምረጥ እና ማዘዝ (Order Process)
    elif query.data.startswith("buy_prod_"):
        await delete_previous_msg(update, context)
        prod_id = query.data.split("_")[2]
        
        # የትራንስፖርት/Location መጠየቂያ ቁልፍ
        loc_keyboard = ReplyKeyboardMarkup(
            [[KeyboardButton("📍 ያለሁበትን ቦታ ይላኩ (Share Location)", request_location=True)]],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        
        await context.bot.send_message(
            chat_id=user_id,
            text="🛒 **የማዘዣ ሂደት (Checkout)**\n\n"
                 "እቃውን ያዘዙበት አድራሻ በትክክል እንዲደርስዎ እባክዎን ከታች ያለውን **'📍 ያለሁበትን ቦታ ይላኩ'** የሚለውን ቁልፍ ይጫኑ፡",
            reply_markup=loc_keyboard,
            parse_mode="Markdown"
        )

# C. Location Message Handler (አድራሻ እና ክፍያ ማስፈጸሚያ)
async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    location = update.message.location

    # የአድራሻ መረጃ ከተቀበለ በኋላ የክፍያ አማራጭ ያሳያል
    payment_kb = [
        [InlineKeyboardButton("💳 Telebirr", callback_data="pay_telebirr")],
        [InlineKeyboardButton("🏦 CBE Birr", callback_data="pay_cbe")],
        [InlineKeyboardButton("💵 Cash on Delivery (ሲረከቡ)", callback_data="pay_cash")],
        [InlineKeyboardButton("🏠 ዋና ገጽ", callback_data="nav_home")]
    ]

    await update.message.reply_text(
        "✅ **አድራሻዎ በስኬት ተቀብለናል!**\n\n"
        "አሁን እባክዎን የክፍያ አማራጭ ይምረጡ፡",
        reply_markup=InlineKeyboardMarkup(payment_kb),
        parse_mode="Markdown"
    )

    # ለአድሚኑ የትዕዛዙን አድራሻ ማስተላለፍ
    if ADMIN_CHAT_ID:
        try:
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=f"📦 **አዲስ ትዕዛዝ ተልኳል!**\nሰውዬው: {user.full_name} (@{user.username})"
            )
            await context.bot.send_location(
                chat_id=ADMIN_CHAT_ID,
                latitude=location.latitude,
                longitude=location.longitude
            )
        except Exception as e:
            print(f"Admin Notify Error: {e}")

# D. Main Message Text Handler
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    # 1. እቃዎች መግዛት (Clean UI with Categories)
    if text == "🛍️ እቃዎች መግዛት":
        inline_kb = [
            [InlineKeyboardButton("📱 ኤሌክትሮኒክስ", callback_data="cat_electronics")],
            [InlineKeyboardButton("🛋️ የቤት እቃዎች", callback_data="cat_furniture")],
            [InlineKeyboardButton("💄 ኮስሞቲክስ", callback_data="cat_cosmetics")],
            [InlineKeyboardButton("🏠 ዋና ገጽ", callback_data="nav_home")]
        ]
        await update.message.reply_text(
            "የሚፈልጉትን የዕቃ ምድብ ይምረጡ፡",
            reply_markup=InlineKeyboardMarkup(inline_kb)
        )

    # 2. እቃ ለመሸጥ / መመዝገብ (የመሸጫ መንገድ)
    elif text == "🏪 እቃ ለመሸጥ / መመዝገብ":
        await update.message.reply_text(
            "📝 **የዕቃ መሸጫ/መመዝገቢያ ቅፅ**\n\n"
            "የሚሸጡትን እቃ መረጃ በሚከተለው አፃፃፍ ይላኩልን፡\n"
            "1. የዕቃው ስም\n"
            "2. የሚፈልጉት ዋጋ\n"
            "3. የስልክ ቁጥር\n"
            "4. የዕቃው ፎቶ\n\n"
            "መረጀውን ሲልኩልን አድሚኖቻችን መዝግበው ለገበያ ያቀርቡታል!",
            reply_markup=main_menu_keyboard(user_id)
        )

    # 3. የጭነት / Delivery አገልግሎት
    elif text == "🚚 የጭነት / Delivery አገልግሎት":
        loc_keyboard = ReplyKeyboardMarkup(
            [[KeyboardButton("📍 የጭነት መነሻ ቦታ ይላኩ", request_location=True)]],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        await update.message.reply_text(
            "🚚 **የጭነት አገልግሎት**\n\nእቃው የሚነሳበትን ቦታ በትክክል ለመላክ ከታች ያለውን ቁልፍ ይጫኑ፡",
            reply_markup=loc_keyboard
        )

    # 4. Admin Panel
    elif text == "⚙️ Admin Panel" and ADMIN_CHAT_ID and str(user_id) == str(ADMIN_CHAT_ID):
        admin_kb = [
            [InlineKeyboardButton("➕ አዲስ እቃ መመዝገብ", callback_data="admin_add_prod")],
            [InlineKeyboardButton("📋 የትዕዛዞች ዝርዝር", callback_data="admin_view_orders")],
            [InlineKeyboardButton("🏠 ዋና ገጽ", callback_data="nav_home")]
        ]
        await update.message.reply_text(
            "⚙️ **Admin Control Panel**\nእንኳን ወደ አድሚን ክፍል በሰላም መጡ።",
            reply_markup=InlineKeyboardMarkup(admin_kb)
        )

    else:
        await update.message.reply_text(
            "ጥያቄዎ ደርሶናል! በፍጥነት ምላሽ እንሰጣለን።",
            reply_markup=main_menu_keyboard(user_id)
        )

# ---------------- 6. MAIN RUNNER ----------------
if __name__ == '__main__':
    if not BOT_TOKEN:
        print("Error: BOT_TOKEN አልተገኘም!")
        exit(1)

    keep_alive()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Handlers ማገናኘት
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.LOCATION, handle_location))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_callback))

    print("🚀 ጎንደር ፕሮፌሽናል ቦት በስኬት ስራ ጀምሯል...")
    app.run_polling()
