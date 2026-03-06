import asyncio
from hummingbot.connector.connector_base import ConnectorBase
from .grvt_rest_api import GRVTRestAPI
from .grvt_websocket import GRVTWebSocket

class GRVTPerpetualConnector(ConnectorBase):
    def __init__(self, config: dict):
        super().__init__(config)
        self.rest_api = GRVTRestAPI(config)
        self.ws_api = GRVTWebSocket(config)

    def start(self):
        self.rest_api.initialize()
        self.ws_api.initialize()

    def place_order(self, order):
        return self.rest_api.place_order(order)

    def cancel_order(self, order_id):
        return self.rest_api.cancel_order(order_id)

    def get_balance(self):
        return self.rest_api.get_balance()

    def get_position(self):
        return self.rest_api.get_position()