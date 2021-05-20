from hummingbot.script.script_base import ScriptBase


class HelloWorldScript(ScriptBase):
    """
    Demonstrates how to send messages using notify and log functions. It also shows how errors handled.
    """

    def on_tick(self):
        if len(self.mid_prices) < 3:
            self.notify("Hello Hummingbots World!")
            self.log("Hello world logged.")
        elif 3 <= len(self.mid_prices) < 5:
            # This below statement will cause ZeroDivisionError, Hummingbot will later report this on the log screen.
            _ = 1 / 0
