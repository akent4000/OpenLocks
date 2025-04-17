import time
from typing import Optional
from loguru import logger

from tgbot.dispatcher import bot
from tgbot.models import TelegramUser, Task, Files, SentMessage
from tgbot.logics.constants import *
from telebot import REPLY_MARKUP_TYPES
from telebot.types import InputMediaPhoto, InputMediaVideo, MessageEntity, CallbackQuery, InlineKeyboardMarkup

def send_mention_notification(
    recipient_chat_id: int,
    actor: TelegramUser,
    text_template: str,
    reply_to_message_id: Optional[int] = None,
    callback: Optional[CallbackQuery] = None,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
):
    """
    Универсальная отправка сообщения с упоминанием actor:
      - если actor.username есть username, ставит @username
      - иначе вставляет text_mention
    text_template — строка, содержащая "{mention}".
    Если передан callback — после отправки проверяет, сработал ли text_mention,
    и, в случае ошибки, удаляет сообщение и шлёт актору инструкцию.
    """
    # 1) Формируем mention
    if actor.username:
        mention = f"@{actor.username}"
    else:
        mention = f"{actor.first_name}{(' ' + actor.last_name) if actor.last_name else ''}".strip()

    # 2) Подставляем в шаблон
    text = text_template.format(mention=mention)

    # 3) Готовим entities для text_mention, если нет username
    entities = None
    if not actor.username:
        try:
            offset = text.index(mention)
            entities = [
                MessageEntity(
                    type="text_mention",
                    offset=offset,
                    length=len(mention),
                    user=actor
                )
            ]
        except ValueError:
            pass  # не нашли — отправляем без entities

    # 4) Отправляем
    sent = bot.send_message(
        chat_id=recipient_chat_id,
        text=text,
        parse_mode=None if entities else "Markdown",
        entities=entities,
        reply_to_message_id=reply_to_message_id,
        reply_markup=reply_markup
    )

    # 5) Если пытались text_mention и он НЕ сработал — делаем fallback
    if callback and not actor.username and not sent.entities:
        try:
            # удаляем неудачное уведомление
            bot.delete_message(chat_id=recipient_chat_id, message_id=sent.message_id)
            # шлём актору подсказку
            bot.send_message(
                chat_id=actor.chat_id,
                text=(
                    "⚠️ Не удалось создать упоминание вашим именем. "
                    "Пожалуйста, в Telegram включите пересылку сообщений от бота:\n"
                    "Настройки → Конфиденциальность → Пересылка сообщений"
                ),
                parse_mode="Markdown"
            )
            # отвечаем на callback, чтобы в интерфейсе ткнуть «OK»
            bot.answer_callback_query(callback.id, "Не удалось упомянуть вас по имени.")
        except Exception as e:
            logger.warning(f"Не смогли отправить fallback-мастеру: {e}")

    return sent


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
                sent_message = bot.send_message(user.chat_id, message_text, parse_mode="Markdown")
                logger.info(f"Отправлено приветственное сообщение (WELCOME_MESSAGE) пользователю {user.chat_id}")
            except Exception as e:
                logger.error(f"Ошибка при отправке приветственного сообщения пользователю {user.chat_id}: {e}")
        else:
            message_text = Messages.CHAT_ACTIVE_MESSAGE
            try:
                sent_message = bot.send_message(user.chat_id, message_text, parse_mode="Markdown")
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
                        telegram_user=recipient
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
                    msg = bot.send_message(chat_id, "Неподдерживаемый тип файла", reply_to_message_id=reply_to_message_id, parse_mode="Markdown")
                if idx == 0:
                    first_msg_id = msg.message_id
                sent = SentMessage.objects.create(
                    message_id=msg.message_id,
                    telegram_user=recipient
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
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
        sent = SentMessage.objects.create(
            message_id=text_msg.message_id,
            telegram_user=recipient
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
            parse_mode="Markdown",
            reply_markup=new_reply_markup
        )
        logger.info(f"Отредактировано сообщение задачи {task.id} для пользователя {chat_id}")
    except Exception as e:
        logger.error(f"Ошибка при редактировании сообщения задачи {task.id} для пользователя {chat_id}: {e}")
        try:
            new_msg = bot.send_message(
                chat_id,
                new_text,
                parse_mode="Markdown",
                reply_markup=new_reply_markup
            )
            new_sent = SentMessage.objects.create(
                message_id=new_msg.message_id,
                telegram_user=recipient
            )
            task.sent_messages.add(new_sent)
            task.save()
            logger.info(f"Отправлено новое сообщение для задачи {task.id} для пользователя {chat_id}")
        except Exception as ex:
            logger.error(f"Ошибка при отправке нового сообщения для задачи {task.id} для пользователя {chat_id}: {ex}")


def broadcast_task_to_subscribers(
    task: Task,
    reply_markup: Optional[InlineKeyboardMarkup] = None
) -> None:
    if not task.tag:
        logger.error(f"Задача {task.id} не имеет тега — рассылка отменена.")
        return

    dispatcher = task.creator
    subscribers = task.tag.subscribers.exclude(chat_id=dispatcher.chat_id)

    for sub in subscribers:
        try:
            # 1) файлы
            first_msg_id = send_task_files(sub, task)

            template =task.task_text_with_mention.format(mention="{mention}",)

            text_msg = send_mention_notification(
                recipient_chat_id=sub.chat_id,
                actor=dispatcher,
                text_template=template,
                reply_to_message_id=first_msg_id,
                reply_markup=reply_markup
            )

            sent = SentMessage.objects.create(
                message_id=text_msg.message_id,
                telegram_user=sub
            )

            task.sent_messages.add(sent)
            task.save()

            logger.info(f"Задача {task.id} отправлена мастеру {sub.chat_id}")
        except Exception as e:
            logger.error(f"Не удалось отправить задачу {task.id} мастеру {sub.chat_id}: {e}")
        time.sleep(0.04)