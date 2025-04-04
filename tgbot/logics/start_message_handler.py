import time

from loguru import logger
logger.add("logs/start_message.log", rotation="10 MB", level="INFO")

from tgbot.dispatcher import bot
from tgbot.models import TelegramUser
from tgbot.logics.constants import *

def send_welcome_message(created: bool, user: TelegramUser) -> None:
    """
    Отправляет приветственное сообщение пользователю.
    
    Если пользователь только что создан или не имеет права публиковать задания,
    отправляется сообщение Messages.WELCOME_MESSAGE.
    Если же пользователь имеет право публиковать задания (can_publish_tasks == True),
    отправляется сообщение Messages.CHAT_ACTIVE_MESSAGE, которое через 5 секунд удаляется.
    
    :param created: Флаг, указывающий, был ли пользователь только что создан.
    :param user: Экземпляр модели TelegramUser.
    """
    if created or not user.can_publish_tasks:
        message_text = Messages.WELCOME_MESSAGE
        sent_message = bot.send_message(user.chat_id, message_text, parse_mode="MarkdownV2")
        logger.info(f"Отправлено приветственное сообщение (WELCOME_MESSAGE) пользователю {user.chat_id}")
    else:
        message_text = Messages.CHAT_ACTIVE_MESSAGE
        sent_message = bot.send_message(user.chat_id, message_text, parse_mode="MarkdownV2")
        logger.info(f"Отправлено активное сообщение (CHAT_ACTIVE_MESSAGE) пользователю {user.chat_id}")
        time.sleep(5)
        bot.delete_message(user.chat_id, sent_message.message_id)
        logger.info(f"Удалено активное сообщение для пользователя {user.chat_id}")
