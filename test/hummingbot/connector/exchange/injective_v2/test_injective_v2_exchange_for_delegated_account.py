import asyncio
import base64
import json
from collections import OrderedDict
from decimal import Decimal
from functools import partial
from test.hummingbot.connector.exchange.injective_v2.programmable_query_executor import ProgrammableQueryExecutor
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from unittest.mock import AsyncMock, MagicMock

from aioresponses import aioresponses
from aioresponses.core import RequestCall
from bidict import bidict
from grpc import RpcError
from pyinjective.composer import Composer
from pyinjective.orderhash import OrderHashManager, OrderHashResponse
from pyinjective.wallet import Address, PrivateKey

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.injective_v2.injective_v2_exchange import InjectiveV2Exchange
from hummingbot.connector.exchange.injective_v2.injective_v2_utils import (
    InjectiveConfigMap,
    InjectiveDelegatedAccountMode,
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
        cls.market_id = "0x0611780ba69656949525013d947713300f56c37b6175e02f26bffa495c3208fe" # noqa: mock

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
                    "subaccountId": "0xa73ad39eab064051fb468a5965ee48ca87ab66d4000000000000000000000000",  # noqa: mock
                    "marketId": "0x0611780ba69656949525013d947713300f56c37b6175e02f26bffa495c3208fe",  # noqa: mock
                    "tradeExecutionType": "limitMatchRestingOrder",
                    "tradeDirection": "sell",
                    "price": {
                        "price": str(Decimal(str(self.expected_latest_price)) * Decimal(f"1e{self.quote_decimals - self.base_decimals}")),
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
        response.append({
            "marketId": "invalid_market_id",
            "marketStatus": "active",
            "ticker": "INVALID/MARKET",
            "makerFeeRate": "-0.0001",
            "takerFeeRate": "0.001",
            "serviceProviderFee": "0.4",
            "minPriceTickSize": "0.000000000000001",
            "minQuantityTickSize": "1000000000000000"
        })

        return ("INVALID_MARKET", response)

    @property
    def network_status_request_successful_mock_response(self):
        return {}

    @property
    def trading_rules_request_mock_response(self):
        raise NotImplementedError

    @property
    def trading_rules_request_erroneous_mock_response(self):
        return [{
            "marketId": self.market_id,
            "marketStatus": "active",
            "ticker": f"{self.base_asset}/{self.quote_asset}",
            "baseDenom": self.base_asset_denom,
            "baseTokenMeta": {
                "name": "Base Asset",
                "address": "0xe28b3B32B6c345A34Ff64674606124Dd5Aceca30",  # noqa: mock
                "symbol": self.base_asset,
                "logo": "https://static.alchemyapi.io/images/assets/7226.png",
                "decimals": 18,
                "updatedAt": "1687190809715"
            },
            "quoteDenom": self.quote_asset_denom,  # noqa: mock
            "quoteTokenMeta": {
                "name": "Quote Asset",
                "address": "0x0000000000000000000000000000000000000000",  # noqa: mock
                "symbol": self.quote_asset,
                "logo": "https://static.alchemyapi.io/images/assets/825.png",
                "decimals": 6,
                "updatedAt": "1687190809716"
            },
            "makerFeeRate": "-0.0001",
            "takerFeeRate": "0.001",
            "serviceProviderFee": "0.4",
        }]

    @property
    def order_creation_request_successful_mock_response(self):
        return {"txhash": "017C130E3602A48E5C9D661CAC657BF1B79262D4B71D5C25B1DA62DE2338DA0E", "rawLog": "[]"}  # noqa: mock

    @property
    def balance_request_mock_response_for_base_and_quote(self):
        return {
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
            ]
        }

    @property
    def balance_request_mock_response_only_base(self):
        return {
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
            ]
        }

    @property
    def balance_event_websocket_update(self):
        return {
            "balance": {
                "subaccountId": self.portfolio_account_subaccount_id,
                "accountAddress": self.portfolio_account_injective_address,
                "denom": self.base_asset_denom,
                "deposit": {
                    "totalBalance": str(Decimal(15) * Decimal(1e18)),
                    "availableBalance": str(Decimal(10) * Decimal(1e18)),
                }
            },
            "timestamp": "1688659208000"
        }

    @property
    def expected_latest_price(self):
        return 9999.9

    @property
    def expected_supported_order_types(self) -> List[OrderType]:
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    @property
    def expected_trading_rule(self):
        market_info = self.all_markets_mock_response[0]
        min_price_tick_size = (Decimal(market_info["minPriceTickSize"])
                               * Decimal(f"1e{market_info['baseTokenMeta']['decimals']-market_info['quoteTokenMeta']['decimals']}"))
        min_quantity_tick_size = Decimal(market_info["minQuantityTickSize"]) * Decimal(
            f"1e{-market_info['baseTokenMeta']['decimals']}")
        trading_rule = TradingRule(
            trading_pair=self.trading_pair,
            min_order_size=min_quantity_tick_size,
            min_price_increment=min_price_tick_size,
            min_base_amount_increment=min_quantity_tick_size,
            min_quote_amount_increment=min_price_tick_size,
        )

        return trading_rule

    @property
    def expected_logged_error_for_erroneous_trading_rule(self):
        erroneous_rule = self.trading_rules_request_erroneous_mock_response[0]
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
        return [{
            "marketId": self.market_id,
            "marketStatus": "active",
            "ticker": f"{self.base_asset}/{self.quote_asset}",
            "baseDenom": self.base_asset_denom,
            "baseTokenMeta": {
                "name": "Base Asset",
                "address": "0xe28b3B32B6c345A34Ff64674606124Dd5Aceca30",  # noqa: mock
                "symbol": self.base_asset,
                "logo": "https://static.alchemyapi.io/images/assets/7226.png",
                "decimals": self.base_decimals,
                "updatedAt": "1687190809715"
            },
            "quoteDenom": self.quote_asset_denom,  # noqa: mock
            "quoteTokenMeta": {
                "name": "Quote Asset",
                "address": "0x0000000000000000000000000000000000000000",  # noqa: mock
                "symbol": self.quote_asset,
                "logo": "https://static.alchemyapi.io/images/assets/825.png",
                "decimals": self.quote_decimals,
                "updatedAt": "1687190809716"
            },
            "makerFeeRate": "-0.0001",
            "takerFeeRate": "0.001",
            "serviceProviderFee": "0.4",
            "minPriceTickSize": "0.000000000000001",
            "minQuantityTickSize": "1000000000000000"
        }]

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
        self.exchange._data_source._query_executor._derivative_markets_responses.put_nowait([])
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
        self.exchange._data_source._query_executor._derivative_markets_responses.put_nowait([])
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

        self.exchange._data_source._query_executor._spot_trades_responses.put_nowait({"trades": [], "paging": {"total": "0"}})

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
            "orderHash": order.exchange_order_id,
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
            "createdAt": "1688667498756",
            "updatedAt": "1688667498756",
            "direction": order.trade_type.name.lower(),
            "txHash": "0x0000000000000000000000000000000000000000000000000000000000000000"  # noqa: mock
        }

    def order_event_for_canceled_order_websocket_update(self, order: InFlightOrder):
        return {
            "orderHash": order.exchange_order_id,
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
            "createdAt": "1688667498756",
            "updatedAt": "1688667498756",
            "direction": order.trade_type.name.lower(),
            "txHash": "0x0000000000000000000000000000000000000000000000000000000000000000"  # noqa: mock
        }

    def order_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return {
            "orderHash": order.exchange_order_id,
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
        }

    def trade_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return {
            "orderHash": order.exchange_order_id,
            "subaccountId": self.portfolio_account_subaccount_id,
            "marketId": self.market_id,
            "tradeExecutionType": "limitMatchRestingOrder",
            "tradeDirection": order.trade_type.name.lower(),
            "price": {
                "price": str(order.price * Decimal(f"1e{self.quote_decimals - self.base_decimals}")),
                "quantity": str(order.amount * Decimal(f"1e{self.base_decimals}")),
                "timestamp": "1687878089569"
            },
            "fee": str(self.expected_fill_fee.flat_fees[0].amount * Decimal(f"1e{self.quote_decimals}")),
            "executedAt": "1687878089569",
            "feeRecipient": self.portfolio_account_injective_address,  # noqa: mock
            "tradeId": self.expected_fill_trade_id,
            "executionSide": "maker"
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
        self.exchange._data_source._order_hash_manager = MagicMock(spec=OrderHashManager)
        self.exchange._data_source._order_hash_manager.compute_order_hashes.return_value = OrderHashResponse(
            spot=["hash1", "hash2"], derivative=[]
        )

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
            buy_order_to_create_in_flight.exchange_order_id,
            self.exchange.in_flight_orders[buy_order_to_create_in_flight.client_order_id].exchange_order_id
        )
        self.assertEqual(
            buy_order_to_create_in_flight.creation_transaction_hash,
            self.exchange.in_flight_orders[buy_order_to_create_in_flight.client_order_id].creation_transaction_hash
        )
        self.assertEqual(
            sell_order_to_create_in_flight.exchange_order_id,
            self.exchange.in_flight_orders[sell_order_to_create_in_flight.client_order_id].exchange_order_id
        )
        self.assertEqual(
            sell_order_to_create_in_flight.creation_transaction_hash,
            self.exchange.in_flight_orders[sell_order_to_create_in_flight.client_order_id].creation_transaction_hash
        )

    def test_batch_order_create_with_one_market_order(self):
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._data_source._order_hash_manager = MagicMock(spec=OrderHashManager)
        self.exchange._data_source._order_hash_manager.compute_order_hashes.return_value = OrderHashResponse(
            spot=["hash1", "hash2"], derivative=[]
        )

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
            buy_order_to_create_in_flight.exchange_order_id,
            self.exchange.in_flight_orders[buy_order_to_create_in_flight.client_order_id].exchange_order_id
        )
        self.assertEqual(
            buy_order_to_create_in_flight.creation_transaction_hash,
            self.exchange.in_flight_orders[buy_order_to_create_in_flight.client_order_id].creation_transaction_hash
        )
        self.assertEqual(
            sell_order_to_create_in_flight.exchange_order_id,
            self.exchange.in_flight_orders[sell_order_to_create_in_flight.client_order_id].exchange_order_id
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
        self.exchange._data_source._order_hash_manager = MagicMock(spec=OrderHashManager)
        self.exchange._data_source._order_hash_manager.compute_order_hashes.return_value = OrderHashResponse(
            spot=["hash1"], derivative=[]
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

        order_id = self.place_buy_order()
        self.async_run_with_timeout(request_sent_event.wait())

        self.assertEqual(1, len(self.exchange.in_flight_orders))
        self.assertIn(order_id, self.exchange.in_flight_orders)

        order = self.exchange.in_flight_orders[order_id]

        self.assertEqual("hash1", order.exchange_order_id)
        self.assertEqual(response["txhash"], order.creation_transaction_hash)

    @aioresponses()
    def test_create_sell_limit_order_successfully(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._data_source._order_hash_manager = MagicMock(spec=OrderHashManager)
        self.exchange._data_source._order_hash_manager.compute_order_hashes.return_value = OrderHashResponse(
            spot=["hash1"], derivative=[]
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

        order_id = self.place_sell_order()
        self.async_run_with_timeout(request_sent_event.wait())

        self.assertEqual(1, len(self.exchange.in_flight_orders))
        self.assertIn(order_id, self.exchange.in_flight_orders)

        order = self.exchange.in_flight_orders[order_id]

        self.assertEqual("hash1", order.exchange_order_id)
        self.assertEqual(response["txhash"], order.creation_transaction_hash)

    @aioresponses()
    def test_create_buy_market_order_successfully(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._data_source._order_hash_manager = MagicMock(spec=OrderHashManager)
        self.exchange._data_source._order_hash_manager.compute_order_hashes.return_value = OrderHashResponse(
            spot=["hash1"], derivative=[]
        )

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

        self.assertEqual("hash1", order.exchange_order_id)
        self.assertEqual(response["txhash"], order.creation_transaction_hash)
        self.assertEqual(expected_price_for_volume, order.price)

    @aioresponses()
    def test_create_sell_market_order_successfully(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._data_source._order_hash_manager = MagicMock(spec=OrderHashManager)
        self.exchange._data_source._order_hash_manager.compute_order_hashes.return_value = OrderHashResponse(
            spot=["hash1"], derivative=[]
        )

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

        self.assertEqual("hash1", order.exchange_order_id)
        self.assertEqual(response["txhash"], order.creation_transaction_hash)
        self.assertEqual(expected_price_for_volume, order.price)

    @aioresponses()
    def test_create_order_fails_and_raises_failure_event(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)
        self.exchange._data_source._order_hash_manager = MagicMock(spec=OrderHashManager)
        self.exchange._data_source._order_hash_manager.compute_order_hashes.return_value = OrderHashResponse(
            spot=["hash1"], derivative=[]
        )

        transaction_simulation_response = self._msg_exec_simulation_mock_response()
        self.exchange._data_source._query_executor._simulate_transaction_responses.put_nowait(
            transaction_simulation_response)

        response = {"txhash": "", "rawLog": "Error"}
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
        # The second order is used only to have the event triggered and avoid using timeouts for tests
        self.exchange._data_source._order_hash_manager = MagicMock(spec=OrderHashManager)
        self.exchange._data_source._order_hash_manager.compute_order_hashes.return_value = OrderHashResponse(
            spot=["hash1"], derivative=[]
        )

        transaction_simulation_response = self._msg_exec_simulation_mock_response()
        self.exchange._data_source._query_executor._simulate_transaction_responses.put_nowait(
            transaction_simulation_response)

        response = {"txhash": "", "rawLog": "Error"}
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
        self.exchange._data_source._query_executor._simulate_transaction_responses.put_nowait(transaction_simulation_response)

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

    def test_order_not_found_in_its_creating_transaction_marked_as_failed_during_order_creation_check(self):
        self.configure_all_symbols_response(mock_api=None)
        self.exchange._set_current_timestamp(1640780000)

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
        order.update_creation_transaction_hash(creation_transaction_hash="66A360DA2FD6884B53B5C019F1A2B5BED7C7C8FC07E83A9C36AD3362EDE096AE")  # noqa: mock

        transaction_data = (b'\x12\xd1\x01\n8/injective.exchange.v1beta1.MsgBatchUpdateOrdersResponse'
                            b'\x12\x94\x01\n\x02\x00\x00\x12\x02\x00\x00\x1aB'
                            b'0xc5d66f56942e1ae407c01eedccd0471deb8e202a514cde3bae56a8307e376cd1'  # noqa: mock
                            b'\x1aB'
                            b'0x115975551b4f86188eee6b93d789fcc78df6e89e40011b929299b6e142f53515'  # noqa: mock
                            b'"\x00"\x00')
        transaction_messages = [
            {
                "type": "/cosmos.authz.v1beta1.MsgExec",
                "value": {
                    "grantee": PrivateKey.from_hex(self.trading_account_private_key).to_public_key().to_acc_bech32(),
                    "msgs": [
                        {
                            "@type": "/injective.exchange.v1beta1.MsgBatchUpdateOrders",
                            "sender": self.portfolio_account_injective_address,
                            "subaccount_id": "",
                            "spot_market_ids_to_cancel_all": [],
                            "derivative_market_ids_to_cancel_all": [],
                            "spot_orders_to_cancel": [],
                            "derivative_orders_to_cancel": [],
                            "spot_orders_to_create": [
                                {
                                    "market_id": self.market_id,
                                    "order_info": {
                                        "subaccount_id": self.portfolio_account_subaccount_id,
                                        "fee_recipient": self.portfolio_account_injective_address,
                                        "price": str(order.price * Decimal(f"1e{self.quote_decimals - self.base_decimals}")),
                                        "quantity": str((order.amount + Decimal(1)) * Decimal(f"1e{self.base_decimals}"))
                                    },
                                    "order_type": order.trade_type.name,
                                    "trigger_price": "0.000000000000000000"
                                }
                            ],
                            "derivative_orders_to_create": [],
                            "binary_options_orders_to_cancel": [],
                            "binary_options_market_ids_to_cancel_all": [],
                            "binary_options_orders_to_create": []
                        }
                    ]
                }
            }
        ]
        transaction_response = {
            "s": "ok",
            "data": {
                "blockNumber": "13302254",
                "blockTimestamp": "2023-07-05 13:55:09.94 +0000 UTC",
                "hash": "0x66a360da2fd6884b53b5c019f1a2b5bed7c7c8fc07e83a9c36ad3362ede096ae",  # noqa: mock
                "data": base64.b64encode(transaction_data).decode(),
                "gasWanted": "168306",
                "gasUsed": "167769",
                "gasFee": {
                    "amount": [
                        {
                            "denom": "inj",
                            "amount": "84153000000000"
                        }
                    ],
                    "gasLimit": "168306",
                    "payer": "inj1hkhdaj2a2clmq5jq6mspsggqs32vynpk228q3r"  # noqa: mock
                },
                "txType": "injective",
                "messages": base64.b64encode(json.dumps(transaction_messages).encode()).decode(),
                "signatures": [
                    {
                        "pubkey": "035ddc4d5642b9383e2f087b2ee88b7207f6286ebc9f310e9df1406eccc2c31813",  # noqa: mock
                        "address": "inj1hkhdaj2a2clmq5jq6mspsggqs32vynpk228q3r",  # noqa: mock
                        "sequence": "16450",
                        "signature": "S9atCwiVg9+8vTpbciuwErh54pJOAry3wHvbHT2fG8IumoE+7vfuoP7mAGDy2w9am+HHa1yv60VSWo3cRhWC9g=="
                    }
                ],
                "txNumber": "13182",
                "blockUnixTimestamp": "1688565309940",
                "logs": "W3sibXNnX2luZGV4IjowLCJldmVudHMiOlt7InR5cGUiOiJtZXNzYWdlIiwiYXR0cmlidXRlcyI6W3sia2V5IjoiYWN0aW9uIiwidmFsdWUiOiIvaW5qZWN0aXZlLmV4Y2hhbmdlLnYxYmV0YTEuTXNnQmF0Y2hVcGRhdGVPcmRlcnMifSx7ImtleSI6InNlbmRlciIsInZhbHVlIjoiaW5qMWhraGRhajJhMmNsbXE1anE2bXNwc2dncXMzMnZ5bnBrMjI4cTNyIn0seyJrZXkiOiJtb2R1bGUiLCJ2YWx1ZSI6ImV4Y2hhbmdlIn1dfSx7InR5cGUiOiJjb2luX3NwZW50IiwiYXR0cmlidXRlcyI6W3sia2V5Ijoic3BlbmRlciIsInZhbHVlIjoiaW5qMWhraGRhajJhMmNsbXE1anE2bXNwc2dncXMzMnZ5bnBrMjI4cTNyIn0seyJrZXkiOiJhbW91bnQiLCJ2YWx1ZSI6IjE2NTE2NTAwMHBlZ2d5MHg4N2FCM0I0Qzg2NjFlMDdENjM3MjM2MTIxMUI5NmVkNERjMzZCMUI1In1dfSx7InR5cGUiOiJjb2luX3JlY2VpdmVkIiwiYXR0cmlidXRlcyI6W3sia2V5IjoicmVjZWl2ZXIiLCJ2YWx1ZSI6ImluajE0dm5tdzJ3ZWUzeHRyc3FmdnBjcWczNWpnOXY3ajJ2ZHB6eDBrayJ9LHsia2V5IjoiYW1vdW50IiwidmFsdWUiOiIxNjUxNjUwMDBwZWdneTB4ODdhQjNCNEM4NjYxZTA3RDYzNzIzNjEyMTFCOTZlZDREYzM2QjFCNSJ9XX0seyJ0eXBlIjoidHJhbnNmZXIiLCJhdHRyaWJ1dGVzIjpbeyJrZXkiOiJyZWNpcGllbnQiLCJ2YWx1ZSI6ImluajE0dm5tdzJ3ZWUzeHRyc3FmdnBjcWczNWpnOXY3ajJ2ZHB6eDBrayJ9LHsia2V5Ijoic2VuZGVyIiwidmFsdWUiOiJpbmoxaGtoZGFqMmEyY2xtcTVqcTZtc3BzZ2dxczMydnlucGsyMjhxM3IifSx7ImtleSI6ImFtb3VudCIsInZhbHVlIjoiMTY1MTY1MDAwcGVnZ3kweDg3YUIzQjRDODY2MWUwN0Q2MzcyMzYxMjExQjk2ZWQ0RGMzNkIxQjUifV19LHsidHlwZSI6Im1lc3NhZ2UiLCJhdHRyaWJ1dGVzIjpbeyJrZXkiOiJzZW5kZXIiLCJ2YWx1ZSI6ImluajFoa2hkYWoyYTJjbG1xNWpxNm1zcHNnZ3FzMzJ2eW5wazIyOHEzciJ9XX0seyJ0eXBlIjoiY29pbl9zcGVudCIsImF0dHJpYnV0ZXMiOlt7ImtleSI6InNwZW5kZXIiLCJ2YWx1ZSI6ImluajFoa2hkYWoyYTJjbG1xNWpxNm1zcHNnZ3FzMzJ2eW5wazIyOHEzciJ9LHsia2V5IjoiYW1vdW50IiwidmFsdWUiOiI1NTAwMDAwMDAwMDAwMDAwMDAwMGluaiJ9XX0seyJ0eXBlIjoiY29pbl9yZWNlaXZlZCIsImF0dHJpYnV0ZXMiOlt7ImtleSI6InJlY2VpdmVyIiwidmFsdWUiOiJpbmoxNHZubXcyd2VlM3h0cnNxZnZwY3FnMzVqZzl2N2oydmRwengwa2sifSx7ImtleSI6ImFtb3VudCIsInZhbHVlIjoiNTUwMDAwMDAwMDAwMDAwMDAwMDBpbmoifV19LHsidHlwZSI6InRyYW5zZmVyIiwiYXR0cmlidXRlcyI6W3sia2V5IjoicmVjaXBpZW50IiwidmFsdWUiOiJpbmoxNHZubXcyd2VlM3h0cnNxZnZwY3FnMzVqZzl2N2oydmRwengwa2sifSx7ImtleSI6InNlbmRlciIsInZhbHVlIjoiaW5qMWhraGRhajJhMmNsbXE1anE2bXNwc2dncXMzMnZ5bnBrMjI4cTNyIn0seyJrZXkiOiJhbW91bnQiLCJ2YWx1ZSI6IjU1MDAwMDAwMDAwMDAwMDAwMDAwaW5qIn1dfSx7InR5cGUiOiJtZXNzYWdlIiwiYXR0cmlidXRlcyI6W3sia2V5Ijoic2VuZGVyIiwidmFsdWUiOiJpbmoxaGtoZGFqMmEyY2xtcTVqcTZtc3BzZ2dxczMydnlucGsyMjhxM3IifV19XX1d"  # noqa: mock
            }
        }
        self.exchange._data_source._query_executor._transaction_by_hash_responses.put_nowait(transaction_response)

        original_order_hash_manager = self.exchange._data_source.order_hash_manager

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

        self.assertNotEqual(original_order_hash_manager, self.exchange._data_source._order_hash_manager)

    def test_order_creation_check_waits_for_originating_transaction_to_be_mined(self):
        request_sent_event = asyncio.Event()
        self.configure_all_symbols_response(mock_api=None)
        self.exchange._set_current_timestamp(1640780000)

        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "1",
            exchange_order_id="hash1",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("100"),
            order_type=OrderType.LIMIT,
        )

        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "2",
            exchange_order_id="hash2",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("20000"),
            amount=Decimal("200"),
            order_type=OrderType.LIMIT,
        )

        self.assertIn(self.client_order_id_prefix + "1", self.exchange.in_flight_orders)
        self.assertIn(self.client_order_id_prefix + "2", self.exchange.in_flight_orders)

        hash_not_matching_order: GatewayInFlightOrder = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]
        hash_not_matching_order.update_creation_transaction_hash(creation_transaction_hash="66A360DA2FD6884B53B5C019F1A2B5BED7C7C8FC07E83A9C36AD3362EDE096AE")  # noqa: mock

        no_mined_tx_order: GatewayInFlightOrder = self.exchange.in_flight_orders[self.client_order_id_prefix + "2"]
        no_mined_tx_order.update_creation_transaction_hash(
            creation_transaction_hash="HHHHHHHHHHHHHHH")

        transaction_data = (b'\x12\xd1\x01\n8/injective.exchange.v1beta1.MsgBatchUpdateOrdersResponse'
                            b'\x12\x94\x01\n\x02\x00\x00\x12\x02\x00\x00\x1aB'
                            b'0xc5d66f56942e1ae407c01eedccd0471deb8e202a514cde3bae56a8307e376cd1'  # noqa: mock
                            b'\x1aB'
                            b'0x115975551b4f86188eee6b93d789fcc78df6e89e40011b929299b6e142f53515'  # noqa: mock
                            b'"\x00"\x00')
        transaction_messages = [
            {
                "type": "/cosmos.authz.v1beta1.MsgExec",
                "value": {
                    "grantee": PrivateKey.from_hex(self.trading_account_private_key).to_public_key().to_acc_bech32(),
                    "msgs": [
                        {
                            "@type": "/injective.exchange.v1beta1.MsgBatchUpdateOrders",
                            "sender": self.portfolio_account_injective_address,
                            "subaccount_id": "",
                            "spot_market_ids_to_cancel_all": [],
                            "derivative_market_ids_to_cancel_all": [],
                            "spot_orders_to_cancel": [],
                            "derivative_orders_to_cancel": [],
                            "spot_orders_to_create": [
                                {
                                    "market_id": self.market_id,
                                    "order_info": {
                                        "subaccount_id": self.portfolio_account_subaccount_id,
                                        "fee_recipient": self.portfolio_account_injective_address,
                                        "price": str(
                                            hash_not_matching_order.price * Decimal(
                                                f"1e{self.quote_decimals - self.base_decimals}")),
                                        "quantity": str(
                                            hash_not_matching_order.amount * Decimal(f"1e{self.base_decimals}"))
                                    },
                                    "order_type": hash_not_matching_order.trade_type.name,
                                    "trigger_price": "0.000000000000000000"
                                }
                            ],
                            "derivative_orders_to_create": [],
                            "binary_options_orders_to_cancel": [],
                            "binary_options_market_ids_to_cancel_all": [],
                            "binary_options_orders_to_create": []
                        }
                    ]
                }
            }
        ]
        transaction_response = {
            "s": "ok",
            "data": {
                "blockNumber": "13302254",
                "blockTimestamp": "2023-07-05 13:55:09.94 +0000 UTC",
                "hash": "0x66a360da2fd6884b53b5c019f1a2b5bed7c7c8fc07e83a9c36ad3362ede096ae",  # noqa: mock
                "data": base64.b64encode(transaction_data).decode(),
                "gasWanted": "168306",
                "gasUsed": "167769",
                "gasFee": {
                    "amount": [
                        {
                            "denom": "inj",
                            "amount": "84153000000000"
                        }
                    ],
                    "gasLimit": "168306",
                    "payer": "inj1hkhdaj2a2clmq5jq6mspsggqs32vynpk228q3r"  # noqa: mock
                },
                "txType": "injective",
                "messages": base64.b64encode(json.dumps(transaction_messages).encode()).decode(),
                "signatures": [
                    {
                        "pubkey": "035ddc4d5642b9383e2f087b2ee88b7207f6286ebc9f310e9df1406eccc2c31813",  # noqa: mock
                        "address": "inj1hkhdaj2a2clmq5jq6mspsggqs32vynpk228q3r",  # noqa: mock
                        "sequence": "16450",
                        "signature": "S9atCwiVg9+8vTpbciuwErh54pJOAry3wHvbHT2fG8IumoE+7vfuoP7mAGDy2w9am+HHa1yv60VSWo3cRhWC9g=="
                    }
                ],
                "txNumber": "13182",
                "blockUnixTimestamp": "1688565309940",
                "logs": "W3sibXNnX2luZGV4IjowLCJldmVudHMiOlt7InR5cGUiOiJtZXNzYWdlIiwiYXR0cmlidXRlcyI6W3sia2V5IjoiYWN0aW9uIiwidmFsdWUiOiIvaW5qZWN0aXZlLmV4Y2hhbmdlLnYxYmV0YTEuTXNnQmF0Y2hVcGRhdGVPcmRlcnMifSx7ImtleSI6InNlbmRlciIsInZhbHVlIjoiaW5qMWhraGRhajJhMmNsbXE1anE2bXNwc2dncXMzMnZ5bnBrMjI4cTNyIn0seyJrZXkiOiJtb2R1bGUiLCJ2YWx1ZSI6ImV4Y2hhbmdlIn1dfSx7InR5cGUiOiJjb2luX3NwZW50IiwiYXR0cmlidXRlcyI6W3sia2V5Ijoic3BlbmRlciIsInZhbHVlIjoiaW5qMWhraGRhajJhMmNsbXE1anE2bXNwc2dncXMzMnZ5bnBrMjI4cTNyIn0seyJrZXkiOiJhbW91bnQiLCJ2YWx1ZSI6IjE2NTE2NTAwMHBlZ2d5MHg4N2FCM0I0Qzg2NjFlMDdENjM3MjM2MTIxMUI5NmVkNERjMzZCMUI1In1dfSx7InR5cGUiOiJjb2luX3JlY2VpdmVkIiwiYXR0cmlidXRlcyI6W3sia2V5IjoicmVjZWl2ZXIiLCJ2YWx1ZSI6ImluajE0dm5tdzJ3ZWUzeHRyc3FmdnBjcWczNWpnOXY3ajJ2ZHB6eDBrayJ9LHsia2V5IjoiYW1vdW50IiwidmFsdWUiOiIxNjUxNjUwMDBwZWdneTB4ODdhQjNCNEM4NjYxZTA3RDYzNzIzNjEyMTFCOTZlZDREYzM2QjFCNSJ9XX0seyJ0eXBlIjoidHJhbnNmZXIiLCJhdHRyaWJ1dGVzIjpbeyJrZXkiOiJyZWNpcGllbnQiLCJ2YWx1ZSI6ImluajE0dm5tdzJ3ZWUzeHRyc3FmdnBjcWczNWpnOXY3ajJ2ZHB6eDBrayJ9LHsia2V5Ijoic2VuZGVyIiwidmFsdWUiOiJpbmoxaGtoZGFqMmEyY2xtcTVqcTZtc3BzZ2dxczMydnlucGsyMjhxM3IifSx7ImtleSI6ImFtb3VudCIsInZhbHVlIjoiMTY1MTY1MDAwcGVnZ3kweDg3YUIzQjRDODY2MWUwN0Q2MzcyMzYxMjExQjk2ZWQ0RGMzNkIxQjUifV19LHsidHlwZSI6Im1lc3NhZ2UiLCJhdHRyaWJ1dGVzIjpbeyJrZXkiOiJzZW5kZXIiLCJ2YWx1ZSI6ImluajFoa2hkYWoyYTJjbG1xNWpxNm1zcHNnZ3FzMzJ2eW5wazIyOHEzciJ9XX0seyJ0eXBlIjoiY29pbl9zcGVudCIsImF0dHJpYnV0ZXMiOlt7ImtleSI6InNwZW5kZXIiLCJ2YWx1ZSI6ImluajFoa2hkYWoyYTJjbG1xNWpxNm1zcHNnZ3FzMzJ2eW5wazIyOHEzciJ9LHsia2V5IjoiYW1vdW50IiwidmFsdWUiOiI1NTAwMDAwMDAwMDAwMDAwMDAwMGluaiJ9XX0seyJ0eXBlIjoiY29pbl9yZWNlaXZlZCIsImF0dHJpYnV0ZXMiOlt7ImtleSI6InJlY2VpdmVyIiwidmFsdWUiOiJpbmoxNHZubXcyd2VlM3h0cnNxZnZwY3FnMzVqZzl2N2oydmRwengwa2sifSx7ImtleSI6ImFtb3VudCIsInZhbHVlIjoiNTUwMDAwMDAwMDAwMDAwMDAwMDBpbmoifV19LHsidHlwZSI6InRyYW5zZmVyIiwiYXR0cmlidXRlcyI6W3sia2V5IjoicmVjaXBpZW50IiwidmFsdWUiOiJpbmoxNHZubXcyd2VlM3h0cnNxZnZwY3FnMzVqZzl2N2oydmRwengwa2sifSx7ImtleSI6InNlbmRlciIsInZhbHVlIjoiaW5qMWhraGRhajJhMmNsbXE1anE2bXNwc2dncXMzMnZ5bnBrMjI4cTNyIn0seyJrZXkiOiJhbW91bnQiLCJ2YWx1ZSI6IjU1MDAwMDAwMDAwMDAwMDAwMDAwaW5qIn1dfSx7InR5cGUiOiJtZXNzYWdlIiwiYXR0cmlidXRlcyI6W3sia2V5Ijoic2VuZGVyIiwidmFsdWUiOiJpbmoxaGtoZGFqMmEyY2xtcTVqcTZtc3BzZ2dxczMydnlucGsyMjhxM3IifV19XX1d"  # noqa: mock
            }
        }
        mock_tx_by_hash_queue = AsyncMock()
        mock_tx_by_hash_queue.get.side_effect = [transaction_response, ValueError("Transaction not found in a block")]
        self.exchange._data_source._query_executor._transaction_by_hash_responses = mock_tx_by_hash_queue

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = partial(
            self._callback_wrapper_with_response,
            callback=lambda args, kwargs: request_sent_event.set(),
            response=13302254
        )
        self.exchange._data_source._query_executor._transaction_block_height_responses = mock_queue

        original_order_hash_manager = self.exchange._data_source.order_hash_manager

        self.async_tasks.append(
            asyncio.get_event_loop().create_task(
                self.exchange._check_orders_creation_transactions()
            )
        )

        self.async_run_with_timeout(request_sent_event.wait())

        self.assertNotEqual(original_order_hash_manager, self.exchange._data_source._order_hash_manager)

        mock_queue.get.assert_called()

    def test_order_creating_transactions_identify_correctly_market_orders(self):
        self.configure_all_symbols_response(mock_api=None)
        self.exchange._set_current_timestamp(1640780000)

        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "1",
            exchange_order_id=None,
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("100"),
            order_type=OrderType.LIMIT,
        )
        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "2",
            exchange_order_id=None,
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("4500"),
            amount=Decimal("20"),
            order_type=OrderType.MARKET,
        )

        self.assertIn(self.client_order_id_prefix + "1", self.exchange.in_flight_orders)
        self.assertIn(self.client_order_id_prefix + "2", self.exchange.in_flight_orders)
        limit_order: GatewayInFlightOrder = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]
        market_order: GatewayInFlightOrder = self.exchange.in_flight_orders[self.client_order_id_prefix + "2"]
        limit_order.update_creation_transaction_hash(creation_transaction_hash="66A360DA2FD6884B53B5C019F1A2B5BED7C7C8FC07E83A9C36AD3362EDE096AE")  # noqa: mock
        market_order.update_creation_transaction_hash(
            creation_transaction_hash="66A360DA2FD6884B53B5C019F1A2B5BED7C7C8FC07E83A9C36AD3362EDE096AE")  # noqa: mock

        expected_hash_1 = "0xc5d66f56942e1ae407c01eedccd0471deb8e202a514cde3bae56a8307e376cd1"  # noqa: mock
        expected_hash_2 = "0x115975551b4f86188eee6b93d789fcc78df6e89e40011b929299b6e142f53515"  # noqa: mock

        transaction_data = ('\x12\xd1\x01\n8/injective.exchange.v1beta1.MsgBatchUpdateOrdersResponse'
                            '\x12\x94\x01\n\x02\x00\x00\x12\x02\x00\x00\x1aB'
                            f'{expected_hash_1}'
                            '\x1aB'
                            f'{expected_hash_2}'
                            f'"\x00"\x00').encode()
        transaction_messages = [
            {
                "type": "/cosmos.authz.v1beta1.MsgExec",
                "value": {
                    "grantee": PrivateKey.from_hex(self.trading_account_private_key).to_public_key().to_acc_bech32(),
                    "msgs": [
                        {
                            "@type": "/injective.exchange.v1beta1.MsgCreateSpotMarketOrder",
                            "sender": self.portfolio_account_injective_address,
                            "order": {
                                "market_id": self.market_id,
                                "order_info": {
                                    "subaccount_id": self.portfolio_account_subaccount_id,
                                    "fee_recipient": self.portfolio_account_injective_address,
                                    "price": str(
                                        market_order.price * Decimal(f"1e{self.quote_decimals - self.base_decimals}")),
                                    "quantity": str(market_order.amount * Decimal(f"1e{self.base_decimals}"))
                                },
                                "order_type": "BUY",
                                "trigger_price": "0.000000000000000000"
                            }
                        },
                        {
                            "@type": "/injective.exchange.v1beta1.MsgBatchUpdateOrders",
                            "sender": self.portfolio_account_injective_address,
                            "subaccount_id": "",
                            "spot_market_ids_to_cancel_all": [],
                            "derivative_market_ids_to_cancel_all": [],
                            "spot_orders_to_cancel": [],
                            "derivative_orders_to_cancel": [],
                            "spot_orders_to_create": [
                                {
                                    "market_id": self.market_id,
                                    "order_info": {
                                        "subaccount_id": self.portfolio_account_subaccount_id,
                                        "fee_recipient": self.portfolio_account_injective_address,
                                        "price": str(limit_order.price * Decimal(f"1e{self.quote_decimals - self.base_decimals}")),
                                        "quantity": str(limit_order.amount * Decimal(f"1e{self.base_decimals}"))
                                    },
                                    "order_type": limit_order.trade_type.name,
                                    "trigger_price": "0.000000000000000000"
                                }
                            ],
                            "derivative_orders_to_create": [],
                            "binary_options_orders_to_cancel": [],
                            "binary_options_market_ids_to_cancel_all": [],
                            "binary_options_orders_to_create": []
                        }
                    ]
                }
            }
        ]
        transaction_response = {
            "s": "ok",
            "data": {
                "blockNumber": "13302254",
                "blockTimestamp": "2023-07-05 13:55:09.94 +0000 UTC",
                "hash": "0x66a360da2fd6884b53b5c019f1a2b5bed7c7c8fc07e83a9c36ad3362ede096ae",  # noqa: mock
                "data": base64.b64encode(transaction_data).decode(),
                "gasWanted": "168306",
                "gasUsed": "167769",
                "gasFee": {
                    "amount": [
                        {
                            "denom": "inj",
                            "amount": "84153000000000"
                        }
                    ],
                    "gasLimit": "168306",
                    "payer": "inj1hkhdaj2a2clmq5jq6mspsggqs32vynpk228q3r"  # noqa: mock
                },
                "txType": "injective",
                "messages": base64.b64encode(json.dumps(transaction_messages).encode()).decode(),
                "signatures": [
                    {
                        "pubkey": "035ddc4d5642b9383e2f087b2ee88b7207f6286ebc9f310e9df1406eccc2c31813",  # noqa: mock
                        "address": "inj1hkhdaj2a2clmq5jq6mspsggqs32vynpk228q3r",  # noqa: mock
                        "sequence": "16450",
                        "signature": "S9atCwiVg9+8vTpbciuwErh54pJOAry3wHvbHT2fG8IumoE+7vfuoP7mAGDy2w9am+HHa1yv60VSWo3cRhWC9g=="
                    }
                ],
                "txNumber": "13182",
                "blockUnixTimestamp": "1688565309940",
                "logs": "W3sibXNnX2luZGV4IjowLCJldmVudHMiOlt7InR5cGUiOiJtZXNzYWdlIiwiYXR0cmlidXRlcyI6W3sia2V5IjoiYWN0aW9uIiwidmFsdWUiOiIvaW5qZWN0aXZlLmV4Y2hhbmdlLnYxYmV0YTEuTXNnQmF0Y2hVcGRhdGVPcmRlcnMifSx7ImtleSI6InNlbmRlciIsInZhbHVlIjoiaW5qMWhraGRhajJhMmNsbXE1anE2bXNwc2dncXMzMnZ5bnBrMjI4cTNyIn0seyJrZXkiOiJtb2R1bGUiLCJ2YWx1ZSI6ImV4Y2hhbmdlIn1dfSx7InR5cGUiOiJjb2luX3NwZW50IiwiYXR0cmlidXRlcyI6W3sia2V5Ijoic3BlbmRlciIsInZhbHVlIjoiaW5qMWhraGRhajJhMmNsbXE1anE2bXNwc2dncXMzMnZ5bnBrMjI4cTNyIn0seyJrZXkiOiJhbW91bnQiLCJ2YWx1ZSI6IjE2NTE2NTAwMHBlZ2d5MHg4N2FCM0I0Qzg2NjFlMDdENjM3MjM2MTIxMUI5NmVkNERjMzZCMUI1In1dfSx7InR5cGUiOiJjb2luX3JlY2VpdmVkIiwiYXR0cmlidXRlcyI6W3sia2V5IjoicmVjZWl2ZXIiLCJ2YWx1ZSI6ImluajE0dm5tdzJ3ZWUzeHRyc3FmdnBjcWczNWpnOXY3ajJ2ZHB6eDBrayJ9LHsia2V5IjoiYW1vdW50IiwidmFsdWUiOiIxNjUxNjUwMDBwZWdneTB4ODdhQjNCNEM4NjYxZTA3RDYzNzIzNjEyMTFCOTZlZDREYzM2QjFCNSJ9XX0seyJ0eXBlIjoidHJhbnNmZXIiLCJhdHRyaWJ1dGVzIjpbeyJrZXkiOiJyZWNpcGllbnQiLCJ2YWx1ZSI6ImluajE0dm5tdzJ3ZWUzeHRyc3FmdnBjcWczNWpnOXY3ajJ2ZHB6eDBrayJ9LHsia2V5Ijoic2VuZGVyIiwidmFsdWUiOiJpbmoxaGtoZGFqMmEyY2xtcTVqcTZtc3BzZ2dxczMydnlucGsyMjhxM3IifSx7ImtleSI6ImFtb3VudCIsInZhbHVlIjoiMTY1MTY1MDAwcGVnZ3kweDg3YUIzQjRDODY2MWUwN0Q2MzcyMzYxMjExQjk2ZWQ0RGMzNkIxQjUifV19LHsidHlwZSI6Im1lc3NhZ2UiLCJhdHRyaWJ1dGVzIjpbeyJrZXkiOiJzZW5kZXIiLCJ2YWx1ZSI6ImluajFoa2hkYWoyYTJjbG1xNWpxNm1zcHNnZ3FzMzJ2eW5wazIyOHEzciJ9XX0seyJ0eXBlIjoiY29pbl9zcGVudCIsImF0dHJpYnV0ZXMiOlt7ImtleSI6InNwZW5kZXIiLCJ2YWx1ZSI6ImluajFoa2hkYWoyYTJjbG1xNWpxNm1zcHNnZ3FzMzJ2eW5wazIyOHEzciJ9LHsia2V5IjoiYW1vdW50IiwidmFsdWUiOiI1NTAwMDAwMDAwMDAwMDAwMDAwMGluaiJ9XX0seyJ0eXBlIjoiY29pbl9yZWNlaXZlZCIsImF0dHJpYnV0ZXMiOlt7ImtleSI6InJlY2VpdmVyIiwidmFsdWUiOiJpbmoxNHZubXcyd2VlM3h0cnNxZnZwY3FnMzVqZzl2N2oydmRwengwa2sifSx7ImtleSI6ImFtb3VudCIsInZhbHVlIjoiNTUwMDAwMDAwMDAwMDAwMDAwMDBpbmoifV19LHsidHlwZSI6InRyYW5zZmVyIiwiYXR0cmlidXRlcyI6W3sia2V5IjoicmVjaXBpZW50IiwidmFsdWUiOiJpbmoxNHZubXcyd2VlM3h0cnNxZnZwY3FnMzVqZzl2N2oydmRwengwa2sifSx7ImtleSI6InNlbmRlciIsInZhbHVlIjoiaW5qMWhraGRhajJhMmNsbXE1anE2bXNwc2dncXMzMnZ5bnBrMjI4cTNyIn0seyJrZXkiOiJhbW91bnQiLCJ2YWx1ZSI6IjU1MDAwMDAwMDAwMDAwMDAwMDAwaW5qIn1dfSx7InR5cGUiOiJtZXNzYWdlIiwiYXR0cmlidXRlcyI6W3sia2V5Ijoic2VuZGVyIiwidmFsdWUiOiJpbmoxaGtoZGFqMmEyY2xtcTVqcTZtc3BzZ2dxczMydnlucGsyMjhxM3IifV19XX1d"  # noqa: mock
            }
        }
        self.exchange._data_source._query_executor._transaction_by_hash_responses.put_nowait(transaction_response)

        self.async_run_with_timeout(self.exchange._check_orders_creation_transactions())

        self.assertEquals(2, len(self.buy_order_created_logger.event_log))
        self.assertEquals(0, len(self.order_failure_logger.event_log))

        self.assertEquals(expected_hash_1, market_order.exchange_order_id)
        self.assertEquals(expected_hash_2, limit_order.exchange_order_id)

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
        )

        exchange_with_non_default_subaccount = InjectiveV2Exchange(
            client_config_map=client_config_map,
            connector_configuration=injective_config,
            trading_pairs=[self.trading_pair],
        )

        exchange_with_non_default_subaccount._data_source._query_executor = self.exchange._data_source._query_executor
        self.exchange = exchange_with_non_default_subaccount
        self.configure_all_symbols_response(mock_api=None)
        self.exchange._set_current_timestamp(1640780000)

        balance_event = self.balance_event_websocket_update

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [balance_event, asyncio.CancelledError]
        self.exchange._data_source._query_executor._subaccount_balance_events = mock_queue

        self.async_tasks.append(
            asyncio.get_event_loop().create_task(
                self.exchange._user_stream_event_listener()
            )
        )

        try:
            self.async_run_with_timeout(self.exchange._data_source._listen_to_account_balance_updates())
        except asyncio.CancelledError:
            pass

        self.assertEqual(Decimal("10"), self.exchange.available_balances[self.base_asset])
        self.assertEqual(Decimal("15"), self.exchange.get_balance(self.base_asset))

    def test_user_stream_update_for_new_order(self):
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
        self.exchange._data_source._query_executor._historical_spot_order_events = mock_queue

        self.async_tasks.append(
            asyncio.get_event_loop().create_task(
                self.exchange._user_stream_event_listener()
            )
        )

        try:
            self.async_run_with_timeout(
                self.exchange._data_source._listen_to_subaccount_spot_order_updates(market_id=self.market_id)
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
        self.exchange._data_source._query_executor._historical_spot_order_events = mock_queue

        self.async_tasks.append(
            asyncio.get_event_loop().create_task(
                self.exchange._user_stream_event_listener()
            )
        )

        try:
            self.async_run_with_timeout(
                self.exchange._data_source._listen_to_subaccount_spot_order_updates(market_id=self.market_id)
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

        orders_queue_mock = AsyncMock()
        trades_queue_mock = AsyncMock()
        orders_messages = []
        trades_messages = []
        if trade_event:
            trades_messages.append(trade_event)
        if order_event:
            orders_messages.append(order_event)
        orders_messages.append(asyncio.CancelledError)
        trades_messages.append(asyncio.CancelledError)

        orders_queue_mock.get.side_effect = orders_messages
        trades_queue_mock.get.side_effect = trades_messages
        self.exchange._data_source._query_executor._historical_spot_order_events = orders_queue_mock
        self.exchange._data_source._query_executor._public_spot_trade_updates = trades_queue_mock

        self.async_tasks.append(
            asyncio.get_event_loop().create_task(
                self.exchange._user_stream_event_listener()
            )
        )

        tasks = [
            asyncio.get_event_loop().create_task(
                self.exchange._data_source._listen_to_public_spot_trades(market_ids=[self.market_id])
            ),
            asyncio.get_event_loop().create_task(
                self.exchange._data_source._listen_to_subaccount_spot_order_updates(market_id=self.market_id)
            )
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
        self.exchange._data_source._query_executor._historical_spot_order_events = mock_queue

        self.async_tasks.append(
            asyncio.get_event_loop().create_task(
                self.exchange._user_stream_event_listener()
            )
        )

        try:
            self.async_run_with_timeout(
                self.exchange._data_source._listen_to_subaccount_spot_order_updates(market_id=self.market_id)
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

        orders_queue_mock = AsyncMock()
        trades_queue_mock = AsyncMock()
        orders_messages = []
        trades_messages = []
        if trade_event:
            trades_messages.append(trade_event)
        if order_event:
            orders_messages.append(order_event)
        orders_messages.append(asyncio.CancelledError)
        trades_messages.append(asyncio.CancelledError)

        orders_queue_mock.get.side_effect = orders_messages
        trades_queue_mock.get.side_effect = trades_messages
        self.exchange._data_source._query_executor._historical_spot_order_events = orders_queue_mock
        self.exchange._data_source._query_executor._public_spot_trade_updates = trades_queue_mock

        self.async_tasks.append(
            asyncio.get_event_loop().create_task(
                self.exchange._user_stream_event_listener()
            )
        )

        tasks = [
            asyncio.get_event_loop().create_task(
                self.exchange._data_source._listen_to_public_spot_trades(market_ids=[self.market_id])
            ),
            asyncio.get_event_loop().create_task(
                self.exchange._data_source._listen_to_subaccount_spot_order_updates(market_id=self.market_id)
            )
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

        maker_fee_rate = Decimal(self.all_markets_mock_response[0]["makerFeeRate"])
        taker_fee_rate = Decimal(self.all_markets_mock_response[0]["takerFeeRate"])

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
        self.exchange._data_source._query_executor._derivative_markets_responses.put_nowait([])
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
        return {"txhash": "79DBF373DE9C534EE2DC9D009F32B850DA8D0C73833FAA0FD52C6AE8989EC659", "rawLog": "[]"}  # noqa: mock

    def _order_cancelation_request_erroneous_mock_response(self, order: InFlightOrder) -> Dict[str, Any]:
        return {"txhash": "79DBF373DE9C534EE2DC9D009F32B850DA8D0C73833FAA0FD52C6AE8989EC659", "rawLog": "Error"}  # noqa: mock

    def _order_status_request_open_mock_response(self, order: GatewayInFlightOrder) -> Dict[str, Any]:
        return {
            "orders": [
                {
                    "orderHash": order.exchange_order_id,
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
                    "subaccountId": self.portfolio_account_subaccount_id,
                    "marketId": self.market_id,
                    "tradeExecutionType": "limitFill",
                    "tradeDirection": order.trade_type.name.lower(),
                    "price": {
                        "price": str(self.expected_partial_fill_price * Decimal(f"1e{self.quote_decimals - self.base_decimals}")),
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
