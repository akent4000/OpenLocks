import telebot
from tgbot.models import Configuration, TelegramBotToken
from loguru import logger

logger.add("logs/dispatcher.log", rotation="10 MB", level="INFO")

main_bot_token = TelegramBotToken.get_main_bot_token()
test_bot_token = TelegramBotToken.get_test_bot_token()

# Подмена токенов в тестовом режиме
if Configuration.get_is_test_mode():
    if test_bot_token:
        main_bot_token, test_bot_token = test_bot_token, main_bot_token
        logger.info("Running in test mode — tokens swapped.")
    else:
        logger.warning("Running in test mode, but test token is missing. Using main token as is.")

# Инициализация ботов
bot = telebot.TeleBot(main_bot_token)
logger.info("Main bot instance created")

# Тестовый бот может отсутствовать
test_bot = None
if test_bot_token:
    test_bot = telebot.TeleBot(test_bot_token)
    logger.info("Test bot instance created")
else:
    logger.warning("Test bot token not provided — test_bot is not initialized.")
