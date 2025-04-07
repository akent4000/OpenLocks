import os
import time
import threading
from loguru import logger
from telebot.types import Message
from tgbot.dispatcher import bot
from tgbot.models import TelegramUser, Task, Tag, Files
from tgbot.logics.constants import *
from tgbot.logics.keyboards import tags_keyboard
from tgbot.logics.messages import *

# Настройка логгера
logger.add("logs/message_handler.log", rotation="10 MB", level="INFO")

# Глобальный кэш для сообщений media group
media_group_cache = {}

# Глобальный кэш для ожидающих текстовых сообщений
# Ключ – chat_id, значение – кортеж (text, message, timer)
pending_text_messages = {}

MIN_TEXT_LENGTH = 13

def extract_files_from_message(message: Message) -> list:
    """
    Извлекает файлы из сообщения и возвращает список словарей с file_id и типом файла.
    """
    files = []
    if message.content_type == 'photo' and message.photo:
        highest_res_photo = message.photo[-1]
        files.append({"file_id": highest_res_photo.file_id, "type": "photo"})
    elif message.content_type == 'document' and message.document:
        files.append({"file_id": message.document.file_id, "type": "document"})
    elif message.content_type == 'video' and message.video:
        files.append({"file_id": message.video.file_id, "type": "video"})
    return files

def process_task_submission(chat_id: int, text: str, reply_to_message_id: int, files: list = None) -> None:
    """
    Валидирует текст, получает пользователя, создает задачу, сохраняет файлы (если есть)
    и отправляет сообщение с выбором тэга.
    """
    if len(text) < MIN_TEXT_LENGTH:
        logger.info(f"Заявка от пользователя {chat_id} слишком короткая: '{text}'")
        return

    try:
        user = TelegramUser.get_user_by_chat_id(chat_id=chat_id)
    except TelegramUser.DoesNotExist:
        logger.error(f"Пользователь {chat_id} не найден. Заявка не сохранена.")
        return

    # Если у пользователя нет прав публиковать задания – отправляем приветственное сообщение
    if not user.can_publish_tasks:
        send_welcome_message(created=False, user=user)
        return

    logger.info(f"Получена валидная заявка от пользователя {chat_id}: '{text}'")
    task = Task.objects.create(
        tag=None,
        title=text if len(text) <= 255 else text[:255],
        description=text,
        payment_type=None,
        creator=user,
        stage=Task.Stage.PENDING_TAG
    )
    logger.info(f"Задание сохранено с id: {task.id}")

    if files:
        for f in files:
            Files.objects.create(
                task=task,
                file_id=f["file_id"],
                file_type=f["type"]
            )

    send_task_message(
        recipient=user, 
        task=task,
        text=f"*Выберите тэг для вашей заявки заявки*\n{task.task_text}",
        reply_markup=tags_keyboard(task), 
        reply_to_message_id=reply_to_message_id,
    )

def process_pending_text(chat_id: int, message: Message, text: str):
    """
    Обрабатывает текстовое сообщение, если в течение ожидания не пришла media group.
    """
    pending_text_messages.pop(chat_id, None)
    process_task_submission(chat_id, text, reply_to_message_id=message.id)

def process_media_group(media_group_id: str):
    """
    Обрабатывает все сообщения, относящиеся к одному media group.
    Собирает файлы и подпись из сообщений.
    Если для этого чата ранее было получено текстовое сообщение, оно используется в качестве подписи.
    """
    messages = media_group_cache.pop(media_group_id, [])
    if not messages:
        return

    chat_id = messages[0].chat.id
    files = []
    text = None

    # Если для этого чата уже есть ожидающее текстовое сообщение, используем его
    if chat_id in pending_text_messages:
        pending_text, pending_msg, timer = pending_text_messages.pop(chat_id)
        timer.cancel()
        text = pending_text

    for message in messages:
        if message.caption and not text:
            text = message.caption.strip()
        files.extend(extract_files_from_message(message))

    if not text:
        logger.info("Media group без подписи. Заявка не обработана.")
        return
    if len(text) < MIN_TEXT_LENGTH:
        logger.info(f"Media group с короткой подписью: '{text}'. Заявка не обработана.")
        return

    process_task_submission(chat_id, text, reply_to_message_id=messages[0].id, files=files)

@bot.message_handler(func=lambda message: message.media_group_id is not None, content_types=['photo', 'video', 'document'])
def handle_media_group(message: Message):
    """
    Обработчик для сообщений, входящих в media group.
    Если сообщение имеет media_group_id, оно добавляется в кэш.
    Через небольшую задержку (например, 1 секунда) все сообщения группы обрабатываются вместе.
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
    Если сообщение является чисто текстовым, оно помещается во временный кэш и ждёт,
    чтобы, возможно, объединиться с последующей media group.
    Если сообщение содержит медиа (с подписью), обрабатывается сразу.
    """
    if message.content_type == 'text':
        text = message.text.strip()
        timer = threading.Timer(2.0, process_pending_text, args=[message.chat.id, message, text])
        pending_text_messages[message.chat.id] = (text, message, timer)
        timer.start()
        return

    files = extract_files_from_message(message)
    if message.caption:
        text = message.caption.strip()
    else:
        logger.info(f"Сообщение от пользователя {message.chat.id} без подписи. Заявка не обработана.")
        return

    process_task_submission(message.chat.id, text, reply_to_message_id=message.id, files=files)
