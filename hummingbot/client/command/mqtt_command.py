import asyncio
import threading
import time
from typing import TYPE_CHECKING

from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.remote_iface.mqtt import MQTTGateway

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication  # noqa: F401


SUBCOMMANDS = ['start', 'stop', 'restart']


class MQTTCommand:
    def mqtt_start(self,  # type: HummingbotApplication
                   timeout: float = 30.0
                   ):
        if threading.current_thread() != threading.main_thread():
            self.ev_loop.call_soon_threadsafe(self.mqtt_start, timeout)
            return
        safe_ensure_future(self.start_mqtt_async(timeout=timeout),
                           loop=self.ev_loop)

    def mqtt_stop(self,  # type: HummingbotApplication
                  ):
        if threading.current_thread() != threading.main_thread():
            self.ev_loop.call_soon_threadsafe(self.mqtt_stop)
            return
        safe_ensure_future(self.stop_mqtt_async(),
                           loop=self.ev_loop)

    def mqtt_restart(self,  # type: HummingbotApplication
                     timeout: float = 30.0
                     ):
        if threading.current_thread() != threading.main_thread():
            self.ev_loop.call_soon_threadsafe(self.mqtt_restart, timeout)
            return
        safe_ensure_future(self.restart_mqtt_async(timeout=timeout),
                           loop=self.ev_loop)

    async def start_mqtt_async(self,  # type: HummingbotApplication
                               timeout: float = 30.0
                               ):
        start_t = time.time()
        sleep_rate = 1  # seconds
        if self._mqtt is None:
            try:
                self._mqtt = MQTTGateway(self)
                self._mqtt.start()
                self.logger().info('Connecting MQTT Bridge...')
                while True:
                    if time.time() - start_t > timeout:
                        raise Exception(
                            f'Connection timed out after {timeout} seconds')
                    if self._mqtt.health:
                        self.logger().info('MQTT Bridge connected with success.')
                        self.notify('MQTT Bridge connected with success.')
                        break
                    await asyncio.sleep(sleep_rate)
            except Exception as e:
                self.logger().error(
                    f'Failed to connect MQTT Bridge: {str(e)}')
                self.notify('MQTT Bridge failed to connect to the broker.')
                self._mqtt.stop()
                self._mqtt = None
        else:
            self.logger().warning("MQTT Bridge is already running!")
            self.notify('MQTT Bridge is already running!')

    async def stop_mqtt_async(self,  # type: HummingbotApplication
                              ):
        if self._mqtt is not None:
            try:
                self._mqtt.stop()
                self._mqtt = None
                self.logger().info("MQTT Bridge disconnected")
                self.notify('MQTT Bridge disconnected')
            except Exception as e:
                self.logger().error(f'Failed to stop MQTT Bridge: {str(e)}')
        else:
            self.logger().error("MQTT is already stopped!")
            self.notify('MQTT Bridge is already stopped!')

    async def restart_mqtt_async(self,  # type: HummingbotApplication
                                 timeout: float = 2.0
                                 ):
        await self.stop_mqtt_async()
        await self.start_mqtt_async(timeout)
