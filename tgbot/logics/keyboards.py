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
    repeat_button = InlineKeyboardButton(
        ButtonNames.REPEAT, 
        callback_data=f"{CallbackData.TASK_REPEAT}?{CallbackData.TASK_ID}={task.id}"
    )
    keyboard.append([cancel_button, close_button, repeat_button])
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

def tag_toggle_keyboard(user: TelegramUser):
    """
    Генератор клавиатуры для настройки подписки на теги.
    Между иконкой и названием тега добавляется ровно столько эм‑пробелов (\u2003),
    чтобы все названия визуально выровнялись по ширине.
    """
    tags = Tag.objects.all()
    if not tags:
        logger.error("Не найден ни один тег для настройки подписки.")
        return None

    names = [tag.name for tag in tags]
    max_len = max(len(name) for name in names)

    subscribed = set(user.subscribed_tags.values_list("id", flat=True))
    keyboard = []

    for tag in tags:
        name = tag.name
        spaces_needed = (max_len - len(name)) + 1
        spacer = "\u2003" * spaces_needed

        status_icon = "🟢" if tag.id in subscribed else "⚪️"
        button_text = f"{status_icon}{spacer}{name}"

        button = InlineKeyboardButton(
            text=button_text,
            callback_data=f"{CallbackData.TAG_TOGGLE}?{CallbackData.TAG_ID}={tag.id}"
        )
        keyboard.append([button])

    return InlineKeyboardMarkup(keyboard)