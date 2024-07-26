import asyncio
import json
import re
import time
from decimal import Decimal
from functools import partial
from typing import Any, Callable, Dict, List, Optional
from unittest.mock import AsyncMock, Mock, patch

import pytest
from aioresponses import aioresponses
from aioresponses.core import RequestCall
from bidict import bidict

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.tegro import tegro_constants as CONSTANTS, tegro_web_utils as web_utils
from hummingbot.connector.exchange.tegro.tegro_exchange import TegroExchange
from hummingbot.connector.test_support.exchange_connector_test import AbstractExchangeConnectorTests
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import get_new_client_order_id
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder
from hummingbot.core.data_type.trade_fee import DeductedFromReturnsTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import BuyOrderCreatedEvent, MarketEvent


class TegroExchangeTests(AbstractExchangeConnectorTests.ExchangeConnectorTests):

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.tegro_api_key = "somePassPhrase"  # noqa: mock
        cls.tegro_api_secret = "kQH5HW/8p1uGOVjbgWA7FunAmGO8lsSUXNsu3eow76sz84Q18fWxnyRzBHCd3pd5nE9qa99HAZtuZuj6F1huXg=="  # noqa: mock
        cls.base_asset = "WETH"
        cls.quote_asset = "USDT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}_{cls.quote_asset}"
        cls.chain_id = "polygon"
        cls.domain = "tegro_optimism_testnet"  # noqa: mock
        cls.chain = 80002
        cls.rpc_url = "http://mock-rpc-url"  # noqa: mock
        cls.market_id = "80002_0x6b94a36d6ff05886d44b3dafabdefe85f09563ba_0x7551122e441edbf3fffcbcf2f7fcc636b636482b"  # noqa: mock
        cls.client_config_map = ClientConfigAdapter(ClientConfigMap())

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.mocking_assistant = NetworkMockingAssistant()
        self.async_tasks: List[asyncio.Task] = []

        self.exchange = TegroExchange(
            client_config_map=self.client_config_map,
            tegro_api_key=self.tegro_api_key,  # noqa: mock
            tegro_api_secret=self.tegro_api_secret,  # noqa: mock
            trading_pairs=[self.trading_pair],
            domain=CONSTANTS.DEFAULT_DOMAIN
        )

        self.exchange.logger().setLevel(1)
        self.exchange.logger().addHandler(self)
        self.exchange._time_synchronizer.add_time_offset_ms_sample(0)
        self.exchange._time_synchronizer.logger().setLevel(1)
        self.exchange._time_synchronizer.logger().addHandler(self)
        self.exchange._order_tracker.logger().setLevel(1)
        self.exchange._order_tracker.logger().addHandler(self)

        self._initialize_event_loggers()

        self.exchange.tokens_info = AsyncMock(return_value=[
            {
                "address": "0x7551122e441edbf3fffcbcf2f7fcc636b636482b",
                "balance": "10000",
                "symbol": "USDT",
                "decimal": 6,
                "price": 0,
                "price_change_24_h": 0,
                "type": "quote",
                "placed_amount": 0
            },
            {
                "address": "0x6b94a36d6ff05886d44b3dafabdefe85f09563ba",
                "balance": "10010.7",
                "symbol": "WETH",
                "decimal": 18,
                "price": 1000,
                "price_change_24_h": 0,
                "type": "base",
                "placed_amount": 0
            }
        ])
        self.exchange.get_chain_list = AsyncMock(return_value=[
            {
                "id": 42161,
                "name": "Arbitrum One",
                "default_quote_token_symbol": "USDT",
                "default_quote_token_contract_address": "0xfd086bc7cd5c481dcc9c85ebe478a1c0b69fcbb9",
                "exchange_contract": "0x34ca94e5ac475238827363f66c065fb54b0db416",
                "settlement_contract": "0xa45e62e64f8a59726aa91d0fb6c5b85b00c454a7",
                "logo": "",
                "min_order_value": "2000000",
                "fee": 0.01,
                "native_token_symbol": "ETH",
                "native_token_symbol_id": "ethereum",
                "native_token_price": 3364,
                "gas_per_trade": 400000,
                "gas_price": 0.01,
                "default_gas_limit": 5000000,
                "Active": True
            },
            {
                "id": 11155420,
                "name": "optimism",
                "default_quote_token_symbol": "OPUSDT",
                "default_quote_token_contract_address": "0x7bda2a5ee22fe43bc1ab2bcba97f7f9504645c08",
                "exchange_contract": "0xad841d6718518e78fd737E45D01bc406Aa7bc098",
                "settlement_contract": "0x9c9e5f6D2F1b033CaCa7AE243D6F3212d0B4cBee",
                "logo": "",
                "min_order_value": "2000000",
                "fee": 0.01,
                "native_token_symbol": "ETH",
                "native_token_symbol_id": "ethereum",
                "native_token_price": 3000,
                "gas_per_trade": 400000,
                "gas_price": 2,
                "default_gas_limit": 8000000,
                "Active": True
            },
            {
                "id": 8453,
                "name": "base",
                "default_quote_token_symbol": "USDC",
                "default_quote_token_contract_address": "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",
                "exchange_contract": "0x7551122e441edbf3fffcbcf2f7fcc636b636482b",
                "settlement_contract": "0xc4215dd825176e8f6fe55f532fefe6c65ec5f179",
                "logo": "",
                "min_order_value": "2000000",
                "fee": 0.05,
                "native_token_symbol": "ETH",
                "native_token_symbol_id": "ethereum",
                "native_token_price": 3085,
                "gas_per_trade": 400000,
                "gas_price": 0.062,
                "default_gas_limit": 5000000,
                "Active": True
            },
            {
                "id": 80002,
                "name": "amoy",
                "default_quote_token_symbol": "USDT",
                "default_quote_token_contract_address": "0x7551122E441edBF3fffcBCF2f7FCC636B636482b",
                "exchange_contract": "0x1d0888a1552996822b71e89ca735b06aed4b20a4",
                "settlement_contract": "0xb365f2c6b51eb5c500f80e9fc1ba771d2de9396e",
                "logo": "",
                "min_order_value": "2000000",
                "fee": 0.01,
                "native_token_symbol": "MATIC",
                "native_token_symbol_id": "matic-network",
                "native_token_price": 0.7,
                "gas_per_trade": 400000,
                "gas_price": 5,
                "default_gas_limit": 8000000,
                "Active": True
            }
        ])
        self.exchange._set_trading_pair_symbol_map(bidict({self.ex_trading_pair: self.trading_pair}))

    def tearDown(self) -> None:
        for task in self.async_tasks:
            task.cancel()
        super().tearDown()

    def _initialize_event_loggers(self):
        self.buy_order_completed_logger = EventLogger()
        self.buy_order_created_logger = EventLogger()
        self.order_cancelled_logger = EventLogger()
        self.order_failure_logger = EventLogger()
        self.order_filled_logger = EventLogger()
        self.sell_order_completed_logger = EventLogger()
        self.sell_order_created_logger = EventLogger()

        events_and_loggers = [
            (MarketEvent.BuyOrderCompleted, self.buy_order_completed_logger),
            (MarketEvent.BuyOrderCreated, self.buy_order_created_logger),
            (MarketEvent.OrderCancelled, self.order_cancelled_logger),
            (MarketEvent.OrderFailure, self.order_failure_logger),
            (MarketEvent.OrderFilled, self.order_filled_logger),
            (MarketEvent.SellOrderCompleted, self.sell_order_completed_logger),
            (MarketEvent.SellOrderCreated, self.sell_order_created_logger)]

        for event, logger in events_and_loggers:
            self.exchange.add_listener(event, logger)

    def handle(self, record):
        self.log_records.append(record)

    @property
    def all_symbols_url(self):
        url = web_utils.public_rest_url(path_url=CONSTANTS.EXCHANGE_INFO_PATH_LIST_URL.format(self.chain), domain=self.exchange._domain)
        url = f"{url}?page=1&sort_order=desc&sort_by=volume&page_size=20&verified=true"
        return url

    @property
    def latest_prices_url(self):
        url = web_utils.public_rest_url(path_url=CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL.format(self.chain, self.market_id), domain=self.exchange._domain)
        url = f"{url}"
        return url

    @property
    def network_status_url(self):
        url = web_utils.public_rest_url(CONSTANTS.PING_PATH_URL, domain=self.exchange._domain)
        return url

    @property
    def trading_rules_url(self):
        url = web_utils.public_rest_url(CONSTANTS.EXCHANGE_INFO_PATH_URL, domain=self.exchange._domain)
        url = f"{url.format(self.chain, self.market_id)}"
        return url

    @property
    def order_creation_url(self):
        url = web_utils.public_rest_url(CONSTANTS.ORDER_PATH_URL, domain=self.exchange._domain)
        return url

    @property
    def balance_url(self):
        url = web_utils.public_rest_url(CONSTANTS.ACCOUNTS_PATH_URL, domain=self.exchange._domain)
        url = f"{url.format(self.chain, self.tegro_api_key)}"
        return url

    @property
    def all_symbols_request_mock_response(self):
        mock_response = [
            {
                "id": "80002_0x6b94a36d6ff05886d44b3dafabdefe85f09563ba_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",  # noqa: mock
                "base_contract_address": "0x6b94a36d6ff05886d44b3dafabdefe85f09563ba",  # noqa: mock
                "quote_contract_address": "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",  # noqa: mock
                "chain_id": 80002,
                "symbol": f"{self.base_asset}_{self.quote_asset}",
                "state": "verified",
                "base_symbol": self.base_asset,
                "quote_symbol": self.quote_asset,
                "base_decimal": 18,
                "quote_decimal": 6,
                "base_precision": 6,
                "quote_precision": 10,
                "ticker": {
                    "base_volume": 265306,
                    "quote_volume": 1423455.3812000754,
                    "price": 0.9541,
                    "price_change_24h": -85.61,
                    "price_high_24h": 10,
                    "price_low_24h": 0.2806,
                    "ask_low": 0.2806,
                    "bid_high": 10
                }
            },
        ]
        return mock_response

    def get_last_traded_prices_rest_msg(self):
        return [
            {
                "id": "80002_0x6b94a36d6ff05886d44b3dafabdefe85f09563ba_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",  # noqa: mock
                "base_contract_address": "0x6b94a36d6ff05886d44b3dafabdefe85f09563ba",  # noqa: mock
                "quote_contract_address": "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",  # noqa: mock
                "chain_id": 80002,
                "symbol": f"{self.base_asset}_{self.quote_asset}",
                "state": "verified",
                "base_symbol": self.base_asset,
                "quote_symbol": self.quote_asset,
                "base_decimal": 18,
                "quote_decimal": 6,
                "base_precision": 6,
                "quote_precision": 10,
                "ticker": {
                    "base_volume": 265306,
                    "quote_volume": 1423455.3812000754,
                    "price": self.expected_latest_price,
                    "price_change_24h": -85.61,
                    "price_high_24h": 10,
                    "price_low_24h": 0.2806,
                    "ask_low": 0.2806,
                    "bid_high": 10
                }
            },
            {
                "id": "80002_0x6b94a36d6ff05886d44b3dafabdefe85f09563ba_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",  # noqa: mock
                "base_contract_address": "0x6b94a36d6ff05886d44b3dafabdefe85f09563ba",  # noqa: mock
                "quote_contract_address": "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",  # noqa: mock
                "chain_id": 80002,
                "symbol": "SOME_PAIR",
                "state": "verified",
                "base_symbol": "SOME",
                "quote_symbol": "PAIR",
                "base_decimal": 18,
                "quote_decimal": 6,
                "base_precision": 6,
                "quote_precision": 10,
                "ticker": {
                    "base_volume": 265306,
                    "quote_volume": 1423455.3812000754,
                    "price": 0.9541,
                    "price_change_24h": -85.61,
                    "price_high_24h": 10,
                    "price_low_24h": 0.2806,
                    "ask_low": 0.2806,
                    "bid_high": 10
                }
            }
        ]

    @property
    def latest_prices_request_mock_response(self):
        pass

    @property
    def all_symbols_including_invalid_pair_mock_response(self) -> list[Dict[str, Any]]:
        response = [
            {
                "id": "80002_0x6b94a36d6ff05886d44b3dafabdefe85f09563ba_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",  # noqa: mock
                "base_contract_address": "0x6b94a36d6ff05886d44b3dafabdefe85f09563ba",  # noqa: mock
                "quote_contract_address": "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",  # noqa: mock
                "chain_id": 80002,
                "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "state": "verified",
                "base_symbol": self.base_asset,
                "quote_symbol": self.quote_asset,
                "base_decimal": 18,
                "quote_decimal": 6,
                "base_precision": 6,
                "quote_precision": 10,
                "ticker": {
                    "base_volume": 265306,
                    "quote_volume": 1423455.3812000754,
                    "price": 0.9541,
                    "price_change_24h": -85.61,
                    "price_high_24h": 10,
                    "price_low_24h": 0.2806,
                    "ask_low": 0.2806,
                    "bid_high": 10
                }
            },
            {
                "id": "80002_0x6b94a36d6ff05886d44b3dafabdefe85f09563ba_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",  # noqa: mock
                "base_contract_address": "0x6b94a36d6ff05886d44b3dafabdefe85f09563ba",  # noqa: mock
                "quote_contract_address": "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",  # noqa: mock
                "chain_id": 80002,
                "symbol": self.exchange_symbol_for_tokens("INVALID", "PAIR"),
                "state": "verified",
                "base_symbol": "INVALID",
                "quote_symbol": "PAIR",
                "base_decimal": 18,
                "quote_decimal": 6,
                "base_precision": 6,
                "quote_precision": 10,
                "ticker": {
                    "base_volume": 265306,
                    "quote_volume": 1423455.3812000754,
                    "price": 0.9541,
                    "price_change_24h": -85.61,
                    "price_high_24h": 10,
                    "price_low_24h": 0.2806,
                    "ask_low": 0.2806,
                    "bid_high": 10
                }
            }
        ]
        return "INVALID-PAIR", response

    @property
    def network_status_request_successful_mock_response(self):
        return self.all_symbols_request_mock_response

    @property
    def trading_rules_request_mock_response(self):
        return self.all_symbols_request_mock_response

    @property
    def trading_rules_request_erroneous_mock_response(self):
        return [
            {
                "id": "80002_0x6b94a36d6ff05886d44b3dafabdefe85f09563ba_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",  # noqa: mock
                "base_contract_address": "0x6b94a36d6ff05886d44b3dafabdefe85f09563ba",  # noqa: mock
                "quote_contract_address": "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",  # noqa: mock
                "chain_id": 80002,
                "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "state": "ENABLED",
                "base_symbol": self.base_asset,
                "quote_symbol": self.quote_asset,
                "base_decimal": 18,
                "ticker": {
                    "base_volume": 265306,
                    "quote_volume": 1423455.3812000754,
                    "price": 0.9541,
                    "price_change_24h": -85.61,
                    "price_high_24h": 10,
                    "price_low_24h": 0.2806,
                    "ask_low": 0.2806,
                    "bid_high": 10
                }
            }
        ]

    @property
    def initialize_verified_market_response(self):
        return {
            "id": "80002_0x6b94a36d6ff05886d44b3dafabdefe85f09563ba_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",  # noqa: mock
            "base_contract_address": "0x6b94a36d6ff05886d44b3dafabdefe85f09563ba",  # noqa: mock
            "quote_contract_address": "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",  # noqa: mock
            "chain_id": self.chain,
            "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "state": "verified",
            "base_symbol": self.base_asset,
            "quote_symbol": self.quote_asset,
            "base_decimal": 18,
            "quote_decimal": 6,
            "base_precision": 6,
            "quote_precision": 10,
            "ticker": {
                "base_volume": 265306,
                "quote_volume": 1423455.3812000754,
                "price": 0.9541,
                "price_change_24h": -85.61,
                "price_high_24h": 10,
                "price_low_24h": 0.2806,
                "ask_low": 0.2806,
                "bid_high": 10
            }
        }

    @property
    def initialize_market_list_response(self):
        return self.all_symbols_request_mock_response

    @property
    def generated_typed_data_response(self):
        return {
            "message": "success",
            "data": {
                "limit_order": {
                    "chain_id": 80002,
                    "base_asset": "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",  # noqa: mock
                    "quote_asset": "0x4200000000000000000000000000000000000006",  # noqa: mock
                    "side": 1,
                    "volume_precision": "100000000000000000",
                    "price_precision": "2700000000",
                    "order_hash": "0x5a28a76181ab0c008368ed09cc018b6d40eb23997b4a234cfe5650b7034d6611",  # noqa: mock
                    "raw_order_data": "{\"baseToken\":\"0x4200000000000000000000000000000000000006\",\"expiryTime\":\"0\",\"isBuy\":true,\"maker\":\"0x3da2b15eB80B1F7d499D18b6f0B671C838E64Cb3\",\"price\":\"2700000000\",\"quoteToken\":\"0x833589fcd6edb6e08f4c7c32d4f71b54bda02913\",\"salt\":\"277564373322\",\"totalQuantity\":\"100000000000000000\"}",
                    "signature": None,
                    "signed_order_type": "tegro",
                    "market_id": "80002_0x6b94a36d6ff05886d44b3dafabdefe85f09563ba_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",  # noqa: mock
                    "market_symbol": "WETH_USDC"
                },
                "sign_data": {
                    "types": {
                        "EIP712Domain": [
                            {
                                "name": "name",
                                "type": "string"
                            },
                            {
                                "name": "version",
                                "type": "string"
                            },
                            {
                                "name": "chainId",
                                "type": "uint256"
                            },
                            {
                                "name": "verifyingContract",
                                "type": "address"
                            }
                        ],
                        "Order": [
                            {
                                "name": "baseToken",
                                "type": "address"
                            },
                            {
                                "name": "quoteToken",
                                "type": "address"
                            },
                            {
                                "name": "price",
                                "type": "uint256"
                            },
                            {
                                "name": "totalQuantity",
                                "type": "uint256"
                            },
                            {
                                "name": "isBuy",
                                "type": "bool"
                            },
                            {
                                "name": "salt",
                                "type": "uint256"
                            },
                            {
                                "name": "maker",
                                "type": "address"
                            },
                            {
                                "name": "expiryTime",
                                "type": "uint256"
                            }
                        ]
                    },
                    "primaryType": "Order",
                    "domain": {
                        "name": "TegroDEX",
                        "version": "1",
                        "chainId": 80002,
                        "verifyingContract": "0xa492c74aAc592F7951d98000a602A22157019563"  # noqa: mock
                    },
                    "message": {
                        "baseToken": "0x4200000000000000000000000000000000000006",
                        "expiryTime": "0",
                        "isBuy": True,
                        "maker": "0x3da2b15eB80B1F7d499D18b6f0B671C838E64Cb3",  # noqa: mock
                        "price": "2700000000",
                        "quoteToken": "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",  # noqa: mock
                        "salt": "277564373322",
                        "totalQuantity": "100000000000000000"
                    }
                }
            }
        }

    @property
    def generated_cancel_typed_data_response(self):
        return {
            "limit_order": {
                "chain_id": 80001,
                "base_asset": "0xec8e3f97af8d451e9d15ae09428cbd2a6931e0ba",  # noqa: mock
                "quote_asset": "0xe5ae73187d0fed71bda83089488736cadcbf072d",  # noqa: mock
                "side": 0,
                "volume_precision": "10000",
                "price_precision": "10000000",
                "order_hash": "0x23ef65f34e480bd9fea189b6f80ee62f71bdc4cea0bebc7599634c4b4bb7b82c",  # noqa: mock
                "raw_order_data": "{\"allowedSender\":\"0x0000000000000000000000000000000000000000\",\"interactions\":\"0x\",\"maker\":\"0xF3ef968DD1687DF8768a960E9D473a3361146A73\",\"makerAsset\":\"0xec8e3f97af8d451e9d15ae09428cbd2a6931e0ba\",\"makingAmount\":\"10000\",\"offsets\":\"0\",\"receiver\":\"0x0000000000000000000000000000000000000000\",\"salt\":\"96743852799\",\"takerAsset\":\"0xe5ae73187d0fed71bda83089488736cadcbf072d\",\"takingAmount\":\"10000000\"}",
                "signature": None,
                "signed_order_type": "tegro",
                "market_id": "80001_0xec8e3f97af8d451e9d15ae09428cbd2a6931e0ba_0xe5ae73187d0fed71bda83089488736cadcbf072d",  # noqa: mock
                "market_symbol": "WETH_USDT"
            },
            "sign_data": {
                "types": {
                    "EIP712Domain": [
                        {
                            "name": "name",
                            "type": "string"
                        },
                        {
                            "name": "version",
                            "type": "string"
                        },
                        {
                            "name": "chainId",
                            "type": "uint256"
                        },
                        {
                            "name": "verifyingContract",
                            "type": "address"
                        }
                    ],
                    "CancelOrder": [
                        {
                            "name": "salt",
                            "type": "uint256"
                        },
                        {
                            "name": "makerAsset",
                            "type": "address"
                        },
                        {
                            "name": "takerAsset",
                            "type": "address"
                        },
                        {
                            "name": "maker",
                            "type": "address"
                        },
                        {
                            "name": "receiver",
                            "type": "address"
                        },
                        {
                            "name": "allowedSender",
                            "type": "address"
                        },
                        {
                            "name": "makingAmount",
                            "type": "uint256"
                        },
                        {
                            "name": "takingAmount",
                            "type": "uint256"
                        },
                        {
                            "name": "offsets",
                            "type": "uint256"
                        },
                        {
                            "name": "interactions",
                            "type": "bytes"
                        }
                    ]
                },
                "primaryType": "CancelOrder",
                "domain": {
                    "name": "Tegro",
                    "version": "5",
                    "chainId": 80001,
                    "verifyingContract": "0xa6bb5cfe9cc68e0affb0bb1785b6efdc2fe8d326"  # noqa: mock
                },
                "message": {
                    "allowedSender": "0x0000000000000000000000000000000000000000",
                    "interactions": "0x",
                    "maker": "0xF3ef968DD1687DF8768a960E9D473a3361146A73",  # noqa: mock
                    "makerAsset": "0xec8e3f97af8d451e9d15ae09428cbd2a6931e0ba",  # noqa: mock
                    "makingAmount": "10000",
                    "offsets": "0",
                    "receiver": "0x0000000000000000000000000000000000000000",
                    "salt": "96743852799",
                    "takerAsset": "0xe5ae73187d0fed71bda83089488736cadcbf072d",  # noqa: mock
                    "takingAmount": "10000000"
                }
            }
        }

    @property
    def approval_reciept(self):
        data = {
            'blockHash': '0x4e3a3754410177e6937ef1f84bba68ea139e8d1a2258c5f85db9f1cd715a1bdd',  # noqa: mock
            'blockNumber': 46147,
            'contractAddress': None,
            'cumulativeGasUsed': 21000,
            'gasUsed': 21000,
            'logs': [],
            'logsBloom': '0x0000000000000000000',  # noqa: mock
            'root': '0x96a8e009d2b88b1483e6941e6812e32263b05683fac202abc622a3e31aed1957',  # noqa: mock
            'transactionHash': '0x5c504ed432cb51138bcf09aa5e8a410dd4a1e204ef84bfed1be16dfba1b22060',  # noqa: mock
            'transactionIndex': 0,
        }
        return data

    @property
    def order_creation_request_successful_mock_response(self):
        data = {
            "clientOrderId": "OID1",
            "order_id": "05881667-3bd3-4fc0-8b0e-db71c8a8fc99",
            "order_hash": "61c97934f3aa9d76d3e08dede89ff03a4c90aa9df09fe1efe055b7132f3b058d",  # noqa: mock
            "marketId": "80002_0x6b94a36d6ff05886d44b3dafabdefe85f09563ba_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",  # noqa: mock
            "side": "buy",
            "baseCurrency": self.base_asset,
            "quoteCurrency": self.quote_asset,
            "baseDecimals": 18,
            "quoteDecimals": 6,
            "contractAddress": "0x6b94a36d6ff05886d44b3dafabdefe85f09563ba",  # noqa: mock
            "quantity": 0.009945,
            "quantityFilled": 0,
            "price": 2010.96,
            "avgPrice": 0,
            "pricePrecision": "2010960000",
            "volumePrecision": "9945498667303179",
            "total": 20,
            "fee": 0,
            "status": "Active",
            "cancel_reason": "",
            "timestamp": "2024-06-12T09:32:27.390651186Z"
        }
        return data

    @property
    def balance_request_mock_response_for_base_and_quote(self):
        return [
            {
                "address": "0xe5ae73187d0fed71bda83089488736cadcbf072d",  # noqa: mock
                "balance": 15,
                "symbol": self.base_asset,
                "decimal": 4,
                "price": 0,
                "price_change_24_h": 0,
                "type": "quote",
                "placed_amount": 22
            },
            {
                "address": "0xe5ae73187d0fed71bda83089488736cadcbf072d",  # noqa: mock
                "balance": 2000,
                "symbol": self.quote_asset,
                "decimal": 4,
                "price": 0,
                "price_change_24_h": 0,
                "type": "quote",
                "placed_amount": 22
            },
        ]

    @property
    def balance_request_mock_response_only_base(self):
        return [
            {
                "address": "0xe5ae73187d0fed71bda83089488736cadcbf072d",  # noqa: mock
                "balance": 15,
                "symbol": self.base_asset,
                "decimal": 4,
                "price": 0,
                "price_change_24_h": 0,
                "type": "quote",
                "placed_amount": 22
            },
        ]

    @property
    def balance_event_websocket_update(self):
        return {}

    @property
    def expected_latest_price(self):
        return 9999.9

    @property
    def expected_supported_order_types(self):
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    @property
    def expected_trading_rule(self):
        return TradingRule(
            trading_pair=self.trading_pair,
            min_order_size= Decimal(0.01),
            min_price_increment=Decimal(
                f'1e-{self.trading_rules_request_mock_response[0]["quote_precision"]}'),
            min_base_amount_increment=Decimal(
                f'1e-{self.trading_rules_request_mock_response[0]["base_precision"]}'),
        )

    @property
    def expected_logged_error_for_erroneous_trading_rule(self):
        erroneous_rule = self.trading_rules_request_erroneous_mock_response[0]
        return f"Error parsing the trading pair rule {erroneous_rule}. Skipping."

    @property
    def expected_exchange_order_id(self):
        return 28

    @property
    def is_order_fill_http_update_included_in_status_update(self) -> bool:
        return True

    @property
    def is_order_fill_http_update_executed_during_websocket_order_event_processing(self) -> bool:
        return False

    @property
    def expected_partial_fill_price(self) -> Decimal:
        return Decimal(10500)

    @property
    def expected_partial_fill_amount(self) -> Decimal:
        return Decimal("0.5")

    @property
    def expected_fill_fee(self) -> TradeFeeBase:
        return DeductedFromReturnsTradeFee(
            percent_token=self.quote_asset,
            flat_fees=[TokenAmount(token=self.quote_asset, amount=Decimal("30"))])

    @property
    def expected_fill_trade_id(self) -> str:
        return str(30000)

    def exchange_symbol_for_tokens(self, base_token: str, quote_token: str) -> str:
        return f"{base_token}_{quote_token}"

    def create_exchange_instance(self):
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        exchange = TegroExchange(
            client_config_map=client_config_map,
            tegro_api_key=self.tegro_api_key,  # noqa: mock
            tegro_api_secret=self.tegro_api_secret,  # noqa: mock
            trading_pairs=[self.trading_pair],
            domain=CONSTANTS.DEFAULT_DOMAIN
        )
        return exchange

    def validate_generated_order_type_request(self, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        self.assertEqual(self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset), request_params["market_symbol"])
        self.assertEqual(self.chain, Decimal(request_params["chain_id"]))
        self.assertEqual(self.tegro_api_key, Decimal(request_params["wallet_address"]))

    def validate_generated_cancel_order_type_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        self.assertEqual([order.exchange_order_id], Decimal(request_params["user_address"]))
        self.assertEqual(self.tegro_api_key, Decimal(request_params["user_address"]))

    def validate_auth_credentials_present(self, request_call: RequestCall):
        self._validate_auth_credentials_taking_parameters_from_argument(
            request_call_tuple=request_call,
            params=request_call.kwargs["params"] or request_call.kwargs["data"]
        )

    def validate_order_creation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = dict(request_call.kwargs["data"])
        self.assertEqual(self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset), request_data["market_symbol"])
        self.assertEqual(order.trade_type.name.lower(), request_data["side"])
        self.assertEqual(self.base_asset, Decimal(request_data["price"]))
        self.assertEqual(self.quote_asset, Decimal(request_data["quote_asset"]))

    def validate_order_cancelation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["data"]
        self.assertIsNone(request_params)

    def validate_order_status_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        self.assertEqual(order.exchange_order_id, request_params["order_id"])

    def validate_trades_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        self.assertIsNone(request_params)

    def configure_generated_typed_data_response(
            self,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.public_rest_url(CONSTANTS.GENERATE_SIGN_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self.generated_typed_data_response
        mock_api.post(regex_url, body=json.dumps(response), callback=callback)
        return response

    def configure_generated_cancel_typed_data_response(
            self,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:

        url = web_utils.public_rest_url(CONSTANTS.GENERATE_ORDER_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self.generated_cancel_typed_data_response
        mock_api.post(regex_url, body=json.dumps(response), callback=callback)
        return response

    def configure_successful_cancelation_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.CANCEL_ORDER_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_cancelation_request_successful_mock_response(order=order)
        mock_api.post(regex_url, body=json.dumps(response), callback=callback)
        return url

    # def configure_successful_creation_order_status_response(
    #         self,
    #         callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
    #     response = self.order_creation_request_successful_mock_response
    #     return response

    def configure_erroneous_cancelation_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.CANCEL_ORDER_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.post(regex_url, status=400, callback=callback)
        return url

    def configure_erroneous_trading_rules_response(
        self,
        mock_api: aioresponses,
        callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> List[str]:

        url = self.trading_rules_url
        response = self.trading_rules_request_erroneous_mock_response
        mock_api.get(url, body=json.dumps(response), callback=callback)
        return [url]

    def configure_order_not_found_error_cancelation_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        url = web_utils.private_rest_url(CONSTANTS.CANCEL_ORDER_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = {"code": -2011, "msg": "Unknown order sent."}
        mock_api.post(regex_url, status=400, body=json.dumps(response), callback=callback)
        return url

    def configure_one_successful_one_erroneous_cancel_all_response(
            self,
            successful_order: InFlightOrder,
            erroneous_order: InFlightOrder,
            mock_api: aioresponses) -> List[str]:
        """
        :return: a list of all configured URLs for the cancelations
        """
        all_urls = []
        url = self.configure_successful_cancelation_response(order=successful_order, mock_api=mock_api)
        all_urls.append(url)
        url = self.configure_erroneous_cancelation_response(order=erroneous_order, mock_api=mock_api)
        all_urls.append(url)
        return all_urls

    def configure_completely_filled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.TEGRO_USER_ORDER_PATH_URL.format(order.exchange_order_id))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_completely_filled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_canceled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.TEGRO_USER_ORDER_PATH_URL.format(order.exchange_order_id))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_canceled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_erroneous_http_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.TRADES_FOR_ORDER_PATH_URL.format(order.exchange_order_id))
        regex_url = re.compile(url + r"\?.*")
        mock_api.get(regex_url, status=400, callback=callback)
        return url

    def configure_open_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        """
        :return: the URL configured
        """
        url = web_utils.private_rest_url(CONSTANTS.TEGRO_USER_ORDER_PATH_URL.format(order.exchange_order_id))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_open_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_http_error_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.TEGRO_USER_ORDER_PATH_URL.format(order.exchange_order_id))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_url, status=401, callback=callback)
        return url

    def configure_partially_filled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.TEGRO_USER_ORDER_PATH_URL.format(order.exchange_order_id))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_partially_filled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_order_not_found_error_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> List[str]:
        url = web_utils.private_rest_url(CONSTANTS.TEGRO_USER_ORDER_PATH_URL.format(order.exchange_order_id))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = {"code": -2013, "msg": "Order does not exist."}
        mock_api.get(regex_url, body=json.dumps(response), status=400, callback=callback)
        return [url]

    def configure_partial_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.TRADES_FOR_ORDER_PATH_URL.format(order.exchange_order_id))
        regex_url = re.compile(url + r"\?.*")
        response = self._order_fills_request_partial_fill_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_token_info_response(
            self,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.public_rest_url(path_url=CONSTANTS.ACCOUNTS_PATH_URL.format(self.chain, self.tegro_api_key))
        regex_url = re.compile(url + r"\?.*")
        response = self._token_info_response()
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_all_pair_price_response(
            self,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.public_rest_url(path_url=CONSTANTS.EXCHANGE_INFO_PATH_LIST_URL.format(self.chain))
        regex_url = re.compile(url + r"\?.*")
        response = self._all_pair_price_response()
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_chain_list_response(
            self,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.public_rest_url(path_url=CONSTANTS.CHAIN_LIST)
        regex_url = re.compile(url + r"\?.*")
        response = self._chain_list_response()
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_full_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.public_rest_url(path_url=CONSTANTS.TRADES_FOR_ORDER_PATH_URL.format(order.exchange_order_id))
        regex_url = re.compile(url + r"\?.*")
        response = self._order_fills_request_full_fill_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return response

    def order_event_for_new_order_websocket_update(self, order: InFlightOrder):
        return {
            "action": "order_submitted",
            "data": {
                "avgPrice": 0,
                "baseCurrency": self.base_asset,
                "baseDecimals": 18,
                "cancel_reason": "",
                "contractAddress": "0x6b94a36d6ff05886d44b3dafabdefe85f09563ba",  # noqa: mock
                "fee": 0,
                "marketId": "80002_0x6b94a36d6ff05886d44b3dafabdefe85f09563ba_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",  # noqa: mock
                "order_hash": "26c9354ee66ced32f74a3c9ba388f80c155012accd5c1b10589d3a9a0d644b73",  # noqa: mock
                "order_id": order.exchange_order_id,
                "price": str(order.price),
                "pricePrecision": "300000000",
                "quantity": str(order.amount),
                "quantityFilled": 0,
                "quoteCurrency": self.quote_asset,
                "quoteDecimals": 6,
                "side": order.trade_type.name.lower(),
                "status": "open",
                "timestamp": 1499405658657,
                "total": 300,
                "volumePrecision": "1000000000000000000"
            }
        }

    def order_event_for_canceled_order_websocket_update(self, order: InFlightOrder):
        return {
            "action": "order_submitted",
            "data": {
                "avgPrice": 0,
                "baseCurrency": self.base_asset,
                "baseDecimals": 18,
                "cancel_reason": "",
                "contractAddress": "0x6b94a36d6ff05886d44b3dafabdefe85f09563ba",  # noqa: mock
                "fee": 0,
                "marketId": "80002_0x6b94a36d6ff05886d44b3dafabdefe85f09563ba_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",  # noqa: mock
                "order_hash": "26c9354ee66ced32f74a3c9ba388f80c155012accd5c1b10589d3a9a0d644b73",  # noqa: mock
                "order_id": order.exchange_order_id,
                "price": str(order.price),
                "pricePrecision": "300000000",
                "quantity": str(order.amount),
                "quantityFilled": 0,
                "quoteCurrency": "alpha",
                "quoteDecimals": 6,
                "side": order.trade_type.name.lower(),
                "status": "cancelled",
                "timestamp": 1499405658657,
                "total": 300,
                "volumePrecision": "1000000000000000000"
            }
        }

    def order_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return {
            "action": "order_trade_processed",
            "data": {
                "avgPrice": 0,
                "baseCurrency": self.base_asset,
                "baseDecimals": 18,
                "cancel_reason": "",
                "contractAddress": "0x6b94a36d6ff05886d44b3dafabdefe85f09563ba",  # noqa: mock
                "fee": 0,
                "marketId": "80002_0x6b94a36d6ff05886d44b3dafabdefe85f09563ba_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",  # noqa: mock
                "order_hash": "26c9354ee66ced32f74a3c9ba388f80c155012accd5c1b10589d3a9a0d644b73",  # noqa: mock
                "order_id": order.exchange_order_id,
                "price": str(order.price),
                "pricePrecision": "300000000",
                "quantity": str(order.amount),
                "quantityFilled": self.expected_fill_fee.flat_fees[0].token,
                "quoteCurrency": self.expected_fill_fee.flat_fees[0].token,
                "quoteDecimals": 6,
                "side": order.trade_type.name.lower(),
                "status": "closed",
                "timestamp": 1499405658657,
                "total": 300,
                "volumePrecision": "1000000000000000000"
            }
        }

    def test_update_order_status_when_canceled(self):
        pass

    # @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange._all_trade_updates_for_order", new_callable=AsyncMock)
    # @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange._request_order_status", new_callable=AsyncMock)
    # @aioresponses()
    # def test_update_order_status_when_filled(self, mock_trades, mock_stats, mock_api):
    #     request_sent_event = asyncio.Event()
    #     self.exchange._set_current_timestamp(1640780000)
    #     self.exchange._last_poll_timestamp = (self.exchange.current_timestamp -
    #                                           10 - 1)

    #     self.exchange.start_tracking_order(
    #         order_id="OID1",
    #         exchange_order_id="EOID1",
    #         trading_pair=self.trading_pair,
    #         order_type=OrderType.LIMIT,
    #         trade_type=TradeType.BUY,
    #         price=Decimal("10000"),
    #         amount=Decimal("1"),
    #     )
    #     order: InFlightOrder = self.exchange.in_flight_orders["OID1"]
    #     mock_trades.return_value = self.trade_event_for_full_fill_websocket_update(order)[0]
    #     mock_stats.return_value = self.configure_full_fill_trade_response(
    #         order=order,
    #         mock_api=mock_api,
    #         callback=lambda *args, **kwargs: request_sent_event.set())

    #     url = web_utils.public_rest_url(CONSTANTS.ORDER_PATH_URL)
    #     regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

    #     order_status = {
    #         "order_id": str(order.exchange_order_id),
    #         "order_hash": "3e45ac4a7c67ab9fd9392c6bdefb0b3de8e498811dd8ac934bbe8cf2c26f72a7",  # noqa: mock
    #         "market_id": "80002_0x6b94a36d6ff05886d44b3dafabdefe85f09563ba_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",  # noqa: mock
    #         "side": order.order_type.name.lower(),
    #         "base_currency": self.base_asset,
    #         "quote_currency": self.quote_asset,
    #         "contract_address": "0xcf9eb56c69ddd4f9cfdef880c828de7ab06b4614",  # noqa: mock
    #         "quantity": str(order.amount),
    #         "quantity_filled": "0",
    #         "quantity_pending": "0",
    #         "price": str(order.price),
    #         "avg_price": "3490",
    #         "price_precision": "3490000000000000000000",
    #         "volume_precision": "3999900000000000000",
    #         "total": "13959.651",
    #         "fee": "0",
    #         "status": "completed",
    #         "cancel": {
    #             "reason": "",
    #             "code": 0
    #         },
    #         "timestamp": 1499827319559
    #     }

    #     mock_api.get(regex_url, body=json.dumps(order_status))

    #     # Simulate the order has been filled with a TradeUpdate
    #     order.completely_filled_event.set()
    #     self.async_run_with_timeout(self.exchange._update_order_status())
    #     self.async_run_with_timeout(order.wait_until_completely_filled())

    #     self.assertTrue(order.is_filled)
    #     self.assertTrue(order.is_done)

    #     buy_event: BuyOrderCompletedEvent = self.buy_order_completed_logger.event_log[0]
    #     self.assertEqual(self.exchange.current_timestamp, buy_event.timestamp)
    #     self.assertEqual(order.client_order_id, buy_event.order_id)
    #     self.assertEqual(order.base_asset, buy_event.base_asset)
    #     self.assertEqual(order.quote_asset, buy_event.quote_asset)
    #     self.assertEqual(Decimal(0), buy_event.base_asset_amount)
    #     self.assertEqual(Decimal(0), buy_event.quote_asset_amount)
    #     self.assertEqual(order.order_type, buy_event.order_type)
    #     self.assertEqual(order.exchange_order_id, buy_event.exchange_order_id)
    #     self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
    #     self.assertTrue(
    #         self._is_logged(
    #             "INFO",
    #             f"BUY order {order.client_order_id} completely filled."
    #         )
    #     )

    # @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange._all_trade_updates_for_order", new_callable=AsyncMock)
    # @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange._request_order_status", new_callable=AsyncMock)
    # @aioresponses()
    # def test_update_order_status_when_cancelled(self, mock_trades, mock_stats, mock_api):
    #     request_sent_event = asyncio.Event()
    #     self.exchange._set_current_timestamp(1640780000)
    #     self.exchange._last_poll_timestamp = (self.exchange.current_timestamp -
    #                                           10 - 1)

    #     self.exchange.start_tracking_order(
    #         order_id="OID1",
    #         exchange_order_id="100234",
    #         trading_pair=self.trading_pair,
    #         order_type=OrderType.LIMIT,
    #         trade_type=TradeType.BUY,
    #         price=Decimal("10000"),
    #         amount=Decimal("1"),
    #     )
    #     order = self.exchange.in_flight_orders["OID1"]

    #     mock_trades.return_value = self.trade_event_for_full_fill_websocket_update(order)[0]
    #     mock_stats.return_value = self.configure_full_fill_trade_response(
    #         order=order,
    #         mock_api=mock_api,
    #         callback=lambda *args, **kwargs: request_sent_event.set())

    #     url = web_utils.public_rest_url(CONSTANTS.ORDER_PATH_URL)
    #     regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

    #     order_status = {
    #         "order_id": str(order.exchange_order_id),
    #         "order_hash": "3e45ac4a7c67ab9fd9392c6bdefb0b3de8e498811dd8ac934bbe8cf2c26f72a7",  # noqa: mock
    #         "market_id": "80002_0x6b94a36d6ff05886d44b3dafabdefe85f09563ba_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",  # noqa: mock
    #         "side": order.order_type.name.lower(),
    #         "base_currency": self.base_asset,
    #         "quote_currency": self.quote_asset,
    #         "contract_address": "0xcf9eb56c69ddd4f9cfdef880c828de7ab06b4614",  # noqa: mock
    #         "quantity": str(order.amount),
    #         "quantity_filled": "0",
    #         "quantity_pending": "0",
    #         "price": str(order.price),
    #         "avg_price": "3490",
    #         "price_precision": "3490000000000000000000",
    #         "volume_precision": "3999900000000000000",
    #         "total": "13959.651",
    #         "fee": "0",
    #         "status": "cancelled",
    #         "cancel": {
    #             "reason": "user_cancel",
    #             "code": 0
    #         },
    #         "timestamp": 1499827319559
    #     }

    #     mock_api.get(regex_url, body=json.dumps(order_status))

    #     self.async_run_with_timeout(self.exchange._update_order_status())

    #     cancel_event: OrderCancelledEvent = self.order_cancelled_logger.event_log[0]
    #     self.assertEqual(self.exchange.current_timestamp, cancel_event.timestamp)
    #     self.assertEqual(order.client_order_id, cancel_event.order_id)
    #     self.assertEqual(order.exchange_order_id, cancel_event.exchange_order_id)
    #     self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
    #     self.assertTrue(
    #         self._is_logged("INFO", f"Successfully canceled order {order.client_order_id}.")
    #     )

    @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange._all_trade_updates_for_order", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange._request_order_status", new_callable=AsyncMock)
    @aioresponses()
    def test_update_order_status_when_order_has_not_changed(self, mock_trades, mock_stats, mock_api):
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._last_poll_timestamp = (self.exchange.current_timestamp -
                                              10 - 1)

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order: InFlightOrder = self.exchange.in_flight_orders["OID1"]

        mock_trades.return_value = self.trade_event_for_full_fill_websocket_update(order)[0]
        mock_stats.return_value = self.configure_full_fill_trade_response(
            order=order,
            mock_api=mock_api,
            callback=lambda *args, **kwargs: request_sent_event.set())

        url = web_utils.public_rest_url(CONSTANTS.ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        order_status = {
            "order_id": str(order.exchange_order_id),
            "order_hash": "3e45ac4a7c67ab9fd9392c6bdefb0b3de8e498811dd8ac934bbe8cf2c26f72a7",  # noqa: mock
            "market_id": "80002_0x6b94a36d6ff05886d44b3dafabdefe85f09563ba_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",  # noqa: mock
            "side": order.order_type.name.lower(),
            "base_currency": self.base_asset,
            "quote_currency": self.quote_asset,
            "contract_address": "0xcf9eb56c69ddd4f9cfdef880c828de7ab06b4614",  # noqa: mock
            "quantity": str(order.amount),
            "quantity_filled": "0",
            "quantity_pending": "0",
            "price": str(order.price),
            "avg_price": "3490",
            "price_precision": "3490000000000000000000",
            "volume_precision": "3999900000000000000",
            "total": "13959.651",
            "fee": "0",
            "status": "open",
            "cancel": {
                "reason": "",
                "code": 0
            },
            "timestamp": 1499827319559
        }

        mock_response = order_status
        mock_api.get(regex_url, body=json.dumps(mock_response))

        self.assertTrue(order.is_open)

        self.async_run_with_timeout(self.exchange._update_order_status())

        self.assertTrue(order.is_open)
        self.assertFalse(order.is_filled)
        self.assertFalse(order.is_done)

    # @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange._all_trade_updates_for_order", new_callable=AsyncMock)
    # @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange._request_order_status", new_callable=AsyncMock)
    # @aioresponses()
    # def test_update_order_status_when_request_fails_marks_order_as_not_found(self, mock_trades, mock_stats, mock_api):
    #     request_sent_event = asyncio.Event()
    #     self.exchange._set_current_timestamp(1640780000)
    #     self.exchange._last_poll_timestamp = (self.exchange.current_timestamp -
    #                                           10 - 1)

    #     self.exchange.start_tracking_order(
    #         order_id="OID1",
    #         exchange_order_id="EOID1",
    #         trading_pair=self.trading_pair,
    #         order_type=OrderType.LIMIT,
    #         trade_type=TradeType.BUY,
    #         price=Decimal("10000"),
    #         amount=Decimal("1"),
    #     )
    #     order: InFlightOrder = self.exchange.in_flight_orders["OID1"]

    #     mock_trades.return_value = self.trade_event_for_full_fill_websocket_update(order)[0]
    #     mock_stats.return_value = self.configure_full_fill_trade_response(
    #         order=order,
    #         mock_api=mock_api,
    #         callback=lambda *args, **kwargs: request_sent_event.set())

    #     url = web_utils.public_rest_url(CONSTANTS.ORDER_PATH_URL)
    #     regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

    #     mock_api.get(regex_url, status=404)

    #     self.async_run_with_timeout(self.exchange._update_order_status())

    #     self.assertTrue(order.is_open)
    #     self.assertFalse(order.is_filled)
    #     self.assertFalse(order.is_done)

    #     self.assertEqual(1, self.exchange._order_tracker._order_not_found_records[order.client_order_id])

    def test_update_order_status_when_filled(self):
        pass

    def test_update_order_status_when_filled_correctly_processed_even_when_trade_fill_update_fails(self):
        pass

    def test_update_order_status_when_order_has_not_changed_and_one_partial_fill(self):
        pass

    def test_cancel_lost_order_raises_failure_event_when_request_fails(self):
        pass

    def test_cancel_order_raises_failure_event_when_request_fails(self):
        pass

    def test_cancel_order_not_found_in_the_exchange(self):
        pass

    def test_cancel_two_orders_with_cancel_all_and_one_fails(self):
        pass

    def test_create_order_fails_and_raises_failure_event(self):
        pass

    def trade_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return [
            {
                "id": self.expected_fill_trade_id,
                "orderId": str(order.exchange_order_id),
                "symbol": self.exchange_symbol_for_tokens(order.base_asset, order.quote_asset),
                "market_id": "80002_0xcabd9e0ea17583d57a972c00a1413295e7c69246_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",  # noqa: mock
                "price": int(order.price),
                "amount": str(order.amount),
                "state": "success",
                "tx_hash": "0x4e240028f16196f421ab266b7ea95acaee4b7fc648e97c19a0f93b3c8f0bb32d",  # noqa: mock
                "timestamp": 1499865549590,
                "fee": str(self.expected_fill_fee.flat_fees[0].amount),
                "taker_type": order.order_type.name.lower(),
                "taker": "0x1870f03410fdb205076718337e9763a91f029280",  # noqa: mock
                "maker": "0x1870f03410fdb205076718337e9763a91f029280"  # noqa: mock
            }
        ]

    def test_create_order_fails_when_trading_rule_error_and_raises_failure_event(self):
        pass

    def test_lost_order_included_in_order_fills_update_and_not_in_order_status_update(self):
        pass

    def test_lost_order_removed_if_not_found_during_order_status_update(self):
        pass

    def test_lost_order_user_stream_full_fill_events_are_processed(self):
        pass

    def test_update_order_status_when_request_fails_marks_order_as_not_found(self):
        pass

    def test_user_stream_update_for_order_full_fill(self):
        pass

    @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange.initialize_market_list", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange.initialize_verified_market", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange.get_all_pairs_prices", new_callable=AsyncMock)
    @aioresponses()
    def test_get_last_trade_prices(self, mock_verified: AsyncMock, mock_list: AsyncMock, _, mock_api):
        mock_list.return_value = self.initialize_market_list_response
        mock_verified.return_value = self.initialize_verified_market_response
        self.exchange._set_trading_pair_symbol_map(None)
        url = f"{CONSTANTS.EXCHANGE_INFO_PATH_LIST_URL.format(self.chain)}"
        resp = {
            "id": "80002_0x6b94a36d6ff05886d44b3dafabdefe85f09563ba_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",  # noqa: mock
            "base_contract_address": "0x6b94a36d6ff05886d44b3dafabdefe85f09563ba",  # noqa: mock
            "quote_contract_address": "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",  # noqa: mock
            "chain_id": self.chain,
            "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "state": "verified",
            "base_symbol": self.base_asset,
            "quote_symbol": self.quote_asset,
            "base_decimal": 18,
            "quote_decimal": 6,
            "base_precision": 6,
            "quote_precision": 10,
            "ticker": {
                "base_volume": 265306,
                "quote_volume": 1423455.3812000754,
                "price": 9999.9,
                "price_change_24h": -85.61,
                "price_high_24h": 10,
                "price_low_24h": 0.2806,
                "ask_low": 0.2806,
                "bid_high": 10
            }
        }

        self.configure_all_pair_price_response(
            mock_api=mock_api
        )
        mock_api.get(url, body=json.dumps(resp))

        ret = self.async_run_with_timeout(coroutine=self.exchange.get_all_pairs_prices())

        self.assertEqual(80002, ret["chain_id"])

    def test_update_balances(self):
        pass

    @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange._make_trading_rules_request", new_callable=AsyncMock)
    @aioresponses()
    def test_update_trading_rules_ignores_rule_with_error(self, mock_rule, mock_api):
        self.exchange._set_current_timestamp(1000)
        url = web_utils.public_rest_url(CONSTANTS.EXCHANGE_INFO_PATH_URL)
        exchange_rules = [
            {
                "id": "80002_0x6b94a36d6ff05886d44b3dafabdefe85f09563ba_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",  # noqa: mock
                "base_contract_address": "0x6b94a36d6ff05886d44b3dafabdefe85f09563ba",  # noqa: mock
                "quote_contract_address": "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",  # noqa: mock
                "chain_id": 80002,
                "symbol": self.ex_trading_pair,
                "state": "ENABLED",
                "baseSymbol": "WETH",
                "quoteSymbol": "USDT",
                "ticker": {
                    "category": 265306,
                }
            }
        ]
        mock_rule.return_value = exchange_rules
        mock_api.get(url, body=json.dumps(exchange_rules))

        self.async_run_with_timeout(coroutine=self.exchange._update_trading_rules())

        self.assertEqual(0, len(self.exchange._trading_rules))

    def _simulate_trading_rules_initialized(self):
        self.exchange._trading_rules = {
            self.trading_pair: TradingRule(
                trading_pair=self.trading_pair,
                min_order_size=Decimal(str(0.01)),
                min_price_increment=Decimal(str(0.0001)),
                min_base_amount_increment=Decimal(str(0.000001)),
            )
        }

    @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange._make_trading_rules_request", new_callable=AsyncMock)
    @aioresponses()
    def test_update_trading_rules(self, mock_list: AsyncMock, mock_api):
        mock_list.return_value = self.all_symbols_request_mock_response
        self.exchange._set_current_timestamp(1000)

        self.configure_trading_rules_response(mock_api=mock_api)

        self.async_run_with_timeout(coroutine=self.exchange._update_trading_rules())

        self.assertTrue(self.trading_pair in self.exchange.trading_rules)
        trading_rule: TradingRule = self.exchange.trading_rules[self.trading_pair]

        self.assertTrue(self.trading_pair in self.exchange.trading_rules)
        self.assertEqual(repr(self.expected_trading_rule), repr(trading_rule))

        trading_rule_with_default_values = TradingRule(trading_pair=self.trading_pair)

        # The following element can't be left with the default value because that breaks quantization in Cython
        self.assertNotEqual(trading_rule_with_default_values.min_base_amount_increment,
                            trading_rule.min_base_amount_increment)
        self.assertNotEqual(trading_rule_with_default_values.min_price_increment,
                            trading_rule.min_price_increment)

    @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange._make_trading_pairs_request", new_callable=AsyncMock)
    @aioresponses()
    def test_all_trading_pairs(self, mock_list: AsyncMock, mock_api):
        mock_list.return_value = self.all_symbols_request_mock_response
        self.exchange._set_trading_pair_symbol_map(None)
        url = f"{CONSTANTS.EXCHANGE_INFO_PATH_LIST_URL.format(self.chain)}"
        resp = [
            {
                "id": "80002_0x6b94a36d6ff05886d44b3dafabdefe85f09563ba_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",  # noqa: mock
                "base_contract_address": "0x6b94a36d6ff05886d44b3dafabdefe85f09563ba",  # noqa: mock
                "quote_contract_address": "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",  # noqa: mock
                "chain_id": 80002,
                "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "state": "verified",
                "base_symbol": self.base_asset,
                "quote_symbol": self.quote_asset,
                "base_decimal": 18,
                "quote_decimal": 6,
                "base_precision": 6,
                "quote_precision": 10,
                "ticker": {
                    "base_volume": 265306,
                    "quote_volume": 1423455.3812000754,
                    "price": 0.9541,
                    "price_change_24h": -85.61,
                    "price_high_24h": 10,
                    "price_low_24h": 0.2806,
                    "ask_low": 0.2806,
                    "bid_high": 10
                }
            },
            {
                "id": "80002_0x6b94a36d6ff05886d44b3dafabdefe85f09563ba_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",  # noqa: mock
                "base_contract_address": "0x6b94a36d6ff05886d44b3dafabdefe85f09563ba",  # noqa: mock
                "quote_contract_address": "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",  # noqa: mock
                "chain_id": 80002,
                "symbol": "SOME_PAIR",
                "state": "verified",
                "base_symbol": "SOME",
                "quote_symbol": "PAIR",
                "base_decimal": 18,
                "quote_decimal": 6,
                "base_precision": 6,
                "quote_precision": 10,
                "ticker": {
                    "base_volume": 265306,
                    "quote_volume": 1423455.3812000754,
                    "price": 0.9541,
                    "price_change_24h": -85.61,
                    "price_high_24h": 10,
                    "price_low_24h": 0.2806,
                    "ask_low": 0.2806,
                    "bid_high": 10
                }
            }
        ]
        mock_api.get(url, body=json.dumps(resp))

        ret = self.async_run_with_timeout(coroutine=self.exchange.all_trading_pairs())

        self.assertEqual(1, len(ret))
        self.assertIn(self.trading_pair, ret)
        self.assertNotIn("SOME-PAIR", ret)

    @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange.get_chain_list", new_callable=AsyncMock)
    @aioresponses()
    def test_get_chain_list(self, mock_list: AsyncMock, mock_api):
        self.exchange._set_trading_pair_symbol_map(None)
        url = f"{CONSTANTS.CHAIN_LIST}"
        resp = [
            {
                "id": 80002,
                "name": "amoy",
                "default_quote_token_symbol": "USDT",
                "default_quote_token_contract_address": "0x7551122E441edBF3fffcBCF2f7FCC636B636482b",  # noqa: mock
                "exchange_contract": "0x1d0888a1552996822b71e89ca735b06aed4b20a4",  # noqa: mock
                "settlement_contract": "0xb365f2c6b51eb5c500f80e9fc1ba771d2de9396e",  # noqa: mock
                "logo": "",
                "min_order_value": "2000000",
                "fee": 0.01,
                "native_token_symbol": "MATIC",
                "native_token_symbol_id": "matic-network",
                "native_token_price": 0.7,
                "gas_per_trade": 400000,
                "gas_price": 5,
                "default_gas_limit": 8000000,
                "Active": True
            }
        ]
        mock_list.return_value = self.configure_chain_list_response(
            mock_api=mock_api
        )
        mock_api.get(url, body=json.dumps(resp))

        ret = self.async_run_with_timeout(coroutine=self.exchange.get_chain_list())

        self.assertEqual(80002, ret[3]["id"])

    @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange.tokens_info", new_callable=AsyncMock)
    @aioresponses()
    def test_tokens_info(self, mock_list: AsyncMock, mock_api):
        resp = [
            {
                "address": "0x7551122e441edbf3fffcbcf2f7fcc636b636482b",
                "balance": "10000",
                "symbol": self.quote_asset,
                "decimal": 6,
                "price": 0,
                "price_change_24_h": 0,
                "type": "quote",
                "placed_amount": 0
            },
            {
                "address": "0x6b94a36d6ff05886d44b3dafabdefe85f09563ba",
                "balance": "10010.7",
                "symbol": self.base_asset,
                "decimal": 18,
                "price": 1000,
                "price_change_24_h": 0,
                "type": "base",
                "placed_amount": 0
            }
        ]
        mock_list.return_value = self.configure_token_info_response(
            mock_api=mock_api
        )
        self.exchange._set_trading_pair_symbol_map(None)
        url = f"{CONSTANTS.ACCOUNTS_PATH_URL.format(self.chain, self.tegro_api_key)}"
        mock_api.get(url, body=json.dumps(resp))

        ret = self.async_run_with_timeout(coroutine=self.exchange.tokens_info())

        self.assertIn(self.base_asset, ret[1]["symbol"])
        self.assertIn(self.quote_asset, ret[0]["symbol"])

    @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange._make_trading_pairs_request", new_callable=AsyncMock)
    @aioresponses()
    def test_all_trading_pairs_does_not_raise_exception(self, mock_list: AsyncMock, mock_api):
        self.exchange._set_trading_pair_symbol_map(None)

        url = f"{CONSTANTS.EXCHANGE_INFO_PATH_LIST_URL.format(self.chain)}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, exception=Exception)

        result: Dict[str] = self.async_run_with_timeout(self.exchange.all_trading_pairs())

        self.assertEqual(0, len(result))

    # def test_create_buy_limit_order_successfully(self):
    #     pass

    def test_create_sell_limit_order_successfully(self):
        pass

    def test_cancel_lost_order_successfully(self):
        pass

    def test_cancel_order_successfully(self):
        pass

    @pytest.mark.asyncio
    @patch('web3.Web3')
    @patch('web3.middleware.geth_poa_middleware')
    def test_approve_allowance(self, mock_geth_poa_middleware, mock_web3):
        mock_w3 = mock_web3.return_value
        mock_contract = Mock()
        mock_contract.functions.approve.return_value.estimate_gas.return_value = 21000
        mock_contract.functions.approve.return_value.build_transaction.return_value = {
            "nonce": 0, "gas": 21000, "gasPrice": 1, "to": "0x123", "value": 0, "data": b"", "chainId": 1
        }
        mock_w3.eth.contract.return_value = mock_contract
        mock_w3.eth.get_transaction_count.return_value = 0
        mock_w3.eth.gas_price = 1
        mock_w3.eth.account.sign_transaction.return_value.rawTransaction = b"signed_tx"
        mock_w3.eth.send_raw_transaction.return_value = "txn_hash"
        mock_w3.eth.wait_for_transaction_receipt.return_value = {"status": 1}
        request_sent_event = asyncio.Event()

        # Run the approve_allowance method
        txn_receipt = self.approval_reciept
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = partial(
            self.exchange.approve_allowance,
            callback=lambda *args, **kwargs: request_sent_event.set(),
            response=txn_receipt
        )

        # Check transaction receipt
        assert txn_receipt == {
            'blockHash': '0x4e3a3754410177e6937ef1f84bba68ea139e8d1a2258c5f85db9f1cd715a1bdd',  # noqa: mock
            'blockNumber': 46147, 'contractAddress': None, 'cumulativeGasUsed': 21000,
            'gasUsed': 21000, 'logs': [], 'logsBloom': '0x0000000000000000000',
            'root': '0x96a8e009d2b88b1483e6941e6812e32263b05683fac202abc622a3e31aed1957',  # noqa: mock
            'transactionHash': '0x5c504ed432cb51138bcf09aa5e8a410dd4a1e204ef84bfed1be16dfba1b22060',  # noqa: mock
            'transactionIndex': 0
        }

    def get_exchange_rules_mock(self) -> Dict:
        exchange_rules = [
            {
                "id": "80002_0x6b94a36d6ff05886d44b3dafabdefe85f09563ba_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",  # noqa: mock
                "base_contract_address": "0x6b94a36d6ff05886d44b3dafabdefe85f09563ba",  # noqa: mock
                "quote_contract_address": "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",  # noqa: mock
                "chain_id": 80002,
                "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "state": "verified",
                "base_symbol": self.base_asset,
                "quote_symbol": self.quote_asset,
                "base_decimal": 18,
                "quote_decimal": 6,
                "base_precision": 6,
                "quote_precision": 10,
                "ticker": {
                    "base_volume": 265306,
                    "quote_volume": 1423455.3812000754,
                    "price": 0.9541,
                    "price_change_24h": -85.61,
                    "price_high_24h": 10,
                    "price_low_24h": 0.2806,
                    "ask_low": 0.2806,
                    "bid_high": 10
                }
            },
            {
                "id": "80002_0x6b94a36d6ff05886d44b3dafabdefe85f09563ba_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",  # noqa: mock
                "base_contract_address": "0x6b94a36d6ff05886d44b3dafabdefe85f09563ba",  # noqa: mock
                "quote_contract_address": "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",  # noqa: mock
                "chain_id": 80002,
                "symbol": "SOME_PAIR",
                "state": "verified",
                "base_symbol": "SOME",
                "quote_symbol": "PAIR",
                "base_decimal": 18,
                "quote_decimal": 6,
                "base_precision": 6,
                "quote_precision": 10,
                "ticker": {
                    "base_volume": 265306,
                    "quote_volume": 1423455.3812000754,
                    "price": 0.9541,
                    "price_change_24h": -85.61,
                    "price_high_24h": 10,
                    "price_low_24h": 0.2806,
                    "ask_low": 0.2806,
                    "bid_high": 10
                }
            }
        ]
        return exchange_rules

    @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange._make_trading_pairs_request", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange._make_trading_rules_request", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange.initialize_market_list", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange.initialize_verified_market", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange._generate_typed_data", new_callable=AsyncMock)
    @patch('hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange.sign_inner')
    @aioresponses()
    def test_create_buy_limit_order_successfully(
        self,
        mock_pair,
        mock_rule,
        mock_list: AsyncMock,
        mock_verified: AsyncMock,
        mock_typed_data: AsyncMock,
        mock_messaage, mock_api
    ):
        mock_pair.return_value = self.all_symbols_request_mock_response
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        tradingrule_url = web_utils.public_rest_url(CONSTANTS.EXCHANGE_INFO_PATH_URL)
        resp = self.get_exchange_rules_mock()
        mock_api.get(tradingrule_url, body=json.dumps(resp))

        mock_list.return_value = self.initialize_market_list_response
        mock_verified.return_value = self.initialize_verified_market_response

        mock_typed_data.return_value = self.configure_generated_typed_data_response(
            mock_api = mock_api)
        mock_messaage.return_value = "0xc5bb16ccc59ae9a3ad1cb8343d4e3351f057c994a97656e1aff8c134e56f7530"  # noqa: mock

        url = web_utils.public_rest_url(CONSTANTS.ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        creation_response = self.order_creation_request_successful_mock_response
        mock_api.post(regex_url,
                      body=json.dumps(creation_response),
                      callback=lambda *args, **kwargs: request_sent_event.set())

        self.test_task = asyncio.get_event_loop().create_task(
            self.exchange._create_order(trade_type=TradeType.BUY,
                                        order_id="OID1",
                                        trading_pair=self.trading_pair,
                                        amount=Decimal("100"),
                                        order_type=OrderType.LIMIT,
                                        price=Decimal("10000")))
        self.async_run_with_timeout(request_sent_event.wait())

        order_id = self.place_buy_order()
        self.async_run_with_timeout(request_sent_event.wait())

        self.configure_successful_creation_order_status_response(
            callback=lambda *args, **kwargs: request_sent_event.set()
        )
        self.assertIn(order_id, self.exchange.in_flight_orders)

        create_event: BuyOrderCreatedEvent = self.buy_order_created_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, create_event.timestamp)
        self.assertEqual(self.trading_pair, create_event.trading_pair)
        self.assertEqual(OrderType.LIMIT, create_event.type)
        self.assertEqual(Decimal("100"), create_event.amount)
        self.assertEqual(Decimal("10000"), create_event.price)
        self.assertEqual(order_id, create_event.order_id)
        self.assertEqual(str(self.expected_exchange_order_id), create_event.exchange_order_id)

        self.assertTrue(
            self.is_logged(
                "INFO",
                f"Created {OrderType.LIMIT.name} {TradeType.BUY.name} order {order_id} for "
                f"{Decimal('100.000000')} {self.trading_pair}.",
            )
        )

    def configure_successful_creation_order_status_response(
        self, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        creation_response = self.order_creation_request_successful_mock_response
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = partial(
            self._callback_wrapper_with_response, callback=callback, response=creation_response
        )
        self.exchange._place_order_responses = mock_queue
        return ""

    @staticmethod
    def _callback_wrapper_with_response(callback: Callable, response: Any, *args, **kwargs):
        callback(args, kwargs)
        if isinstance(response, Exception):
            raise response
        else:
            return response

    # @patch('hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange.sign_inner')
    # @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange._generate_typed_data", new_callable=AsyncMock)
    # @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange.initialize_market_list", new_callable=AsyncMock)
    # @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange.initialize_verified_market", new_callable=AsyncMock)
    # @aioresponses()
    # def test_create_sell_limit_order_successfully(self, mock_list: AsyncMock, mock_verified: AsyncMock, mock_typed_data: AsyncMock, mock_messaage, mock_api):
    #     mock_list.return_value = self.initialize_market_list_response
    #     mock_verified.return_value = self.initialize_verified_market_response
    #     request_sent_event = asyncio.Event()
    #     mock_typed_data.return_value = self.configure_generated_typed_data_response(
    #         mock_api = mock_api)

    #     mock_messaage.return_value = "0xc5bb16ccc59ae9a3ad1cb8343d4e3351f057c994a97656e1aff8c134e56f7530"  # noqa: mock

    #     self._simulate_trading_rules_initialized()
    #     request_sent_event = asyncio.Event()
    #     self.exchange._set_current_timestamp(1640780000)

    #     self.configure_successful_creation_order_status_response(
    #         callback=lambda *args, **kwargs: request_sent_event.set()
    #     )

    #     order_id = self.place_sell_order()
    #     self.async_run_with_timeout(request_sent_event.wait())

    #     self.assertIn(order_id, self.exchange.in_flight_orders)

    #     create_event: SellOrderCreatedEvent = self.sell_order_created_logger.event_log[0]
    #     self.assertEqual(self.exchange.current_timestamp, create_event.timestamp)
    #     self.assertEqual(self.trading_pair, create_event.trading_pair)
    #     self.assertEqual(OrderType.LIMIT, create_event.type)
    #     self.assertEqual(Decimal("100"), create_event.amount)
    #     self.assertEqual(Decimal("10000"), create_event.price)
    #     self.assertEqual(order_id, create_event.order_id)
    #     self.assertEqual(str(self.expected_exchange_order_id), create_event.exchange_order_id)

    #     self.assertTrue(
    #         self.is_logged(
    #             "INFO",
    #             f"Created {OrderType.LIMIT.name} {TradeType.SELL.name} order {order_id} for "
    #             f"{Decimal('100.000000')} {self.trading_pair}.",
    #         )
    #     )

    # @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange._generate_typed_data")
    # @patch('hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange.sign_inner')
    # @aioresponses()
    # def test_cancel_lost_order_successfully(self, mock_messaage, mock_typed_data: AsyncMock, mock_api):
    #     # Mock the Account.from_key method

    #     request_sent_event = asyncio.Event()
    #     self.exchange._set_current_timestamp(1640780000)

    #     self.exchange.start_tracking_order(
    #         order_id = self.client_order_id_prefix + "1",
    #         exchange_order_id = self.exchange_order_id_prefix + "1",
    #         trading_pair = self.trading_pair,
    #         trade_type = TradeType.BUY,
    #         price = Decimal("10000"),
    #         amount = Decimal("100"),
    #         order_type = OrderType.LIMIT,
    #     )

    #     self.assertIn(self.client_order_id_prefix + "1", self.exchange.in_flight_orders)
    #     order: InFlightOrder = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

    #     mock_typed_data.return_value = self.configure_generated_cancel_typed_data_response(
    #         mock_api = mock_api
    #     )
    #     mock_messaage.return_value = "0xc5bb16ccc59ae9a3ad1cb8343d4e3351f057c994a97656e1aff8c134e56f7530"  # noqa: mock

    #     mock_signed_message = MagicMock()
    #     mock_signed_message.signature.hex().return_value = "0xsignature"

    #     for _ in range(self.exchange._order_tracker._lost_order_count_limit + 1):
    #         self.async_run_with_timeout(
    #             self.exchange._order_tracker.process_order_not_found(client_order_id=order.client_order_id))

    #     self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)

    #     self.configure_successful_cancelation_response(
    #         order=order,
    #         mock_api=mock_api,
    #         callback=lambda *args, **kwargs: request_sent_event.set())

    #     self.async_run_with_timeout(self.exchange._cancel_lost_orders())
    #     self.async_run_with_timeout(request_sent_event.wait())

    #     self.assertIn(order.client_order_id, self.exchange._order_tracker.lost_orders)
    #     self.assertTrue(order.is_failure)

    # @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange._generate_cancel_order_typed_data", new_callable=AsyncMock)
    # @patch('hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange.sign_inner')
    # @aioresponses()
    # def test_cancel_order_successfully(self, mock_message, mock_typed_data: AsyncMock, mock_api):
    #     request_sent_event = asyncio.Event()
    #     self.exchange._set_current_timestamp(1640780000)

    #     self.exchange.start_tracking_order(
    #         order_id=self.client_order_id_prefix + "1",
    #         exchange_order_id=self.exchange_order_id_prefix + "1",
    #         trading_pair=self.trading_pair,
    #         trade_type=TradeType.BUY,
    #         price=Decimal("10000"),
    #         amount=Decimal("100"),
    #         order_type=OrderType.LIMIT,
    #     )

    #     self.assertIn(self.client_order_id_prefix + "1", self.exchange.in_flight_orders)
    #     order: InFlightOrder = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

    #     mock_typed_data.return_value = self.configure_generated_cancel_typed_data_response(
    #         mock_api = mock_api
    #     )
    #     mock_message.return_value = "0xc5bb16ccc59ae9a3ad1cb8343d4e3351f057c994a97656e1aff8c134e56f7530"  # noqa: mock

    #     self.configure_successful_cancelation_response(
    #         order=order, mock_api=mock_api, callback=lambda *args, **kwargs: request_sent_event.set()
    #     )

    #     self.exchange.cancel(trading_pair=order.trading_pair, client_order_id=order.client_order_id)
    #     self.async_run_with_timeout(request_sent_event.wait())

    #     self.assertIn(order.client_order_id, self.exchange.in_flight_orders)
    #     self.assertTrue(order.is_pending_cancel_confirmation)

    @aioresponses()
    def test_initialize_verified_market(
            self,
            mock_api) -> str:
        url = web_utils.private_rest_url(CONSTANTS.EXCHANGE_INFO_PATH_URL.format(
            self.chain, "80002_0x6b94a36d6ff05886d44b3dafabdefe85f09563ba_0x7551122e441edbf3fffcbcf2f7fcc636b636482b"),)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self.initialize_verified_market_response
        mock_api.get(regex_url, body=json.dumps(response))
        return response

    @aioresponses()
    def test_initialize_market_list(
            self,
            mock_api) -> str:
        url = web_utils.private_rest_url(CONSTANTS.MARKET_LIST_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self.initialize_market_list_response
        mock_api.get(regex_url, body=json.dumps(response))
        return response

    @aioresponses()
    def test_update_time_synchronizer_raises_cancelled_error(self, mock_api):
        return time.time()

    @aioresponses()
    def test_update_time_synchronizer_failure_is_logged(self, mock_api):
        return time.time()

    @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange._all_trade_updates_for_order", new_callable=AsyncMock)
    @aioresponses()
    def test_update_order_fills_request_parameters(self, mock_fills: AsyncMock, mock_api):
        self.exchange._set_current_timestamp(0)
        self.exchange._last_poll_timestamp = -1

        self.exchange.start_tracking_order(
            order_id="OID1",
            exchange_order_id="100234",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order = self.exchange.in_flight_orders["OID1"]

        mock_fills.return_value = self.configure_full_fill_trade_response(
            order=order, mock_api=mock_api
        )

        url = web_utils.private_rest_url(CONSTANTS.TRADES_FOR_ORDER_PATH_URL.format(order.exchange_order_id))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = []
        mock_api.get(regex_url, body=json.dumps(mock_response))

        self.exchange._set_current_timestamp(1640780000)
        self.exchange._last_poll_timestamp = (self.exchange.current_timestamp -
                                              self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL - 1)
        self.exchange._last_trades_poll_tegro_timestamp = 10
        self.async_run_with_timeout(self.exchange._all_trade_updates_for_order(order))

    # @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange._all_trade_updates_for_order", new_callable=AsyncMock)
    # @aioresponses()
    # def test_update_order_fills_from_trades_with_repeated_fill_triggers_only_one_event(self, mock_fills: AsyncMock, mock_api):

    #     self.exchange._set_current_timestamp(1640780000)
    #     self.exchange._last_poll_timestamp = (self.exchange.current_timestamp -
    #                                           self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL - 1)

    #     self.exchange.start_tracking_order(
    #         order_id="OID1",
    #         exchange_order_id="100234",
    #         trading_pair=self.trading_pair,
    #         order_type=OrderType.LIMIT,
    #         trade_type=TradeType.BUY,
    #         price=Decimal("10000"),
    #         amount=Decimal("1"),
    #     )
    #     order = self.exchange.in_flight_orders["OID1"]
    #     mock_fills.return_value = self.configure_full_fill_trade_response(
    #         order=order, mock_api=mock_api
    #     )

    #     url = web_utils.private_rest_url(CONSTANTS.TRADES_FOR_ORDER_PATH_URL.format(order))
    #     regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

    #     trade_fill_non_tracked_order = {
    #         "id": 30000,
    #         "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
    #         "marketId": "80002_0x6b94a36d6ff05886d44b3dafabdefe85f09563ba_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",  # noqa: mock
    #         "price": "4.00000100",
    #         "amount": "12.00000000",
    #         "state": "success",
    #         "txHash": "0xf962a6b0c436f37a0a3ff049b51507b4e3c25226be752cf3b9944ad27a99a2a5",  # noqa: mock
    #         "timestamp": 1499865549590,
    #         "taker_type": "buy",
    #         "taker": "0x3da2b15eb80b1f7d499d18b6f0b671c838e64cb3",  # noqa: mock
    #         "maker": "0x3da2b15eb80b1f7d499d18b6f0b671c838e64cb3"  # noqa: mock
    #     }

    #     mock_response = [trade_fill_non_tracked_order, trade_fill_non_tracked_order]
    #     mock_api.get(regex_url, body=json.dumps(mock_response))

    #     self.async_run_with_timeout(self.exchange._all_trade_updates_for_order(order))

    #     self.assertEqual(1, len(self.order_filled_logger.event_log))
    #     fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
    #     self.assertEqual(float(trade_fill_non_tracked_order["timestamp"]) * 1e-3, fill_event.timestamp)
    #     self.assertEqual("OID99", fill_event.order_id)
    #     self.assertEqual(self.trading_pair, fill_event.trading_pair)
    #     self.assertEqual(TradeType.BUY, fill_event.trade_type)
    #     self.assertEqual(OrderType.LIMIT, fill_event.order_type)
    #     self.assertEqual(Decimal(trade_fill_non_tracked_order["price"]), fill_event.price)
    #     self.assertEqual(Decimal(trade_fill_non_tracked_order["amount"]), fill_event.amount)
    #     self.assertEqual(0.0, fill_event.trade_fee.percent)
    #     self.assertEqual([
    #         TokenAmount(self.base_asset,
    #                     Decimal(0))],
    #         fill_event.trade_fee.flat_fees)
    #     self.assertTrue(self.is_logged(
    #         "INFO",
    #         f"Recreating missing trade in TradeFill: {trade_fill_non_tracked_order}"
    #     ))

    @patch("hummingbot.connector.utils.get_tracking_nonce")
    def test_client_order_id_on_order(self, mocked_nonce):
        mocked_nonce.return_value = 7

        result = self.exchange.buy(
            trading_pair=self.trading_pair,
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            price=Decimal("2"),
        )
        expected_client_order_id = get_new_client_order_id(
            is_buy=True,
            trading_pair=self.trading_pair,
            hbot_order_id_prefix=CONSTANTS.HBOT_ORDER_ID_PREFIX,
            max_id_len=CONSTANTS.MAX_ORDER_ID_LEN,
        )

        self.assertEqual(result, expected_client_order_id)

        result = self.exchange.sell(
            trading_pair=self.trading_pair,
            amount=Decimal("1"),
            order_type=OrderType.LIMIT,
            price=Decimal("2"),
        )
        expected_client_order_id = get_new_client_order_id(
            is_buy=False,
            trading_pair=self.trading_pair,
            hbot_order_id_prefix=CONSTANTS.HBOT_ORDER_ID_PREFIX,
            max_id_len=CONSTANTS.MAX_ORDER_ID_LEN,
        )

        self.assertEqual(result, expected_client_order_id)

    def test_time_synchronizer_related_request_error_detection(self):
        pass

    def test_place_order_manage_server_overloaded_error_unkown_order(self):
        pass

    def test_place_order_manage_server_overloaded_error_failure(self):
        pass

    def test_format_trading_rules__min_notional_present(self):
        pass

    def test_format_trading_rules__notional_but_no_min_notional_present(self):
        pass

    def _validate_auth_credentials_taking_parameters_from_argument(self,
                                                                   request_call_tuple: RequestCall,
                                                                   params: Dict[str, Any]):
        pass

    def _order_cancelation_request_successful_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "cancelled_order_ids": [str(order.exchange_order_id)],
        }

    def _order_status_request_completely_filled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "order_id": str(order.exchange_order_id),
            "order_hash": "3e45ac4a7c67ab9fd9392c6bdefb0b3de8e498811dd8ac934bbe8cf2c26f72a7",  # noqa: mock
            "market_id": "80002_0x6b94a36d6ff05886d44b3dafabdefe85f09563ba_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",  # noqa: mock
            "side": order.order_type.name.lower(),
            "base_currency": self.base_asset,
            "quote_currency": self.quote_asset,
            "contract_address": "0xcf9eb56c69ddd4f9cfdef880c828de7ab06b4614",  # noqa: mock
            "quantity": str(order.amount),
            "quantity_filled": "0",
            "quantity_pending": "0",
            "price": str(order.price),
            "avg_price": "3490",
            "price_precision": "3490000000000000000000",
            "volume_precision": "3999900000000000000",
            "total": "13959.651",
            "fee": "0",
            "status": "closed",
            "cancel": {
                "reason": "",
                "code": 0
            },
            "timestamp": 1499827319559
        }

    def _order_status_request_canceled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "order_id": str(order.exchange_order_id),
            "order_hash": "3e45ac4a7c67ab9fd9392c6bdefb0b3de8e498811dd8ac934bbe8cf2c26f72a7",  # noqa: mock
            "market_id": "80002_0x6b94a36d6ff05886d44b3dafabdefe85f09563ba_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",  # noqa: mock
            "side": order.order_type.name.lower(),
            "base_currency": self.base_asset,
            "quote_currency": self.quote_asset,
            "contract_address": "0xcf9eb56c69ddd4f9cfdef880c828de7ab06b4614",  # noqa: mock
            "quantity": str(order.amount),
            "quantity_filled": "0",
            "quantity_pending": "0",
            "price": str(order.price),
            "avg_price": "3490",
            "price_precision": "3490000000000000000000",
            "volume_precision": "3999900000000000000",
            "total": "13959.651",
            "fee": "0",
            "status": "cancelled",
            "cancel": {
                "reason": "user_cancel",
                "code": 611
            },
            "timestamp": 1499827319559
        }

    def _order_status_request_open_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "order_id": str(order.exchange_order_id),
            "order_hash": "3e45ac4a7c67ab9fd9392c6bdefb0b3de8e498811dd8ac934bbe8cf2c26f72a7",  # noqa: mock
            "market_id": "80002_0x6b94a36d6ff05886d44b3dafabdefe85f09563ba_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",  # noqa: mock
            "side": order.order_type.name.lower(),
            "base_currency": self.base_asset,
            "quote_currency": self.quote_asset,
            "contract_address": "0xcf9eb56c69ddd4f9cfdef880c828de7ab06b4614",  # noqa: mock
            "quantity": str(order.amount),
            "quantity_filled": "0",
            "quantity_pending": "0",
            "price": str(order.price),
            "avg_price": "3490",
            "price_precision": "3490000000000000000000",
            "volume_precision": "3999900000000000000",
            "total": "13959.651",
            "fee": "0",
            "status": "open",
            "cancel": {
                "reason": "",
                "code": 0
            },
            "timestamp": 1499827319559
        }

    def _order_status_request_partially_filled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "order_id": str(order.exchange_order_id),
            "order_hash": "3e45ac4a7c67ab9fd9392c6bdefb0b3de8e498811dd8ac934bbe8cf2c26f72a7",  # noqa: mock
            "market_id": "80002_0x6b94a36d6ff05886d44b3dafabdefe85f09563ba_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",  # noqa: mock
            "side": order.order_type.name.lower(),
            "base_currency": self.base_asset,
            "quote_currency": self.quote_asset,
            "contract_address": "0xcf9eb56c69ddd4f9cfdef880c828de7ab06b4614",  # noqa: mock
            "quantity": str(order.amount),
            "quantity_filled": "0",
            "quantity_pending": "0",
            "price": str(order.price),
            "avg_price": "3490",
            "price_precision": "3490000000000000000000",
            "volume_precision": "3999900000000000000",
            "total": "13959.651",
            "fee": "0",
            "status": "open",
            "cancel": {
                "reason": "",
                "code": 0
            },
            "timestamp": 1499827319559
        }

    def _order_fills_request_partial_fill_mock_response(self, order: InFlightOrder):
        return [
            {
                "symbol": self.exchange_symbol_for_tokens(order.base_asset, order.quote_asset),
                "market_id": "80002_0xcabd9e0ea17583d57a972c00a1413295e7c69246_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",  # noqa: mock
                "price": str(self.expected_partial_fill_price),
                "amount": str(self.expected_partial_fill_amount),
                "state": "partial",
                "tx_hash": "0x4e240028f16196f421ab266b7ea95acaee4b7fc648e97c19a0f93b3c8f0bb32d",  # noqa: mock
                "timestamp": 1499865549590,
                "fee": str(self.expected_fill_fee.flat_fees[0].amount),
                "taker_type": order.order_type.name.lower(),
                "taker": "0x1870f03410fdb205076718337e9763a91f029280",  # noqa: mock
                "maker": "0x1870f03410fdb205076718337e9763a91f029280"  # noqa: mock
            }
        ]

    def _order_fills_request_full_fill_mock_response(self, order: InFlightOrder):
        return [
            {
                "id": self.expected_fill_trade_id,
                "orderId": str(order.exchange_order_id),
                "symbol": self.exchange_symbol_for_tokens(order.base_asset, order.quote_asset),
                "market_id": "80002_0xcabd9e0ea17583d57a972c00a1413295e7c69246_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",  # noqa: mock
                "price": int(order.price),
                "amount": str(order.amount),
                "state": "success",
                "tx_hash": "0x4e240028f16196f421ab266b7ea95acaee4b7fc648e97c19a0f93b3c8f0bb32d",  # noqa: mock
                "timestamp": 1499865549590,
                "fee": str(self.expected_fill_fee.flat_fees[0].amount),
                "taker_type": order.order_type.name.lower(),
                "taker": "0x1870f03410fdb205076718337e9763a91f029280",  # noqa: mock
                "maker": "0x1870f03410fdb205076718337e9763a91f029280"  # noqa: mock
            }
        ]

    def _token_info_response(self):
        return [
            {
                "address": "0x7551122e441edbf3fffcbcf2f7fcc636b636482b",
                "balance": "10000",
                "symbol": "USDT",
                "decimal": 6,
                "price": 0,
                "price_change_24_h": 0,
                "type": "quote",
                "placed_amount": 0
            },
            {
                "address": "0x6b94a36d6ff05886d44b3dafabdefe85f09563ba",
                "balance": "10010.7",
                "symbol": "WETH",
                "decimal": 18,
                "price": 1000,
                "price_change_24_h": 0,
                "type": "base",
                "placed_amount": 0
            }
        ]

    def _all_pair_price_response(self):
        return {
            "id": "80002_0x6b94a36d6ff05886d44b3dafabdefe85f09563ba_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",  # noqa: mock
            "base_contract_address": "0x6b94a36d6ff05886d44b3dafabdefe85f09563ba",  # noqa: mock
            "quote_contract_address": "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",  # noqa: mock
            "chain_id": self.chain,
            "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            "state": "verified",
            "base_symbol": self.base_asset,
            "quote_symbol": self.quote_asset,
            "base_decimal": 18,
            "quote_decimal": 6,
            "base_precision": 6,
            "quote_precision": 10,
            "ticker": {
                "base_volume": 265306,
                "quote_volume": 1423455.3812000754,
                "price": 9999.9,
                "price_change_24h": -85.61,
                "price_high_24h": 10,
                "price_low_24h": 0.2806,
                "ask_low": 0.2806,
                "bid_high": 10
            }
        }

    def _chain_list_response(self):
        return [
            {
                "id": 80002,
                "name": "amoy",
                "default_quote_token_symbol": "USDT",
                "default_quote_token_contract_address": "0x7551122E441edBF3fffcBCF2f7FCC636B636482b",  # noqa: mock
                "exchange_contract": "0x1d0888a1552996822b71e89ca735b06aed4b20a4",  # noqa: mock
                "settlement_contract": "0xb365f2c6b51eb5c500f80e9fc1ba771d2de9396e",  # noqa: mock
                "logo": "",
                "min_order_value": "2000000",
                "fee": 0.01,
                "native_token_symbol": "MATIC",
                "native_token_symbol_id": "matic-network",
                "native_token_price": 0.7,
                "gas_per_trade": 400000,
                "gas_price": 5,
                "default_gas_limit": 8000000,
                "Active": True
            }
        ]
