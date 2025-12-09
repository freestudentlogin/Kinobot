import logging
import os
import re
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from telegram.constants import ParseMode
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

# ========== RAILWAY CONFIGURATION ==========
TOKEN = os.environ.get("BOT_TOKEN", "8071915816:AAE6VGglu3WBnxXtu3_UZfYJ8prVhvqVRSo")
CHANNEL_USERNAME = os.environ.get("CHANNEL_USERNAME", "@uzkinolarbot_manba")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "7901013364"))

# PostgreSQL connection - Railway automatik yaratadi
DATABASE_URL = os.environ.get("DATABASE_URL")

# ========== BOT CONFIGURATION ==========
UPLOAD_FILE, GET_NAME, GET_CODE = range(3)

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ========== DATABASE FUNCTIONS ==========
def get_db_connection():
    """PostgreSQL ulanishini olish"""
    try:
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        return conn
    except Exception as e:
        logger.error(f"❌ Database connection error: {e}")
        return None

def init_database():
    """PostgreSQL bazasini yaratish/yuklash"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
        
        cur = conn.cursor()
        
        # Films jadvalini yaratish
        cur.execute('''
            CREATE TABLE IF NOT EXISTS films (
                id SERIAL PRIMARY KEY,
                code VARCHAR(50) UNIQUE NOT NULL,
                name TEXT NOT NULL,
                file_id TEXT NOT NULL,
                file_type VARCHAR(20) NOT NULL,
                duration VARCHAR(20),
                message_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Index yaratish tez qidirish uchun
        cur.execute('CREATE INDEX IF NOT EXISTS idx_films_code ON films(code)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_films_name ON films(name)')
        
        conn.commit()
        cur.close()
        conn.close()
        
        logger.info("✅ PostgreSQL database initialized successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Database initialization error: {e}")
        return False

# ========== HELPER FUNCTIONS ==========
def safe_sql(text):
    """SQL uchun xavfsiz matn yaratish"""
    if text is None:
        return ""
    
    text = str(text)
    text = text.replace("'", "''")
    text = text.replace('"', '""')
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

# ========== DATABASE OPERATIONS ==========
def add_film_to_db(code, name, file_id, file_type, duration, message_id):
    """Filmni bazaga qo'shish"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
        
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO films (code, name, file_id, file_type, duration, message_id)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (code) DO NOTHING
        ''', (code, name, file_id, file_type, duration, message_id))
        
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"❌ Add film error: {e}")
        return False

def get_film_by_code(code):
    """Kod bo'yicha filmni olish"""
    try:
        conn = get_db_connection()
        if not conn:
            return None
        
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute('SELECT * FROM films WHERE code = %s', (code,))
        film = cur.fetchone()
        
        cur.close()
        conn.close()
        return film
    except Exception as e:
        logger.error(f"❌ Get film error: {e}")
        return None

def delete_film_from_db(code):
    """Filmini bazadan o'chirish"""
    try:
        conn = get_db_connection()
        if not conn:
            return None
        
        cur = conn.cursor(cursor_factory=RealDictCursor)
        # Avval filmni olish
        cur.execute('SELECT * FROM films WHERE code = %s', (code,))
        film = cur.fetchone()
        
        if film:
            # Keyin o'chirish
            cur.execute('DELETE FROM films WHERE code = %s', (code,))
            conn.commit()
        
        cur.close()
        conn.close()
        return film
    except Exception as e:
        logger.error(f"❌ Delete film error: {e}")
        return None

def get_all_films():
    """Barcha filmlarni olish"""
    try:
        conn = get_db_connection()
        if not conn:
            return []
        
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute('SELECT * FROM films ORDER BY created_at DESC')
        films = cur.fetchall()
        
        cur.close()
        conn.close()
        return films
    except Exception as e:
        logger.error(f"❌ Get all films error: {e}")
        return []

def search_films_in_db(search_term):
    """Filmlarni qidirish"""
    try:
        conn = get_db_connection()
        if not conn:
            return []
        
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute('''
            SELECT * FROM films 
            WHERE LOWER(name) LIKE %s OR LOWER(code) LIKE %s
            ORDER BY created_at DESC
        ''', (f'%{search_term.lower()}%', f'%{search_term.upper()}%'))
        
        results = cur.fetchall()
        cur.close()
        conn.close()
        return results
    except Exception as e:
        logger.error(f"❌ Search films error: {e}")
        return []

def get_film_stats():
    """Film statistikasi"""
    try:
        conn = get_db_connection()
        if not conn:
            return {"total": 0, "videos": 0, "documents": 0}
        
        cur = conn.cursor()
        
        # Umumiy son
        cur.execute('SELECT COUNT(*) FROM films')
        total = cur.fetchone()[0]
        
        # Video soni
        cur.execute("SELECT COUNT(*) FROM films WHERE file_type = 'video'")
        videos = cur.fetchone()[0]
        
        # Dokument soni
        cur.execute("SELECT COUNT(*) FROM films WHERE file_type = 'document'")
        documents = cur.fetchone()[0]
        
        cur.close()
        conn.close()
        
        return {
            "total": total,
            "videos": videos,
            "documents": documents
        }
    except Exception as e:
        logger.error(f"❌ Get stats error: {e}")
        return {"total": 0, "videos": 0, "documents": 0}

def clear_database():
    """Bazani tozalash"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
        
        cur = conn.cursor()
        cur.execute('DELETE FROM films')
        conn.commit()
        
        cur.close()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"❌ Clear database error: {e}")
        return False

# ========== COMMAND HANDLERS ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Siz admin emassiz!")
        return
    
    stats_data = get_film_stats()
    
    stats_text = f"""<b>📊 Bot Statistikasi</b>

🎬 <b>Jami filmlar:</b> {stats_data['total']} ta
🎥 <b>Videolar:</b> {stats_data['videos']} ta
📄 <b>Dokumentlar:</b> {stats_data['documents']} ta
📢 <b>Kanal:</b> {CHANNEL_USERNAME}
👑 <b>Admin:</b> {ADMIN_ID}
🤖 <b>Host:</b> Railway + PostgreSQL
🔄 <b>Holat:</b> Faol
    """
    await update.message.reply_text(stats_text, parse_mode=ParseMode.HTML)

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
    
    # Kod allaqachon mavjudligini tekshirish
    existing_film = get_film_by_code(code)
    if existing_film:
        await update.message.reply_text(f"❌ {code} kodi allaqachon mavjud!\nBoshqa kod tanlang.")
        return GET_CODE
    
    # Filmni kanalga joylash
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
        
        # Bazaga saqlash
        success = add_film_to_db(code, film_name, file_id, file_type, duration, sent_message.message_id)
        
        if success:
            await update.message.reply_text(
                f"✅ <b>Film muvaffaqiyatli qo'shildi!</b>\n\n"
                f"🎬 <b>Nomi:</b> {film_name_safe}\n"
                f"🔢 <b>Kodi:</b> <code>{code_safe}</code>\n"
                f"⏱️ <b>Davomiylik:</b> {duration}\n"
                f"📤 <b>Kanal:</b> {CHANNEL_USERNAME}\n"
                f"🔗 <b>Xabar ID:</b> {sent_message.message_id}\n"
                f"🗄️ <b>Baza:</b> PostgreSQL",
                parse_mode=ParseMode.HTML
            )
        else:
            await update.message.reply_text("❌ Bazaga saqlashda xatolik!")
        
    except Exception as e:
        await update.message.reply_text(f"❌ Xatolik yuz berdi: {str(e)}")
    
    context.user_data.clear()
    return ConversationHandler.END

# ========== OTHER HANDLERS ==========
async def list_films(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Siz admin emassiz!")
        return
    
    films = get_all_films()
    
    if not films:
        await update.message.reply_text("📭 Bazada hech qanday film yo'q.")
        return
    
    films_list = "<b>📋 Bazadagi filmlar:</b>\n\n"
    for film in films:
        code_safe = safe_html(film['code'])
        name_safe = safe_html(film['name'])
        created_at = film['created_at'].strftime('%Y-%m-%d') if film['created_at'] else "Noma'lum"
        films_list += f"• <code>{code_safe}</code> - {name_safe} ({film['file_type']}, {film['duration']}) - {created_at}\n"
    
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
    results = search_films_in_db(search_term)
    
    if not results:
        await update.message.reply_text(f"🔍 '{search_term}' bo'yicha hech narsa topilmadi.")
        return
    
    search_results = f"<b>🔍 Qidiruv natijalari ('{safe_html(search_term)}'):</b>\n\n"
    for result in results:
        code_safe = safe_html(result['code'])
        name_safe = safe_html(result['name'])
        search_results += f"• <code>{code_safe}</code> - {name_safe} ({result['file_type']}, {result['duration']})\n"
    
    await update.message.reply_text(search_results, parse_mode=ParseMode.HTML)

async def delete_film(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Siz admin emassiz!")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Iltimos, film kodini kiriting!\n\nMisol: /deletefilm H1")
        return
    
    code = context.args[0].upper()
    
    # Bazadan filmni o'chirish
    film = delete_film_from_db(code)
    
    if film:
        # Kanaldan o'chirish
        try:
            await context.bot.delete_message(
                chat_id=CHANNEL_USERNAME,
                message_id=film['message_id']
            )
            channel_deleted = True
        except:
            channel_deleted = False
        
        film_name_safe = safe_html(film['name'])
        code_safe = safe_html(code)
        
        if channel_deleted:
            await update.message.reply_text(
                f"✅ <b>Film to'liq o'chirildi!</b>\n\n"
                f"🎬 <b>Nomi:</b> {film_name_safe}\n"
                f"🔢 <b>Kodi:</b> <code>{code_safe}</code>\n"
                f"🗄️ <b>Baza:</b> PostgreSQL dan o'chirildi",
                parse_mode=ParseMode.HTML
            )
        else:
            await update.message.reply_text(
                f"⚠️ <b>Film qisman o'chirildi!</b>\n\n"
                f"🎬 <b>Nomi:</b> {film_name_safe}\n"
                f"🔢 <b>Kodi:</b> <code>{code_safe}</code>\n"
                f"🗄️ <b>Baza:</b> PostgreSQL dan o'chirildi\n\n"
                f"<i>Kanaldagi postni qo'lda o'chiring.</i>",
                parse_mode=ParseMode.HTML
            )
    else:
        await update.message.reply_text(
            f"❌ <code>{safe_html(code)}</code> kodi bilan film topilmadi!", 
            parse_mode=ParseMode.HTML
        )

async def send_film_by_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip().upper()
    
    film = get_film_by_code(code)
    
    if film:
        film_name_safe = safe_html(film['name'])
        code_safe = safe_html(code)
        duration_str = film['duration'] if film['duration'] else "Noma'lum"
        
        try:
            if film['file_type'] == "video":
                await update.message.reply_video(
                    video=film['file_id'],
                    caption=f"""✅ <b>{film_name_safe}</b>

⏱️ <b>Davomiylik:</b> {duration_str}

🔢 <b>Kod:</b> <code>{code_safe}</code>

📥 <b>Bot:</b> @{context.bot.username}""",
                    parse_mode=ParseMode.HTML
                )
            elif film['file_type'] == "document":
                await update.message.reply_document(
                    document=film['file_id'],
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
            f"❌ <code>{safe_html(code)}</code> kodi bilan film topilmadi!",
            parse_mode=ParseMode.HTML
        )

async def cleanup_db(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Siz admin emassiz!")
        return
    
    await update.message.reply_text("⚠️ <b>Baza tozalanmoqda...</b>", parse_mode=ParseMode.HTML)
    
    if clear_database():
        await update.message.reply_text(
            "✅ <b>Baza muvaffaqiyatli tozalandi!</b>\n\n"
            "🗄️ <b>Baza:</b> PostgreSQL tozalandi\n"
            "🔧 <b>Holat:</b> Ishga tayyor",
            parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_text(
            "❌ <b>Bazani tozalashda xatolik!</b>",
            parse_mode=ParseMode.HTML
        )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Film qo'shish bekor qilindi.")
    context.user_data.clear()
    return ConversationHandler.END

# ========== MAIN FUNCTION ==========
def main():
    # Database initialization
    if not init_database():
        logger.error("❌ Failed to initialize PostgreSQL database!")
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
    logger.info("🤖 Bot PostgreSQL bilan ishga tushdi...")
    logger.info(f"👨‍💻 Admin ID: {ADMIN_ID}")
    logger.info(f"📢 Kanal: {CHANNEL_USERNAME}")
    logger.info(f"🗄️ Database: PostgreSQL")
    
    # Railway uchun polling
    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_UPDATES
    )

if __name__ == '__main__':
    main()
