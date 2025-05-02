from tgbot.models import *
from telebot.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from tgbot.logics.constants import *

from pathlib import Path
from loguru import logger

# Убедимся, что папка logs существует
Path("logs").mkdir(parents=True, exist_ok=True)

# Лог-файл будет называться так же, как модуль, например user_helper.py → logs/user_helper.log
log_filename = Path("logs") / f"{Path(__file__).stem}.log"
logger.add(str(log_filename), rotation="10 MB", level="INFO")

def dispather_task_keyboard(task: Task):
    keyboard = []
    cancel_button = InlineKeyboardButton(
        ButtonNames.CANCEL, 
        callback_data=f"{CallbackData.TASK_CANCEL}?{CallbackData.TASK_ID}={task.id}"
    )
    close_button = InlineKeyboardButton(
        ButtonNames.CLOSE, 
        callback_data=f"{CallbackData.TASK_CLOSE}?{CallbackData.TASK_ID}={task.id}"
    )
    keyboard.append([cancel_button, close_button])
    markup = InlineKeyboardMarkup(keyboard)
    return markup

def repeat_task_dispather_task_keyboard(task: Task):
    keyboard = []
    repeat_button = InlineKeyboardButton(
        ButtonNames.REPEAT, 
        callback_data=f"{CallbackData.TASK_REPEAT}?{CallbackData.TASK_ID}={task.id}"
    )
    keyboard.append([repeat_button])
    markup = InlineKeyboardMarkup(keyboard)
    return markup

def payment_types_keyboard(task: Task):
    payment_types = PaymentTypeModel.objects.all()
    if not payment_types:
        logger.error("Не найдено ни одгого типа оплаты")
        return

    keyboard = []
    for payment_type in payment_types:
        button = InlineKeyboardButton(
            payment_type.name, 
            callback_data=f"{CallbackData.PAYMENT_SELECT}?{CallbackData.PAYMENT_ID}={payment_type.id}&{CallbackData.TASK_ID}={task.id}"
        ) 
        keyboard.append([button])
    button = InlineKeyboardButton("Отменить мой отклик", callback_data="111s")
    keyboard.append([button])
    markup = InlineKeyboardMarkup(keyboard)
    return markup

def master_response_cancel_keyboard(response: Response):
    keyboard = []
    cancel_button = InlineKeyboardButton(
        ButtonNames.CANCEL, 
        callback_data=f"{CallbackData.RESPONSE_CANCEL}?{CallbackData.RESPONSE_ID}={response.id}"
    )
    keyboard.append([cancel_button])
    markup = InlineKeyboardMarkup(keyboard)
    return markup