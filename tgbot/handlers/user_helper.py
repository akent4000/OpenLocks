from telebot.types import Message, CallbackQuery
from tgbot.models import TelegramUser
from tgbot.models import Configuration
from loguru import logger

def sync_user_data(update: Message | CallbackQuery) -> TelegramUser | None:
    """
    Синхронизирует поля TelegramUser (first_name, last_name, username, can_publish_tasks)
    на основании приходящего Message или CallbackQuery.
    Возвращает объект TelegramUser или None, если не удалось получить chat_id.
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

    chat_id = chat.id

    # 2) Получаем или создаем пользователя
    user, created = TelegramUser.objects.get_or_create(
        chat_id=chat_id,
        defaults={
            "first_name": chat.first_name or "",
            "last_name": chat.last_name or "",
            "username": chat.username or "",
            "can_publish_tasks": Configuration.get_solo().auto_request_permission,
        }
    )

    # 3) При необходимости обновляем изменившиеся поля
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
    desired_flag = Configuration.get_solo().auto_request_permission
    if user.can_publish_tasks != desired_flag:
        user.can_publish_tasks = desired_flag
        changed = True

    if changed:
        try:
            user.save()
            logger.info(f"sync_user_data: Updated TelegramUser {user.chat_id}")
        except Exception as e:
            logger.error(f"sync_user_data: Failed to save TelegramUser {user.chat_id}: {e}")

    else:
        logger.debug(f"sync_user_data: No changes for TelegramUser {user.chat_id}")

    return user, created