import time
import re
from typing import Optional, Iterable, Union

from tgbot.dispatcher import bot
from tgbot.logics.keyboards import *
from tgbot.logics.text_helper import escape_markdown, get_mention, safe_markdown_mention
from tgbot.models import *
from tgbot.logics.constants import *
from telebot import REPLY_MARKUP_TYPES
from telebot.types import InputMediaPhoto, InputMediaVideo, MessageEntity, CallbackQuery, InlineKeyboardMarkup

from pathlib import Path
from loguru import logger

# Убедимся, что папка logs существует
Path("logs").mkdir(parents=True, exist_ok=True)

# Лог-файл будет называться так же, как модуль, например user_helper.py → logs/user_helper.log
log_filename = Path("logs") / f"{Path(__file__).stem}.log"
logger.add(str(log_filename), rotation="10 MB", level="INFO")

def send_notification_with_mention_check(
    recipient_chat_id: int,
    actor: TelegramUser,
    text_template: str,
    reply_to_message_id: Optional[int] = None,
    callback: Optional[CallbackQuery] = None,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
):
    """
    Универсальная отправка упоминания actor с экранированием Markdown и логированием.
    """
    # 4) Отправка
    try:
        sent = bot.send_message(
            chat_id=recipient_chat_id,
            text=text_template,
            parse_mode="Markdown",
            reply_to_message_id=reply_to_message_id,
            reply_markup=reply_markup
        )
        logger.info(f"send_mention_notification: отправлено сообщение {sent.message_id} для chat_id={recipient_chat_id}")
    except Exception as e:
        logger.error(f"send_mention_notification: ошибка при send_message для chat_id={recipient_chat_id}: {e}")
        return None

    # 5) Фолбэк для неудачного text_mention
    has_mention = False
    for ent in sent.entities or []:
        if ent.type == "text_mention" and ent.user.id == actor.chat_id:
            has_mention = True
            break
    
    if not actor.username and not has_mention:
        try:
            bot.delete_message(chat_id=recipient_chat_id, message_id=sent.message_id)
            logger.info(f"send_mention_notification: удалено неудачное mention-сообщение {sent.message_id}")
            bot.send_message(
                chat_id=actor.chat_id,
                text=(
                    "⚠️ Не удалось создать упоминание вашим именем. "
                    "Пожалуйста, включите пересылку сообщений от бота:\n"
                    "Настройки → Конфиденциальность → Пересылка сообщений"
                ),
                parse_mode="Markdown"
            )
            if callback:
                bot.answer_callback_query(callback.id, "Не удалось упомянуть вас по имени.")
            logger.info(f"send_mention_notification: отправлено уведомление о проблеме упоминания пользователю {actor.chat_id}")
            return Constants.USER_MENTION_PROBLEM
        except Exception as e:
            logger.warning(f"send_mention_notification fallback: ошибка при fallback‑логике: {e}")

    return sent

def update_dipsather_task_text(
    task: Task,
    response: Optional[Response] = None,
    callback: Optional[CallbackQuery] = None,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
):
    if response:
        actor = response.telegram_user
    text = task.dispather_task_text
    try:
        sent = edit_task_message(
            recipient=task.creator,
            task=task,
            new_text=text,
            new_reply_markup=reply_markup
        )
        logger.info(f"update_dipsather_task_text: изменено сообщение {sent.message_id} для chat_id={task.creator.chat_id}")
    except Exception as e:
        logger.error(f"update_dipsather_task_text: ошибка при send_message для chat_id={task.creator.chat_id}: {e}")
        return None

    # 5) Фолбэк для неудачного text_mention
    if response:
        has_mention = False
        for ent in sent.entities or []:
            if ent.type == "text_mention" and ent.user.id == actor.chat_id:
                has_mention = True
                break
        
        if not actor.username and not has_mention:
            try:
                logger.info(f"update_dipsather_task_text: удалено неудачное mention-сообщение {sent.message_id}")
                response.delete()
                text = task.dispather_task_text
                sent = edit_task_message(
                    recipient=task.creator,
                    task=task,
                    new_text=text,
                    new_reply_markup=reply_markup
                )
                bot.send_message(
                    chat_id=actor.chat_id,
                    text=Messages.USER_MENTION_PROBLEM,
                    parse_mode="Markdown"
                )
                if callback:
                    bot.answer_callback_query(callback.id, "Не удалось упомянуть вас по имени.")
                logger.info(f"update_dipsather_task_text: отправлено уведомление о проблеме упоминания пользователю {actor.chat_id}")
                return Constants.USER_MENTION_PROBLEM
            except Exception as e:
                logger.warning(f"update_dipsather_task_text fallback: ошибка при fallback‑логике: {e}")

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
        if user.is_group:
            message_text = Messages.WELCOME_MESSAGE_GROUP
            try:
                sent_message = bot.send_message(user.chat_id, message_text, parse_mode="Markdown")
                logger.info(f"Отправлено приветственное сообщение (WELCOME_MESSAGE_GROUP) в группе {user.chat_id}")
            except Exception as e:
                logger.error(f"Ошибка при отправке приветственное сообщения в группе {user.chat_id}: {e}")
            time.sleep(5)
            try:
                bot.delete_message(user.chat_id, sent_message.message_id)
                logger.info(f"Удалено приветственное сообщение для группы {user.chat_id}")
            except Exception as e:
                logger.error(f"Ошибка при удалении приветственного сообщения для группы {user.chat_id}: {e}")
        else:
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
    Отправляет файлы + текст задания с экранированием и логированием.
    """
    # Отправка файлов
    try:
        first_msg_id = send_task_files(recipient, task, reply_to_message_id)
        logger.info(f"send_task_message: отправлены файлы задачи {task.id} пользователю {recipient.chat_id}")
    except Exception as e:
        logger.error(f"send_task_message: ошибка при отправке файлов задачи {task.id}: {e}")
        first_msg_id = None

    reply_id = first_msg_id or reply_to_message_id

    # Экранирование текста

    try:
        text_msg = bot.send_message(
            recipient.chat_id,
            text,
            reply_to_message_id=reply_id,
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
        logger.info(f"send_task_message: отправлен текст задачи {task.id} сообщением {text_msg.message_id}")
    except Exception as e:
        logger.error(f"send_task_message: ошибка при send_message задачи {task.id} для {recipient.chat_id}: {e}")
        return

    try:
        sent = SentMessage.objects.create(message_id=text_msg.message_id, telegram_user=recipient)
        task.sent_messages.add(sent)
        task.save()
        logger.info(f"send_task_message: сохранён SentMessage {sent.id} для задачи {task.id}")
    except Exception as e:
        logger.error(f"send_task_message: ошибка при сохранении SentMessage для задачи {task.id}: {e}")


def edit_task_message(
    recipient: TelegramUser,
    task: Task,
    new_text: str,
    new_reply_markup: Optional[REPLY_MARKUP_TYPES] = None
) -> SentMessage:
    """
    Редактирует последнее сообщение по задаче с экранированием и логированием.
    """
    sent: SentMessage = task.sent_messages.filter(telegram_user=recipient).order_by("created_at").last()
    if not sent:
        logger.error(f"edit_task_message: нет сообщения для редактирования у {recipient.chat_id} (задача {task.id})")
        return


    try:
        sent = bot.edit_message_text(
            chat_id=recipient.chat_id,
            message_id=sent.message_id,
            text=new_text,
            parse_mode="Markdown",
            reply_markup=new_reply_markup
        )
        logger.info(f"edit_task_message: отредактировано сообщение {sent.message_id} задачи {task.id}")
    except Exception as e:
        logger.error(f"edit_task_message: ошибка при edit_message_text {sent.message_id}: {e}")
        try:
            new_msg = bot.send_message(
                recipient.chat_id,
                new_text,
                parse_mode="Markdown",
                reply_markup=new_reply_markup
            )
            new_sent = SentMessage.objects.create(message_id=new_msg.message_id, telegram_user=recipient)
            task.sent_messages.add(new_sent)
            sent = new_msg
            task.save()
            logger.info(f"edit_task_message: отправлено новое сообщение {new_msg.message_id} для задачи {task.id}")
        except Exception as ex:
            logger.error(f"edit_task_message: ошибка при отправке нового сообщения задачи {task.id}: {ex}")
    return sent


def broadcast_send_task_to_users(
    task: Task,
    reply_markup: Optional[InlineKeyboardMarkup] = None
) -> None:
    # if not task.tag:
    #     logger.error(f"Задача {task.id} не имеет тега — рассылка отменена.")
    #     return

    dispatcher = task.creator
    users = TelegramUser.objects.exclude(chat_id=dispatcher.chat_id).exclude(blocked=True)

    for sub in users:
        try:
            # 1) файлы
            first_msg_id = send_task_files(sub, task)

            task_text = task.master_task_text_with_dispather_mention

            text_msg = send_notification_with_mention_check(
                recipient_chat_id=sub.chat_id,
                actor=dispatcher,
                text_template=task_text,
                reply_to_message_id=first_msg_id,
                reply_markup=reply_markup
            )

            if text_msg == Constants.USER_MENTION_PROBLEM:
                logger.error(f"send_mention_notification не удалось создать упоминание пользователя, рассылка прекращена")
                return

            if text_msg:
                sent = SentMessage.objects.create(
                    message_id=text_msg.message_id,
                    telegram_user=sub
                )

                task.sent_messages.add(sent)
                task.save()

                logger.info(f"Задача {task.id} отправлена мастеру {sub.chat_id}")

        except Exception as e:
            logger.error(f"Не удалось отправить задачу {task.id} мастеру {sub.chat_id}: {e}")

def edit_master_task_message(
    recipient: TelegramUser,
    task: Task,
    new_text: str,
    new_reply_markup: Optional[InlineKeyboardMarkup] = None,
) -> None:

    sent: SentMessage = (
        task.sent_messages
            .filter(telegram_user=recipient)
            .order_by("created_at")
            .last()
    )
    if not sent:
        logger.error(f"edit_master_task_message: для задачи {task.id} нет сообщений у {recipient.chat_id}")
        return

    try:
        bot.edit_message_text(
            chat_id=recipient.chat_id,
            message_id=sent.message_id,
            text=new_text,
            parse_mode="Markdown",
            reply_markup=new_reply_markup
        )
        logger.info(f"edit_master_task_message: отредактировано сообщение {sent}")
        return
    except Exception as e:
        logger.warning(f"edit_master_task_message: не удалось отредактировать {sent}: {e}")

    try:
        sent.delete()
        bot.delete_message(chat_id=recipient, message_id=sent.message_id)
        logger.info(f"edit_master_task_message: удалено старое сообщение {sent}")
    except Exception as e:
        logger.warning(f"edit_master_task_message: не удалось удалить {sent}: {e}")

    files = task.files
    for file in files:
        msg = file.sent_messages.filter(telegram_user=recipient).order_by("created_at").last()
        try:
            bot.delete_message(chat_id=recipient, message_id=msg.message_id)
            msg.delete()
            logger.info(f"edit_master_task_message: удалено старое сообщение {msg}")
        except Exception as e:
            logger.warning(f"edit_master_task_message: не удалось удалить {msg}: {e}")

    
    logger.info(f"edit_master_task_message: вызвана edit_master_task_message для сообщения {sent.message_id}")

    first_msg_id = send_task_files(recipient, task)

    text_msg = send_notification_with_mention_check(
        recipient_chat_id=recipient.chat_id,
        actor=task.creator,
        text_template=new_text,
        reply_to_message_id=first_msg_id,
        reply_markup=new_reply_markup
    )

    if text_msg == Constants.USER_MENTION_PROBLEM:
        logger.error(f"send_mention_notification не удалось создать упоминание пользователя, рассылка прекращена")
        return

    if text_msg:
        sent = SentMessage.objects.create(
            message_id=text_msg.message_id,
            telegram_user=recipient
        )

        task.sent_messages.add(sent)
        task.save()

        logger.info(f"Задача {task.id} заново отправлена мастеру после ошибки {recipient.chat_id}")

def broadcast_edit_master_task_message(
    task: Task,
    new_text: Optional[str] = None,
    new_reply_markup: Optional[InlineKeyboardMarkup] = None,
    exclude: Optional[Iterable[Union[TelegramUser, int]]] = None,
) -> None:
    """
    Массово редактирует сообщения у всех мастеров по задаче, кроме:
      - диспетчера (task.creator),
      - заблокированных,
      - и любых, указанных в параметре exclude.
    При наличии отклика у мастера будет использована клавиатура master_response_cancel_keyboard.
    """
    dispatcher = task.creator

    # Собираем set chat_id, которых исключаем
    exclude_ids = {dispatcher.chat_id}
    if exclude:
        for item in exclude:
            exclude_ids.add(item.chat_id if isinstance(item, TelegramUser) else int(item))

    # Фильтруем мастеров
    masters = (
        TelegramUser.objects
        .exclude(chat_id__in=exclude_ids)
        .exclude(blocked=True)
    )

    for master in masters:
        try:
            has_response = task.responses.filter(telegram_user=master).exists()

            # для каждого мастера заводим свои локальные переменные
            if has_response:
                # берём последний отклик мастера
                response = task.responses.filter(telegram_user=master).last()

                # если не передан общий new_text — используем специальный текст для откликнувшихся
                text_to_send = new_text if new_text is not None else Messages.RESPONSE_SENT_TASK_TEXT.format(
                    task_text=task.master_task_text_with_dispather_mention
                )
                # если не передана общая клавиатура — ставим кнопку отмены отклика
                markup_to_send = new_reply_markup if new_reply_markup is not None else master_response_cancel_keyboard(response=response)
            else:
                # мастер ещё не откликался
                text_to_send = new_text if new_text is not None else task.master_task_text_with_dispather_mention
                markup_to_send = new_reply_markup if new_reply_markup is not None else payment_types_keyboard(task=task)

            edit_master_task_message(
                recipient=master,
                task=task,
                new_text=text_to_send,
                new_reply_markup=markup_to_send
            )
            logger.info(f"broadcast_edit: отредактировано сообщение задачи {task.id} у мастера {master.chat_id}")
        except Exception as e:
            logger.error(f"broadcast_edit: не удалось отредактировать сообщение задачи {task.id} у {master.chat_id}: {e}")