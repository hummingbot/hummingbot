from hummingbot.script.script_base import ScriptBase


class HelloWorldScript(ScriptBase):

    def on_tick(self):
        self.notify("Hello Hummingbots World!")
