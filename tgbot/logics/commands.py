from telebot import types
from tgbot.logics.constants import Commands
def init_bot_commands(bot):
    """
    Устанавливает команды бота для всех пользователей.
    """
    commands = [
        types.BotCommand(Commands.START, "Старт бота и проверка доступа к публикации заданий"),
        types.BotCommand(Commands.RULES, "Правила использования"),
        types.BotCommand(Commands.CHAT, "Общий чат"),
        types.BotCommand(Commands.ADMIN, "Контакт администратора"),
        types.BotCommand(Commands.TODAY, "Заявки за день"),
        types.BotCommand(Commands.TAGS, "Настройка тегов на которые вы подписаны"),
    ]

    bot.set_my_commands(commands)
