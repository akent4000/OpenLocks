import time
from typing import List, Optional

from loguru import logger
logger.add("logs/start_message.log", rotation="10 MB", level="INFO")

from tgbot.dispatcher import bot
from tgbot.models import TelegramUser, Task
from tgbot.logics.constants import *

from telebot import REPLY_MARKUP_TYPES
from telebot.types import InputMediaPhoto, InputMediaVideo

def send_welcome_message(created: bool, user: TelegramUser) -> None:
    """
    Отправляет приветственное сообщение пользователю.
    
    Если пользователь только что создан или не имеет права публиковать задания,
    отправляется сообщение Messages.WELCOME_MESSAGE.
    Если же пользователь имеет право публиковать задания (can_publish_tasks == True),
    отправляется сообщение Messages.CHAT_ACTIVE_MESSAGE, которое через 5 секунд удаляется.
    
    :param created: Флаг, указывающий, был ли пользователь только что создан.
    :param user: Экземпляр модели TelegramUser.
    """
    if created or not user.can_publish_tasks:
        message_text = Messages.WELCOME_MESSAGE
        sent_message = bot.send_message(user.chat_id, message_text, parse_mode="MarkdownV2")
        logger.info(f"Отправлено приветственное сообщение (WELCOME_MESSAGE) пользователю {user.chat_id}")
    else:
        message_text = Messages.CHAT_ACTIVE_MESSAGE
        sent_message = bot.send_message(user.chat_id, message_text, parse_mode="MarkdownV2")
        logger.info(f"Отправлено активное сообщение (CHAT_ACTIVE_MESSAGE) пользователю {user.chat_id}")
        time.sleep(5)
        bot.delete_message(user.chat_id, sent_message.message_id)
        logger.info(f"Удалено активное сообщение для пользователя {user.chat_id}")

def send_dispatcher_task_message(
        task: Task,
        chat_id: int | str,
        reply_to_message_id: int | None = None,
):
    """
    Отправляет сообщение с текстом и прикреплёнными файлами из task.files.
    
    Если файлов нет — отправляется обычное текстовое сообщение.
    Если передан один файл, то используется соответствующий метод отправки:
      - send_photo для "photo",
      - send_video для "video",
      - send_document для "document".
    Если файлов несколько и они все являются фотографиями или видео,
    отправляется media group (caption прикрепляется к первому элементу).
    В противном случае сначала отправляется текстовое сообщение, а затем файлы по отдельности.
    """
    text = f"Ваша заявка {task.id}\n{task.description}"

    # Если файлов нет, отправляем просто сообщение
    if not task.files:
        bot.send_message(chat_id, text, reply_to_message_id=reply_to_message_id)
        return

    # Если один файл, отправляем его с подписью
    if len(task.files) == 1:
        file = task.files[0]
        if file["type"] == "photo":
            bot.send_photo(chat_id, photo=file["file_id"], caption=text, reply_to_message_id=reply_to_message_id)
        elif file["type"] == "video":
            bot.send_video(chat_id, video=file["file_id"], caption=text, reply_to_message_id=reply_to_message_id)
        elif file["type"] == "document":
            bot.send_document(chat_id, document=file["file_id"], caption=text, reply_to_message_id=reply_to_message_id)
        else:
            bot.send_message(chat_id, text, reply_to_message_id=reply_to_message_id)
        return

    # Если файлов несколько, проверяем, все ли они являются фото или видео
    if all(f["type"] in ["photo", "video"] for f in task.files):
        media = []
        for i, f in enumerate(task.files):
            # Для первого элемента добавляем caption с текстом
            if f["type"] == "photo":
                if i == 0:
                    media.append(InputMediaPhoto(media=f["file_id"], caption=text))
                else:
                    media.append(InputMediaPhoto(media=f["file_id"]))
            elif f["type"] == "video":
                if i == 0:
                    media.append(InputMediaVideo(media=f["file_id"], caption=text))
                else:
                    media.append(InputMediaVideo(media=f["file_id"]))
        bot.send_media_group(chat_id, media=media, reply_to_message_id=reply_to_message_id)
    else:
        # Если присутствуют смешанные типы (например, документ) — сначала отправляем текст, потом файлы отдельно
        bot.send_message(chat_id, text, reply_to_message_id=reply_to_message_id)
        for f in task.files:
            if f["type"] == "photo":
                bot.send_photo(chat_id, photo=f["file_id"])
            elif f["type"] == "video":
                bot.send_video(chat_id, video=f["file_id"])
            elif f["type"] == "document":
                bot.send_document(chat_id, document=f["file_id"])