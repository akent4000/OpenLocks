#!/usr/bin/python3

import threading
import time
from django.core.management.base import BaseCommand
from tgbot import dispatcher
from tgbot.models import Configuration
import traceback
from tgbot.logics.info_for_admins import send_messege_to_admins

from pathlib import Path
from loguru import logger

# Убедимся, что папка logs существует
Path("logs").mkdir(parents=True, exist_ok=True)

# Лог-файл будет называться так же, как модуль, например user_helper.py → logs/user_helper.log
log_filename = Path("logs") / f"{Path(__file__).stem}.log"
logger.add(str(log_filename), rotation="10 MB", level="INFO")

class Command(BaseCommand):
    help = 'Запускает два бота на платформе Telegram'

    def handle(self, *args, **options):
        logger.info('Запуск основного и тестового бота')
        
        # Функция, которая непрерывно пытается запустить polling для основного бота
        def run_main_bot():
            from tgbot.handlers import commands, message_handler, utils  # Импортируем обработчики
            while True:
                try:
                    logger.info('Основной бот запущен')
                    dispatcher.bot.polling(none_stop=True, interval=0, timeout=20)
                except Exception as e:
                    logger.error(f"Ошибка в основном боте: {str(e)}\n{traceback.format_exc()}")
                    send_messege_to_admins(f"Ошибка в основном боте: {str(e)}\n{traceback.format_exc()}\n\nБот перезапущен")
                    dispatcher.bot.stop_polling()
                    # Подождать пару секунд перед перезапуском
                    time.sleep(1)
                    logger.info("Перезапуск основного бота...")

        def run_test_bot():
            if dispatcher.test_bot is None:
                logger.warning("Тестовый бот не инициализирован. Поток run_test_bot завершён.")
                return

            while True:
                try:
                    if Configuration.get_solo().test_mode:
                        logger.info('Тестовый бот запущен')

                        @dispatcher.test_bot.message_handler(func=lambda message: True)
                        def handle_all_messages(message):
                            dispatcher.test_bot.reply_to(
                                message,
                                "⚠️ *Технические работы* ⚠️\n\nВсе VPN конфигурации работают, но сейчас бот может не работать, или работать некорректно",
                                parse_mode="Markdown"
                            )

                        dispatcher.test_bot.polling(none_stop=True, interval=0, timeout=20)

                except Exception as e:
                    logger.error(f"Ошибка в тестовом боте: {str(e)}\n{traceback.format_exc()}")
                    dispatcher.test_bot.stop_polling()
                    time.sleep(5)
                    logger.info("Перезапуск тестового бота...")


        # Запускаем оба бота в отдельных потоках
        thread_main_bot = threading.Thread(target=run_main_bot, daemon=True)
        thread_test_bot = threading.Thread(target=run_test_bot, daemon=True)

        thread_main_bot.start()
        thread_test_bot.start()

        # Бесконечно ждём завершения работы потоков
        thread_main_bot.join()
        thread_test_bot.join()
