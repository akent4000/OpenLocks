import os
import time

from loguru import logger
logger.add("logs/start_message.log", rotation="10 MB", level="INFO")

from telebot.types import Message
from tgbot.dispatcher import bot
from tgbot.models import TelegramUser, Task, Tag
from tgbot.logics.constants import *

@bot.message_handler(func=lambda message: True, content_types=['text', 'photo', 'document', 'video'])
def handle_request(message: Message):
    """
    Обработчик заявок, отправленных пользователями.

    Если пользователь отправляет текстовое сообщение или сообщение с медиа (фото, документ, видео)
    с подписью (caption), содержащей менее 13 символов, заявка не обрабатывается.
    В противном случае, заявка сохраняется как задание в объект Task, причем все file_id из медиа добавляются.
    """
    file_ids = []
    
    # Определяем текст заявки: если это текстовое сообщение – берём message.text,
    # для остальных типов (фото, документ, видео) требуется наличие caption.
    if message.content_type == 'text':
        text = message.text.strip()
    else:
        if message.caption:
            text = message.caption.strip()
        else:
            logger.info(f"Сообщение от пользователя {message.chat.id} без подписи. Заявка не обработана.")
            return

    # Собираем все file_id из сообщения, если они присутствуют
    if message.content_type == 'photo' and message.photo:
        # Для фото добавляем все варианты, если необходимо (в основном нужен последний, но можно сохранить и все)
        for photo in message.photo:
            file_ids.append(photo.file_id)
    if message.content_type == 'document' and message.document:
        file_ids.append(message.document.file_id)
    if message.content_type == 'video' and message.video:
        file_ids.append(message.video.file_id)

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

    # Сохраняем задание в объект Task с добавлением всех file_id
    task = Task.objects.create(
        tag=tag,
        title=text if len(text) <= 255 else text[:255],
        description=text,
        payment_type=None,  # При необходимости можно указать тип оплаты
        creator=user,
        stage=Task.Stage.CREATED,
        file_ids=file_ids
    )
    logger.info(f"Задание сохранено с id: {task.id}")

