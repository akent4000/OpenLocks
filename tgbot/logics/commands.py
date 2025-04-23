from telebot import types
from tgbot.logics.constants import Commands, CommandsNames

from pathlib import Path
from loguru import logger

# Убедимся, что папка logs существует
Path("logs").mkdir(parents=True, exist_ok=True)

# Лог-файл будет называться так же, как модуль, например user_helper.py → logs/user_helper.log
log_filename = Path("logs") / f"{Path(__file__).stem}.log"
logger.add(str(log_filename), rotation="10 MB", level="INFO")

def init_bot_commands(bot):
    """
    Устанавливает команды бота для всех пользователей.
    """
    commands = [
        types.BotCommand(Commands.START, CommandsNames.START),
        types.BotCommand(Commands.RULES, CommandsNames.RULES),
        types.BotCommand(Commands.CHAT,  CommandsNames.CHAT),
        types.BotCommand(Commands.ADMIN, CommandsNames.ADMIN),
        types.BotCommand(Commands.TODAY, CommandsNames.TODAY),
        #TAGS
        #types.BotCommand(Commands.TAGS, "Настройка тегов на которые вы подписаны"),
    ]

    bot.set_my_commands(commands)
