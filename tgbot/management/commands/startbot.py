#!/usr/bin/python3

import threading
import time
import traceback
from pathlib import Path

from django.core.management.base import BaseCommand
from tgbot import dispatcher
from tgbot.models import Configuration
from tgbot.logics.info_for_admins import send_messege_to_admins
from loguru import logger

# Убедимся, что папка logs существует
Path("logs").mkdir(parents=True, exist_ok=True)
log_filename = Path("logs") / f"{Path(__file__).stem}.log"
logger.add(str(log_filename), rotation="10 MB", level="INFO")

# Глобальные треды
_main_thread = None
_test_thread = None

def _run_main_bot():
    """Цикл polling для основного бота."""
    from tgbot.handlers import commands, message_handler, utils
    while True:
        try:
            logger.info('Основной бот запущен')
            dispatcher.bot.polling(none_stop=True, interval=0, timeout=20)
        except Exception as e:
            logger.error(f"Ошибка в основном боте: {e}\n{traceback.format_exc()}")
            send_messege_to_admins(f"Ошибка в основном боте: {e}\n{traceback.format_exc()}\n\nБот перезапущен")
            dispatcher.bot.stop_polling()
            time.sleep(1)
            logger.info("Перезапуск основного бота...")

def _run_test_bot():
    """Цикл polling для тестового бота (активен только в test_mode)."""
    if dispatcher.test_bot is None:
        logger.warning("Тестовый бот не инициализирован, поток завершается.")
        return
    while True:
        try:
            if Configuration.get_solo().test_mode:
                logger.info('Тестовый бот запущен')
                @dispatcher.test_bot.message_handler(func=lambda message: True)
                def handle_all_messages(message):
                    dispatcher.test_bot.reply_to(
                        message,
                        "⚠️ *Технические работы*",
                        parse_mode="Markdown"
                    )
                dispatcher.test_bot.polling(none_stop=True, interval=0, timeout=20)
            else:
                # Если test_mode выключен — немного подождём и проверим снова
                time.sleep(5)
        except Exception as e:
            logger.error(f"Ошибка в тестовом боте: {e}\n{traceback.format_exc()}")
            dispatcher.test_bot.stop_polling()
            time.sleep(5)
            logger.info("Перезапуск тестового бота...")

def start_bots():
    """Запустить оба бота (если они уже запущены — перезапустит)."""
    global _main_thread, _test_thread

    # Если уже запущены — остановим
    stop_bots()
    time.sleep(2)
    logger.info("Запускаем основные треды ботов")
    _main_thread = threading.Thread(target=_run_main_bot, daemon=True)
    _test_thread = threading.Thread(target=_run_test_bot, daemon=True)
    _main_thread.start()
    _test_thread.start()

def stop_bots(join_timeout: float = 5.0):
    """Остановить polling у обоих ботов и дождаться тредов."""
    global _main_thread, _test_thread

    try:
        dispatcher.bot.stop_polling()
    except Exception:
        pass
    try:
        if dispatcher.test_bot:
            dispatcher.test_bot.stop_polling()
    except Exception:
        pass

    # join с таймаутом, чтобы не блокировать навсегда
    if _main_thread and _main_thread.is_alive():
        _main_thread.join(join_timeout)
    if _test_thread and _test_thread.is_alive():
        _test_thread.join(join_timeout)

def restart_bots():
    """Удобная обёртка: останавливает и запускает заново."""
    logger.info("Перезапуск ботов извне")
    start_bots()

class Command(BaseCommand):
    help = 'Запускает два бота на платформе Telegram'

    def handle(self, *args, **options):
        # При старте management command просто запускаем ботов и ждём тредов
        start_bots()
        # Блокируем основной поток, пока треды живы
        if _main_thread:
            _main_thread.join()
        if _test_thread:
            _test_thread.join()
