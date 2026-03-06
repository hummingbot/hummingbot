import logging
import requests
import websockets
import asyncio
import json

class GRVTPerpetualConnector:
    def __init__(self, api_key: str, api_secret: str, base_url: str = 'https://api.grvt.io'):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url
        self.session = requests.Session()

    def _get_headers(self):
        return {
            'API-Key': self.api_key,
            'API-Secret': self.api_secret
        }

    def place_order(self, symbol: str, side: str, price: float, quantity: float, order_type: str = "LIMIT"):
        url = f"{self.base_url}/v1/order"
        payload = {
            'symbol': symbol,
            'side': side,
            'price': price,
            'quantity': quantity,
            'order_type': order_type
        }
        response = self.session.post(url, headers=self._get_headers(), data=payload)
        return response.json()

    def cancel_order(self, order_id: str):
        url = f"{self.base_url}/v1/order/{order_id}/cancel"
        response = self.session.delete(url, headers=self._get_headers())
        return response.json()

    def get_balance(self):
        url = f"{self.base_url}/v1/account/balance"
        response = self.session.get(url, headers=self._get_headers())
        return response.json()

    def get_positions(self):
        url = f"{self.base_url}/v1/positions"
        response = self.session.get(url, headers=self._get_headers())
        return response.json()

    async def websocket_connect(self, symbol: str):
        uri = f"wss://api.grvt.io/ws"
        async with websockets.connect(uri) as websocket:
            subscribe_msg = json.dumps({
                'type': 'subscribe',
                'symbol': symbol
            })
            await websocket.send(subscribe_msg)
            while True:
                response = await websocket.recv()
                print(response)

    def start_websocket(self, symbol: str):
        asyncio.get_event_loop().run_until_complete(self.websocket_connect(symbol))