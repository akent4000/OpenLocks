import json
import os
import uuid
import re
from decimal import Decimal
from django.db import models
from django.db.models import F, QuerySet
from telebot import TeleBot
from django.utils import timezone
from django.core.validators import RegexValidator
import subprocess
from solo.models import SingletonModel
from tgbot.logics.constants import Constants, Messages
from tgbot.logics.random_numbers import random_number_list

from pathlib import Path
from loguru import logger

from tgbot.logics.text_helper import Partial

# Убедимся, что папка logs существует
Path("logs").mkdir(parents=True, exist_ok=True)

# Лог-файл будет называться так же, как модуль, например user_helper.py → logs/user_helper.log
log_filename = Path("logs") / f"{Path(__file__).stem}.log"
logger.add(str(log_filename), rotation="10 MB", level="INFO")

class Configuration(SingletonModel):
    """
    Сингл модель для хранения текущей конфигурации.
    Гарантирует, что в базе будет ровно один объект.
    """
    test_mode = models.BooleanField(
        default=False,
        verbose_name='Включить тестовый режим'
    )
    auto_request_permission = models.BooleanField(
        default=False,
        verbose_name='Автоматически разрешать пользователям давать и принимать заявки'
    )

    class Meta:
        verbose_name = 'Конфигурация'
        verbose_name_plural = 'Конфигурация'

    def __str__(self):
        return "Конфигурация бота"


class TelegramBotToken(models.Model):
    """Модель для хранения токена бота"""
    token = models.CharField(max_length=255, verbose_name='Токен бота')
    name = models.CharField(max_length=255, verbose_name='Название бота', default='Bot')
    test_bot = models.BooleanField(default=False, verbose_name='Бот для тестирования')

    def __str__(self):
        return self.name
    
    @staticmethod
    def get_main_bot_token():
        last_obj = TelegramBotToken.objects.filter(test_bot=False).last()
        return last_obj.token if last_obj else ""
    
    @staticmethod
    def get_test_bot_token():
        last_obj = TelegramBotToken.objects.filter(test_bot=True).last()
        return last_obj.token if last_obj else ""

    class Meta:
        verbose_name = 'Токен бота'
        verbose_name_plural = 'Токены ботов'


class Server(SingletonModel):
    """
    Сингл модель для хранения параметров сервера.
    В базе всегда будет единственный экземпляр.
    """
    ip = models.CharField(max_length=255, verbose_name='IP сервера')
    password_auth = models.BooleanField(default=False, verbose_name='Разрешить доступ по паролю')
    pubkey_auth = models.BooleanField(default=True, verbose_name='Разрешить доступ по SSH ключу')
    permit_root_login = models.CharField(
        max_length=50,
        default='prohibit-password',
        verbose_name='root логин',
        help_text='Например: yes, no, prohibit-password, forced-commands-only'
    )
    permit_empty_passwords = models.BooleanField(default=False, verbose_name='Разрешить пустые пароли')
    user = models.CharField(default="root", max_length=255, verbose_name='Пользователь SSH')

    class Meta:
        verbose_name = 'Сервер'
        verbose_name_plural = 'Сервер'

    def __str__(self):
        return f"Сервер ({self.ip})"


class SSHKey(models.Model):
    key_name = models.CharField(
        max_length=255,
        verbose_name="Название ключа",
        help_text="Уникальное имя для ключа"
    )
    public_key = models.TextField(
        verbose_name="Публичный ключ",
        help_text="Публичный SSH ключ в формате OpenSSH"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")

    def __str__(self):
        return self.key_name

    class Meta:
        verbose_name = 'SSH ключ'
        verbose_name_plural = 'SSH ключи'


class TelegramUser(models.Model):
    """Модель пользователя Telegram"""
    chat_id = models.BigIntegerField(unique=True, verbose_name='Chat ID')
    first_name = models.CharField(max_length=255, blank=True, null=True, verbose_name='Имя')
    last_name = models.CharField(max_length=255, blank=True, null=True, verbose_name='Фамилия')
    username = models.CharField(max_length=255, blank=True, null=True, verbose_name='Username')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата регистрации')
    can_publish_tasks = models.BooleanField(default=False, verbose_name='Доступ к публикации заданий')
    blocked = models.BooleanField(default=False, verbose_name='Блокировка')
    is_group = models.BooleanField(default=False, verbose_name='Групповой чат')
    bot_was_blocked = models.BooleanField(default=False, verbose_name='Бот заблокирован')
    send_admin_notifications = models.BooleanField(default=False, verbose_name='Оповещения об ошибках')

    def __str__(self):
        return f"{self.first_name} {self.last_name or ''} (@{self.username})"

    @staticmethod
    def get_user_by_chat_id(chat_id: int):
        try:
            return TelegramUser.objects.get(chat_id=chat_id)
        except TelegramUser.DoesNotExist:
            return None

    class Meta:
        verbose_name = 'Пользователь Telegram'
        verbose_name_plural = 'Пользователи Telegram'

class PaymentTypeModel(models.Model):
    """Модель типа оплаты"""
    name = models.CharField(max_length=50, unique=True, verbose_name='Тип оплаты')  # Например, "50/50", "70/30"
    description = models.TextField(blank=True, null=True, verbose_name='Описание')

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Тип оплаты'
        verbose_name_plural = 'Типы оплаты'


class SentMessage(models.Model):
    message_id = models.IntegerField(verbose_name='ID сообщения')
    telegram_user = models.ForeignKey(
        'TelegramUser', on_delete=models.CASCADE, null=True, blank=True, verbose_name='Пользователь'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')

    def __str__(self):
        return f"{self.telegram_user} - {self.message_id}"

    class Meta:
        verbose_name = 'Отправленное сообщение'
        verbose_name_plural = 'Отправленные сообщения'

class Task(models.Model):
    """Модель задания"""
    class Stage(models.TextChoices):
        #PENDING_TAG = 'pending_tag', 'В ожидании выбора тэга'
        CREATED = 'created', 'Создано'
        CLOSED = 'closed', 'Задание закрыто'
    title = models.CharField(max_length=255, verbose_name='Название')
    description = models.TextField(verbose_name='Текст задания')
    creator = models.ForeignKey(
        TelegramUser,
        on_delete=models.CASCADE,
        related_name='created_tasks',
        verbose_name='Кто дал задание'
    )
    creator_message_id_to_reply = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='ID сообщения для ответа'
    )
    stage = models.CharField(
        max_length=20,
        choices=Stage.choices,
        default=Stage.CREATED,
        verbose_name='Этап задания'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    sent_messages = models.ManyToManyField(
        SentMessage,
        blank=True,
        related_name="tasks",
        verbose_name="Отправленные сообщения"
    )

    def __str__(self):
        return self.title
    
    @property
    def random_task_number(self):
        number = random_number_list.get(self.id)
        return f"{number:0{Constants.NUMBER_LENGTH}}"

    @property
    def dispather_task_text(self):
        from tgbot.logics.text_helper import get_mention
        text = Messages.DISPATHER_TASK_TEXT.format(random_task_number=self.random_task_number, description=self.description)

        if self.responses.all():
            text += Messages.RESPONSES

        for response in self.responses.all():
            actor = response.telegram_user
            mention = get_mention(actor)

            text += Messages.MASTER_WANT_TO_PICK_UP_TASK.format(mention=mention, payment_type=response.payment_type.name)
            
        return text
    
    @property
    def master_task_text_with_dispather_mention(self):
        from tgbot.logics.text_helper import get_mention
        actor = self.creator
        mention = get_mention(actor)
        text = Messages.MASTER_TASK_TEXT.format(random_task_number=self.random_task_number, mention=mention, description=self.description)

        if self.responses.all():
            text += Messages.RESPONSES

        for response in self.responses.all():
            actor = response.telegram_user
            mention = get_mention(actor)

            text += Messages.MASTER_WANT_TO_PICK_UP_TASK.format(mention=mention, payment_type=response.payment_type.name)
            
        return text
    

    class Meta:
        verbose_name = 'Задание'
        verbose_name_plural = 'Задания'


class Files(models.Model):
    """Модель для хранения файлов, прикреплённых к заданию."""
    FILE_TYPE_CHOICES = [
        ('photo', 'Фото'),
        ('video', 'Видео'),
        ('document', 'Документ'),
    ]
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='files', verbose_name='Задание')
    file_id = models.CharField(max_length=255, verbose_name='ID файла')
    file_type = models.CharField(max_length=50, choices=FILE_TYPE_CHOICES, verbose_name='Тип файла')
    sent_messages = models.ManyToManyField(
        SentMessage,
        blank=True,
        related_name="file_sent_messages",
        verbose_name="Отправленные сообщения"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')

    def __str__(self):
        return f"{self.get_file_type_display()} - {self.file_id}"

    class Meta:
        verbose_name = 'Файл'
        verbose_name_plural = 'Файлы'


class Response(models.Model):
    """
    Модель отклика на задание.
    Хранит в себе тип оплаты, пользователя и задание.
    """
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='responses',
        verbose_name='Задание'
    )
    telegram_user = models.ForeignKey(
        TelegramUser,
        on_delete=models.CASCADE,
        related_name='responses',
        verbose_name='Пользователь'
    )
    payment_type = models.ForeignKey(
        PaymentTypeModel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Тип оплаты'
    )
    sent_messages = models.ManyToManyField(
        SentMessage,
        blank=True,
        related_name="response_sent_messages",
        verbose_name="Отправленные сообщения"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания отклика')

    def __str__(self):
        return f"Отклик пользователя {self.telegram_user} на задание {self.task}"

    class Meta:
        verbose_name = 'Отклик'
        verbose_name_plural = 'Отклики'
