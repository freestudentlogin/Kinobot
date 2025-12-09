import logging
import os
import re
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from telegram.constants import ParseMode
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

# ========== CONFIGURATION ==========
TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_USERNAME = os.environ.get("CHANNEL_USERNAME")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
DATABASE_URL = os.environ.get("DATABASE_URL")

# Debug uchun
print("=" * 50)
print(f"TOKEN mavjud: {'Ha' if TOKEN else 'Yoq'}")
print(f"CHANNEL_USERNAME: {CHANNEL_USERNAME}")
print(f"ADMIN_ID: {ADMIN_ID}")
print(f"DATABASE_URL mavjud: {'Ha' if DATABASE_URL else 'Yoq'}")
print("=" * 50)

if not TOKEN:
    print("❌ BOT_TOKEN environment variable topilmadi!")
    exit(1)

if not DATABASE_URL:
    print("❌ DATABASE_URL environment variable topilmadi!")
    exit(1)

# ========== BOT CONFIG ==========
UPLOAD_FILE, GET_NAME, GET_CODE = range(3)

# Logging
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
        logger.error(f"Database connection error: {e}")
        print(f"❌ Database connection failed: {e}")
        return None

def init_database():
    """PostgreSQL bazasini yaratish"""
    try:
        conn = get_db_connection()
        if not conn:
            print("❌ Database connection failed")
            return False
        
        cur = conn.cursor()
        
        # Jadvalni yaratish
        cur.execute('''
            CREATE TABLE IF NOT EXISTS films (
                id SERIAL PRIMARY KEY,
                code VARCHAR(50) UNIQUE NOT NULL,
                name TEXT NOT NULL,
                file_id TEXT NOT NULL,
                file_type VARCHAR(20) NOT NULL,
                duration VARCHAR(20),
                message_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Index lar
        cur.execute('CREATE INDEX IF NOT EXISTS idx_films_code ON films(code)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_films_created ON films(created_at DESC)')
        
        conn.commit()
        cur.close()
        conn.close()
        
        print("✅ Database initialized successfully")
        logger.info("Database initialized")
        return True
    except Exception as e:
        print(f"❌ Database initialization error: {e}")
        logger.error(f"Database init error: {e}")
        return False

# ========== HELPER FUNCTIONS ==========
def safe_html(text):
    """HTML uchun xavfsiz matn"""
    if not text:
        return ""
    text = str(text)
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    return text

# ========== DATABASE OPERATIONS ==========
def film_exists(code):
    """Kod mavjudligini tekshirish"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM films WHERE code = %s", (code,))
        exists = cur.fetchone() is not None
        cur.close()
        conn.close()
        return exists
    except Exception as e:
        logger.error(f"Film exists check error: {e}")
        return False

def add_film(code, name, file_id, file_type, duration, message_id):
    """Film qo'shish"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO films (code, name, file_id, file_type, duration, message_id)
            VALUES (%s, %s, %s, %s, %s, %s)
        ''', (code, name, file_id, file_type, duration, message_id))
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Add film error: {e}")
        return False

def get_film(code):
    """Film olish"""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM films WHERE code = %s", (code,))
        film = cur.fetchone()
        cur.close()
        conn.close()
        return film
    except Exception as e:
        logger.error(f"Get film error: {e}")
        return None

def get_all_films():
    """Barcha filmlar"""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM films ORDER BY created_at DESC")
        films = cur.fetchall()
        cur.close()
        conn.close()
        return films
    except Exception as e:
        logger.error(f"Get all films error: {e}")
        return []

def delete_film(code):
    """Film o'chirish"""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Avval filmni olish
        cur.execute("SELECT * FROM films WHERE code = %s", (code,))
        film = cur.fetchone()
        
        if film:
            # Keyin o'chirish
            cur.execute("DELETE FROM films WHERE code = %s", (code,))
            conn.commit()
        
        cur.close()
        conn.close()
        return film
    except Exception as e:
        logger.error(f"Delete film error: {e}")
        return None

# ========== COMMAND HANDLERS ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = f"""🎬 Salom, {user.first_name}!
    
Men film kodlari orqali kinolar topshiradigan botman.

<b>📌 Qanday foydalanish:</b>
1. Film kodini yozing (masalan: <code>1234</code>)
2. Men sizga shu kodli filmni yuboraman

Admin panel: /admin
    """
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Siz admin emassiz!")
        return
    
    text = """<b>⚙️ Admin Panel</b>

📥 Film qo'shish: /addfilm
📊 Filmlar ro'yxati: /listfilms
🔎 Qidirish: /search [nomi]
🗑️ O'chirish: /deletefilm [kod]
📊 Statistika: /stats
    """
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Siz admin emassiz!")
        return
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM films")
        total = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM films WHERE file_type = 'video'")
        videos = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM films WHERE file_type = 'document'")
        documents = cur.fetchone()[0]
        
        cur.close()
        conn.close()
        
        text = f"""<b>📊 Bot Statistikasi</b>

🎬 Jami filmlar: {total} ta
🎥 Videolar: {videos} ta
📄 Dokumentlar: {documents} ta
📢 Kanal: {CHANNEL_USERNAME}
🤖 Host: Railway + PostgreSQL
        """
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"❌ Xatolik: {str(e)}")

# ========== CONVERSATION HANDLERS ==========
async def add_film_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Siz admin emassiz!")
        return ConversationHandler.END
    
    await update.message.reply_text("🎥 Film faylini yuboring (video yoki dokument)...")
    return UPLOAD_FILE

async def receive_film_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.video:
        file_id = update.message.video.file_id
        file_type = "video"
        duration = update.message.video.duration
        mins, secs = divmod(duration, 60)
        hrs, mins = divmod(mins, 60)
        duration_str = f"{hrs}:{mins:02d}:{secs:02d}" if hrs > 0 else f"{mins}:{secs:02d}"
        context.user_data['duration'] = duration_str
    elif update.message.document:
        file_id = update.message.document.file_id
        file_type = "document"
        context.user_data['duration'] = "Dokument"
    else:
        await update.message.reply_text("❌ Video yoki dokument yuboring!")
        return UPLOAD_FILE
    
    context.user_data['file_id'] = file_id
    context.user_data['file_type'] = file_type
    
    await update.message.reply_text("✅ Fayl qabul qilindi!\n\n📝 Film nomini yuboring:")
    return GET_NAME

async def receive_film_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    film_name = update.message.text.strip()
    if not film_name:
        await update.message.reply_text("❌ Nom bo'sh bo'lmasligi kerak!")
        return GET_NAME
    
    context.user_data['film_name'] = film_name
    await update.message.reply_text(f"✅ Nom saqlandi: {film_name}\n\n🔢 Film kodini yuboring:")
    return GET_CODE

async def receive_film_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip().upper()
    film_name = context.user_data.get('film_name', 'Noma\'lum')
    
    if not code:
        await update.message.reply_text("❌ Kod bo'sh bo'lmasligi kerak!")
        return GET_CODE
    
    if film_exists(code):
        await update.message.reply_text(f"❌ {code} kodi allaqachon mavjud!")
        return GET_CODE
    
    try:
        file_id = context.user_data['file_id']
        file_type = context.user_data['file_type']
        duration = context.user_data.get('duration', 'Noma\'lum')
        
        # Kanalga yuborish
        caption = f"""🎬 <b>{safe_html(film_name)}</b>

🔢 <b>Kod:</b> <code>{safe_html(code)}</code>
🎥 <b>Format:</b> {file_type.upper()}
⏱️ <b>Davomiylik:</b> {duration}
📥 <b>Bot:</b> @{context.bot.username}

💾 Filmni olish uchun botga <code>{safe_html(code)}</code> deb yozing."""
        
        if file_type == "video":
            sent = await context.bot.send_video(
                chat_id=CHANNEL_USERNAME,
                video=file_id,
                caption=caption,
                parse_mode=ParseMode.HTML
            )
        else:
            sent = await context.bot.send_document(
                chat_id=CHANNEL_USERNAME,
                document=file_id,
                caption=caption,
                parse_mode=ParseMode.HTML
            )
        
        # Bazaga saqlash
        if add_film(code, film_name, file_id, file_type, duration, sent.message_id):
            await update.message.reply_text(
                f"✅ <b>Film qo'shildi!</b>\n\n"
                f"🎬 Nomi: {safe_html(film_name)}\n"
                f"🔢 Kodi: <code>{safe_html(code)}</code>\n"
                f"📢 Kanal: {CHANNEL_USERNAME}",
                parse_mode=ParseMode.HTML
            )
        else:
            await update.message.reply_text("❌ Bazaga saqlashda xatolik!")
    
    except Exception as e:
        await update.message.reply_text(f"❌ Xatolik: {str(e)}")
    
    context.user_data.clear()
    return ConversationHandler.END

# ========== OTHER HANDLERS ==========
async def list_films(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Siz admin emassiz!")
        return
    
    films = get_all_films()
    if not films:
        await update.message.reply_text("📭 Hech qanday film yo'q.")
        return
    
    text = "<b>📋 Filmlar ro'yxati:</b>\n\n"
    for film in films:
        text += f"• <code>{safe_html(film['code'])}</code> - {safe_html(film['name'])}\n"
    
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def send_film_by_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip().upper()
    film = get_film(code)
    
    if not film:
        await update.message.reply_text(f"❌ <code>{safe_html(code)}</code> kodi bilan film topilmadi!")
        return
    
    try:
        if film['file_type'] == "video":
            await update.message.reply_video(
                video=film['file_id'],
                caption=f"""✅ <b>{safe_html(film['name'])}</b>

⏱️ <b>Davomiylik:</b> {film['duration']}

🔢 <b>Kod:</b> <code>{safe_html(film['code'])}</code>

📥 <b>Bot:</b> @{context.bot.username}""",
                parse_mode=ParseMode.HTML
            )
        else:
            await update.message.reply_document(
                document=film['file_id'],
                caption=f"""✅ <b>{safe_html(film['name'])}</b>

⏱️ <b>Davomiylik:</b> {film['duration']}

🔢 <b>Kod:</b> <code>{safe_html(film['code'])}</code>

📥 <b>Bot:</b> @{context.bot.username}""",
                parse_mode=ParseMode.HTML
            )
    except Exception as e:
        await update.message.reply_text(f"❌ Film yuborishda xatolik: {str(e)}")

async def delete_film_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Siz admin emassiz!")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Kodni kiriting!\nMasalan: /deletefilm H1")
        return
    
    code = context.args[0].upper()
    film = delete_film(code)
    
    if film:
        try:
            await context.bot.delete_message(
                chat_id=CHANNEL_USERNAME,
                message_id=film['message_id']
            )
            await update.message.reply_text(f"✅ <code>{safe_html(code)}</code> kodi bilan film o'chirildi!", parse_mode=ParseMode.HTML)
        except:
            await update.message.reply_text(
                f"⚠️ Film bazadan o'chirildi, lekin kanaldan o'chirish mumkin emas.\n"
                f"Kanalda qo'lda o'chiring: {CHANNEL_USERNAME}",
                parse_mode=ParseMode.HTML
            )
    else:
        await update.message.reply_text(f"❌ <code>{safe_html(code)}</code> kodi bilan film topilmadi!", parse_mode=ParseMode.HTML)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Bekor qilindi.")
    context.user_data.clear()
    return ConversationHandler.END

# ========== MAIN ==========
def main():
    print("🚀 Bot ishga tushmoqda...")
    
    # Database initialization
    if not init_database():
        print("❌ Database initialization failed!")
        return
    
    # Bot application
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
    
    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("listfilms", list_films))
    app.add_handler(CommandHandler("deletefilm", delete_film_cmd))
    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, send_film_by_code))
    
    # Start
    print("🤖 Bot ishga tushdi!")
    print(f"📢 Kanal: {CHANNEL_USERNAME}")
    print(f"👑 Admin ID: {ADMIN_ID}")
    
    app.run_polling()

if __name__ == '__main__':
    main()
