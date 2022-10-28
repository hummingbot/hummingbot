import threading
from typing import TYPE_CHECKING

from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.remote_iface.mqtt import MQTTGateway

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication


class MQTTStartCommand:
    def start_mqtt(self,  # type: HummingbotApplication
                   ):
        if threading.current_thread() != threading.main_thread():
            self.ev_loop.call_soon_threadsafe(self.start_mqtt,)
            return
        safe_ensure_future(self.start_mqtt_async(), loop=self.ev_loop)

    async def start_mqtt_async(self,  # type: HummingbotApplication
                               ):
        if self._mqtt is None:
            self.logger().info("MQTT.Start command initiated.")
            self._mqtt = MQTTGateway(self)
            self._mqtt.start_notifier()
            self._mqtt.start_commands()
            self._mqtt.run()
        else:
            self.logger().info("MQTT is already initiated!")
