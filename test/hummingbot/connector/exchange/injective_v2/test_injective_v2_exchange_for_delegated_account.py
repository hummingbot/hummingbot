import asyncio
import base64
import json
from collections import OrderedDict
from decimal import Decimal
from functools import partial
from test.hummingbot.connector.exchange.injective_v2.programmable_query_executor import ProgrammableQueryExecutor
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from unittest.mock import AsyncMock, patch

from aioresponses import aioresponses
from aioresponses.core import RequestCall
from bidict import bidict
from grpc import RpcError
from pyinjective.composer import Composer
from pyinjective.core.market import SpotMarket
from pyinjective.core.token import Token
from pyinjective.wallet import Address, PrivateKey

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.injective_v2.injective_v2_exchange import InjectiveV2Exchange
from hummingbot.connector.exchange.injective_v2.injective_v2_utils import (
    InjectiveConfigMap,
    InjectiveDelegatedAccountMode,
    InjectiveMessageBasedTransactionFeeCalculatorMode,
    InjectiveTestnetNetworkMode,
)
from hummingbot.connector.gateway.gateway_in_flight_order import GatewayInFlightOrder
from hummingbot.connector.test_support.exchange_connector_test import AbstractExchangeConnectorTests
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.market_order import MarketOrder
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_row import OrderBookRow
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    MarketOrderFailureEvent,
    OrderCancelledEvent,
    OrderFilledEvent,
)
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import safe_gather


class InjectiveV2ExchangeTests(AbstractExchangeConnectorTests.ExchangeConnectorTests):

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "INJ"
        cls.quote_asset = "USDT"
        cls.base_asset_denom = "inj"
        cls.quote_asset_denom = "peggy0x87aB3B4C8661e07D6372361211B96ed4Dc36B1B5"  # noqa: mock
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.market_id = "0x0611780ba69656949525013d947713300f56c37b6175e02f26bffa495c3208fe"  # noqa: mock

        _, grantee_private_key = PrivateKey.generate()
        cls.trading_account_private_key = grantee_private_key.to_hex()
        cls.trading_account_subaccount_index = 0
        _, granter_private_key = PrivateKey.generate()
        granter_address = Address(bytes.fromhex(granter_private_key.to_public_key().to_hex()))
        cls.portfolio_account_injective_address = granter_address.to_acc_bech32()
        cls.portfolio_account_subaccount_index = 0
        portfolio_adderss = Address.from_acc_bech32(cls.portfolio_account_injective_address)
        cls.portfolio_account_subaccount_id = portfolio_adderss.get_subaccount_id(
            index=cls.portfolio_account_subaccount_index
        )
        cls.base_decimals = 18
        cls.quote_decimals = 6

    def setUp(self) -> None:
        self._initialize_timeout_height_sync_task = patch(
            "hummingbot.connector.exchange.injective_v2.data_sources.injective_grantee_data_source"
            ".AsyncClient._initialize_timeout_height_sync_task"
        )
        self._initialize_timeout_height_sync_task.start()
        self._initialize_timeout_height_patch = patch(
            "hummingbot.connector.exchange.injective_v2.data_sources.injective_grantee_data_source"
            ".AsyncClient.sync_timeout_height"
        )
        self._initialize_timeout_height_patch.start()
        super().setUp()
        self._original_async_loop = asyncio.get_event_loop()
        self.async_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.async_loop)
        self._logs_event: Optional[asyncio.Event] = None
        self.exchange._data_source.logger().setLevel(1)
        self.exchange._data_source.logger().addHandler(self)

        self.exchange._orders_processing_delta_time = 0.1
        self.async_tasks.append(self.async_loop.create_task(self.exchange._process_queued_orders()))

    def tearDown(self) -> None:
        super().tearDown()
        self._initialize_timeout_height_patch.stop()
        self._initialize_timeout_height_sync_task.stop()
        self.async_loop.stop()
        self.async_loop.close()
        asyncio.set_event_loop(self._original_async_loop)
        self._logs_event = None

    def handle(self, record):
        super().handle(record=record)
        if self._logs_event is not None:
            self._logs_event.set()

    def reset_log_event(self):
        if self._logs_event is not None:
            self._logs_event.clear()

    async def wait_for_a_log(self):
        if self._logs_event is not None:
            await self._logs_event.wait()

    @property
    def all_symbols_url(self):
        raise NotImplementedError

    @property
    def latest_prices_url(self):
        raise NotImplementedError

    @property
    def network_status_url(self):
        raise NotImplementedError

    @property
    def trading_rules_url(self):
        raise NotImplementedError

    @property
    def order_creation_url(self):
        raise NotImplementedError

    @property
    def balance_url(self):
        raise NotImplementedError

    @property
    def all_symbols_request_mock_response(self):
        raise NotImplementedError

    @property
    def latest_prices_request_mock_response(self):
        return {
            "trades": [
                {
                    "orderHash": "0x9ffe4301b24785f09cb529c1b5748198098b17bd6df8fe2744d923a574179229",  # noqa: mock
                    "cid": "",
                    "subaccountId": "0xa73ad39eab064051fb468a5965ee48ca87ab66d4000000000000000000000000",  # noqa: mock
                    "marketId": "0x0611780ba69656949525013d947713300f56c37b6175e02f26bffa495c3208fe",  # noqa: mock
                    "tradeExecutionType": "limitMatchRestingOrder",
                    "tradeDirection": "sell",
                    "price": {
                        "price": str(Decimal(str(self.expected_latest_price)) * Decimal(
                            f"1e{self.quote_decimals - self.base_decimals}")),
                        "quantity": "142000000000000000000",
                        "timestamp": "1688734042063"
                    },
                    "fee": "-112393",
                    "executedAt": "1688734042063",
                    "feeRecipient": "inj15uad884tqeq9r76x3fvktmjge2r6kek55c2zpa",  # noqa: mock
                    "tradeId": "13374245_801_0",
                    "executionSide": "maker"
                }
            ],
            "paging": {
                "total": "1000",
                "from": 1,
                "to": 1
            }
        }

    @property
    def all_symbols_including_invalid_pair_mock_response(self) -> Tuple[str, Any]:
        response = self.all_markets_mock_response
        response["invalid_market_id"] = SpotMarket(
            id="invalid_market_id",
            status="active",
            ticker="INVALID/MARKET",
            base_token=None,
            quote_token=None,
            maker_fee_rate=Decimal("-0.0001"),
            taker_fee_rate=Decimal("0.001"),
            service_provider_fee=Decimal("0.4"),
            min_price_tick_size=Decimal("0.000000000000001"),
            min_quantity_tick_size=Decimal("1000000000000000"),
            min_notional=Decimal("1000000"),
        )

        return ("INVALID_MARKET", response)

    @property
    def network_status_request_successful_mock_response(self):
        return {}

    @property
    def trading_rules_request_mock_response(self):
        raise NotImplementedError

    @property
    def trading_rules_request_erroneous_mock_response(self):
        base_native_token = Token(
            name="Base Asset",
            symbol=self.base_asset,
            denom=self.base_asset_denom,
            address="0xe28b3B32B6c345A34Ff64674606124Dd5Aceca30",  # noqa: mock
            decimals=self.base_decimals,
            logo="https://static.alchemyapi.io/images/assets/7226.png",
            updated=1687190809715,
        )
        quote_native_token = Token(
            name="Base Asset",
            symbol=self.quote_asset,
            denom=self.quote_asset_denom,
            address="0x0000000000000000000000000000000000000000",  # noqa: mock
            decimals=self.quote_decimals,
            logo="https://static.alchemyapi.io/images/assets/825.png",
            updated=1687190809716,
        )

        native_market = SpotMarket(
            id="0x0611780ba69656949525013d947713300f56c37b6175e02f26bffa495c3208fe",  # noqa: mock
            status="active",
            ticker=f"{self.base_asset}/{self.quote_asset}",
            base_token=base_native_token,
            quote_token=quote_native_token,
            maker_fee_rate=Decimal("-0.0001"),
            taker_fee_rate=Decimal("0.001"),
            service_provider_fee=Decimal("0.4"),
            min_price_tick_size=None,
            min_quantity_tick_size=None,
            min_notional=None,
        )

        return {native_market.id: native_market}

    @property
    def order_creation_request_successful_mock_response(self):
        return {"txhash": "017C130E3602A48E5C9D661CAC657BF1B79262D4B71D5C25B1DA62DE2338DA0E",  # noqa: mock"
                "rawLog": "[]",
                "code": 0}  # noqa: mock

    @property
    def balance_request_mock_response_for_base_and_quote(self):
        return {
            "portfolio": {
                "accountAddress": self.portfolio_account_injective_address,
                "bankBalances": [
                    {
                        "denom": self.base_asset_denom,
                        "amount": str(Decimal(5) * Decimal(1e18))
                    },
                    {
                        "denom": self.quote_asset_denom,
                        "amount": str(Decimal(1000) * Decimal(1e6))
                    }
                ],
                "subaccounts": [
                    {
                        "subaccountId": self.portfolio_account_subaccount_id,
                        "denom": self.quote_asset_denom,
                        "deposit": {
                            "totalBalance": str(Decimal(1000) * Decimal(1e6)),
                            "availableBalance": str(Decimal(1000) * Decimal(1e6))
                        }
                    },
                    {
                        "subaccountId": self.portfolio_account_subaccount_id,
                        "denom": self.base_asset_denom,
                        "deposit": {
                            "totalBalance": str(Decimal(10) * Decimal(1e18)),
                            "availableBalance": str(Decimal(5) * Decimal(1e18))
                        }
                    },
                ],
            }
        }

    @property
    def balance_request_mock_response_only_base(self):
        return {
            "portfolio": {
                "accountAddress": self.portfolio_account_injective_address,
                "bankBalances": [
                    {
                        "denom": self.base_asset_denom,
                        "amount": str(Decimal(5) * Decimal(1e18))
                    },
                ],
                "subaccounts": [
                    {
                        "subaccountId": self.portfolio_account_subaccount_id,
                        "denom": self.base_asset_denom,
                        "deposit": {
                            "totalBalance": str(Decimal(10) * Decimal(1e18)),
                            "availableBalance": str(Decimal(5) * Decimal(1e18))
                        }
                    },
                ],
            }
        }

    @property
    def balance_event_websocket_update(self):
        return {
            "blockHeight": "20583",
            "blockTime": "1640001112223",
            "subaccountDeposits": [
                {
                    "subaccountId": self.portfolio_account_subaccount_id,
                    "deposits": [
                        {
                            "denom": self.base_asset_denom,
                            "deposit": {
                                "availableBalance": str(int(Decimal("10") * Decimal("1e36"))),
                                "totalBalance": str(int(Decimal("15") * Decimal("1e36")))
                            }
                        }
                    ]
                },
            ],
            "spotOrderbookUpdates": [],
            "derivativeOrderbookUpdates": [],
            "bankBalances": [],
            "spotTrades": [],
            "derivativeTrades": [],
            "spotOrders": [],
            "derivativeOrders": [],
            "positions": [],
            "oraclePrices": [],
        }

    @property
    def expected_latest_price(self):
        return 9999.9

    @property
    def expected_supported_order_types(self) -> List[OrderType]:
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    @property
    def expected_trading_rule(self):
        market = list(self.all_markets_mock_response.values())[0]
        min_price_tick_size = (market.min_price_tick_size
                               * Decimal(f"1e{market.base_token.decimals - market.quote_token.decimals}"))
        min_quantity_tick_size = market.min_quantity_tick_size * Decimal(
            f"1e{-market.base_token.decimals}")
        min_notional = market.min_notional * Decimal(f"1e{-market.quote_token.decimals}")
        trading_rule = TradingRule(
            trading_pair=self.trading_pair,
            min_order_size=min_quantity_tick_size,
            min_price_increment=min_price_tick_size,
            min_base_amount_increment=min_quantity_tick_size,
            min_quote_amount_increment=min_price_tick_size,
            min_notional_size=min_notional,
        )

        return trading_rule

    @property
    def expected_logged_error_for_erroneous_trading_rule(self):
        erroneous_rule = list(self.trading_rules_request_erroneous_mock_response.values())[0]
        return f"Error parsing the trading pair rule: {erroneous_rule}. Skipping..."

    @property
    def expected_exchange_order_id(self):
        return "0x3870fbdd91f07d54425147b1bb96404f4f043ba6335b422a6d494d285b387f00"  # noqa: mock

    @property
    def is_order_fill_http_update_included_in_status_update(self) -> bool:
        return True

    @property
    def is_order_fill_http_update_executed_during_websocket_order_event_processing(self) -> bool:
        return False

    @property
    def expected_partial_fill_price(self) -> Decimal:
        return Decimal("100")

    @property
    def expected_partial_fill_amount(self) -> Decimal:
        return Decimal("10")

    @property
    def expected_fill_fee(self) -> TradeFeeBase:
        return AddedToCostTradeFee(
            percent_token=self.quote_asset, flat_fees=[TokenAmount(token=self.quote_asset, amount=Decimal("30"))]
        )

    @property
    def expected_fill_trade_id(self) -> str:
        return "10414162_22_33"

    @property
    def all_markets_mock_response(self):
        base_native_token = Token(
            name="Base Asset",
            symbol=self.base_asset,
            denom=self.base_asset_denom,
            address="0xe28b3B32B6c345A34Ff64674606124Dd5Aceca30",  # noqa: mock
            decimals=self.base_decimals,
            logo="https://static.alchemyapi.io/images/assets/7226.png",
            updated=1687190809715,
        )
        quote_native_token = Token(
            name="Base Asset",
            symbol=self.quote_asset,
            denom=self.quote_asset_denom,
            address="0x0000000000000000000000000000000000000000",  # noqa: mock
            decimals=self.quote_decimals,
            logo="https://static.alchemyapi.io/images/assets/825.png",
            updated=1687190809716,
        )

        native_market = SpotMarket(
            id=self.market_id,
            status="active",
            ticker=f"{self.base_asset}/{self.quote_asset}",
            base_token=base_native_token,
            quote_token=quote_native_token,
            maker_fee_rate=Decimal("-0.0001"),
            taker_fee_rate=Decimal("0.001"),
            service_provider_fee=Decimal("0.4"),
            min_price_tick_size=Decimal("0.000000000000001"),
            min_quantity_tick_size=Decimal("1000000000000000"),
            min_notional=Decimal("1000000"),
        )

        return {native_market.id: native_market}

    def exchange_symbol_for_tokens(self, base_token: str, quote_token: str) -> str:
        return self.market_id

    def create_exchange_instance(self):
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        network_config = InjectiveTestnetNetworkMode(testnet_node="sentry")

        account_config = InjectiveDelegatedAccountMode(
            private_key=self.trading_account_private_key,
            subaccount_index=self.trading_account_subaccount_index,
            granter_address=self.portfolio_account_injective_address,
            granter_subaccount_index=self.portfolio_account_subaccount_index,
        )

        injective_config = InjectiveConfigMap(
            network=network_config,
            account_type=account_config,
            fee_calculator=InjectiveMessageBasedTransactionFeeCalculatorMode(),
        )

        exchange = InjectiveV2Exchange(
            client_config_map=client_config_map,
            connector_configuration=injective_config,
            trading_pairs=[self.trading_pair],
        )

        exchange._data_source._query_executor = ProgrammableQueryExecutor()
        exchange._data_source._spot_market_and_trading_pair_map = bidict({self.market_id: self.trading_pair})
        exchange._data_source._derivative_market_and_trading_pair_map = bidict()

        exchange._data_source._composer = Composer(network=exchange._data_source.network_name)

        return exchange

    def validate_auth_credentials_present(self, request_call: RequestCall):
        raise NotImplementedError

    def validate_order_creation_request(self, order: InFlightOrder, request_call: RequestCall):
        raise NotImplementedError

    def validate_order_cancelation_request(self, order: InFlightOrder, request_call: RequestCall):
        raise NotImplementedError

    def validate_order_status_request(self, order: InFlightOrder, request_call: RequestCall):
        raise NotImplementedError

    def validate_trades_request(self, order: InFlightOrder, request_call: RequestCall):
        raise NotImplementedError

    def configure_all_symbols_response(
            self, mock_api: aioresponses, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        all_markets_mock_response = self.all_markets_mock_response
        self.exchange._data_source._query_executor._spot_markets_responses.put_nowait(all_markets_mock_response)
        market = list(all_markets_mock_response.values())[0]
        self.exchange._data_source._query_executor._tokens_responses.put_nowait(
            {token.symbol: token for token in [market.base_token, market.quote_token]}
        )
        self.exchange._data_source._query_executor._derivative_markets_responses.put_nowait({})
        return ""

    def configure_trading_rules_response(
            self,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> List[str]:

        self.configure_all_symbols_response(mock_api=mock_api, callback=callback)
        return ""

    def configure_erroneous_trading_rules_response(
            self,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> List[str]:

        response = self.trading_rules_request_erroneous_mock_response
        self.exchange._data_source._query_executor._spot_markets_responses.put_nowait(response)
        market = list(response.values())[0]
        self.exchange._data_source._query_executor._tokens_responses.put_nowait(
            {token.symbol: token for token in [market.base_token, market.quote_token]}
        )
        self.exchange._data_source._query_executor._derivative_markets_responses.put_nowait({})
        return ""

    def configure_successful_cancelation_response(self, order: InFlightOrder, mock_api: aioresponses,
                                                  callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        transaction_simulation_response = self._msg_exec_simulation_mock_response()
        self.exchange._data_source._query_executor._simulate_transaction_responses.put_nowait(
            transaction_simulation_response)
        response = self._order_cancelation_request_successful_mock_response(order=order)
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = partial(self._callback_wrapper_with_response, callback=callback, response=response)
        self.exchange._data_source._query_executor._send_transaction_responses = mock_queue
        return ""

    def configure_erroneous_cancelation_response(self, order: InFlightOrder, mock_api: aioresponses,
                                                 callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        transaction_simulation_response = self._msg_exec_simulation_mock_response()
        self.exchange._data_source._query_executor._simulate_transaction_responses.put_nowait(
            transaction_simulation_response)
        response = self._order_cancelation_request_erroneous_mock_response(order=order)
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = partial(self._callback_wrapper_with_response, callback=callback, response=response)
        self.exchange._data_source._query_executor._send_transaction_responses = mock_queue
        return ""

    def configure_order_not_found_error_cancelation_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        raise NotImplementedError

    def configure_one_successful_one_erroneous_cancel_all_response(
            self,
            successful_order: InFlightOrder,
            erroneous_order: InFlightOrder,
            mock_api: aioresponses
    ) -> List[str]:
        raise NotImplementedError

    def configure_completely_filled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> List[str]:
        self.configure_all_symbols_response(mock_api=mock_api)
        response = self._order_status_request_completely_filled_mock_response(order=order)
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = partial(self._callback_wrapper_with_response, callback=callback, response=response)
        self.exchange._data_source._query_executor._historical_spot_orders_responses = mock_queue
        return []

    def configure_canceled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> Union[str, List[str]]:
        self.configure_all_symbols_response(mock_api=mock_api)

        self.exchange._data_source._query_executor._spot_trades_responses.put_nowait(
            {"trades": [], "paging": {"total": "0"}})

        response = self._order_status_request_canceled_mock_response(order=order)
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = partial(self._callback_wrapper_with_response, callback=callback, response=response)
        self.exchange._data_source._query_executor._historical_spot_orders_responses = mock_queue
        return []

    def configure_open_order_status_response(self, order: InFlightOrder, mock_api: aioresponses,
                                             callback: Optional[Callable] = lambda *args, **kwargs: None) -> List[str]:
        self.configure_all_symbols_response(mock_api=mock_api)

        self.exchange._data_source._query_executor._spot_trades_responses.put_nowait(
            {"trades": [], "paging": {"total": "0"}})

        response = self._order_status_request_open_mock_response(order=order)
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = partial(self._callback_wrapper_with_response, callback=callback, response=response)
        self.exchange._data_source._query_executor._historical_spot_orders_responses = mock_queue
        return []

    def configure_http_error_order_status_response(self, order: InFlightOrder, mock_api: aioresponses,
                                                   callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        self.configure_all_symbols_response(mock_api=mock_api)

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = IOError("Test error for trades responses")
        self.exchange._data_source._query_executor._spot_trades_responses = mock_queue

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = IOError("Test error for historical orders responses")
        self.exchange._data_source._query_executor._historical_spot_orders_responses = mock_queue
        return None

    def configure_partially_filled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        self.configure_all_symbols_response(mock_api=mock_api)
        response = self._order_status_request_partially_filled_mock_response(order=order)
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = partial(self._callback_wrapper_with_response, callback=callback, response=response)
        self.exchange._data_source._query_executor._historical_spot_orders_responses = mock_queue
        return None

    def configure_order_not_found_error_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> List[str]:
        self.configure_all_symbols_response(mock_api=mock_api)
        response = self._order_status_request_not_found_mock_response(order=order)
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = partial(self._callback_wrapper_with_response, callback=callback, response=response)
        self.exchange._data_source._query_executor._historical_spot_orders_responses = mock_queue
        return []

    def configure_partial_fill_trade_response(self, order: InFlightOrder, mock_api: aioresponses,
                                              callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        response = self._order_fills_request_partial_fill_mock_response(order=order)
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = partial(self._callback_wrapper_with_response, callback=callback, response=response)
        self.exchange._data_source._query_executor._spot_trades_responses = mock_queue
        return None

    def configure_erroneous_http_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = IOError("Test error for trades responses")
        self.exchange._data_source._query_executor._spot_trades_responses = mock_queue
        return None

    def configure_full_fill_trade_response(self, order: InFlightOrder, mock_api: aioresponses,
                                           callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        response = self._order_fills_request_full_fill_mock_response(order=order)
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = partial(self._callback_wrapper_with_response, callback=callback, response=response)
        self.exchange._data_source._query_executor._spot_trades_responses = mock_queue
        return []

    def order_event_for_new_order_websocket_update(self, order: InFlightOrder):
        return {
            "blockHeight": "20583",
            "blockTime": "1640001112223",
            "subaccountDeposits": [],
            "spotOrderbookUpdates": [],
            "derivativeOrderbookUpdates": [],
            "bankBalances": [],
            "spotTrades": [],
            "derivativeTrades": [],
            "spotOrders": [
                {
                    "status": "Booked",
                    "orderHash": base64.b64encode(bytes.fromhex(order.exchange_order_id.replace("0x", ""))).decode(),
                    "cid": order.client_order_id,
                    "order": {
                        "marketId": self.market_id,
                        "order": {
                            "orderInfo": {
                                "subaccountId": self.portfolio_account_subaccount_id,
                                "feeRecipient": self.portfolio_account_injective_address,
                                "price": str(
                                    int(order.price * Decimal(f"1e{self.quote_decimals - self.base_decimals + 18}"))),
                                "quantity": str(int(order.amount * Decimal(f"1e{self.base_decimals + 18}"))),
                                "cid": order.client_order_id
                            },
                            "orderType": order.trade_type.name.lower(),
                            "fillable": str(int(order.amount * Decimal(f"1e{self.base_decimals + 18}"))),
                            "orderHash": base64.b64encode(
                                bytes.fromhex(order.exchange_order_id.replace("0x", ""))).decode(),
                            "triggerPrice": "",
                        }
                    },
                },
            ],
            "derivativeOrders": [],
            "positions": [],
            "oraclePrices": [],
        }

    def order_event_for_canceled_order_websocket_update(self, order: InFlightOrder):
        return {
            "blockHeight": "20583",
            "blockTime": "1640001112223",
            "subaccountDeposits": [],
            "spotOrderbookUpdates": [],
            "derivativeOrderbookUpdates": [],
            "bankBalances": [],
            "spotTrades": [],
            "derivativeTrades": [],
            "spotOrders": [
                {
                    "status": "Cancelled",
                    "orderHash": base64.b64encode(bytes.fromhex(order.exchange_order_id.replace("0x", ""))).decode(),
                    "cid": order.client_order_id,
                    "order": {
                        "marketId": self.market_id,
                        "order": {
                            "orderInfo": {
                                "subaccountId": self.portfolio_account_subaccount_id,
                                "feeRecipient": self.portfolio_account_injective_address,
                                "price": str(
                                    int(order.price * Decimal(f"1e{self.quote_decimals - self.base_decimals + 18}"))),
                                "quantity": str(int(order.amount * Decimal(f"1e{self.base_decimals + 18}"))),
                                "cid": order.client_order_id,
                            },
                            "orderType": order.trade_type.name.lower(),
                            "fillable": str(int(order.amount * Decimal(f"1e{self.base_decimals + 18}"))),
                            "orderHash": base64.b64encode(
                                bytes.fromhex(order.exchange_order_id.replace("0x", ""))).decode(),
                            "triggerPrice": "",
                        }
                    },
                },
            ],
            "derivativeOrders": [],
            "positions": [],
            "oraclePrices": [],
        }

    def order_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return {
            "blockHeight": "20583",
            "blockTime": "1640001112223",
            "subaccountDeposits": [],
            "spotOrderbookUpdates": [],
            "derivativeOrderbookUpdates": [],
            "bankBalances": [],
            "spotTrades": [],
            "derivativeTrades": [],
            "spotOrders": [
                {
                    "status": "Matched",
                    "orderHash": base64.b64encode(bytes.fromhex(order.exchange_order_id.replace("0x", ""))).decode(),
                    "cid": order.client_order_id,
                    "order": {
                        "marketId": self.market_id,
                        "order": {
                            "orderInfo": {
                                "subaccountId": self.portfolio_account_subaccount_id,
                                "feeRecipient": self.portfolio_account_injective_address,
                                "price": str(
                                    int(order.price * Decimal(f"1e{self.quote_decimals - self.base_decimals + 18}"))),
                                "quantity": str(int(order.amount * Decimal(f"1e{self.base_decimals + 18}"))),
                                "cid": order.client_order_id,
                            },
                            "orderType": order.trade_type.name.lower(),
                            "fillable": str(int(order.amount * Decimal(f"1e{self.base_decimals + 18}"))),
                            "orderHash": base64.b64encode(
                                bytes.fromhex(order.exchange_order_id.replace("0x", ""))).decode(),
                            "triggerPrice": "",
                        }
                    },
                },
            ],
            "derivativeOrders": [],
            "positions": [],
            "oraclePrices": [],
        }

    def trade_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return {
            "blockHeight": "20583",
            "blockTime": "1640001112223",
            "subaccountDeposits": [],
            "spotOrderbookUpdates": [],
            "derivativeOrderbookUpdates": [],
            "bankBalances": [],
            "spotTrades": [
                {
                    "marketId": self.market_id,
                    "isBuy": order.trade_type == TradeType.BUY,
                    "executionType": "LimitMatchRestingOrder",
                    "quantity": str(int(order.amount * Decimal(f"1e{self.base_decimals + 18}"))),
                    "price": str(int(order.price * Decimal(f"1e{self.quote_decimals - self.base_decimals + 18}"))),
                    "subaccountId": self.portfolio_account_subaccount_id,
                    "fee": str(int(
                        self.expected_fill_fee.flat_fees[0].amount * Decimal(f"1e{self.quote_decimals + 18}")
                    )),
                    "orderHash": base64.b64encode(bytes.fromhex(order.exchange_order_id.replace("0x", ""))).decode(),
                    "feeRecipientAddress": self.portfolio_account_injective_address,
                    "cid": order.client_order_id,
                    "tradeId": self.expected_fill_trade_id,
                },
            ],
            "derivativeTrades": [],
            "spotOrders": [],
            "derivativeOrders": [],
            "positions": [],
            "oraclePrices": [],
        }

    @aioresponses()
    def test_all_trading_pairs_does_not_raise_exception(self, mock_api):
        self.exchange._set_trading_pair_symbol_map(None)
        self.exchange._data_source._spot_market_and_trading_pair_map = None
        queue_mock = AsyncMock()
        queue_mock.get.side_effect = Exception("Test error")
        self.exchange._data_source._query_executor._spot_markets_responses = queue_mock

        result: List[str] = self.async_run_with_timeout(self.exchange.all_trading_pairs(), timeout=10)

        self.assertEqual(0, len(result))

    def test_batch_order_create(self):
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        # Configure all symbols response to initialize the trading rules
        self.configure_all_symbols_response(mock_api=None)
        self.async_run_with_timeout(self.exchange._update_trading_rules())

        buy_order_to_create = LimitOrder(
            client_order_id="",
            trading_pair=self.trading_pair,
            is_buy=True,
            base_currency=self.base_asset,
            quote_currency=self.quote_asset,
            price=Decimal("10"),
            quantity=Decimal("2"),
        )
        sell_order_to_create = LimitOrder(
            client_order_id="",
            trading_pair=self.trading_pair,
            is_buy=False,
            base_currency=self.base_asset,
            quote_currency=self.quote_asset,
            price=Decimal("11"),
            quantity=Decimal("3"),
        )
        orders_to_create = [buy_order_to_create, sell_order_to_create]

        transaction_simulation_response = self._msg_exec_simulation_mock_response()
        self.exchange._data_source._query_executor._simulate_transaction_responses.put_nowait(
            transaction_simulation_response)

        response = self.order_creation_request_successful_mock_response
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = partial(
            self._callback_wrapper_with_response,
            callback=lambda args, kwargs: request_sent_event.set(),
            response=response
        )
        self.exchange._data_source._query_executor._send_transaction_responses = mock_queue

        orders: List[LimitOrder] = self.exchange.batch_order_create(orders_to_create=orders_to_create)

        buy_order_to_create_in_flight = GatewayInFlightOrder(
            client_order_id=orders[0].client_order_id,
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            creation_timestamp=1640780000,
            price=orders[0].price,
            amount=orders[0].quantity,
            exchange_order_id="hash1",
            creation_transaction_hash=response["txhash"]
        )
        sell_order_to_create_in_flight = GatewayInFlightOrder(
            client_order_id=orders[1].client_order_id,
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.SELL,
            creation_timestamp=1640780000,
            price=orders[1].price,
            amount=orders[1].quantity,
            exchange_order_id="hash2",
            creation_transaction_hash=response["txhash"]
        )

        self.async_run_with_timeout(request_sent_event.wait())

        self.assertEqual(2, len(orders))
        self.assertEqual(2, len(self.exchange.in_flight_orders))

        self.assertIn(buy_order_to_create_in_flight.client_order_id, self.exchange.in_flight_orders)
        self.assertIn(sell_order_to_create_in_flight.client_order_id, self.exchange.in_flight_orders)

        self.assertEqual(
            buy_order_to_create_in_flight.creation_transaction_hash,
            self.exchange.in_flight_orders[buy_order_to_create_in_flight.client_order_id].creation_transaction_hash
        )
        self.assertEqual(
            sell_order_to_create_in_flight.creation_transaction_hash,
            self.exchange.in_flight_orders[sell_order_to_create_in_flight.client_order_id].creation_transaction_hash
        )

    def test_batch_order_create_with_one_market_order(self):
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        # Configure all symbols response to initialize the trading rules
        self.configure_all_symbols_response(mock_api=None)
        self.async_run_with_timeout(self.exchange._update_trading_rules())

        order_book = OrderBook()
        self.exchange.order_book_tracker._order_books[self.trading_pair] = order_book
        order_book.apply_snapshot(
            bids=[OrderBookRow(price=5000, amount=20, update_id=1)],
            asks=[],
            update_id=1,
        )

        buy_order_to_create = LimitOrder(
            client_order_id="",
            trading_pair=self.trading_pair,
            is_buy=True,
            base_currency=self.base_asset,
            quote_currency=self.quote_asset,
            price=Decimal("10"),
            quantity=Decimal("2"),
        )
        sell_order_to_create = MarketOrder(
            order_id="",
            trading_pair=self.trading_pair,
            is_buy=False,
            base_asset=self.base_asset,
            quote_asset=self.quote_asset,
            amount=3,
            timestamp=self.exchange.current_timestamp,
        )
        orders_to_create = [buy_order_to_create, sell_order_to_create]

        transaction_simulation_response = self._msg_exec_simulation_mock_response()
        self.exchange._data_source._query_executor._simulate_transaction_responses.put_nowait(
            transaction_simulation_response)

        response = self.order_creation_request_successful_mock_response
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = partial(
            self._callback_wrapper_with_response,
            callback=lambda args, kwargs: request_sent_event.set(),
            response=response
        )
        self.exchange._data_source._query_executor._send_transaction_responses = mock_queue

        expected_price_for_volume = self.exchange.get_price_for_volume(
            trading_pair=self.trading_pair,
            is_buy=True,
            volume=Decimal(str(sell_order_to_create.amount)),
        ).result_price

        orders: List[LimitOrder] = self.exchange.batch_order_create(orders_to_create=orders_to_create)

        buy_order_to_create_in_flight = GatewayInFlightOrder(
            client_order_id=orders[0].client_order_id,
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            creation_timestamp=1640780000,
            price=orders[0].price,
            amount=orders[0].quantity,
            exchange_order_id="hash1",
            creation_transaction_hash=response["txhash"]
        )
        sell_order_to_create_in_flight = GatewayInFlightOrder(
            client_order_id=orders[1].order_id,
            trading_pair=self.trading_pair,
            order_type=OrderType.MARKET,
            trade_type=TradeType.SELL,
            creation_timestamp=1640780000,
            price=expected_price_for_volume,
            amount=orders[1].quantity,
            exchange_order_id="hash2",
            creation_transaction_hash=response["txhash"]
        )

        self.async_run_with_timeout(request_sent_event.wait())

        self.assertEqual(2, len(orders))
        self.assertEqual(2, len(self.exchange.in_flight_orders))

        self.assertIn(buy_order_to_create_in_flight.client_order_id, self.exchange.in_flight_orders)
        self.assertIn(sell_order_to_create_in_flight.client_order_id, self.exchange.in_flight_orders)

        self.assertEqual(
            buy_order_to_create_in_flight.creation_transaction_hash,
            self.exchange.in_flight_orders[buy_order_to_create_in_flight.client_order_id].creation_transaction_hash
        )
        self.assertEqual(
            sell_order_to_create_in_flight.creation_transaction_hash,
            self.exchange.in_flight_orders[sell_order_to_create_in_flight.client_order_id].creation_transaction_hash
        )

    @aioresponses()
    def test_create_buy_limit_order_successfully(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        transaction_simulation_response = self._msg_exec_simulation_mock_response()
        self.exchange._data_source._query_executor._simulate_transaction_responses.put_nowait(
            transaction_simulation_response)

        response = self.order_creation_request_successful_mock_response
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = partial(
            self._callback_wrapper_with_response,
            callback=lambda args, kwargs: request_sent_event.set(),
            response=response
        )
        self.exchange._data_source._query_executor._send_transaction_responses = mock_queue

        order_id = self.place_buy_order()
        self.async_run_with_timeout(request_sent_event.wait())

        self.assertEqual(1, len(self.exchange.in_flight_orders))
        self.assertIn(order_id, self.exchange.in_flight_orders)

        order = self.exchange.in_flight_orders[order_id]

        self.assertEqual(response["txhash"], order.creation_transaction_hash)

    @aioresponses()
    def test_create_sell_limit_order_successfully(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        transaction_simulation_response = self._msg_exec_simulation_mock_response()
        self.exchange._data_source._query_executor._simulate_transaction_responses.put_nowait(
            transaction_simulation_response)

        response = self.order_creation_request_successful_mock_response
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = partial(
            self._callback_wrapper_with_response,
            callback=lambda args, kwargs: request_sent_event.set(),
            response=response
        )
        self.exchange._data_source._query_executor._send_transaction_responses = mock_queue

        order_id = self.place_sell_order()
        self.async_run_with_timeout(request_sent_event.wait())

        self.assertEqual(1, len(self.exchange.in_flight_orders))
        self.assertIn(order_id, self.exchange.in_flight_orders)

        order = self.exchange.in_flight_orders[order_id]

        self.assertEqual(response["txhash"], order.creation_transaction_hash)

    @aioresponses()
    def test_create_buy_market_order_successfully(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        order_book = OrderBook()
        self.exchange.order_book_tracker._order_books[self.trading_pair] = order_book
        order_book.apply_snapshot(
            bids=[],
            asks=[OrderBookRow(price=5000, amount=20, update_id=1)],
            update_id=1,
        )

        transaction_simulation_response = self._msg_exec_simulation_mock_response()
        self.exchange._data_source._query_executor._simulate_transaction_responses.put_nowait(
            transaction_simulation_response)

        response = self.order_creation_request_successful_mock_response
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = partial(
            self._callback_wrapper_with_response,
            callback=lambda args, kwargs: request_sent_event.set(),
            response=response
        )
        self.exchange._data_source._query_executor._send_transaction_responses = mock_queue

        order_amount = Decimal(1)
        expected_price_for_volume = self.exchange.get_price_for_volume(
            trading_pair=self.trading_pair,
            is_buy=True,
            volume=order_amount
        ).result_price

        order_id = self.place_buy_order(amount=order_amount, price=None, order_type=OrderType.MARKET)
        self.async_run_with_timeout(request_sent_event.wait())

        self.assertEqual(1, len(self.exchange.in_flight_orders))
        self.assertIn(order_id, self.exchange.in_flight_orders)

        order = self.exchange.in_flight_orders[order_id]

        self.assertEqual(response["txhash"], order.creation_transaction_hash)
        self.assertEqual(expected_price_for_volume, order.price)

    @aioresponses()
    def test_create_sell_market_order_successfully(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        order_book = OrderBook()
        self.exchange.order_book_tracker._order_books[self.trading_pair] = order_book
        order_book.apply_snapshot(
            bids=[OrderBookRow(price=5000, amount=20, update_id=1)],
            asks=[],
            update_id=1,
        )

        transaction_simulation_response = self._msg_exec_simulation_mock_response()
        self.exchange._data_source._query_executor._simulate_transaction_responses.put_nowait(
            transaction_simulation_response)

        response = self.order_creation_request_successful_mock_response
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = partial(
            self._callback_wrapper_with_response,
            callback=lambda args, kwargs: request_sent_event.set(),
            response=response
        )
        self.exchange._data_source._query_executor._send_transaction_responses = mock_queue

        order_amount = Decimal(1)
        expected_price_for_volume = self.exchange.get_price_for_volume(
            trading_pair=self.trading_pair,
            is_buy=False,
            volume=order_amount
        ).result_price

        order_id = self.place_sell_order(amount=order_amount, price=None, order_type=OrderType.MARKET)
        self.async_run_with_timeout(request_sent_event.wait())

        self.assertEqual(1, len(self.exchange.in_flight_orders))
        self.assertIn(order_id, self.exchange.in_flight_orders)

        order = self.exchange.in_flight_orders[order_id]

        self.assertEqual(response["txhash"], order.creation_transaction_hash)
        self.assertEqual(expected_price_for_volume, order.price)

    @aioresponses()
    def test_create_order_fails_and_raises_failure_event(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        transaction_simulation_response = self._msg_exec_simulation_mock_response()
        self.exchange._data_source._query_executor._simulate_transaction_responses.put_nowait(
            transaction_simulation_response)

        response = {"txhash": "", "rawLog": "Error", "code": 11}
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = partial(
            self._callback_wrapper_with_response,
            callback=lambda args, kwargs: request_sent_event.set(),
            response=response
        )
        self.exchange._data_source._query_executor._send_transaction_responses = mock_queue

        order_id = self.place_buy_order()
        self.async_run_with_timeout(request_sent_event.wait())

        self.assertNotIn(order_id, self.exchange.in_flight_orders)

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
    def test_create_order_fails_when_trading_rule_error_and_raises_failure_event(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        order_id_for_invalid_order = self.place_buy_order(
            amount=Decimal("0.0001"), price=Decimal("0.0001")
        )

        transaction_simulation_response = self._msg_exec_simulation_mock_response()
        self.exchange._data_source._query_executor._simulate_transaction_responses.put_nowait(
            transaction_simulation_response)

        response = {"txhash": "", "rawLog": "Error", "code": 11}
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = partial(
            self._callback_wrapper_with_response,
            callback=lambda args, kwargs: request_sent_event.set(),
            response=response
        )
        self.exchange._data_source._query_executor._send_transaction_responses = mock_queue

        order_id = self.place_buy_order()
        self.async_run_with_timeout(request_sent_event.wait())

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
                "Buy order amount 0.0001 is lower than the minimum order size 0.01. The order will not be created, "
                "increase the amount to be higher than the minimum order size."
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

    def test_batch_order_cancel(self):
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        self.exchange.start_tracking_order(
            order_id="11",
            exchange_order_id=self.expected_exchange_order_id + "1",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("100"),
            order_type=OrderType.LIMIT,
        )
        self.exchange.start_tracking_order(
            order_id="12",
            exchange_order_id=self.expected_exchange_order_id + "2",
            trading_pair=self.trading_pair,
            trade_type=TradeType.SELL,
            price=Decimal("11000"),
            amount=Decimal("110"),
            order_type=OrderType.LIMIT,
        )

        buy_order_to_cancel: GatewayInFlightOrder = self.exchange.in_flight_orders["11"]
        sell_order_to_cancel: GatewayInFlightOrder = self.exchange.in_flight_orders["12"]
        orders_to_cancel = [buy_order_to_cancel, sell_order_to_cancel]

        transaction_simulation_response = self._msg_exec_simulation_mock_response()
        self.exchange._data_source._query_executor._simulate_transaction_responses.put_nowait(
            transaction_simulation_response)

        response = self._order_cancelation_request_successful_mock_response(order=buy_order_to_cancel)
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = partial(
            self._callback_wrapper_with_response,
            callback=lambda args, kwargs: request_sent_event.set(),
            response=response
        )
        self.exchange._data_source._query_executor._send_transaction_responses = mock_queue

        self.exchange.batch_order_cancel(orders_to_cancel=orders_to_cancel)

        self.async_run_with_timeout(request_sent_event.wait())

        self.assertIn(buy_order_to_cancel.client_order_id, self.exchange.in_flight_orders)
        self.assertIn(sell_order_to_cancel.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(buy_order_to_cancel.is_pending_cancel_confirmation)
        self.assertEqual(response["txhash"], buy_order_to_cancel.cancel_tx_hash)
        self.assertTrue(sell_order_to_cancel.is_pending_cancel_confirmation)
        self.assertEqual(response["txhash"], sell_order_to_cancel.cancel_tx_hash)

    @aioresponses()
    def test_cancel_order_not_found_in_the_exchange(self, mock_api):
        # This tests does not apply for Injective. The batch orders update message used for cancelations will not
        # detect if the orders exists or not. That will happen when the transaction is executed.
        pass

    @aioresponses()
    def test_cancel_two_orders_with_cancel_all_and_one_fails(self, mock_api):
        # This tests does not apply for Injective. The batch orders update message used for cancelations will not
        # detect if the orders exists or not. That will happen when the transaction is executed.
        pass

    def test_user_stream_balance_update(self):
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        network_config = InjectiveTestnetNetworkMode(testnet_node="sentry")

        account_config = InjectiveDelegatedAccountMode(
            private_key=self.trading_account_private_key,
            subaccount_index=self.trading_account_subaccount_index,
            granter_address=self.portfolio_account_injective_address,
            granter_subaccount_index=1,
        )

        injective_config = InjectiveConfigMap(
            network=network_config,
            account_type=account_config,
            fee_calculator=InjectiveMessageBasedTransactionFeeCalculatorMode(),
        )

        exchange_with_non_default_subaccount = InjectiveV2Exchange(
            client_config_map=client_config_map,
            connector_configuration=injective_config,
            trading_pairs=[self.trading_pair],
        )

        exchange_with_non_default_subaccount._data_source._query_executor = self.exchange._data_source._query_executor
        exchange_with_non_default_subaccount._data_source._composer = Composer(
            network=exchange_with_non_default_subaccount._data_source.network_name
        )
        self.exchange = exchange_with_non_default_subaccount
        self.configure_all_symbols_response(mock_api=None)
        self.exchange._set_current_timestamp(1640780000)

        balance_event = self.balance_event_websocket_update

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [balance_event, asyncio.CancelledError]
        self.exchange._data_source._query_executor._chain_stream_events = mock_queue

        self.async_tasks.append(
            asyncio.get_event_loop().create_task(
                self.exchange._user_stream_event_listener()
            )
        )

        market = self.async_run_with_timeout(
            self.exchange._data_source.spot_market_info_for_id(market_id=self.market_id)
        )
        try:
            self.async_run_with_timeout(
                self.exchange._data_source._listen_to_chain_updates(
                    spot_markets=[market],
                    derivative_markets=[],
                    subaccount_ids=[self.portfolio_account_subaccount_id]
                ),
                timeout=2,
            )
        except asyncio.CancelledError:
            pass

        self.assertEqual(Decimal("10"), self.exchange.available_balances[self.base_asset])
        self.assertEqual(Decimal("15"), self.exchange.get_balance(self.base_asset))

    def test_user_stream_update_for_new_order(self):
        self.configure_all_symbols_response(mock_api=None)

        self.exchange._set_current_timestamp(1640780000)
        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "1",
            exchange_order_id=str(self.expected_exchange_order_id),
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

        order_event = self.order_event_for_new_order_websocket_update(order=order)

        mock_queue = AsyncMock()
        event_messages = [order_event, asyncio.CancelledError]
        mock_queue.get.side_effect = event_messages
        self.exchange._data_source._query_executor._chain_stream_events = mock_queue

        self.async_tasks.append(
            asyncio.get_event_loop().create_task(
                self.exchange._user_stream_event_listener()
            )
        )

        market = self.async_run_with_timeout(
            self.exchange._data_source.spot_market_info_for_id(market_id=self.market_id)
        )
        try:
            self.async_run_with_timeout(
                self.exchange._data_source._listen_to_chain_updates(
                    spot_markets=[market],
                    derivative_markets=[],
                    subaccount_ids=[self.portfolio_account_subaccount_id]
                ),
                timeout=2,
            )
        except asyncio.CancelledError:
            pass

        event: BuyOrderCreatedEvent = self.buy_order_created_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, event.timestamp)
        self.assertEqual(order.order_type, event.type)
        self.assertEqual(order.trading_pair, event.trading_pair)
        self.assertEqual(order.amount, event.amount)
        self.assertEqual(order.price, event.price)
        self.assertEqual(order.client_order_id, event.order_id)
        self.assertEqual(order.exchange_order_id, event.exchange_order_id)
        self.assertTrue(order.is_open)

        tracked_order: InFlightOrder = list(self.exchange.in_flight_orders.values())[0]

        self.assertTrue(self.is_logged("INFO", tracked_order.build_order_created_message()))

    def test_user_stream_update_for_canceled_order(self):
        self.configure_all_symbols_response(mock_api=None)

        self.exchange._set_current_timestamp(1640780000)
        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "1",
            exchange_order_id=str(self.expected_exchange_order_id),
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

        order_event = self.order_event_for_canceled_order_websocket_update(order=order)

        mock_queue = AsyncMock()
        event_messages = [order_event, asyncio.CancelledError]
        mock_queue.get.side_effect = event_messages
        self.exchange._data_source._query_executor._chain_stream_events = mock_queue

        self.async_tasks.append(
            asyncio.get_event_loop().create_task(
                self.exchange._user_stream_event_listener()
            )
        )

        market = self.async_run_with_timeout(
            self.exchange._data_source.spot_market_info_for_id(market_id=self.market_id)
        )
        try:
            self.async_run_with_timeout(
                self.exchange._data_source._listen_to_chain_updates(
                    spot_markets=[market],
                    derivative_markets=[],
                    subaccount_ids=[self.portfolio_account_subaccount_id]
                ),
                timeout=5,
            )
        except asyncio.CancelledError:
            pass

        cancel_event: OrderCancelledEvent = self.order_cancelled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, cancel_event.timestamp)
        self.assertEqual(order.client_order_id, cancel_event.order_id)
        self.assertEqual(order.exchange_order_id, cancel_event.exchange_order_id)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(order.is_cancelled)
        self.assertTrue(order.is_done)

        self.assertTrue(
            self.is_logged("INFO", f"Successfully canceled order {order.client_order_id}.")
        )

    @aioresponses()
    def test_user_stream_update_for_order_full_fill(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "1",
            exchange_order_id=str(self.expected_exchange_order_id),
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

        self.configure_all_symbols_response(mock_api=None)
        order_event = self.order_event_for_full_fill_websocket_update(order=order)
        trade_event = self.trade_event_for_full_fill_websocket_update(order=order)

        chain_stream_queue_mock = AsyncMock()
        messages = []
        if trade_event:
            messages.append(trade_event)
        if order_event:
            messages.append(order_event)
        messages.append(asyncio.CancelledError)

        chain_stream_queue_mock.get.side_effect = messages
        self.exchange._data_source._query_executor._chain_stream_events = chain_stream_queue_mock

        self.async_tasks.append(
            asyncio.get_event_loop().create_task(
                self.exchange._user_stream_event_listener()
            )
        )

        market = self.async_run_with_timeout(
            self.exchange._data_source.spot_market_info_for_id(market_id=self.market_id)
        )
        tasks = [
            asyncio.get_event_loop().create_task(
                self.exchange._data_source._listen_to_chain_updates(
                    spot_markets=[market],
                    derivative_markets=[],
                    subaccount_ids=[self.portfolio_account_subaccount_id]
                )
            ),
        ]
        try:
            self.async_run_with_timeout(safe_gather(*tasks))
        except asyncio.CancelledError:
            pass
        # Execute one more synchronization to ensure the async task that processes the update is finished
        self.async_run_with_timeout(order.wait_until_completely_filled())

        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, fill_event.timestamp)
        self.assertEqual(order.client_order_id, fill_event.order_id)
        self.assertEqual(order.trading_pair, fill_event.trading_pair)
        self.assertEqual(order.trade_type, fill_event.trade_type)
        self.assertEqual(order.order_type, fill_event.order_type)
        self.assertEqual(order.price, fill_event.price)
        self.assertEqual(order.amount, fill_event.amount)
        expected_fee = self.expected_fill_fee
        self.assertEqual(expected_fee, fill_event.trade_fee)

        buy_event: BuyOrderCompletedEvent = self.buy_order_completed_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, buy_event.timestamp)
        self.assertEqual(order.client_order_id, buy_event.order_id)
        self.assertEqual(order.base_asset, buy_event.base_asset)
        self.assertEqual(order.quote_asset, buy_event.quote_asset)
        self.assertEqual(order.amount, buy_event.base_asset_amount)
        self.assertEqual(order.amount * fill_event.price, buy_event.quote_asset_amount)
        self.assertEqual(order.order_type, buy_event.order_type)
        self.assertEqual(order.exchange_order_id, buy_event.exchange_order_id)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(order.is_filled)
        self.assertTrue(order.is_done)

        self.assertTrue(
            self.is_logged(
                "INFO",
                f"BUY order {order.client_order_id} completely filled."
            )
        )

    def test_user_stream_logs_errors(self):
        # This test does not apply to Injective because it handles private events in its own data source
        pass

    def test_user_stream_raises_cancel_exception(self):
        # This test does not apply to Injective because it handles private events in its own data source
        pass

    def test_lost_order_removed_after_cancel_status_user_event_received(self):
        self.configure_all_symbols_response(mock_api=None)

        self.exchange._set_current_timestamp(1640780000)
        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "1",
            exchange_order_id=str(self.expected_exchange_order_id),
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

        for _ in range(self.exchange._order_tracker._lost_order_count_limit + 1):
            self.async_run_with_timeout(
                self.exchange._order_tracker.process_order_not_found(client_order_id=order.client_order_id))

        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)

        order_event = self.order_event_for_canceled_order_websocket_update(order=order)

        mock_queue = AsyncMock()
        event_messages = [order_event, asyncio.CancelledError]
        mock_queue.get.side_effect = event_messages
        self.exchange._data_source._query_executor._chain_stream_events = mock_queue

        self.async_tasks.append(
            asyncio.get_event_loop().create_task(
                self.exchange._user_stream_event_listener()
            )
        )

        market = self.async_run_with_timeout(
            self.exchange._data_source.spot_market_info_for_id(market_id=self.market_id)
        )
        try:
            self.async_run_with_timeout(
                self.exchange._data_source._listen_to_chain_updates(
                    spot_markets=[market],
                    derivative_markets=[],
                    subaccount_ids=[self.portfolio_account_subaccount_id]
                ),
                timeout=5,
            )
        except asyncio.CancelledError:
            pass

        self.assertNotIn(order.client_order_id, self.exchange._order_tracker.lost_orders)
        self.assertEqual(0, len(self.order_cancelled_logger.event_log))
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertFalse(order.is_cancelled)
        self.assertTrue(order.is_failure)

    @aioresponses()
    def test_lost_order_user_stream_full_fill_events_are_processed(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)
        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "1",
            exchange_order_id=str(self.expected_exchange_order_id),
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

        for _ in range(self.exchange._order_tracker._lost_order_count_limit + 1):
            self.async_run_with_timeout(
                self.exchange._order_tracker.process_order_not_found(client_order_id=order.client_order_id))

        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)

        self.configure_all_symbols_response(mock_api=None)
        order_event = self.order_event_for_full_fill_websocket_update(order=order)
        trade_event = self.trade_event_for_full_fill_websocket_update(order=order)

        chain_stream_queue_mock = AsyncMock()
        messages = []
        if trade_event:
            messages.append(trade_event)
        if order_event:
            messages.append(order_event)
        messages.append(asyncio.CancelledError)

        chain_stream_queue_mock.get.side_effect = messages
        self.exchange._data_source._query_executor._chain_stream_events = chain_stream_queue_mock

        self.async_tasks.append(
            asyncio.get_event_loop().create_task(
                self.exchange._user_stream_event_listener()
            )
        )

        market = self.async_run_with_timeout(
            self.exchange._data_source.spot_market_info_for_id(market_id=self.market_id)
        )
        tasks = [
            asyncio.get_event_loop().create_task(
                self.exchange._data_source._listen_to_chain_updates(
                    spot_markets=[market],
                    derivative_markets=[],
                    subaccount_ids=[self.portfolio_account_subaccount_id]
                )
            ),
        ]
        try:
            self.async_run_with_timeout(safe_gather(*tasks))
        except asyncio.CancelledError:
            pass
        # Execute one more synchronization to ensure the async task that processes the update is finished
        self.async_run_with_timeout(order.wait_until_completely_filled())

        fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, fill_event.timestamp)
        self.assertEqual(order.client_order_id, fill_event.order_id)
        self.assertEqual(order.trading_pair, fill_event.trading_pair)
        self.assertEqual(order.trade_type, fill_event.trade_type)
        self.assertEqual(order.order_type, fill_event.order_type)
        self.assertEqual(order.price, fill_event.price)
        self.assertEqual(order.amount, fill_event.amount)
        expected_fee = self.expected_fill_fee
        self.assertEqual(expected_fee, fill_event.trade_fee)

        self.assertEqual(0, len(self.buy_order_completed_logger.event_log))
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertNotIn(order.client_order_id, self.exchange._order_tracker.lost_orders)
        self.assertTrue(order.is_filled)
        self.assertTrue(order.is_failure)

    @aioresponses()
    def test_invalid_trading_pair_not_in_all_trading_pairs(self, mock_api):
        self.exchange._set_trading_pair_symbol_map(None)

        invalid_pair, response = self.all_symbols_including_invalid_pair_mock_response
        self.exchange._data_source._query_executor._spot_markets_responses.put_nowait(response)
        self.exchange._data_source._query_executor._derivative_markets_responses.put_nowait([])

        all_trading_pairs = self.async_run_with_timeout(coroutine=self.exchange.all_trading_pairs())

        self.assertNotIn(invalid_pair, all_trading_pairs)

    @aioresponses()
    def test_check_network_success(self, mock_api):
        response = self.network_status_request_successful_mock_response
        self.exchange._data_source._query_executor._ping_responses.put_nowait(response)

        network_status = self.async_run_with_timeout(coroutine=self.exchange.check_network(), timeout=10)

        self.assertEqual(NetworkStatus.CONNECTED, network_status)

    @aioresponses()
    def test_check_network_failure(self, mock_api):
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = RpcError("Test Error")
        self.exchange._data_source._query_executor._ping_responses = mock_queue

        ret = self.async_run_with_timeout(coroutine=self.exchange.check_network())

        self.assertEqual(ret, NetworkStatus.NOT_CONNECTED)

    @aioresponses()
    def test_check_network_raises_cancel_exception(self, mock_api):
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = asyncio.CancelledError()
        self.exchange._data_source._query_executor._ping_responses = mock_queue

        self.assertRaises(asyncio.CancelledError, self.async_run_with_timeout, self.exchange.check_network())

    @aioresponses()
    def test_get_last_trade_prices(self, mock_api):
        self.configure_all_symbols_response(mock_api=mock_api)
        response = self.latest_prices_request_mock_response
        self.exchange._data_source._query_executor._spot_trades_responses.put_nowait(response)

        latest_prices: Dict[str, float] = self.async_run_with_timeout(
            self.exchange.get_last_traded_prices(trading_pairs=[self.trading_pair])
        )

        self.assertEqual(1, len(latest_prices))
        self.assertEqual(self.expected_latest_price, latest_prices[self.trading_pair])

    def test_get_fee(self):
        self.exchange._data_source._spot_market_and_trading_pair_map = None
        self.exchange._data_source._derivative_market_and_trading_pair_map = None
        self.configure_all_symbols_response(mock_api=None)
        self.async_run_with_timeout(self.exchange._update_trading_fees())

        market = list(self.all_markets_mock_response.values())[0]
        maker_fee_rate = market.maker_fee_rate
        taker_fee_rate = market.taker_fee_rate

        maker_fee = self.exchange.get_fee(
            base_currency=self.base_asset,
            quote_currency=self.quote_asset,
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            amount=Decimal("1000"),
            price=Decimal("5"),
            is_maker=True
        )

        self.assertEqual(maker_fee_rate, maker_fee.percent)
        self.assertEqual(self.quote_asset, maker_fee.percent_token)

        taker_fee = self.exchange.get_fee(
            base_currency=self.base_asset,
            quote_currency=self.quote_asset,
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            amount=Decimal("1000"),
            price=Decimal("5"),
            is_maker=False,
        )

        self.assertEqual(taker_fee_rate, taker_fee.percent)
        self.assertEqual(self.quote_asset, maker_fee.percent_token)

    def test_restore_tracking_states_only_registers_open_orders(self):
        orders = []
        orders.append(GatewayInFlightOrder(
            client_order_id=self.client_order_id_prefix + "1",
            exchange_order_id=str(self.expected_exchange_order_id),
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            price=Decimal("1.0"),
            creation_timestamp=1640001112.223,
        ))
        orders.append(GatewayInFlightOrder(
            client_order_id=self.client_order_id_prefix + "2",
            exchange_order_id=self.exchange_order_id_prefix + "2",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            price=Decimal("1.0"),
            creation_timestamp=1640001112.223,
            initial_state=OrderState.CANCELED
        ))
        orders.append(GatewayInFlightOrder(
            client_order_id=self.client_order_id_prefix + "3",
            exchange_order_id=self.exchange_order_id_prefix + "3",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            price=Decimal("1.0"),
            creation_timestamp=1640001112.223,
            initial_state=OrderState.FILLED
        ))
        orders.append(GatewayInFlightOrder(
            client_order_id=self.client_order_id_prefix + "4",
            exchange_order_id=self.exchange_order_id_prefix + "4",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            price=Decimal("1.0"),
            creation_timestamp=1640001112.223,
            initial_state=OrderState.FAILED
        ))

        tracking_states = {order.client_order_id: order.to_json() for order in orders}

        self.exchange.restore_tracking_states(tracking_states)

        self.assertIn(self.client_order_id_prefix + "1", self.exchange.in_flight_orders)
        self.assertNotIn(self.client_order_id_prefix + "2", self.exchange.in_flight_orders)
        self.assertNotIn(self.client_order_id_prefix + "3", self.exchange.in_flight_orders)
        self.assertNotIn(self.client_order_id_prefix + "4", self.exchange.in_flight_orders)

    @aioresponses()
    def test_update_balances(self, mock_api):
        response = self.balance_request_mock_response_for_base_and_quote
        self._configure_balance_response(response=response, mock_api=mock_api)

        self.async_run_with_timeout(self.exchange._update_balances())

        available_balances = self.exchange.available_balances
        total_balances = self.exchange.get_all_balances()

        self.assertEqual(Decimal("10"), available_balances[self.base_asset])
        self.assertEqual(Decimal("2000"), available_balances[self.quote_asset])
        self.assertEqual(Decimal("15"), total_balances[self.base_asset])
        self.assertEqual(Decimal("2000"), total_balances[self.quote_asset])

        response = self.balance_request_mock_response_only_base

        self._configure_balance_response(response=response, mock_api=mock_api)
        self.async_run_with_timeout(self.exchange._update_balances())

        available_balances = self.exchange.available_balances
        total_balances = self.exchange.get_all_balances()

        self.assertNotIn(self.quote_asset, available_balances)
        self.assertNotIn(self.quote_asset, total_balances)
        self.assertEqual(Decimal("10"), available_balances[self.base_asset])
        self.assertEqual(Decimal("15"), total_balances[self.base_asset])

    def test_order_found_in_its_creating_transaction_not_marked_as_failed_during_order_creation_check(self):
        self.configure_all_symbols_response(mock_api=None)
        self.exchange._set_current_timestamp(1640780000.0)

        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "1",
            exchange_order_id="0x9f94598b4842ab66037eaa7c64ec10ae16dcf196e61db8522921628522c0f62e",  # noqa: mock
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("100"),
            order_type=OrderType.LIMIT,
        )

        self.assertIn(self.client_order_id_prefix + "1", self.exchange.in_flight_orders)
        order: GatewayInFlightOrder = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]
        order.update_creation_transaction_hash(
            creation_transaction_hash="66A360DA2FD6884B53B5C019F1A2B5BED7C7C8FC07E83A9C36AD3362EDE096AE")  # noqa: mock

        transaction_response = {
            "tx": {
                "body": {
                    "messages": [],
                    "timeoutHeight": "20557725",
                    "memo": "",
                    "extensionOptions": [],
                    "nonCriticalExtensionOptions": []
                },
                "authInfo": {},
                "signatures": [
                    "/xSRaq4l5D6DZI5syfAOI5ITongbgJnN97sxCBLXsnFqXLbc4ztEOdQJeIZUuQM+EoqMxUjUyP1S5hg8lM+00w=="
                ]
            },
            "txResponse": {
                "height": "20557627",
                "txhash": "7CC335E98486A7C13133E04561A61930F9F7AD34E6A14A72BC25956F2495CE33",  # noqa: mock"
                "data": "",
                "rawLog": "",
                "logs": [],
                "gasWanted": "209850",
                "gasUsed": "93963",
                "tx": {},
                "timestamp": "2024-01-10T13:23:29Z",
                "events": [
                    {
                        "type": "coin_spent",
                        "attributes": [
                            {
                                "key": "spender",
                                "value": "inj1jtcvrdguuyx6dwz6xszpvkucyplw7z94vxlu07",
                                "index": True
                            },
                            {
                                "key": "amount",
                                "value": "33576000000000inj",
                                "index": True
                            }
                        ]
                    },
                    {
                        "type": "coin_received",
                        "attributes": [
                            {
                                "key": "receiver",
                                "value": "inj17xpfvakm2amg962yls6f84z3kell8c5l6s5ye9",
                                "index": True
                            },
                            {
                                "key": "amount",
                                "value": "33576000000000inj",
                                "index": True
                            }
                        ]
                    },
                    {
                        "type": "transfer",
                        "attributes": [
                            {
                                "key": "recipient",
                                "value": "inj17xpfvakm2amg962yls6f84z3kell8c5l6s5ye9",
                                "index": True
                            },
                            {
                                "key": "sender",
                                "value": "inj1jtcvrdguuyx6dwz6xszpvkucyplw7z94vxlu07",
                                "index": True
                            },
                            {
                                "key": "amount",
                                "value": "33576000000000inj",
                                "index": True
                            }
                        ]
                    },
                    {
                        "type": "message",
                        "attributes": [
                            {
                                "key": "sender",
                                "value": "inj1jtcvrdguuyx6dwz6xszpvkucyplw7z94vxlu07",
                                "index": True
                            }
                        ]
                    },
                    {
                        "type": "tx",
                        "attributes": [
                            {
                                "key": "fee",
                                "value": "33576000000000inj",
                                "index": True
                            },
                            {
                                "key": "fee_payer",
                                "value": "inj1jtcvrdguuyx6dwz6xszpvkucyplw7z94vxlu07",
                                "index": True
                            }
                        ]
                    },
                    {
                        "type": "tx",
                        "attributes": [
                            {
                                "key": "acc_seq",
                                "value": "inj1jtcvrdguuyx6dwz6xszpvkucyplw7z94vxlu07/989",
                                "index": True
                            }
                        ]
                    },
                    {
                        "type": "tx",
                        "attributes": [
                            {
                                "key": "signature",
                                "value": "/xSRaq4l5D6DZI5syfAOI5ITongbgJnN97sxCBLXsnFqXLbc4ztEOdQJeIZUuQM+EoqMxUjUyP1S5hg8lM+00w==",
                                "index": True
                            }
                        ]
                    },
                    {
                        "type": "message",
                        "attributes": [
                            {
                                "key": "action",
                                "value": "/injective.exchange.v1beta1.MsgBatchUpdateOrders",
                                "index": True
                            },
                            {
                                "key": "sender",
                                "value": "inj1jtcvrdguuyx6dwz6xszpvkucyplw7z94vxlu07",
                                "index": True
                            },
                            {
                                "key": "module",
                                "value": "exchange",
                                "index": True
                            }
                        ]
                    },
                    {
                        "type": "injective.exchange.v1beta1.EventNewSpotOrders",
                        "attributes": [
                            {
                                "key": "buy_orders",
                                "value": json.dumps(
                                    [
                                        {
                                            "order_info": {
                                                "subaccount_id": "0xece2f1eea8b02ed71a06c2c9a18e5e56d5e59300000000000000000000000000",  # noqa: mock"
                                                "fee_recipient": "inj175ye6f0xul5vvkztv7pxzfasfjw78e25mq40xk",
                                                "price": "0.000000000475004000",
                                                "quantity": "10000000000000000000.000000000000000000",
                                                "cid": order.client_order_id,
                                            },
                                            "order_type": "BUY_PO",
                                            "fillable": "10000000000000000000.000000000000000000",
                                            "trigger_price": "0.000000000000000000",
                                            "order_hash": base64.b64encode(order.exchange_order_id.encode()).decode()
                                        }
                                    ]
                                ),
                                "index": True
                            },
                            {
                                "key": "market_id",
                                "value": "\"0x0611780ba69656949525013d947713300f56c37b6175e02f26bffa495c3208fe\"",  # noqa: mock"
                                "index": True
                            },
                            {
                                "key": "sell_orders",
                                "value": "[]",
                                "index": True
                            },
                            {
                                "key": "authz_msg_index",
                                "value": "0",
                                "index": True
                            }
                        ]
                    },
                ],
                "codespace": "",
                "code": 0,
                "info": ""
            }
        }

        self.exchange._data_source._query_executor._get_tx_responses.put_nowait(transaction_response)

        self.async_run_with_timeout(self.exchange._check_orders_creation_transactions())

        self.assertEquals(0, len(self.buy_order_created_logger.event_log))
        self.assertEquals(0, len(self.order_failure_logger.event_log))

        self.assertFalse(
            self.is_logged(
                "INFO",
                f"Order {order.client_order_id} has failed. Order Update: OrderUpdate(trading_pair='{self.trading_pair}', "
                f"update_timestamp={self.exchange.current_timestamp}, new_state={repr(OrderState.FAILED)}, "
                f"client_order_id='{order.client_order_id}', exchange_order_id=None, misc_updates=None)"
            )
        )

    # Momentarily disabled
    # @patch("hummingbot.connector.exchange.injective_v2.data_sources.injective_data_source.InjectiveDataSource._time")
    # def test_order_not_found_in_its_creating_transaction_marked_as_failed_during_order_creation_check(self, time_mock):
    #     self.configure_all_symbols_response(mock_api=None)
    #     self.exchange._set_current_timestamp(1640780000.0)
    #     time_mock.return_value = 1640780000.0
    #
    #     self.exchange.start_tracking_order(
    #         order_id=self.client_order_id_prefix + "1",
    #         exchange_order_id="0x9f94598b4842ab66037eaa7c64ec10ae16dcf196e61db8522921628522c0f62e",  # noqa: mock
    #         trading_pair=self.trading_pair,
    #         trade_type=TradeType.BUY,
    #         price=Decimal("10000"),
    #         amount=Decimal("100"),
    #         order_type=OrderType.LIMIT,
    #     )
    #
    #     self.assertIn(self.client_order_id_prefix + "1", self.exchange.in_flight_orders)
    #     order: GatewayInFlightOrder = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]
    #     order.update_creation_transaction_hash(
    #         creation_transaction_hash="66A360DA2FD6884B53B5C019F1A2B5BED7C7C8FC07E83A9C36AD3362EDE096AE")  # noqa: mock
    #
    #     transaction_response = {
    #         "tx": {
    #             "body": {
    #                 "messages": [],
    #                 "timeoutHeight": "20557725",
    #                 "memo": "",
    #                 "extensionOptions": [],
    #                 "nonCriticalExtensionOptions": []
    #             },
    #             "authInfo": {},
    #             "signatures": [
    #                 "/xSRaq4l5D6DZI5syfAOI5ITongbgJnN97sxCBLXsnFqXLbc4ztEOdQJeIZUuQM+EoqMxUjUyP1S5hg8lM+00w=="
    #             ]
    #         },
    #         "txResponse": {
    #             "height": "20557627",
    #             "txhash": "7CC335E98486A7C13133E04561A61930F9F7AD34E6A14A72BC25956F2495CE33",  # noqa: mock"
    #             "data": "",
    #             "rawLog": "",
    #             "logs": [],
    #             "gasWanted": "209850",
    #             "gasUsed": "93963",
    #             "tx": {},
    #             "timestamp": "2024-01-10T13:23:29Z",
    #             "events": [
    #                 {
    #                     "type": "coin_spent",
    #                     "attributes": [
    #                         {
    #                             "key": "spender",
    #                             "value": "inj1jtcvrdguuyx6dwz6xszpvkucyplw7z94vxlu07",
    #                             "index": True
    #                         },
    #                         {
    #                             "key": "amount",
    #                             "value": "33576000000000inj",
    #                             "index": True
    #                         }
    #                     ]
    #                 },
    #                 {
    #                     "type": "coin_received",
    #                     "attributes": [
    #                         {
    #                             "key": "receiver",
    #                             "value": "inj17xpfvakm2amg962yls6f84z3kell8c5l6s5ye9",
    #                             "index": True
    #                         },
    #                         {
    #                             "key": "amount",
    #                             "value": "33576000000000inj",
    #                             "index": True
    #                         }
    #                     ]
    #                 },
    #                 {
    #                     "type": "transfer",
    #                     "attributes": [
    #                         {
    #                             "key": "recipient",
    #                             "value": "inj17xpfvakm2amg962yls6f84z3kell8c5l6s5ye9",
    #                             "index": True
    #                         },
    #                         {
    #                             "key": "sender",
    #                             "value": "inj1jtcvrdguuyx6dwz6xszpvkucyplw7z94vxlu07",
    #                             "index": True
    #                         },
    #                         {
    #                             "key": "amount",
    #                             "value": "33576000000000inj",
    #                             "index": True
    #                         }
    #                     ]
    #                 },
    #                 {
    #                     "type": "message",
    #                     "attributes": [
    #                         {
    #                             "key": "sender",
    #                             "value": "inj1jtcvrdguuyx6dwz6xszpvkucyplw7z94vxlu07",
    #                             "index": True
    #                         }
    #                     ]
    #                 },
    #                 {
    #                     "type": "tx",
    #                     "attributes": [
    #                         {
    #                             "key": "fee",
    #                             "value": "33576000000000inj",
    #                             "index": True
    #                         },
    #                         {
    #                             "key": "fee_payer",
    #                             "value": "inj1jtcvrdguuyx6dwz6xszpvkucyplw7z94vxlu07",
    #                             "index": True
    #                         }
    #                     ]
    #                 },
    #                 {
    #                     "type": "tx",
    #                     "attributes": [
    #                         {
    #                             "key": "acc_seq",
    #                             "value": "inj1jtcvrdguuyx6dwz6xszpvkucyplw7z94vxlu07/989",
    #                             "index": True
    #                         }
    #                     ]
    #                 },
    #                 {
    #                     "type": "tx",
    #                     "attributes": [
    #                         {
    #                             "key": "signature",
    #                             "value": "/xSRaq4l5D6DZI5syfAOI5ITongbgJnN97sxCBLXsnFqXLbc4ztEOdQJeIZUuQM+EoqMxUjUyP1S5hg8lM+00w==",
    #                             "index": True
    #                         }
    #                     ]
    #                 },
    #                 {
    #                     "type": "message",
    #                     "attributes": [
    #                         {
    #                             "key": "action",
    #                             "value": "/injective.exchange.v1beta1.MsgBatchUpdateOrders",
    #                             "index": True
    #                         },
    #                         {
    #                             "key": "sender",
    #                             "value": "inj1jtcvrdguuyx6dwz6xszpvkucyplw7z94vxlu07",
    #                             "index": True
    #                         },
    #                         {
    #                             "key": "module",
    #                             "value": "exchange",
    #                             "index": True
    #                         }
    #                     ]
    #                 },
    #                 {
    #                     "type": "injective.exchange.v1beta1.EventNewSpotOrders",
    #                     "attributes": [
    #                         {
    #                             "key": "buy_orders",
    #                             "value": json.dumps(
    #                                 [
    #                                     {
    #                                         "order_info": {
    #                                             "subaccount_id": "0xf5099d25e6e7e8c6584b67826127b04c9de3e554000000000000000000000000",  # noqa: mock"
    #                                             "fee_recipient": "inj175ye6f0xul5vvkztv7pxzfasfjw78e25mq40xk",
    #                                             "price": "0.000000000475004000",
    #                                             "quantity": "10000000000000000000.000000000000000000",
    #                                             "cid": "HBOTBIJUT60e848f5d7f540cb90799499732"
    #                                         },
    #                                         "order_type": "BUY_PO",
    #                                         "fillable": "10000000000000000000.000000000000000000",
    #                                         "trigger_price": "0.000000000000000000",
    #                                         "order_hash": "DkA7cww2uUIBvKG9hGOM281kpsbjWZKzkMkWbFALBkY="
    #                                     }
    #                                 ]
    #                             ),
    #                             "index": True
    #                         },
    #                         {
    #                             "key": "market_id",
    #                             "value": "\"0x0611780ba69656949525013d947713300f56c37b6175e02f26bffa495c3208fe\"",  # noqa: mock"
    #                             "index": True
    #                         },
    #                         {
    #                             "key": "sell_orders",
    #                             "value": "[]",
    #                             "index": True
    #                         },
    #                         {
    #                             "key": "authz_msg_index",
    #                             "value": "0",
    #                             "index": True
    #                         }
    #                     ]
    #                 },
    #                 {
    #                     "type": "injective.exchange.v1beta1.EventOrderFail",
    #                     "attributes": [
    #                         {
    #                             "key": "account",
    #                             "value": "\"kvDBtRzhDaa4WjQEFluYIH7vCLU=\"",
    #                             "index": True
    #                         },
    #                         {
    #                             "key": "flags",
    #                             "value": "[95]",
    #                             "index": True
    #                         },
    #                         {
    #                             "key": "hashes",
    #                             "value": "[\"X7hrvEMpmG7s/sw9q5l1r6dPyHgx5PkH0LPGOs5rTV0=\"]",
    #                             "index": True,
    #                         }
    #                     ]
    #                 }
    #             ],
    #             "codespace": "",
    #             "code": 0,
    #             "info": ""
    #         }
    #     }
    #
    #     self.exchange._data_source._query_executor._get_tx_responses.put_nowait(transaction_response)
    #
    #     self.async_run_with_timeout(self.exchange._check_orders_creation_transactions())
    #
    #     self.assertEquals(0, len(self.buy_order_created_logger.event_log))
    #     failure_event: MarketOrderFailureEvent = self.order_failure_logger.event_log[0]
    #     self.assertEqual(self.exchange.current_timestamp, failure_event.timestamp)
    #     self.assertEqual(OrderType.LIMIT, failure_event.order_type)
    #     self.assertEqual(order.client_order_id, failure_event.order_id)
    #
    #     self.assertTrue(
    #         self.is_logged(
    #             "INFO",
    #             f"Order {order.client_order_id} has failed. Order Update: OrderUpdate(trading_pair='{self.trading_pair}', "
    #             f"update_timestamp={self.exchange.current_timestamp}, new_state={repr(OrderState.FAILED)}, "
    #             f"client_order_id='{order.client_order_id}', exchange_order_id=None, misc_updates=None)"
    #         )
    #     )

    @patch("hummingbot.connector.exchange.injective_v2.data_sources.injective_data_source.InjectiveDataSource._time")
    def test_order_in_failed_transaction_marked_as_failed_during_order_creation_check(self, time_mock):
        self.configure_all_symbols_response(mock_api=None)
        self.exchange._set_current_timestamp(1640780000.0)
        time_mock.return_value = 1640780000.0

        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "1",
            exchange_order_id="0x9f94598b4842ab66037eaa7c64ec10ae16dcf196e61db8522921628522c0f62e",  # noqa: mock
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("100"),
            order_type=OrderType.LIMIT,
        )

        self.assertIn(self.client_order_id_prefix + "1", self.exchange.in_flight_orders)
        order: GatewayInFlightOrder = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]
        order.update_creation_transaction_hash(
            creation_transaction_hash="66A360DA2FD6884B53B5C019F1A2B5BED7C7C8FC07E83A9C36AD3362EDE096AE")  # noqa: mock

        transaction_response = {
            "tx": {
                "body": {
                    "messages": [],
                    "timeoutHeight": "20557725",
                    "memo": "",
                    "extensionOptions": [],
                    "nonCriticalExtensionOptions": []
                },
                "authInfo": {},
                "signatures": [
                    "/xSRaq4l5D6DZI5syfAOI5ITongbgJnN97sxCBLXsnFqXLbc4ztEOdQJeIZUuQM+EoqMxUjUyP1S5hg8lM+00w=="
                ]
            },
            "txResponse": {
                "height": "20557627",
                "txhash": "7CC335E98486A7C13133E04561A61930F9F7AD34E6A14A72BC25956F2495CE33",  # noqa: mock"
                "data": "",
                "rawLog": "",
                "logs": [],
                "gasWanted": "209850",
                "gasUsed": "93963",
                "tx": {},
                "timestamp": "2024-01-10T13:23:29Z",
                "events": [],
                "codespace": "",
                "code": 5,
                "info": ""
            }
        }

        self.exchange._data_source._query_executor._get_tx_responses.put_nowait(transaction_response)

        self.async_run_with_timeout(self.exchange._check_orders_creation_transactions())

        self.assertEquals(0, len(self.buy_order_created_logger.event_log))
        failure_event: MarketOrderFailureEvent = self.order_failure_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, failure_event.timestamp)
        self.assertEqual(OrderType.LIMIT, failure_event.order_type)
        self.assertEqual(order.client_order_id, failure_event.order_id)

        self.assertTrue(
            self.is_logged(
                "INFO",
                f"Order {order.client_order_id} has failed. Order Update: OrderUpdate(trading_pair='{self.trading_pair}', "
                f"update_timestamp={self.exchange.current_timestamp}, new_state={repr(OrderState.FAILED)}, "
                f"client_order_id='{order.client_order_id}', exchange_order_id=None, misc_updates=None)"
            )
        )

    def _expected_initial_status_dict(self) -> Dict[str, bool]:
        status_dict = super()._expected_initial_status_dict()
        status_dict["data_source_initialized"] = False
        return status_dict

    @staticmethod
    def _callback_wrapper_with_response(callback: Callable, response: Any, *args, **kwargs):
        callback(args, kwargs)
        if isinstance(response, Exception):
            raise response
        else:
            return response

    def _configure_balance_response(
            self,
            response: Dict[str, Any],
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> str:
        all_markets_mock_response = self.all_markets_mock_response
        self.exchange._data_source._query_executor._spot_markets_responses.put_nowait(all_markets_mock_response)
        market = list(all_markets_mock_response.values())[0]
        self.exchange._data_source._query_executor._tokens_responses.put_nowait(
            {token.symbol: token for token in [market.base_token, market.quote_token]}
        )
        self.exchange._data_source._query_executor._derivative_markets_responses.put_nowait({})
        self.exchange._data_source._query_executor._account_portfolio_responses.put_nowait(response)
        return ""

    def _msg_exec_simulation_mock_response(self) -> Any:
        return {
            "gasInfo": {
                "gasWanted": "50000000",
                "gasUsed": "90749"
            },
            "result": {
                "data": "Em8KJS9jb3Ntb3MuYXV0aHoudjFiZXRhMS5Nc2dFeGVjUmVzcG9uc2USRgpECkIweGYxNGU5NGMxZmQ0MjE0M2I3ZGRhZjA4ZDE3ZWMxNzAzZGMzNzZlOWU2YWI0YjY0MjBhMzNkZTBhZmFlYzJjMTA=",
                "log": "",
                "events": [],
                "msgResponses": [
                    OrderedDict([
                        ("@type", "/cosmos.authz.v1beta1.MsgExecResponse"),
                        ("results", [
                            "CkIweGYxNGU5NGMxZmQ0MjE0M2I3ZGRhZjA4ZDE3ZWMxNzAzZGMzNzZlOWU2YWI0YjY0MjBhMzNkZTBhZmFlYzJjMTA="])
                    ])
                ]
            }
        }

    def _order_cancelation_request_successful_mock_response(self, order: InFlightOrder) -> Dict[str, Any]:
        return {"txhash": "79DBF373DE9C534EE2DC9D009F32B850DA8D0C73833FAA0FD52C6AE8989EC659",  # noqa: mock"
                "rawLog": "[]",
                "code": 0}  # noqa: mock

    def _order_cancelation_request_erroneous_mock_response(self, order: InFlightOrder) -> Dict[str, Any]:
        return {"txhash": "79DBF373DE9C534EE2DC9D009F32B850DA8D0C73833FAA0FD52C6AE8989EC659",  # noqa: mock"
                "rawLog": "Error",
                "code": 11}  # noqa: mock

    def _order_status_request_open_mock_response(self, order: GatewayInFlightOrder) -> Dict[str, Any]:
        return {
            "orders": [
                {
                    "orderHash": order.exchange_order_id,
                    "cid": order.client_order_id,
                    "marketId": self.market_id,
                    "isActive": True,
                    "subaccountId": self.portfolio_account_subaccount_id,
                    "executionType": "market" if order.order_type == OrderType.MARKET else "limit",
                    "orderType": order.trade_type.name.lower(),
                    "price": str(order.price * Decimal(f"1e{self.quote_decimals - self.base_decimals}")),
                    "triggerPrice": "0",
                    "quantity": str(order.amount * Decimal(f"1e{self.base_decimals}")),
                    "filledQuantity": "0",
                    "state": "booked",
                    "createdAt": "1688476825015",
                    "updatedAt": "1688476825015",
                    "direction": order.trade_type.name.lower(),
                    "txHash": order.creation_transaction_hash
                },
            ],
            "paging": {
                "total": "1"
            },
        }

    def _order_status_request_partially_filled_mock_response(self, order: GatewayInFlightOrder) -> Dict[str, Any]:
        return {
            "orders": [
                {
                    "orderHash": order.exchange_order_id,
                    "cid": order.client_order_id,
                    "marketId": self.market_id,
                    "isActive": True,
                    "subaccountId": self.portfolio_account_subaccount_id,
                    "executionType": "market" if order.order_type == OrderType.MARKET else "limit",
                    "orderType": order.trade_type.name.lower(),
                    "price": str(order.price * Decimal(f"1e{self.quote_decimals - self.base_decimals}")),
                    "triggerPrice": "0",
                    "quantity": str(order.amount * Decimal(f"1e{self.base_decimals}")),
                    "filledQuantity": str(self.expected_partial_fill_amount * Decimal(f"1e{self.base_decimals}")),
                    "state": "partial_filled",
                    "createdAt": "1688476825015",
                    "updatedAt": "1688476825015",
                    "direction": order.trade_type.name.lower(),
                    "txHash": order.creation_transaction_hash
                },
            ],
            "paging": {
                "total": "1"
            },
        }

    def _order_status_request_completely_filled_mock_response(self, order: GatewayInFlightOrder) -> Dict[str, Any]:
        return {
            "orders": [
                {
                    "orderHash": order.exchange_order_id,
                    "cid": order.client_order_id,
                    "marketId": self.market_id,
                    "isActive": True,
                    "subaccountId": self.portfolio_account_subaccount_id,
                    "executionType": "market" if order.order_type == OrderType.MARKET else "limit",
                    "orderType": order.trade_type.name.lower(),
                    "price": str(order.price * Decimal(f"1e{self.quote_decimals - self.base_decimals}")),
                    "triggerPrice": "0",
                    "quantity": str(order.amount * Decimal(f"1e{self.base_decimals}")),
                    "filledQuantity": str(order.amount * Decimal(f"1e{self.base_decimals}")),
                    "state": "filled",
                    "createdAt": "1688476825015",
                    "updatedAt": "1688476825015",
                    "direction": order.trade_type.name.lower(),
                    "txHash": order.creation_transaction_hash
                },
            ],
            "paging": {
                "total": "1"
            },
        }

    def _order_status_request_canceled_mock_response(self, order: GatewayInFlightOrder) -> Dict[str, Any]:
        return {
            "orders": [
                {
                    "orderHash": order.exchange_order_id,
                    "cid": order.client_order_id,
                    "marketId": self.market_id,
                    "isActive": True,
                    "subaccountId": self.portfolio_account_subaccount_id,
                    "executionType": "market" if order.order_type == OrderType.MARKET else "limit",
                    "orderType": order.trade_type.name.lower(),
                    "price": str(order.price * Decimal(f"1e{self.quote_decimals - self.base_decimals}")),
                    "triggerPrice": "0",
                    "quantity": str(order.amount * Decimal(f"1e{self.base_decimals}")),
                    "filledQuantity": "0",
                    "state": "canceled",
                    "createdAt": "1688476825015",
                    "updatedAt": "1688476825015",
                    "direction": order.trade_type.name.lower(),
                    "txHash": order.creation_transaction_hash
                },
            ],
            "paging": {
                "total": "1"
            },
        }

    def _order_status_request_not_found_mock_response(self, order: GatewayInFlightOrder) -> Dict[str, Any]:
        return {
            "orders": [],
            "paging": {
                "total": "0"
            },
        }

    def _order_fills_request_partial_fill_mock_response(self, order: GatewayInFlightOrder) -> Dict[str, Any]:
        return {
            "trades": [
                {
                    "orderHash": order.exchange_order_id,
                    "cid": order.client_order_id,
                    "subaccountId": self.portfolio_account_subaccount_id,
                    "marketId": self.market_id,
                    "tradeExecutionType": "limitFill",
                    "tradeDirection": order.trade_type.name.lower(),
                    "price": {
                        "price": str(self.expected_partial_fill_price * Decimal(
                            f"1e{self.quote_decimals - self.base_decimals}")),
                        "quantity": str(self.expected_partial_fill_amount * Decimal(f"1e{self.base_decimals}")),
                        "timestamp": "1681735786785"
                    },
                    "fee": str(self.expected_fill_fee.flat_fees[0].amount * Decimal(f"1e{self.quote_decimals}")),
                    "executedAt": "1681735786785",
                    "feeRecipient": self.portfolio_account_injective_address,
                    "tradeId": self.expected_fill_trade_id,
                    "executionSide": "maker"
                },
            ],
            "paging": {
                "total": "1",
                "from": 1,
                "to": 1
            }
        }

    def _order_fills_request_full_fill_mock_response(self, order: GatewayInFlightOrder) -> Dict[str, Any]:
        return {
            "trades": [
                {
                    "orderHash": order.exchange_order_id,
                    "cid": order.client_order_id,
                    "subaccountId": self.portfolio_account_subaccount_id,
                    "marketId": self.market_id,
                    "tradeExecutionType": "limitFill",
                    "tradeDirection": order.trade_type.name.lower(),
                    "price": {
                        "price": str(order.price * Decimal(f"1e{self.quote_decimals - self.base_decimals}")),
                        "quantity": str(order.amount * Decimal(f"1e{self.base_decimals}")),
                        "timestamp": "1681735786785"
                    },
                    "fee": str(self.expected_fill_fee.flat_fees[0].amount * Decimal(f"1e{self.quote_decimals}")),
                    "executedAt": "1681735786785",
                    "feeRecipient": self.portfolio_account_injective_address,
                    "tradeId": self.expected_fill_trade_id,
                    "executionSide": "maker"
                },
            ],
            "paging": {
                "total": "1",
                "from": 1,
                "to": 1
            }
        }
