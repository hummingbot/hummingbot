import asyncio, websockets, json, zlib

OKCOIN_WS_URI = "wss://real.okex.com:8443/ws/v3"

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

        subscribe_request = {"op": "subscribe", "args": ["spot/trade:BTC-USDT"]}

        await ws.send(json.dumps(subscribe_request))
        while True:
            msg: str = await asyncio.wait_for(ws.recv(), timeout=1000000000)
            # uses Deflate compression: https://en.wikipedia.org/wiki/DEFLATE
            decripted_msg = inflate(msg).decode('utf-8')
            print(decripted_msg)



if __name__ == '__main__':
    asyncio.get_event_loop().run_until_complete(sockets())
