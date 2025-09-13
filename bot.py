import logging
import sqlite3
import os
from contextlib import closing
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Константы
TOKEN = os.environ.get("BOT_TOKEN", "8369190866:AAE1G2UHoA1lErQvE4iw7L0s21Alkc5Otak")
GROUP_CHAT_ID = os.environ.get("GROUP_CHAT_ID", "-1003031407522")
DB_NAME = 'bot_data.db'

# Создаем Flask приложение
app = Flask(__name__)

@app.route('/')
def home():
    return "Бот работает и готов к приему сообщений!"

@app.route('/health')
def health():
    return "OK", 200

# Утилиты для работы с базой данных
def get_db_connection():
    """Создает и возвращает соединение с базой данных"""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Инициализация базы данных"""
    with closing(get_db_connection()) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS messages
                     (user_id INTEGER, message_id INTEGER, group_message_id INTEGER)''')
        conn.commit()

def save_message_link(user_id, user_message_id, group_message_id):
    """Сохранение связи между сообщениями"""
    with closing(get_db_connection()) as conn:
        conn.execute("INSERT INTO messages VALUES (?, ?, ?)",
                  (user_id, user_message_id, group_message_id))
        conn.commit()

def get_user_message_data(group_message_id):
    """Получение user_id и message_id по group_message_id"""
    with closing(get_db_connection()) as conn:
        result = conn.execute(
            "SELECT user_id, message_id FROM messages WHERE group_message_id=?",
            (group_message_id,)
        ).fetchone()
        return (result['user_id'], result['message_id']) if result else (None, None)

# Текстовые константы
WELCOME_TEXT = """Привет! Рад тебя здесь увидеть🤠👋

• КОНКУРС Что бы участвовать в конкурсе на "❤️" в TikTok отправь сюда ссылки на свои видео. 
Обязательно пишем свой юз тг в начале! 📆до 28.09 - 20:00. (по мск)

- Формат сообщения:
@ваш_ник:
1) ссылка на видео 1
2) ссылка на видео 2
3) ссылка на видео 3

• АКЦИЯ «ПРИВЕДИ ЧИТАТЕЛЯ»
Если ты участвуешь в акции «приведи читателя» то присылай сюда его ник и свой. 
Акция действует📆до 30.11 - 20:00

- Формат сообщения:
@ник_приведенного_читателя - @ваш_ник

• ВЫИГРЫШ И ВЫПЛАТА ПРИЗА 🥳💸
После окончания конкурса/акции я свяжусь с вами здесь, в этом чате, для уточнения деталей выплаты.
Все полученные данные (например, номер карты) являются строго конфиденциальными, 
видны только мне и будут использованы исключительно для перевода вашего выигрыша. 
После выплаты они будут удалены.

• Если у тебя возникли вопросы по поводу конкурса или акции - пиши, рад буду ответить☺️
обо всех условиях конкурса и акции можно прочитать в закрепе тгк: @saaibankrot

А также здесь ты можешь мне задать любой вопрос или просто любое сообщение🙃
(постараюсь ответить как можно скорее))"""

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_html(WELCOME_TEXT)

# Пересылка сообщений от пользователя в группу
async def forward_to_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    user_info = f"@{user.username}" if user.username else f"{user.first_name} {user.last_name or ''} (ID: {user.id})"
    caption = f"📨 Сообщение от: {user_info}\n\n"
    
    try:
        # Отправляем заголовок
        await context.bot.send_message(chat_id=GROUP_CHAT_ID, text=caption)
        # Пересылаем сообщение
        forwarded_msg = await update.message.forward(chat_id=GROUP_CHAT_ID)
        # Сохраняем связь между сообщениями
        save_message_link(user.id, update.message.message_id, forwarded_msg.message_id)
        # Подтверждение пользователю
        await update.message.reply_text("✅ ваше сообщение отправлено! пожалуйста, ожидайте ответа от автора🙂‍↕️")
    except Exception as e:
        logger.error(f"Ошибка при пересылке: {e}")
        await update.message.reply_text("😔 Что-то пошло не так. Попробуйте позже.")

# Обработка ответов в группе
async def handle_group_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Проверяем, что сообщение из нужной группы и это ответ на сообщение
    if (str(update.effective_chat.id) != str(GROUP_CHAT_ID) or 
        not update.message.reply_to_message):
        return
        
    replied_message_id = update.message.reply_to_message.message_id
    
    # Ищем данные пользователя
    user_id, original_message_id = get_user_message_data(replied_message_id)
    if user_id:
        # Отправляем ответ пользователю
        reply_text = f"✨ответ от автора:\n\n{update.message.text}"
        await context.bot.send_message(chat_id=user_id, text=reply_text)
        # Уведомляем в группе об успешной отправке
        await update.message.reply_text("✅ Ответ отправлен читателю!")
    else:
        await update.message.reply_text("❌ Не удалось найти читателя для ответа.")

# Обработка ошибок
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f"Ошибка при обработке обновления {update}: {context.error}")

# Фильтр для приватных сообщений (не групп)
PRIVATE_FILTER = filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE
MEDIA_FILTER = (filters.PHOTO | filters.Document.ALL | 
                filters.VIDEO | filters.AUDIO) & filters.ChatType.PRIVATE

# Функция для запуска бота
def run_bot():
    """Запуск бота"""
    # Инициализируем базу данных
    init_db()
    
    # Создаем Application
    application = Application.builder().token(TOKEN).build()
    
    # Добавляем обработчики
    handlers = [
        CommandHandler("start", start),
        MessageHandler(PRIVATE_FILTER, forward_to_group),
        MessageHandler(MEDIA_FILTER, forward_to_group),
        MessageHandler(filters.TEXT & filters.ChatType.GROUPS, handle_group_reply)
    ]
    
    for handler in handlers:
        application.add_handler(handler)
    
    # Обработчик ошибок
    application.add_error_handler(error_handler)
    
    # Запускаем бота в режиме polling
    logger.info("Бот запущен и работает...")
    application.run_polling()

if __name__ == '__main__':
    run_bot()




from flask import Flask
import os

app = Flask(__name__)
port = int(os.environ.get('PORT', 4000))

@app.route('/')
def hello_world():
    return 'Hello World!'

if __name__ == '__main__':
    print(f'Example app listening on port {port}')
    app.run(host='0.0.0.0', port=port)
