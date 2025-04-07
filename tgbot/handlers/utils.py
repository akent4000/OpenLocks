import urllib.parse
from telebot.types import CallbackQuery
from tgbot.dispatcher import bot
from tgbot.models import Tag, Task, Files, TelegramUser
from tgbot.logics.constants import *
from tgbot.logics.messages import *
from tgbot.logics.keyboards import *

from loguru import logger
logger.add("logs/utils.log", rotation="10 MB", level="INFO")


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
        reply_markup=payment_types_keyboard()
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith(f"{CallbackData.TASK_CANCEL}?"))
def handle_task_cancel(call: CallbackQuery):
    """
    Обработчик для кнопки "Отменить".
    Удаляет заявку и связанные с ней отклики, удаляет сообщения с файлами,
    обновляет диспетчерское сообщение на "Заявка №{task.id} отменена" и удаляет заявку.
    """
    user = get_user_from_call(call)
    if not user:
        return

    params = extract_query_params(call)
    task_id = extract_int_param(call, params, CallbackData.TASK_ID, "Ошибка: отсутствует task_id.")
    if task_id is None:
        return

    task = get_task_from_call(call, task_id)
    if not task:
        return

    # Удаляем связанные отклики
    task.responses.all().delete()

    # Удаляем сообщения с файлами
    for file in task.files.all():
        for sent in file.sent_messages.all():
            try:
                bot.delete_message(call.message.chat.id, sent.message_id)
            except Exception as e:
                logger.error(f"Ошибка при удалении сообщения файла {file.file_id}: {e}")

    cancel_text = f"*Ваша заявка №{task.id} отменена*"
    try:
        edit_task_message(
            recipient=user,
            task=task, 
            new_text=cancel_text,
        )
    except Exception as e:
        logger.error(f"Ошибка при редактировании dispatcher сообщения для задачи {task.id}: {e}")

    task.delete()
    bot.answer_callback_query(call.id, "Заявка отменена.")


@bot.callback_query_handler(func=lambda call: call.data.startswith(f"{CallbackData.TASK_CLOSE}?"))
def handle_task_close(call: CallbackQuery):
    """
    Обработчик для кнопки "Закрыть".
    Изменяет состояние заявки на CLOSED и обновляет диспетчерское сообщение.
    """
    user = get_user_from_call(call)
    if not user:
        return

    params = extract_query_params(call)
    task_id = extract_int_param(call, params, CallbackData.TASK_ID, "Ошибка: отсутствует task_id.")
    if task_id is None:
        return

    task = get_task_from_call(call, task_id)
    if not task:
        return

    task.stage = Task.Stage.CLOSED
    task.save()

    close_text = f"*Ваша заявка №{task.id} закрыта*"
    try:
        edit_task_message(
            recipient=user,
            task=task, 
            new_text=close_text,
        )
    except Exception as e:
        logger.error(f"Ошибка при редактировании dispatcher сообщения для закрытия задачи {task.id}: {e}")
    bot.answer_callback_query(call.id, "Заявка закрыта.")


@bot.callback_query_handler(func=lambda call: call.data.startswith(f"{CallbackData.TASK_REPEAT}?"))
def handle_task_repeat(call: CallbackQuery):
    """
    Обработчик для кнопки "Повторить".
    Пока просто сообщает, что заявка повторно выложена, и обновляет диспетчерское сообщение.
    """
    user = get_user_from_call(call)
    if not user:
        return

    params = extract_query_params(call)
    task_id = extract_int_param(call, params, CallbackData.TASK_ID, "Ошибка: отсутствует task_id.")
    if task_id is None:
        return

    task = get_task_from_call(call, task_id)
    if not task:
        return

    repeat_text = f"*Ваша заявка №{task.id} повторно выложена*"
    try:
        edit_task_message(
            recipient=user,
            task=task, 
            new_text=repeat_text,
        )
    except Exception as e:
        logger.error(f"Ошибка при редактировании dispatcher сообщения для повторной выкладки задачи {task.id}: {e}")
    bot.answer_callback_query(call.id, "Заявка повторно выложена.")
