import re
import subprocess
import os
import time

from loguru import logger
logger.add("logs/start_message.log", rotation="10 MB", level="INFO")

from telebot.types import Message
from tgbot.dispatcher import bot
from tgbot.models import TelegramUser, Task, Tag
from tgbot.logics.constants import *

@bot.message_handler(func=lambda message: True, content_types=['text', 'photo'])
def handle_request(message: Message):
    """
    Обработчик заявок, отправленных пользователями.

    Если пользователь отправляет текст или фото с подписью, содержащие менее 13 символов, сообщение не обрабатывается.
    В противном случае, заявка сохраняется как задание в объект Task.
    """
    file_ids = []
    # Определяем текст заявки: если это текстовое сообщение – берём text, если фото – caption.
    if message.content_type == 'text':
        text = message.text.strip()
    elif message.content_type == 'photo':
        if message.caption:
            text = message.caption.strip()
        else:
            logger.info(f"Фото от пользователя {message.chat.id} без подписи. Заявка не обработана.")
            return
        # Получаем file_id фото (наибольшее разрешение — последний элемент)
        photo = message.photo[-1]
        file_ids.append(photo.file_id)
    else:
        return

    # Проверка длины текста
    if len(text) < 13:
        logger.info(f"Заявка от пользователя {message.chat.id} слишком короткая: '{text}'")
        return

    logger.info(f"Получена валидная заявка от пользователя {message.chat.id}: '{text}'")

    # Поиск пользователя в базе данных
    try:
        user = TelegramUser.objects.get(chat_id=message.chat.id)
    except TelegramUser.DoesNotExist:
        logger.error(f"Пользователь {message.chat.id} не найден. Заявка не сохранена.")
        return

    # Определяем тег для задания. Предполагается, что хотя бы один тег существует.
    tag = Tag.objects.first()
    if not tag:
        logger.error("Не найден ни один тег. Заявка не может быть сохранена.")
        return

    # Сохраняем задание в объект Task
    task = Task.objects.create(
        tag=tag,
        title=text if len(text) <= 255 else text[:255],
        description=text,
        payment_type=None,  # Если необходимо, здесь можно указать тип оплаты
        creator=user,
        stage=Task.Stage.CREATED,
        file_ids=file_ids
    )
    logger.info(f"Задание сохранено с id: {task.id}")
