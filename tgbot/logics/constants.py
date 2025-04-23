class CallbackData:
    TAG_SELECT = "tag_select"
    TAG_ID = "tag_id"
    TAG_TOGGLE = "tag_toggle"
    CLOSE_TAG_TOGGLES = "close_tag_toggles"

    TASK_ID = "task_id"
    TASK_CLOSE = "task_close"
    TASK_CANCEL = "task_cancel"
    TASK_REPEAT = "task_repeat"

    RESPONSE_CANCEL = "response_cancel"
    RESPONSE_ID = "response_id"

    PAYMENT_SELECT = "payment_select"
    PAYMENT_ID = "payment_id"

class Commands:
    START = "start"
    RULES = "rules"
    CHAT = "chat"
    ADMIN = "admin"
    TODAY = "today"

class ButtonNames:
    CLOSE = "Закрыть"
    CANCEL = "Отменить"
    REPEAT = "Повторить"

class Urls:
    RULES = "https://telegra.ph/pravila-03-15-224"
    GENERAL_CHAT = "https://t.me/+J8BI5oX0iN4xOGRi"
    SUPPORT = "https://t.me/OpenLocks_Support"

class Constants:
    MIN_TEXT_LENGTH = 13
    USER_MENTION_PROBLEM = "USER_MENTION_PROBLEM"
    RANDOM_LIST_SEED = 2649037
    NUMBER_LENGTH = 4

class Messages:
    WELCOME_MESSAGE = f"Для добавления напишите [Администратору]({Urls.SUPPORT})\nПосле добавления введите /start"
    CHAT_ACTIVE_MESSAGE = "Чат активен, вы можете принимать и отправлять заявки, приятного пользования"
    
    USER_CANT_PUBLISH_TASKS = f"❗️ У вас пока нет доступа к публикации, редактированию или отклику на заявки.\nЧтобы получить права, обратитесь к [Администратору]({Urls.SUPPORT})"
    USER_IS_NO_REGISTERED = "❗️ Вы не зарегистрированы в системе. Пожалуйста, отправьте команду /start для начала работы."
    TASK_TEXT_IS_TOO_SHORT = f"❗️ Заявка не создана: текст слишком короткий (минимум {Constants.MIN_TEXT_LENGTH} символов)."
    TASK_TEXT_IS_NOT_DEFINIDED = "❗️ Заявка не создана: нет текста для описания."
    USER_CANT_DO_IT = "❌ У вас нет права выполнять это действие.\nОбратитесь к Администратору"

    USER_MENTION_PROBLEM = """⚠️ Не удалось создать упоминание вашим именем.
Пожалуйста, включите пересылку сообщений от бота:
Настройки → Конфиденциальность → Пересылка сообщений"""

    RULES = f"[Правила использования]({Urls.RULES})"


class CommandsNames:
    START = "Старт бота и проверка доступа к публикации заданий"
    RULES = "Правила использования"
    CHAT = "Общий чат"
    ADMIN = "Контакт администратора"
    TODAY = "Заявки за день"