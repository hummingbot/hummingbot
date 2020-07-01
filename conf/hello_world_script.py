from hummingbot.script.script_base import ScriptBase


class HelloWorldScript(ScriptBase):
    """
    Demonstrates how to send messages using notify and log functions.
    """

    def on_tick(self):
        self.notify("Hello Hummingbots World!")
        self.log("Hello world logged.")
