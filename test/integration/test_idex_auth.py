#!/usr/bin/env python

from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../")))

import logging
import unittest

import asyncio
import uuid

from pprint import pformat
from urllib.parse import urljoin

import aiohttp
from eth_account.signers.local import LocalAccount

from hummingbot.connector.exchange.idex.idex_auth import IdexAuth

import conf


"""
In order to run the integration test please set environment variables with the API key, secret and ETH Wallet.
Example in bash (these are not real api key and address, substitute your own):

export IDEX_API_KEY='d88c5070-42ea-435f-ba26-8cb82064a972'
export IDEX_API_SECRET_KEY='pLrUpy53o8enXTAHkOqsH8pLpQVMQ47p'
export IDEX_WALLET_PRIVATE_KEY='ad10037142dc378b3f004bbb4803e24984b8d92969ec9407efb56a0135661576'
export IDEX_CONTRACT_BLOCKCHAIN='ETH'
"""


IDEX_API_KEY = ''
IDEX_API_SECRET_KEY = ''
IDEX_WALLET_PRIVATE_KEY = ''
IDEX_CONTRACT_BLOCKCHAIN = ''

BASE_URL = 'https://api-sandbox-eth.idex.io/'  # rest url for sandbox (rinkeby) ETH chain


def api_keys_provided():
    return IDEX_API_KEY and IDEX_API_SECRET_KEY


def eth_wallet_provided():
    return IDEX_WALLET_PRIVATE_KEY


# load config from Hummingbot's central debug conf
# Values can be overridden by env variables (in uppercase). Example: export IDEX_WALLET_PRIVATE_KEY="1234567"
if not api_keys_provided():
    IDEX_API_KEY = getattr(conf, 'idex_api_key')
    IDEX_API_SECRET_KEY = getattr(conf, 'idex_api_secret_key')
    IDEX_WALLET_PRIVATE_KEY = getattr(conf, 'idex_wallet_private_key')
    IDEX_CONTRACT_BLOCKCHAIN = getattr(conf, 'idex_contract_blockchain', 'ETH')


class IdexAuthUnitTest(unittest.TestCase):

    def test_get_signature(self):
        wallet_private_key = "0x3952043cbb4217a5cf45e6518f40bfce245c6d8b227039c4102ab8a09dd9dbd8"
        auth = IdexAuth(api_key="key_id", secret_key="key_secret", wallet_private_key=wallet_private_key)
        result = auth.generate_auth_dict(
            http_method="get",
            url="https://url.com/",
            params={"foo": "bar", "nonce": "2c1b41ae-0eeb-11eb-971f-0242ac110002"}
        )
        self.assertEqual(result["headers"]["IDEX-API-Key"], "key_id")

        self.assertEqual(
            result["headers"]["IDEX-HMAC-Signature"],
            "32d603e2854a6d13c9b53b9abc612280871263ec6f0e5b64bc3e44502f4a9bbc"
        )
        self.assertIn("nonce", result["url"])

    @unittest.skip('deprecated')
    def test_uint128_integration(self):
        for item in [
            "0x46c588f0-1f69-11eb-9714-fb733e326f68",
            "46c588f0-1f69-11eb-9714-fb733e326f68",
            "0x46c588f01f6911eb9714fb733e326f68"
        ]:
            uint128 = IdexAuth.hex_to_uint128(item)  # todo: deprecated
            self.assertEqual(uint128, 0x46c588f01f6911eb9714fb733e326f68)

    @unittest.skip('deprecated')
    def test_sign_message_string(self):
        wallet_private_key = "0x3952043cbb4217a5cf45e6518f40bfce245c6d8b227039c4102ab8a09dd9dbd8"
        self._idex_auth = IdexAuth(api_key="key_id", secret_key="key_secret", wallet_private_key=wallet_private_key)
        orderVersion = 1
        market = "DIL-ETH"
        typeEnum = 0

        nonce = "91766796-4531-11eb-9669-30d16bd1b425"
        walletBytes = self._idex_auth.get_wallet_bytes()
        price = "0.20000000"
        sideEnum = 0
        amountEnum = 0  # base quantity
        amountString = "1.00000000"
        timeInForceEnum = 0
        selfTradePreventionEnum = 0

        byteArray = [  # todo: deprecation warning
            IdexAuth.number_to_be(orderVersion, 1),
            bytes(nonce, 'utf-8'),
            IdexAuth.base16_to_binary(walletBytes),
            IdexAuth.encode(market),
            IdexAuth.number_to_be(typeEnum, 1),
            IdexAuth.number_to_be(sideEnum, 1),
            IdexAuth.encode(amountString),
            IdexAuth.number_to_be(amountEnum, 1),
            IdexAuth.encode(price),
            IdexAuth.encode(''),  # stopPrice
            IdexAuth.encode("abc123"),  # clientOrderId
            IdexAuth.number_to_be(timeInForceEnum, 1),
            IdexAuth.number_to_be(selfTradePreventionEnum, 1),
            IdexAuth.number_to_be(0, 8),  # unused
        ]

        binary = IdexAuth.binary_concat_array(byteArray)
        hash = IdexAuth.hash(binary, 'keccak', 'hex')  # todo: deprecation warning
        # todo: deprecation warning
        signature = self._idex_auth.sign_message_string(hash, IdexAuth.binary_to_base16(self._idex_auth.new_wallet_object(private_key=wallet_private_key).key))
        self.assertEqual(
            signature,
            "0xec305ed5ccde1789956eaec99dcac61955fcbef79e443535f0bd1485de1d2fe5"
            "34c7287bb6cb3e2ae6c45490843dfec9b558437cd8aca32a7e1aa03f617caad21c"
        )

    def test_wallet_signature(self):
        wallet_private_key = '0xbae6890011b64ee26ee282692c8eef07330fd8ac101d2ae6cfa6acd30f940d01'

        idex_auth = IdexAuth(api_key='api-key-1', secret_key='api-secret-1')
        idex_auth.init_wallet(wallet_private_key)

        # set nonce to fixed value, this is not necessary in normal use
        nonce_str = "cf7989e0-2030-11eb-8473-f1ca5eaaaff1"
        idex_auth._nonce = uuid.UUID(nonce_str)

        signature_parameters = (
            ("uint128", idex_auth.get_nonce_int()),
            ("address", idex_auth.get_wallet_address()),
        )
        wallet_signature = idex_auth.wallet_sign(signature_parameters)

        self.assertEqual(
            wallet_signature,
            "0x42c474e4d58070c9be966ab925d0370b8e5ff4c5fd9ab623382b15262de2956e"
            "02e0a11b721edc26896134fd87fec71dd5e0cb6ada7ad2d5b004ac8dc32eb8071c"
        )

    def test_post_signature(self):
        auth = IdexAuth(api_key="key_id", secret_key="key_secret", wallet_private_key="0x3952043cbb4217a5cf45e6518f40bfce245c6d8b227039c4102ab8a09dd9dbd8")
        result = auth.generate_auth_dict(
            http_method="post",
            url="https://url.com/",
            body={
                "parameters": {
                    "foo": "bar",
                    "nonce": "2c1b41ae-0eeb-11eb-971f-0242ac110002"
                }
            }
        )
        self.assertEqual(result["headers"]["IDEX-API-Key"], "key_id")
        self.assertEqual(
            result["headers"]["IDEX-HMAC-Signature"],
            "24efc46758e2bd21d9ce8589b0c247ff9d34d8a1df6e06d9c8837ef45f471346"
        )
        self.assertIn("nonce", result["body"])


class TestIdexAuthIntegration(unittest.TestCase):

    # move to FixtureIdex ?
    example_response_user_detail = {
        'cancelEnabled': True,
        'depositEnabled': True,
        'kycTier': 2,
        'makerFeeRate': '0.001',
        'orderEnabled': True,
        'takerFeeRate': '0.002',
        'totalPortfolioValueUsd': '3623.60',
        'withdrawEnabled': True,
        'withdrawalLimit': 'unlimited',
        'withdrawalRemaining': 'unlimited'
    }

    example_response_balances = [
        {
            'asset': 'ETH',
            'availableForTrade': '2.00000000',
            'locked': '0.00000000',
            'quantity': '2.00000000',
            'usdValue': '3687.60'
        },
    ]

    example_response_associate_wallet = {
        'address': '0x3e4074B1C4D3081AA6Fb44B7503d71CdedDEf51b',
        'time': 1615427975803,
        'totalPortfolioValueUsd': '3683.00'
    }

    example_response_markets = [
        {
            'baseAsset': 'DIL',
            'baseAssetPrecision': 8,
            'market': 'DIL-ETH',
            'quoteAsset': 'ETH',
            'quoteAssetPrecision': 8,
            'status': 'active'
        },
    ]

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

    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.base_url = BASE_URL
        # you can inject values into conf by setting env variables with these names (in uppercase)
        cls.api_key = IDEX_API_KEY                          # conf.idex_api_key
        cls.secret_key = IDEX_API_SECRET_KEY                # conf.idex_api_secret_key
        cls.wallet_private_key = IDEX_WALLET_PRIVATE_KEY    # conf.idex_wallet_private_key
        cls.blockchain = IDEX_CONTRACT_BLOCKCHAIN           # conf.idex_contract_blockchain
        cls.idex_auth = IdexAuth(
            api_key=cls.api_key, secret_key=cls.secret_key, wallet_private_key=cls.wallet_private_key,
        )

    async def rest_get(self, url, headers=None, params=None):
        async with aiohttp.ClientSession() as client:
            async with client.get(url, headers=headers, params=params) as resp:
                # add: encoded=True arg to client.get() to avoid double urlencode (URL canonicalization) ?
                # assert resp.status == 200
                print(resp.status)
                body = await resp.json()
                return resp.status, body

    async def rest_post(self, url, payload, headers=None, params=None):
        async with aiohttp.ClientSession() as client:
            async with client.post(url, json=payload, headers=headers, params=params) as resp:
                # assert resp.status == 200
                print(resp.status)
                body = await resp.json()
                return resp.status, body

    def test_markets(self):
        """Test a public access route. GET /v1/markets"""
        # base_url = 'https://api-sandbox-eth.idex.io/'  # rest url for sandbox (rinkeby) ETH chain
        path = '/v1/markets'
        url = urljoin(self.base_url, path)

        status, markets = self.ev_loop.run_until_complete(
            self.rest_get(url)
        )
        print('markets:\n', pformat(markets))
        self.assertEqual(status, 200)
        self.assertIsInstance(markets, list)
        for m_item in markets:
            self.assertEqual(set(m_item.keys()), set(self.example_response_markets[0].keys()))

    @unittest.skipIf(not api_keys_provided(), 'IDEX_API_KEY env var missing')
    def test_user_details_access(self):
        """Tests HMAC authentication (user data level) by requesting GET /v1/user"""

        # base_url = 'https://api-sandbox-eth.idex.io/'  # rest url for sandbox (rinkeby) ETH chain
        path = '/v1/user'
        url = urljoin(self.base_url, path)

        # check normal response
        self.idex_auth.generate_nonce()
        url_params = {
            'nonce': self.idex_auth.get_nonce_str(),
        }
        auth_dict = self.idex_auth.generate_auth_dict(http_method='GET', url=url, params=url_params)
        status, user_details = self.ev_loop.run_until_complete(
            self.rest_get(
                auth_dict['url'],  # url already has the encoded url params included
                headers=auth_dict['headers'],
            )
        )

        print('user_details:\n', pformat(user_details))
        self.assertEqual(status, 200)
        self.assertEqual(set(user_details.keys()), set(self.example_response_user_detail.keys()))

        # test nonce most be unique error: always regenerate the nonce before each new call
        status, error_obj = self.ev_loop.run_until_complete(
            self.rest_get(auth_dict['url'], headers=auth_dict['headers'])
        )

        print('nonce_error:\n', pformat(error_obj))
        self.assertEqual(status, 400)
        self.assertEqual('INVALID_PARAMETER', error_obj['code'])
        self.assertIn('nonce must be unique', error_obj['message'])

        # test that passing the params unencoded for aiohttp to encode them also work
        self.idex_auth.generate_nonce()
        url_params = {'nonce': self.idex_auth.get_nonce_str()}
        auth_dict = self.idex_auth.generate_auth_dict(http_method='GET', url=url, params=url_params)
        status2, user_details2 = self.ev_loop.run_until_complete(
            self.rest_get(
                url,                # url without encoded params
                params=url_params,  # we pass the url params as a dict for aiohttp to encode them
                headers=auth_dict['headers'],
            )
        )

        print('user_details2:\n', pformat(user_details2))
        self.assertEqual(status2, 200)
        self.assertEqual(set(user_details2.keys()), set(self.example_response_user_detail.keys()))
        # notice: user_details and user_details2 may not be equals as the totalPortfolioValueUsd may fluctuate

    @unittest.skipIf(not api_keys_provided(), 'IDEX_API_KEY env var missing')
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
        self.idex_auth.init_wallet(self.wallet_private_key)

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

    @unittest.skipIf(
        not api_keys_provided() or not eth_wallet_provided(),
        'IDEX_API_KEY or IDEX_WALLET_PRIVATE_KEY env vars missing'
    )
    def test_associate_wallet(self):
        """
        Tests trade level authentication (HMAC Header + ETH Wallet signature) with request: POST /v1/wallets
        """
        # base_url = 'https://api-sandbox-eth.idex.io/'  # rest url for sandbox (rinkeby) ETH chain
        path = '/v1/wallets'
        url = urljoin(self.base_url, path)

        self.idex_auth.generate_nonce()  # re create nonce before each request

        signature_parameters = (  # see idex doc: https://docs.idex.io/#associate-wallet
            ("uint128", self.idex_auth.get_nonce_int()),
            ("address", self.idex_auth.get_wallet_address()),
        )
        wallet_signature = self.idex_auth.wallet_sign(signature_parameters)

        payload = {
            "parameters": {
                'nonce': self.idex_auth.get_nonce_str(),         # example: "9436afa0-9ee6-11ea-8a53-71994564322f",
                'wallet': self.idex_auth.get_wallet_address(),   # example: "0xA71C4aeeAabBBB8D2910F41C2ca3964b81F7310d"
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

        self.assertEqual(status, 200)
        self.assertIsInstance(response, dict)
        self.assertEqual(set(response.keys()), set(self.example_response_associate_wallet))

    @unittest.skipIf(
        not api_keys_provided() or not eth_wallet_provided(),
        'IDEX_API_KEY or IDEX_WALLET_PRIVATE_KEY env vars missing'
    )
    def test_create_order(self):
        """
        Tests create order to check trade level authentication (HMAC Header + ETH Wallet signature)
        with request: POST /v1/orders
        """
        # base_url = 'https://api-sandbox-eth.idex.io/'  # rest url for sandbox (rinkeby) ETH chain
        path = '/v1/orders'
        url = urljoin(self.base_url, path)

        self.idex_auth.generate_nonce()  # re create nonce before each request

        order = {
            'nonce': self.idex_auth.get_nonce_str(),  # example: "9436afa0-9ee6-11ea-8a53-71994564322f",
            'wallet': self.idex_auth.get_wallet_address(),  # example: "0xA71C4aeeAabBBB8D2910F41C2ca3964b81F7310d"
            'market': 'DIL-ETH',
            'type': 0,  # enum value for market orders
            'side': 0,  # enum value for buy
            'quoteOrderQuantity': '100.00000000',
        }

        signature_parameters = (  # see idex doc: https://docs.idex.io/#associate-wallet
            ('uint8', 1),      # 0 - The signature hash version is 1 for Ethereum, 2 for BSC

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
            ('uint8', 0),  # 12 - Order self-trade prevention enum value  Unused, always should be 0
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


def main():
    logging.basicConfig(level=logging.INFO)
    unittest.main()


if __name__ == "__main__":
    main()
