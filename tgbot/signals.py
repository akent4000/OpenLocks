import os
from decimal import Decimal

from django.db.models.signals import *
from django.db import transaction
from django.dispatch import receiver

from tgbot.models import *
from tgbot.managers.ssh_manager import SSHAccessManager, sync_keys
import threading

from pathlib import Path
from loguru import logger

# Убедимся, что папка logs существует
Path("logs").mkdir(parents=True, exist_ok=True)

# Лог-файл будет называться так же, как модуль, например user_helper.py → logs/user_helper.log
log_filename = Path("logs") / f"{Path(__file__).stem}.log"
logger.add(str(log_filename), rotation="10 MB", level="INFO")

@receiver(pre_save, sender=Server)
def server_pre_save(sender, instance, **kwargs):
    if instance.pk:
        instance._old_instance = sender.objects.get(pk=instance.pk)

@receiver(post_save, sender=Server)
def server_post_save(sender, instance, created, **kwargs):
    # Determine changed fields
    changed_fields = []
    if hasattr(instance, "_old_instance"):
        old_instance = instance._old_instance
        for field in instance._meta.fields:
            field_name = field.name
            old_value = getattr(old_instance, field_name)
            new_value = getattr(instance, field_name)
            if old_value != new_value:
                changed_fields.append(field_name)
    else:
        changed_fields = [field.name for field in instance._meta.fields]

    # If the 'user' field changed, synchronize SSH keys
    if 'user' in changed_fields:
        if created:
            timer = threading.Timer(30, sync_keys)
            timer.start()
        else:
            manager = SSHAccessManager()
            current_keys = set(manager.get_ssh_keys(instance._old_instance.user))
            for key in current_keys:
                manager.remove_ssh_key(instance._old_instance.user, key)
            sync_keys()

    # For SSH authentication settings, check if any relevant field changed
    auth_fields = ['password_auth', 'pubkey_auth', 'permit_root_login', 'permit_empty_passwords']
    if created or any(field in changed_fields for field in auth_fields):
        password_auth = instance.password_auth
        pubkey_auth = instance.pubkey_auth
        permit_root_login = instance.permit_root_login
        permit_empty_passwords = instance.permit_empty_passwords
        new_password_for_user = None  # Not stored in model; update only if provided elsewhere
        
        # Choose appropriate manager: SSHAccessManager for main server, RemoteServerManager otherwise
        manager = SSHAccessManager()
        
        # If the server is newly created, run the update after 30 seconds, else run it immediately.
        if created:
            timer = threading.Timer(30, lambda: manager.set_auth_methods(
                password_auth, pubkey_auth, permit_root_login, permit_empty_passwords, new_password_for_user))
            timer.start()
        else:
            manager.set_auth_methods(
                password_auth, pubkey_auth, permit_root_login, permit_empty_passwords, new_password_for_user)
            

@receiver(pre_delete, sender=Task)
def cleanup_task_sent_messages(sender, instance, **kwargs):
    """
    Перед удалением Task чистим все связанные SentMessage.
    """
    msg_ids = list(instance.sent_messages.values_list('id', flat=True))
    if msg_ids:
        SentMessage.objects.filter(id__in=msg_ids).delete()

@receiver(pre_delete, sender=Files)
def cleanup_files_sent_messages(sender, instance, **kwargs):
    """
    Перед удалением Files чистим все связанные SentMessage.
    """
    msg_ids = list(instance.sent_messages.values_list('id', flat=True))
    if msg_ids:
        SentMessage.objects.filter(id__in=msg_ids).delete()

@receiver(pre_delete, sender=Response)
def cleanup_response_sent_messages(sender, instance, **kwargs):
    """
    Перед удалением Response чистим все связанные SentMessage.
    """
    msg_ids = list(instance.sent_messages.values_list('id', flat=True))
    if msg_ids:
        SentMessage.objects.filter(id__in=msg_ids).delete()

@receiver(pre_delete, sender=TelegramUser)
def cleanup_user_tasks(sender, instance: TelegramUser, **kwargs):
    tasks = Task.objects.filter(creator=instance)
    count = tasks.count()
    for task in tasks:
        try:
            from tgbot.handlers.utils import delete_all_task_related
            delete_all_task_related(task)
            task.delete()
            logger.info(f"cleanup_user_tasks: удалена задача {task.id} пользователя {instance.chat_id}")
        except Exception as e:
            logger.error(f"cleanup_user_tasks: не удалось удалить задачу {task.id}: {e}")
    logger.info(f"cleanup_user_tasks: всего удалено {count} задач для пользователя {instance.chat_id}")

@receiver(pre_save, sender=TelegramUser)
def telegramuser_pre_save(sender, instance: TelegramUser, **kwargs):
    if instance.pk:
        try:
            instance._old_instance = sender.objects.get(pk=instance.pk)
        except sender.DoesNotExist:
            instance._old_instance = None

@receiver(post_save, sender=TelegramUser)
def delete_tasks_on_block(sender, instance: TelegramUser, created, **kwargs):
    if created:
        return

    old = getattr(instance, "_old_instance", None)
    # если флаг blocked поднимается с False на True
    if old and not old.blocked and instance.blocked:
        tasks = Task.objects.filter(creator=instance)
        count = tasks.count()
        for task in tasks:
            try:
                from tgbot.handlers.utils import delete_all_task_related
                delete_all_task_related(task)
                task.delete()
                logger.info(f"delete_tasks_on_block: удалена задача {task.id} пользователя {instance.chat_id}")
            except Exception as e:
                logger.error(f"delete_tasks_on_block: не удалось удалить задачу {task.id}: {e}")
        logger.info(f"delete_tasks_on_block: всего удалено {count} задач для заблокированного пользователя {instance.chat_id}")

@receiver(pre_delete, sender=Task)
def cleanup_task(sender, instance: Task, **kwargs):
    from tgbot.handlers.utils import delete_all_task_related
    delete_all_task_related(instance)

@receiver(pre_save, sender=Configuration)
def configuration_pre_save(sender, instance, **kwargs):
    """
    Перед сохранением сохраняем старое значение test_mode
    в instance._old_test_mode, чтобы потом понять, поменялось ли оно.
    """
    if not instance.pk:
        # ещё нет записи в БД — это первая сохранёнка
        instance._old_test_mode = None
    else:
        try:
            old = Configuration.objects.get(pk=instance.pk)
            instance._old_test_mode = old.test_mode
        except Configuration.DoesNotExist:
            instance._old_test_mode = None

def _restart_service():
    # выполняем systemctl restart bot
    try:
        subprocess.run(
            ['sudo', 'systemctl', 'restart', 'bot'],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except Exception as e:
        # здесь можно залогировать неудачу, если нужно
        logger.error("Failed to restart service 'bot':", e)

@receiver(post_save, sender=Configuration)
def configuration_post_save(sender, instance, created, **kwargs):
    old = getattr(instance, '_old_test_mode', None)
    new = instance.test_mode

    # если тестовый режим не менялся — выходим
    if not (created or (old is not None and old != new)):
        return

    # откладываем рестарт до конца транзакции и отдачи ответа
    def _deferred():
        # запускаем в отдельном потоке, чтобы не блокировать процесс Django
        threading.Thread(target=_restart_service, daemon=True).start()

    transaction.on_commit(_deferred)

@receiver(post_save, sender=TelegramBotToken)
def tgbot_token_post_save(sender, instance, created, **kwargs):
    def _deferred():
        # запускаем в отдельном потоке, чтобы не блокировать процесс Django
        threading.Thread(target=_restart_service, daemon=True).start()

    transaction.on_commit(_deferred)