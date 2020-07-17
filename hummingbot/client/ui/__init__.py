from prompt_toolkit.shortcuts import input_dialog, message_dialog
from prompt_toolkit.styles import Style
from os.path import join, realpath, dirname
import sys; sys.path.insert(0, realpath(join(__file__, "../../../")))

with open(realpath(join(dirname(__file__), '../../VERSION'))) as version_file:
    version = version_file.read().strip()

dialog_style = Style.from_dict({
    'dialog': 'bg:#171E2B',
    'dialog frame.label': 'bg:#ffffff #000000',
    'dialog.body': 'bg:#000000 #1CD085',
    'dialog shadow': 'bg:#171E2B',
    'button': 'bg:#000000',
    'text-area': 'bg:#000000 #ffffff',
})


def show_welcome():
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
    Codebase: https://github.com/coinalpha/hummingbot


        """.format(version=version),
        style=dialog_style).run()
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
        style=dialog_style).run()
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
        style=dialog_style).run()


def login_prompt():
    from hummingbot.client.config.security import Security
    import time

    err_msg = None
    if Security.new_password_required():
        show_welcome()
        password = input_dialog(
            title="Set Password",
            text="Create a password to protect your sensitive data. "
                 "This password is not shared with us nor with anyone else, so please store it securely."
                 "\n\nEnter your new password:",
            password=True,
            style=dialog_style).run()
        if password is None:
            return False
        re_password = input_dialog(
            title="Set Password",
            text="Please re-enter your password:",
            password=True,
            style=dialog_style).run()
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
            style=dialog_style).run()
        if password is None:
            return False
        if not Security.login(password):
            err_msg = "Invalid password - please try again."
    if err_msg is not None:
        message_dialog(
            title='Error',
            text=err_msg,
            style=dialog_style).run()
        return login_prompt()
    return True
