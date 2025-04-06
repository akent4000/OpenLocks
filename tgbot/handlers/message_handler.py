import os
import time
import threading
from loguru import logger
from telebot.types import Message
from tgbot.dispatcher import bot
from tgbot.models import TelegramUser, Task, Tag
from tgbot.logics.constants import *
from tgbot.logics.keyboards import tags_keyboard

# Настройка логгера
logger.add("logs/start_message.log", rotation="10 MB", level="INFO")

# Глобальный кэш для сообщений media group
media_group_cache = {}

def process_media_group(media_group_id: str):
    """
    Обрабатывает все сообщения, относящиеся к одному media group.
    Собирает только файлы и подпись (caption) из сообщений.
    При сохранении для фото выбирается вариант с наивысшим разрешением.
    """
    messages = media_group_cache.pop(media_group_id, [])
    files = []
    text = None

    for message in messages:
        # Используем первую найденную подпись как текст заявки
        if message.caption and not text:
            text = message.caption.strip()

        # Если тип сообщения photo, сохраняем только фото в самом высоком разрешении
        if message.content_type == 'photo' and message.photo:
            highest_res_photo = message.photo[-1]
            files.append({"file_id": highest_res_photo.file_id, "type": "photo"})
        elif message.content_type == 'document' and message.document:
            files.append({"file_id": message.document.file_id, "type": "document"})
        elif message.content_type == 'video' and message.video:
            files.append({"file_id": message.video.file_id, "type": "video"})

    if not text:
        logger.info("Media group без подписи. Заявка не обработана.")
        return
    if len(text) < 13:
        logger.info(f"Media group с короткой подписью: '{text}'. Заявка не обработана.")
        return

    logger.info(f"Получена валидная заявка из media group: '{text}'")

    try:
        user = TelegramUser.objects.get(chat_id=messages[0].chat.id)
    except TelegramUser.DoesNotExist:
        logger.error(f"Пользователь {messages[0].chat.id} не найден. Заявка не сохранена.")
        return

    task = Task.objects.create(
        tag=None,
        title=text if len(text) <= 255 else text[:255],
        description=text,
        payment_type=None,
        creator=user,
        stage=Task.Stage.PENDING,
        files=files
    )
    logger.info(f"Задание сохранено с id: {task.id}")

    message_to_edit = bot.send_message(
        chat_id=messages[0].chat.id,
        reply_to_message_id=messages[0].id,
        reply_markup=tags_keyboard(task),
        text="Выберите тэг задания"
    )
    task.message_to_edit_id = message_to_edit.id
    task.save()

@bot.message_handler(func=lambda message: message.media_group_id is not None, content_types=['photo', 'video', 'document'])
def handle_media_group(message: Message):
    """
    Обработчик для сообщений, входящих в media group.
    Если сообщение имеет media_group_id, оно добавляется в кэш.
    Через небольшую задержку все сообщения группы обрабатываются вместе.
    """
    media_group_id = message.media_group_id

    if media_group_id not in media_group_cache:
        media_group_cache[media_group_id] = []
        threading.Timer(1.0, process_media_group, args=[media_group_id]).start()

    media_group_cache[media_group_id].append(message)

@bot.message_handler(func=lambda message: message.media_group_id is None, content_types=['text', 'photo', 'document', 'video'])
def handle_single_message(message: Message):
    """
    Обработчик одиночных сообщений (не входящих в media group).
    Сохраняет файлы, выбирая для фото вариант с самым высоким разрешением.
    """
    files = []

    if message.content_type == 'text':
        text = message.text.strip()
    else:
        if message.caption:
            text = message.caption.strip()
        else:
            logger.info(f"Сообщение от пользователя {message.chat.id} без подписи. Заявка не обработана.")
            return

    if message.content_type == 'photo' and message.photo:
        highest_res_photo = message.photo[-1]
        files.append({"file_id": highest_res_photo.file_id, "type": "photo"})
    if message.content_type == 'document' and message.document:
        files.append({"file_id": message.document.file_id, "type": "document"})
    if message.content_type == 'video' and message.video:
        files.append({"file_id": message.video.file_id, "type": "video"})

    if len(text) < 13:
        logger.info(f"Заявка от пользователя {message.chat.id} слишком короткая: '{text}'")
        return

    logger.info(f"Получена валидная заявка от пользователя {message.chat.id}: '{text}'")

    try:
        user = TelegramUser.objects.get(chat_id=message.chat.id)
    except TelegramUser.DoesNotExist:
        logger.error(f"Пользователь {message.chat.id} не найден. Заявка не сохранена.")
        return

    task = Task.objects.create(
        tag=None,
        title=text if len(text) <= 255 else text[:255],
        description=text,
        payment_type=None,
        creator=user,
        stage=Task.Stage.PENDING,
        files=files
    )
    logger.info(f"Задание сохранено с id: {task.id}")

    message_to_edit = bot.send_message(
        chat_id=message.chat.id,
        reply_to_message_id=message.id,
        reply_markup=tags_keyboard(task),
        text="Выберите тэг задания"
    )
    task.message_to_edit_id = message_to_edit.id
    task.save()
