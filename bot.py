import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes
from telegram.ext import filters
import sqlite3
import os

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Константы (теперь через переменные окружения)
TOKEN = os.environ.get("TOKEN")
GROUP_CHAT_ID = os.environ.get("GROUP_CHAT_ID", "-1003031407522")

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS messages
                 (user_id INTEGER, message_id INTEGER, group_message_id INTEGER)''')
    conn.commit()
    conn.close()

# Сохранение связи между сообщениями
def save_message_link(user_id, user_message_id, group_message_id):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("INSERT INTO messages VALUES (?, ?, ?)",
              (user_id, user_message_id, group_message_id))
    conn.commit()
    conn.close()

# Получение user_id и message_id по group_message_id
def get_user_message_data(group_message_id):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("SELECT user_id, message_id FROM messages WHERE group_message_id=?",
              (group_message_id,))
    result = c.fetchone()
    conn.close()
    return result

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    welcome_text = """
   Привет! Рад тебя здесь увидеть🤠👋

• КОНКУРС 
Что бы участвовать в конкурсе на "❤️" в TikTok отправь сюда ссылки на свои видео. Обязательно пишем свой юз тг в начале! 
📆до 28.09 - 20:00. (по мск)
- Формат сообщения:
@ваш_ник:
1) ссылка на видео 1
2) ссылка на видео 2
3) ссылка на видео 3

• АКЦИЯ «ПРИВЕДИ ЧИТАТЕЛЯ»
Если ты участвуешь в акции «приведи читателя» то присылай сюда его ник и свой. Акция действует
📆до 30.11 - 20:00
- Формат сообщения:
@ник_приведенного_чиатетля - @ваш_ник

• ВЫИГРЫШ И ВЫПЛАТА ПРИЗА 🥳💸
После окончания конкурса/акции я свяжусь с вами здесь, в этом чате, для уточнения деталей выплаты.
Все полученные данные (например, номер карты) являются строго конфиденциальными, видны только мне и будут использованы исключительно для перевода вашего выигрыша. После выплаты они будут удалены.
 
• Если у тебя возникли вопросы по поводу конкурса или акции - пиши, рад буду ответить☺️
обо всех условиях конкурса и акции можно прочитать в закрепе тгк: @saaibankrot

А также здесь ты можешь мне задать любой вопрос или просто любое сообщение🙃
(постараюсь ответить как можно скорее))
    """
    await update.message.reply_html(welcome_text)

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
        await update.message.reply_text("✅ ваше сообщение отправленно! пожалуйста, ожидайте ответа от автора🙂‍↕️")

    except Exception as e:
        logger.error(f"Ошибка при пересылке: {e}")
        await update.message.reply_text("😔 Что-то пошло не так. Попробуйте позже.")

# Обработка ответов в группе
async def handle_group_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Проверяем, что сообщение из нужной группы
    if str(update.effective_chat.id) != str(GROUP_CHAT_ID):
        return

    # Проверяем, что это ответ на сообщение
    if not update.message.reply_to_message:
        return

    replied_message_id = update.message.reply_to_message.message_id

    # Ищем данные пользователя
    user_data = get_user_message_data(replied_message_id)

    if user_data:
        user_id, original_message_id = user_data

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

# Основная функция
def main() -> None:
    # Инициализируем базу данных
    init_db()

    # Создаем Application
    application = Application.builder().token(TOKEN).build()

    # Обработчик команды /start
    application.add_handler(CommandHandler("start", start))

    # Обработчик текстовых сообщений от пользователей
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & ~filters.ChatType.GROUPS,
        forward_to_group
    ))

    # Обработчик медиа-сообщений от пользователей
    application.add_handler(MessageHandler(
        filters.PHOTO | filters.Document.ALL | filters.VIDEO | filters.AUDIO,
        forward_to_group
    ))

    # Обработчик ответов в группе (все сообщения в группах)
    application.add_handler(MessageHandler(
        filters.TEXT & filters.ChatType.GROUPS,
        handle_group_reply
    ))

    # Обработчик ошибок
    application.add_error_handler(error_handler)

    # Запускаем бота
    print("Бот запущен и работает...")
    application.run_polling()

if __name__ == '__main__':
    main()
