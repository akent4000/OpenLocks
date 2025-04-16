from telebot import types

def init_bot_commands(bot):
    """
    Устанавливает команды бота для всех пользователей.
    """
    commands = [
        types.BotCommand("start", "Старт бота и проверка доступа к публикации заданий"),
        types.BotCommand("rules", "Правила использования"),
        types.BotCommand("chat", "Общий чат"),
        types.BotCommand("admin", "Админ-панель"),
        types.BotCommand("today", "Заявки за день"),
        types.BotCommand("tags", "Настройка тегов на которые подписан пользователь"),
    ]

    bot.set_my_commands(commands)
