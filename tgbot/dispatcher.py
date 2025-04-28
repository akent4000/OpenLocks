import telebot
from tgbot.logics.constants import Messages
from tgbot.models import Configuration, TelegramBotToken, TelegramUser
from tgbot.logics.commands import init_bot_commands
from typing import List
from telebot import TeleBot
from telebot.types import Update, Message, CallbackQuery
from telebot.apihelper import ApiException

from tgbot.handlers.user_helper import sync_user_data
from tgbot.logics.random_numbers import RandomNumberList

from pathlib import Path
from loguru import logger
import time
import threading
import queue
import concurrent.futures

# Убедимся, что папка logs существует
Path("logs").mkdir(parents=True, exist_ok=True)

# Лог-файл будет называться так же, как модуль, например user_helper.py → logs/user_helper.log
log_filename = Path("logs") / f"{Path(__file__).stem}.log"
logger.add(str(log_filename), rotation="10 MB", level="INFO")

class SyncBot(TeleBot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # очередь задач: каждый элемент — (func, args, kwargs, future)
        self._call_queue: queue.Queue = queue.Queue()
        # поток-демон, который обрабатывает очередь
        self._worker = threading.Thread(target=self._process_queue, daemon=True)
        self._worker.start()

    def _process_queue(self):
        while True:
            func, args, kwargs, future = self._call_queue.get()
            try:
                result = func(*args, **kwargs)
                future.set_result(result)
            except Exception as e:
                future.set_exception(e)
            # задержка между запросами
            time.sleep(0.05)

    def _enqueue(self, func, *args, **kwargs):
        """
        Помещает вызов func(*args, **kwargs) в очередь и
        возвращает его результат, блокируясь до выполнения.
        """
        future = concurrent.futures.Future()
        self._call_queue.put((func, args, kwargs, future))
        return future.result()

    # --- обёртки реальных вызовов ---
    def _do_send_message(self, chat_id, *args, **kwargs):
        try:
            msg = super().send_message(chat_id, *args, **kwargs)
        except ApiException as e:
            err = str(e).lower()
            # если бот заблокирован — отмечаем в пользователе
            if e.error_code == 403 and "bot was blocked by the user" in err:
                try:
                    u = TelegramUser.objects.get(chat_id=chat_id)
                    u.bot_was_blocked = True
                    u.save(update_fields=['bot_was_blocked'])
                    logger.info(f"User {chat_id} blocked bot, flag set")
                except TelegramUser.DoesNotExist:
                    logger.warning(f"No TelegramUser with chat_id={chat_id}")
                return None
            raise
        else:
            # при успешной отправке — сбрасываем признак блокировки
            try:
                u = TelegramUser.objects.get(chat_id=chat_id)
                if u.bot_was_blocked:
                    u.bot_was_blocked = False
                    u.save(update_fields=['bot_was_blocked'])
                    logger.info(f"User {chat_id} unblocked bot, flag cleared")
            except TelegramUser.DoesNotExist:
                pass
            return msg

    def _do_edit_message_text(self, chat_id, message_id, text, parse_mode=None, reply_markup=None, **kwargs):
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
                return None
            logger.error(f"Failed to edit_message_text {message_id}: {e}")
            raise

    def _do_edit_message_reply_markup(self, chat_id, message_id, reply_markup, **kwargs):
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
            logger.error(f"Failed to edit_message_reply_markup {message_id}: {e}")
            raise

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
        from tgbot.handlers.user_helper import is_group_chat
        if not user or not user.blocked:
            return False
        
        msg = Messages.GROUP_BLOCKED if is_group_chat(update.message or update.callback_query) else Messages.USER_BLOCKED
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
    
    def _do_answer_callback_query(self, callback_query_id, *args, **kwargs):
        try:
            return super().answer_callback_query(callback_query_id, *args, **kwargs)
        except ApiException as e:
            err = str(e).lower()
            if e.error_code == 403 and "bot was blocked by the user" in err:
                # блокировка при ответе на callback
                # можно отметить, если нужно, но обычно это не критично
                logger.info(f"Callback {callback_query_id}: bot blocked by user")
                return None
            raise

    def _do_delete_message(self, chat_id, message_id):
        try:
            return super().delete_message(chat_id, message_id)
        except ApiException as e:
            err = str(e).lower()
            # Telegram может вернуть 400 Bad Request: "Message to delete not found"
            if "message to delete not found" in err or "message can't be deleted" in err:
                return None
            logger.error(f"Не удалось delete_message {message_id}: {e}")
            raise

    def _do_send_media_group(self, chat_id, media, *args, **kwargs):
        try:
            msgs = super().send_media_group(chat_id, media, *args, **kwargs)
        except ApiException as e:
            err = str(e).lower()
            if e.error_code == 403 and "bot was blocked by the user" in err:
                TelegramUser.objects.filter(chat_id=chat_id).update(bot_was_blocked=True)
                return None
            raise
        else:
            TelegramUser.objects.filter(chat_id=chat_id, bot_was_blocked=True).update(bot_was_blocked=False)
            return msgs

    def _do_send_photo(self, chat_id, *args, **kwargs):
        try:
            return super().send_photo(chat_id, *args, **kwargs)
        except ApiException as e:
            if e.error_code == 403 and "bot was blocked by the user" in str(e).lower():
                TelegramUser.objects.filter(chat_id=chat_id).update(bot_was_blocked=True)
                return None
            raise

    def _do_send_video(self, chat_id, *args, **kwargs):
        try:
            return super().send_video(chat_id, *args, **kwargs)
        except ApiException as e:
            if e.error_code == 403 and "bot was blocked by the user" in str(e).lower():
                TelegramUser.objects.filter(chat_id=chat_id).update(bot_was_blocked=True)
                return None
            raise

    def _do_send_document(self, chat_id, *args, **kwargs):
        try:
            return super().send_document(chat_id, *args, **kwargs)
        except ApiException as e:
            if e.error_code == 403 and "bot was blocked by the user" in str(e).lower():
                TelegramUser.objects.filter(chat_id=chat_id).update(bot_was_blocked=True)
                return None
            raise

    def send_message(self, chat_id, *args, **kwargs):
        return self._enqueue(self._do_send_message, chat_id, *args, **kwargs)
    
    def send_media_group(self, chat_id, media, *args, **kwargs):
        return self._enqueue(self._do_send_media_group, chat_id, media, *args, **kwargs)

    def send_photo(self, chat_id, *args, **kwargs):
        return self._enqueue(self._do_send_photo, chat_id, *args, **kwargs)

    def send_video(self, chat_id, *args, **kwargs):
        return self._enqueue(self._do_send_video, chat_id, *args, **kwargs)

    def send_document(self, chat_id, *args, **kwargs):
        return self._enqueue(self._do_send_document, chat_id, *args, **kwargs)

    def edit_message_text(self, chat_id, message_id, text, parse_mode=None, reply_markup=None, **kwargs):
        return self._enqueue(
            self._do_edit_message_text,
            chat_id, message_id, text, parse_mode, reply_markup, **kwargs
        )

    def edit_message_reply_markup(self, chat_id, message_id, reply_markup, **kwargs):
        return self._enqueue(
            self._do_edit_message_reply_markup,
            chat_id, message_id, reply_markup, **kwargs
        )

    def answer_callback_query(self, callback_query_id, *args, **kwargs):
        return self._enqueue(self._do_answer_callback_query, callback_query_id, *args, **kwargs)
    
    def delete_message(self, chat_id, message_id):
        return self._enqueue(self._do_delete_message, chat_id, message_id)

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

logger.info(bot.get_chat(583655273).type)

# Тестовый бот может отсутствовать
test_bot = None
if test_bot_token:
    test_bot = SyncBot(test_bot_token)
    init_bot_commands(test_bot)
    logger.info("Test bot instance created")
else:
    logger.warning("Test bot token not provided — test_bot is not initialized.")
