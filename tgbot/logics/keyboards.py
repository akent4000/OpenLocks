from tgbot.models import *
from telebot.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from tgbot.logics.constants import *

from loguru import logger
logger.add("logs/keyboards.log", rotation="10 MB", level="INFO")

def tags_keyboard(task):
    tags = Tag.objects.all()
    if not tags:
        logger.error("Не найден ни один тег. Заявка не может быть сохранена.")
        return

    keyboard = []
    for tag in tags:
        button = InlineKeyboardButton(tag.name, callback_data=f"{CallbackData.TAG_SELECT}?{CallbackData.TAG_ID}={tag.id}&{CallbackData.TASK_ID}={task.id}")
        keyboard.append([button])
    markup = InlineKeyboardMarkup(keyboard)
    return markup