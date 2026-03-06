import websockets
import asyncio

class GRVTWebSocket:
    def __init__(self, config):
        self.api_key = config.get('api_key')
        self.ws_url = 'wss://api.grvt.io/ws'

    async def initialize(self):
        async with websockets.connect(self.ws_url) as websocket:
            await self.listen(websocket)

    async def listen(self, websocket):
        while True:
            response = await websocket.recv()
            print(f'Received message: {response}')