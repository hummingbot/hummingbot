from decimal import Decimal
from unittest import TestCase

from hummingbot.connector.exchange.chainflip_lp.chainflip_lp_data_formatter import DataFormatter


class DataFormatterTests(TestCase):
    def setUp(self):
        self.base_asset_dict = {"chain": "Ethereum", "asset": "ETH"}
        self.quote_asset_dict = {"chain": "Ethereum", "asset": "USDC"}
        self.base_asset = "ETH/Ethereum"
        self.quote_asset = "USDC/Ethereum"
        self.trading_pair = f"{self.base_asset}-{self.quote_asset}/{self.quote_asset_dict['chain']}"
        self.ex_trading_pair = f"{self.base_asset}-{self.quote_asset}/{self.quote_asset_dict['chain']}"

    def test_hex_str_to_int(self):
        string = "0x759a614014"  # noqa: mock
        int_value = DataFormatter.hex_str_to_int(string)
        self.assertEqual(type(int_value), int)

    def test_format_hex_balance(self):
        balance = "0x3baddb29af3e837abc358"  # noqa: mock
        asset = self.quote_asset_dict
        formatted_balance = DataFormatter.format_hex_balance(balance, asset)
        self.assertEqual(type(formatted_balance), float)

    def test_format_amount(self):
        amount = 10000
        formatted_amount = DataFormatter.format_amount(amount, self.quote_asset_dict)
        self.assertEqual(type(formatted_amount), str)
        self.assertTrue(formatted_amount.startswith("0x"))

    def test_format_price(self):
        price = 4512835869581138250956800
        formmatted_price = DataFormatter.format_price(price, self.base_asset_dict, self.quote_asset_dict)
        self.assertTrue(type(formmatted_price), float)

    def test_format_order_response(self):
        response = {
            "result": {
                "limit_orders": {
                    "asks": [
                        {
                            "lp": "cFLGvPhhrribWCx9id5kLVqwiFK4QiVNjQ6ViyaRFF2Nrgq7j",  # noqa: mock
                            "id": "0x0",  # noqa: mock
                            "tick": -195623,
                            "sell_amount": "0x56d3a03776ce8ba0",  # noqa: mock
                            "fees_earned": "0x0",
                            "original_sell_amount": "0x56d3a03776ce8ba0",  # noqa: mock
                        },
                    ],
                    "bids": [
                        {
                            "lp": "cFLGvPhhrribWCx9id5kLVqwiFK4QiVNjQ6ViyaRFF2Nrgq7j",  # noqa: mock
                            "id": "0x0",  # noqa: mock
                            "tick": -195622,
                            "sell_amount": "0x4a817c800",  # noqa: mock
                            "fees_earned": "0x0",  # noqa: mock
                            "original_sell_amount": "0x4a817c800",  # noqa: mock
                        },
                    ],
                },
            }
        }
        formatted_response = DataFormatter.format_order_response(response, self.base_asset_dict, self.quote_asset_dict)
        self.assertIn("asks", formatted_response)
        self.assertIn("bids", formatted_response)
        self.assertEqual(len(formatted_response["asks"]), 1)
        self.assertEqual(len(formatted_response["bids"]), 1)
        self.assertIn("tick", formatted_response["asks"][0])
        self.assertIn("price", formatted_response["asks"][0])
        self.assertEqual(float, type(formatted_response["asks"][0]["price"]))

    def test_format_balance_response(self):
        response = {
            "result": {
                "Ethereum": {
                    "ETH": "0x2386f26fc0bda2",  # noqa: mock
                    "FLIP": "0xde0b6b3a763ec60",  # noqa: mock
                    "USDC": "0x8bb50bca00",  # noqa: mock
                },
            }
        }
        balances = DataFormatter.format_balance_response(response)
        self.assertEqual(type(balances), dict)
        self.assertEqual(len(balances), 3)
        self.assertEqual(type(balances[f"{self.base_asset}"]), Decimal)

    def test_format_all_market_response(self):
        response = {
            "result": {
                "fees": {
                    "Ethereum": {
                        self.base_asset: {
                            "limit_order_fee_hundredth_pips": 500,
                            "range_order_fee_hundredth_pips": 500,
                            "range_order_total_fees_earned": {
                                "base": "0x3d4a754fc1d2302",  # noqa: mock
                                "quote": "0x3689782a",  # noqa: mock
                            },
                            "limit_order_total_fees_earned": {
                                "base": "0x83c94dd54804790a",  # noqa: mock
                                "quote": "0x670a76ae0",  # noqa: mock
                            },
                            "range_total_swap_inputs": {
                                "base": "0x1dc18b046dde67f2b0",  # noqa: mock
                                "quote": "0x1a774f80e62",  # noqa: mock
                            },
                            "limit_total_swap_inputs": {
                                "base": "0x369c2e5bafeffddab46",  # noqa: mock
                                "quote": "0x2be491b4d31d",  # noqa: mock
                            },
                            "quote_asset": {"chain": "Ethereum", "asset": self.quote_asset},
                        },
                    }
                }
            }
        }
        all_market = DataFormatter.format_all_market_response(response)
        self.assertEqual(len(all_market), 1)
        self.assertEqual(type(all_market[0]["symbol"]), str)
        self.assertIn(self.base_asset, all_market[0]["symbol"].split("-"))
        self.assertIn(self.quote_asset, all_market[0]["symbol"].split("-"))

    def test_format_all_assets_response(self):
        response = {
            "result": [
                {"chain": "Ethereum", "asset": "ETH"},
                {"chain": "Ethereum", "asset": "FLIP"},
                {"chain": "Ethereum", "asset": "USDC"},
                {"chain": "Ethereum", "asset": "USDT"},
                {"chain": "Polkadot", "asset": "DOT"},
                {"chain": "Bitcoin", "asset": "BTC"},
                {"chain": "Arbitrum", "asset": "ETH"},
                {"chain": "Arbitrum", "asset": "USDC"},
            ]
        }
        all_assets = DataFormatter.format_all_assets_response(response)
        self.assertEqual(len(all_assets), 8)

    def test_format_orderbook_response(self):
        response = {
            "result": {
                "asks": [
                    {"amount": "0x54b2cec31723f8b04", "sqrt_price": "0x2091b342e50d7f26cdc582"},  # noqa: mock
                    {"amount": "0x5b475d13fc0374e", "sqrt_price": "0x1e38a26ccc8cad8ff5ed7d0e"},  # noqa: mock
                    {"amount": "0x625ecb4a48690", "sqrt_price": "0x1c0ae64c925b19f39a41ff17bd"},  # noqa: mock
                    {"amount": "0x6a03445844f", "sqrt_price": "0x1a055f3578ef64659516605ff66d"},  # noqa: mock
                ],
                "bids": [
                    {"amount": "0x9a488cdb615edf25fd", "sqrt_price": "0x62bac2a2b8f0b98b9ceb"},  # noqa: mock
                    {"amount": "0x1217d98319cd00bc28de", "sqrt_price": "0x349e212a7a008282ff9"},  # noqa: mock
                    {"amount": "0x21f2ffe1f3cc8bebab567", "sqrt_price": "0x1c0ae0758c0acee837"},  # noqa: mock
                    {"amount": "0x3fb3690cb0511666161b4d", "sqrt_price": "0xef1f790088e3f323"},  # noqa: mock
                ],
            },
        }
        orderbook = DataFormatter.format_orderbook_response(response, self.base_asset_dict, self.quote_asset_dict)
        self.assertIn("asks", orderbook)
        self.assertIn("bids", orderbook)

    def test_format_trading_pair(self):
        all_assets = [
            {"chain": "Ethereum", "asset": "ETH"},
            {"chain": "Ethereum", "asset": "USDC"},
            {"chain": "Polkadot", "asset": "DOT"},
            {"chain": "Bitcoin", "asset": "BTC"},
        ]
        pair = "ETH-USDC/Ethereum"
        asset = DataFormatter.format_trading_pair(pair, all_assets)
        self.assertIn("base_asset", asset)
        self.assertIn("quote_asset", asset)
        self.assertTrue(isinstance(asset["base_asset"], dict))
        self.assertTrue(isinstance(asset["quote_asset"], dict))
        self.assertEqual(asset["base_asset"]["chain"], "Ethereum")
        self.assertEqual(asset["quote_asset"]["chain"], "Ethereum")
        self.assertEqual(asset["base_asset"]["asset"], "ETH")
        self.assertEqual(asset["quote_asset"]["asset"], "USDC")

    def test_format_market_price(self):
        response = {
            "result": {
                "base_asset": {"chain": "Bitcoin", "asset": "BTC"},
                "quote_asset": {"chain": "Ethereum", "asset": "USDC"},
                "sell": "0x10b09273676d13f5d254e20a20",  # noqa: mock
                "buy": "0x10b09273676d13f5d254e20a20",  # noqa: mock
                "range_order": "0x10b09273676d13f5d254e20a20",  # noqa: mock
            }
        }
        price = DataFormatter.format_market_price(response)

        self.assertTrue(isinstance(price, dict))
        self.assertIn("price", price)
        self.assertIn("sell", price)
        self.assertIn("buy", price)
        self.assertTrue(isinstance(price["buy"], float))
        self.assertTrue(isinstance(price["sell"], float))
        self.assertTrue(isinstance(price["price"], float))

    def test_format_order_fills_response(self):
        response = {
            "result": {
                "fills": {
                    "limit_orders": {
                        "lp": "cFPdef3hF5zEwbWUG6ZaCJ3X7mTvEeAog7HxZ8QyFcCgDVGDM",  # noqa: mock
                        "base_asset": "FLIP",
                        "quote_asset": "USDC",
                        "side": "buy",
                        "id": "0x0",  # noqa: mock
                        "tick": 0,
                        "sold": "0x1200",  # noqa: mock
                        "bought": "0x1200",  # noqa: mock
                        "fees": "0x100",  # noqa: mock
                        "remaining": "0x100000",  # noqa: mock
                    }
                }
            }
        }
        all_assets = [
            {"chain": "Ethereum", "asset": "ETH"},
            {"chain": "Ethereum", "asset": "FLIP"},
            {"chain": "Ethereum", "asset": "USDC"},
            {"chain": "Polkadot", "asset": "DOT"},
            {"chain": "Bitcoin", "asset": "BTC"},
        ]
        order_fills = DataFormatter.format_order_fills_response(
            response, "cFPdef3hF5zEwbWUG6ZaCJ3X7mTvEeAog7HxZ8QyFcCgDVGDM", all_assets  # noqa: mock
        )
        self.assertTrue(isinstance(order_fills, list))
        self.assertEqual(len(order_fills), 1)
        order_fill = order_fills[0]
        self.assertIn("trading_pair", order_fill)
        self.assertIn("side", order_fill)
        self.assertIn("id", order_fill)
        self.assertIn("base_amount", order_fill)
        self.assertIn("quote_amount", order_fill)
        self.assertIn("price", order_fill)

        self.assertTrue(order_fill["side"], "buy")
        self.assertTrue(isinstance(order_fill["base_amount"], float))
        self.assertTrue(isinstance(order_fill["quote_amount"], float))
        self.assertTrue(isinstance(order_fill["price"], float))

    def test_convert_tick_to_price(self):
        tick = 50
        base_asset = {"chain": "Ethereum", "asset": "ETH"}
        quote_asset = {"chain": "Ethereum", "asset": "USDC"}
        price = DataFormatter.convert_tick_to_price(tick, base_asset, quote_asset)
        self.assertTrue(isinstance(price, float))

    def test_format_place_order_response(self):
        response = {
            "jsonrpc": "2.0",
            "result": {
                "tx_details": {
                    "tx_hash": "0x3cb78cdbbfc34634e33d556a94ee7438938b65a5b852ee523e4fc3c0ec3f8151",  # noqa: mock
                    "response": [
                        {
                            "base_asset": "ETH",
                            "quote_asset": "USDC",
                            "side": "buy",
                            "id": "0x11",  # noqa: mock
                            "tick": 50,
                            "sell_amount_total": "0x100000",  # noqa: mock
                            "collected_fees": "0x0",  # noqa: mock
                            "bought_amount": "0x0",  # noqa: mock
                            "sell_amount_change": {"increase": "0x100000"},  # noqa: mock
                        }
                    ],
                }
            },
            "id": 1,
        }
        order_data = DataFormatter.format_place_order_response(response)
        self.assertTrue(isinstance(order_data, dict))
        self.assertIn("order_id", order_data)

    def test_format_order_status(self):
        response_data = {
            "result": {
                "limit_orders": {
                    "asks": [
                        {
                            "lp": "cFLGvPhhrribWCx9id5kLVqwiFK4QiVNjQ6ViyaRFF2Nrgq7j",  # noqa: mock
                            "id": "0x0",  # noqa: mock
                            "tick": -195623,
                            "sell_amount": "0x56d3a03776ce8ba0",  # noqa: mock
                            "fees_earned": "0x0",  # noqa: mock
                            "original_sell_amount": "0x56d3a03776ce8ba0"  # noqa: mock
                        },
                    ],
                    "bids": [
                        {
                            "lp": "cFLGvPhhrribWCx9id5kLVqwiFK4QiVNjQ6ViyaRFF2Nrgq7j",  # noqa: mock
                            "id": "0x0",  # noqa: mock
                            "tick": -195622,
                            "sell_amount": "0x4a817c800",  # noqa: mock
                            "fees_earned": "0x0",  # noqa: mock
                            "original_sell_amount": "0x4a817c800"  # noqa: mock
                        },
                    ]
                },
            }
        }
        status = DataFormatter.format_order_status(
            response_data,
            "0x0",  # noqa: mock
            "sell"
        )

        self.assertIsNotNone(status)
        self.assertIsInstance(status, dict)
