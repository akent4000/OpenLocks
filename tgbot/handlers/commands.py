from tgbot.logics.text_helper import *
import datetime
from django.utils import timezone
from telebot.types import Message
from tgbot.dispatcher import bot
from tgbot.models import TelegramUser, Configuration, Task
from tgbot.logics.messages import *
from tgbot.logics.constants import *
from tgbot.logics.keyboards import *
from tgbot.handlers.user_helper import *

from pathlib import Path
from loguru import logger

# Убедимся, что папка logs существует
Path("logs").mkdir(parents=True, exist_ok=True)

# Лог-файл будет называться так же, как модуль, например user_helper.py → logs/user_helper.log
log_filename = Path("logs") / f"{Path(__file__).stem}.log"
logger.add(str(log_filename), rotation="10 MB", level="INFO")

@bot.message_handler(commands=[Commands.START])
def handle_start(message: Message):
    try:
        logger.info(f"User {message.chat.id} started the bot.")
        user, created = sync_user_data(message)
        logger.info(f"User {user} created: {created}")
        send_welcome_message(created=created, user=user)

    except Exception as e:
        logger.exception(e)

@bot.message_handler(commands=[Commands.RULES])
def handle_rules(message: Message):
    """
    Отправляет пользователю ссылку на правила использования.
    """
    bot.send_message(
        chat_id=message.chat.id,
        text=f"Правила использования: {Urls.RULES}"
    )

@bot.message_handler(commands=[Commands.CHAT])
def handle_chat(message: Message):
    """
    Отправляет пользователю ссылку на общий чат.
    """
    bot.send_message(
        chat_id=message.chat.id,
        text=f"Общий чат: {Urls.GENERAL_CHAT}"
    )

@bot.message_handler(commands=[Commands.ADMIN])
def handle_admin(message: Message):
    """
    Информирует пользователя о времени ответа админа и даёт ссылку на поддержку.
    """
    text = (
        f"Админ может ответить в течение нескольких часов.'\n[Админ]({Urls.SUPPORT})"
    )
    bot.send_message(
        chat_id=message.chat.id,
        text=text,
        parse_mode="Markdown"
    )

@bot.message_handler(commands=[Commands.TODAY])
def handle_today(message: Message):
    """
    Показывает, сколько заявок было отправлено с начала сегодняшнего дня.
    """
    now = timezone.localtime()
    today_start = timezone.make_aware(
        datetime.datetime.combine(now.date(), datetime.time.min),
        timezone.get_current_timezone()
    )
    count = Task.objects.filter(created_at__gte=today_start).count()
    date_str = now.strftime("%d.%m.%Y")
    bot.send_message(
        chat_id=message.chat.id,
        text=f"За {date_str} {word_number_case_was(count)} {word_number_case_sent(count)} {word_number_case_tasks(count)}"
    )

#TAGS
# @bot.message_handler(commands=[Commands.TAGS])
# def handle_tags(message: Message):
#     """
#     Обработчик команды /tags — отправляет клавиатуру с доступными тегами.
#     Позволяет подписаться или отписаться от тегов.
#     """
#     user = TelegramUser.objects.filter(chat_id=message.chat.id).first()
#     if not user:
#         bot.send_message(message.chat.id, "Пользователь не найден. Введите /start сначала.")
#         return

#     keyboard = tag_toggle_keyboard(user)
#     if not keyboard:
#         bot.send_message(message.chat.id, "Теги пока не заданы.")
#         return

#     bot.send_message(
#         chat_id=message.chat.id,
#         text="Выберите теги, на которые хотите подписаться или отписаться:",
#         reply_markup=keyboard
#     )