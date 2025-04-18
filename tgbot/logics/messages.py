import time
import re
from typing import Optional
from loguru import logger

from tgbot.dispatcher import bot
from tgbot.models import *
from tgbot.logics.constants import *
from telebot import REPLY_MARKUP_TYPES
from telebot.types import InputMediaPhoto, InputMediaVideo, MessageEntity, CallbackQuery, InlineKeyboardMarkup

def escape_markdown(text: str) -> str:
    """
    Экранирует все специальные символы Markdown, добавляя перед ними обратный слеш.
    Поддерживает CommonMark и MarkdownV2 (Telegram).
    """
    # Список всех спецсимволов Markdown / MarkdownV2
    # Для Telegram MarkdownV2: _ * [ ] ( ) ~ ` > # + - = | { } . !
    pattern = r'([\\`*_{}\[\]()#+\-.!|~>])'
    return re.sub(pattern, r'\\\1', text)

def safe_markdown_mention(actor: TelegramUser) -> str:
    """
    Формирует кликабельную Markdown‑ссылку на пользователя без излишнего экранирования.
    Экранируем только [, ], ( ), и обратный слеш.
    """
    # Собираем имя
    raw = f"{actor.first_name}{(' ' + actor.last_name) if actor.last_name else ''}".strip() or str(actor.chat_id)
    # Экранируем только нужные символы
    escaped = re.sub(r'([\\\[\]\(\)])', r'\\\1', raw)
    return f"[{escaped}](tg://user?id={actor.chat_id})"

def send_mention_notification(
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
    # 1) Формируем mention и сразу экранируем
    if actor.username:
        mention = escape_markdown(f"@{actor.username}")
    else:
        mention = safe_markdown_mention(actor)

    # 2) Подставляем в шаблон и экранируем весь текст
    text = text_template.format(mention=mention)

    # 4) Отправка
    try:
        sent = bot.send_message(
            chat_id=recipient_chat_id,
            text=text,
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
            return Constants.MENTION_PROBLEM
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
                    text=(
                        "⚠️ Не удалось создать упоминание вашим именем. "
                        "Пожалуйста, включите пересылку сообщений от бота:\n"
                        "Настройки → Конфиденциальность → Пересылка сообщений"
                    ),
                    parse_mode="Markdown"
                )
                if callback:
                    bot.answer_callback_query(callback.id, "Не удалось упомянуть вас по имени.")
                logger.info(f"update_dipsather_task_text: отправлено уведомление о проблеме упоминания пользователю {actor.chat_id}")
                return Constants.MENTION_PROBLEM
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


def broadcast_task_to_users(
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

            template =task.master_task_text_with_dispather_mention.format(mention="{mention}",)

            text_msg = send_mention_notification(
                recipient_chat_id=sub.chat_id,
                actor=dispatcher,
                text_template=template,
                reply_to_message_id=first_msg_id,
                reply_markup=reply_markup
            )

            if text_msg == Constants.MENTION_PROBLEM:
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
        time.sleep(0.04)

def edit_mention_notification(
    recipient: TelegramUser,
    message: SentMessage,
    actor: TelegramUser,
    text_template: str,
    task: Task,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
):
    """
    Редактирует ранее отправленное уведомление с упоминанием actor,
    экранируя Markdown-спецсимволы в тексте.
    """
    # 1) Формируем и экранируем mention
    if actor.username:
        mention = escape_markdown(f"@{actor.username}")
    else:
        mention = safe_markdown_mention(actor)

    text = text_template.format(mention=mention)

    # 3) Пытаемся отредактировать
    try:
        bot.edit_message_text(
            chat_id=recipient.chat_id,
            message_id=message.message_id,
            text=text,
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
        logger.info(f"edit_mention_notification: отредактировано сообщение {message}")
        return
    except Exception as e:
        logger.warning(f"edit_mention_notification: не удалось отредактировать {message}: {e}")

    # 4) Фолбэк: удаляем старое и шлём заново
    try:
        bot.delete_message(chat_id=recipient, message_id=message)
        logger.info(f"edit_mention_notification: удалено старое сообщение {message}")
    except Exception as e:
        logger.warning(f"edit_mention_notification: не удалось удалить {message}: {e}")

    new_msg = send_mention_notification(
        recipient_chat_id=recipient,
        actor=actor,
        text_template=text_template,
        reply_to_message_id=None,
        callback=None,
        reply_markup=reply_markup
    )


def edit_master_task_message(
    recipient: TelegramUser,
    task: Task,
    new_text: str,
    new_reply_markup: Optional[InlineKeyboardMarkup] = None,
) -> None:
    """
    Редактирует последнее сообщение по задаче, вставляя mention диспетчера,
    и экранирует Markdown-спецсимволы.
    """
    sent: SentMessage = (
        task.sent_messages
            .filter(telegram_user=recipient)
            .order_by("created_at")
            .last()
    )
    if not sent:
        logger.error(f"edit_mention_task_message: для задачи {task.id} нет сообщений у {recipient.chat_id}")
        return


    edit_mention_notification(
        recipient=recipient,
        message=sent,
        actor=task.creator,
        text_template=new_text,
        reply_markup=new_reply_markup,
        task=task
    )
    logger.info(f"edit_mention_task_message: вызвана edit_mention_notification для сообщения {sent.message_id}")
