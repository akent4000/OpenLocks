
# import telebot

# from tgbot.models import Configuration, TelegramBotToken
# from loguru import logger

# main_bot_token = TelegramBotToken.get_main_bot_token()
# test_bot_token = TelegramBotToken.get_test_bot_token()

# if Configuration.is_test_mode():
#     main_bot_token, test_bot_token = test_bot_token, main_bot_token

# logger.add("logs/dispatcher.log", rotation="10 MB", level="INFO")
# bot = telebot.TeleBot(main_bot_token)
# test_bot = telebot.TeleBot(test_bot_token)
# logger.info("Bot instance created")
