from unittest import TestCase
from hummingbot.connector.exchange.chainflip_lp import chainflip_lp_constants as CONSTANTS
from hummingbot.connector.exchange.chainflip_lp.chainflip_lp_data_formatter import DataFormatter


class DataFormatterTests(TestCase):
    def setUp(self):
        self.base_asset_dict = {"chain":"Ethereum", "asset":"ETH"}
        self.quote_asset_dict = {"chain": "Ethereum","asset":"USDC"}
        self.base_asset = "ETH"
        self.quote_asset = "USDC"
        self.trading_pair = f'{self.base_asset}-{self.quote_asset}'
        self.ex_trading_pair = f'{self.base_asset}-{self.quote_asset}'
    def test_hex_str_to_int(self):
        string  = "0x759a614014"
        int_value = DataFormatter.hex_str_to_int(string)
        self.assertEqual(type(int_value),int)

    def test_format_hex_balance(self):
        balance = "0x3baddb29af3e837abc358"
        asset = self.quote_asset_dict
        formatted_balance = DataFormatter.format_hex_balance(
            balance, asset
        )
        self.assertEqual(type(formatted_balance), float)
    def test_format_amount(self):
        amount = 10000
        formatted_amount = DataFormatter.format_amount(
            amount, self.quote_asset_dict
        )
        self.assertEqual(type(formatted_amount), str)
        self.assertTrue(formatted_amount.startswith("0x"))
    def test_format_price(self):
        price = 4512835869581138250956800
        formmatted_price = DataFormatter.format_price(
            price, self.base_asset_dict, self.quote_asset_dict
        )
        self.assertTrue(type(formmatted_price), float)
    def test_format_order_response(self):
        response = {
            "result":{
                "limit_orders":{
                    "asks":[
                        {
                        "lp":"cFLGvPhhrribWCx9id5kLVqwiFK4QiVNjQ6ViyaRFF2Nrgq7j",
                        "id":"0x0",
                        "tick":-195623,
                        "sell_amount":"0x56d3a03776ce8ba0",
                        "fees_earned":"0x0",
                        "original_sell_amount":"0x56d3a03776ce8ba0"
                        },
                        
                    ],
                    "bids":[
                        {
                        "lp":"cFLGvPhhrribWCx9id5kLVqwiFK4QiVNjQ6ViyaRFF2Nrgq7j",
                        "id":"0x0",
                        "tick":-195622,
                        "sell_amount":"0x4a817c800",
                        "fees_earned":"0x0",
                        "original_sell_amount":"0x4a817c800"
                        },
                    ]
                },
            }
        }
        formatted_response = DataFormatter.format_order_response(
            response, self.base_asset_dict, self.quote_asset_dict
        )
        self.assertIn("asks", formatted_response)
        self.assertIn("bids", formatted_response)
        self.assertEqual(len(formatted_response["asks"]),1)
        self.assertEqual(len(formatted_response["bids"]),1)
        self.assertIn("tick",formatted_response["asks"][0])
        self.assertIn("price",formatted_response["asks"][0])
        self.assertEqual(float, type(formatted_response["asks"][0]["price"]))
    def test_format_balance_response(self):
        response = {
            "result": {
                "Ethereum": [
                    {
                        "asset": "ETH",
                        "balance": "0x2386f26fc0bda2"
                    },
                    {
                        "asset": "FLIP",
                        "balance": "0xde0b6b3a763ec60"
                    },
                    {
                        "asset": "USDC",
                        "balance": "0x8bb50bca00"
                    }
                ],
            }
        }
        balances = DataFormatter.format_balance_response(response)
        self.assertEqual(type(balances), dict)
        self.assertEqual(len(balances), 3)
        self.assertEqual(type(balances[self.base_asset]), float)
    def test_format_all_market_response(self):
        response = {
            "result": {
                "fees": {
                    "Ethereum": {
                        self.base_asset: {
                            "limit_order_fee_hundredth_pips": 500,
                            "range_order_fee_hundredth_pips": 500,
                            "range_order_total_fees_earned": {
                                "base": "0x3d4a754fc1d2302",
                                "quote": "0x3689782a",
                            },
                            "limit_order_total_fees_earned": {
                                "base": "0x83c94dd54804790a",
                                "quote": "0x670a76ae0",
                            },
                            "range_total_swap_inputs": {
                                "base": "0x1dc18b046dde67f2b0",
                                "quote": "0x1a774f80e62",
                            },
                            "limit_total_swap_inputs": {
                                "base": "0x369c2e5bafeffddab46",
                                "quote": "0x2be491b4d31d",
                            },
                            "quote_asset": {"chain": "Ethereum", "asset": self.quote_asset},
                        },
                        
                    }
                }   
            }
        }
        all_market = DataFormatter.format_all_market_response(response)
        self.assertEqual(len(all_market),1)
        self.assertEqual(type(all_market[0]["symbol"]), str)
        self.assertIn(self.base_asset, all_market[0]["symbol"].split("-"))
        self.assertIn(self.quote_asset, all_market[0]["symbol"].split("-"))

    def test_format_all_assets_response(self):
        response = {
            'result': [
                {'chain': 'Ethereum', 'asset': 'ETH'}, 
                {'chain': 'Ethereum', 'asset': 'FLIP'}, 
                {'chain': 'Ethereum', 'asset': 'USDC'}, 
                {'chain': 'Ethereum', 'asset': 'USDT'}, 
                {'chain': 'Polkadot', 'asset': 'DOT'}, 
                {'chain': 'Bitcoin', 'asset': 'BTC'}, 
                {'chain': 'Arbitrum', 'asset': 'ETH'}, 
                {'chain': 'Arbitrum', 'asset': 'USDC'}
            ]
        }
        all_assets = DataFormatter.format_all_assets_response(response)
        self.assertEqual(len(all_assets), 6)
    
    def test_format_orderbook_response(self):
        response = {
            "result": {
                "asks": [
                    {
                        "amount": "0x54b2cec31723f8b04",
                        "sqrt_price": "0x2091b342e50d7f26cdc582"
                    },
                    {
                        "amount": "0x5b475d13fc0374e",
                        "sqrt_price": "0x1e38a26ccc8cad8ff5ed7d0e"
                    },
                    {
                        "amount": "0x625ecb4a48690",
                        "sqrt_price": "0x1c0ae64c925b19f39a41ff17bd"
                    },
                    {
                        "amount": "0x6a03445844f",
                        "sqrt_price": "0x1a055f3578ef64659516605ff66d"
                    },
                ],
                "bids": [
                    {
                        "amount": "0x9a488cdb615edf25fd",
                        "sqrt_price": "0x62bac2a2b8f0b98b9ceb"
                    },
                    {
                        "amount": "0x1217d98319cd00bc28de",
                        "sqrt_price": "0x349e212a7a008282ff9"
                    },
                    {
                        "amount": "0x21f2ffe1f3cc8bebab567",
                        "sqrt_price": "0x1c0ae0758c0acee837"
                    },
                    {
                        "amount": "0x3fb3690cb0511666161b4d",
                        "sqrt_price": "0xef1f790088e3f323"
                    }
                ]
            },
        }
        orderbook = DataFormatter.format_orderbook_response(
            response,
            self.base_asset_dict,
            self.quote_asset_dict
        )
        self.assertIn("asks", orderbook)
        self.assertIn("bids", orderbook)
    def test_format_trading_pair(self):
        pass
    def test_format_market_price(self):
        pass
    def test_format_order_fills_response(self):
        pass
    def test_convert_tick_to_price(self):
        pass




