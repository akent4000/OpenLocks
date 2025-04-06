import urllib.parse
from telebot.types import CallbackQuery
from tgbot.dispatcher import bot
from tgbot.models import Tag, Task
from tgbot.logics.constants import *
from tgbot.logics.messages import edit_dispatcher_task_message

@bot.callback_query_handler(func=lambda call: call.data.startswith("tag_select?"))
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
        new_text=task.dispatcher_text
    )