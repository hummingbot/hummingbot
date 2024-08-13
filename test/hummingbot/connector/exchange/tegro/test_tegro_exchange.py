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

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.tegro import tegro_constants as CONSTANTS, tegro_web_utils as web_utils
from hummingbot.connector.exchange.tegro.tegro_exchange import TegroExchange
from hummingbot.connector.test_support.exchange_connector_test import AbstractExchangeConnectorTests
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import get_new_client_order_id
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.common import OrderType, PositionAction, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.event.events import (
    BuyOrderCreatedEvent,
    MarketOrderFailureEvent,
    OrderCancelledEvent,
    OrderFilledEvent,
    SellOrderCreatedEvent,
)


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
        cls.chain_id = "base"
        cls.domain = "tegro"  # noqa: mock
        cls.chain = 8453
        cls.rpc_url = "http://mock-rpc-url"  # noqa: mock
        cls.market_id = "80002_0x6b94a36d6ff05886d44b3dafabdefe85f09563ba_0x7551122e441edbf3fffcbcf2f7fcc636b636482b"  # noqa: mock
        cls.client_config_map = ClientConfigAdapter(ClientConfigMap())

    @property
    def all_symbols_url(self):
        url = web_utils.public_rest_url(path_url=CONSTANTS.EXCHANGE_INFO_PATH_LIST_URL.format(self.chain), domain=self.exchange._domain)
        url = f"{url}?page=1&sort_order=desc&sort_by=volume&page_size=20&verified=true"
        return url

    @property
    def latest_prices_url(self):
        url = web_utils.public_rest_url(path_url=CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL.format(self.chain, self.tegro_api_key), domain=self.exchange._domain)
        url = f"{url}"
        return url

    @property
    def network_status_url(self):
        url = web_utils.public_rest_url(CONSTANTS.PING_PATH_URL, domain=self.exchange._domain)
        return url

    @property
    def trading_rules_url(self):
        url = web_utils.public_rest_url(path_url=CONSTANTS.EXCHANGE_INFO_PATH_LIST_URL.format(self.chain), domain=self.exchange._domain)
        url = f"{url}?page=1&sort_order=desc&sort_by=volume&page_size=20&verified=true"
        return url

    @property
    def order_creation_url(self):
        url = web_utils.public_rest_url(CONSTANTS.ORDER_PATH_URL, domain=self.exchange._domain)
        return url

    @property
    def balance_url(self):
        url = web_utils.public_rest_url(CONSTANTS.ACCOUNTS_PATH_URL.format(self.chain, self.tegro_api_key), domain=self.domain)
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

    @property
    def latest_prices_request_mock_response(self):
        return {
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
                    "price": str(self.expected_latest_price),
                    "price_change_24h": -85.61,
                    "price_high_24h": 10,
                    "price_low_24h": 0.2806,
                    "ask_low": 0.2806,
                    "bid_high": 10
                }
        }

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
        return response

    @property
    def network_status_request_successful_mock_response(self):
        return self.all_symbols_request_mock_response

    @property
    def trading_rules_request_mock_response(self):
        return [
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
        ]

    @property
    def trading_rules_request_erroneous_mock_response(self):
        mock_response = [
            {
                "id": "80002_0x6b94a36d6ff05886d44b3dafabdefe85f09563ba_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",  # noqa: mock
                "base_contract_address": "0x6b94a36d6ff05886d44b3dafabdefe85f09563ba",  # noqa: mock
                "quote_contract_address": "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",  # noqa: mock
                "chain_id": 80002,
                "symbol": self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                "state": "verified",
                "base_symbol": self.base_asset,
                "quote_symbol": self.quote_asset,
            },
        ]
        return mock_response

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
    def generated_buy_typed_data_response(self):
        return {
            "limit_order": {
                "chain_id": 80002,
                "base_asset": "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",  # noqa: mock
                "quote_asset": "0x4200000000000000000000000000000000000006",  # noqa: mock
                "side": "buy",
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

    @property
    def generated_sell_typed_data_response(self):
        return {
            "limit_order": {
                "chain_id": 80002,
                "base_asset": "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",  # noqa: mock
                "quote_asset": "0x4200000000000000000000000000000000000006",  # noqa: mock
                "side": "sell",
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
            "order_id": "05881667-3bd3-4fc0-8b0e-db71c8a8fc99",  # noqa: mock
            "order_hash": "61c97934f3aa9d76d3e08dede89ff03a4c90aa9df09fe1efe055b7132f3b058d",  # noqa: mock
            "marketId": "80002_0x6b94a36d6ff05886d44b3dafabdefe85f09563ba_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",  # noqa: mock
            "side": "buy",
            "baseCurrency": self.base_asset,
            "quoteCurrency": self.quote_asset,
            "baseDecimals": 18,
            "quoteDecimals": 6,
            "contractAddress": "0x6b94a36d6ff05886d44b3dafabdefe85f09563ba",  # noqa: mock
            "quantity": 0.009945,
            "quantity_filled": 0,
            "price": 2010.96,
            "avgPrice": 0,
            "pricePrecision": "2010960000",
            "volumePrecision": "9945498667303179",
            "total": 20,
            "fee": 0,
            "status": "Active",
            "cancel_reason": "",
            "timestamp": 1640780000
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
        return "05881667-3bd3-4fc0-8b0e-db71c8a8fc99"  # noqa: mock

    @property
    def is_order_fill_http_update_included_in_status_update(self) -> bool:
        return True

    @property
    def is_order_fill_http_update_executed_during_websocket_order_event_processing(self) -> bool:
        return True

    @property
    def expected_partial_fill_price(self) -> Decimal:
        return Decimal(10500)

    @property
    def expected_partial_fill_amount(self) -> Decimal:
        return Decimal("0.5")

    @property
    def expected_fill_fee(self) -> TradeFeeBase:
        return AddedToCostTradeFee(
            percent_token=self.quote_asset, flat_fees=[TokenAmount(token=self.quote_asset, amount=Decimal("30"))]
        )

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
            chain_name=self.chain_id,
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
        pass

    def validate_order_creation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = json.loads(request_call.kwargs["data"])
        self.assertEqual(self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset), request_data["market_symbol"])
        self.assertEqual(order.trade_type.name.lower(), request_data["side"])

    def validate_order_cancelation_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = json.loads(request_call.kwargs["data"])
        self.assertEqual(order.exchange_order_id, request_params["order_ids"][0])

    def validate_order_status_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        self.assertEqual(8453, request_params["chain_id"])

    def validate_trades_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        self.assertIsNone(request_params)

    def configure_generated_cancel_typed_data_response(
            self,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:

        url = web_utils.public_rest_url(CONSTANTS.GENERATE_ORDER_URL)
        response = self.generated_cancel_typed_data_response
        mock_api.post(url, body=json.dumps(response), callback=callback)
        return response

    def configure_successful_cancelation_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.public_rest_url(CONSTANTS.CANCEL_ORDER_URL)
        response = self._order_cancelation_request_successful_mock_response(order=order)
        mock_api.post(url, body=json.dumps(response), callback=callback)
        return url

    def _configure_balance_response(
            self,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:

        url = self.balance_url
        response = self.balance_request_mock_response_for_base_and_quote
        mock_api.get(
            re.compile(f"{url}"),
            body=json.dumps(response),
            callback=callback)
        return url

    def configure_erroneous_cancelation_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.public_rest_url(CONSTANTS.CANCEL_ORDER_URL)
        mock_api.post(url, status=400, callback=callback)
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
        url = web_utils.public_rest_url(CONSTANTS.CANCEL_ORDER_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = {"code": -2011, "msg": "Order not found"}
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
        url = web_utils.public_rest_url(CONSTANTS.TEGRO_USER_ORDER_PATH_URL.format(self.tegro_api_key))
        url = f"{url}?chain_id={self.chain}&order_id={order.exchange_order_id}"
        response = self._order_status_request_completely_filled_mock_response(order=order)
        mock_api.get(url, body=json.dumps(response), callback=callback)
        return url

    def configure_canceled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.public_rest_url(CONSTANTS.ORDER_LIST.format(self.tegro_api_key))
        url = f"{url}?chain_id={self.chain}&order_id={order.exchange_order_id}"
        response = self._order_status_request_canceled_mock_response(order=order)
        mock_api.get(url, body=json.dumps(response), callback=callback)
        return url

    def configure_erroneous_http_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.public_rest_url(path_url=CONSTANTS.TRADES_FOR_ORDER_PATH_URL.format(order.exchange_order_id))
        response = [
            {
                "id": self.expected_fill_trade_id,
                "symbol": self.exchange_symbol_for_tokens(order.base_asset, order.quote_asset),
                "market_id": "80002_0xcabd9e0ea17583d57a972c00a1413295e7c69246_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",  # noqa: mock
                "price": str(self.expected_partial_fill_price),
                "amount": str(self.expected_partial_fill_amount),
                "state": "partial",
                "tx_hash": "0x4e240028f16196f421ab266b7ea95acaee4b7fc648e97c19a0f93b3c8f0bb32d",  # noqa: mock
                "timestamp": 1499865549590,
                "fee": 0,
                "taker_fee": "0.03",
                "maker_fee": str(self.expected_fill_fee.flat_fees[0].amount),
                "is_buyer_maker": True,
                "taker": "0x1870f03410fdb205076718337e9763a91f029280",  # noqa: mock
                "maker": "0x1870f03410fdb205076718337e9763a91f029280"  # noqa: mock
            }
        ]
        mock_api.get(url, body=json.dumps(response), callback=callback)
        return url

    def configure_open_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        """
        :return: the URL configured
        """
        url = web_utils.public_rest_url(CONSTANTS.TEGRO_USER_ORDER_PATH_URL.format(self.tegro_api_key))
        response = self._order_status_request_open_mock_response(order=order)
        mock_api.get(url, body=json.dumps(response), callback=callback)
        return url

    def configure_http_error_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.public_rest_url(CONSTANTS.TEGRO_USER_ORDER_PATH_URL.format(self.tegro_api_key))
        url = f"{url}?chain_id={self.chain}&order_id={order.exchange_order_id}"
        mock_api.get(url, status=401, callback=callback)
        return url

    def configure_partially_filled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.public_rest_url(CONSTANTS.TEGRO_USER_ORDER_PATH_URL.format(self.tegro_api_key))
        url = f"{url}?chain_id={self.chain}&order_id={order.exchange_order_id}"
        response = self._order_status_request_partially_filled_mock_response(order=order)
        mock_api.get(url, body=json.dumps(response), callback=callback)
        return url

    def configure_order_not_found_error_order_status_response(
        self, order: InFlightOrder, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> List[str]:
        url = web_utils.public_rest_url(CONSTANTS.TEGRO_USER_ORDER_PATH_URL.format(self.tegro_api_key))
        url = f"{url}?chain_id={self.chain}&order_id={order.exchange_order_id}"
        response = self._order_status_request_completely_filled_mock_response(order=order)
        mock_api.get(url, body=json.dumps(response), callback=callback)
        return url

    def configure_partial_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.public_rest_url(path_url=CONSTANTS.TRADES_FOR_ORDER_PATH_URL.format(order.exchange_order_id))
        response = self._order_fills_request_partial_fill_mock_response(order=order)
        mock_api.get(url, body=json.dumps(response), callback=callback)
        return url

    def configure_token_info_response(
            self,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.public_rest_url(path_url=CONSTANTS.ACCOUNTS_PATH_URL.format(self.chain, self.tegro_api_key))
        response = self._token_info_response()
        mock_api.get(url, body=json.dumps(response), callback=callback)
        return url

    def configure_all_pair_price_response(
            self,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.public_rest_url(path_url=CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL.format(self.chain, "80002_0x6b94a36d6ff05886d44b3dafabdefe85f09563ba_0x7551122e441edbf3fffcbcf2f7fcc636b636482b"))
        response = self._all_pair_price_response()
        mock_api.get(url, body=json.dumps(response), callback=callback)
        return url

    def configure_chain_list_response(
            self,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.public_rest_url(path_url=CONSTANTS.CHAIN_LIST)
        response = self._chain_list_response()
        mock_api.get(url, body=json.dumps(response), callback=callback)
        return url

    def configure_full_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.public_rest_url(path_url=CONSTANTS.TRADES_FOR_ORDER_PATH_URL.format(order.exchange_order_id))
        response = self.trade_update(order=order)
        mock_api.get(url, body=json.dumps(response), callback=callback)
        return url

    def configure_no_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.public_rest_url(path_url=CONSTANTS.TRADES_FOR_ORDER_PATH_URL.format(order.exchange_order_id))
        response = self.trade_no_fills_update(order=order)
        mock_api.get(url, body=json.dumps(response), callback=callback)
        return url

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
                "quantity_filled": 0,
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
                "quantity_filled": 0,
                "quoteCurrency": self.quote_asset,
                "quoteDecimals": 6,
                "side": order.trade_type.name.lower(),
                "status": "cancelled",
                "cancel": {
                    "reason": "user_cancel",
                    "code": 611
                },
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
                "quantity_filled": 0,
                "quoteCurrency": self.quote_asset,
                "quoteDecimals": 6,
                "side": order.trade_type.name.lower(),
                "status": "completed",
                "timestamp": 1499405658657,
                "total": 300,
                "volumePrecision": "1000000000000000000"
            }
        }

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

    def test_node_rpc_mainnet(self):
        exchange = TegroExchange(
            client_config_map = ClientConfigAdapter(ClientConfigMap()),
            domain = "tegro",
            tegro_api_key = "tegro_api_key",
            tegro_api_secret = "tegro_api_secret",
            chain_name = "base")
        self.assertEqual(exchange.node_rpc, "base", "Mainnet rpc params should be base")

    def test_node_rpc_testnet(self):
        """Test chain property for mainnet domain"""
        exchange = TegroExchange(
            client_config_map = ClientConfigAdapter(ClientConfigMap()),
            domain = "tegro_testnet",
            tegro_api_key = "tegro_api_key",
            tegro_api_secret = "tegro_api_secret",
            chain_name = "polygon")
        self.assertEqual(exchange.node_rpc, "tegro_polygon_testnet", "Testnet rpc params should be polygon")

    def test_node_rpc_empty(self):
        """Test chain property for mainnet domain"""
        exchange = TegroExchange(
            client_config_map = ClientConfigAdapter(ClientConfigMap()),
            domain = "",
            tegro_api_key = "",
            tegro_api_secret = "",
            chain_name = "")
        self.assertEqual(exchange.node_rpc, "", "Empty rpc params should be empty")

    def test_chain_mainnet(self):
        """Test chain property for mainnet domain"""
        exchange = TegroExchange(
            client_config_map = ClientConfigAdapter(ClientConfigMap()),
            domain = "tegro",
            tegro_api_key = "tegro_api_key",
            tegro_api_secret = "tegro_api_secret",
            chain_name = "base")
        self.assertEqual(exchange.chain, 8453, "Mainnet chain ID should be 8453")

    def test_chain_testnet(self):
        """Test chain property for mainnet domain"""
        exchange = TegroExchange(
            client_config_map = ClientConfigAdapter(ClientConfigMap()),
            domain = "tegro_testnet",
            tegro_api_key = "tegro_api_key",
            tegro_api_secret = "tegro_api_secret",
            chain_name = "polygon")
        self.assertEqual(exchange.chain, 80002, "Mainnet chain ID should be 8453")

    def test_chain_invalid(self):
        """Test chain property with an empty domain"""
        exchange = TegroExchange(
            client_config_map = ClientConfigAdapter(ClientConfigMap()),
            domain = "",
            tegro_api_key = "",
            tegro_api_secret = "",
            chain_name = "")
        self.assertEqual(exchange.chain, 8453, "Chain should be an base by default for empty domains")

    @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange._update_balances", new_callable=AsyncMock)
    @aioresponses()
    def test_update_balances(
        self,
        mock_balance,
        mock_api
    ):
        mock_balance.return_value = self.balance_request_mock_response_for_base_and_quote
        response = self.balance_request_mock_response_for_base_and_quote

        response = self.balance_request_mock_response_only_base

        url = self._configure_balance_response(mock_api=mock_api)
        mock_api.get(url, body=json.dumps(response))

        ret = self.async_run_with_timeout(coroutine=self.exchange._update_balances())
        available_balances = self.exchange.available_balances
        total_balances = self.exchange.get_all_balances()

        self.assertNotIn(self.quote_asset, available_balances)
        self.assertNotIn(self.quote_asset, total_balances)
        self.assertEqual(Decimal("15"), ret[0]["balance"])
        self.assertEqual(Decimal("2000"), ret[1]["balance"])

    def configure_generate_typed_data(
            self,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        """
        :return: the URL configured
        """
        url = web_utils.public_rest_url(CONSTANTS.GENERATE_ORDER_URL)
        response = self.generated_cancel_typed_data_response
        mock_api.get(url, body=json.dumps(response), callback=callback)
        return url

    def configure_generate_sell_typed_data(
            self,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        """
        :return: the URL configured
        """
        url = web_utils.public_rest_url(CONSTANTS.GENERATE_ORDER_URL)
        response = self.generated_cancel_typed_data_response
        mock_api.get(url, body=json.dumps(response), callback=callback)
        return url

    def configure_generate_cancel_order_typed_data(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        """
        :return: the URL configured
        """
        url = web_utils.public_rest_url(CONSTANTS.GENERATE_ORDER_URL)
        response = self.generated_buy_typed_data_response
        mock_api.get(url, body=json.dumps(response), callback=callback)
        return url

    @patch('hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange.sign_inner')
    @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange._generate_cancel_order_typed_data", new_callable=AsyncMock)
    @aioresponses()
    def test_cancel_order_not_found_in_the_exchange(self, mock_messaage, mock_typed_data: AsyncMock, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        request_sent_event = asyncio.Event()

        self.exchange.start_tracking_order(
            order_id = self.client_order_id_prefix + "1",
            exchange_order_id = str(self.expected_exchange_order_id),
            trading_pair = self.trading_pair,
            order_type = OrderType.LIMIT,
            trade_type = TradeType.BUY,
            price = Decimal("10000"),
            amount = Decimal("1"),
        )

        self.assertIn(self.client_order_id_prefix + "1", self.exchange.in_flight_orders)
        order = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]
        self.configure_generate_cancel_order_typed_data(
            order=order, mock_api=mock_api, callback=lambda *args, **kwargs: request_sent_event.set())
        mock_typed_data.return_value = self.generated_sell_typed_data_response
        mock_messaage.return_value = "0xc5bb16ccc59ae9a3ad1cb8343d4e3351f057c994a97656e1aff8c134e56f7530"  # noqa: mock

        self.configure_order_not_found_error_cancelation_response(
            order=order, mock_api=mock_api, callback=lambda *args, **kwargs: request_sent_event.set()
        )

        self.exchange.cancel(trading_pair=self.trading_pair, client_order_id=self.client_order_id_prefix + "1")
        self.async_run_with_timeout(request_sent_event.wait())

        self.assertFalse(order.is_done)
        self.assertFalse(order.is_failure)
        self.assertFalse(order.is_cancelled)

        self.assertIn(order.client_order_id, self.exchange._order_tracker.all_updatable_orders)
        self.assertEqual(1, self.exchange._order_tracker._order_not_found_records[order.client_order_id])

    @patch('hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange.sign_inner')
    @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange._generate_cancel_order_typed_data", new_callable=AsyncMock)
    @aioresponses()
    def test_cancel_lost_order_raises_failure_event_when_request_fails(self, mock_messaage, mock_typed_data: AsyncMock, mock_api):
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "1",
            exchange_order_id=self.exchange_order_id_prefix + "1",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("100"),
            order_type=OrderType.LIMIT,
        )

        self.assertIn(self.client_order_id_prefix + "1", self.exchange.in_flight_orders)
        order = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]
        self.configure_generate_cancel_order_typed_data(
            order=order, mock_api=mock_api, callback=lambda *args, **kwargs: request_sent_event.set())
        mock_typed_data.return_value = self.generated_sell_typed_data_response
        mock_messaage.return_value = "0xc5bb16ccc59ae9a3ad1cb8343d4e3351f057c994a97656e1aff8c134e56f7530"  # noqa: mock

        for _ in range(self.exchange._order_tracker._lost_order_count_limit + 1):
            self.async_run_with_timeout(
                self.exchange._order_tracker.process_order_not_found(client_order_id=order.client_order_id))

        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)

        url = self.configure_erroneous_cancelation_response(
            order=order,
            mock_api=mock_api,
            callback=lambda *args, **kwargs: request_sent_event.set())

        self.async_run_with_timeout(self.exchange._cancel_lost_orders())
        self.async_run_with_timeout(request_sent_event.wait())

        if url:
            cancel_request = self._all_executed_requests(mock_api, url)[0]
            self.validate_order_cancelation_request(
                order=order,
                request_call=cancel_request)

        self.assertIn(order.client_order_id, self.exchange._order_tracker.lost_orders)
        self.assertEquals(0, len(self.order_cancelled_logger.event_log))
        self.assertTrue(
            any(
                log.msg.startswith(f"Failed to cancel order {order.client_order_id}")
                for log in self.log_records
            )
        )

    @patch('hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange.sign_inner')
    @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange._generate_cancel_order_typed_data", new_callable=AsyncMock)
    @aioresponses()
    def test_cancel_order_raises_failure_event_when_request_fails(self, mock_messaage, mock_typed_data: AsyncMock, mock_api):
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "1",
            exchange_order_id=self.exchange_order_id_prefix + "1",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("100"),
            order_type=OrderType.LIMIT,
        )

        self.assertIn(self.client_order_id_prefix + "1", self.exchange.in_flight_orders)
        order = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

        mock_typed_data.return_value = self.generated_sell_typed_data_response
        mock_messaage.return_value = "0xc5bb16ccc59ae9a3ad1cb8343d4e3351f057c994a97656e1aff8c134e56f7530"  # noqa: mock

        url = self.configure_erroneous_cancelation_response(
            order=order,
            mock_api=mock_api,
            callback=lambda *args, **kwargs: request_sent_event.set())

        self.exchange.cancel(trading_pair=self.trading_pair, client_order_id=self.client_order_id_prefix + "1")
        self.async_run_with_timeout(request_sent_event.wait())

        if url != "":
            cancel_request = self._all_executed_requests(mock_api, url)[0]
            self.validate_order_cancelation_request(
                order=order,
                request_call=cancel_request)

        self.assertEquals(0, len(self.order_cancelled_logger.event_log))
        self.assertTrue(
            any(
                log.msg.startswith(f"Failed to cancel order {order.client_order_id}")
                for log in self.log_records
            )
        )

    @patch('hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange.sign_inner')
    @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange._generate_cancel_order_typed_data", new_callable=AsyncMock)
    @aioresponses()
    def test_cancel_two_orders_with_cancel_all_and_one_fails(self, mock_messaage, mock_typed_data: AsyncMock, mock_api):
        self.exchange._set_current_timestamp(1640780000)

        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "1",
            exchange_order_id=self.exchange_order_id_prefix + "1",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("100"),
            order_type=OrderType.LIMIT,
        )

        self.assertIn(self.client_order_id_prefix + "1", self.exchange.in_flight_orders)
        order1 = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

        mock_typed_data.return_value = self.generated_sell_typed_data_response
        mock_messaage.return_value = "0xc5bb16ccc59ae9a3ad1cb8343d4e3351f057c994a97656e1aff8c134e56f7530"  # noqa: mock

        self.exchange.start_tracking_order(
            order_id="12",
            exchange_order_id="5",
            trading_pair=self.trading_pair,
            trade_type=TradeType.SELL,
            price=Decimal("11000"),
            amount=Decimal("90"),
            order_type=OrderType.LIMIT,
        )

        self.assertIn("12", self.exchange.in_flight_orders)
        order2 = self.exchange.in_flight_orders["12"]

        urls = self.configure_one_successful_one_erroneous_cancel_all_response(
            successful_order=order1,
            erroneous_order=order2,
            mock_api=mock_api)

        cancellation_results = self.async_run_with_timeout(self.exchange.cancel_all(10))

        for url in urls:
            self._all_executed_requests(mock_api, url)[0]

        self.assertEqual(2, len(cancellation_results))
        self.assertEqual(CancellationResult(order1.client_order_id, True), cancellation_results[0])
        self.assertEqual(CancellationResult(order2.client_order_id, False), cancellation_results[1])

        if self.exchange.is_cancel_request_in_exchange_synchronous:
            self.assertEqual(1, len(self.order_cancelled_logger.event_log))
            cancel_event: OrderCancelledEvent = self.order_cancelled_logger.event_log[0]
            self.assertEqual(self.exchange.current_timestamp, cancel_event.timestamp)
            self.assertEqual(order1.client_order_id, cancel_event.order_id)

            self.assertTrue(
                self.is_logged(
                    "INFO",
                    f"Successfully canceled order {order1.client_order_id}."
                )
            )

    @patch('hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange.sign_inner')
    @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange._generate_typed_data", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange._make_trading_pairs_request", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange._make_trading_rules_request", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange.initialize_market_list", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange.initialize_verified_market", new_callable=AsyncMock)
    @aioresponses()
    def test_create_order_fails_and_raises_failure_event(
        self,
        mock_pair,
        mock_rule,
        mock_list: AsyncMock,
        mock_verified: AsyncMock,
        mock_typed_data: AsyncMock,
        mock_messaage,
        mock_api,
    ):
        mock_pair.return_value = self.all_symbols_request_mock_response
        mock_rule.return_value = self.trading_rules_request_mock_response

        mock_list.return_value = self.initialize_market_list_response
        mock_verified.return_value = self.initialize_verified_market_response

        mock_typed_data.return_value = self.generated_buy_typed_data_response
        self.configure_generate_typed_data(
            mock_api=mock_api, callback=lambda *args, **kwargs: request_sent_event.set())
        mock_messaage.return_value = "0xc5bb16ccc59ae9a3ad1cb8343d4e3351f057c994a97656e1aff8c134e56f7530"  # noqa: mock
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)
        url = self.order_creation_url
        mock_api.post(url,
                      status=400,
                      callback=lambda *args, **kwargs: request_sent_event.set())

        order_id = self.place_buy_order()
        self.async_run_with_timeout(request_sent_event.wait())

        order_request = self._all_executed_requests(mock_api, url)[0]
        self.assertNotIn(order_id, self.exchange.in_flight_orders)
        order_to_validate_request = InFlightOrder(
            client_order_id=order_id,
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("100"),
            creation_timestamp=self.exchange.current_timestamp,
            price=Decimal("10000")
        )
        self.validate_order_creation_request(
            order=order_to_validate_request,
            request_call=order_request)

        self.assertEquals(0, len(self.buy_order_created_logger.event_log))
        failure_event: MarketOrderFailureEvent = self.order_failure_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, failure_event.timestamp)
        self.assertEqual(OrderType.LIMIT, failure_event.order_type)
        self.assertEqual(order_id, failure_event.order_id)

        self.assertTrue(
            self.is_logged(
                "INFO",
                f"Order {order_id} has failed. Order Update: OrderUpdate(trading_pair='{self.trading_pair}', "
                f"update_timestamp={self.exchange.current_timestamp}, new_state={repr(OrderState.FAILED)}, "
                f"client_order_id='{order_id}', exchange_order_id=None, misc_updates=None)"
            )
        )

    @aioresponses()
    def test_update_order_status_when_canceled(self, mock_api):
        pass

    @aioresponses()
    def test_update_order_status_when_filled_correctly_processed_even_when_trade_fill_update_fails(self, mock_api):
        pass

    @aioresponses()
    def test_update_order_status_when_request_fails_marks_order_as_not_found(self, mock_api):
        pass

    @aioresponses()
    def test_update_order_status_when_order_has_not_changed_and_one_partial_fill(self, mock_api):
        pass

    @aioresponses()
    def test_lost_order_removed_if_not_found_during_order_status_update(self, mock_api):
        # Disabling this test because the connector has not been updated yet to validate
        # order not found during status update (check _is_order_not_found_during_status_update_error)
        pass

    def test_create_order_update_with_order_status_data(self):
        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "1",
            exchange_order_id=str(self.expected_exchange_order_id),
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            position_action=PositionAction.OPEN,
        )
        order: InFlightOrder = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

        order_statuses = [
            {"status": "closed", "quantity_pending": "0", "timestamp": 1622471123, "order_id": "12345"},
            {"status": "open", "quantity_filled": "0", "timestamp": 1622471123, "order_id": "12346"},
            {"status": "open", "quantity_filled": "0.5", "timestamp": 1622471123, "order_id": "12347"},
            {"status": "closed", "quantity_pending": "1", "timestamp": 1622471123, "order_id": "12348"},
            {"status": "cancelled", "cancel": {"code": 611}, "timestamp": 1622471123, "order_id": "12349"},
            {"status": "cancelled", "cancel": {"code": 712}, "timestamp": 1622471123, "order_id": "12350"},
        ]

        expected_states = [
            OrderState.FILLED,
            OrderState.OPEN,
            OrderState.PARTIALLY_FILLED,
            OrderState.PENDING_CANCEL,
            OrderState.CANCELED,
            OrderState.FAILED,
        ]

        for order_status, expected_state in zip(order_statuses, expected_states):
            order_update = self.exchange._create_order_update_with_order_status_data(order_status, order)
            self.assertEqual(order_update.new_state, expected_state)
            self.assertEqual(order_update.trading_pair, order.trading_pair)
            self.assertEqual(order_update.client_order_id, order.client_order_id)
            self.assertEqual(order_update.exchange_order_id, str(order_status["order_id"]))
            self.assertEqual(order_update.update_timestamp, order_status["timestamp"] * 1e-3)

    @aioresponses()
    def test_update_order_status_when_filled(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        request_sent_event = asyncio.Event()

        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "1",
            exchange_order_id=str(self.expected_exchange_order_id),
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            position_action=PositionAction.OPEN,
        )
        order: InFlightOrder = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

        self.configure_completely_filled_order_status_response(
            order=order,
            mock_api=mock_api,
            callback=lambda *args, **kwargs: request_sent_event.set())

        if self.is_order_fill_http_update_included_in_status_update:
            self.configure_full_fill_trade_response(
                order=order,
                mock_api=mock_api,
                callback=lambda *args, **kwargs: request_sent_event.set())
        else:
            # If the fill events will not be requested with the order status, we need to manually set the event
            # to allow the ClientOrderTracker to process the last status update
            order.completely_filled_event.set()
            request_sent_event.set()

        self.async_run_with_timeout(self.exchange._update_order_status())
        # Execute one more synchronization to ensure the async task that processes the update is finished
        self.async_run_with_timeout(request_sent_event.wait())

        self.async_run_with_timeout(order.wait_until_completely_filled())
        self.assertTrue(order.is_done)
        self.assertTrue(order.is_filled)

        if self.is_order_fill_http_update_included_in_status_update:
            fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
            self.assertEqual(self.exchange.current_timestamp, fill_event.timestamp)
            self.assertEqual(order.client_order_id, fill_event.order_id)
            self.assertEqual(order.trading_pair, fill_event.trading_pair)
            self.assertEqual(order.trade_type, fill_event.trade_type)
            self.assertEqual(order.order_type, fill_event.order_type)
            self.assertEqual(order.price, fill_event.price)
            self.assertEqual(order.amount, fill_event.amount)
            self.assertEqual(self.expected_fill_fee, fill_event.trade_fee)

        self.assertEqual(0, len(self.buy_order_completed_logger.event_log))
        self.assertIn(order.client_order_id, self.exchange._order_tracker.all_fillable_orders)
        self.assertFalse(
            self.is_logged(
                "INFO",
                f"BUY order {order.client_order_id} completely filled."
            )
        )

    @aioresponses()
    def test_lost_order_included_in_order_fills_update_and_not_in_order_status_update(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        request_sent_event = asyncio.Event()

        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "1",
            exchange_order_id=str(self.expected_exchange_order_id),
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
            position_action=PositionAction.OPEN,
        )
        order: InFlightOrder = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

        for _ in range(self.exchange._order_tracker._lost_order_count_limit + 1):
            self.async_run_with_timeout(
                self.exchange._order_tracker.process_order_not_found(client_order_id=order.client_order_id))

        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)

        self.configure_completely_filled_order_status_response(
            order=order,
            mock_api=mock_api,
            callback=lambda *args, **kwargs: request_sent_event.set())

        if self.is_order_fill_http_update_included_in_status_update:
            self.configure_full_fill_trade_response(
                order=order,
                mock_api=mock_api,
                callback=lambda *args, **kwargs: request_sent_event.set())
        else:
            # If the fill events will not be requested with the order status, we need to manually set the event
            # to allow the ClientOrderTracker to process the last status update
            order.completely_filled_event.set()
            request_sent_event.set()

        self.async_run_with_timeout(self.exchange._update_order_status())
        # Execute one more synchronization to ensure the async task that processes the update is finished
        self.async_run_with_timeout(request_sent_event.wait())

        self.async_run_with_timeout(order.wait_until_completely_filled())
        self.assertTrue(order.is_done)
        self.assertTrue(order.is_failure)

        if self.is_order_fill_http_update_included_in_status_update:
            fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
            self.assertEqual(self.exchange.current_timestamp, fill_event.timestamp)
            self.assertEqual(order.client_order_id, fill_event.order_id)
            self.assertEqual(order.trading_pair, fill_event.trading_pair)
            self.assertEqual(order.trade_type, fill_event.trade_type)
            self.assertEqual(order.order_type, fill_event.order_type)
            self.assertEqual(order.price, fill_event.price)
            self.assertEqual(order.amount, fill_event.amount)
            self.assertEqual(self.expected_fill_fee, fill_event.trade_fee)

        self.assertEqual(0, len(self.buy_order_completed_logger.event_log))
        self.assertIn(order.client_order_id, self.exchange._order_tracker.all_fillable_orders)
        self.assertFalse(
            self.is_logged(
                "INFO",
                f"BUY order {order.client_order_id} completely filled."
            )
        )

        request_sent_event.clear()

        # Configure again the response to the order fills request since it is required by lost orders update logic
        self.configure_full_fill_trade_response(
            order=order,
            mock_api=mock_api,
            callback=lambda *args, **kwargs: request_sent_event.set())

        self.async_run_with_timeout(self.exchange._update_lost_orders_status())
        # Execute one more synchronization to ensure the async task that processes the update is finished
        self.async_run_with_timeout(request_sent_event.wait())

        self.assertTrue(order.is_done)
        self.assertTrue(order.is_failure)

        self.assertEqual(1, len(self.order_filled_logger.event_log))
        self.assertEqual(0, len(self.buy_order_completed_logger.event_log))
        # self.assertNotIn(order.client_order_id, self.exchange._order_tracker.all_fillable_orders)
        self.assertFalse(
            self.is_logged(
                "INFO",
                f"BUY order {order.client_order_id} completely filled."
            )
        )

    @patch('hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange.sign_inner')
    @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange._generate_typed_data", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange._make_trading_pairs_request", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange._make_trading_rules_request", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange.initialize_market_list", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange.initialize_verified_market", new_callable=AsyncMock)
    @aioresponses()
    def test_create_order_fails_when_trading_rule_error_and_raises_failure_event(
        self,
        mock_pair,
        mock_rule,
        mock_list: AsyncMock,
        mock_verified: AsyncMock,
        mock_typed_data: AsyncMock,
        mock_messaage,
        mock_api,
    ):
        mock_pair.return_value = self.all_symbols_request_mock_response
        mock_rule.return_value = self.trading_rules_request_mock_response

        mock_list.return_value = self.initialize_market_list_response
        mock_verified.return_value = self.initialize_verified_market_response

        mock_typed_data.return_value = self.generated_buy_typed_data_response

        mock_messaage.return_value = "0xc5bb16ccc59ae9a3ad1cb8343d4e3351f057c994a97656e1aff8c134e56f7530"  # noqa: mock

        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        url = self.order_creation_url
        mock_api.post(url,
                      status=400,
                      callback=lambda *args, **kwargs: request_sent_event.set())

        order_id_for_invalid_order = self.place_buy_order(
            amount=Decimal("0.0001"), price=Decimal("0.0001")
        )
        # The second order is used only to have the event triggered and avoid using timeouts for tests
        order_id = self.place_buy_order()
        self.async_run_with_timeout(request_sent_event.wait(), timeout=3)

        self.assertNotIn(order_id_for_invalid_order, self.exchange.in_flight_orders)
        self.assertNotIn(order_id, self.exchange.in_flight_orders)

        self.assertEquals(0, len(self.buy_order_created_logger.event_log))
        failure_event: MarketOrderFailureEvent = self.order_failure_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, failure_event.timestamp)
        self.assertEqual(OrderType.LIMIT, failure_event.order_type)
        self.assertEqual(order_id_for_invalid_order, failure_event.order_id)

        self.assertTrue(
            self.is_logged(
                "WARNING",
                "Buy order amount 0.0001 is lower than the minimum order "
                "size 0.01. The order will not be created, increase the "
                "amount to be higher than the minimum order size."
            )
        )
        self.assertTrue(
            self.is_logged(
                "INFO",
                f"Order {order_id} has failed. Order Update: OrderUpdate(trading_pair='{self.trading_pair}', "
                f"update_timestamp={self.exchange.current_timestamp}, new_state={repr(OrderState.FAILED)}, "
                f"client_order_id='{order_id}', exchange_order_id=None, misc_updates=None)"
            )
        )

    def trade_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return None

    def trade_update(self, order: InFlightOrder):
        return [
            {
                "id": self.expected_fill_trade_id,
                "symbol": self.exchange_symbol_for_tokens(order.base_asset, order.quote_asset),
                "market_id": "80002_0xcabd9e0ea17583d57a972c00a1413295e7c69246_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",  # noqa: mock
                "price": str(order.price),
                "amount": str(order.amount),
                "state": "success",
                "tx_hash": "0x4e240028f16196f421ab266b7ea95acaee4b7fc648e97c19a0f93b3c8f0bb32d",  # noqa: mock
                "timestamp": 1499865549590,
                "fee": 0,
                "taker_fee": "0.03",
                "maker_fee": str(self.expected_fill_fee.flat_fees[0].amount),
                "is_buyer_maker": True,
                "taker": "0x1870f03410fdb205076718337e9763a91f029280",  # noqa: mock
                "maker": "0x1870f03410fdb205076718337e9763a91f029280"  # noqa: mock
            }
        ]

    def trade_no_fills_update(self, order: InFlightOrder):
        return []

    @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange.initialize_verified_market", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange.initialize_market_list", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange._make_trading_pairs_request", new_callable=AsyncMock)
    @aioresponses()
    def test_get_last_trade_prices(self, mock_list: AsyncMock, mock_pair: AsyncMock, mock_verified: AsyncMock, mock_api):
        mock_pair.return_value = self.initialize_market_list_response
        mock_list.return_value = self.initialize_market_list_response
        mock_verified.return_value = self.initialize_verified_market_response
        self.exchange._set_trading_pair_symbol_map(None)

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
        url = CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL.format(self.chain, resp['id'])
        self.configure_all_pair_price_response(
            mock_api=mock_api
        )
        mock_api.get(url, body=json.dumps(resp))

        latest_prices: Dict[str, float] = self.async_run_with_timeout(
            self.exchange.get_last_traded_prices(trading_pairs=[self.trading_pair])
        )
        self.assertEqual(1, len(latest_prices))
        self.assertEqual(self.expected_latest_price, latest_prices[self.trading_pair])

    def _simulate_trading_rules_initialized(self):
        rule = {
            "quote_precision": 10,
            "base_precision": 6
        }
        min_price_inc = Decimal(f"1e-{rule['quote_precision']}")
        step_size = Decimal(f'1e-{rule["base_precision"]}')
        self.exchange._trading_rules = {
            self.trading_pair: TradingRule(
                trading_pair=self.trading_pair,
                min_order_size=Decimal(str(0.01)),
                min_price_increment=Decimal(min_price_inc),
                min_base_amount_increment=Decimal(step_size),
            )
        }

    @aioresponses()
    def test_get_chain_list(self, mock_api):
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._set_trading_pair_symbol_map(None)
        url = web_utils.public_rest_url(CONSTANTS.CHAIN_LIST)
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
        self.configure_chain_list_response(
            mock_api=mock_api,
            callback=lambda *args, **kwargs: request_sent_event.set())
        mock_api.get(url, body=json.dumps(resp))

        ret = self.async_run_with_timeout(coroutine=self.exchange.get_chain_list())
        self.assertEqual(80002, ret[0]["id"])

    @aioresponses()
    def test_tokens_info(self, mock_api):
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)
        url = web_utils.public_rest_url(CONSTANTS.ACCOUNTS_PATH_URL.format(self.chain, self.tegro_api_key))
        resp = [
            {
                "address": "0x7551122e441edbf3fffcbcf2f7fcc636b636482b",
                "symbol": self.quote_asset,
            },
            {
                "address": "0x6b94a36d6ff05886d44b3dafabdefe85f09563ba",
                "symbol": self.base_asset,
            }
        ]
        self.configure_token_info_response(
            mock_api=mock_api,
            callback=lambda *args, **kwargs: request_sent_event.set())
        mock_api.get(url, body=json.dumps(resp))
        ret = self.async_run_with_timeout(coroutine=self.exchange.tokens_info())
        self.assertIn(self.base_asset, ret[1]["symbol"])
        self.assertIn(self.quote_asset, ret[0]["symbol"])

    @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange._make_trading_pairs_request", new_callable=AsyncMock)
    @aioresponses()
    def test_all_trading_pairs_does_not_raise_exception(self, mock_list: AsyncMock, mock_api):
        self.exchange._set_trading_pair_symbol_map(None)

        url = f"{CONSTANTS.EXCHANGE_INFO_PATH_LIST_URL.format(self.chain)}"

        mock_api.get(url, exception=Exception)

        result: Dict[str] = self.async_run_with_timeout(self.exchange.all_trading_pairs())

        self.assertEqual(0, len(result))

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

    @patch('hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange.sign_inner')
    @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange._generate_typed_data", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange._make_trading_pairs_request", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange._make_trading_rules_request", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange.initialize_market_list", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange.initialize_verified_market", new_callable=AsyncMock)
    @aioresponses()
    def test_create_buy_limit_order_successfully(
        self,
        mock_pair,
        mock_rule,
        mock_list: AsyncMock,
        mock_verified: AsyncMock,
        mock_typed_data: AsyncMock,
        mock_messaage,
        mock_api,
        # order_res_mock: AsyncMock
    ):
        mock_pair.return_value = self.all_symbols_request_mock_response
        mock_rule.return_value = self.trading_rules_request_mock_response

        mock_list.return_value = self.initialize_market_list_response
        mock_verified.return_value = self.initialize_verified_market_response

        mock_typed_data.return_value = self.generated_buy_typed_data_response
        self.configure_generate_typed_data(
            mock_api=mock_api, callback=lambda *args, **kwargs: request_sent_event.set())
        mock_messaage.return_value = "0xc5bb16ccc59ae9a3ad1cb8343d4e3351f057c994a97656e1aff8c134e56f7530"  # noqa: mock
        self._simulate_trading_rules_initialized()

        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        url = self.order_creation_url

        creation_response = self.order_creation_request_successful_mock_response

        mock_api.post(url,
                      body=json.dumps(creation_response),
                      callback=lambda *args, **kwargs: request_sent_event.set())

        order_id = self.place_buy_order()
        self.async_run_with_timeout(request_sent_event.wait())

        order_request = self._all_executed_requests(mock_api, url)[0]
        self.assertIn(order_id, self.exchange.in_flight_orders)
        self.validate_order_creation_request(
            order=self.exchange.in_flight_orders[order_id],
            request_call=order_request)

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
        return creation_response

    @staticmethod
    def _callback_wrapper_with_response(callback: Callable, response: Any, *args, **kwargs):
        callback(args, kwargs)
        if isinstance(response, Exception):
            raise response
        else:
            return response

    @patch('hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange.sign_inner')
    @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange._generate_typed_data", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange._make_trading_pairs_request", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange._make_trading_rules_request", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange.initialize_market_list", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange.initialize_verified_market", new_callable=AsyncMock)
    @aioresponses()
    def test_create_sell_limit_order_successfully(
        self,
        mock_pair,
        mock_rule,
        mock_list: AsyncMock,
        mock_verified: AsyncMock,
        mock_typed_data: AsyncMock,
        mock_messaage,
        mock_api,
        # order_res_mock: AsyncMock
    ):
        mock_pair.return_value = self.all_symbols_request_mock_response
        mock_rule.return_value = self.trading_rules_request_mock_response

        mock_list.return_value = self.initialize_market_list_response
        mock_verified.return_value = self.initialize_verified_market_response

        mock_typed_data.return_value = self.generated_sell_typed_data_response
        self.configure_generate_sell_typed_data(
            mock_api=mock_api, callback=lambda *args, **kwargs: request_sent_event.set())
        mock_messaage.return_value = "0xc5bb16ccc59ae9a3ad1cb8343d4e3351f057c994a97656e1aff8c134e56f7530"  # noqa: mock
        self._simulate_trading_rules_initialized()

        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        url = self.order_creation_url

        creation_response = self.order_creation_request_successful_mock_response

        mock_api.post(url,
                      body=json.dumps(creation_response),
                      callback=lambda *args, **kwargs: request_sent_event.set())

        order_id = self.place_sell_order()
        self.async_run_with_timeout(request_sent_event.wait())

        order_request = self._all_executed_requests(mock_api, url)[0]
        self.assertIn(order_id, self.exchange.in_flight_orders)
        self.validate_order_creation_request(
            order=self.exchange.in_flight_orders[order_id],
            request_call=order_request)

        create_event: SellOrderCreatedEvent = self.sell_order_created_logger.event_log[0]
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
                f"Created {OrderType.LIMIT.name} {TradeType.SELL.name} order {order_id} for "
                f"{Decimal('100.000000')} {self.trading_pair}.",
            )
        )

    @patch('hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange.sign_inner')
    @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange._generate_cancel_order_typed_data", new_callable=AsyncMock)
    @aioresponses()
    def test_cancel_lost_order_successfully(self, mock_messaage, mock_typed_data: AsyncMock, mock_api):

        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        self.exchange.start_tracking_order(
            order_id = self.client_order_id_prefix + "1",
            exchange_order_id = self.exchange_order_id_prefix + "1",
            trading_pair = self.trading_pair,
            trade_type = TradeType.BUY,
            price = Decimal("10000"),
            amount = Decimal("100"),
            order_type = OrderType.LIMIT,
        )

        self.assertIn(self.client_order_id_prefix + "1", self.exchange.in_flight_orders)
        order: InFlightOrder = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

        mock_typed_data.return_value = self.generated_sell_typed_data_response
        mock_messaage.return_value = "0xc5bb16ccc59ae9a3ad1cb8343d4e3351f057c994a97656e1aff8c134e56f7530"  # noqa: mock

        for _ in range(self.exchange._order_tracker._lost_order_count_limit + 1):
            self.async_run_with_timeout(
                self.exchange._order_tracker.process_order_not_found(client_order_id=order.client_order_id))

        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)

        url = self.configure_successful_cancelation_response(
            order=order,
            mock_api=mock_api,
            callback=lambda *args, **kwargs: request_sent_event.set())

        self.async_run_with_timeout(self.exchange._cancel_lost_orders())
        self.async_run_with_timeout(request_sent_event.wait())

        if url:
            cancel_request = self._all_executed_requests(mock_api, url)[0]
            self.validate_order_cancelation_request(
                order=order,
                request_call=cancel_request)

        if self.exchange.is_cancel_request_in_exchange_synchronous:
            self.assertNotIn(order.client_order_id, self.exchange._order_tracker.lost_orders)
            self.assertFalse(order.is_cancelled)
            self.assertTrue(order.is_failure)
            self.assertEqual(0, len(self.order_cancelled_logger.event_log))
        else:
            self.assertIn(order.client_order_id, self.exchange._order_tracker.lost_orders)
            self.assertTrue(order.is_failure)

    @patch('hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange.sign_inner')
    @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange._generate_cancel_order_typed_data", new_callable=AsyncMock)
    @aioresponses()
    def test_cancel_order_successfully(
        self,
        mock_messaage,
        mock_typed_data: AsyncMock,
        mock_api
    ):
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        mock_typed_data.return_value = self.generated_sell_typed_data_response
        mock_messaage.return_value = "0xc5bb16ccc59ae9a3ad1cb8343d4e3351f057c994a97656e1aff8c134e56f7530"  # noqa: mock

        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "1",
            exchange_order_id=self.exchange_order_id_prefix + "1",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("100"),
            order_type=OrderType.LIMIT,
        )

        self.assertIn(self.client_order_id_prefix + "1", self.exchange.in_flight_orders)
        order: InFlightOrder = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

        url = self.configure_successful_cancelation_response(
            order=order,
            mock_api=mock_api,
            callback=lambda *args, **kwargs: request_sent_event.set())

        self.exchange.cancel(trading_pair=order.trading_pair, client_order_id=order.client_order_id)
        self.async_run_with_timeout(request_sent_event.wait())

        if url != "":
            cancel_request = self._all_executed_requests(mock_api, url)[0]
            self.validate_order_cancelation_request(
                order=order,
                request_call=cancel_request)

        if self.exchange.is_cancel_request_in_exchange_synchronous:
            self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
            self.assertTrue(order.is_cancelled)
            cancel_event: OrderCancelledEvent = self.order_cancelled_logger.event_log[0]
            self.assertEqual(self.exchange.current_timestamp, cancel_event.timestamp)
            self.assertEqual(order.client_order_id, cancel_event.order_id)

            self.assertTrue(
                self.is_logged(
                    "INFO",
                    f"Successfully canceled order {order.client_order_id}."
                )
            )
        else:
            self.assertIn(order.client_order_id, self.exchange.in_flight_orders)
            self.assertTrue(order.is_pending_cancel_confirmation)

    @aioresponses()
    def test_initialize_verified_market(
            self,
            mock_api) -> str:
        url = web_utils.public_rest_url(CONSTANTS.EXCHANGE_INFO_PATH_URL.format(
            self.chain, "80002_0x6b94a36d6ff05886d44b3dafabdefe85f09563ba_0x7551122e441edbf3fffcbcf2f7fcc636b636482b"),)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self.initialize_verified_market_response
        mock_api.get(regex_url, body=json.dumps(response))
        return response

    @aioresponses()
    def test_initialize_market_list(
            self,
            mock_api) -> str:
        url = web_utils.public_rest_url(CONSTANTS.MARKET_LIST_PATH_URL)
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

    @patch('hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange.sign_inner')
    @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange._generate_typed_data", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange._make_trading_pairs_request", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange._make_trading_rules_request", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange.initialize_market_list", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange.initialize_verified_market", new_callable=AsyncMock)
    @aioresponses()
    def test_place_order_manage_server_overloaded_error_unkown_order(self,
                                                                     mock_pair,
                                                                     mock_rule,
                                                                     mock_list: AsyncMock,
                                                                     mock_verified: AsyncMock,
                                                                     mock_typed_data: AsyncMock,
                                                                     mock_messaage,
                                                                     mock_api):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._last_poll_timestamp = (self.exchange.current_timestamp -
                                              self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL - 1)
        mock_pair.return_value = self.all_symbols_request_mock_response
        mock_rule.return_value = self.trading_rules_request_mock_response

        mock_list.return_value = self.initialize_market_list_response
        mock_verified.return_value = self.initialize_verified_market_response

        mock_typed_data.return_value = self.generated_buy_typed_data_response

        mock_messaage.return_value = "0xc5bb16ccc59ae9a3ad1cb8343d4e3351f057c994a97656e1aff8c134e56f7530"  # noqa: mock

        url = web_utils.public_rest_url(CONSTANTS.ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_response = {"code": -1003, "msg": "Unknown error, please check your request or try again later."}
        mock_api.post(regex_url, body=json.dumps(mock_response), status=503)

        o_id, transact_time = self.async_run_with_timeout(self.exchange._place_order(
            order_id="test_order_id",
            trading_pair=self.trading_pair,
            amount=Decimal("1"),
            trade_type=TradeType.BUY,
            order_type=OrderType.LIMIT,
            price=Decimal("2"),
        ))
        self.assertEqual(o_id, "Unknown")

    @patch('hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange.sign_inner')
    @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange._generate_typed_data", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange._make_trading_pairs_request", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange._make_trading_rules_request", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange.initialize_market_list", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.tegro.tegro_exchange.TegroExchange.initialize_verified_market", new_callable=AsyncMock)
    @aioresponses()
    def test_place_order_manage_server_overloaded_error_failure(
        self,
        mock_pair,
        mock_rule,
        mock_list: AsyncMock,
        mock_verified: AsyncMock,
        mock_typed_data: AsyncMock,
        mock_messaage,
        mock_api
    ):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._last_poll_timestamp = (self.exchange.current_timestamp -
                                              self.exchange.UPDATE_ORDER_STATUS_MIN_INTERVAL - 1)

        mock_pair.return_value = self.all_symbols_request_mock_response
        mock_rule.return_value = self.trading_rules_request_mock_response

        mock_list.return_value = self.initialize_market_list_response
        mock_verified.return_value = self.initialize_verified_market_response

        mock_typed_data.return_value = self.generated_buy_typed_data_response

        mock_messaage.return_value = "0xc5bb16ccc59ae9a3ad1cb8343d4e3351f057c994a97656e1aff8c134e56f7530"  # noqa: mock

        url = web_utils.public_rest_url(CONSTANTS.ORDER_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_response = {"code": -1003, "msg": "Service Unavailable."}
        mock_api.post(regex_url, body=json.dumps(mock_response), status=503)

        self.assertRaises(
            IOError,
            self.async_run_with_timeout,
            self.exchange._place_order(
                order_id="test_order_id",
                trading_pair=self.trading_pair,
                amount=Decimal("1"),
                trade_type=TradeType.BUY,
                order_type=OrderType.LIMIT,
                price=Decimal("2"),
            ))

        mock_response = {"code": -1003, "msg": "Internal error; unable to process your request. Please try again."}
        mock_api.post(regex_url, body=json.dumps(mock_response), status=503)

        self.assertRaises(
            IOError,
            self.async_run_with_timeout,
            self.exchange._place_order(
                order_id="test_order_id",
                trading_pair=self.trading_pair,
                amount=Decimal("1"),
                trade_type=TradeType.BUY,
                order_type=OrderType.LIMIT,
                price=Decimal("2"),
            ))

    def _order_cancelation_request_successful_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "cancelled_order_ids": [order.exchange_order_id],
        }

    def _order_status_request_completely_filled_mock_response(self, order: InFlightOrder) -> Any:
        return {
            "order_id": order.exchange_order_id,
            "order_hash": "3e45ac4a7c67ab9fd9392c6bdefb0b3de8e498811dd8ac934bbe8cf2c26f72a7",  # noqa: mock
            "market_id": "80002_0x6b94a36d6ff05886d44b3dafabdefe85f09563ba_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",  # noqa: mock
            "side": "buy",
            "base_currency": self.base_asset,
            "quote_currency": self.quote_asset,
            "contract_address": "0xcf9eb56c69ddd4f9cfdef880c828de7ab06b4614",  # noqa: mock
            "quantity": str(order.amount),
            "quantity_filled": str(order.amount),
            "quantity_pending": "0",
            "price": str(order.price),
            "avg_price": "3490",
            "price_precision": "3490000000000000000000",
            "volume_precision": "3999900000000000000",
            "total": "13959.651",
            "fee": "0",
            "status": "completed",
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

    def _order_status_request_failed_mock_response(self, order: InFlightOrder) -> Any:
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
                "code": 711
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
            "quantity_filled": "5",
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
            "quantity_filled": "0.5",
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
                "id": self.expected_fill_trade_id,
                "symbol": self.exchange_symbol_for_tokens(order.base_asset, order.quote_asset),
                "market_id": "80002_0xcabd9e0ea17583d57a972c00a1413295e7c69246_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",  # noqa: mock
                "price": str(self.expected_partial_fill_price),
                "amount": str(self.expected_partial_fill_amount),
                "state": "partial",
                "tx_hash": "0x4e240028f16196f421ab266b7ea95acaee4b7fc648e97c19a0f93b3c8f0bb32d",  # noqa: mock
                "timestamp": 1499865549590,
                "fee": 0,
                "taker_fee": "0.03",
                "maker_fee": str(self.expected_fill_fee.flat_fees[0].amount),
                "is_buyer_maker": True,
                "taker": "0x1870f03410fdb205076718337e9763a91f029280",  # noqa: mock
                "maker": "0x1870f03410fdb205076718337e9763a91f029280"  # noqa: mock
            }
        ]

    def _order_fills_request_full_fill_mock_response(self, order: InFlightOrder):
        self._simulate_trading_rules_initialized()
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
                "fee": 0,
                "taker_fee": "0.03",
                "maker_fee": str(self.expected_fill_fee.flat_fees[0].amount),
                "is_buyer_maker": True,
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
