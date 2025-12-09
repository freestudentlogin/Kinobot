import logging
import sqlite3
import re
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from telegram.constants import ParseMode

# ========== RAILWAY CONFIGURATION ==========
# Environment variables dan olish
TOKEN = os.environ.get("BOT_TOKEN", "8071915816:AAE6VGglu3WBnxXtu3_UZfYJ8prVhvqVRSo")
CHANNEL_USERNAME = os.environ.get("CHANNEL_USERNAME", "@uzkinolarbot_manba")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "7901013364"))

# Baza faylini Railway da saqlash (ephemeral storage uchun)
DB_PATH = os.environ.get("DB_PATH", "films.db")

# Railway port
PORT = int(os.environ.get("PORT", 8080))

# ========== BOT CONFIGURATION ==========
UPLOAD_FILE, GET_NAME, GET_CODE = range(3)

# Logging setup for Railway
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ========== HELPER FUNCTIONS ==========
def safe_sql(text):
    """SQL uchun xavfsiz matn yaratish"""
    if text is None:
        return ""
    
    text = str(text)
    text = text.replace("'", "''")
    text = text.replace('"', '""')
    text = text.replace(';', '')
    text = text.replace('--', '')
    text = text.replace('#', '№')
    text = text.replace('%', '%%')
    text = text.replace('_', '\_')
    text = re.sub(r'[\x00-\x1F\x7F]', '', text)
    return text.strip()

def safe_html(text):
    """HTML uchun xavfsiz matn yaratish"""
    if text is None:
        return ""
    
    text = str(text)
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    text = text.replace('"', '&quot;')
    text = text.replace("'", '&#39;')
    return text

def init_database():
    """Ma'lumotlar bazasini yaratish"""
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        c = conn.cursor()
        
        # Faqat agar mavjud bo'lmasa yaratish
        c.execute('''CREATE TABLE IF NOT EXISTS films
                     (code TEXT PRIMARY KEY, 
                      name TEXT,
                      file_id TEXT,
                      file_type TEXT,
                      duration TEXT,
                      message_id INTEGER,
                      date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        
        conn.commit()
        conn.close()
        logger.info("✅ Database initialized successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Database initialization error: {e}")
        return False

# ========== COMMAND HANDLERS ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    user = update.effective_user
    welcome_text = f"""🎬 Salom, {user.first_name}!
    
Men film kodlari orqali kinolar topshiradigan botman.

<b>📌 Qanday foydalanish:</b>
1. Film kodini yozing (masalan: <code>1234</code>)
2. Men sizga shu kodli filmni yuboraman

📥 Admin panel: /admin
    """
    await update.message.reply_text(welcome_text, parse_mode=ParseMode.HTML)

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin panel handler"""
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Siz admin emassiz!")
        return
    
    admin_text = """<b>⚙️ Admin Panel</b>

📥 Film qo'shish: /addfilm
📊 Bazadagi filmlar: /listfilms
🔎 Film qidirish: /search [nomi]
🗑️ Film o'chirish: /deletefilm [kod]
🧹 Bazani tozalash: /cleanup
📈 Bot statistikasi: /stats

<i>Misol:</i>
/search Avatar
/deletefilm H1
    """
    await update.message.reply_text(admin_text, parse_mode=ParseMode.HTML)

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bot statistikasi"""
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Siz admin emassiz!")
        return
    
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM films")
        film_count = c.fetchone()[0]
        
        c.execute("SELECT COUNT(DISTINCT file_type) FROM films")
        type_count = c.fetchone()[0]
        
        conn.close()
        
        stats_text = f"""<b>📊 Bot Statistikasi</b>

🎬 <b>Filmlar soni:</b> {film_count}
🎥 <b>Formatlar:</b> {type_count} tur
📢 <b>Kanal:</b> {CHANNEL_USERNAME}
👑 <b>Admin:</b> {ADMIN_ID}
🤖 <b>Host:</b> Railway
🔄 <b>Holat:</b> Faol
        """
        await update.message.reply_text(stats_text, parse_mode=ParseMode.HTML)
        
    except Exception as e:
        await update.message.reply_text(f"❌ Statistika olishda xatolik: {str(e)}")

# ========== CONVERSATION HANDLERS ==========
async def add_film_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Siz admin emassiz!")
        return ConversationHandler.END
    
    await update.message.reply_text("🎥 Iltimos, film faylini yuboring.")
    return UPLOAD_FILE

async def receive_film_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.video:
        file_id = update.message.video.file_id
        file_type = "video"
        duration = update.message.video.duration
        minutes, seconds = divmod(duration, 60)
        hours, minutes = divmod(minutes, 60)
        if hours > 0:
            duration_str = f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            duration_str = f"{minutes}:{seconds:02d}"
        context.user_data['duration'] = duration_str
    elif update.message.document:
        file_id = update.message.document.file_id
        file_type = "document"
        context.user_data['duration'] = "Dokument"
    else:
        await update.message.reply_text("❌ Iltimos, video yoki dokument fayl yuboring!")
        return UPLOAD_FILE
    
    context.user_data['file_id'] = file_id
    context.user_data['file_type'] = file_type
    
    await update.message.reply_text("✅ Film qabul qilindi!\n\n📝 Endi film NOMINI yuboring:")
    return GET_NAME

async def receive_film_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    film_name = update.message.text.strip()
    
    if not film_name:
        await update.message.reply_text("❌ Film nomi bo'sh bo'lishi mumkin emas!")
        return GET_NAME
    
    context.user_data['film_name'] = film_name
    
    await update.message.reply_text(f"✅ Film nomi saqlandi: {film_name}\n\n🔢 Endi film KODINI yuboring:")
    return GET_CODE

async def receive_film_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip().upper()
    film_name = context.user_data.get('film_name', 'Noma\'lum')
    
    if not code:
        await update.message.reply_text("❌ Kod bo'sh bo'lishi mumkin emas!")
        return GET_CODE
    
    film_name_sql = safe_sql(film_name)
    code_sql = safe_sql(code)
    
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    try:
        c.execute("SELECT * FROM films WHERE code = ?", (code_sql,))
        if c.fetchone():
            await update.message.reply_text(f"❌ {code} kodi allaqachon mavjud!\nBoshqa kod tanlang.")
            conn.close()
            return GET_CODE
    except Exception as e:
        await update.message.reply_text(f"❌ Bazada xatolik: {str(e)}")
        conn.close()
        return GET_CODE
    
    try:
        file_id = context.user_data['file_id']
        file_type = context.user_data['file_type']
        duration = context.user_data.get('duration', 'Noma\'lum')
        
        film_name_safe = safe_html(film_name)
        code_safe = safe_html(code)
        
        caption = f"""🎬 <b>{film_name_safe}</b>

🔢 <b>Kod:</b> <code>{code_safe}</code>
🎥 <b>Format:</b> {file_type.upper()}
⏱️ <b>Davomiylik:</b> {duration}
📥 <b>Bot:</b> @{context.bot.username}

💾 Filmni olish uchun botga <code>{code_safe}</code> deb yozing."""

        if file_type == "video":
            sent_message = await context.bot.send_video(
                chat_id=CHANNEL_USERNAME,
                video=file_id,
                caption=caption,
                parse_mode=ParseMode.HTML
            )
        elif file_type == "document":
            sent_message = await context.bot.send_document(
                chat_id=CHANNEL_USERNAME,
                document=file_id,
                caption=caption,
                parse_mode=ParseMode.HTML
            )
        
        c.execute("INSERT INTO films (code, name, file_id, file_type, duration, message_id) VALUES (?, ?, ?, ?, ?, ?)",
                  (code_sql, film_name_sql, file_id, file_type, duration, sent_message.message_id))
        conn.commit()
        
        await update.message.reply_text(
            f"✅ <b>Film muvaffaqiyatli qo'shildi!</b>\n\n"
            f"🎬 <b>Nomi:</b> {film_name_safe}\n"
            f"🔢 <b>Kodi:</b> <code>{code_safe}</code>\n"
            f"⏱️ <b>Davomiylik:</b> {duration}\n"
            f"📤 <b>Kanal:</b> {CHANNEL_USERNAME}\n"
            f"🔗 <b>Xabar ID:</b> {sent_message.message_id}",
            parse_mode=ParseMode.HTML
        )
        
    except Exception as e:
        await update.message.reply_text(f"❌ Xatolik yuz berdi: {str(e)}")
    finally:
        conn.close()
    
    context.user_data.clear()
    return ConversationHandler.END

# ========== OTHER HANDLERS ==========
async def list_films(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Siz admin emassiz!")
        return
    
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    try:
        c.execute("SELECT code, name, file_type, duration, date_added FROM films ORDER BY date_added DESC")
        films = c.fetchall()
    except Exception as e:
        await update.message.reply_text(f"❌ Bazada xatolik: {str(e)}")
        conn.close()
        return
    
    conn.close()
    
    if not films:
        await update.message.reply_text("📭 Bazada hech qanday film yo'q.")
        return
    
    films_list = "<b>📋 Bazadagi filmlar:</b>\n\n"
    for film in films:
        code_safe = safe_html(film[0])
        name_safe = safe_html(film[1])
        films_list += f"• <code>{code_safe}</code> - {name_safe} ({film[2]}, {film[3]}) - {film[4][:10]}\n"
    
    if len(films_list) > 4000:
        parts = [films_list[i:i+4000] for i in range(0, len(films_list), 4000)]
        for part in parts:
            await update.message.reply_text(part, parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(films_list, parse_mode=ParseMode.HTML)

async def search_film(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Iltimos, qidirish uchun so'z kiriting!\n\nMisol: /search Inception")
        return
    
    search_term = " ".join(context.args)
    
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    try:
        c.execute("SELECT code, name, file_type, duration FROM films WHERE LOWER(name) LIKE ? OR LOWER(code) LIKE ?",
                  (f"%{search_term.lower()}%", f"%{search_term.upper()}%"))
        results = c.fetchall()
    except Exception as e:
        await update.message.reply_text(f"❌ Bazada xatolik: {str(e)}")
        conn.close()
        return
    
    conn.close()
    
    if not results:
        await update.message.reply_text(f"🔍 '{search_term}' bo'yicha hech narsa topilmadi.")
        return
    
    search_results = f"<b>🔍 Qidiruv natijalari ('{safe_html(search_term)}'):</b>\n\n"
    for result in results:
        code_safe = safe_html(result[0])
        name_safe = safe_html(result[1])
        search_results += f"• <code>{code_safe}</code> - {name_safe} ({result[2]}, {result[3]})\n"
    
    await update.message.reply_text(search_results, parse_mode=ParseMode.HTML)

async def delete_film(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Siz admin emassiz!")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Iltimos, film kodini kiriting!\n\nMisol: /deletefilm H1")
        return
    
    code = safe_sql(context.args[0].upper())
    
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    
    try:
        c.execute("SELECT name, message_id FROM films WHERE code = ?", (code,))
        film = c.fetchone()
        
        if film:
            film_name, message_id = film
            
            try:
                await context.bot.delete_message(
                    chat_id=CHANNEL_USERNAME,
                    message_id=message_id
                )
                channel_deleted = True
            except:
                channel_deleted = False
            
            c.execute("DELETE FROM films WHERE code = ?", (code,))
            conn.commit()
            
            if channel_deleted:
                await update.message.reply_text(
                    f"✅ <b>Film to'liq o'chirildi!</b>\n\n"
                    f"🎬 <b>Nomi:</b> {safe_html(film_name)}\n"
                    f"🔢 <b>Kodi:</b> <code>{safe_html(code)}</code>",
                    parse_mode=ParseMode.HTML
                )
            else:
                await update.message.reply_text(
                    f"⚠️ <b>Film qisman o'chirildi!</b>\n\n"
                    f"🎬 <b>Nomi:</b> {safe_html(film_name)}\n"
                    f"🔢 <b>Kodi:</b> <code>{safe_html(code)}</code>\n\n"
                    f"<i>Kanaldagi postni qo'lda o'chiring.</i>",
                    parse_mode=ParseMode.HTML
                )
        else:
            await update.message.reply_text(
                f"❌ <code>{safe_html(code)}</code> kodi bilan film topilmadi!", 
                parse_mode=ParseMode.HTML
            )
    
    except Exception as e:
        await update.message.reply_text(
            f"❌ Xatolik yuz berdi: {str(e)}",
            parse_mode=ParseMode.HTML
        )
    finally:
        conn.close()

async def send_film_by_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip().upper()
    code_sql = safe_sql(code)
    
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    try:
        c.execute("SELECT name, file_id, file_type, duration FROM films WHERE code = ?", (code_sql,))
        film = c.fetchone()
    except Exception as e:
        await update.message.reply_text(f"❌ Bazada xatolik: {str(e)}")
        conn.close()
        return
    
    conn.close()
    
    if film:
        film_name, file_id, file_type, duration = film
        
        duration_str = duration if duration else "Noma'lum"
        film_name_safe = safe_html(film_name)
        code_safe = safe_html(code)
        
        try:
            if file_type == "video":
                await update.message.reply_video(
                    video=file_id,
                    caption=f"""✅ <b>{film_name_safe}</b>

⏱️ <b>Davomiylik:</b> {duration_str}

🔢 <b>Kod:</b> <code>{code_safe}</code>

📥 <b>Bot:</b> @{context.bot.username}""",
                    parse_mode=ParseMode.HTML
                )
            elif file_type == "document":
                await update.message.reply_document(
                    document=file_id,
                    caption=f"""✅ <b>{film_name_safe}</b>

⏱️ <b>Davomiylik:</b> {duration_str}

🔢 <b>Kod:</b> <code>{code_safe}</code>

📥 <b>Bot:</b> @{context.bot.username}""",
                    parse_mode=ParseMode.HTML
                )
        except Exception as e:
            await update.message.reply_text(f"❌ Film yuborishda xatolik: {str(e)}")
    else:
        await update.message.reply_text(
            f"❌ <code>{code_safe}</code> kodi bilan film topilmadi!",
            parse_mode=ParseMode.HTML
        )

async def cleanup_db(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bazani to'liq tozalash"""
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Siz admin emassiz!")
        return
    
    await update.message.reply_text("⚠️ <b>Baza tozalanmoqda...</b>", parse_mode=ParseMode.HTML)
    
    if init_database():
        await update.message.reply_text(
            "✅ <b>Baza muvaffaqiyatli tozalandi!</b>\n\n"
            "🗄️ <b>Baza:</b> Yangilandi\n"
            "📁 <b>Fayl:</b> films.db qayta yaratildi\n"
            "🔧 <b>Holat:</b> Ishga tayyor",
            parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_text(
            "❌ <b>Bazani tozalashda xatolik!</b>\n\n"
            "films.db faylini qo'lda o'chiring.",
            parse_mode=ParseMode.HTML
        )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Film qo'shish bekor qilindi.")
    context.user_data.clear()
    return ConversationHandler.END

# ========== MAIN FUNCTION ==========
def main():
    """Asosiy funksiya"""
    # Database initialization
    if not init_database():
        logger.error("❌ Failed to initialize database!")
        return
    
    # Create application
    app = Application.builder().token(TOKEN).build()
    
    # Conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('addfilm', add_film_start)],
        states={
            UPLOAD_FILE: [
                MessageHandler(filters.VIDEO, receive_film_file),
                MessageHandler(filters.Document.ALL, receive_film_file),
            ],
            GET_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_film_name)],
            GET_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_film_code)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    # Command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("listfilms", list_films))
    app.add_handler(CommandHandler("search", search_film))
    app.add_handler(CommandHandler("deletefilm", delete_film))
    app.add_handler(CommandHandler("cleanup", cleanup_db))
    app.add_handler(conv_handler)
    
    # Message handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, send_film_by_code))
    
    # Start the bot
    logger.info("🤖 Bot ishga tushdi...")
    logger.info(f"👨‍💻 Admin ID: {ADMIN_ID}")
    logger.info(f"📢 Kanal: {CHANNEL_USERNAME}")
    logger.info(f"🗄️ Baza fayli: {DB_PATH}")
    
    # Railway uchun polling
    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_UPDATES
    )

if __name__ == '__main__':
    main()
