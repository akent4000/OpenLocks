import telebot
from tgbot.logics.constants import Messages
from tgbot.models import Configuration, TelegramBotToken
from tgbot.logics.commands import init_bot_commands
from typing import List
from telebot import TeleBot
from telebot.types import Update, Message, CallbackQuery
from telebot.apihelper import ApiException

from tgbot.handlers.user_helper import sync_user_data
from tgbot.logics.random_numbers import RandomNumberList

from pathlib import Path
from loguru import logger

# Убедимся, что папка logs существует
Path("logs").mkdir(parents=True, exist_ok=True)

# Лог-файл будет называться так же, как модуль, например user_helper.py → logs/user_helper.log
log_filename = Path("logs") / f"{Path(__file__).stem}.log"
logger.add(str(log_filename), rotation="10 MB", level="INFO")

class SyncBot(TeleBot):
    def _eat_update(self, update: Update):
        """
        Повышает offset (last_update_id), чтобы этот update не возвращался.
        """
        try:
            # TeleBot хранит последний апдейт в last_update_id или _last_update_id
            self.last_update_id = update.update_id
        except AttributeError:
            self._last_update_id = update.update_id
        logger.debug(f"_eat_update: съеден update {update.update_id}")

    def process_new_updates(self, updates: List[Update]):
        """
        Фильтрует и обрабатывает только те обновления, из которых удалось
        безопасно получить данные пользователя и которые не заблокированы.
        Все пропущенные апдейты «съедаются» методом _eat_update.
        """
        to_handle: List[Update] = []

        for update in updates:
            # 1) Достаем сообщение или callback
            message_or_callback = update.message or update.callback_query
            if message_or_callback is None:
                logger.debug("Пропущен update без message/callback: %r", update)
                self._eat_update(update)
                continue

            # 2) Синхронизация данных пользователя
            try:
                data = sync_user_data(message_or_callback)
            except Exception as e:
                logger.exception("Ошибка sync_user_data для update %r: %s", update, e)
                self._eat_update(update)
                continue

            # 3) Если sync_user_data вернул None (например, групповой чат) — тоже пропускаем
            if not data:
                logger.debug("sync_user_data вернул None — пропускаем update %s", update.update_id)
                self._eat_update(update)
                continue

            # 4) Проверяем, не заблокирован ли пользователь
            user, _ = data
            try:
                if self._handle_blocked_user(update, user):
                    # внутри _handle_blocked_user уже съедает апдейт
                    continue
            except Exception as e:
                logger.exception(
                    "Ошибка при проверке блокировки пользователя %s: %s", user.id, e
                )
                self._eat_update(update)
                continue

            # 5) Всё успешно — добавляем к обработке
            to_handle.append(update)

        # 6) Передаём оставшиеся апдейты в TeleBot
        if to_handle:
            try:
                super().process_new_updates(to_handle)
            except Exception as e:
                logger.exception("Ошибка super().process_new_updates: %s", e)

    def _handle_blocked_user(self, update: Update, user) -> bool:
        if not user or not user.blocked:
            return False

        msg = Messages.USER_BLOCKED
        try:
            if update.message:
                self.send_message(
                    chat_id=update.message.chat.id,
                    text=msg,
                    reply_to_message_id=update.message.message_id
                )
            else:
                self.answer_callback_query(update.callback_query.id, msg)

            # «Съедаем» update прямо здесь
            self._eat_update(update)

            logger.info(f"_handle_blocked_user: апдейт {update.update_id} съеден (заблокирован)")
        except Exception as e:
            logger.error(f"_handle_blocked_user: ошибка при обработке заблокированного: {e}")

        return True
    
    def edit_message_text(
        self,
        chat_id: int,
        message_id: int,
        text: str,
        parse_mode: str | None = None,
        reply_markup = None,
        **kwargs
    ):
        """
        Безопасно правит текст и/или клавиатуру сообщения.
        Игнорирует ошибку 'message is not modified' от Telegram API.
        """
        try:
            return super().edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                parse_mode=parse_mode,
                reply_markup=reply_markup,
                **kwargs
            )
        except ApiException as e:
            err = str(e).lower()
            if "message is not modified" in err or "reply_markup is not modified" in err:
                # ничего не изменилось — пропускаем
                return None
            # другая ошибка — логируем и пробрасываем
            logger.error(f"Не удалось отредактировать сообщение {message_id}: {e}")
            raise

    def edit_message_reply_markup(
        self,
        chat_id: int,
        message_id: int,
        reply_markup,
        **kwargs
    ):
        """
        Безопасно правит только клавиатуру.
        Игнорирует 'reply_markup is not modified'.
        """
        try:
            return super().edit_message_reply_markup(
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=reply_markup,
                **kwargs
            )
        except ApiException as e:
            err = str(e).lower()
            if "reply_markup is not modified" in err or "message is not modified" in err:
                return None
            logger.error(f"Не удалось отредактировать клавиатуру для {message_id}: {e}")
            raise

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
