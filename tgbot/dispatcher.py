import telebot
from tgbot.models import Configuration, TelegramBotToken
from loguru import logger
from tgbot.logics.commands import init_bot_commands

from telebot import TeleBot
from telebot.types import Update, Message, CallbackQuery
from tgbot.handlers.user_helper import sync_user_data

class SyncBot(TeleBot):
    def process_new_updates(self, updates: list[Update]):
        for update in updates:
            if update.message:
                sync_user_data(update.message)
            elif update.callback_query:
                sync_user_data(update.callback_query)
        super().process_new_updates(updates)

logger.add("logs/dispatcher.log", rotation="10 MB", level="INFO")

main_bot_token = TelegramBotToken.get_main_bot_token()
test_bot_token = TelegramBotToken.get_test_bot_token()

# Подмена токенов в тестовом режиме
if Configuration.get_solo().test_mode:
    if test_bot_token:
        main_bot_token, test_bot_token = test_bot_token, main_bot_token
        logger.info("Running in test mode — tokens swapped.")
    else:
        logger.warning("Running in test mode, but test token is missing. Using main token as is.")

# Инициализация ботов
bot = SyncBot(main_bot_token)
logger.info("Main bot instance created")

# Установка команд
init_bot_commands(bot)
logger.info("Bot commands initialized")

# Тестовый бот может отсутствовать
test_bot = None
if test_bot_token:
    test_bot = SyncBot(test_bot_token)
    init_bot_commands(test_bot)
    logger.info("Test bot instance created")
else:
    logger.warning("Test bot token not provided — test_bot is not initialized.")
