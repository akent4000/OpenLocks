import os
import subprocess
import pwd
from typing import Optional, Tuple
from cryptography.hazmat.primitives.asymmetric import rsa, ed25519
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
import glob
import time

from pathlib import Path
from loguru import logger

# Убедимся, что папка logs существует
Path("logs").mkdir(parents=True, exist_ok=True)

# Лог-файл будет называться так же, как модуль, например user_helper.py → logs/user_helper.log
log_filename = Path("logs") / f"{Path(__file__).stem}.log"
logger.add(str(log_filename), rotation="10 MB", level="INFO")

class SSHAccessManager:
    def __init__(self, sshd_config_path='/etc/ssh/sshd_config'):
        self.sshd_config_path = sshd_config_path

    def _update_config_option(self, option, value):
        """
        Updates (or adds, if not found) an option in the SSH configuration file.
        It searches for the option in the main configuration file as well as in the included files
        specified by the Include directive.
        """
        found = False

        # Read the main configuration file
        try:
            with open(self.sshd_config_path, 'r') as f:
                main_lines = f.readlines()
        except Exception as e:
            logger.error(f"Error reading configuration file {self.sshd_config_path}: {e}")
            return

        new_main_lines = []
        for line in main_lines:
            if line.strip().startswith(option):
                new_main_lines.append(f"{option} {value}\n")
                found = True
            else:
                new_main_lines.append(line)

        # Search for Include directives and update the found files
        include_files = []
        for line in main_lines:
            stripped = line.strip()
            if stripped.startswith("Include"):
                parts = stripped.split()
                if len(parts) >= 2:
                    pattern = parts[1]
                    # Expand pattern, e.g., /etc/ssh/sshd_config.d/*.conf
                    include_files.extend(glob.glob(pattern))
        for inc_file in include_files:
            try:
                with open(inc_file, 'r') as f:
                    inc_lines = f.readlines()
            except Exception as e:
                logger.error(f"Error reading file {inc_file}: {e}")
                continue
            new_inc_lines = []
            updated = False
            for line in inc_lines:
                if line.strip().startswith(option):
                    new_inc_lines.append(f"{option} {value}\n")
                    found = True
                    updated = True
                else:
                    new_inc_lines.append(line)
            if updated:
                try:
                    with open(inc_file, 'w') as f:
                        f.writelines(new_inc_lines)
                    logger.info(f"Option {option} updated in {inc_file} with value: {value}")
                except Exception as e:
                    logger.error(f"Error writing file {inc_file}: {e}")

        # If the option was not found in either the main file or included files, add it to the end of the main file
        if not found:
            new_main_lines.append(f"\n{option} {value}\n")

        try:
            with open(self.sshd_config_path, 'w') as f:
                f.writelines(new_main_lines)
            logger.info(f"Option {option} set to: {value} in the main file {self.sshd_config_path}")
        except Exception as e:
            logger.error(f"Error writing configuration file {self.sshd_config_path}: {e}")

    def set_auth_methods(self,
                     password_auth: bool,
                     pubkey_auth: bool,
                     permit_root_login: str,
                     permit_empty_passwords: bool,
                     new_password_for_user: Optional[Tuple[str, str]] = None) -> dict:
        """
        Sets all SSH authentication settings based on the given parameters.

        :param password_auth: Enable or disable password authentication.
        :param pubkey_auth: Enable or disable SSH key authentication.
        :param permit_root_login: Value for the PermitRootLogin option (e.g., 'yes', 'no', 'prohibit-password', 'forced-commands-only').
        :param permit_empty_passwords: Enable or disable empty passwords.
        :param new_password_for_user: Optional tuple (username, new_password) to update the user's password.
        :return: A dictionary with the status of each operation.
        """
        results = {}
        try:
            self.set_password_auth(password_auth)
            results["password_auth"] = "updated"
        except Exception as e:
            results["password_auth"] = f"error: {e}"
        
        try:
            self.set_pubkey_auth(pubkey_auth)
            results["pubkey_auth"] = "updated"
        except Exception as e:
            results["pubkey_auth"] = f"error: {e}"
        
        try:
            self.set_permit_root_login(permit_root_login)
            results["permit_root_login"] = "updated"
        except Exception as e:
            results["permit_root_login"] = f"error: {e}"
        
        try:
            self.set_permit_empty_passwords(permit_empty_passwords)
            results["permit_empty_passwords"] = "updated"
        except Exception as e:
            results["permit_empty_passwords"] = f"error: {e}"
        
        if new_password_for_user:
            try:
                user, new_password = new_password_for_user
                self.set_new_password_for_user(user, new_password)
                results["new_password_for_user"] = "updated"
            except Exception as e:
                results["new_password_for_user"] = f"error: {e}"
        
        try:
            self.reload_ssh_service()
            results["reload_ssh_service"] = "success"
        except Exception as e:
            results["reload_ssh_service"] = f"error: {e}"

        return results

    def set_password_auth(self, enable: bool):
        """
        Enables (True) or disables (False) password authentication.
        """
        value = 'yes' if enable else 'no'
        self._update_config_option("PasswordAuthentication", value)

    def set_pubkey_auth(self, enable: bool):
        """
        Enables (True) or disables (False) SSH key authentication.
        """
        value = 'yes' if enable else 'no'
        self._update_config_option("PubkeyAuthentication", value)

    def set_permit_root_login(self, value: str):
        """
        Sets the PermitRootLogin option.
        Acceptable values include: 'yes', 'no', 'prohibit-password', 'forced-commands-only', etc.
        """
        self._update_config_option("PermitRootLogin", value)

    def set_permit_empty_passwords(self, enable: bool):
        """
        Enables (True) or disables (False) empty passwords.
        """
        val = "yes" if enable else "no"
        self._update_config_option("PermitEmptyPasswords", val)

    def set_new_password_for_user(self, user: str, new_password: str):
        """
        Sets a new password for the given user.
        Requires appropriate privileges (i.e. running as root).
        """
        try:
            password_entry = f"{user}:{new_password}"
            subprocess.check_call(
                ["chpasswd"],
                input=password_entry.encode(),
                stderr=subprocess.STDOUT
            )
            logger.info(f"Password for user {user} updated successfully.")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to update password for user {user}: {e}")

    def reload_ssh_service(self):
        """
        Reloads the SSH service to apply configuration changes.
        Tries multiple common commands to restart or reload the ssh/sshd service.
        If all commands fail, retries after 1 second, up to 5 attempts.
        """
        commands = [
            ['service', 'ssh', 'restart'],
            ['service', 'sshd', 'restart'],
            ['systemctl', 'reload', 'sshd'],
            ['systemctl', 'restart', 'sshd'],
            ['/etc/init.d/sshd', 'restart']
        ]
        
        max_attempts = 5
        for attempt in range(1, max_attempts + 1):
            for cmd in commands:
                try:
                    subprocess.check_call(cmd)
                    logger.info(f"SSH service reloaded successfully using: {' '.join(cmd)}")
                    return
                except subprocess.CalledProcessError as e:
                    logger.error(f"Attempt {attempt}: Error reloading SSH service using: {' '.join(cmd)}: {e}")
            # If none of the commands succeeded, wait one second before retrying
            logger.info(f"Retrying SSH service reload (attempt {attempt}/{max_attempts}) in 1 second...")
            time.sleep(1)
        
        logger.error("Failed to reload SSH service using all known commands after 5 attempts.")

    def add_ssh_key(self, username: str, public_key: str):
        """
        Adds a public SSH key to the specified user's authorized_keys file.
        If the .ssh directory or the authorized_keys file does not exist, they will be created.
        """
        try:
            user_info = pwd.getpwnam(username)
        except KeyError:
            logger.error(f"User {username} not found.")
            return

        home_dir = user_info.pw_dir
        ssh_dir = os.path.join(home_dir, '.ssh')
        auth_keys = os.path.join(ssh_dir, 'authorized_keys')

        os.makedirs(ssh_dir, mode=0o700, exist_ok=True)

        if not os.path.exists(auth_keys):
            open(auth_keys, 'a').close()
            os.chmod(auth_keys, 0o600)

        with open(auth_keys, 'r') as f:
            keys = f.read().splitlines()

        if public_key.strip() in keys:
            logger.info("Key is already added.")
        else:
            with open(auth_keys, 'a') as f:
                f.write(public_key.strip() + "\n")
            logger.info("Key added successfully.")
            self.reload_ssh_service()

    def remove_ssh_key(self, username: str, public_key: str):
        """
        Removes the specified public SSH key from the user's authorized_keys file.
        """
        try:
            user_info = pwd.getpwnam(username)
        except KeyError:
            logger.error(f"User {username} not found.")
            return

        home_dir = user_info.pw_dir
        auth_keys = os.path.join(home_dir, '.ssh', 'authorized_keys')

        if not os.path.exists(auth_keys):
            logger.info("authorized_keys file not found.")
            return

        with open(auth_keys, 'r') as f:
            keys = f.read().splitlines()

        new_keys = [k for k in keys if k.strip() != public_key.strip()]

        if len(new_keys) == len(keys):
            logger.info("The specified key was not found in authorized_keys.")
        else:
            with open(auth_keys, 'w') as f:
                f.write("\n".join(new_keys) + "\n")
            logger.info("Key removed successfully.")
            self.reload_ssh_service()

    def get_ssh_keys(self, username: str):
        """
        Returns a list of all SSH keys for the specified user, read from the authorized_keys file.
        If the file or the .ssh directory does not exist, an empty list is returned.
        """
        try:
            user_info = pwd.getpwnam(username)
        except KeyError:
            logger.error(f"User {username} not found.")
            return []

        auth_keys_path = os.path.join(user_info.pw_dir, '.ssh', 'authorized_keys')

        if not os.path.exists(auth_keys_path):
            logger.info("authorized_keys file not found.")
            return []

        try:
            with open(auth_keys_path, 'r') as f:
                keys = [line.strip() for line in f if line.strip()]
            logger.info(f"Found {len(keys)} SSH key(s) for user {username}.")
            return keys
        except Exception as e:
            logger.error(f"Error reading file {auth_keys_path}: {e}")
            return []

    def generate_ssh_key(self, comment: str = "", passphrase: str = "", key_type: str = "rsa", bits: int = 2048):
        """
        Генерирует SSH ключи (приватный и публичный) с использованием библиотеки cryptography и возвращает их в виде словаря.
        Ключи не сохраняются на диск.
        
        :param comment: Комментарий к ключу, который будет добавлен в публичный ключ.
        :param passphrase: Пароль для защиты приватного ключа. Если пустая строка, используется NoEncryption.
        :param key_type: Тип ключа ('rsa' или 'ed25519'). По умолчанию 'rsa'.
        :param bits: Размер ключа для RSA. Не используется для ed25519.
        :return: Словарь с ключами: 'private_key' (в PEM формате), 'public_key' (строка OpenSSH формата) и 'comment'.
        """
        try:
            if key_type.lower() == 'rsa':
                private_key = rsa.generate_private_key(
                    public_exponent=65537,
                    key_size=bits,
                    backend=default_backend()
                )
            elif key_type.lower() == 'ed25519':
                private_key = ed25519.Ed25519PrivateKey.generate()
            else:
                raise ValueError("Unsupported key type. Use 'rsa' or 'ed25519'.")

            if passphrase:
                encryption_algorithm = serialization.BestAvailableEncryption(passphrase.encode())
            else:
                encryption_algorithm = serialization.NoEncryption()
            
            if key_type.lower() == 'ed25519':
                private_bytes = private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,  # Для ed25519 используется PKCS8
                    encryption_algorithm=encryption_algorithm
                )
            else:
                private_bytes = private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.TraditionalOpenSSL,
                    encryption_algorithm=encryption_algorithm
                )

            public_key = private_key.public_key()
            public_bytes = public_key.public_bytes(
                encoding=serialization.Encoding.OpenSSH,
                format=serialization.PublicFormat.OpenSSH
            )
            public_key_str = public_bytes.decode('utf-8')
            if comment:
                public_key_str += " " + comment

            # Возвращаем словарь с приватным и публичным ключом, а также комментарий
            return {
                "private_key": private_bytes,
                "public_key": public_key_str,
                "comment": comment
            }
        except Exception as e:
            logger.error(f"Ошибка при генерации SSH ключа: {e}")
            return None
        
def sync_keys():
    from tgbot.models import SSHKey, Server
    server = Server.get_solo()
    desired_keys = set(SSHKey.objects.values_list('public_key', flat=True))
    manager = SSHAccessManager()
    
    current_keys = set(manager.get_ssh_keys(server.user))
    keys_to_add = desired_keys - current_keys
    keys_to_remove = current_keys - desired_keys

    for key in keys_to_add:
        manager.add_ssh_key(server.user, key)
    
    for key in keys_to_remove:
        manager.remove_ssh_key(server.user, key)
    
