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
    GENERAL_CHAT = "chat"
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
    WELCOME_MESSAGE_GROUP = f"Бот работает в групповом чате"
    CHAT_ACTIVE_MESSAGE = "Чат активен, вы можете принимать и отправлять заявки, приятного пользования"
    
    DISPATHER_TASK_TEXT = "*Ваша заявка №{random_task_number}:*\n{description}\n"
    RESPONSES = "\n*Отклики:*\n"
    MASTER_WANT_TO_PICK_UP_TASK = "Мастер {mention} хочет забрать заявку {payment_type}\n"

    MASTER_TASK_TEXT = "*Заявка №{random_task_number}:\nДиспетчер:* {mention}\n{description}\n"

    TASK_CANCELED = "Заявка отменена."
    TASK_CLOSED = "Заявка закрыта."
    TASK_CLOSED_TASK_TEXT = "*Заявка закрыта*\n\n{task_text}"
    TASK_REPEATED = "Заявка выложена повторно."
    TASK_REPEATED_TASK_TEXT = "*Заявка выложена повторно*:\n{task_text}"
    RESPONSE_SENT = "Ваш отклик отправлен"
    RESPONSE_SENT_TASK_TEXT = "*Ваш отклик отправлен*\n\n{task_text}"
    RESPONSE_CANCELED = "Ваш отклик удалён."
    RESPONSE_CANCELED_TASK_TEXT = "*Ваш отклик удалён*\n\n{task_text}"

    DISPATCHER_CANNOT_RESPOND_TO_HIS_REQUEST = "❗️ Вы не можете откликнуться на свою заявку"
    USER_CANT_PUBLISH_TASKS = f"❗️ У вас пока нет доступа к публикации, редактированию или отклику на заявки.\nЧтобы получить права, обратитесь к [Администратору]({Urls.SUPPORT})"
    USER_IS_NO_REGISTERED = "❗️ Вы не зарегистрированы в системе. Пожалуйста, отправьте команду /start для начала работы."
    TASK_TEXT_IS_TOO_SHORT = f"❗️ Заявка не создана: текст слишком короткий (минимум {Constants.MIN_TEXT_LENGTH} символов)."
    TASK_TEXT_IS_NOT_DEFINIDED = "❗️ Заявка не создана: нет текста для описания."
    USER_CANT_DO_IT = "❌ У вас нет права выполнять это действие.\nОбратитесь к Администратору"

    USER_MENTION_PROBLEM = """⚠️ Не удалось создать упоминание вашим именем.
Пожалуйста, включите пересылку сообщений от бота:
Настройки → Конфиденциальность → Пересылка сообщений"""
    USER_BLOCKED = "❌ Вы заблокированы и не можете пользоваться ботом."
    GROUP_BLOCKED = "❌ Эта группа заблокирована и вы не можете пользоваться в ней этим ботом."

    RULES = f"[Правила использования]({Urls.RULES})"
    GENERAL_CHAT = f"[Общий чат]({Urls.GENERAL_CHAT})"
    ADMIN = f"Админ может ответить в течение нескольких часов.\n[Админ]({Urls.SUPPORT})"

    USER_NOT_FOUND_ERROR = "Ошибка: пользователь не найден."
    MISSING_PARAMETERS_ERROR = "Ошибка: отсутствуют параметры."
    INCORRECT_VALUE_ERROR = "Ошибка: неверное значение для {key}."
    TASK_NOT_FOUND_ERROR = "Ошибка: заявка не найдена."
    MISSING_TASK_ID_ERROR = "Ошибка: отсутствует task_id."
    MISSING_PAYMENT_ID_ERROR = "Ошибка: отсутствует payment_id."
    PAYMENT_NOT_FOUND_ERROR = "Ошибка: выбранный тип оплаты не найден."
    MISSING_RESPONSE_ID_ERROR = "Ошибка: отсутствует response_id."
    RESPONSE_NOT_FOUND_ERROR = "Ошибка: отклик не найден."

class CommandsNames:
    START = "Старт бота и проверка доступа к публикации заданий"
    RULES = "Правила использования"
    GENERAL_CHAT = "Общий чат"
    ADMIN = "Контакт администратора"
    TODAY = "Заявки за день"