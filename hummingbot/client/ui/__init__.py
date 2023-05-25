import os
import sys
from os.path import dirname, join, realpath
from typing import Type

from prompt_toolkit.shortcuts import input_dialog, message_dialog
from prompt_toolkit.styles import Style

from hummingbot import root_path
from hummingbot.client.config.conf_migration import migrate_configs, migrate_non_secure_configs_only
from hummingbot.client.config.config_crypt import BaseSecretsManager, store_password_verification
from hummingbot.client.config.security import Security
from hummingbot.client.settings import CONF_DIR_PATH

sys.path.insert(0, str(root_path()))


with open(realpath(join(dirname(__file__), '../../VERSION'))) as version_file:
    version = version_file.read().strip()


def login_prompt(secrets_manager_cls: Type[BaseSecretsManager], style: Style):
    err_msg = None
    secrets_manager = None
    if Security.new_password_required():
        if legacy_confs_exist():
            secrets_manager = migrate_configs_prompt(secrets_manager_cls, style)
        else:
            show_welcome(style)
            password = input_dialog(
                title="Set Password",
                text="""
        Create a password to protect your sensitive data.
        This password is not shared with us nor with anyone else, so please store it securely.

        Enter your new password:""",
                password=True,
                style=style).run()
            if password is None:
                return None
            if password == str():
                err_msg = "The password must not be empty."
            else:
                re_password = input_dialog(
                    title="Set Password",
                    text="Please re-enter your password:",
                    password=True,
                    style=style).run()
                if re_password is None:
                    return None
                if password != re_password:
                    err_msg = "Passwords entered do not match, please try again."
                else:
                    secrets_manager = secrets_manager_cls(password)
                    store_password_verification(secrets_manager)
    else:
        password = input_dialog(
            title="Welcome back to Hummingbot",
            text="Enter your password:",
            password=True,
            style=style).run()
        if password is None:
            return None
        secrets_manager = secrets_manager_cls(password)
    if err_msg is None and not Security.login(secrets_manager):
        err_msg = "Invalid password - please try again."
    if err_msg is not None:
        message_dialog(
            title='Error',
            text=err_msg,
            style=style).run()
        return login_prompt(secrets_manager_cls, style)
    return secrets_manager


def legacy_confs_exist() -> bool:
    encrypted_conf_prefix = "encrypted_"
    encrypted_conf_postfix = ".json"
    exist = False
    for f in sorted(os.listdir(CONF_DIR_PATH)):
        f_path = CONF_DIR_PATH / f
        if os.path.isfile(f_path) and f.startswith(encrypted_conf_prefix) and f.endswith(encrypted_conf_postfix):
            exist = True
            break
    return exist


def migrate_configs_prompt(secrets_manager_cls: Type[BaseSecretsManager], style: Style) -> BaseSecretsManager:
    message_dialog(
        title='Configs Migration',
        text="""


            CONFIGS MIGRATION:

            We have recently refactored the way hummingbot handles configurations.
            To migrate your legacy configuration files to the new format,
            please enter your password on the following screen.

                """,
        style=style).run()
    password = input_dialog(
        title="Input Password",
        text="\n\nEnter your previous password:",
        password=True,
        style=style).run()
    if password is None:
        raise ValueError("Wrong password.")
    secrets_manager = secrets_manager_cls(password)
    errors = migrate_configs(secrets_manager)
    if len(errors) != 0:
        _migration_errors_dialog(errors, style)
    else:
        message_dialog(
            title='Configs Migration Success',
            text="""


                            CONFIGS MIGRATION SUCCESS:

                            The migration process was completed successfully.

                                """,
            style=style).run()
    return secrets_manager


def migrate_non_secure_only_prompt(style: Style):
    message_dialog(
        title='Configs Migration',
        text="""


                CONFIGS MIGRATION:

                We have recently refactored the way hummingbot handles configurations.
                We will now attempt to migrate any legacy config files to the new format.

                    """,
        style=style).run()
    errors = migrate_non_secure_configs_only()
    if len(errors) != 0:
        _migration_errors_dialog(errors, style)
    else:
        message_dialog(
            title='Configs Migration Success',
            text="""


                            CONFIGS MIGRATION SUCCESS:

                            The migration process was completed successfully.

                                """,
            style=style).run()


def _migration_errors_dialog(errors, style: Style):
    padding = "\n                    "
    errors_str = padding + padding.join(errors)
    message_dialog(
        title='Configs Migration Errors',
        text=f"""


                CONFIGS MIGRATION ERRORS:

                {errors_str}

                    """,
        style=style).run()


def show_welcome(style: Style):
    message_dialog(
        title='Welcome to Hummingbot',
        text="""

    ██╗  ██╗██╗   ██╗███╗   ███╗███╗   ███╗██╗███╗   ██╗ ██████╗ ██████╗  ██████╗ ████████╗
    ██║  ██║██║   ██║████╗ ████║████╗ ████║██║████╗  ██║██╔════╝ ██╔══██╗██╔═══██╗╚══██╔══╝
    ███████║██║   ██║██╔████╔██║██╔████╔██║██║██╔██╗ ██║██║  ███╗██████╔╝██║   ██║   ██║
    ██╔══██║██║   ██║██║╚██╔╝██║██║╚██╔╝██║██║██║╚██╗██║██║   ██║██╔══██╗██║   ██║   ██║
    ██║  ██║╚██████╔╝██║ ╚═╝ ██║██║ ╚═╝ ██║██║██║ ╚████║╚██████╔╝██████╔╝╚██████╔╝   ██║
    ╚═╝  ╚═╝ ╚═════╝ ╚═╝     ╚═╝╚═╝     ╚═╝╚═╝╚═╝  ╚═══╝ ╚═════╝ ╚═════╝  ╚═════╝    ╚═╝

    =======================================================================================

    Version: {version}
    Codebase: https://github.com/hummingbot/hummingbot


        """.format(version=version),
        style=style).run()
    message_dialog(
        title='Important Warning',
        text="""


    PLEASE READ THIS CAREFULLY BEFORE USING HUMMINGBOT:

    Hummingbot is a free and open source software client that helps you build algorithmic
    crypto trading strategies.

    Algorithmic crypto trading is a risky activity. You will be building a "bot" that
    automatically places orders and trades based on parameters that you set. Please take
    the time to understand how each strategy works before you risk real capital with it.
    You are solely responsible for the trades that you perform using Hummingbot.

        """,
        style=style).run()
    message_dialog(
        title='Important Warning',
        text="""


    SET A SECURE PASSWORD:

    To use Hummingbot, you will need to give it access to your crypto assets by entering
    your exchange API keys and/or wallet private keys. These keys are not shared with
    anyone, including us.

    On the next screen, you will set a password to protect these keys and other sensitive
    data. Please store this password safely since there is no way to reset it.

        """,
        style=style).run()
