import base64
import io
import os
import secrets
import string
import zipfile

import telebot
from django import forms
from django.contrib import admin, messages
from django.db.models import Count, IntegerField, Q, Value
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.http import urlencode

from rangefilter.filters import DateRangeFilter, NumericRangeFilter

from solo.admin import SingletonModelAdmin

from tgbot.managers.ssh_manager import SSHAccessManager, sync_keys
from tgbot.models import (
    Configuration,
    SSHKey,
    TelegramBotToken,
    Server,
    TelegramUser,
    Tag,
    PaymentTypeModel,
    Task,
    Files,
    Response,
    SentMessage,
)
from tgbot.forms import SSHKeyAdminForm, SSHKeyChangeForm

admin.site.site_header = "Администрирование Open Locks"
admin.site.site_title = "Администрирование Open Locks"
admin.site.index_title = "Администрирование Open Locks"

##############################
# TelegramBotToken Admin
##############################
@admin.register(TelegramBotToken)
class TelegramBotTokenAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'test_bot', 'token', 'bot_link')
    search_fields = ('id', 'token', 'name')
    readonly_fields = ('bot_link', )

    def bot_link(self, obj: TelegramBotToken):
        if not obj.token:
            return "Bot token is not defined"
        try:
            bot_instance = telebot.TeleBot(obj.token)
            bot_info = bot_instance.get_me()
            return format_html(
                '<a href="https://t.me/{}" target="_blank">https://t.me/{}</a>',
                bot_info.username,
                bot_info.username,
            )
        except Exception as e:
            return f"Ошибка: {e}"
    bot_link.short_description = "Ссылка на бота"

##############################
# Server Admin (Singleton)
##############################
class ServerAdminForm(forms.ModelForm):
    PERMIT_ROOT_LOGIN_CHOICES = [
        ('yes', 'Полный доступ'),
        ('no', 'Доступ запрещён'),
        ('prohibit-password', 'Только без пароля (например с SSH ключом)'),
        ('forced-commands-only', 'Только принудительные команды'),
    ]
    permit_root_login = forms.ChoiceField(
        choices=PERMIT_ROOT_LOGIN_CHOICES,
        initial='prohibit-password',
        label="root логин"
    )
    
    class Meta:
        model = Server
        fields = '__all__'

@admin.register(Server)
class ServerAdmin(SingletonModelAdmin):
    form = ServerAdminForm
    change_form_template = 'admin/server_change_form.html'
    actions = ['sync_ssh_keys']
    fieldsets = (
        (None, {'fields': ('ip',)}),
        ('Настройки сервера', {'fields': ('user',)}),
        ('SSH аутентификация', {'fields': ('password_auth', 'pubkey_auth', 'permit_empty_passwords', 'permit_root_login')}),
    )

    @admin.action(description="Синхронизировать SSH ключи")
    def sync_ssh_keys(self, request, queryset=None):
        server = Server.get_solo()
        sync_keys(server=server)
        self.message_user(request, f"SSH ключи синхронизированы для сервера {server.ip}.", level=messages.SUCCESS)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'sync-ssh-keys/',
                self.admin_site.admin_view(self.sync_ssh_keys),
                name='server_sync_ssh_keys'
            ),
            path(
                'reset-password/',
                self.admin_site.admin_view(self.reset_password),
                name='server_reset_password'
            ),
        ]
        return custom_urls + urls

    def reset_password(self, request):
        server = Server.get_solo()
        alphabet = string.ascii_letters + string.digits
        new_password = ''.join(secrets.choice(alphabet) for _ in range(12))
        new_password_for_user = (server.user, new_password)
        manager = SSHAccessManager()
        manager.set_auth_methods(
            server.password_auth,
            server.pubkey_auth,
            server.permit_root_login,
            server.permit_empty_passwords,
            new_password_for_user
        )
        self.message_user(request, f"Пароль для пользователя {server.user} сброшен. Новый пароль: {new_password}", level=messages.SUCCESS)
        return HttpResponseRedirect(request.path)

##############################
# SSHKey Admin
##############################
@admin.register(SSHKey)
class SSHKeyAdmin(admin.ModelAdmin):
    list_display = ("key_name", "public_key", "created_at")
    readonly_fields = ("public_key", "created_at")
    form = SSHKeyAdminForm

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'sync-keys/',
                self.admin_site.admin_view(self.sync_keys),
                name="%s_%s_sync_keys" % (self.model._meta.app_label, self.model._meta.model_name)
            ),
            path(
                'delete-key/<int:pk>/',
                self.admin_site.admin_view(self.delete_key),
                name="sshkey_delete_key"
            ),
        ]
        return custom_urls + urls

    def sync_keys(self, request):
        sync_keys()
        self.message_user(request, "SSH ключи успешно синхронизированы.", messages.SUCCESS)
        return redirect("..")

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        sync_url = reverse("admin:%s_%s_sync_keys" % (self.model._meta.app_label, self.model._meta.model_name))
        extra_context["sync_keys_url"] = sync_url
        return super().changelist_view(request, extra_context=extra_context)

    def delete_key(self, request, pk):
        obj = self.get_object(request, pk)
        if obj:
            obj.delete()
            self.message_user(request, "SSH ключ удалён.", level=messages.SUCCESS)
        else:
            self.message_user(request, "SSH ключ не найден.", level=messages.ERROR)
        return redirect("..")

    def save_model(self, request, obj, form, change):
        if not change:
            manager = SSHAccessManager()
            comment = obj.key_name
            passphrase = form.cleaned_data.get("passphrase", "")
            key_type = form.cleaned_data.get("key_type", "rsa")
            bits = form.cleaned_data.get("bits") or 2048

            result = manager.generate_ssh_key(comment=comment, passphrase=passphrase, key_type=key_type, bits=bits)
            if result is None:
                messages.error(request, "Ошибка генерации SSH ключа.")
                return
            obj.public_key = result["public_key"]
            super().save_model(request, obj, form, change)
            obj._private_key = result["private_key"]
        else:
            super().save_model(request, obj, form, change)

    def response_add(self, request, obj, post_url_continue=None):
        if hasattr(obj, "_private_key"):
            pem_filename = f"{obj.key_name}_private_key.pem"
            zip_filename = f"{obj.key_name}_private_key.zip"
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                zip_info = zipfile.ZipInfo(pem_filename)
                zip_info.external_attr = (0o600 << 16)
                zip_file.writestr(zip_info, obj._private_key)
            zip_buffer.seek(0)
            zip_content = zip_buffer.getvalue()
            zip_content_b64 = base64.b64encode(zip_content).decode('utf-8')
            
            changelist_url = reverse("admin:%s_%s_changelist" % (obj._meta.app_label, obj._meta.model_name))
            
            html = f"""
            <html>
            <head>
                <script>
                function downloadAndRedirect() {{
                    var a = document.createElement('a');
                    a.href = "data:application/zip;base64,{zip_content_b64}";
                    a.download = "{zip_filename}";
                    document.body.appendChild(a);
                    a.click();
                    setTimeout(function() {{
                        window.location.href = "{changelist_url}";
                    }}, 1000);
                }}
                window.onload = downloadAndRedirect;
                </script>
            </head>
            <body>
                <p>SSH ключ успешно создан. Если скачивание не началось автоматически, <a href="#" onclick="downloadAndRedirect(); return false;">нажмите здесь</a>.</p>
            </body>
            </html>
            """
            del obj._private_key
            return HttpResponse(html)
        return super().response_add(request, obj, post_url_continue)

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ("key_name", "public_key", "created_at")
        return self.readonly_fields

    def get_form(self, request, obj=None, **kwargs):
        if obj:
            kwargs["form"] = SSHKeyChangeForm
        else:
            kwargs["form"] = SSHKeyAdminForm
        return super().get_form(request, obj, **kwargs)

##############################
# Configuration Admin (Singleton)
##############################
@admin.register(Configuration)
class ConfigurationAdmin(SingletonModelAdmin):
    fieldsets = (
        (None, {'fields': ('test_mode', 'auto_request_permission')}),
    )

##############################
# TelegramUser Admin
##############################
@admin.register(TelegramUser)
class TelegramUserAdmin(admin.ModelAdmin):
    list_display = (
        'chat_id', 'first_name', 'last_name', 'username', 
        'can_publish_tasks', 'created_at', 'get_subscribed_tags'
    )
    search_fields = ('chat_id', 'first_name', 'last_name', 'username')
    list_filter = ('can_publish_tasks', 'created_at', 'subscribed_tags')

    def get_subscribed_tags(self, obj):
        return ", ".join(tag.name for tag in obj.subscribed_tags.all())
    get_subscribed_tags.short_description = "Подписка на теги"

##############################
# Tag Admin
##############################
@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)

##############################
# PaymentTypeModel Admin
##############################
@admin.register(PaymentTypeModel)
class PaymentTypeModelAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'description')
    search_fields = ('name',)

##############################
# Files Inline for Task
##############################
class FilesInline(admin.TabularInline):
    model = Files
    extra = 0
    readonly_fields = ('file_id', 'file_type', 'get_sent_messages', 'created_at')
    can_delete = True

    def get_sent_messages(self, obj):
        return ", ".join(f"{sm.message_id} ({sm.telegram_user})" for sm in obj.sent_messages.all())
    get_sent_messages.short_description = "Отправленные сообщения"

##############################
# Response Inline for Task
##############################
class ResponseInline(admin.TabularInline):
    model = Response
    extra = 0
    readonly_fields = ('telegram_user', 'payment_type', 'created_at')

##############################
# Task Admin
##############################
@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'tag', 'creator', 'stage', 'created_at', 'get_sent_messages')
    list_filter = ('stage', 'tag', 'payment_type')
    search_fields = ('title', 'description')
    readonly_fields = ('task_text', 'get_sent_messages')
    inlines = [FilesInline, ResponseInline]

    def get_sent_messages(self, obj):
        return ", ".join(f"{sm.message_id} ({sm.telegram_user})" for sm in obj.sent_messages.all())
    get_sent_messages.short_description = "Отправленные сообщения"
