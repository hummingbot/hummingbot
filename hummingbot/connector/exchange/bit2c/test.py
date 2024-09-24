import asyncio
import base64
import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import aiohttp

API_KEY = 'xxxxxx'
SECRET_KEY = 'xxxxxxxxxxxx'
BASE_URL = 'https://bit2c.co.il'


def generate_signature(secret_key, params):
    """
    Generates an HMAC SHA512 signature for the Bit2C API.
    """
    encoded_params_str = urlencode(params)
    signature = base64.b64encode(hmac.new(SECRET_KEY.upper().encode("ASCII"), encoded_params_str.encode("ASCII"), hashlib.sha512).digest()).decode("ASCII").replace("\n", "")
    return signature


async def fetch_balances(session):
    try:
        url = f"{BASE_URL}/Account/Balance"
        nonce = int(time.time_ns() * 1e-3)
        params = {'nonce': nonce}
        sign = generate_signature(SECRET_KEY, params)
        headers = {
            'Key': API_KEY,
            'Sign': sign,
            'Content-Type': 'application/x-www-form-urlencoded',
        }
        async with session.get(url, headers=headers, params=params) as response:
            if response.status != 200:
                error_message = await response.text()
                raise Exception(f"Error fetching balances: HTTP {response.status} - {error_message}")
            return await response.json()
    except Exception as e:
        print(f"An error occurred while fetching balances: {e}")
        return None


async def place_limit_order(session, amount, price, side, pair='BtcNis'):
    try:
        url = f"{BASE_URL}/Order/AddOrder"
        nonce = int(time.time_ns() * 1e-3)
        params = {
            'nonce': nonce,
            'Amount': f"{amount:.8f}",
            'Price': f"{price:.2f}",
            'IsBid': True if side == 'buy' else False,
            'Pair': pair
        }
        sign = generate_signature(SECRET_KEY, params)
        headers = {
            'Key': API_KEY,
            'Sign': sign,
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        async with session.post(url, headers=headers, data=params) as response:
            if response.status == 409:
                error_message = await response.text()
                print(f"Conflict error: {error_message}")
                return None
            if response.content_type != 'application/json':
                error_message = await response.text()
                print(f"Error: Non-JSON response received: {error_message}")
                return None
            return await response.json()
    except Exception as e:
        print(f"An error occurred while placing the limit order: {e}")
        return None


async def place_market_order(session, amount, side, pair='BtcNis'):
    try:
        url = f"{BASE_URL}/Order/AddOrderMarketPrice{side.capitalize()}"
        nonce = int(time.time_ns() * 1e-3)
        params = {}
        if side == 'buy':
            params = {
                'nonce': nonce,
                'Total': f"{amount:.2f}",
                'Pair': pair
            }
        elif side == 'sell':
            params = {
                'nonce': nonce,
                'Amount': f"{amount:.8f}",
                'Pair': pair
            }
        sign = generate_signature(SECRET_KEY, params)
        headers = {
            'Key': API_KEY,
            'Sign': sign,
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        async with session.post(url, headers=headers, data=params) as response:
            if response.status != 200:
                error_message = await response.text()
                raise Exception(f"Error placing market order: HTTP {response.status} - {error_message}")
            return await response.json()
    except Exception as e:
        print(f"An error occurred while placing the market order: {e}")
        return None


async def cancel_order(session, order_id):
    try:
        url = f"{BASE_URL}/Order/CancelOrder"
        nonce = int(time.time_ns() * 1e-3)
        params = {
            'nonce': nonce,
            'id': order_id
        }
        sign = generate_signature(SECRET_KEY, params)
        headers = {
            'Key': API_KEY,
            'Sign': sign
        }
        async with session.post(url, headers=headers, data=params) as response:
            if response.status != 200:
                error_message = await response.text()
                raise Exception(f"Error canceling order: HTTP {response.status} - {error_message}")
            return await response.json()
    except Exception as e:
        print(f"An error occurred while canceling the order: {e}")
        return None


async def get_order_by_id(session, order_id):
    try:
        url = f"{BASE_URL}/Order/GetById"
        nonce = int(time.time_ns() * 1e-3)
        params = {
            'nonce': nonce,
            'id': order_id
        }
        sign = generate_signature(SECRET_KEY, params)
        headers = {
            'Key': API_KEY,
            'Sign': sign
        }
        async with session.get(url, headers=headers, params=params) as response:
            if response.status != 200:
                error_message = await response.text()
                raise Exception(f"Error fetching order by ID: HTTP {response.status} - {error_message}")
            return await response.json()
    except Exception as e:
        print(f"An error occurred while fetching order by ID: {e}")
        return None


async def get_order_history_by_id(session, order_id):
    try:
        url = f"{BASE_URL}/Order/HistoryByOrderId"
        nonce = int(time.time_ns() * 1e-3)
        params = {
            'nonce': nonce,
            'id': order_id
        }
        sign = generate_signature(SECRET_KEY, params)
        headers = {
            'Key': API_KEY,
            'Sign': sign
        }
        async with session.get(url, headers=headers, params=params) as response:
            if response.status != 200:
                error_message = await response.text()
                raise Exception(f"Error fetching order history by ID: HTTP {response.status} - {error_message}")
            return await response.json()
    except Exception as e:
        print(f"An error occurred while fetching order history by ID: {e}")
        return None


async def get_my_orders(session, pair='BtcNis'):
    try:
        url = f"{BASE_URL}/Order/MyOrders"
        nonce = int(time.time_ns() * 1e-3)
        params = {
            'nonce': nonce,
            'pair': pair
        }
        sign = generate_signature(SECRET_KEY, params)
        headers = {
            'Key': API_KEY,
            'Sign': sign
        }
        async with session.get(url, headers=headers, params=params) as response:
            if response.status != 200:
                error_message = await response.text()
                raise Exception(f"Error fetching MyOrders: HTTP {response.status} - {error_message}")
            return await response.json()
    except Exception as e:
        print(f"An error occurred while fetching MyOrders: {e}")
        return None


async def main():
    async with aiohttp.ClientSession() as session:
        # Step 1: Fetch initial balances
        balance_data = await fetch_balances(session)
        print("Initial Balances:", json.dumps(balance_data, indent=4))
        # return

        # Commenting out the market order for now
        # Uncomment if needed to place a market order
        # total_nis = balance_data['AVAILABLE_NIS']
        # market_order_buy_response = await place_market_order(session, total_nis / 2, 'buy')
        # print("Market Buy Order Response:", json.dumps(market_order_buy_response, indent=4))

        # balance_data = await fetch_balances(session)
        # print("Initial Balances:", json.dumps(balance_data, indent=4))

        # get my orders
        my_orders = await get_my_orders(session)
        print("My Orders:", json.dumps(my_orders, indent=4))

        # Step 3: Cancel all the fetched orders (ask and bid)
        orders_to_cancel = []

        # Fetching ask orders
        for ask_order in my_orders.get("BtcNis", {}).get("ask", []):
            orders_to_cancel.append(ask_order["id"])

        # Fetching bid orders
        for bid_order in my_orders.get("BtcNis", {}).get("bid", []):
            orders_to_cancel.append(bid_order["id"])

        # Cancel all orders
        for order_id in orders_to_cancel:
            cancel_response = await cancel_order(session, order_id)
            print(f"Cancel Order {order_id} Response:", json.dumps(cancel_response, indent=4))

        # Step 4: Fetch balances after canceling the orders
        balance_after_cancel = await fetch_balances(session)
        print("Balances After Cancelling Orders:", json.dumps(balance_after_cancel, indent=4))
        return

        # # Define the wait time between orders
        # wait_time = 0.75  # seconds

        # # Last traded price for BtcNis
        # last_traded_price = 239751

        # # Spread multipliers for different orders
        # spread_multipliers = [0, 0.5, 1]

        # # Step 2: Place 3 buy and 3 sell limit orders
        # buy_orders = []
        # sell_orders = []
        # for i, multiplier in enumerate(spread_multipliers):
        #     # Calculate the limit prices
        #     buy_price = last_traded_price * (1 - (multiplier / 100))  # Spread down for buy orders
        #     sell_price = last_traded_price * (1 + (multiplier / 100))  # Spread up for sell orders

        #     # Place buy order
        #     buy_order_response = await place_limit_order(session, 0.00008, buy_price, 'buy')
        #     print(f"Buy Limit Order {i+1} Response:", json.dumps(buy_order_response, indent=4))
        #     if buy_order_response:
        #         buy_orders.append(buy_order_response['NewOrder']['id'])

        #     await asyncio.sleep(wait_time)  # Wait between placing orders

        #     # Place sell order
        #     sell_order_response = await place_limit_order(session, 0.00008, sell_price, 'sell')
        #     print(f"Sell Limit Order {i+1} Response:", json.dumps(sell_order_response, indent=4))
        #     if sell_order_response:
        #         sell_orders.append(sell_order_response['NewOrder']['id'])

        #     await asyncio.sleep(wait_time)

        # # Step 3: Fetch balances after placing the orders
        # balance_after_orders = await fetch_balances(session)
        # print("Balances After Placing Orders:", json.dumps(balance_after_orders, indent=4))

        # # Step 4: Fetch details and histories for buy and sell orders
        # for i, order_id in enumerate(buy_orders):
        #     buy_order_details = await get_order_by_id(session, order_id)
        #     print(f"Buy Order {order_id} Details:", json.dumps(buy_order_details, indent=4))

        #     buy_order_history = await get_order_history_by_id(session, order_id)
        #     print(f"Buy Order {order_id} History:", json.dumps(buy_order_history, indent=4))

        # for i, order_id in enumerate(sell_orders):
        #     sell_order_details = await get_order_by_id(session, order_id)
        #     print(f"Sell Order {order_id} Details:", json.dumps(sell_order_details, indent=4))

        #     sell_order_history = await get_order_history_by_id(session, order_id)
        #     print(f"Sell Order {order_id} History:", json.dumps(sell_order_history, indent=4))

        # # Step 6: Wait for a few seconds before canceling
        # await asyncio.sleep(5)

        # # Step 7: Cancel both the buy and sell limit orders
        # for i, order_id in enumerate(buy_orders):
        #     cancel_buy_order_response = await cancel_order(session, order_id)
        #     print(f"Cancel Buy Order {order_id} Response:", json.dumps(cancel_buy_order_response, indent=4))

        # for i, order_id in enumerate(sell_orders):
        #     cancel_sell_order_response = await cancel_order(session, order_id)
        #     print(f"Cancel Sell Order {order_id} Response:", json.dumps(cancel_sell_order_response, indent=4))

        # # Step 8: Fetch balances after canceling the orders
        # balance_after_cancelling = await fetch_balances(session)
        # print("Balances After Cancelling Orders:", json.dumps(balance_after_cancelling, indent=4))

        # Step 2: Place one limit order of 0.00016 amount
        last_traded_price = 239751  # Use the current last traded price

        # buy_price = last_traded_price * 0.99  # Slightly lower for limit buy order
        limit_order_response = await place_limit_order(session, 0.00016, last_traded_price, 'buy')
        print("Limit Order Response:", json.dumps(limit_order_response, indent=4))
        if limit_order_response:
            limit_order_id = limit_order_response['NewOrder']['id']

        await asyncio.sleep(0.75)

        # Step 3: Place two market orders (one buy and one sell)
        # Buy market order
        market_order_response_1 = await place_market_order(session, 0.00008, 'sell')
        print("Market Buy Order Response:", json.dumps(market_order_response_1, indent=4))

        await asyncio.sleep(0.75)

        # Sell market order
        market_order_response_2 = await place_market_order(session, 0.00008, 'sell')
        print("Market Sell Order Response:", json.dumps(market_order_response_2, indent=4))

        # Collect order IDs for market orders
        market_order_id_1 = market_order_response_1['NewOrder']['id'] if market_order_response_1 else None
        market_order_id_2 = market_order_response_2['NewOrder']['id'] if market_order_response_2 else None

        # Step 4: Fetch order details and order history for all orders
        order_ids = [limit_order_id, market_order_id_1, market_order_id_2]
        for order_id in order_ids:
            if order_id:
                # Fetch order details by ID
                order_details = await get_order_by_id(session, order_id)
                print(f"Order {order_id} Details:", json.dumps(order_details, indent=4))
                order_details = await get_order_by_id(session, order_id)
                print(f"Order {order_id} Details:", json.dumps(order_details, indent=4))
                order_details = await get_order_by_id(session, order_id)
                print(f"Order {order_id} Details:", json.dumps(order_details, indent=4))
                order_details = await get_order_by_id(session, order_id)
                print(f"Order {order_id} Details:", json.dumps(order_details, indent=4))

                # Fetch order history by ID
                order_history = await get_order_history_by_id(session, order_id)
                print(f"Order {order_id} History:", json.dumps(order_history, indent=4))
                order_history = await get_order_history_by_id(session, order_id)
                print(f"Order {order_id} History:", json.dumps(order_history, indent=4))
                order_history = await get_order_history_by_id(session, order_id)
                print(f"Order {order_id} History:", json.dumps(order_history, indent=4))
                order_history = await get_order_history_by_id(session, order_id)
                print(f"Order {order_id} History:", json.dumps(order_history, indent=4))

        # Step 5: Fetch balances after placing the orders
        balance_after_orders = await fetch_balances(session)
        print("Balances After Placing Orders:", json.dumps(balance_after_orders, indent=4))

        cancel_limit_order_response = await cancel_order(session, limit_order_id)
        print(f"Cancel Sell Order {order_id} Response:", json.dumps(cancel_limit_order_response, indent=4))
        cancel_limit_order_response = await cancel_order(session, limit_order_id)
        print(f"Cancel Sell Order {order_id} Response:", json.dumps(cancel_limit_order_response, indent=4))
        cancel_limit_order_response = await cancel_order(session, limit_order_id)
        print(f"Cancel Sell Order {order_id} Response:", json.dumps(cancel_limit_order_response, indent=4))
        cancel_limit_order_response = await cancel_order(session, limit_order_id)
        print(f"Cancel Sell Order {order_id} Response:", json.dumps(cancel_limit_order_response, indent=4))

        # Step 5: Fetch balances after placing the orders
        balance_after_orders = await fetch_balances(session)
        print("Balances After:", json.dumps(balance_after_orders, indent=4))
        balance_after_orders = await fetch_balances(session)
        print("Balances After:", json.dumps(balance_after_orders, indent=4))
        await asyncio.sleep(1)
        balance_after_orders = await fetch_balances(session)
        print("Balances After:", json.dumps(balance_after_orders, indent=4))


if __name__ == "__main__":
    asyncio.run(main())
