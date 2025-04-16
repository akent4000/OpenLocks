import urllib.parse
from telebot.types import CallbackQuery
from tgbot.dispatcher import bot
from tgbot.models import Tag, Task, Files, TelegramUser
from tgbot.logics.constants import *
from tgbot.logics.messages import *
from tgbot.logics.keyboards import *
import re

from loguru import logger
logger.add("logs/utils.log", rotation="10 MB", level="INFO")

def escape_md_v2(text: str) -> str:
    """
    Экранирует спецсимволы для MarkdownV2.
    """
    return re.sub(r'([_*[\]()~`>#+\-=|{}.!])', r'\\\1', text)

def get_user_from_call(call: CallbackQuery) -> TelegramUser | None:
    """Извлекает пользователя по chat_id из сообщения callback."""
    try:
        return TelegramUser.get_user_by_chat_id(chat_id=call.message.chat.id)
    except TelegramUser.DoesNotExist:
        logger.error(f"Пользователь {call.message.chat.id} не найден")
        bot.answer_callback_query(call.id, "Ошибка: пользователь не найден.")
        return None


def extract_query_params(call: CallbackQuery) -> dict:
    """Извлекает параметры из callback data."""
    try:
        query_string = call.data.split("?", 1)[1]
        return urllib.parse.parse_qs(query_string)
    except IndexError:
        bot.answer_callback_query(call.id, "Ошибка: отсутствуют параметры.")
        return {}


def extract_int_param(call: CallbackQuery, params: dict, key: str, error_message: str) -> int | None:
    """Извлекает целочисленный параметр по ключу из словаря параметров."""
    param_list = params.get(key)
    if not param_list:
        bot.answer_callback_query(call.id, error_message)
        return None
    try:
        return int(param_list[0])
    except ValueError:
        bot.answer_callback_query(call.id, f"Ошибка: неверное значение для {key}.")
        return None


def get_task_from_call(call: CallbackQuery, task_id: int) -> Task | None:
    """Получает объект Task по task_id и chat_id создателя."""
    try:
        return Task.objects.get(id=task_id, creator__chat_id=call.message.chat.id)
    except Task.DoesNotExist:
        bot.answer_callback_query(call.id, "Ошибка: заявка не найдена.")
        return None


def get_tag_by_id(call: CallbackQuery, tag_id: int) -> Tag | None:
    """Получает объект Tag по tag_id."""
    try:
        return Tag.objects.get(id=tag_id)
    except Tag.DoesNotExist:
        bot.answer_callback_query(call.id, "Ошибка: выбранный тег не найден.")
        return None

def delete_all_task_related(task: Task):
    """
    Удаляет все сообщения, связанные с заявкой:
      - все SentMessage из task.sent_messages
      - все SentMessage из Files.sent_messages
      - все SentMessage из Response.sent_messages
    """
    # Сообщения по задаче (диспетчер и мастерам)
    for sent in task.sent_messages.all():
        try:
            bot.delete_message(chat_id=sent.telegram_user.chat_id, message_id=sent.message_id)
        except Exception as e:
            logger.error(f"Не удалось удалить сообщение {sent.message_id} у {sent.telegram_user}: {e}")

    # Сообщения, отправленные для файлов
    for f in task.files.all():
        for sent in f.sent_messages.all():
            try:
                bot.delete_message(chat_id=sent.telegram_user.chat_id, message_id=sent.message_id)
            except Exception as e:
                logger.error(f"Не удалось удалить сообщение файла {sent.message_id}: {e}")

    # Сообщения, отправленные для откликов
    for resp in task.responses.all():
        for sent in resp.sent_messages.all():
            try:
                bot.delete_message(chat_id=sent.telegram_user.chat_id, message_id=sent.message_id)
            except Exception as e:
                logger.error(f"Не удалось удалить сообщение отклика {sent.message_id}: {e}")

def get_task_for_creator(call: CallbackQuery, task_id: int) -> Task | None:
    """Получает объект Task по task_id и chat_id создателя."""
    try:
        return Task.objects.get(id=task_id, creator__chat_id=call.message.chat.id)
    except Task.DoesNotExist:
        bot.answer_callback_query(call.id, "Ошибка: заявка не найдена.")
        return None

@bot.callback_query_handler(func=lambda call: call.data.startswith(f"{CallbackData.TAG_SELECT}?"))
def handle_tag_selection(call: CallbackQuery):
    """
    Обработчик выбора тега через inline-кнопку.
    
    Callback data имеет формат:
        "tag_select?tag_id={tag.id}&task_id={task.id}"
    
    Из callback data извлекаются параметры tag_id и task_id.
    По ним определяется выбранный тег и обновляется существующая заявка:
      - заменяется тег,
      - устанавливается stage в Task.Stage.CREATED.
    """
    user = get_user_from_call(call)
    if not user:
        return

    params = extract_query_params(call)
    tag_id = extract_int_param(call, params, CallbackData.TAG_ID, "Ошибка: отсутствует tag_id.")
    task_id = extract_int_param(call, params, CallbackData.TASK_ID, "Ошибка: отсутствует task_id.")
    if tag_id is None or task_id is None:
        return

    tag = get_tag_by_id(call, tag_id)
    if not tag:
        return

    task = get_task_from_call(call, task_id)
    if not task:
        return

    task.tag = tag
    task.stage = Task.Stage.CREATED
    task.save()
    
    bot.answer_callback_query(call.id, f"Заявка обновлена: выбран тег '{tag.name}'.")
    edit_task_message(
        recipient=user,
        task=task, 
        new_text=f"*Ваша заявка*:\n{task.task_text}",
        new_reply_markup=dispather_task_keyboard(task=task)
    )

    broadcast_task_to_subscribers(
        task=task,
        text=task.task_text,
        reply_markup=payment_types_keyboard(task=task)
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith(f"{CallbackData.TASK_CANCEL}?"))
def handle_task_cancel(call: CallbackQuery):
    """
    Обработчик для кнопки "Отменить":
      - удаляет все связанные сообщения,
      - удаляет отклики и файлы через каскад,
      - удаляет саму заявку.
    """
    user = get_user_from_call(call)
    if not user:
        return

    params = extract_query_params(call)
    task_id = extract_int_param(call, params, CallbackData.TASK_ID, "Ошибка: отсутствует task_id.")
    if task_id is None:
        return

    task = get_task_for_creator(call, task_id)
    if not task:
        return

    # Удаляем все сообщения, связанные с заявкой
    delete_all_task_related(task)

    # Удаляем все отклики (и связанные с ними sent_messages через каскад)
    task.responses.all().delete()

    # Заявка и файлы (Files) будут удалены каскадно
    task.delete()

    bot.answer_callback_query(call.id, "Заявка отменена.")


@bot.callback_query_handler(func=lambda call: call.data.startswith(f"{CallbackData.TASK_CLOSE}?"))
def handle_task_close(call: CallbackQuery):
    """
    Обработчик для кнопки "Закрыть":
      - меняет статус заявки,
      - редактирует все сообщения диспетчера и мастеров,
      - сохраняет изменения.
    """
    user = get_user_from_call(call)
    if not user:
        return

    params = extract_query_params(call)
    task_id = extract_int_param(call, params, CallbackData.TASK_ID, "Ошибка: отсутствует task_id.")
    if task_id is None:
        return

    task = get_task_for_creator(call, task_id)
    if not task:
        return

    task.stage = Task.Stage.CLOSED
    task.save()

    closed_text = f"*Заявка закрыта*\n\n{task.task_text}"

    # Обновляем сообщения диспетчера
    for sent in task.sent_messages.filter(telegram_user=task.creator):
        try:
            bot.edit_message_text(
                chat_id=task.creator.chat_id,
                message_id=sent.message_id,
                text=closed_text,
                parse_mode="MarkdownV2",
                reply_markup=repeat_task_dispather_task_keyboard(task)
            )
        except Exception as e:
            logger.error(f"Не удалось отредактировать диспетчерское сообщение {sent.message_id}: {e}")

    # Обновляем сообщения мастеров (отправленные через broadcast_task_to_subscribers)
    for sent in task.sent_messages.exclude(telegram_user=task.creator):
        try:
            bot.edit_message_text(
                chat_id=sent.telegram_user.chat_id,
                message_id=sent.message_id,
                text=closed_text,
                parse_mode="MarkdownV2",
                reply_markup=None
            )
        except Exception as e:
            logger.error(f"Не удалось отредактировать сообщение мастера {sent.message_id}: {e}")

    bot.answer_callback_query(call.id, "Заявка закрыта.")


@bot.callback_query_handler(func=lambda call: call.data.startswith(f"{CallbackData.TASK_REPEAT}?"))
def handle_task_repeat(call: CallbackQuery):
    """
    Обработчик для кнопки "Повторить":
      - удаляет все сообщения, связанные с заявкой,
      - удаляет все отклики,
      - повторно рассылает задачу мастерам.
    """
    user = get_user_from_call(call)
    if not user:
        return

    params = extract_query_params(call)
    task_id = extract_int_param(call, params, CallbackData.TASK_ID, "Ошибка: отсутствует task_id.")
    if task_id is None:
        return

    task = get_task_for_creator(call, task_id)
    if not task:
        return

    delete_all_task_related(task)
    task.responses.all().delete()

    task.stage = Task.Stage.CREATED
    task.save()

    send_task_message(
        recipient=user, 
        task=task,
        text=f"*Заявка повторно выложена*:\n{task.task_text}",
        reply_to_message_id=task.creator_message_id_to_reply,
        reply_markup=dispather_task_keyboard(task=task),
    )

    broadcast_task_to_subscribers(
        task=task,
        text=task.task_text,
        reply_markup=payment_types_keyboard(task)
    )

    bot.answer_callback_query(call.id, "Заявка повторно выложена.")

@bot.callback_query_handler(func=lambda call: call.data.startswith(f"{CallbackData.PAYMENT_SELECT}?"))
def handle_payment_select(call: CallbackQuery):
    """
    Обработчик для кнопок выбора типа оплаты.
    При выборе типа оплаты:
      1) Из callback data извлекаются payment_id и task_id.
      2) Получается объект PaymentType и заявка.
      3) Формируется уведомление для создателя заявки:
         "Мастер [Имя Фамилия](tg://user?id=master_chat_id) хочет забрать заявку 0099 70/30"
         где номер заявки форматируется с ведущими нулями, а имя мастера кликабельно.
      4) Уведомление отправляется создателю заявки в виде ответа на диспетчерское сообщение (reply_to_message_id).
      5) Создаётся объект Response, а отправленное уведомление сохраняется в поле sent_messages.
    """
    master = get_user_from_call(call)
    if not master:
        return

    params = extract_query_params(call)
    payment_id = extract_int_param(call, params, CallbackData.PAYMENT_ID, "Ошибка: отсутствует payment_id.")
    task_id = extract_int_param(call, params, CallbackData.TASK_ID, "Ошибка: отсутствует task_id.")
    if payment_id is None or task_id is None:
        return

    try:
        payment_type = PaymentTypeModel.objects.get(id=payment_id)
    except PaymentTypeModel.DoesNotExist:
        bot.answer_callback_query(call.id, "Ошибка: выбранный тип оплаты не найден.")
        return

    try:
        task = Task.objects.get(id=task_id)
    except Task.DoesNotExist:
        bot.answer_callback_query(call.id, "Ошибка: заявка не найдена.")
        return

    raw_name = master.first_name + (f" {master.last_name}" if master.last_name else "")
    name_esc = escape_md_v2("test")
    url = f"tg://user?id={master.chat_id}"
    clickable_name = f"[{name_esc}]({url})"

    task_number = f"{task.id}"

    notification_text = f"Мастер {clickable_name} хочет забрать заявку {task_number} {payment_type.name}"

    reply_to_message_id = None
    if task.sent_messages.exists():
        reply_to_message_id = task.sent_messages.filter(telegram_user=task.creator).last().message_id

    try:
        sent_message = bot.send_message(
            task.creator.chat_id,
            notification_text,
            parse_mode="MarkdownV2",
            reply_to_message_id=reply_to_message_id
        )
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления создателю заявки {task.creator.chat_id}: {e}")
        bot.answer_callback_query(call.id, "Ошибка при отправке уведомления.")
        return

    response = Response.objects.create(
        task=task,
        telegram_user=master,
        payment_type=payment_type
    )
    sent_msg_obj = SentMessage.objects.create(
        message_id=sent_message.message_id,
        telegram_user=task.creator
    )
    response.sent_messages.add(sent_msg_obj)
    response.save()

    edit_task_message(
        recipient=master, 
        task=task,
        new_text=f"*Ваш отклик отправлен*\n\n{task.task_text}",
        new_reply_markup=master_response_cancel_keyboard(response=response)
    )
    bot.answer_callback_query(call.id, "Ваш отклик отправлен")

@bot.callback_query_handler(func=lambda call: call.data.startswith(f"{CallbackData.RESPONSE_CANCEL}?"))
def handle_response_cancel(call: CallbackQuery):
    """
    Обработчик нажатия кнопки "Отменить" в master_response_cancel_keyboard.
    
    При нажатии:
      1. Удаляются все сообщения из response.sent_messages (удаляются уведомления, отправленные создателю заявки).
      2. Объект Response удаляется.
      3. Выполняется изменение диспетчерского сообщения для мастера, которое теперь содержит текст:
         "*Ваш отклик удалён*\n\n{task.task_text}"
         и новую клавиатуру (payment_types_keyboard) для повторного выбора типа оплаты.
    """
    params = extract_query_params(call)
    response_id = extract_int_param(call, params, CallbackData.RESPONSE_ID, "Ошибка: отсутствует response_id.")
    if response_id is None:
        return

    try:
        response_obj = Response.objects.get(id=response_id)
    except Response.DoesNotExist:
        bot.answer_callback_query(call.id, "Ошибка: отклик не найден.")
        return

    master = response_obj.telegram_user
    task = response_obj.task

    for sent in response_obj.sent_messages.all():
        try:
            bot.delete_message(task.creator.chat_id, sent.message_id)
        except Exception as e:
            logger.error(f"Ошибка при удалении уведомления с ID {sent.message_id}: {e}")

    response_obj.delete()
    edit_task_message(
        recipient=master,
        task=task,
        new_text=f"*Ваш отклик удалён*\n\n{task.task_text}",
        new_reply_markup=payment_types_keyboard(task=task)
    )

    bot.answer_callback_query(call.id, "Ваш отклик удалён.")
