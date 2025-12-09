import logging
import sqlite3
import re
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from telegram.constants import ParseMode

# 1. TOKEN ni @BotFather dan olingan token bilan almashtiring
TOKEN = "8071915816:AAE6VGglu3WBnxXtu3_UZfYJ8prVhvqVRSo"

# 2. KANAL USERNAME ni o'z kanalingiz bilan almashtiring
CHANNEL_USERNAME = "@uzkinolarbot_manba"

# 3. Admin ID raqamingizni qo'shing
ADMIN_ID = 7901013364  # O'z ID raqamingizni qo'ying

# 4. Holatlar (states) - ENDI 3 TA BOSQICH
UPLOAD_FILE, GET_NAME, GET_CODE = range(3)

# 5. SQL uchun xavfsiz matn yaratish (YANGI VA MUHIM)
def safe_sql(text):
    """SQL uchun xavfsiz matn yaratish"""
    if text is None:
        return ""
    
    text = str(text)
    # SQL maxsus belgilarini tozalash
    text = text.replace("'", "''")  # Bitta qo'shtirnoqni ikkita qilish
    text = text.replace('"', '""')  # Qo'shtirnoqlarni ikkita qilish
    text = text.replace(';', '')    # Semicolon ni o'chirish
    text = text.replace('--', '')   # Comment ni o'chirish
    text = text.replace('#', '№')   # Hash ni boshqa belgiga almashtirish
    text = text.replace('%', '%%')  # Procent belgisini ikkita qilish
    text = text.replace('_', '\_')  # Underscore ni escape qilish
    
    # SQL injection uchun boshqa xavfli belgilar
    text = re.sub(r'[\x00-\x1F\x7F]', '', text)  # Kontrol belgilarini o'chirish
    
    return text.strip()

# 6. HTML uchun xavfsiz matn yaratish
def safe_html(text):
    """HTML uchun xavfsiz matn yaratish"""
    if text is None:
        return ""
    
    text = str(text)
    # HTML maxsus belgilarini escape qilish
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    text = text.replace('"', '&quot;')
    text = text.replace("'", '&#39;')
    
    return text

# 7. Ma'lumotlar bazasini yaratish (YANGILANDI)
def init_database():
    try:
        conn = sqlite3.connect('films.db', check_same_thread=False)
        c = conn.cursor()
        
        # Tozalash: eski jadvalni o'chirish
        c.execute("DROP TABLE IF EXISTS films")
        
        # Yangi jadval yaratish
        c.execute('''CREATE TABLE films
                     (code TEXT PRIMARY KEY, 
                      name TEXT,
                      file_id TEXT,
                      file_type TEXT,
                      duration TEXT,
                      message_id INTEGER,
                      date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        
        conn.commit()
        conn.close()
        print("✅ Yangi films.db bazasi yaratildi")
        return True
    except Exception as e:
        print(f"❌ Bazani yaratishda xatolik: {e}")
        return False

# 8. Start komandasi
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

# 9. Admin panel
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

<i>Misol:</i>
/search Avatar
/deletefilm H1
    """
    await update.message.reply_text(admin_text, parse_mode=ParseMode.HTML)

# 10. Film qo'shishni boshlash
async def add_film_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Siz admin emassiz!")
        return ConversationHandler.END
    
    await update.message.reply_text("🎥 Iltimos, film faylini yuboring.")
    return UPLOAD_FILE

# 11. Filmni qabul qilish
async def receive_film_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Fayl turini aniqlash
    if update.message.video:
        file_id = update.message.video.file_id
        file_type = "video"
        duration = update.message.video.duration
        # Durationni soat:daqiqa formatiga o'tkazish
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
    
    # Fayl ma'lumotlarini contextga saqlash
    context.user_data['file_id'] = file_id
    context.user_data['file_type'] = file_type
    
    await update.message.reply_text("✅ Film qabul qilindi!\n\n📝 Endi film NOMINI yuboring:")
    return GET_NAME

# 12. Film nomini qabul qilish
async def receive_film_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    film_name = update.message.text.strip()
    
    if not film_name:
        await update.message.reply_text("❌ Film nomi bo'sh bo'lishi mumkin emas!")
        return GET_NAME
    
    context.user_data['film_name'] = film_name
    
    await update.message.reply_text(f"✅ Film nomi saqlandi: {film_name}\n\n🔢 Endi film KODINI yuboring:")
    return GET_CODE

# 13. Film kodini qabul qilish va kanalga joylash
async def receive_film_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip().upper()
    film_name = context.user_data.get('film_name', 'Noma\'lum')
    
    # Kodni tekshirish
    if not code:
        await update.message.reply_text("❌ Kod bo'sh bo'lishi mumkin emas!")
        return GET_CODE
    
    # SQL uchun xavfsiz qilish
    film_name_sql = safe_sql(film_name)
    code_sql = safe_sql(code)
    
    # Bazada kod borligini tekshirish
    conn = sqlite3.connect('films.db', check_same_thread=False)
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
    
    # Filmni kanalga joylash
    try:
        file_id = context.user_data['file_id']
        file_type = context.user_data['file_type']
        duration = context.user_data.get('duration', 'Noma\'lum')
        
        # Matnlarni tozalash
        film_name_safe = safe_html(film_name)
        code_safe = safe_html(code)
        
        # Kanal uchun chiroyli caption yaratish
        caption = f"""🎬 <b>{film_name_safe}</b>

🔢 <b>Kod:</b> <code>{code_safe}</code>
🎥 <b>Format:</b> {file_type.upper()}
⏱️ <b>Davomiylik:</b> {duration}
📥 <b>Bot:</b> @{context.bot.username}

💾 Filmni olish uchun botga <code>{code_safe}</code> deb yozing."""

        # Kanalga yuborish
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
        
        # Bazaga saqlash (parametrli query bilan)
        c.execute("INSERT INTO films (code, name, file_id, file_type, duration, message_id) VALUES (?, ?, ?, ?, ?, ?)",
                  (code_sql, film_name_sql, file_id, file_type, duration, sent_message.message_id))
        conn.commit()
        
        # Admin ga javob
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
    
    # User data ni tozalash
    context.user_data.clear()
    return ConversationHandler.END

# 14. Bazadagi filmlar ro'yxati
async def list_films(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Siz admin emassiz!")
        return
    
    conn = sqlite3.connect('films.db', check_same_thread=False)
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

# 15. Film qidirish
async def search_film(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Iltimos, qidirish uchun so'z kiriting!\n\nMisol: /search Inception")
        return
    
    search_term = " ".join(context.args)
    
    conn = sqlite3.connect('films.db', check_same_thread=False)
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

# 16. Film o'chirish
async def delete_film(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Siz admin emassiz!")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Iltimos, film kodini kiriting!\n\nMisol: /deletefilm H1")
        return
    
    code = safe_sql(context.args[0].upper())
    
    conn = sqlite3.connect('films.db', check_same_thread=False)
    c = conn.cursor()
    
    try:
        # Avval film ma'lumotlarini olish
        c.execute("SELECT name, message_id FROM films WHERE code = ?", (code,))
        film = c.fetchone()
        
        if film:
            film_name, message_id = film
            
            # Kanaldan o'chirish
            try:
                await context.bot.delete_message(
                    chat_id=CHANNEL_USERNAME,
                    message_id=message_id
                )
                channel_deleted = True
            except:
                channel_deleted = False
            
            # Bazadan o'chirish
            c.execute("DELETE FROM films WHERE code = ?", (code,))
            conn.commit()
            
            # Javob yuborish
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

# 17. Foydalanuvchi kod yozganda film yuborish
async def send_film_by_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip().upper()
    code_sql = safe_sql(code)
    
    # Bazadan filmni qidirish
    conn = sqlite3.connect('films.db', check_same_thread=False)
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
        
        # Durationni aniqlash
        duration_str = duration if duration else "Noma'lum"
        
        # Matnlarni tozalash
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

# 18. Bazani tozalash
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

# 19. Conversation cancel
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Film qo'shish bekor qilindi.")
    context.user_data.clear()
    return ConversationHandler.END

# 20. Asosiy funksiya
def main():
    # Ma'lumotlar bazasini yaratish
    if not init_database():
        print("❌ Bazani yaratishda xatolik!")
        return
    
    # Bot ilovasini yaratish
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
    
    # Handlerlarni qo'shish
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("listfilms", list_films))
    app.add_handler(CommandHandler("search", search_film))
    app.add_handler(CommandHandler("deletefilm", delete_film))
    app.add_handler(CommandHandler("cleanup", cleanup_db))
    app.add_handler(conv_handler)
    
    # Matnli xabarlarni qayta ishlash
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, send_film_by_code))
    
    # Botni ishga tushirish
    print("🤖 Bot ishga tushdi...")
    print(f"👨‍💻 Admin ID: {ADMIN_ID}")
    print(f"📢 Kanal: {CHANNEL_USERNAME}")
    
    app.run_polling()

if __name__ == '__main__':
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
    
    try:
        main()
    except Exception as e:
        print(f"❌ Botda xatolik: {e}")
        print("Bot to'xtatildi.")
