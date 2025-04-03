import re
import subprocess

import os
import time

from loguru import logger
logger.add("logs/commands.log", rotation="10 MB", level="INFO")


from telebot.types import Message

from tgbot.dispatcher import bot

from tgbot.models import TelegramUser


@bot.message_handler(commands=['start'])
def handle_start(message: Message):
    """Обработчик команды /start. Создает пользователя в базе данных, начисляет бонус рефереру и отправляет приветственное сообщение."""
    try:
        logger.info(f"User {message.chat.id} started the bot.")
        chat_id = message.chat.id
        args = message.text.split()
        referrer_id = int(args[1]) if len(args) > 1 else None
        referrer = None
        if referrer_id:
            referrer = TelegramUser.objects.filter(chat_id=referrer_id).first()
            logger.info(f"Referrer: {referrer}")
            if referrer:
                logger.info(f"User {referrer} is referrer")

        user, created = TelegramUser.objects.get_or_create(
            chat_id=chat_id,
            defaults={
                'first_name': message.chat.first_name,
                'last_name': message.chat.last_name,
                'username': message.chat.username,
            })
        logger.info(f"User {user} created: {created}")

        if created:
            logger.info(f"User {user} created")

        else:
            logger.info(f"User {user} already exists")
        bot.send_message(chat_id, "test", parse_mode='HTML')

    except Exception as e:
        logger.exception(e)
