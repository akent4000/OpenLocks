#!/usr/bin/python3

import threading
import time
from django.core.management.base import BaseCommand
from loguru import logger
from tgbot import dispatcher
from tgbot.models import Configuration
import traceback
from tgbot.logics.info_for_admins import send_messege_to_admins

logger.add("logs/startbot.log", rotation="10 MB", level="INFO")

class Command(BaseCommand):
    help = 'Запускает два бота на платформе Telegram'

    def handle(self, *args, **options):
        logger.info('Запуск основного и тестового бота')
        
        # Функция, которая непрерывно пытается запустить polling для основного бота
        def run_main_bot():
            from tgbot.handlers import commands, pay, utils  # Импортируем обработчики
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

        # Функция, которая непрерывно пытается запустить polling для тестового бота
        def run_test_bot():
            while True:
                try:
                    if Configuration.is_test_mode():
                        logger.info('Тестовый бот запущен')
                        @dispatcher.test_bot.message_handler(func=lambda message: True)
                        def handle_all_messages(message):
                            # Отправка сообщения о технических работах
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
