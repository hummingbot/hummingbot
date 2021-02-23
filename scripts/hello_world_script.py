from hummingbot.script.script_base import ScriptBase


class HelloWorldScript(ScriptBase):
    """
    Demonstrates how to send messages using notify and log functions. It also shows how errors and commands are handled.
    """

    def on_tick(self):
        if len(self.mid_prices) < 3:
            self.notify("Hello Hummingbots World!")
            self.log("Hello world logged.")
        elif 3 <= len(self.mid_prices) < 5:
            # This below statement will cause ZeroDivisionError, Hummingbot will later report this on the log screen.
            _ = 1 / 0

    def on_command(self, cmd, args):
        if cmd == 'ping':
            self.notify('pong!')
        else:
            self.notify(f'Unrecognised command: {cmd}')
