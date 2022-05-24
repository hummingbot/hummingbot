from os.path import dirname, join, realpath

from prompt_toolkit.shortcuts import input_dialog, message_dialog
from prompt_toolkit.styles import Style

import sys; sys.path.insert(0, realpath(join(__file__, "../../../")))

with open(realpath(join(dirname(__file__), '../../VERSION'))) as version_file:
    version = version_file.read().strip()


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

    To use Hummingbot, you first need to give it access to your crypto assets by entering
    API keys and/or private keys. These keys are not shared with anyone, including us.

    On the next screen, you will set a password to protect your use of Hummingbot. Please
    store this password safely, since only you have access to it and we cannot reset it.

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


def login_prompt(style: Style):
    import time

    from hummingbot.client.config.security import Security

    err_msg = None
    if Security.new_password_required():
        show_welcome(style)
        password = input_dialog(
            title="Set Password",
            text="Create a password to protect your sensitive data. "
                 "This password is not shared with us nor with anyone else, so please store it securely."
                 "\n\nEnter your new password:",
            password=True,
            style=style).run()
        if password is None:
            return False
        re_password = input_dialog(
            title="Set Password",
            text="Please re-enter your password:",
            password=True,
            style=style).run()
        if re_password is None:
            return False
        if password != re_password:
            err_msg = "Passwords entered do not match, please try again."
        else:
            Security.login(password)
            # encrypt current timestamp as a dummy to prevent promping for password if bot exits without connecting an exchange
            dummy = f"{time.time()}"
            Security.update_secure_config("default", dummy)
    else:
        password = input_dialog(
            title="Welcome back to Hummingbot",
            text="Enter your password:",
            password=True,
            style=style).run()
        if password is None:
            return False
        if not Security.login(password):
            err_msg = "Invalid password - please try again."
    if err_msg is not None:
        message_dialog(
            title='Error',
            text=err_msg,
            style=style).run()
        return login_prompt()
    return True
