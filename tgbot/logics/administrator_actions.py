from tgbot.models import TelegramUser
import telebot
from tgbot.dispatcher import bot
import time
from tgbot.logics.constants import *
from pathlib import Path
from loguru import logger

Path("logs").mkdir(parents=True, exist_ok=True)

log_filename = Path("logs") / f"{Path(__file__).stem}.log"
logger.add(str(log_filename), rotation="10 MB", level="INFO")

def mass_mailing(admin: TelegramUser, users:list[TelegramUser]=None, text = None, ):
    msg = ""
    if text is not None and admin is not None:
        msg = f"{text}\n\n{admin.admin_signature or 'Администратор'}"
    else:
        return None
    
    if users is None:
        users = TelegramUser.objects.exclude(blocked=True)
    total_users = len(users)

    num = 0
    for user in users:
        try:
            bot.send_message(user.chat_id, msg)
            num += 1
        except Exception as e:
            logger.error(f"mass_mailing: Failed to send message to {user.chat_id}: {e}")

    final_text = f"Рассылка закончена\nКоличество обработанных пользователей:\n{total_users} из {total_users}\nУспешно отправлено: {num}\nОшибок отправки: {total_users - num}"
    return final_text