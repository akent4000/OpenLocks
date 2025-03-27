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

from tgbot.managers.ssh_manager import SSHAccessManager, sync_keys
from tgbot.models import (
    Configuration,
    SSHKey,
    TelegramBotToken,
    Server,
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
            return format_html('<a href="https://t.me/{}" target="_blank">https://t.me/{}</a>', bot_info.username, bot_info.username)
        except Exception as e:
            return f"Ошибка: {e}"
    bot_link.short_description = "Ссылка на бота"

##############################
# Server Admin
##############################
# Custom ModelForm with a dropdown for permit_root_login.
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

##############################
# Server Admin формы
##############################
@admin.register(Server)
class ServerAdmin(admin.ModelAdmin):
    form = ServerAdminForm
    list_display = (
        'id', 'ip',
    )
    actions = ['sync_ssh_keys']

    fieldsets = (
        (None, {
            'fields': ('ip',)
        }),
        ('Настройки сервера', {
            'fields': ('user')
        }),
        ('SSH аутентификация', {
            'fields': ('password_auth', 'pubkey_auth', 'permit_empty_passwords', 'permit_root_login')
        }),
    )

    @admin.action(description="Синхронизировать SSH ключи выбранных серверов")
    def sync_ssh_keys(self, request, queryset):
        for server in queryset:
            sync_keys(server=server)
            self.message_user(request, f"SSH ключи синхронизированы для сервера {server.ip}.", level=messages.SUCCESS)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:object_id>/sync_ssh_keys/',
                self.admin_site.admin_view(self.sync_ssh_keys_change),
                name='nameserver_sync_ssh_keys'
            ),
            path(
                '<int:object_id>/reset_password/',
                self.admin_site.admin_view(self.reset_password_change),
                name='nameserver_reset_password'
            ),
        ]
        return custom_urls + urls
    
    def sync_ssh_keys_change(self, request, object_id):
        server = self.get_queryset(request).filter(pk=object_id).first()
        if server:
            sync_keys(server=server)
            self.message_user(request, f"SSH ключи синхронизированы для сервера {server.ip}.", level=messages.SUCCESS)
        else:
            self.message_user(request, "Сервер не найден.", level=messages.ERROR)
        return HttpResponseRedirect(reverse("admin:tgbot_nameserver_change", args=[object_id]))
    
    def reset_password_change(self, request, object_id):
        server = self.get_queryset(request).filter(pk=object_id).first()
        if not server:
            self.message_user(request, "Сервер не найден.", level=messages.ERROR)
            return HttpResponseRedirect(reverse("admin:tgbot_nameserver_change", args=[object_id]))
        
        # Generate a new random password (12 characters)
        alphabet = string.ascii_letters + string.digits
        new_password = ''.join(secrets.choice(alphabet) for _ in range(12))
        new_password_for_user = (server.user, new_password)
        
        # Retrieve current authentication settings from the instance
        password_auth = server.password_auth
        pubkey_auth = server.pubkey_auth
        permit_root_login = server.permit_root_login
        permit_empty_passwords = server.permit_empty_passwords

        # Choose manager based on whether server is main
        manager = SSHAccessManager()
                
        # Call the unified API method to update authentication settings with new password
        manager.set_auth_methods(
            password_auth,
            pubkey_auth,
            permit_root_login,
            permit_empty_passwords,
            new_password_for_user
        )
        
        # Inform user with new password details
        self.message_user(request, f"Пароль для пользователя {server.user} сброшен. Новый пароль: {new_password}", level=messages.SUCCESS)
        return HttpResponseRedirect(reverse("admin:tgbot_nameserver_change", args=[object_id]))
    
    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['download_ssl_files_url'] = reverse("admin:nameserver_download_ssl_files", args=[object_id])
        extra_context['download_configurations_url'] = reverse("admin:nameserver_download_configurations", args=[object_id])
        extra_context['sync_ssh_keys_url'] = reverse("admin:nameserver_sync_ssh_keys", args=[object_id])
        extra_context['reset_password_url'] = reverse("admin:nameserver_reset_password", args=[object_id])
        return super().change_view(request, object_id, form_url, extra_context)
    

##############################
# SSHKey Admin формы
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
        if extra_context is None:
            extra_context = {}
        # Формируем URL для кнопки синхронизации
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

            result = manager.generate_ssh_key(
                comment=comment, passphrase=passphrase, key_type=key_type, bits=bits
            )
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
            # Создаем zip-архив в памяти
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                # Создаем ZipInfo для файла и устанавливаем права доступа 600 (-rw-------)
                zip_info = zipfile.ZipInfo(pem_filename)
                zip_info.external_attr = (0o600 << 16)
                zip_file.writestr(zip_info, obj._private_key)
            zip_buffer.seek(0)
            # Получаем содержимое архива и кодируем его в base64
            zip_content = zip_buffer.getvalue()
            zip_content_b64 = base64.b64encode(zip_content).decode('utf-8')
            
            # Получаем URL для списка объектов (changelist)
            changelist_url = reverse("admin:%s_%s_changelist" % (obj._meta.app_label, obj._meta.model_name))
            
            # Формируем HTML-страницу с JavaScript, который скачивает файл и через 1 сек. редиректит
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
            # Удаляем временное поле с приватным ключом
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