from tgbot.models import TelegramUser
from tgbot.dispatcher import bot

from pathlib import Path
from loguru import logger

# Убедимся, что папка logs существует
Path("logs").mkdir(parents=True, exist_ok=True)

# Лог-файл будет называться так же, как модуль, например user_helper.py → logs/user_helper.log
log_filename = Path("logs") / f"{Path(__file__).stem}.log"
logger.add(str(log_filename), rotation="10 MB", level="INFO")

def send_messege_to_admins(msg, markup=None, admins=None):
    admins = admins if admins is not None else TelegramUser.objects.filter(send_admin_notifications=True)
    for admin in admins:
        try:
            bot.send_message(admin.chat_id, msg, reply_markup=markup)
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление администратору {admin.chat_id}. Ошибка: {e}")