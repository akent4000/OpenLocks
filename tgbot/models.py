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

    @staticmethod
    def is_test_mode():
        last_obj = Configuration.objects.last()
        if last_obj is None:
            return False
        return last_obj.test_mode

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

