import re
import urllib.parse
from telebot.types import CallbackQuery, MessageEntity

from tgbot.dispatcher import bot
from tgbot.models import *
from tgbot.logics.constants import *
from tgbot.logics.messages import *
from tgbot.logics.keyboards import *

from pathlib import Path
from loguru import logger

# Убедимся, что папка logs существует
Path("logs").mkdir(parents=True, exist_ok=True)

# Лог-файл будет называться так же, как модуль, например user_helper.py → logs/user_helper.log
log_filename = Path("logs") / f"{Path(__file__).stem}.log"
logger.add(str(log_filename), rotation="10 MB", level="INFO")

def ensure_publish_permission(user: TelegramUser, call: CallbackQuery) -> bool:
    """
    Проверяет, имеет ли user право публиковать или редактировать заявки.
    Если нет — отвечает на callback и возвращает False.
    Иначе — возвращает True.
    """
    if not user.can_publish_tasks:
        bot.answer_callback_query(call.id, Messages.USER_CANT_DO_IT)
        return False
    return True

def get_user_from_call(call: CallbackQuery) -> TelegramUser | None:
    """Извлекает пользователя по chat_id из сообщения callback."""
    try:
        return TelegramUser.get_user_by_chat_id(chat_id=call.from_user.id)
    except TelegramUser.DoesNotExist:
        logger.error(f"Пользователь {call.from_user.id} не найден")
        bot.answer_callback_query(call.id, Messages.USER_NOT_FOUND_ERROR)
        return None


def extract_query_params(call: CallbackQuery) -> dict:
    """Извлекает параметры из callback data."""
    try:
        query_string = call.data.split("?", 1)[1]
        return urllib.parse.parse_qs(query_string)
    except IndexError:
        bot.answer_callback_query(call.id, Messages.MISSING_PARAMETERS_ERROR)
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
        bot.answer_callback_query(call.id, Messages.INCORRECT_VALUE_ERROR.format(key=key))
        return None


def get_task_from_call(call: CallbackQuery, task_id: int) -> Task | None:
    """Получает объект Task по task_id и chat_id создателя."""
    try:
        return Task.objects.get(id=task_id, creator__chat_id=call.from_user.id)
    except Task.DoesNotExist:
        bot.answer_callback_query(call.id, Messages.TASK_NOT_FOUND_ERROR)
        return None

def delete_all_task_related(task: Task):
    """
    Удаляет все сообщения, связанные с заявкой:
      - удаляет сами сообщения в Telegram,
      - удаляет записи SentMessage из БД для:
        * task.sent_messages
        * всех f.sent_messages в task.files
        * всех resp.sent_messages в task.responses
    """
    for sent in task.sent_messages.all():
        try:
            bot.delete_message(chat_id=sent.telegram_user.chat_id, message_id=sent.message_id)
        except Exception as e:
            logger.error(f"Не удалось удалить сообщение {sent.message_id} у {sent.telegram_user}: {e}")

    for f in task.files.all():
        for sent in f.sent_messages.all():
            try:
                bot.delete_message(chat_id=sent.telegram_user.chat_id, message_id=sent.message_id)
            except Exception as e:
                logger.error(f"Не удалось удалить сообщение файла {sent.message_id}: {e}")

    for resp in task.responses.all():
        for sent in resp.sent_messages.all():
            try:
                bot.delete_message(chat_id=sent.telegram_user.chat_id, message_id=sent.message_id)
            except Exception as e:
                logger.error(f"Не удалось удалить сообщение отклика {sent.message_id}: {e}")

    task.sent_messages.all().delete()
    for f in task.files.all():
        f.sent_messages.all().delete()
    for resp in task.responses.all():
        resp.sent_messages.all().delete()

def get_task_for_creator(call: CallbackQuery, task_id: int) -> Task | None:
    """Получает объект Task по task_id и chat_id создателя."""
    try:
        return Task.objects.get(id=task_id, creator__chat_id=call.from_user.id)
    except Task.DoesNotExist:
        bot.answer_callback_query(call.id, Messages.TASK_NOT_FOUND_ERROR)
        return None

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
    task_id = extract_int_param(call, params, CallbackData.TASK_ID, Messages.MISSING_TASK_ID_ERROR)
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

    bot.answer_callback_query(call.id, Messages.TASK_CANCELED)


@bot.callback_query_handler(func=lambda call: call.data.startswith(f"{CallbackData.TASK_CLOSE}?"))
def handle_task_close(call: CallbackQuery):
    """
    Обработчик для кнопки "Закрыть":
      - меняет статус заявки,
      - редактирует сообщение диспетчера через edit_task_message,
      - редактирует все сообщения мастеров через edit_mention_task_message.
    """
    user = get_user_from_call(call)
    if not user:
        return

    params = extract_query_params(call)
    task_id = extract_int_param(call, params, CallbackData.TASK_ID, Messages.MISSING_TASK_ID_ERROR)
    if task_id is None:
        return

    task = get_task_for_creator(call, task_id)
    if not task:
        return

    # 1) Ставим статус CLOSED
    task.stage = Task.Stage.CLOSED
    task.save()

    # 2) Готовим тексты
    # для диспетчера — без упоминаний
    dispatcher_text = Messages.TASK_CLOSED_TASK_TEXT.format(task_text=task.dispather_task_text)
    # для мастеров — шаблон с {mention}
    master_template = Messages.TASK_CLOSED_TASK_TEXT.format(task_text=task.master_task_text_with_dispather_mention)

    edit_task_message(
        recipient=task.creator,
        task=task,
        new_text=dispatcher_text,
        new_reply_markup=repeat_task_dispather_task_keyboard(task)
    )
    broadcast_edit_master_task_message(
        task=task,
        new_text = master_template,
        new_reply_markup=None
    )
    bot.answer_callback_query(call.id, Messages.TASK_CLOSED)


@bot.callback_query_handler(func=lambda call: call.data.startswith(f"{CallbackData.TASK_REPEAT}?"))
def handle_task_repeat(call: CallbackQuery):
    """
    Обработчик для кнопки "Повторить":
      - удаляет все сообщения, связанные с заявкой,
      - удаляет все отклики,
      - повторно рассылает задачу мастерам.
    """
    user = get_user_from_call(call)
    if not user or not ensure_publish_permission(user, call):
        return

    params = extract_query_params(call)
    task_id = extract_int_param(call, params, CallbackData.TASK_ID, Messages.MISSING_TASK_ID_ERROR)
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
        text=Messages.TASK_REPEATED_TASK_TEXT.format(task_text=task.dispather_task_text),
        reply_to_message_id=task.creator_message_id_to_reply,
        reply_markup=dispather_task_keyboard(task=task),
    )

    broadcast_send_task_to_users(
        task=task,
        reply_markup=payment_types_keyboard(task)
    )

    bot.answer_callback_query(call.id, Messages.TASK_REPEATED)

@bot.callback_query_handler(func=lambda call: call.data.startswith(f"{CallbackData.PAYMENT_SELECT}?"))
def handle_payment_select(call: CallbackQuery):
    """
    Обработчик кнопок выбора типа оплаты, с упоминанием мастера.
    Приоритет: @username, если нет — text_mention, с фоллбеком на приватность.
    """
    # 1. Получаем мастера и проверяем права
    master = get_user_from_call(call)
    if not master or not ensure_publish_permission(master, call):
        bot.answer_callback_query(call.id, Messages.USER_IS_NO_REGISTERED)
        return

    # 2. Извлекаем payment_id и task_id
    params = extract_query_params(call)
    payment_id = extract_int_param(call, params, CallbackData.PAYMENT_ID, Messages.MISSING_PAYMENT_ID_ERROR)
    task_id    = extract_int_param(call, params, CallbackData.TASK_ID, Messages.MISSING_TASK_ID_ERROR)
    if payment_id is None or task_id is None:
        return

    # 3. Загружаем объекты PaymentType и Task
    try:
        payment_type = PaymentTypeModel.objects.get(id=payment_id)
    except PaymentTypeModel.DoesNotExist:
        bot.answer_callback_query(call.id, Messages.PAYMENT_NOT_FOUND_ERROR)
        return

    try:
        task = Task.objects.get(id=task_id)
    except Task.DoesNotExist:
        bot.answer_callback_query(call.id, Messages.TASK_NOT_FOUND_ERROR)
        return

    if master == task.creator:
        bot.answer_callback_query(call.id, Messages.DISPATCHER_CANNOT_RESPOND_TO_HIS_REQUEST)
        return

    if task.responses.filter(telegram_user=master).exists():
        bot.answer_callback_query(call.id, Messages.USER_CANNOT_RESPOND_TWICE)
        return

    last_disp = (
        task.sent_messages
            .filter(telegram_user=task.creator)
            .order_by("created_at")
            .last()
    )
    response = Response.objects.create(
        task=task,
        telegram_user=master,
        payment_type=payment_type
    )

    sent = update_dipsather_task_text(
        task=task,
        response=response,
        callback=call,
        reply_markup=dispather_task_keyboard(task=task),
    )

    if sent and sent != Constants.USER_MENTION_PROBLEM:
        bot.answer_callback_query(call.id, Messages.RESPONSE_SENT)

        broadcast_edit_master_task_message(
            task=task,
        )
    


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
    response_id = extract_int_param(call, params, CallbackData.RESPONSE_ID, Messages.MISSING_RESPONSE_ID_ERROR)
    if response_id is None:
        return

    try:
        response_obj = Response.objects.get(id=response_id)
    except Response.DoesNotExist:
        bot.answer_callback_query(call.id, Messages.RESPONSE_NOT_FOUND_ERROR)
        return

    master = response_obj.telegram_user
    task = response_obj.task
    
    for sent in response_obj.sent_messages.all():
        try:
            bot.delete_message(task.creator.chat_id, sent.message_id)
        except Exception as e:
            logger.error(f"Ошибка при удалении уведомления с ID {sent.message_id}: {e}")

    response_obj.delete()
    sent = update_dipsather_task_text(
        task=task,
        callback=call,
        reply_markup=dispather_task_keyboard(task=task),
    )
    broadcast_edit_master_task_message(
        task=task,
    )

    bot.answer_callback_query(call.id, Messages.RESPONSE_CANCELED)
