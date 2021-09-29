from hummingbot.strategy.remote_commands_delegate_base import RemoteCommandsDelegateBase


class RemoteCommandsDelegate(RemoteCommandsDelegateBase):
    def on_remote_cmd(self, event_tag, executor, event):
        """
        Do anything you want with received remote command events here
        See RemoteCommandsDelegateBase for more info.
        """
        self.logger().notify(f"Received Remote Event:\n{event}")
