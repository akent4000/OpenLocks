import time
from typing import List, Optional

from loguru import logger
logger.add("logs/messages.log", rotation="10 MB", level="INFO")

from tgbot.dispatcher import bot
from tgbot.models import TelegramUser, Task, Files, SentMessage
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
    """
    try:
        if created or not user.can_publish_tasks:
            message_text = Messages.WELCOME_MESSAGE
            try:
                sent_message = bot.send_message(user.chat_id, message_text, parse_mode="MarkdownV2")
                logger.info(f"Отправлено приветственное сообщение (WELCOME_MESSAGE) пользователю {user.chat_id}")
            except Exception as e:
                logger.error(f"Ошибка при отправке приветственного сообщения пользователю {user.chat_id}: {e}")
        else:
            message_text = Messages.CHAT_ACTIVE_MESSAGE
            try:
                sent_message = bot.send_message(user.chat_id, message_text, parse_mode="MarkdownV2")
                logger.info(f"Отправлено активное сообщение (CHAT_ACTIVE_MESSAGE) пользователю {user.chat_id}")
            except Exception as e:
                logger.error(f"Ошибка при отправке активного сообщения пользователю {user.chat_id}: {e}")
                return
            time.sleep(5)
            try:
                bot.delete_message(user.chat_id, sent_message.message_id)
                logger.info(f"Удалено активное сообщение для пользователя {user.chat_id}")
            except Exception as e:
                logger.error(f"Ошибка при удалении активного сообщения для пользователя {user.chat_id}: {e}")
    except Exception as e:
        logger.error(f"Общая ошибка при отправке приветственного сообщения пользователю {user.chat_id}: {e}")


def send_dispatcher_task_message(
        task: Task,
        chat_id: int | str,
        reply_to_message_id: int | None = None,
        text: str | None = None,
        reply_markup: REPLY_MARKUP_TYPES | None = None,
):
    """
    Отправляет файлы и текст задачи в два этапа:
      1. Сначала отправляются файлы (даже один файл) – в виде media group, если файлов больше одного и все они фото/видео,
         или по отдельности, если файлы смешанные или один файл.
         Для каждого отправленного файла создаётся SentMessage, который добавляется в task.files.sent_messages.
      2. Затем отправляется текстовое сообщение (с reply_markup) как ответ на первое сообщение.
         Для этого создаётся SentMessage, и добавляется в task.sent_messages.
    Если файлов нет – отправляется только текстовое сообщение.
    """
    try:
        # Получаем список файлов, связанных с задачей
        files_qs = list(task.files.all())
        
        # Если файлов нет, отправляем только текст
        if not files_qs:
            try:
                msg = bot.send_message(
                    chat_id,
                    text,
                    reply_to_message_id=reply_to_message_id,
                    parse_mode="MarkdownV2",
                    reply_markup=reply_markup
                )
                sent = SentMessage.objects.create(message_id=msg.message_id, message_type="dispatcher")
                task.sent_messages.add(sent)
                task.save()
            except Exception as e:
                logger.error(f"Ошибка при отправке текстового сообщения: {e}")
            return

        first_msg_id = None  # id первого отправленного сообщения с файлом

        # Если файлов больше одного и все являются фото или видео – отправляем media group
        if len(files_qs) > 1 and all(f.file_type in ["photo", "video"] for f in files_qs):
            media = []
            for f in files_qs:
                if f.file_type == "photo":
                    media.append(InputMediaPhoto(media=f.file_id))
                elif f.file_type == "video":
                    media.append(InputMediaVideo(media=f.file_id))
            try:
                msgs = bot.send_media_group(
                    chat_id,
                    media=media,
                    reply_to_message_id=reply_to_message_id,
                )
                if msgs:
                    first_msg_id = msgs[0].message_id
                    # Для каждого файла создаём SentMessage и добавляем его
                    for f, msg in zip(files_qs, msgs):
                        sent = SentMessage.objects.create(message_id=msg.message_id, message_type="dispatcher")
                        f.sent_messages.add(sent)
                        f.save()
            except Exception as e:
                logger.error(f"Ошибка при отправке media group: {e}")
        else:
            # Если один файл или файлы смешанных типов – отправляем каждый файл отдельно
            for idx, f in enumerate(files_qs):
                try:
                    if f.file_type == "photo":
                        msg = bot.send_photo(
                            chat_id,
                            photo=f.file_id,
                            reply_to_message_id=reply_to_message_id,
                        )
                    elif f.file_type == "video":
                        msg = bot.send_video(
                            chat_id,
                            video=f.file_id,
                            reply_to_message_id=reply_to_message_id,
                        )
                    elif f.file_type == "document":
                        msg = bot.send_document(
                            chat_id,
                            document=f.file_id,
                            reply_to_message_id=reply_to_message_id,
                        )
                    else:
                        msg = bot.send_message(
                            chat_id,
                            "Неподдерживаемый тип файла",
                            reply_to_message_id=reply_to_message_id,
                            parse_mode="MarkdownV2"
                        )
                    if idx == 0:
                        first_msg_id = msg.message_id
                    sent = SentMessage.objects.create(message_id=msg.message_id, message_type="dispatcher")
                    f.sent_messages.add(sent)
                    f.save()
                except Exception as e:
                    logger.error(f"Ошибка при отправке файла {f.file_id} (тип {f.file_type}): {e}")

        # Отправляем текстовое сообщение как ответ на первое сообщение с файлом
        if first_msg_id is not None:
            try:
                text_msg = bot.send_message(
                    chat_id,
                    text,
                    reply_to_message_id=first_msg_id,
                    parse_mode="MarkdownV2",
                    reply_markup=reply_markup
                )
                sent = SentMessage.objects.create(message_id=text_msg.message_id, message_type="dispatcher")
                task.sent_messages.add(sent)
                task.save()
            except Exception as e:
                logger.error(f"Ошибка при отправке текстового сообщения: {e}")
        else:
            # Если по какой-то причине id первого сообщения не определён, отправляем текст как обычное сообщение
            try:
                text_msg = bot.send_message(
                    chat_id,
                    text,
                    reply_to_message_id=reply_to_message_id,
                    parse_mode="MarkdownV2",
                    reply_markup=reply_markup
                )
                sent = SentMessage.objects.create(message_id=text_msg.message_id, message_type="dispatcher")
                task.sent_messages.add(sent)
                task.save()
            except Exception as e:
                logger.error(f"Ошибка при отправке текстового сообщения (без файлов): {e}")
    except Exception as e:
        logger.error(f"Общая ошибка в send_dispatcher_task_message: {e}")


def edit_dispatcher_task_message(
        task: Task,
        chat_id: int | str,
        new_text: str,
        new_reply_markup: REPLY_MARKUP_TYPES | None = None,
):
    """
    Редактирует последнее отправленное диспетчерское сообщение (с текстом и reply_markup), отправленное в рамках задачи.
    Для редактирования берётся последнее сообщение из task.sent_messages (по дате создания).
    При возникновении ошибки редактирования отправляется новое сообщение, и его SentMessage добавляется в task.sent_messages.
    """
    try:
        # Получаем последнее отправленное сообщение для задачи
        sent = task.sent_messages.order_by("created_at").last()
        if not sent:
            logger.error(f"Задача {task.id} не содержит сохранённых отправленных сообщений для редактирования.")
            return
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=sent.message_id,
            text=new_text,
            parse_mode="MarkdownV2",
            reply_markup=new_reply_markup
        )
        logger.info(f"Отредактировано сообщение задачи {task.id}")
    except Exception as e:
        logger.error(f"Ошибка при редактировании сообщения задачи {task.id}: {e}")
        try:
            new_msg = bot.send_message(
                chat_id=chat_id,
                text=new_text,
                parse_mode="MarkdownV2",
                reply_markup=new_reply_markup
            )
            new_sent = SentMessage.objects.create(message_id=new_msg.message_id, message_type="dispatcher")
            task.sent_messages.add(new_sent)
            task.save()
            logger.info(f"Отправлено новое сообщение для задачи {task.id}")
        except Exception as ex:
            logger.error(f"Ошибка при отправке нового сообщения для задачи {task.id}: {ex}")
