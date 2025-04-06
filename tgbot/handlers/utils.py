import urllib.parse
from telebot.types import CallbackQuery
from tgbot.dispatcher import bot
from tgbot.models import Tag, Task
from tgbot.logics.constants import *
from tgbot.logics.messages import edit_dispatcher_task_message
from tgbot.logics.keyboards import dispather_task

from loguru import logger
logger.add("logs/utils.log", rotation="10 MB", level="INFO")

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
    query_string = call.data.split("?", 1)[1]
    params = urllib.parse.parse_qs(query_string)
    
    tag_id_list = params.get(CallbackData.TAG_ID)
    task_id_list = params.get(CallbackData.TASK_ID)
    
    if not tag_id_list or not task_id_list:
        bot.answer_callback_query(call.id, "Ошибка: отсутствуют параметры.")
        return
    
    try:
        tag_id = int(tag_id_list[0])
        task_id = int(task_id_list[0])
    except ValueError:
        bot.answer_callback_query(call.id, "Ошибка: неверные параметры.")
        return
    
    # Получаем выбранный тег
    try:
        tag = Tag.objects.get(id=tag_id)
    except Tag.DoesNotExist:
        bot.answer_callback_query(call.id, "Ошибка: выбранный тег не найден.")
        return
    
    # Получаем заявку, которую необходимо обновить
    try:
        task = Task.objects.get(id=task_id, creator__chat_id=call.message.chat.id)
    except Task.DoesNotExist:
        bot.answer_callback_query(call.id, "Ошибка: заявка не найдена.")
        return

    # Обновляем заявку: меняем тег и устанавливаем stage в CREATED
    task.tag = tag
    task.stage = Task.Stage.CREATED
    task.save()
    
    bot.answer_callback_query(call.id, f"Заявка обновлена: выбран тег '{tag.name}'.")
    edit_dispatcher_task_message(
        task=task, 
        chat_id=call.message.chat.id, 
        new_text=task.dispatcher_text,
        new_reply_markup=dispather_task(task=task)
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith(f"{CallbackData.TASK_CANCEL}?"))
def handle_task_cancel(call: CallbackQuery):
    """
    Обработчик для кнопки "Отменить".
    Удаляет заявку и связанные с ней отклики, удаляет сообщения с файлами,
    изменяет диспетчерское сообщение на "Заявка №{task.id} отменена" и удаляет заявку.
    """
    query_string = call.data.split("?", 1)[1]
    params = urllib.parse.parse_qs(query_string)
    task_id_list = params.get(CallbackData.TASK_ID)
    if not task_id_list:
        bot.answer_callback_query(call.id, "Ошибка: отсутствует task_id.")
        return
    try:
        task_id = int(task_id_list[0])
    except ValueError:
        bot.answer_callback_query(call.id, "Ошибка: неверный task_id.")
        return

    try:
        task = Task.objects.get(id=task_id, creator__chat_id=call.message.chat.id)
    except Task.DoesNotExist:
        bot.answer_callback_query(call.id, "Ошибка: заявка не найдена.")
        return

    # Удаляем связанные отклики (если они есть)
    task.responses.all().delete()

    # Удаляем сообщения с файлами
    for file in task.files.all():
        if file.message_id:
            try:
                bot.delete_message(call.message.chat.id, file.message_id)
            except Exception as e:
                # Логируем, если не удалось удалить отдельное сообщение
                logger.error(f"Ошибка при удалении сообщения файла {file.file_id}: {e}")

    # Обновляем диспетчерское сообщение перед удалением
    cancel_text = f"*Ваша заявка №{task.id} отменена*"
    try:
        edit_dispatcher_task_message(
            task=task, 
            chat_id=call.message.chat.id, 
            new_text=cancel_text,
        )
    except Exception as e:
        logger.error(f"Ошибка при редактировании dispatcher сообщения для задачи {task.id}: {e}")

    # Удаляем заявку
    task.delete()
    bot.answer_callback_query(call.id, "Заявка отменена.")

@bot.callback_query_handler(func=lambda call: call.data.startswith(f"{CallbackData.TASK_CLOSE}?"))
def handle_task_close(call: CallbackQuery):
    """
    Обработчик для кнопки "Закрыть".
    Изменяет состояние заявки на CLOSED и обновляет диспетчерское сообщение.
    """
    query_string = call.data.split("?", 1)[1]
    params = urllib.parse.parse_qs(query_string)
    task_id_list = params.get(CallbackData.TASK_ID)
    if not task_id_list:
        bot.answer_callback_query(call.id, "Ошибка: отсутствует task_id.")
        return
    try:
        task_id = int(task_id_list[0])
    except ValueError:
        bot.answer_callback_query(call.id, "Ошибка: неверный task_id.")
        return

    try:
        task = Task.objects.get(id=task_id, creator__chat_id=call.message.chat.id)
    except Task.DoesNotExist:
        bot.answer_callback_query(call.id, "Ошибка: заявка не найдена.")
        return

    # Изменяем состояние заявки на CLOSED
    task.stage = Task.Stage.CLOSED
    task.save()

    close_text = f"*Ваша заявка №{task.id} закрыта*"
    try:
        edit_dispatcher_task_message(
            task=task, 
            chat_id=call.message.chat.id, 
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
    query_string = call.data.split("?", 1)[1]
    params = urllib.parse.parse_qs(query_string)
    task_id_list = params.get(CallbackData.TASK_ID)
    if not task_id_list:
        bot.answer_callback_query(call.id, "Ошибка: отсутствует task_id.")
        return
    try:
        task_id = int(task_id_list[0])
    except ValueError:
        bot.answer_callback_query(call.id, "Ошибка: неверный task_id.")
        return

    try:
        task = Task.objects.get(id=task_id, creator__chat_id=call.message.chat.id)
    except Task.DoesNotExist:
        bot.answer_callback_query(call.id, "Ошибка: заявка не найдена.")
        return

    repeat_text = f"*Ваша заявка №{task.id} повторно выложена*"
    try:
        edit_dispatcher_task_message(
            task=task, 
            chat_id=call.message.chat.id, 
            new_text=repeat_text,
            new_reply_markup=dispather_task(task=task)
        )
    except Exception as e:
        logger.error(f"Ошибка при редактировании dispatcher сообщения для повторной выкладки задачи {task.id}: {e}")
    bot.answer_callback_query(call.id, "Заявка повторно выложена.")