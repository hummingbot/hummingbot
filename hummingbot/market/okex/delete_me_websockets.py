import asyncio, websockets, json, zlib

OKCOIN_WS_URI = "wss://real.okex.com:8443/ws/v3"
#OKCOIN_WS_URI = "wss://real.okex.com:8443/ws/v3?brokerId=9999"
OKCOIN_WS_URI = "wss://real.okcoin.com:8443/ws/v3"


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


# Paper mode
# auth = OKExAuth(api_key="fa4129c0-d8dd-46ea-9f30-192b5d3c4e72",
#                 secret_key="6895B90754AA2308ADC8ABA5C5756681",
#                 passphrase="OBQ6s1D4hHEUdUZw6ZXlZ")


# Example response

# {"table":"spot/order","data":[{"client_oid":"","created_at":"2020-08-25T10:13:05.313Z","event_code":"0","event_message":"","fee":"","fee_currency":"","filled_notional":"0","filled_size":"0","instrument_id":"ETH-EUR","last_amend_result":"","last_fill_id":"0","last_fill_px":"0","last_fill_qty":"0","last_fill_time":"1970-01-01T00:00:00.000Z","last_request_id":"","margin_trading":"1","notional":"","order_id":"5479752355820544","order_type":"0","price":"500","rebate":"","rebate_currency":"","side":"sell","size":"0.1","state":"0","status":"open","timestamp":"2020-08-25T10:13:05.313Z","type":"limit"}]}

# {"table":"spot/account","data":[{"available":"2.573878","balance":"2.673878","currency":"ETH","hold":"0.1","id":"","timestamp":"2020-08-25T10:13:05.313Z"}]}

# {"table":"spot/order","data":[{"client_oid":"","created_at":"2020-08-25T10:13:05.313Z","event_code":"0","event_message":"","fee":"","fee_currency":"","filled_notional":"0","filled_size":"0","instrument_id":"ETH-EUR","last_amend_result":"","last_fill_id":"0","last_fill_px":"0","last_fill_qty":"0","last_fill_time":"1970-01-01T00:00:00.000Z","last_request_id":"","margin_trading":"1","notional":"","order_id":"5479752355820544","order_type":"0","price":"500","rebate":"","rebate_currency":"","side":"sell","size":"0.1","state":"-1","status":"cancelled","timestamp":"2020-08-25T10:15:13.338Z","type":"limit"}]}

# {"table":"spot/account","data":[{"available":"2.673878","balance":"2.673878","currency":"ETH","hold":"0","id":"","timestamp":"2020-08-25T10:15:13.338Z"}]}

# {"table":"spot/order","data":[{"client_oid":"","created_at":"2020-08-25T10:15:47.400Z","event_code":"0","event_message":"","fee":"","fee_currency":"","filled_notional":"0","filled_size":"0","instrument_id":"ETH-EUR","last_amend_result":"","last_fill_id":"0","last_fill_px":"0","last_fill_qty":"0","last_fill_time":"1970-01-01T00:00:00.000Z","last_request_id":"","margin_trading":"1","notional":"","order_id":"5479762978418688","order_type":"0","price":"100","rebate":"","rebate_currency":"","side":"sell","size":"0.01","state":"0","status":"open","timestamp":"2020-08-25T10:15:47.400Z","type":"limit"}]}

# {"table":"spot/account","data":[{"available":"2.663878","balance":"2.673878","currency":"ETH","hold":"0.01","id":"","timestamp":"2020-08-25T10:15:47.400Z"}]}

# {"table":"spot/order","data":[{"client_oid":"","created_at":"2020-08-25T10:15:47.400Z","event_code":"0","event_message":"","fee":"-0.006682","fee_currency":"EUR","filled_notional":"3.341","filled_size":"0.01","instrument_id":"ETH-EUR","last_amend_result":"","last_fill_id":"33456","last_fill_px":"334.1","last_fill_qty":"0.01","last_fill_time":"2020-08-25T10:15:47.404Z","last_request_id":"","margin_trading":"1","notional":"","order_id":"5479762978418688","order_type":"0","price":"100","rebate":"","rebate_currency":"","side":"sell","size":"0.01","state":"2","status":"filled","timestamp":"2020-08-25T10:15:47.404Z","type":"limit"}]}

# {"table":"spot/account","data":[{"available":"4.210284826","balance":"4.210284826","currency":"EUR","hold":"0","id":"","timestamp":"2020-08-25T10:15:47.405Z"}]}

# {"table":"spot/account","data":[{"available":"2.663878","balance":"2.663878","currency":"ETH","hold":"0","id":"","timestamp":"2020-08-25T10:15:47.405Z"}]}

# {"table":"spot/order","data":[{"client_oid":"","created_at":"2020-08-25T10:16:26.354Z","event_code":"0","event_message":"","fee":"","fee_currency":"","filled_notional":"0","filled_size":"0","instrument_id":"ETH-EUR","last_amend_result":"","last_fill_id":"0","last_fill_px":"0","last_fill_qty":"0","last_fill_time":"1970-01-01T00:00:00.000Z","last_request_id":"","margin_trading":"1","notional":"","order_id":"5479765531310080","order_type":"0","price":"334.2","rebate":"","rebate_currency":"","side":"sell","size":"0.01","state":"0","status":"open","timestamp":"2020-08-25T10:16:26.354Z","type":"limit"}]}

# {"table":"spot/account","data":[{"available":"2.653878","balance":"2.663878","currency":"ETH","hold":"0.01","id":"","timestamp":"2020-08-25T10:16:26.354Z"}]}

# {"table":"spot/account","data":[{"available":"7.548942826","balance":"7.548942826","currency":"EUR","hold":"0","id":"","timestamp":"2020-08-25T10:16:50.807Z"}]}

# {"table":"spot/order","data":[{"client_oid":"","created_at":"2020-08-25T10:16:26.354Z","event_code":"0","event_message":"","fee":"-0.003342","fee_currency":"EUR","filled_notional":"3.342","filled_size":"0.01","instrument_id":"ETH-EUR","last_amend_result":"","last_fill_id":"33457","last_fill_px":"334.2","last_fill_qty":"0.01","last_fill_time":"2020-08-25T10:16:50.807Z","last_request_id":"","margin_trading":"1","notional":"","order_id":"5479765531310080","order_type":"0","price":"334.2","rebate":"","rebate_currency":"","side":"sell","size":"0.01","state":"2","status":"filled","timestamp":"2020-08-25T10:16:50.807Z","type":"limit"}]}

# {"table":"spot/account","data":[{"available":"2.653878","balance":"2.653878","currency":"ETH","hold":"0","id":"","timestamp":"2020-08-25T10:16:50.807Z"}]}



async def sockets_auth():
    async with websockets.connect(OKCOIN_WS_URI) as ws:
        ws: websockets.WebSocketClientProtocol = ws

        subscribe_request = auth.generate_ws_auth()
        await ws.send(json.dumps(subscribe_request))
        await asyncio.wait_for(ws.recv(), timeout=10)
        

        # await ws.send(json.dumps({"op": "subscribe", "args": ["spot/order:BTC-USDT"]}))

        # await ws.send(json.dumps({"op": "subscribe", "args": ["spot/account:USDT"]}))
        # await ws.send(json.dumps({"op": "subscribe", "args": ["spot/account:BTC"]}))

        await ws.send(json.dumps({"op": "subscribe", "args": ["spot/order:ETH-EUR"]}))

        await ws.send(json.dumps({"op": "subscribe", "args": ["spot/account:EUR"]}))
        await ws.send(json.dumps({"op": "subscribe", "args": ["spot/account:ETH"]}))

        while True:
            msg: str = await asyncio.wait_for(ws.recv(), timeout=1000000000)
            # uses Deflate compression: https://en.wikipedia.org/wiki/DEFLATE
            decripted_msg = inflate(msg).decode('utf-8')
            print(decripted_msg)
            print()



if __name__ == '__main__':
    #asyncio.get_event_loop().run_until_complete(sockets())
    asyncio.get_event_loop().run_until_complete(sockets_auth())
