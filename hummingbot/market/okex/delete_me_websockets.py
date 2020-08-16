import asyncio, websockets, json, zlib

OKCOIN_WS_URI = "wss://real.okex.com:8443/ws/v3"
# OKCOIN_WS_URI = "wss://okex.com:8443/ws/v3"


def inflate(data):
    decompress = zlib.decompressobj(
            -zlib.MAX_WBITS  # see above
    )
    inflated = decompress.decompress(data)
    inflated += decompress.flush()
    return inflated


async def sockets():
    async with websockets.connect(OKCOIN_WS_URI) as ws:
        ws: websockets.WebSocketClientProtocol = ws

        subscribe_request = {"op": "subscribe", "args": ["spot/depth:BTC-USDT"]}

        await ws.send(json.dumps(subscribe_request))
        while True:
            msg: str = await asyncio.wait_for(ws.recv(), timeout=1000000000)
            # uses Deflate compression: https://en.wikipedia.org/wiki/DEFLATE
            decripted_msg = inflate(msg).decode('utf-8')
            print(decripted_msg)
            print()


from okex_auth import OKExAuth

auth = OKExAuth(api_key="7fe4ba8a-88bd-4622-bb5e-45be8f5ff5f3", secret_key="2AA46A2E673364796E8AF154330C9ECB", passphrase="OBQ6s1D4hHEUdUZw6ZXlZ")

async def sockets_auth():
    async with websockets.connect(OKCOIN_WS_URI) as ws:
        ws: websockets.WebSocketClientProtocol = ws

        subscribe_request = auth.generate_ws_auth()
        await ws.send(json.dumps(subscribe_request))
        await asyncio.wait_for(ws.recv(), timeout=10)
        

        await ws.send(json.dumps({"op": "subscribe", "args": ["spot/order:BTC-USDT"]}))

        await ws.send(json.dumps({"op": "subscribe", "args": ["spot/account:USDT"]}))
        await ws.send(json.dumps({"op": "subscribe", "args": ["spot/account:BTC"]}))

        while True:
            msg: str = await asyncio.wait_for(ws.recv(), timeout=1000000000)
            # uses Deflate compression: https://en.wikipedia.org/wiki/DEFLATE
            decripted_msg = inflate(msg).decode('utf-8')
            print(decripted_msg)
            print()



if __name__ == '__main__':
    # asyncio.get_event_loop().run_until_complete(sockets())
    asyncio.get_event_loop().run_until_complete(sockets_auth())
