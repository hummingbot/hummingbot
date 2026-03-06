import logging
import requests
import json
from websocket import create_connection

# Set up logging
logger = logging.getLogger(__name__)

class DecibelPerpConnector:
    def __init__(self, api_key, api_secret, base_url='https://api.decibel.trade'):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url
        self.session = requests.Session()

    def _send_request(self, method, endpoint, params=None):
        url = f"{self.base_url}{endpoint}"
        headers = {
            'X-API-KEY': self.api_key,
        }
        response = self.session.request(method, url, headers=headers, params=params)
        if response.status_code != 200:
            logger.error(f"Error: {response.status_code}, {response.text}")
            return None
        return response.json()

    # REST API - Place limit order
    def place_limit_order(self, symbol, side, quantity, price, time_in_force='GTC'):
        params = {
            'symbol': symbol,
            'side': side,
            'quantity': quantity,
            'price': price,
            'time_in_force': time_in_force
        }
        return self._send_request('POST', '/v1/order', params)

    # REST API - Place market order
    def place_market_order(self, symbol, side, quantity):
        params = {
            'symbol': symbol,
            'side': side,
            'quantity': quantity
        }
        return self._send_request('POST', '/v1/order/market', params)

    # REST API - Cancel order
    def cancel_order(self, order_id):
        return self._send_request('DELETE', f'/v1/order/{order_id}')

    # REST API - Fetch balance
    def get_balance(self):
        return self._send_request('GET', '/v1/balance')

    # WebSocket API - Connect and listen for orderbook updates
    def listen_orderbook(self, symbol):
        ws_url = f"wss://ws.decibel.trade/orderbook/{symbol}"
        ws = create_connection(ws_url)
        while True:
            message = ws.recv()
            logger.info(f"Orderbook Update: {message}")
            print(message)
        ws.close()

# Example usage:
if __name__ == "__main__":
    connector = DecibelPerpConnector(api_key='your_api_key', api_secret='your_api_secret')

    # Place a limit order example
    response = connector.place_limit_order('BTCUSD', 'buy', 1.0, 50000)
    print(response)

    # Fetch balance example
    balance = connector.get_balance()
    print(balance)

    # WebSocket connection for live orderbook updates
    connector.listen_orderbook('BTCUSD')