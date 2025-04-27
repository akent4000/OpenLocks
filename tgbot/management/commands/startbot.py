#!/usr/bin/env python3

import os
import sys
import threading
import time
import traceback
from pathlib import Path

from django.core.management.base import BaseCommand
from tgbot import dispatcher
from tgbot.models import Configuration
from tgbot.logics.info_for_admins import send_messege_to_admins
from loguru import logger

# Создаём папку для логов
Path("logs").mkdir(parents=True, exist_ok=True)
log_filename = Path("logs") / f"{Path(__file__).stem}.log"
logger.add(str(log_filename), rotation="10 MB", level="INFO")

_main_thread = None
_test_thread = None

def _run_main_bot():
    """Цикл polling для основного бота"""
    from tgbot.handlers import commands, message_handler, utils  # noqa: F401

    while True:
        try:
            logger.info('Основной бот polling запущен')
            dispatcher.bot.polling(
                none_stop=True,
                interval=0,
                timeout=20,
                skip_pending=True
            )
        except Exception as e:
            logger.error(f"Ошибка в основном боте: {e}\n{traceback.format_exc()}")
            send_messege_to_admins(
                f"Ошибка в основном боте: {e}\n{traceback.format_exc()}\n\nБот перезапущен"
            )
            dispatcher.bot.stop_polling()
            time.sleep(1)
            logger.info("Перезапуск основного бота...")
        else:
            break

    logger.info("Поток основного бота завершён")


def _run_test_bot():
    """Цикл polling для тестового бота (только в test_mode)"""
    if dispatcher.test_bot is None:
        logger.warning("Тестовый бот не инициализирован, поток завершён")
        return

    while True:
        try:
            if Configuration.get_solo().test_mode:
                logger.info('Тестовый бот polling запущен')

                @dispatcher.test_bot.message_handler(func=lambda m: True)
                def handle_all_messages(message):  # noqa: F811
                    from tgbot.handlers.user_helper import is_group_chat
                    if is_group_chat(message):
                        return
                    dispatcher.test_bot.reply_to(
                        message,
                        "⚠️ *Технические работы*",
                        parse_mode="Markdown"
                    )

                dispatcher.test_bot.polling(
                    none_stop=True,
                    interval=0,
                    timeout=20,
                    skip_pending=True
                )
            else:
                time.sleep(1)
        except Exception as e:
            logger.error(f"Ошибка в тестовом боте: {e}\n{traceback.format_exc()}")
            dispatcher.test_bot.stop_polling()
            time.sleep(1)
            logger.info("Перезапуск тестового бота...")
        else:
            break

    logger.info("Поток тестового бота завершён")


def start_bots():
    """Запустить или перезапустить оба бота"""
    global _main_thread, _test_thread

    logger.info("Запуск потоков ботов")
    _main_thread = threading.Thread(target=_run_main_bot, daemon=True)
    _test_thread = threading.Thread(target=_run_test_bot, daemon=True)
    _main_thread.start()
    _test_thread.start()

class Command(BaseCommand):
    help = 'Запускает два бота на платформе Telegram'

    def handle(self, *args, **options):
        start_bots()
        # Блокируем основной процесс, пока потоки работают
        global _main_thread, _test_thread
        if _main_thread:
            _main_thread.join()
        if _test_thread:
            _test_thread.join()
