from telebot.types import Message, CallbackQuery
from tgbot.models import TelegramUser
from tgbot.models import Configuration
from pathlib import Path
from loguru import logger

# Убедимся, что папка logs существует
Path("logs").mkdir(parents=True, exist_ok=True)

# Лог-файл будет называться так же, как модуль, например user_helper.py → logs/user_helper.log
log_filename = Path("logs") / f"{Path(__file__).stem}.log"
logger.add(str(log_filename), rotation="10 MB", level="INFO")

def sync_user_data(update: Message | CallbackQuery) -> tuple[TelegramUser, bool] | None:
    """
    Синхронизирует поля TelegramUser (first_name, last_name, username, can_publish_tasks)
    на основании приходящего Message или CallbackQuery.
    Возвращает кортеж (user, created) или None, если не удалось получить chat_id
    или если это групповой чат.
    """
    # 1) Определяем chat и chat_id
    if isinstance(update, Message):
        chat = update.chat
    elif isinstance(update, CallbackQuery):
        if not update.message:
            logger.error("sync_user_data: у CallbackQuery нет message")
            return None
        chat = update.message.chat
    else:
        logger.error(f"sync_user_data: Unsupported update type {type(update)}")
        return None

    # 2) Пропускаем групповые чаты
    if chat.type in ("group", "supergroup"):
        logger.debug("sync_user_data: пропущен групповой чат %s (%s)", chat.id, chat.type)
        return None

    chat_id = chat.id

    # 3) Получаем или создаем пользователя
    user, created = TelegramUser.objects.get_or_create(
        chat_id=chat_id,
        defaults={
            "first_name": chat.first_name or "",
            "last_name": chat.last_name or "",
            "username": chat.username or "",
            "can_publish_tasks": Configuration.get_solo().auto_request_permission,
        }
    )

    # 4) При необходимости обновляем изменившиеся поля
    changed = False
    if user.first_name != (chat.first_name or ""):
        user.first_name = chat.first_name or ""
        changed = True
    if user.last_name != (chat.last_name or ""):
        user.last_name = chat.last_name or ""
        changed = True
    if user.username != (chat.username or ""):
        user.username = chat.username or ""
        changed = True

    if changed:
        try:
            user.save()
            logger.info("sync_user_data: Updated TelegramUser %s", user.chat_id)
        except Exception as e:
            logger.error("sync_user_data: Failed to save TelegramUser %s: %s", user.chat_id, e)
    else:
        logger.debug("sync_user_data: No changes for TelegramUser %s", user.chat_id)

    return user, created
