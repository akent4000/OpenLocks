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

#TAGS
# def get_tag_by_id(call: CallbackQuery, tag_id: int) -> Tag | None:
#     """Получает объект Tag по tag_id."""
#     try:
#         return Tag.objects.get(id=tag_id)
#     except Tag.DoesNotExist:
#         bot.answer_callback_query(call.id, "Ошибка: выбранный тег не найден.")
#         return None

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
        return Task.objects.get(id=task_id, creator__chat_id=call.message.chat.id)
    except Task.DoesNotExist:
        bot.answer_callback_query(call.id, "Ошибка: заявка не найдена.")
        return None

#TAGS
# @bot.callback_query_handler(func=lambda call: call.data.startswith(f"{CallbackData.TAG_SELECT}?"))
# def handle_tag_selection(call: CallbackQuery):
#     """
#     Обработчик выбора тега через inline-кнопку.
    
#     Callback data имеет формат:
#         "tag_select?tag_id={tag.id}&task_id={task.id}"
    
#     Из callback data извлекаются параметры tag_id и task_id.
#     По ним определяется выбранный тег и обновляется существующая заявка:
#       - заменяется тег,
#       - устанавливается stage в Task.Stage.CREATED.
#     """
#     user = get_user_from_call(call)
#     if not user or not ensure_publish_permission(user, call):
#         return
#     params = extract_query_params(call)
    
#     tag_id = extract_int_param(call, params, CallbackData.TAG_ID, "Ошибка: отсутствует tag_id.")
#     task_id = extract_int_param(call, params, CallbackData.TASK_ID, "Ошибка: отсутствует task_id.")
#     if tag_id is None or task_id is None:
#         return
    
#     tag = get_tag_by_id(call, tag_id)
#     if not tag:
#         return

#     task = get_task_from_call(call, task_id)
#     if not task:
#         return

#     task.tag = tag
#     task.stage = Task.Stage.CREATED
#     task.save()
    
#     bot.answer_callback_query(call.id, f"Заявка обновлена: выбран тег '{tag.name}'.")
#     edit_task_message(
#         recipient=user,
#         task=task, 
#         new_text=f"*Ваша заявка*:\n{task.task_text}",
#         new_reply_markup=dispather_task_keyboard(task=task)
#     )

#     broadcast_task_to_subscribers(
#         task=task,
#         reply_markup=payment_types_keyboard(task=task)
#     )

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
      - редактирует сообщение диспетчера через edit_task_message,
      - редактирует все сообщения мастеров через edit_mention_task_message.
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

    # 1) Ставим статус CLOSED
    task.stage = Task.Stage.CLOSED
    task.save()

    # 2) Готовим тексты
    # для диспетчера — без упоминаний
    dispatcher_text = f"*Заявка закрыта*\n\n{task.dispather_task_text}"
    # для мастеров — шаблон с {mention}
    master_template = f"*Заявка закрыта*\n\n{task.master_task_text_with_dispather_mention}"

    edit_task_message(
        recipient=task.creator,
        task=task,
        new_text=dispatcher_text,
        new_reply_markup=repeat_task_dispather_task_keyboard(task)
    )
    masters = {
        sent.telegram_user
        for sent in task.sent_messages.exclude(telegram_user=task.creator)
    }
    for master in masters:
        edit_master_task_message(
            recipient=master,
            task=task,
            new_text=master_template,
            new_reply_markup=None
        )

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
    if not user or not ensure_publish_permission(user, call):
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
        text=f"*Заявка выложена повторно*:\n{task.dispather_task_text}",
        reply_to_message_id=task.creator_message_id_to_reply,
        reply_markup=dispather_task_keyboard(task=task),
    )

    broadcast_task_to_users(
        task=task,
        reply_markup=payment_types_keyboard(task)
    )

    bot.answer_callback_query(call.id, "Заявка выложена повторно.")

@bot.callback_query_handler(func=lambda call: call.data.startswith(f"{CallbackData.PAYMENT_SELECT}?"))
def handle_payment_select(call: CallbackQuery):
    """
    Обработчик кнопок выбора типа оплаты, с упоминанием мастера.
    Приоритет: @username, если нет — text_mention, с фоллбеком на приватность.
    """
    # 1. Получаем мастера и проверяем права
    master = get_user_from_call(call)
    if not master or not ensure_publish_permission(master, call):
        return

    # 2. Извлекаем payment_id и task_id
    params = extract_query_params(call)
    payment_id = extract_int_param(call, params, CallbackData.PAYMENT_ID, "Ошибка: отсутствует payment_id.")
    task_id    = extract_int_param(call, params, CallbackData.TASK_ID,    "Ошибка: отсутствует task_id.")
    if payment_id is None or task_id is None:
        return

    # 3. Загружаем объекты PaymentType и Task
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
        edit_master_task_message(
            recipient=master,
            task=task,
            new_text=f"*Ваш отклик отправлен*\n\n{task.master_task_text_with_dispather_mention}",
            new_reply_markup=master_response_cancel_keyboard(response=response)
        )

        bot.answer_callback_query(call.id, "Ваш отклик отправлен")
    # reply_to = last_disp.message_id if last_disp else None

    # # 5. Формируем шаблон текста с placeholder {mention}
    # text_template = (
    #     f"Мастер {{mention}} хочет забрать заявку №{task.id} {payment_type.name}"
    # )

    # # 6. Отправляем уведомление через общую функцию
    # try:
    #     sent_msg = send_mention_notification(
    #         recipient_chat_id=task.creator.chat_id,
    #         actor=master,
    #         text_template=text_template,
    #         reply_to_message_id=reply_to,
    #         callback=call
    #     )
    # except Exception as e:
    #     logger.error(f"Ошибка при отправке уведомления создателю заявки: {e}")
    #     bot.answer_callback_query(call.id, "Ошибка при отправке уведомления.")
    #     return

    # # 7. Сохраняем отклик и привязанное SentMessage
    # response = Response.objects.create(
    #     task=task,
    #     telegram_user=master,
    #     payment_type=payment_type
    # )
    # sent_record = SentMessage.objects.create(
    #     message_id=sent_msg.message_id,
    #     telegram_user=task.creator
    # )
    # response.sent_messages.add(sent_record)
    # response.save()

    # 8. Обновляем сообщение мастера
    


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
    sent = update_dipsather_task_text(
        task=task,
        callback=call,
        reply_markup=dispather_task_keyboard(task=task),
    )
    edit_master_task_message(
        recipient=master,
        task=task,
        new_text=f"*Ваш отклик удалён*\n\n{task.master_task_text_with_dispather_mention}",
        new_reply_markup=payment_types_keyboard(task=task)
    )

    bot.answer_callback_query(call.id, "Ваш отклик удалён.")

#TAGS
# @bot.callback_query_handler(func=lambda call: call.data.startswith(f"{CallbackData.TAG_TOGGLE}?"))
# def handle_tag_toggle(call: CallbackQuery):
#     """
#     Переключает подписку пользователя на тег и обновляет клавиатуру.
#     """
#     user = get_user_from_call(call)
#     if not user:
#         return

#     params = extract_query_params(call)
#     tag_id = extract_int_param(call, params, CallbackData.TAG_ID, "Ошибка: отсутствует tag_id.")
#     if tag_id is None:
#         return

#     try:
#         tag = Tag.objects.get(id=tag_id)
#     except Tag.DoesNotExist:
#         bot.answer_callback_query(call.id, "Ошибка: тег не найден.")
#         return

#     if tag.id in set(user.subscribed_tags.values_list("id", flat=True)):
#         user.subscribed_tags.remove(tag)
#         action = "отписались"
#     else:
#         user.subscribed_tags.add(tag)
#         action = "подписались"
#     user.save()

#     new_markup = tag_toggle_keyboard(user)
#     try:
#         bot.edit_message_reply_markup(
#             chat_id=call.message.chat.id,
#             message_id=call.message.message_id,
#             reply_markup=new_markup
#         )
#     except Exception as e:
#         logger.error(f"Не удалось обновить клавиатуру тегов: {e}")

#     bot.answer_callback_query(call.id, f"Вы {action} от тега «{tag.name}»")

# @bot.callback_query_handler(func=lambda call: call.data == CallbackData.CLOSE_TAG_TOGGLES)
# def handle_close_tag_toggles(call: CallbackQuery):
#     """
#     Закрывает меню настройки тегов — удаляет сообщение с клавиатурой.
#     """
#     try:
#         bot.delete_message(
#             chat_id=call.message.chat.id,
#             message_id=call.message.message_id
#         )
#     except Exception as e:
#         logger.error(f"Не удалось удалить сообщение с тегами: {e}")

#     bot.answer_callback_query(call.id)