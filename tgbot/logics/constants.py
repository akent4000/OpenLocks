class CallbackData:
    TAG_SELECT = "tag_select"
    TAG_ID = "tag_id"

    TASK_ID = "task_id"
    TASK_CLOSE = "task_close"
    TASK_CANCEL = "task_cancel"
    TASK_REPEAT = "task_repeat"

    RESPONSE_CANCEL = "response_cancel"
    RESPONSE_ID = "response_id"

    PAYMENT_SELECT = "payment_select"
    PAYMENT_ID = "payment_id"

class ButtonNames:
    CLOSE = "Закрыть"
    CANCEL = "Отменить"
    REPEAT = "Повторить"

class Urls:
    RULES = "https://telegra.ph/pravila-03-15-224"
    GENERAL_CHAT = "https://t.me/+J8BI5oX0iN4xOGRi"
    SUPPORT = "https://t.me/OpenLocks_Support"

class Messages:
    WELCOME_MESSAGE = f"""Для добавления напишите [Админу]({Urls.SUPPORT})
После добавления введите /start
"""
    CHAT_ACTIVE_MESSAGE = "Чат активен, вы можете принимать и отправлять заявки, приятного пользования"
    