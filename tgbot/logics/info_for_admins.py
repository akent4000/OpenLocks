from tgbot.models import TelegramUser
from tgbot.dispatcher import bot

def send_messege_to_admins(msg, markup=None, admins=None):
    admins = admins if admins is not None else TelegramUser.objects.filter(send_admin_notifications=True)
    for admins in admins:
        try:
            bot.send_message(admins.chat_id, msg, reply_markup=markup)
        except:
            pass