import os
import sqlite3
import threading
import time
import requests
from flask import Flask
from telegram import (
    Update, ReplyKeyboardMarkup, KeyboardButton, 
    InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, 
    CallbackQueryHandler, ContextTypes, filters, ConversationHandler
)

# ---------------- 1. ENVIRONMENT VARIABLES ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
RENDER_URL = os.getenv("RENDER_URL")

# Conversation States for Selling Item (እቃ የመሸጥ ደረጃዎች)
SELL_TITLE, SELL_PRICE, SELL_PHOTO, SELL_PHONE = range(4)
# Conversation States for Admin Adding Product (አድሚን እቃ የመመዝገብ ደረጃዎች)
ADMIN_CAT, ADMIN_TITLE, ADMIN_PRICE, ADMIN_PHOTO = range(4, 8)

# ---------------- 2. KEEP-ALIVE SERVER ----------------
web_app = Flask('')

@web_app.route('/')
def home():
    return "Gondar Pro Market Bot is Active!"

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
            title TEXT, price REAL, category TEXT, photo_id TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def add_product_db(title, price, category, photo_id):
    conn = sqlite3.connect("gondar_market.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO products (title, price, category, photo_id) VALUES (?, ?, ?, ?)",
                   (title, price, category, photo_id))
    conn.commit()
    conn.close()

def get_products_by_cat(category):
    conn = sqlite3.connect("gondar_market.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, price FROM products WHERE category=?", (category,))
    items = cursor.fetchall()
    conn.close()
    return items

# ---------------- 4. HELPER FUNCTIONS ----------------
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
        "እንኳን ወደ **ጎንደር ኦንላይን ገበያ እና ዴሊቨሪ** በሰላም መጡ።\n\n"
        "እባክዎን ከታች ካሉት አማራጮች አንዱን ይምረጡ፡",
        reply_markup=main_menu_keyboard(user_id),
        parse_mode="Markdown"
    )

# B. እቃ የመሸጥ ደረጃ በደረጃ ሂደት (Seller Conversation)
async def sell_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📝 **የዕቃ መሸጫ ቅፅ (ደረጃ 1/4)**\n\nእባክዎን የዕቃውን ስም ያስገቡ፡", reply_markup=ReplyKeyboardRemove())
    return SELL_TITLE

async def sell_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['sell_title'] = update.message.text
    await update.message.reply_text("💰 **ደረጃ 2/4:** የሚሸጡበትን ዋጋ በብር ያስገቡ (ምሳሌ፡ 2500)፡")
    return SELL_PRICE

async def sell_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['sell_price'] = update.message.text
    await update.message.reply_text("📸 **ደረጃ 3/4:** እባክዎን የዕቃውን ጥራት ያለው ፎቶ ይላኩ፡")
    return SELL_PHOTO

async def sell_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("እባክዎን ፎቶ ይላኩ!")
        return SELL_PHOTO
    context.user_data['sell_photo'] = update.message.photo[-1].file_id
    await update.message.reply_text("📞 **ደረጃ 4/4:** አድሚኖቻችን እንዲያነጋግሩዎት የስልክ ቁጥርዎን ያስገቡ፡")
    return SELL_PHONE

async def sell_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    phone = update.message.text
    title = context.user_data['sell_title']
    price = context.user_data['sell_price']
    photo = context.user_data['sell_photo']

    await update.message.reply_text(
        "✅ **የመሸጫ ጥያቄዎ ተቀብለናል!**\n\n"
        "አድሚኖቻችን መረጃውን መርምረው ካረጋገጡ በኋላ ለገበያ ያቀርቡታል መልስ በቅርቡ ይደርስዎታል።",
        reply_markup=main_menu_keyboard(user.id)
    )

    # ለአድሚኑ መረጃውን በፎቶ መላክ
    if ADMIN_CHAT_ID:
        try:
            caption = f"📩 **አዲስ የዕቃ መሸጫ ጥያቄ:**\n\n👤 ከ: {user.full_name} (@{user.username})\n📦 እቃ: {title}\n💰 ዋጋ: {price} Birr\n📞 ስልክ: {phone}"
            await context.bot.send_photo(chat_id=ADMIN_CHAT_ID, photo=photo, caption=caption, parse_mode="Markdown")
        except Exception as e:
            print(f"Admin Send Error: {e}")

    return ConversationHandler.END

# C. አድሚን እቃ የሚመዘግብበት ደረጃዎች (Admin Add Product)
async def admin_start_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    cats = [
        [InlineKeyboardButton("ኤሌክትሮኒክስ", callback_data="addcat_electronics")],
        [InlineKeyboardButton("የቤት እቃዎች", callback_data="addcat_furniture")],
        [InlineKeyboardButton("ኮስሞቲክስ", callback_data="addcat_cosmetics")]
    ]
    await query.message.reply_text("አዲስ እቃ ለመመዝገብ መጀመሪያ ምድብ ይምረጡ፡", reply_markup=InlineKeyboardMarkup(cats))
    return ADMIN_CAT

async def admin_cat_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['admin_cat'] = query.data.split("_")[1]
    await query.message.reply_text("የእቃውን ስም ያስገቡ፡")
    return ADMIN_TITLE

async def admin_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['admin_title'] = update.message.text
    await update.message.reply_text("የእቃውን ዋጋ በብር ያስገቡ፡")
    return ADMIN_PRICE

async def admin_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['admin_price'] = update.message.text
    await update.message.reply_text("የእቃውን ፎቶ ይላኩ፡")
    return ADMIN_PHOTO

async def admin_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("እባክዎን ፎቶ ይላኩ!")
        return ADMIN_PHOTO
    
    photo_id = update.message.photo[-1].file_id
    cat = context.user_data['admin_cat']
    title = context.user_data['admin_title']
    price = float(context.user_data['admin_price'])

    # በዳታቤዝ መመዝገብ
    add_product_db(title, price, cat, photo_id)

    await update.message.reply_text(
        f"✅ **እቃው በስኬት ተመዝግቧል!**\n\nእቃ: {title}\nዋጋ: {price} Birr\nምድብ: {cat}",
        reply_markup=main_menu_keyboard(update.effective_user.id),
        parse_mode="Markdown"
    )
    return ConversationHandler.END

# D. Dynamic E-Commerce Catalog (እቃዎች መግዛት)
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    # የምድብ መምረጫ
    if query.data.startswith("cat_"):
        category = query.data.split("_")[1]
        products = get_products_by_cat(category)

        if not products:
            kb = [[InlineKeyboardButton("🏠 ዋና ገጽ", callback_data="nav_home")]]
            await query.message.edit_text("ℹ️ **በዚህ ምድብ ውስጥ እስካሁን የተመዘገበ እቃ የለም።**\nአድሚኑ አዳዲስ እቃዎችን ሲጨምር እዚህ ያገኙታል።", 
                                         reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
        else:
            inline_kb = []
            for prod in products:
                inline_kb.append([InlineKeyboardButton(f"{prod[1]} - {prod[2]} Birr", callback_data=f"buy_prod_{prod[0]}")])
            inline_kb.append([InlineKeyboardButton("🏠 ዋና ገጽ", callback_data="nav_home")])
            await query.message.edit_text(f"📂 የምድብ እቃዎች ({category})፡", reply_markup=InlineKeyboardMarkup(inline_kb))

    # እቃ መምረጥ እና ማዘዝ
    elif query.data.startswith("buy_prod_"):
        prod_id = query.data.split("_")[2]
        context.user_data['selected_prod_id'] = prod_id
        
        # GPS ማሳሰቢያ ጽሁፍ እና Location መጠየቂያ
        loc_keyboard = ReplyKeyboardMarkup(
            [[KeyboardButton("📍 ያለሁበትን ቦታ ይላኩ (Share Location)", request_location=True)]],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        
        await query.message.delete()
        await context.bot.send_message(
            chat_id=user_id,
            text="⚠️ **ትኩረት:** አድራሻዎን በትክክል ለመላክ **የስልክዎን GPS (Location)** ማብራትዎን ያረጋግጡ!\n\n"
                 "ከዚያ ከታች ያለውን **'📍 ያለሁበትን ቦታ ይላኩ'** የሚለውን ቁልፍ ይጫኑ፡",
            reply_markup=loc_keyboard,
            parse_mode="Markdown"
        )

    # የክፍያ አማራጭ ሲመረጥ ትዕዛዝ ማጠናቀቂያ
    elif query.data.startswith("pay_"):
        pay_method = query.data.split("_")[1].upper()
        await query.message.edit_text(
            f"✅ **ትዕዛዝዎ በስኬት ተልኳል!**\n\n"
            f"የመረጡት የክፍያ መንገድ: **{pay_method}**\n"
            "በአጭር ጊዜ ውስጥ ደውለን አድራሻዎ ድረስ እቃውን እናደርሳለን። አመሰግናለሁ!",
            parse_mode="Markdown"
        )
        
        # ለአድሚኑ ማስታወቂያ መላክ
        if ADMIN_CHAT_ID:
            try:
                user = update.effective_user
                await context.bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text=f"🛒 **አዲስ የክፍያ ትዕዛዝ!**\n\nተጠቃሚ: {user.full_name} (@{user.username})\nየክፍያ አይነት: {pay_method}"
                )
            except Exception as e:
                print(f"Payment Notify Error: {e}")

    elif query.data == "nav_home":
        await query.message.delete()
        await context.bot.send_message(chat_id=user_id, text="🏠 ወደ ዋና ገጽ ተመልሰዋል፡", reply_markup=main_menu_keyboard(user_id))

# E. Location Handler
async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    location = update.message.location

    payment_kb = [
        [InlineKeyboardButton("💳 Telebirr", callback_data="pay_telebirr")],
        [InlineKeyboardButton("🏦 CBE Birr", callback_data="pay_cbe")],
        [InlineKeyboardButton("💵 Cash on Delivery", callback_data="pay_cash")]
    ]

    await update.message.reply_text(
        "📍 **አድራሻዎ በትክክል ተቀብለናል!**\n\nእባክዎን የመጨረሻውን የክፍያ አማራጭ ይምረጡ፡",
        reply_markup=InlineKeyboardMarkup(payment_kb),
        parse_mode="Markdown"
    )

    if ADMIN_CHAT_ID:
        try:
            await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=f"📍 **አዲስ የሎኬሽን አድራሻ ከ:** {user.full_name} (@{user.username})")
            await context.bot.send_location(chat_id=ADMIN_CHAT_ID, latitude=location.latitude, longitude=location.longitude)
        except Exception as e:
            print(f"Location Forward Error: {e}")

# F. Main Message Handler
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    if text == "🛍️ እቃዎች መግዛት":
        inline_kb = [
            [InlineKeyboardButton("📱 ኤሌክትሮኒክስ", callback_data="cat_electronics")],
            [InlineKeyboardButton("🛋️ የቤት እቃዎች", callback_data="cat_furniture")],
            [InlineKeyboardButton("💄 ኮስሞቲክስ", callback_data="cat_cosmetics")],
            [InlineKeyboardButton("🏠 ዋና ገጽ", callback_data="nav_home")]
        ]
        await update.message.reply_text("የሚፈልጉትን የዕቃ ምድብ ይምረጡ፡", reply_markup=InlineKeyboardMarkup(inline_kb))

    elif text == "🚚 የጭነት / Delivery አገልግሎት":
        loc_keyboard = ReplyKeyboardMarkup(
            [[KeyboardButton("📍 የጭነት መነሻ ቦታ ይላኩ", request_location=True)]],
            resize_keyboard=True, one_time_keyboard=True
        )
        await update.message.reply_text("⚠️ **ማሳሰቢያ:** እባክዎን የስልክዎን GPS ያብሩ!\n\nየጭነት መነሻ አድራሻዎን ለመላክ ከታች ያለውን ቁልፍ ይጫኑ፡", reply_markup=loc_keyboard, parse_mode="Markdown")

    elif text == "⚙️ Admin Panel" and ADMIN_CHAT_ID and str(user_id) == str(ADMIN_CHAT_ID):
        admin_kb = [[InlineKeyboardButton("➕ አዲስ እቃ መመዝገብ", callback_data="admin_add_start")]]
        await update.message.reply_text("⚙️ **Admin Control Panel**", reply_markup=InlineKeyboardMarkup(admin_kb))

    else:
        await update.message.reply_text("ጥያቄዎ ደርሶናል!", reply_markup=main_menu_keyboard(user_id))

# ---------------- 6. MAIN RUNNER ----------------
def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return ConversationHandler.END

if __name__ == '__main__':
    if not BOT_TOKEN:
        print("Error: BOT_TOKEN አልተገኘም!")
        exit(1)

    keep_alive()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Seller Conversation Handler
    sell_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^🏪 እቃ ለመሸጥ / መመዝገብ$'), sell_start)],
        states={
            SELL_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, sell_title)],
            SELL_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, sell_price)],
            SELL_PHOTO: [MessageHandler(filters.PHOTO, sell_photo)],
            SELL_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, sell_phone)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    # Admin Product Add Conversation Handler
    admin_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_start_add, pattern='^admin_add_start$')],
        states={
            ADMIN_CAT: [CallbackQueryHandler(admin_cat_select, pattern='^addcat_')],
            ADMIN_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_title)],
            ADMIN_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_price)],
            ADMIN_PHOTO: [MessageHandler(filters.PHOTO, admin_photo)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    app.add_handler(sell_conv)
    app.add_handler(admin_conv)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.LOCATION, handle_location))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_callback))

    print("🚀 ጎንደር ገበያ ፕሮፌሽናል ቦት በስኬት ስራ ጀምሯል...")
    app.run_polling()
