import os
from decimal import Decimal

from django.db.models.signals import *
from django.dispatch import receiver

from tgbot.models import *
from tgbot.managers.ssh_manager import SSHAccessManager, sync_keys
import threading

from loguru import logger
logger.add("logs/signals.log", rotation="10 MB", level="INFO")

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
            

@receiver(post_save, sender=TelegramUser)
def subscribe_user_to_all_tags(sender, instance, created, **kwargs):
    if created:
        instance.subscribed_tags.set(Tag.objects.all())


@receiver(post_save, sender=Tag)
def subscribe_all_users_to_new_tag(sender, instance, created, **kwargs):
    """
    При создании нового тега подписывает всех существующих пользователей на него.
    """
    if not created:
        return

    users = TelegramUser.objects.all()
    for user in users:
        user.subscribed_tags.add(instance)
    logger.info(f"Подписано {users.count()} пользователей на новый тег «{instance.name}»")

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