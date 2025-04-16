import re
import subprocess

import os
import time

from loguru import logger
logger.add("logs/commands.log", rotation="10 MB", level="INFO")

from telebot.types import Message
from tgbot.dispatcher import bot
from tgbot.models import TelegramUser, Configuration
from tgbot.logics.messages import send_welcome_message

@bot.message_handler(commands=['start'])
def handle_start(message: Message):
    """Обработчик команды /start."""
    try:
        logger.info(f"User {message.chat.id} started the bot.")
        chat_id = message.chat.id

        # разбираем referrer, создаём/обновляем пользователя
        args = message.text.split()
        referrer_id = int(args[1]) if len(args) > 1 else None
        referrer = None
        if referrer_id:
            referrer = TelegramUser.objects.filter(chat_id=referrer_id).first()
            logger.info(f"Referrer: {referrer}")

        user, created = TelegramUser.objects.get_or_create(
            chat_id=chat_id,
            defaults={
                'first_name': message.chat.first_name,
                'last_name': message.chat.last_name,
                'username': message.chat.username,
                'can_publish_tasks': Configuration.get_auto_request_permission(),
            }
        )
        # Если уже был юзер, обновим username на случай, если он появился
        if not created and user.username != message.chat.username:
            user.username = message.chat.username
            user.save()

        logger.info(f"User {user} created: {created}")

        # --- НОВАЯ ПРОВЕРКА PRIVACY & USERNAME ---

        # 1) Пересылаем ему его же /start
        fwd_msg = bot.forward_message(chat_id, chat_id, message.message_id)
        # 2) Смотрим, есть ли у пересланного сообщения поле forward_from
        forbidden = fwd_msg.forward_from is None
        # 3) Удаляем это пересланное сообщение
        bot.delete_message(chat_id, fwd_msg.message_id)

        # 4) Если у пользователя нет username И пересылка не даёт ссылки —
        #    просим его либо установить username, либо снять запрет
        if not message.chat.username and forbidden:
            bot.send_message(
                chat_id,
                "⚠️ Чтобы корректно работать с ботом, пожалуйста:\n"
                "• Установите username в Telegram (Settings → Edit Profile → Username)\n"
                "  или\n"
                "• В настройках Privacy & Security → Forwarded Messages добавьте этого бота в «Always allow».",
                parse_mode="Markdown"
            )
            return

        # --- Если всё ок, отправляем обычное приветствие ---
        send_welcome_message(created=created, user=user)

    except Exception as e:
        logger.exception(e)
