from typing import Dict

import random
import pandas as pd
import pandas_ta as ta  # noqa: F401
from paho.mqtt import client as mqtt_client

from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from hummingbot.data_feed.candles_feed.candles_factory import CandlesConfig, CandlesFactory


class A(ScriptStrategyBase):
    """突破趋势自动交易策略
    MQTT
    """

    maker_pair = "ETH-USDT"
    maker_exchange = "kucoin_paper_trade"
    markets = {maker_exchange: {maker_pair}}

    # MQTT 配置
    client = None
    mqtt_data = None
    broker = "broker.emqx.io"
    port = 1883
    topic = "/hummingbot/mqtt"
    client_id = f"hummingbot-mqtt-{random.randint(0, 100)}"

    def __init__(self, connectors: Dict[str, ConnectorBase]):
        super().__init__(connectors)

        # 启动MQTT
        self.client = self.connect_mqtt()
        self.subscribe(self.client)
        self.client.loop_start()

    def on_tick(self):
        """1秒执行一次心跳"""
        if self.mqtt_data:
            self.logger().info(f"MQTT数据: {self.mqtt_data}")
            self.notify_hb_app_with_timestamp(f"收到MQTT数据：{self.mqtt_data}")
            self.mqtt_data = None

    def on_stop(self):
        """结束时运行"""
        self.client.loop_stop()

    def format_status(self) -> str:
        """
        Displays the three candlesticks involved in the script with RSI, BBANDS and EMA.
        """
        if not self.ready_to_trade:
            return "Market connectors are not ready."

        lines = []
        if self.all_mqtt_ready:
            lines.extend(
                [
                    "\n############################################ MQTT已经连接 ############################################\n"
                ]
            )
        else:
            lines.extend(["", "  未连接."])

        return "\n".join(lines)

    @property
    def all_mqtt_ready(self):
        return self.client and self.client.is_connected()

    def connect_mqtt(
        self,
    ) -> mqtt_client:
        def on_connect(client: any, userdata: any, flags: any, rc: any):
            if rc == 0:
                self.logger().info("已连接到 MQTT Broker!")
            else:
                self.logger().info("无法连接到 MQTT 错误码 %d\n", rc)

        client = mqtt_client.Client(self.client_id)
        client.on_connect = on_connect
        client.connect(self.broker, self.port)
        return client

    def subscribe(self, client: mqtt_client):
        def on_message(client: any, userdata: any, msg: any):
            self.logger().info(f"收到 MQTT 服务器数据 `{msg.payload.decode()}` 主题 `{msg.topic}` topic")
            self.mqtt_data = msg.payload.decode()

        client.subscribe(self.topic)
        client.on_message = on_message
