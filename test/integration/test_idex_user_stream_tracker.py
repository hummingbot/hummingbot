#!/usr/bin/env python
# import os
from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../")))

import asyncio
import logging
import unittest
# from decimal import Decimal
from urllib.parse import urljoin
from pprint import pformat
import aiohttp
from eth_account.signers.local import LocalAccount

# from typing import Optional

from hummingbot.connector.exchange.idex.idex_user_stream_tracker import IdexUserStreamTracker
from hummingbot.connector.exchange.idex.idex_exchange import IdexAuth, IdexExchange
# from hummingbot.connector.exchange.idex.idex_order_book_message import IdexOrderBookMessage

# from hummingbot.core.utils.async_utils import safe_ensure_future
# from hummingbot.connector.exchange.idex.idex_order_book_tracker import IdexOrderBookTracker
# from hummingbot.core.event.events import OrderType
from typing import Optional
import contextlib
from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    safe_gather,
)
from hummingbot.core.clock import Clock, ClockMode
from decimal import Decimal
import time
# from hummingbot.connector.exchange.idex.idex_utils import get_idex_rest_url, get_idex_ws_feed


logging.basicConfig(level=logging.DEBUG)


class IdexOrderBookTrackerUnitTest(unittest.TestCase):
    # order_book_tracker: Optional[IdexOrderBookTracker] = None
    IDEX_SECRET_KEY = "tkDey53dr1ZlyM2tzUAu82l+nhgzxCJl"
    IDEX_API_KEY = "889fe7dd-ea60-4bf4-86f8-4eec39146510"
    IDEX_PRIVATE_KEY = "0227070369c04f55c66988ee3b272f8ae297cf7967ca7bad6d2f71f72072e18d"  # compromised

    # IDEX_API_KEY = ""
    # IDEX_SECRET_KEY = ""
    # IDEX_PRIVATE_KEY = "not this time! ;P"  # don't commit me please

    user_stream_tracker: Optional[IdexUserStreamTracker] = None

    market: IdexExchange
    stack: contextlib.ExitStack

    @classmethod
    def setUpClass(cls):
        IDEX_API_KEY = "tkDey53dr1ZlyM2tzUAu82l+nhgzxCJl"
        IDEX_SECRET_KEY = "889fe7dd-ea60-4bf4-86f8-4eec39146510"
        IDEX_PRIVATE_KEY = "0227070369c04f55c66988ee3b272f8ae297cf7967ca7bad6d2f71f72072e18d"  # don't commit me please
        #
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.coinbase_pro_auth = IdexAuth(IDEX_API_KEY, IDEX_SECRET_KEY, IDEX_PRIVATE_KEY)
        cls.trading_pairs = ["DIL-ETH"]
        cls.user_stream_tracker: IdexUserStreamTracker = IdexUserStreamTracker(idex_auth=cls.idex_auth, trading_pairs=cls.trading_pairs)
        cls.user_stream_tracker_task: asyncio.Task = safe_ensure_future(cls.user_stream_tracker.start())

        cls.clock: Clock = Clock(ClockMode.REALTIME)
        cls.market: IdexExchange = IdexExchange(
            IDEX_API_KEY,
            IDEX_SECRET_KEY,
            IDEX_PRIVATE_KEY,
            trading_pairs=cls.trading_pairs
        )
        print("Initializing Idex market... this will take about a minute.")
        cls.clock.add_iterator(cls.market)
        cls.stack = contextlib.ExitStack()
        cls._clock = cls.stack.enter_context(cls.clock)
        cls.ev_loop.run_until_complete(cls.wait_til_ready())
        print("Ready.")

    @classmethod
    async def wait_til_ready(cls):
        while True:
            now = time.time()
            next_iteration = now // 1.0 + 1
            if cls.market.ready:
                break
            else:
                await cls._clock.run_til(next_iteration)
            await asyncio.sleep(1.0)

    async def run_parallel_async(self, *tasks):
        future: asyncio.Future = safe_ensure_future(safe_gather(*tasks))
        while not future.done():
            now = time.time()
            next_iteration = now // 1.0 + 1
            await self.clock.run_til(next_iteration)
        return future.result()

    def run_parallel(self, *tasks):
        return self.ev_loop.run_until_complete(self.run_parallel_async(*tasks))

    def test_limit_order_cancelled(self):
        """
        This test should be run after the developer has implemented the limit buy and cancel
        in the corresponding market class
        """
        # self.assertGreater(self.market.get_balance("ETH"), Decimal("0.1"))
        trading_pair = self.trading_pairs[0]
        amount: Decimal = Decimal("0.02")
        quantized_amount: Decimal = self.market.quantize_order_amount(trading_pair, amount)

        # NOTE: coinbase grabs 80% of mkt price, I figure if we cancel it it doesn't really matter how small it is
        bid_price: Decimal = "0.5"  # This is for the sandbox/rinkeby DIL-ETH
        quantize_bid_price: Decimal = self.market.quantize_order_price(trading_pair, bid_price)

        client_order_id = self.buy_limit_on_book(quantized_amount, quantize_bid_price)

        self.ev_loop.run_until_complete(asyncio.sleep(5.0))
        [open_message] = self.run_parallel(self.user_stream_tracker.user_stream.get())

        # print(open_message)
        # TODO:elliott-- orderbook message should be tailored to the below, or use "example" above and match keys
        # self.assertTrue(isinstance(open_message, CoinbaseProOrderBookMessage))
        # self.assertEqual(open_message.trading_pair, trading_pair)
        # self.assertEqual(open_message.content["type"], "open")
        # self.assertEqual(open_message.content["side"], "buy")
        # self.assertEqual(open_message.content["product_id"], trading_pair)
        # self.assertEqual(Decimal(open_message.content["price"]), quantize_bid_price)
        # self.assertEqual(Decimal(open_message.content["remaining_size"]), quantized_amount)

        self.run_parallel(asyncio.sleep(5.0))
        # TODO:elliott-- make cancel a thing
        self.market.cancel(trading_pair, client_order_id)

        self.ev_loop.run_until_complete(asyncio.sleep(5.0))
        [done_message] = self.run_parallel(self.user_stream_tracker.user_stream.get())

        print("done")
        print(done_message)
        # TODO: uncomment and adapt to idex done message return
        # self.assertEqual(done_message.trading_pair, trading_pair)
        # self.assertEqual(done_message.content["type"], "done")
        # self.assertEqual(done_message.content["side"], "buy")
        # self.assertEqual(done_message.content["product_id"], trading_pair)
        # self.assertEqual(Decimal(done_message.content["price"]), quantize_bid_price)
        # self.assertEqual(Decimal(done_message.content["remaining_size"]), quantized_amount)
        # self.assertEqual(done_message.content["reason"], "canceled")

    @unittest.skip
    def test_limit_order_filled(self):
        """
        This test should be run after the developer has implemented the limit buy in the corresponding market class
        """
        # probably unnecessary
        # self.assertGreater(self.market.get_balance("ETH"), Decimal("0.1"))
        # trading_pair = self.trading_pairs[0]
        # amount: Decimal = Decimal("0.02")
        # quantized_amount: Decimal = self.market.quantize_order_amount(trading_pair, amount)

        # current_bid_price: Decimal = self.market.get_order_book(trading_pair)._best_bid
        # print("current bid: ")
        # print(current_bid_price)
        # NOTE: coinbase does a limit buy that will fill (1.05 of market).. market order is easier.

        # self.buy_limit_on_book(quantized_amount, quantize_bid_price)
        quantity = "0.5"
        self.market_buy(quantity)

        self.ev_loop.run_until_complete(asyncio.sleep(5.0))
        [message_1, message_2] = self.run_parallel(self.user_stream_tracker.user_stream.get(),
                                                   self.user_stream_tracker.user_stream.get())
        # TODO: replace coinbase messages w/ idex
        print(message_1, message_2)
        # self.assertTrue(isinstance(message_1, CoinbaseProOrderBookMessage))
        # self.assertTrue(isinstance(message_2, CoinbaseProOrderBookMessage))
        if message_1.content["type"] == "done":
            done_message = message_1
            match_message = message_2
        else:
            done_message = message_2
            match_message = message_1

        print(done_message)
        # self.assertEqual(done_message.trading_pair, trading_pair)
        # self.assertEqual(done_message.content["type"], "done")
        # self.assertEqual(done_message.content["side"], "buy")
        # self.assertEqual(done_message.content["product_id"], trading_pair)
        # self.assertEqual(Decimal(done_message.content["price"]), quantize_bid_price)
        # self.assertEqual(Decimal(done_message.content["remaining_size"]), Decimal(0.0))
        # self.assertEqual(done_message.content["reason"], "filled")

        print(match_message)
        # self.assertEqual(match_message.trading_pair, trading_pair)
        # self.assertEqual(match_message.content["type"], "match")
        # self.assertEqual(match_message.content["side"], "sell")
        # self.assertEqual(match_message.content["product_id"], trading_pair)
        # self.assertLessEqual(Decimal(match_message.content["price"]), quantize_bid_price)
        # self.assertEqual(Decimal(match_message.content["size"]), quantized_amount)

    @unittest.skip
    def test_user_stream_manually(self):
        """
        This test should be run before market functions like buy and sell are implemented.
        Developer needs to manually trigger those actions in order for the messages to show up in the user stream.
        """
        self.ev_loop.run_until_complete(asyncio.sleep(30.0))
        print(self.user_stream_tracker.user_stream)

    # first_order = OrderType.LIMIT?
    base_url = 'https://api-sandbox-eth.idex.io/'  # rest url for sandbox (rinkeby) ETH chain
    idex_auth = IdexAuth(
        api_key=IDEX_API_KEY,
        secret_key=IDEX_SECRET_KEY,
        wallet_private_key=IDEX_PRIVATE_KEY,
        # trading_pairs=["DIL-ETH", "PIP-ETH", "CUR-ETH"],
        # trading_required=True,
    )

    example_response_balances = [
        {
            'asset': 'ETH',
            'availableForTrade': '2.00000000',
            'locked': '0.00000000',
            'quantity': '2.00000000',
            'usdValue': '3687.60'
        },
    ]

    def test_user_balance_access(self):
        """
        Test access to user balance (HMAC authentication): GET /v1/balances
        Url parameters include the wallet public address.
        This test may fail if the user have not associated the ethereum wallet address with their account yet.
        See `test_associate_wallet` for how to associate the wallet with the account/api_key.
        """
        # base_url = 'https://api-sandbox-eth.idex.io/'  # rest url for sandbox (rinkeby) ETH chain
        path = '/v1/balances'
        url = urljoin(self.base_url, path)

        # the ethereum private key can be passed as an argument on IdexAuth() creation,
        # or can be entered an any time during the lifetime of the auth object
        self.idex_auth.init_wallet(self.IDEX_PRIVATE_KEY)

        nonce: str = self.idex_auth.generate_nonce()  # regenerate nonce before each request
        wallet: LocalAccount = self.idex_auth.wallet

        params = {
            'nonce': nonce,
            'wallet': wallet.address,  # notice: user must have associated wallet with api_key before
            # 'asset': [],  # Optional. Array of asset symbols to query for balance information
        }

        auth_dict = self.idex_auth.generate_auth_dict(http_method='GET', url=url, params=params)

        status, balances = self.ev_loop.run_until_complete(
            self.rest_get(auth_dict['url'], headers=auth_dict['headers'])
        )
        print('balances:\n', pformat(balances))
        self.assertEqual(status, 200)
        self.assertIsInstance(balances, list)
        for b_item in balances:
            self.assertIsInstance(b_item, dict)
            self.assertEqual(set(b_item.keys()), set(self.example_response_balances[0].keys()))

    example_response_limit_order_partially_filled = {
        'cumulativeQuoteQuantity': '0.00000000',
        'executedQuantity': '0.00000000',
        'market': 'DIL-ETH',
        'orderId': 'b0b8c3a0-88bc-11eb-8929-772a825d8ec1',
        'originalQuantity': '5.00000000',
        'price': '1000.00000000',
        'selfTradePrevention': 'dc',
        'side': 'sell',
        'status': 'open',
        'time': 1616162956507,
        'timeInForce': 'gtc',
        'type': 'limit',
        'wallet': '0x96525939c7cA0D73aDe68B54510970B97CA020c9'
    }

    example_response_market_order_partially_filled = {
        'avgExecutionPrice': '0.10146579',
        'cumulativeQuoteQuantity': '0.67649341',
        'executedQuantity': '6.66720651',
        'fills': [
            {
                'fee': '0.00452051',
                'feeAsset': 'DIL',
                'fillId': '44b8e980-7bff-36a0-9d84-3100b522aa62',
                'gas': '0.00840155',
                'liquidity': 'taker',
                'makerSide': 'sell',
                'price': '0.10129292',
                'quantity': '2.26025738',
                'quoteQuantity': '0.22894807',
                'sequence': 20328,
                'time': 1615526924128,
                'txId': None,
                'txStatus': 'pending',
            },
            {
                'fee': '0.00881389',
                'feeAsset': 'DIL',
                'fillId': 'b62b74c1-c14e-3aa4-9488-7fe623bd2a3a',
                'gas': '0.00840155',
                'liquidity': 'taker',
                'makerSide': 'sell',
                'price': '0.10155446',
                'quantity': '4.40694913',
                'quoteQuantity': '0.44754534',
                'sequence': 20329,
                'time': 1615526924128,
                'txId': None,
                'txStatus': 'pending',
            },
        ],
        'market': 'DIL-ETH',
        'orderId': 'cfe1aef0-82f3-11eb-97a3-d3cdd9c6cba4',
        'originalQuoteQuantity': '100.00000000',
        'selfTradePrevention': 'dc',
        'side': 'buy',
        'status': 'canceled',
        'time': 1615526924128,
        'type': 'market',
        'wallet': '0x3e4074B1C4D3081AA6Fb44B7503d71CdedDEf51b'
    }

    # def market_buy(self, quoteOrderQuantity):
    #     """
    #     Test is used to create a market buy order for Dil, therefore buying ETH
    #     This is used to see a filled order
    #     """
    #     path = '/v1/orders'
    #     url = urljoin(self.base_url, path)
    #
    #     self.idex_auth.generate_nonce()  # re create nonce before each request
    #
    #     order = {
    #         'nonce': self.idex_auth.get_nonce_str(),  # example: "9436afa0-9ee6-11ea-8a53-71994564322f",
    #         'wallet': self.idex_auth.get_wallet_address(),  # example: "0xA71C4aeeAabBBB8D2910F41C2ca3964b81F7310d"
    #         'market': 'DIL-ETH',
    #         'type': 1,  # enum value for market orders
    #         'side': 0,  # enum value for buy
    #         'quantity': quantized_amount,
    #         'price': quantize_bid_price,
    #     }
    #
    #     signature_parameters = (  # see idex doc: https://docs.idex.io/#associate-wallet
    #         ('uint8', 1),  # 0 - The signature hash version is 1 for Ethereum, 2 for BSC
    #
    #         ('uint128', self.idex_auth.get_nonce_int()),  # 1 - Nonce
    #         ('address', order['wallet']),  # 2 - Signing wallet address
    #         ('string', order['market']),  # 3 - Market symbol (e.g. ETH-USDC)
    #         ('uint8', order['type']),  # 4 - Order type enum value
    #         ('uint8', order['side']),  # 5 - Order side enum value
    #
    #         ('string', order['quoteOrderQuantity']),  # 6 - Order quantity in base or quote terms
    #         ('bool', True),  # 7 - false if order quantity in base terms; true if order quantity in quote terms
    #         ('string', ''),  # 8 - Order price or empty string if market order
    #         ('string', ''),  # 9 - Order stop price or empty string if not a stop loss or take profit order
    #
    #         ('string', ''),  # 10 - Client order id or empty string
    #         ('uint8', 0),  # 11 - Order time in force enum value
    #         ('uint8', 0),  # 12 - Order self-trade prevention enum value
    #         ('uint64', 0),  # 13 - Unused, always should be 0
    #     )
    #     wallet_signature = self.idex_auth.wallet_sign(signature_parameters)
    #
    #     payload = {
    #         "parameters": {
    #             'nonce': order['nonce'],  # example: "9436afa0-9ee6-11ea-8a53-71994564322f",
    #             'wallet': order['wallet'],  # example: "0xA71C4aeeAabBBB8D2910F41C2ca3964b81F7310d"
    #             "market": order['market'],
    #             "type": "market",  # todo: declare enums
    #             "side": "buy",
    #             "quoteOrderQuantity": order['quoteOrderQuantity']
    #         },
    #         'signature': wallet_signature,
    #     }
    #     # TODO: Finish converting this from buy limit to buy market and test functionality
    #     # TODO: use clientIDs, so that coinbase cribbed code can identify orders
    #     # TODO: self.buy_limit_on_book(quantized_amount, quantize_bid_price) <-- call should look like that
    #     print('payload:\n', pformat(payload))
    #
    #     auth_dict = self.idex_auth.generate_auth_dict(http_method='POST', url=url, body=payload)
    #
    #     print('auth_dict:\n', pformat(auth_dict))
    #
    #     status, response = self.ev_loop.run_until_complete(
    #         self.rest_post(auth_dict['url'], payload, headers=auth_dict['headers'])
    #     )
    #     print('response:\n', pformat(response))
    #
    #     if status == 200:
    #         # check order was correctly placed (if partially filled you get status: cancelled)
    #         self.assertIsInstance(response, dict)
    #         self.assertEqual(set(response.keys()), set(self.example_response_market_order_partially_filled))
    #         # note: curious behavior observed: even if account has insufficient funds, an order can sometimes be placed
    #         # and you get get response back which lacks fields: avgExecutionPrice and fills
    #     elif status == 402:  # HTTP 402: Payment Required. Error due to lack of funds
    #         self.assertIsInstance(response, dict) and self.assertEqual(set(response.keys()), {'code', 'message'})
    #         self.assertEqual('INSUFFICIENT_FUNDS', response['code'])
    #         self.fail(msg="Test account has insufficient funds to run the test")  # make test fail for awareness
    #     else:
    #         self.assertEqual(status, 200, msg=f'Unexpected error when creating order. Response: {response}')

    def buy_limit_on_book(self, quantized_amount, quantize_bid_price):
        """
        Test is used to create a sell order for ETH, therefore buying DIL
        Tests create order to check trade level authentication (HMAC Header + ETH Wallet signature)
        with request: POST /v1/orders
        """
        path = '/v1/orders'
        url = urljoin(self.base_url, path)

        self.idex_auth.generate_nonce()  # re create nonce before each request

        order = {
            'nonce': self.idex_auth.get_nonce_str(),  # example: "9436afa0-9ee6-11ea-8a53-71994564322f",
            'wallet': self.idex_auth.get_wallet_address(),  # example: "0xA71C4aeeAabBBB8D2910F41C2ca3964b81F7310d"
            'market': 'DIL-ETH',
            'type': 1,  # enum value for market orders
            'side': 0,  # enum value for buy
            'quantity': quantized_amount,
            'price': quantize_bid_price,
        }

        signature_parameters = (  # see idex doc: https://docs.idex.io/#associate-wallet
            ('uint8', 1),  # 0 - The signature hash version is 1 for Ethereum, 2 for BSC

            ('uint128', self.idex_auth.get_nonce_int()),  # 1 - Nonce
            ('address', order['wallet']),  # 2 - Signing wallet address
            ('string', order['market']),  # 3 - Market symbol (e.g. ETH-USDC)
            ('uint8', order['type']),  # 4 - Order type enum value
            ('uint8', order['side']),  # 5 - Order side enum value

            ('string', order['quoteOrderQuantity']),  # 6 - Order quantity in base or quote terms
            ('bool', True),  # 7 - false if order quantity in base terms; true if order quantity in quote terms
            ('string', ''),  # 8 - Order price or empty string if market order
            ('string', ''),  # 9 - Order stop price or empty string if not a stop loss or take profit order

            ('string', ''),  # 10 - Client order id or empty string
            ('uint8', 0),  # 11 - Order time in force enum value
            ('uint8', 0),  # 12 - Order self-trade prevention enum value
            ('uint64', 0),  # 13 - Unused, always should be 0
        )
        wallet_signature = self.idex_auth.wallet_sign(signature_parameters)

        payload = {
            "parameters": {
                'nonce': order['nonce'],  # example: "9436afa0-9ee6-11ea-8a53-71994564322f",
                'wallet': order['wallet'],  # example: "0xA71C4aeeAabBBB8D2910F41C2ca3964b81F7310d"
                "market": order['market'],
                "type": "market",  # todo: declare enums
                "side": "buy",
                "quoteOrderQuantity": order['quoteOrderQuantity']
            },
            'signature': wallet_signature,
        }
        # TODO: Finish converting this from buy limit to buy market and test functionality
        # TODO: use clientIDs, so that coinbase cribbed code can identify orders
        # TODO: self.buy_limit_on_book(quantized_amount, quantize_bid_price) <-- call should look like that
        print('payload:\n', pformat(payload))

        auth_dict = self.idex_auth.generate_auth_dict(http_method='POST', url=url, body=payload)

        print('auth_dict:\n', pformat(auth_dict))

        status, response = self.ev_loop.run_until_complete(
            self.rest_post(auth_dict['url'], payload, headers=auth_dict['headers'])
        )
        print('response:\n', pformat(response))

        if status == 200:
            # check order was correctly placed (if partially filled you get status: cancelled)
            self.assertIsInstance(response, dict)
            self.assertEqual(set(response.keys()), set(self.example_response_market_order_partially_filled))
            # note: curious behavior observed: even if account has insufficient funds, an order can sometimes be placed
            # and you get get response back which lacks fields: avgExecutionPrice and fills
        elif status == 402:  # HTTP 402: Payment Required. Error due to lack of funds
            self.assertIsInstance(response, dict) and self.assertEqual(set(response.keys()), {'code', 'message'})
            self.assertEqual('INSUFFICIENT_FUNDS', response['code'])
            self.fail(msg="Test account has insufficient funds to run the test")  # make test fail for awareness
        else:
            self.assertEqual(status, 200, msg=f'Unexpected error when creating order. Response: {response}')

    def create_test_sell_dil_order_limit(self):
        """
        Test is used to create a sell order for DIL, therefore buying ETH
        Tests create order to check trade level authentication (HMAC Header + ETH Wallet signature)
        with request: POST /v1/orders
        """
        path = '/v1/orders'
        url = urljoin(self.base_url, path)

        self.idex_auth.generate_nonce()  # re create nonce before each request

        order = {
            'nonce': self.idex_auth.get_nonce_str(),  # example: "9436afa0-9ee6-11ea-8a53-71994564322f",
            'wallet': self.idex_auth.get_wallet_address(),  # example: "0xA71C4aeeAabBBB8D2910F41C2ca3964b81F7310d"
            'market': 'DIL-ETH',
            'type': 1,  # enum value for mkt
            'side': 1,  # enum value for sell
            'quantity': '5.00000000',
            'price': '1000.00000000',
            # "stopPrice": "10095.00000000"
        }

        signature_parameters = (  # see idex doc: https://docs.idex.io/#associate-wallet
            ('uint8', 1),  # 0 - The signature hash version is 1 for Ethereum, 2 for BSC

            ('uint128', self.idex_auth.get_nonce_int()),  # 1 - Nonce
            ('address', order['wallet']),  # 2 - Signing wallet address
            ('string', order['market']),  # 3 - Market symbol (e.g. ETH-USDC)
            ('uint8', order['type']),  # 4 - Order type enum value
            ('uint8', order['side']),  # 5 - Order side enum value

            ('string', order['quantity']),  # 6 - Order quantity in base (quoteOfQuantity for mkt/quote) terms
            ('bool', False),  # 7 - false IF order quantity in base terms (limit); true if qoQ in quote terms (mkt)
            ('string', order['price']),  # 8 - Order price or empty string if market order
            ('string', ''),  # 9 - Order stop price or empty string if not a stop loss or take profit order

            ('string', ''),  # 10 - Client order id or empty string
            ('uint8', 0),  # 11 - Order time in force enum value
            ('uint8', 0),  # 12 - Order self-trade prevention enum value
            ('uint64', 0),  # 13 - Unused, always should be 0
        )

        wallet_signature = self.idex_auth.wallet_sign(signature_parameters)

        payload = {
            "parameters": {
                'nonce': order['nonce'],  # example: "9436afa0-9ee6-11ea-8a53-71994564322f",
                'wallet': order['wallet'],  # example: "0xA71C4aeeAabBBB8D2910F41C2ca3964b81F7310d"
                "market": order['market'],
                "type": "limit",  # todo: declare enums
                "side": "sell",
                "quantity": order['quantity'],
                "price": order['price'],
                # "stopPrice": order['stopPrice'],
            },
            'signature': wallet_signature,
        }

        print('payload:\n', pformat(payload))

        auth_dict = self.idex_auth.generate_auth_dict(http_method='POST', url=url, body=payload)

        print('auth_dict:\n', pformat(auth_dict))

        status, response = self.ev_loop.run_until_complete(
            self.rest_post(auth_dict['url'], payload, headers=auth_dict['headers'])
        )
        print('response:\n', pformat(response))

        if status == 200:
            # check order was correctly placed (if partially filled you get status: cancelled)
            self.assertIsInstance(response, dict)
            self.assertEqual(set(response.keys()), set(self.example_response_limit_order_partially_filled))
            # note: curious behavior observed: even if account has insufficient funds, an order can sometimes be placed
            # and you get get response back which lacks fields: avgExecutionPrice and fills
        elif status == 402:  # HTTP 402: Payment Required. Error due to lack of funds
            self.assertIsInstance(response, dict) and self.assertEqual(set(response.keys()), {'code', 'message'})
            self.assertEqual('INSUFFICIENT_FUNDS', response['code'])
            self.fail(msg="Test account has insufficient funds to run the test")  # make test fail for awareness
        else:
            self.assertEqual(status, 200, msg=f'Unexpected error when creating order. Response: {response}')

    def cancel_order_with_id(self, order_id):
        print("cancel")

    async def rest_post(self, url, payload, headers=None, params=None):
        async with aiohttp.ClientSession() as client:
            async with client.post(url, json=payload, headers=headers, params=params) as resp:
                # assert resp.status == 200
                print(resp.status)
                body = await resp.json()
                return resp.status, body

    async def rest_get(self, url, headers=None, params=None):
        async with aiohttp.ClientSession() as client:
            async with client.get(url, headers=headers, params=params) as resp:
                # add: encoded=True arg to client.get() to avoid double urlencode (URL canonicalization) ?
                # assert resp.status == 200
                print(resp.status)
                body = await resp.json()
                return resp.status, body

    # @classmethod
    # def setUpClass(cls):
    #     print("setup")

    #     cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
    #     cls.user_stream_tracker: IdexUserStreamTracker = IdexUserStreamTracker(
    #         # idex_auth=IdexAuth(
    #         #     api_key=os.getenv("IDEX_API_KEY"),
    #         #     secret_key=os.getenv("IDEX_SECRET_KEY"),
    #         #     wallet_private_key=os.getenv("IDEX_PRIVATE_KEY"),
    #         # )
    #         idex_auth=IdexAuth(
    #             api_key=IDEX_API_KEY,
    #             secret_key=IDEX_SECRET_KEY,
    #             wallet_private_key=IDEX_PRIVATE_KEY,
    #             # trading_pairs=["DIL-ETH", "PIP-ETH", "CUR-ETH"],
    #             # trading_required=True,
    #         )
    #     )

        # cls.market: IdexExchange = IdexExchange(self.IDEX_API_KEY,
        #                                         self.IDEX_SECRET_KEY,
        #                                         self.IDEX_PRIVATE_KEY,
        #                                         ["DIL-ETH", "PIP-ETH", "CUR-ETH"],
        #                                         True
        #                                         )

    # @unittest.skip
    # def test_user_stream(self):
    #     print("streaming")
    #     # Wait process some msgs.
    #     self.ev_loop.run_until_complete(asyncio.sleep(10.0))
    #     self.create_test_sell_dil_order_limit()
    #     print("-----------------------------------------")
    #     print(self.user_stream_tracker.user_stream)
    #     print(self.user_stream_tracker.last_recv_time)
    #     print("-----------------------------------------")

    # def test_user_stream_manually(self):
    #     """
    #     This test should be run before market functions like buy and sell are implemented.
    #     Developer needs to manually trigger those actions in order for the messages to show up in the user stream.
    #     """
    #     # self.ev_loop.run_until_complete(asyncio.sleep(10.0))
    #     # print(self.user_stream_tracker.user_stream)
    #     # print("Make an order then see if it shows up")
    #     # print("goals: see if balances go through, create a second order, cancel an order")
    #     # self.test_user_stream()
    #     # self.create_test_sell_dil_order_limit()
    #     # self.test_user_balance_access()
    #     # self.create_test_buy_dil_order()
    #     # self.create_test_sell_dil_order_limit()
    #
    #     # self.test_user_balance_access()

# def main():  # idex
#     print("MAIN!!!!!!!!!!!!!!!")
#     unittest.main()
#
#
# if __name__ == "__main__":  # idex
#     main()


def main():
    logging.basicConfig(level=logging.INFO)
    unittest.main()


if __name__ == "__main__":
    main()
