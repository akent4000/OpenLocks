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

from loguru import logger
logger.add("logs/models.log", rotation="10 MB", level="INFO")

class Configuration(models.Model):
    """Модель для хранения текущей конфигурации"""
    
    test_mode = models.BooleanField(default=False, verbose_name='Включить тестовый режим')
    auto_request_permission = models.BooleanField(
        default=False,
        verbose_name='Автоматически разрешать пользователям давать и принимать заявки'
    )

    @staticmethod
    def get_is_test_mode():
        last_obj = Configuration.objects.last()
        if last_obj is None:
            return False
        return last_obj.test_mode
    
    @staticmethod
    def get_auto_request_permission():
        last_obj = Configuration.objects.last()
        if last_obj is None:
            return False
        return last_obj.auto_request_permission

class TelegramBotToken(models.Model):
    """Модель для хранения токена бота"""
    token = models.CharField(max_length=255, verbose_name='Токен бота')
    name = models.CharField(max_length=255, verbose_name='Название бота', default='Bot')
    test_bot = models.BooleanField(default=False, verbose_name='Бот для тестирования')

    def __str__(self):
        return self.name
    
    @staticmethod
    def get_main_bot_token():
        last_obj: TelegramBotToken = TelegramBotToken.objects.filter(test_bot=False).last()
        if last_obj is None:
            return ""
        return last_obj.token

    @staticmethod
    def get_test_bot_token():
        last_obj: TelegramBotToken = TelegramBotToken.objects.filter(test_bot=True).last()
        if last_obj is None:
            return ""
        return last_obj.token

    class Meta:
        verbose_name = 'Токен бота'
        verbose_name_plural = 'Токены ботов'

class Server(models.Model):
    """Модель для хранения серверов."""
    ip = models.CharField(max_length=255, verbose_name='IP сервера')
    password_auth = models.BooleanField(default=False, verbose_name='Разрешить доступ по паролю')
    pubkey_auth = models.BooleanField(default=True, verbose_name='Разрешить доступ по SSH ключу')
    permit_root_login = models.CharField(
        max_length=50,
        default='prohibit-password',
        verbose_name='root логин',
        help_text='Например: yes, no, prohibit-password, forced-commands-only'
    )
    permit_empty_passwords = models.BooleanField(
        default=False,
        verbose_name='Разрешить пустые пароли'
    )
    user = models.CharField(default="root", max_length=255, verbose_name='Пользователь SSH')

    class Meta:
        verbose_name = 'DNS сервер'
        verbose_name_plural = 'DNS сервера'

    @staticmethod
    def get_server():
        return Server.objects.last()

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
    first_name = models.CharField(max_length=255, verbose_name='Имя')
    last_name = models.CharField(max_length=255, blank=True, null=True, verbose_name='Фамилия')
    username = models.CharField(max_length=255, blank=True, null=True, verbose_name='Username')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата регистрации')
    can_publish_tasks = models.BooleanField(default=False, verbose_name='Доступ к публикации заданий')

    def __str__(self):
        return f"{self.first_name} {self.last_name or ''} (@{self.username})"

    class Meta:
        verbose_name = 'Пользователь Telegram'
        verbose_name_plural = 'Пользователи Telegram'


class Tag(models.Model):
    """Модель тега"""
    name = models.CharField(max_length=100, unique=True, verbose_name='Имя тега')

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Тег'
        verbose_name_plural = 'Теги'


class PaymentTypeModel(models.Model):
    """Модель типа оплаты"""
    name = models.CharField(max_length=50, unique=True, verbose_name='Тип оплаты')  # Например, "50/50", "70/30"
    description = models.TextField(blank=True, null=True, verbose_name='Описание')

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Тип оплаты'
        verbose_name_plural = 'Типы оплаты'


class Task(models.Model):
    """Модель задания"""
    class Stage(models.TextChoices):
        PENDING = 'pending', 'В ожидании'
        CREATED = 'created', 'Создано'
        EXECUTOR_CHOSEN = 'executor_chosen', 'Выбран исполнитель'
        CLOSED = 'closed', 'Задание закрыто'

    tag = models.ForeignKey(
        Tag, 
        on_delete=models.CASCADE,  
        blank=True,
        null=True,
        verbose_name='Тег',
    )
    title = models.CharField(max_length=255, verbose_name='Название')
    description = models.TextField(verbose_name='Текст задания')
    payment_type = models.ForeignKey(
        PaymentTypeModel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Тип оплаты'
    )
    creator = models.ForeignKey(
        TelegramUser,
        on_delete=models.CASCADE,
        related_name='created_tasks',
        verbose_name='Кто дал задание'
    )
    selected_executor = models.ForeignKey(
        TelegramUser,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='assigned_tasks',
        verbose_name='Выбранный исполнитель'
    )
    stage = models.CharField(
        max_length=20,
        choices=Stage.choices,
        default=Stage.PENDING,
        verbose_name='Этап задания'
    )
    file_ids = models.JSONField(
        blank=True,
        null=True,
        default=list,
        verbose_name='Список File IDs'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = 'Задание'
        verbose_name_plural = 'Задания'

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
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания отклика')

    def __str__(self):
        return f"Отклик пользователя {self.telegram_user} на задание {self.task}"

    class Meta:
        verbose_name = 'Отклик'
        verbose_name_plural = 'Отклики'
