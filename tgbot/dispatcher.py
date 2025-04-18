import telebot
from tgbot.models import Configuration, TelegramBotToken
from loguru import logger
from tgbot.logics.commands import init_bot_commands

from telebot import TeleBot
from telebot.types import Update, Message, CallbackQuery
from tgbot.handlers.user_helper import sync_user_data

class SyncBot(TeleBot):
    def process_new_updates(self, updates: list[Update]):
        to_handle = []
        for update in updates:
            user, _ = sync_user_data(update.message or update.callback_query)
            if self._handle_blocked_user(update, user):
                continue
            to_handle.append(update)

        if to_handle:
            super().process_new_updates(to_handle)

    def _handle_blocked_user(self, update: Update, user) -> bool:
        if not user or not user.blocked:
            return False

        msg = "❌ Вы заблокированы и не можете пользоваться ботом."
        try:
            if update.message:
                self.send_message(
                    chat_id=update.message.chat.id,
                    text=msg,
                    reply_to_message_id=update.message.message_id
                )
            else:
                self.answer_callback_query(update.callback_query.id, msg)

            # **ВАЖНО**: вручную повышаем offset, чтобы этот update не вернулся
            try:
                self.last_update_id = update.update_id
            except AttributeError:
                self._last_update_id = update.update_id

            logger.info(f"_handle_blocked_user: апдейт {update.update_id} съеден (пользователь заблокирован)")
        except Exception as e:
            logger.error(f"_handle_blocked_user: ошибка при обработке заблокированного: {e}")

        return True

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
