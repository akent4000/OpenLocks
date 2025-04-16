from loguru import logger
logger.add("logs/commands.log", rotation="10 MB", level="INFO")

import datetime
from django.utils import timezone
from telebot.types import Message
from tgbot.dispatcher import bot
from tgbot.models import TelegramUser, Configuration, Task
from tgbot.logics.messages import send_welcome_message
from tgbot.logics.constants import Commands, Urls


@bot.message_handler(commands=[Commands.START])
def handle_start(message: Message):
    try:
        logger.info(f"User {message.chat.id} started the bot.")
        chat_id = message.chat.id

        user, created = TelegramUser.objects.get_or_create(
            chat_id=chat_id,
            defaults={
                'first_name': message.chat.first_name,
                'last_name': message.chat.last_name,
                'username': message.chat.username,
                'can_publish_tasks': Configuration.get_auto_request_permission(),
            }
        )
        if not created and user.username != message.chat.username:
            user.username = message.chat.username
            user.save()

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
        "Админ может ответить в течение нескольких часов.\n"
        f"Если нужна помощь прямо сейчас — напишите [Админу]({Urls.SUPPORT})"
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
    # Получаем начало сегодняшнего дня в локальном времени
    now = timezone.localtime()
    today_start = timezone.make_aware(
        datetime.datetime.combine(now.date(), datetime.time.min),
        timezone.get_current_timezone()
    )
    count = Task.objects.filter(created_at__gte=today_start).count()
    date_str = now.strftime("%d.%m.%Y")
    bot.send_message(
        chat_id=message.chat.id,
        text=f"За {date_str} было отправлено {count} заявок"
    )