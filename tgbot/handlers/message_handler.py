import os
import time
import threading
from telebot.types import Message
from tgbot.dispatcher import bot
from tgbot.models import *
from tgbot.logics.constants import *
from tgbot.logics.keyboards import *
from tgbot.logics.messages import *
from tgbot.handlers.user_helper import is_group_chat
from pathlib import Path
from loguru import logger

# Убедимся, что папка logs существует
Path("logs").mkdir(parents=True, exist_ok=True)

# Лог-файл будет называться так же, как модуль, например user_helper.py → logs/user_helper.log
log_filename = Path("logs") / f"{Path(__file__).stem}.log"
logger.add(str(log_filename), rotation="10 MB", level="INFO")

# Кэши для media_group и ожидающих текстов
media_group_cache = {}
pending_text_messages = {}

def extract_files_from_message(message: Message) -> list:
    files = []
    if message.content_type == 'photo' and message.photo:
        highest = message.photo[-1]
        files.append({"file_id": highest.file_id, "type": "photo"})
    elif message.content_type == 'document' and message.document:
        files.append({"file_id": message.document.file_id, "type": "document"})
    elif message.content_type == 'video' and message.video:
        files.append({"file_id": message.video.file_id, "type": "video"})
    return files

def send_temporary_error(chat_id: int, reply_to_message_id, message_text: str):
    try:
        sent = bot.send_message(chat_id, message_text, reply_to_message_id=reply_to_message_id, parse_mode="Markdown")
        logger.info(f"process_task_submission: отправлена ошибка '{message_text}' пользователю {chat_id}")
        time.sleep(5)
        try:
            bot.delete_message(chat_id, sent.message_id)
            logger.info(f"process_task_submission: удалено сообщение об ошибке {sent.message_id} для {chat_id}")
        except Exception as e:
            logger.error(f"process_task_submission: ошибка при удалении сообщения об ошибке {sent.message_id}: {e}")
    except Exception as e:
        logger.error(f"process_task_submission: ошибка при отправке сообщения об ошибке пользователю {chat_id}: {e}")

def process_task_submission(chat_id: int, text: str, reply_to_message_id: int, files: list = None) -> None:
    """
    Пытается создать новую задачу. Если что-то идёт не так — уведомляет пользователя и удаляет сообщение об ошибке через 5 секунд.
    """

    # 1) Проверка длины
    if len(text) < Constants.MIN_TEXT_LENGTH:
        logger.info(f"Заявка от {chat_id} слишком короткая: '{text}'")
        send_temporary_error(chat_id, reply_to_message_id, Messages.TASK_TEXT_IS_TOO_SHORT)
        return

    # 2) Найти/зарегистрировать пользователя
    user = TelegramUser.get_user_by_chat_id(chat_id=chat_id)
    if not user:
        logger.error(f"Пользователь {chat_id} не зарегистрирован")
        send_temporary_error(chat_id, reply_to_message_id, Messages.USER_IS_NO_REGISTERED)
        return

    # 3) Проверка прав
    if not user.can_publish_tasks:
        logger.info(f"Пользователю {chat_id} запрещено публиковать задачи")
        send_temporary_error(chat_id, reply_to_message_id, Messages.USER_CANT_PUBLISH_TASKS)
        return

    # Всё ок — создаём задачу
    logger.info(f"Создаём задачу от пользователя {chat_id}: '{text}'")
    task = Task.objects.create(
        title=text if len(text) <= 255 else text[:255],
        description=text,
        creator=user,
        creator_message_id_to_reply=reply_to_message_id,
        stage=Task.Stage.CREATED
    )
    logger.info(f"Задача {task.id} сохранена")

    # Сохраняем файлы, если есть
    if files:
        for f in files:
            Files.objects.create(
                task=task,
                file_id=f["file_id"],
                file_type=f["type"]
            )

    # Отправляем задачу диспетчеру
    send_task_message(
        recipient=user,
        task=task,
        text=task.dispather_task_text,
        reply_markup=dispather_task_keyboard(task=task),
        reply_to_message_id=task.creator_message_id_to_reply,
    )

    # Рассылаем мастерам
    broadcast_task_to_users(
        task=task,
        reply_markup=payment_types_keyboard(task=task)
    )
    

def process_pending_text(chat_id: int, message: Message, text: str):
    pending_text_messages.pop(chat_id, None)
    process_task_submission(chat_id, text, reply_to_message_id=message.message_id)

def process_media_group(media_group_id: str):
    messages = media_group_cache.pop(media_group_id, [])
    if not messages:
        return

    chat_id = messages[0].chat.id
    files = []
    text = None

    # Используем ранее сохранённый текст, если есть
    if chat_id in pending_text_messages:
        pending, pending_msg, timer = pending_text_messages.pop(chat_id)
        timer.cancel()
        text = pending

    for msg in messages:
        if msg.caption and not text:
            text = msg.caption.strip()
        files.extend(extract_files_from_message(msg))

    if not text:
        logger.info(f"Media group {media_group_id} без подписи от {chat_id}")
        send_temporary_error(chat_id, messages[0].message_id, Messages.TASK_TEXT_IS_NOT_DEFINIDED)
        return
    if len(text) < Constants.MIN_TEXT_LENGTH:
        logger.info(f"Media group {media_group_id} с короткой подписью от {chat_id}")
        send_temporary_error(chat_id, messages[0].message_id, Messages.TASK_TEXT_IS_TOO_SHORT)
        return

    process_task_submission(chat_id, text, reply_to_message_id=messages[0].message_id, files=files)

@bot.message_handler(func=lambda m: m.media_group_id is not None, content_types=['photo','video','document'])
def handle_media_group(message: Message):
    if is_group_chat(message):
        return
    mgid = message.media_group_id
    if mgid not in media_group_cache:
        media_group_cache[mgid] = []
        threading.Timer(1.0, process_media_group, args=[mgid]).start()
    media_group_cache[mgid].append(message)

@bot.message_handler(func=lambda m: m.media_group_id is None, content_types=['text','photo','document','video'])
def handle_single_message(message: Message):
    if is_group_chat(message):
        return
    if message.content_type == 'text':
        text = message.text.strip()
        timer = threading.Timer(2.0, process_pending_text, args=[message.chat.id, message, text])
        pending_text_messages[message.chat.id] = (text, message, timer)
        timer.start()
    else:
        files = extract_files_from_message(message)
        if not message.caption:
            logger.info(f"Сообщение {message.message_id} от {message.chat.id} без подписи")
            send_temporary_error(message.chat.id, message.message_id, Messages.TASK_TEXT_IS_NOT_DEFINIDED)
            return
        process_task_submission(message.chat.id, message.caption.strip(), reply_to_message_id=message.message_id, files=files)
