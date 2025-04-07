import time
from typing import Optional
from loguru import logger

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

def send_task_files(recipient: TelegramUser, task: Task, reply_to_message_id: Optional[int] = None) -> Optional[int]:
    """
    Отправляет файлы, прикреплённые к заданию, универсально для диспетчера и мастера.
    Возвращает ID первого отправленного сообщения (для возможности отправки ответа),
    если файлы отправлены, иначе возвращает None.
    
    Учтите лимиты Telegram по размеру файлов:
      - Отправляемые файлы (без локального сервера Bot API): до 50 МБ.
      - Лимит выгрузки файлов с локальным сервером Bot API: до 2000 МБ.
      - Принимаемые файлы (без локального сервера Bot API): до 20 МБ.
      - Лимит загрузки файлов с локальным сервером Bot API: до 2000 МБ.
    """
    files_qs = list(task.files.all())
    if not files_qs:
        return None

    first_msg_id = None
    chat_id = recipient.chat_id

    if len(files_qs) > 1 and all(f.file_type in ["photo", "video"] for f in files_qs):
        media = []
        for f in files_qs:
            if f.file_type == "photo":
                media.append(InputMediaPhoto(media=f.file_id))
            elif f.file_type == "video":
                media.append(InputMediaVideo(media=f.file_id))
        try:
            msgs = bot.send_media_group(chat_id, media=media, reply_to_message_id=reply_to_message_id)
            if msgs:
                first_msg_id = msgs[0].message_id
                for f, msg in zip(files_qs, msgs):
                    sent = SentMessage.objects.create(
                        message_id=msg.message_id,
                        telegram_user=task.creator
                    )
                    f.sent_messages.add(sent)
                    f.save()
        except Exception as e:
            logger.error(f"Ошибка при отправке media group: {e}")
    else:
        for idx, f in enumerate(files_qs):
            try:
                if f.file_type == "photo":
                    msg = bot.send_photo(chat_id, photo=f.file_id, reply_to_message_id=reply_to_message_id)
                elif f.file_type == "video":
                    msg = bot.send_video(chat_id, video=f.file_id, reply_to_message_id=reply_to_message_id)
                elif f.file_type == "document":
                    msg = bot.send_document(chat_id, document=f.file_id, reply_to_message_id=reply_to_message_id)
                else:
                    msg = bot.send_message(chat_id, "Неподдерживаемый тип файла", reply_to_message_id=reply_to_message_id, parse_mode="MarkdownV2")
                if idx == 0:
                    first_msg_id = msg.message_id
                sent = SentMessage.objects.create(
                    message_id=msg.message_id,
                    telegram_user=task.creator
                )
                f.sent_messages.add(sent)
                f.save()
            except Exception as e:
                logger.error(f"Ошибка при отправке файла {f.file_id} (тип {f.file_type}): {e}")
    return first_msg_id


def send_task_message(
    recipient: TelegramUser,
    task: Task,
    text: str,
    reply_markup: Optional[REPLY_MARKUP_TYPES] = None,
    reply_to_message_id: Optional[int] = None
) -> None:
    """
    Отправляет сообщение по заданию получателю (TelegramUser).
    Сначала вызывается send_task_files для отправки прикреплённых файлов,
    затем отправляется текстовое сообщение с указанным reply_markup.
    
    Сообщение отправляется от имени создателя задания.
    """
    chat_id = recipient.chat_id
    try:
        first_msg_id = send_task_files(recipient, task, reply_to_message_id)
        reply_id = first_msg_id if first_msg_id is not None else reply_to_message_id
        text_msg = bot.send_message(
            chat_id,
            text,
            reply_to_message_id=reply_id,
            parse_mode="MarkdownV2",
            reply_markup=reply_markup
        )
        sent = SentMessage.objects.create(
            message_id=text_msg.message_id,
            telegram_user=task.creator
        )
        task.sent_messages.add(sent)
        task.save()
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения по заданию для пользователя {chat_id}: {e}")


def edit_task_message(
    recipient: TelegramUser,
    task: Task,
    new_text: str,
    new_reply_markup: Optional[REPLY_MARKUP_TYPES] = None
) -> None:
    """
    Редактирует последнее отправленное сообщение по заданию для заданного получателя (TelegramUser).
    Если редактирование не удалось, отправляется новое сообщение.
    """
    chat_id = recipient.chat_id
    try:
        sent = task.sent_messages.filter(telegram_user=recipient).order_by("created_at").last()
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
        logger.info(f"Отредактировано сообщение задачи {task.id} для пользователя {chat_id}")
    except Exception as e:
        logger.error(f"Ошибка при редактировании сообщения задачи {task.id} для пользователя {chat_id}: {e}")
        try:
            new_msg = bot.send_message(
                chat_id,
                new_text,
                parse_mode="MarkdownV2",
                reply_markup=new_reply_markup
            )
            new_sent = SentMessage.objects.create(
                message_id=new_msg.message_id,
                telegram_user=task.creator
            )
            task.sent_messages.add(new_sent)
            task.save()
            logger.info(f"Отправлено новое сообщение для задачи {task.id} для пользователя {chat_id}")
        except Exception as ex:
            logger.error(f"Ошибка при отправке нового сообщения для задачи {task.id} для пользователя {chat_id}: {ex}")


def broadcast_task_to_subscribers(
    task: Task,
    text: str,
    reply_markup: Optional[REPLY_MARKUP_TYPES] = None
) -> None:
    """
    Отправляет сообщение с заданием всем пользователям (мастерам), подписанным на тэг задачи,
    кроме создателя задания.
    
    Учитываются ограничения Telegram:
      - Отправление сообщений разным пользователям: до 30 сообщений с интервалом от 1 секунды.
      - Ограничения по размеру файлов и количеству кнопок (до 100 штук).
    
    Для отправки файлов используется универсальная функция send_task_files.
    """
    if not task.tag:
        logger.error(f"Задача {task.id} не имеет тега, рассылка не выполнена.")
        return

    # Исключаем создателя задания (сравнение по chat_id)
    subscribers = task.tag.subscribers.exclude(chat_id=task.creator.chat_id)
    for subscriber in subscribers:
        try:
            send_task_message(subscriber, task, text, reply_markup)
            logger.info(f"Сообщение по задаче {task.id} отправлено пользователю {subscriber.chat_id}")
        except Exception as e:
            logger.error(f"Ошибка при рассылке сообщения по задаче {task.id} пользователю {subscriber.chat_id}: {e}")
        # Соблюдаем лимит Telegram для отправки сообщений разным пользователям:
        # не более 30 сообщений с интервалом от 1 секунды.
        time.sleep(1)
