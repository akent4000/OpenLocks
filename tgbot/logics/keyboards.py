from tgbot.models import *
from telebot.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from tgbot.logics.constants import *

from loguru import logger
logger.add("logs/keyboards.log", rotation="10 MB", level="INFO")

def tags_keyboard(task: Task):
    tags = Tag.objects.all()
    if not tags:
        logger.error("Не найден ни один тег. Заявка не может быть сохранена.")
        return

    keyboard = []
    for tag in tags:
        button = InlineKeyboardButton(
            tag.name, 
            callback_data=f"{CallbackData.TAG_SELECT}?{CallbackData.TAG_ID}={tag.id}&{CallbackData.TASK_ID}={task.id}"
        )
        keyboard.append([button])
    markup = InlineKeyboardMarkup(keyboard)
    return markup


def dispather_task(task: Task):
    keyboard = []
    cancel_button = InlineKeyboardButton(
        ButtonNames.CANCEL, 
        callback_data=f"{CallbackData.TASK_CANCEL}?{CallbackData.TASK_ID}={task.id}"
    )
    close_button = InlineKeyboardButton(
        ButtonNames.CLOSE, 
        callback_data=f"{CallbackData.TASK_CLOSE}?{CallbackData.TASK_ID}={task.id}"
    )
    repeat_button = InlineKeyboardButton(
        ButtonNames.REPEAT, 
        callback_data=f"{CallbackData.TASK_REPEAT}?{CallbackData.TASK_ID}={task.id}"
    )
    keyboard.append([cancel_button, close_button, repeat_button])
    markup = InlineKeyboardMarkup(keyboard)
    return markup