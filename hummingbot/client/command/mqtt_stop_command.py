import threading
from typing import TYPE_CHECKING

from hummingbot.core.utils.async_utils import safe_ensure_future

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication  # noqa: F401


class MQTTStopCommand:
    def stop_mqtt(self,  # type: HummingbotApplication
                  timeout: int = 2
                  ):
        if threading.current_thread() != threading.main_thread():
            self.ev_loop.call_soon_threadsafe(self.stop_mqtt,)
            return
        safe_ensure_future(self.stop_mqtt_async(timeout=timeout),
                           loop=self.ev_loop)

    async def stop_mqtt_async(self,  # type: HummingbotApplication
                              timeout: int = 2
                              ):
        if self._mqtt is not None:
            try:
                self._mqtt.stop()
                self._mqtt = None
                self.logger().info("MQTT Bridge stopped.")
            except Exception as e:
                self.logger().error(f'Failed to stop MQTT Bridge: {str(e)}')
        else:
            self.logger().error("MQTT is already stopped")
