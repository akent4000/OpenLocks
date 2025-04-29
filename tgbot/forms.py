from django import forms
from tgbot.models import SSHKey, TelegramUser

class SSHKeyAdminForm(forms.ModelForm):
    # Дополнительные поля используются только при создании ключа
    passphrase = forms.CharField(
        required=False, label="Пароль", widget=forms.PasswordInput(render_value=True)
    )
    key_type = forms.ChoiceField(
        choices=[("rsa", "RSA"), ("ed25519", "Ed25519")],
        initial="rsa",
        label="Тип ключа"
    )
    bits = forms.IntegerField(initial=2048, label="Размер ключа (для RSA)", required=False)

    class Meta:
        model = SSHKey
        # Используем key_name как основное поле, оно также служит комментарием
        fields = ("key_name", "passphrase", "key_type", "bits")

# Форма для редактирования (change view), которая показывает только поле key_name
class SSHKeyChangeForm(forms.ModelForm):
    class Meta:
        model = SSHKey
        fields = ("key_name",)

class SendMessageForm(forms.Form):
    message = forms.CharField(
        label="Текст сообщения",
        widget=forms.Textarea(attrs={"rows": 4, "cols": 40}),
        required=True
    )
    sender = forms.ModelChoiceField(
        label="Отправить от имени",
        queryset=TelegramUser.objects.filter(is_admin=True),
        widget=forms.Select,
        required=True
    )