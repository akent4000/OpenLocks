class CallbackData:
    START = "start"

    RULES = "rules"
    GENERAL_CHAT = "general_chat"
    SUPPORT = "support"
    REQUEST_PER_DAY = "request_per_day"

class ButtonNames:
    START = "Старт"

    RULES = "Правила"
    GENERAL_CHAT = "Общий чат"
    SUPPORT = "Админ"
    REQUEST_PER_DAY = "Заявки за день"
    
    CLOSE = "Закрыть"
    CANCEL = "Отменить"
    REPEAT = "Повторить" 
class Urls:
    RULES = "https://telegra.ph/pravila-03-15-224"
    GENERAL_CHAT = "https://t.me/+J8BI5oX0iN4xOGRi"
    SUPPORT = "https://t.me/OpenLocks_Support"

class Messages:
    WELCOME_MESSAGE = f"""Для добавления напишите [админу]({Urls.SUPPORT})
После добавления введите {ButtonNames.START}
"""
    CHAT_ACTIVE_MESSAGE = "Чат активен, вы можете принимать и отправлять заявки, приятного пользования"
    