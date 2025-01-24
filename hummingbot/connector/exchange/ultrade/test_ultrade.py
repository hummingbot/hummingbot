import asyncio
import json

from ultrade import Client, socket_options

ultrade_trading_key = "xxxxxxxxxxx"
ultrade_wallet_address = "xxxxxxxx"
ultrade_mnemonic = "xxxxxxxxxxxx"
ultrade_session_token = "xxxxxxx"

NETWORK = "testnet"


async def create_client() -> Client:
    client = Client(network=NETWORK)
    client.set_trading_key(
        trading_key=ultrade_trading_key,
        address=ultrade_wallet_address,
        trading_key_mnemonic=ultrade_mnemonic
    )
    return client


async def fetch_balances(client: Client):
    try:
        balances = await client.get_balances()
        print("[fetch_balances] Balances:", json.dumps(balances, indent=4))
        return balances
    except Exception as e:
        print(f"[fetch_balances] Error: {str(e)}")
        return None


async def get_my_orders(client: Client, symbol: str = "algo_usdt"):
    try:
        orders_data = await client.get_orders_with_trades(symbol=symbol)
        print(f"[get_my_orders] Orders for {symbol}:", json.dumps(orders_data, indent=4))
        return orders_data
    except Exception as e:
        print(f"[get_my_orders] Error: {str(e)}")
        return None


async def cancel_order(client: Client, order_id: int):
    try:
        cancel_result = await client.cancel_order(order_id)
        print(f"[cancel_order] Successfully canceled order {order_id}")
        return cancel_result
    except Exception as e:
        print(f"[cancel_order] Error canceling order {order_id}: {str(e)}")


async def get_order_by_id(client: Client, order_id: int):
    try:
        order_info = await client.get_order_by_id(order_id)
        print(f"[get_order_by_id] Order {order_id} details:", json.dumps(order_info, indent=4))
        return order_info
    except Exception as e:
        print(f"[get_order_by_id] Error: {str(e)}")
        return None


async def place_limit_order(client: Client, pair_id: int, amount: int, price: int, side: str = 'buy'):
    try:
        order_side = 'B' if side == 'buy' else 'S'
        order_type = 'L'  # L = limit
        order_result = await client.create_order(
            pair_id=pair_id,
            order_side=order_side,
            order_type=order_type,
            amount=amount,
            price=price
        )
        print(f"[place_limit_order] Created limit order: {json.dumps(order_result, indent=4)}")
        return order_result
    except Exception as e:
        print(f"[place_limit_order] Error placing limit order: {str(e)}")
        return None


async def place_market_order(client: Client, pair_id: int, amount: int, side: str = 'buy'):
    try:
        order_side = 'B' if side == 'buy' else 'S'
        order_type = 'M'  # M = market
        order_result = await client.create_order(
            pair_id=pair_id,
            order_side=order_side,
            order_type=order_type,
            amount=amount,
            price=0
        )
        print(f"[place_market_order] Created market order: {json.dumps(order_result, indent=4)}")
        return order_result
    except Exception as e:
        print(f"[place_market_order] Error placing market order: {str(e)}")
        return None


async def main():
    client = await create_client()

    # initial_balances = await fetch_balances(client)

    # pairs = await client.get_pair_list()
    # print(f"[main] Pair list: {json.dumps(pairs, indent=4)}")
    symbol = "amax_usdc"
    # pair_info = await client.get_pair_info(symbol)
    # print(f"[main] pair_info for '{symbol}': {json.dumps(pair_info, indent=4)}")
    # order_book = await client.get_depth(symbol)
    # print(f"[main] order_book for '{symbol}': {json.dumps(order_book, indent=4)}")
    # price = await client.get_price(symbol)
    # print(f"[main] price for '{symbol}': {json.dumps(price, indent=4)}")

    # if not pair_info:
    #     print("[main] This symbol doesn't exist on your pair_list. Try a real pair from pair_list().")
    #     # Let's stop here, or pick a known pair from your pair_list:
    #     return

    # pair_id = pair_info["id"]
    # print(f"[main] Pair info => pair_id: {pair_id}")

    # # my_orders = await get_my_orders(client, symbol)
    # # if my_orders:
    # #     print(f"[main] Canceling all existing orders for {symbol}")
    # #     if isinstance(my_orders, list):
    # #         for order in my_orders:
    # #             order_id = order["id"]
    # #             await cancel_order(client, order_id)
    # #     else:
    # #         print(f"[main] Received non-list data for open orders, skipping cancellation logic.")

    # cancel_order_id = 12847747646
    # cancel_response = await cancel_order(client, cancel_order_id)
    # print(f"Cancel response: {cancel_response}")

    # get_order_by_id_response = await get_order_by_id(client, cancel_order_id)
    # print(f"Get order by ID response: {get_order_by_id_response}")

    def websocket_event_handler(event_name, event_data):
        print("======== WEBSOCKET EVENT ========")
        print("Event Name:", event_name)
        print("Event Data:", event_data)
        print("==================================")

    subscribe_options = {
        'symbol': symbol,
        'streams': [
            # socket_options.DEPTH,
            socket_options.TRADES,
            socket_options.ORDERS,
            socket_options.CODEX_BALANCES
        ],
        'options': {
            'address': ultrade_wallet_address,
            'company_id': 1,
            "token": ultrade_session_token
        }
    }

    connection_id = await client.subscribe(subscribe_options, websocket_event_handler)
    print(f"[main] Subscribed to websockets. Connection ID: {connection_id}")

    await asyncio.sleep(3000)

    await client.unsubscribe(connection_id)
    print("[main] Unsubscribed from websockets")

    # limit_order_amount = 3_000_000
    # limit_order_price = 500_000_000_000_000_000
    # limit_buy_response = await place_limit_order(
    #     client=client,
    #     pair_id=pair_id,
    #     amount=limit_order_amount,
    #     price=limit_order_price,
    #     side='buy'
    # )
    # limit_buy_order_id = None
    # if limit_buy_response and isinstance(limit_buy_response, dict):
    #     limit_buy_order_id = limit_buy_response.get("orderId") or limit_buy_response.get("id")

    # market_buy_amount = 1_000_000   # 1.0 ALGO
    # market_buy_response = await place_market_order(
    #     client=client,
    #     pair_id=pair_id,
    #     amount=market_buy_amount,
    #     side='buy'
    # )
    # market_buy_order_id = None
    # if market_buy_response and isinstance(market_buy_response, dict):
    #     market_buy_order_id = market_buy_response.get("orderId") or market_buy_response.get("id")

    # market_sell_amount = 500_000   # 0.5 ALGO
    # market_sell_response = await place_market_order(
    #     client=client,
    #     pair_id=pair_id,
    #     amount=market_sell_amount,
    #     side='sell'
    # )
    # market_sell_order_id = None
    # if market_sell_response and isinstance(market_sell_response, dict):
    #     market_sell_order_id = market_sell_response.get("orderId") or market_sell_response.get("id")

    # order_ids = [limit_buy_order_id, market_buy_order_id, market_sell_order_id]
    # for oid in order_ids:
    #     if oid is not None:
    #         await get_order_by_id(client, oid)

    # await fetch_balances(client)

    # if limit_buy_order_id:
    #     print(f"[main] Canceling limit buy order {limit_buy_order_id}")
    #     await cancel_order(client, limit_buy_order_id)
    #     await get_order_by_id(client, limit_buy_order_id)

    # await fetch_balances(client)
    # print("[main] All done.")


if __name__ == "__main__":
    asyncio.run(main())


# import asyncio
# import socketio

# sio = socketio.AsyncClient(reconnection_delay_max=5, logger=True)

# @sio.event
# async def connect():
#     print("Connected to Ultrade Testnet WebSocket")

# @sio.event
# async def disconnect():
#     print("Disconnected from Ultrade Testnet WebSocket")

# @sio.on("*")
# async def catch_all(event, data, sid=None):
#     print(f"Event: {event} | Data: {data} | SID: {sid}")

# async def main():
#     await sio.connect("wss://ws.testnet.ultrade.org", transports=["websocket"])

#     subscribe_data = [
#         "subscribe",
#         {
#             "symbol": "amax_usdc",
#             "streams": [3,4,5,6,7,8,9,10,13],
#             "options": {
#                 "address": "0x1136EaF53249B181B8e8a9D739c952Bdc1345de7",
#                 "companyId": 1,
#                 "token": "094bd9d6-e226-44b8-8833-0f2aef1cd0d5"
#             }
#         }
#     ]

#     await sio.emit(*subscribe_data)

#     await asyncio.sleep(20)

#     await sio.disconnect()

# if __name__ == "__main__":
#     asyncio.run(main())
