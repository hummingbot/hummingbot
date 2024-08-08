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
from pyinjective import Address, PrivateKey
from pyinjective.composer import Composer
from pyinjective.core.market import DerivativeMarket, SpotMarket
from pyinjective.core.token import Token

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.derivative.injective_v2_perpetual.injective_v2_perpetual_derivative import (
    InjectiveV2PerpetualDerivative,
)
from hummingbot.connector.exchange.injective_v2.injective_v2_utils import (
    InjectiveConfigMap,
    InjectiveDelegatedAccountMode,
    InjectiveMessageBasedTransactionFeeCalculatorMode,
    InjectiveTestnetNetworkMode,
)
from hummingbot.connector.gateway.gateway_in_flight_order import GatewayPerpetualInFlightOrder
from hummingbot.connector.test_support.perpetual_derivative_test import AbstractPerpetualDerivativeTests
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.funding_info import FundingInfo, FundingInfoUpdate
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.market_order import MarketOrder
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_row import OrderBookRow
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    FundingPaymentCompletedEvent,
    MarketOrderFailureEvent,
    OrderCancelledEvent,
    OrderFilledEvent,
)
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import safe_gather


class InjectiveV2PerpetualDerivativeTests(AbstractPerpetualDerivativeTests.PerpetualDerivativeTests):

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "INJ"
        cls.quote_asset = "USDT"
        cls.base_asset_denom = "inj"
        cls.quote_asset_denom = "peggy0x87aB3B4C8661e07D6372361211B96ed4Dc36B1B5"  # noqa: mock
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.market_id = "0x17ef48032cb24375ba7c2e39f384e56433bcab20cbee9a7357e4cba2eb00abe6"  # noqa: mock

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
    def expected_supported_position_modes(self) -> List[PositionMode]:
        return [PositionMode.ONEWAY]

    @property
    def funding_info_url(self):
        raise NotImplementedError

    @property
    def funding_payment_url(self):
        raise NotImplementedError

    @property
    def funding_info_mock_response(self):
        raise NotImplementedError

    @property
    def empty_funding_payment_mock_response(self):
        raise NotImplementedError

    @property
    def funding_payment_mock_response(self):
        raise NotImplementedError

    def position_event_for_full_fill_websocket_update(self, order: InFlightOrder, unrealized_pnl: float):
        raise NotImplementedError

    def configure_successful_set_position_mode(
            self,
            position_mode: PositionMode,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None):
        raise NotImplementedError

    def configure_failed_set_position_mode(
            self,
            position_mode: PositionMode,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> Tuple[str, str]:
        # Do nothing
        return "", ""

    def configure_failed_set_leverage(
            self,
            leverage: int,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> Tuple[str, str]:
        raise NotImplementedError

    def configure_successful_set_leverage(
            self,
            leverage: int,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ):
        raise NotImplementedError

    def funding_info_event_for_websocket_update(self):
        raise NotImplementedError

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
                    "positionDelta": {
                        "tradeDirection": "sell",
                        "executionPrice": str(
                            Decimal(str(self.expected_latest_price)) * Decimal(f"1e{self.quote_decimals}")),
                        "executionQuantity": "142000000000000000000",
                        "executionMargin": "1245280000"
                    },
                    "payout": "1187984833.579447998034818126",
                    "fee": "-112393",
                    "executedAt": "1688734042063",
                    "feeRecipient": "inj15uad884tqeq9r76x3fvktmjge2r6kek55c2zpa",  # noqa: mock
                    "tradeId": "13374245_801_0",
                    "executionSide": "maker"
                },
            ],
            "paging": {
                "total": "1",
                "from": 1,
                "to": 1
            }
        }

    @property
    def all_symbols_including_invalid_pair_mock_response(self) -> Tuple[str, Any]:
        response = self.all_derivative_markets_mock_response
        response["invalid_market_id"] = DerivativeMarket(
            id="invalid_market_id",
            status="active",
            ticker="INVALID/MARKET",
            oracle_base="",
            oracle_quote="",
            oracle_type="pyth",
            oracle_scale_factor=6,
            initial_margin_ratio=Decimal("0.195"),
            maintenance_margin_ratio=Decimal("0.05"),
            quote_token=None,
            maker_fee_rate=Decimal("-0.0003"),
            taker_fee_rate=Decimal("0.003"),
            service_provider_fee=Decimal("0.4"),
            min_price_tick_size=Decimal("100"),
            min_quantity_tick_size=Decimal("0.0001"),
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
        quote_native_token = Token(
            name="Base Asset",
            symbol=self.quote_asset,
            denom=self.quote_asset_denom,
            address="0x0000000000000000000000000000000000000000",  # noqa: mock
            decimals=self.quote_decimals,
            logo="https://static.alchemyapi.io/images/assets/825.png",
            updated=1687190809716,
        )

        native_market = DerivativeMarket(
            id=self.market_id,
            status="active",
            ticker=f"{self.base_asset}/{self.quote_asset} PERP",
            oracle_base="0x2d9315a88f3019f8efa88dfe9c0f0843712da0bac814461e27733f6b83eb51b3",  # noqa: mock
            oracle_quote="0x1fc18861232290221461220bd4e2acd1dcdfbc89c84092c93c18bdc7756c1588",  # noqa: mock
            oracle_type="pyth",
            oracle_scale_factor=6,
            initial_margin_ratio=Decimal("0.195"),
            maintenance_margin_ratio=Decimal("0.05"),
            quote_token=quote_native_token,
            maker_fee_rate=Decimal("-0.0003"),
            taker_fee_rate=Decimal("0.003"),
            service_provider_fee=Decimal("0.4"),
            min_price_tick_size=None,
            min_quantity_tick_size=None,
            min_notional=None,
        )

        return {native_market.id: native_market}

    @property
    def order_creation_request_successful_mock_response(self):
        return {"txhash": "017C130E3602A48E5C9D661CAC657BF1B79262D4B71D5C25B1DA62DE2338DA0E",  # noqa: mock
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
    def expected_supported_order_types(self):
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    @property
    def expected_trading_rule(self):
        market = list(self.all_derivative_markets_mock_response.values())[0]
        min_price_tick_size = (market.min_price_tick_size
                               * Decimal(f"1e{-market.quote_token.decimals}"))
        min_quantity_tick_size = market.min_quantity_tick_size
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
    def all_spot_markets_mock_response(self) -> Dict[str, SpotMarket]:
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
            min_price_tick_size=Decimal("0.000000000000001"),
            min_quantity_tick_size=Decimal("1000000000000000"),
            min_notional=Decimal("1000000"),
        )

        return {native_market.id: native_market}

    @property
    def all_derivative_markets_mock_response(self) -> Dict[str, DerivativeMarket]:
        quote_native_token = Token(
            name="Base Asset",
            symbol=self.quote_asset,
            denom=self.quote_asset_denom,
            address="0x0000000000000000000000000000000000000000",  # noqa: mock
            decimals=self.quote_decimals,
            logo="https://static.alchemyapi.io/images/assets/825.png",
            updated=1687190809716,
        )

        native_market = DerivativeMarket(
            id=self.market_id,
            status="active",
            ticker=f"{self.base_asset}/{self.quote_asset} PERP",
            oracle_base="0x2d9315a88f3019f8efa88dfe9c0f0843712da0bac814461e27733f6b83eb51b3",  # noqa: mock
            oracle_quote="0x1fc18861232290221461220bd4e2acd1dcdfbc89c84092c93c18bdc7756c1588",  # noqa: mock
            oracle_type="pyth",
            oracle_scale_factor=6,
            initial_margin_ratio=Decimal("0.195"),
            maintenance_margin_ratio=Decimal("0.05"),
            quote_token=quote_native_token,
            maker_fee_rate=Decimal("-0.0003"),
            taker_fee_rate=Decimal("0.003"),
            service_provider_fee=Decimal("0.4"),
            min_price_tick_size=Decimal("100"),
            min_quantity_tick_size=Decimal("0.0001"),
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

        exchange = InjectiveV2PerpetualDerivative(
            client_config_map=client_config_map,
            connector_configuration=injective_config,
            trading_pairs=[self.trading_pair],
        )

        exchange._data_source._query_executor = ProgrammableQueryExecutor()
        exchange._data_source._spot_market_and_trading_pair_map = bidict()
        exchange._data_source._derivative_market_and_trading_pair_map = bidict({self.market_id: self.trading_pair})

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
        all_markets_mock_response = self.all_spot_markets_mock_response
        self.exchange._data_source._query_executor._spot_markets_responses.put_nowait(all_markets_mock_response)
        market = list(all_markets_mock_response.values())[0]
        self.exchange._data_source._query_executor._tokens_responses.put_nowait(
            {token.symbol: token for token in [market.base_token, market.quote_token]}
        )
        all_markets_mock_response = self.all_derivative_markets_mock_response
        self.exchange._data_source._query_executor._derivative_markets_responses.put_nowait(all_markets_mock_response)
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

        self.exchange._data_source._query_executor._spot_markets_responses.put_nowait({})
        response = self.trading_rules_request_erroneous_mock_response
        self.exchange._data_source._query_executor._derivative_markets_responses.put_nowait(response)
        market = list(response.values())[0]
        self.exchange._data_source._query_executor._tokens_responses.put_nowait(
            {token.symbol: token for token in [market.quote_token]}
        )
        return ""

    def configure_successful_cancelation_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        transaction_simulation_response = self._msg_exec_simulation_mock_response()
        self.exchange._data_source._query_executor._simulate_transaction_responses.put_nowait(
            transaction_simulation_response)
        response = self._order_cancelation_request_successful_mock_response(order=order)
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = partial(self._callback_wrapper_with_response, callback=callback, response=response)
        self.exchange._data_source._query_executor._send_transaction_responses = mock_queue
        return ""

    def configure_erroneous_cancelation_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
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
            callback: Optional[Callable] = lambda *args, **kwargs: None
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
        self.exchange._data_source._query_executor._historical_derivative_orders_responses = mock_queue
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
        self.exchange._data_source._query_executor._derivative_trades_responses.put_nowait(
            {"trades": [], "paging": {"total": "0"}})

        response = self._order_status_request_canceled_mock_response(order=order)
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = partial(self._callback_wrapper_with_response, callback=callback, response=response)
        self.exchange._data_source._query_executor._historical_derivative_orders_responses = mock_queue
        return []

    def configure_open_order_status_response(self, order: InFlightOrder, mock_api: aioresponses,
                                             callback: Optional[Callable] = lambda *args, **kwargs: None) -> List[str]:
        self.configure_all_symbols_response(mock_api=mock_api)

        self.exchange._data_source._query_executor._derivative_trades_responses.put_nowait(
            {"trades": [], "paging": {"total": "0"}})

        response = self._order_status_request_open_mock_response(order=order)
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = partial(self._callback_wrapper_with_response, callback=callback, response=response)
        self.exchange._data_source._query_executor._historical_derivative_orders_responses = mock_queue
        return []

    def configure_http_error_order_status_response(self, order: InFlightOrder, mock_api: aioresponses,
                                                   callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        self.configure_all_symbols_response(mock_api=mock_api)

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = IOError("Test error for trades responses")
        self.exchange._data_source._query_executor._derivative_trades_responses = mock_queue

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = IOError("Test error for historical orders responses")
        self.exchange._data_source._query_executor._historical_derivative_orders_responses = mock_queue
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
        self.exchange._data_source._query_executor._historical_derivative_orders_responses = mock_queue
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
        self.exchange._data_source._query_executor._historical_derivative_orders_responses = mock_queue
        return []

    def configure_partial_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        response = self._order_fills_request_partial_fill_mock_response(order=order)
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = partial(self._callback_wrapper_with_response, callback=callback, response=response)
        self.exchange._data_source._query_executor._derivative_trades_responses = mock_queue
        return None

    def configure_erroneous_http_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = IOError("Test error for trades responses")
        self.exchange._data_source._query_executor._derivative_trades_responses = mock_queue
        return None

    def configure_full_fill_trade_response(self, order: InFlightOrder, mock_api: aioresponses,
                                           callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        response = self._order_fills_request_full_fill_mock_response(order=order)
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = partial(self._callback_wrapper_with_response, callback=callback, response=response)
        self.exchange._data_source._query_executor._derivative_trades_responses = mock_queue
        return None

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
            "spotOrders": [],
            "derivativeOrders": [
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
                                    int(order.price * Decimal(f"1e{self.quote_decimals + 18}"))),
                                "quantity": str(int(order.amount * Decimal("1e18"))),
                                "cid": order.client_order_id,
                            },
                            "orderType": order.trade_type.name.lower(),
                            "fillable": str(int(order.amount * Decimal("1e18"))),
                            "orderHash": base64.b64encode(
                                bytes.fromhex(order.exchange_order_id.replace("0x", ""))).decode(),
                            "triggerPrice": "",
                        }
                    },
                },
            ],
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
            "spotOrders": [],
            "derivativeOrders": [
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
                                    int(order.price * Decimal(f"1e{self.quote_decimals + 18}"))),
                                "quantity": str(int(order.amount * Decimal("1e18"))),
                                "cid": order.client_order_id,
                            },
                            "orderType": order.trade_type.name.lower(),
                            "fillable": str(int(order.amount * Decimal("1e18"))),
                            "orderHash": base64.b64encode(
                                bytes.fromhex(order.exchange_order_id.replace("0x", ""))).decode(),
                            "triggerPrice": "",
                        }
                    },
                },
            ],
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
            "spotOrders": [],
            "derivativeOrders": [
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
                                    int(order.price * Decimal(f"1e{self.quote_decimals + 18}"))),
                                "quantity": str(int(order.amount * Decimal("1e18"))),
                                "cid": order.client_order_id,
                            },
                            "orderType": order.trade_type.name.lower(),
                            "fillable": str(int(order.amount * Decimal("1e18"))),
                            "orderHash": base64.b64encode(
                                bytes.fromhex(order.exchange_order_id.replace("0x", ""))).decode(),
                            "triggerPrice": "",
                        }
                    },
                },
            ],
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
            "spotTrades": [],
            "derivativeTrades": [
                {
                    "marketId": self.market_id,
                    "isBuy": order.trade_type == TradeType.BUY,
                    "executionType": "LimitMatchRestingOrder",
                    "subaccountId": self.portfolio_account_subaccount_id,
                    "positionDelta": {
                        "isLong": True,
                        "executionQuantity": str(int(order.amount * Decimal("1e18"))),
                        "executionMargin": "186681600000000000000000000",
                        "executionPrice": str(int(order.price * Decimal(f"1e{self.quote_decimals + 18}"))),
                    },
                    "payout": "207636617326923969135747808",
                    "fee": str(self.expected_fill_fee.flat_fees[0].amount * Decimal(f"1e{self.quote_decimals + 18}")),
                    "orderHash": base64.b64encode(bytes.fromhex(order.exchange_order_id.replace("0x", ""))).decode(),
                    "feeRecipientAddress": self.portfolio_account_injective_address,
                    "cid": order.client_order_id,
                    "tradeId": self.expected_fill_trade_id,
                },
            ],
            "spotOrders": [],
            "derivativeOrders": [],
            "positions": [],
            "oraclePrices": [],
        }

    @aioresponses()
    def test_all_trading_pairs_does_not_raise_exception(self, mock_api):
        self.exchange._set_trading_pair_symbol_map(None)
        self.exchange._data_source._spot_market_and_trading_pair_map = None
        self.exchange._data_source._derivative_market_and_trading_pair_map = None
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

        buy_order_to_create_in_flight = GatewayPerpetualInFlightOrder(
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
        sell_order_to_create_in_flight = GatewayPerpetualInFlightOrder(
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
            position=PositionAction.OPEN,
        )
        sell_order_to_create = MarketOrder(
            order_id="",
            trading_pair=self.trading_pair,
            is_buy=False,
            base_asset=self.base_asset,
            quote_asset=self.quote_asset,
            amount=3,
            timestamp=self.exchange.current_timestamp,
            position=PositionAction.CLOSE,
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

        buy_order_to_create_in_flight = GatewayPerpetualInFlightOrder(
            client_order_id=orders[0].client_order_id,
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            creation_timestamp=1640780000,
            price=orders[0].price,
            amount=orders[0].quantity,
            exchange_order_id="hash1",
            creation_transaction_hash=response["txhash"],
            position=PositionAction.OPEN
        )
        sell_order_to_create_in_flight = GatewayPerpetualInFlightOrder(
            client_order_id=orders[1].order_id,
            trading_pair=self.trading_pair,
            order_type=OrderType.MARKET,
            trade_type=TradeType.SELL,
            creation_timestamp=1640780000,
            price=expected_price_for_volume,
            amount=orders[1].quantity,
            exchange_order_id="hash2",
            creation_transaction_hash=response["txhash"],
            position=PositionAction.CLOSE
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
        """Open long position"""
        # Configure all symbols response to initialize the trading rules
        self.configure_all_symbols_response(mock_api=None)
        self.async_run_with_timeout(self.exchange._update_trading_rules())
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

        leverage = 2
        self.exchange._perpetual_trading.set_leverage(self.trading_pair, leverage)
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

    @aioresponses()
    def test_create_order_to_close_short_position(self, mock_api):
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

        leverage = 4
        self.exchange._perpetual_trading.set_leverage(self.trading_pair, leverage)
        order_id = self.place_buy_order(position_action=PositionAction.CLOSE)
        self.async_run_with_timeout(request_sent_event.wait())

        order = self.exchange.in_flight_orders[order_id]

        self.assertEqual(response["txhash"], order.creation_transaction_hash)

    @aioresponses()
    def test_create_order_to_close_long_position(self, mock_api):
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

        leverage = 5
        self.exchange._perpetual_trading.set_leverage(self.trading_pair, leverage)
        order_id = self.place_sell_order(position_action=PositionAction.CLOSE)
        self.async_run_with_timeout(request_sent_event.wait())

        order = self.exchange.in_flight_orders[order_id]

        self.assertEqual(response["txhash"], order.creation_transaction_hash)

    def test_get_buy_and_sell_collateral_tokens(self):
        self._simulate_trading_rules_initialized()

        linear_buy_collateral_token = self.exchange.get_buy_collateral_token(self.trading_pair)
        linear_sell_collateral_token = self.exchange.get_sell_collateral_token(self.trading_pair)

        self.assertEqual(self.quote_asset, linear_buy_collateral_token)
        self.assertEqual(self.quote_asset, linear_sell_collateral_token)

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

        buy_order_to_cancel: GatewayPerpetualInFlightOrder = self.exchange.in_flight_orders["11"]
        sell_order_to_cancel: GatewayPerpetualInFlightOrder = self.exchange.in_flight_orders["12"]
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

    @aioresponses()
    def test_update_order_status_when_order_has_not_changed_and_one_partial_fill(self, mock_api):
        self.exchange._set_current_timestamp(1640780000)

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

        self.configure_partially_filled_order_status_response(
            order=order,
            mock_api=mock_api)

        if self.is_order_fill_http_update_included_in_status_update:
            self.configure_partial_fill_trade_response(
                order=order,
                mock_api=mock_api)

        self.assertTrue(order.is_open)

        self.async_run_with_timeout(self.exchange._update_order_status())

        self.assertTrue(order.is_open)
        self.assertEqual(OrderState.PARTIALLY_FILLED, order.current_state)

        if self.is_order_fill_http_update_included_in_status_update:
            fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
            self.assertEqual(self.exchange.current_timestamp, fill_event.timestamp)
            self.assertEqual(order.client_order_id, fill_event.order_id)
            self.assertEqual(order.trading_pair, fill_event.trading_pair)
            self.assertEqual(order.trade_type, fill_event.trade_type)
            self.assertEqual(order.order_type, fill_event.order_type)
            self.assertEqual(self.expected_partial_fill_price, fill_event.price)
            self.assertEqual(self.expected_partial_fill_amount, fill_event.amount)
            self.assertEqual(self.expected_fill_fee, fill_event.trade_fee)

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

        exchange_with_non_default_subaccount = InjectiveV2PerpetualDerivative(
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
            self.exchange._data_source.derivative_market_info_for_id(market_id=self.market_id)
        )
        try:
            self.async_run_with_timeout(
                self.exchange._data_source._listen_to_chain_updates(
                    spot_markets=[],
                    derivative_markets=[market],
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
            self.exchange._data_source.derivative_market_info_for_id(market_id=self.market_id)
        )
        try:
            self.async_run_with_timeout(
                self.exchange._data_source._listen_to_chain_updates(
                    spot_markets=[],
                    derivative_markets=[market],
                    subaccount_ids=[self.portfolio_account_subaccount_id]
                )
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
            self.exchange._data_source.derivative_market_info_for_id(market_id=self.market_id)
        )
        try:
            self.async_run_with_timeout(
                self.exchange._data_source._listen_to_chain_updates(
                    spot_markets=[],
                    derivative_markets=[market],
                    subaccount_ids=[self.portfolio_account_subaccount_id]
                )
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
            self.exchange._data_source.derivative_market_info_for_id(market_id=self.market_id)
        )
        tasks = [
            asyncio.get_event_loop().create_task(
                self.exchange._data_source._listen_to_chain_updates(
                    spot_markets=[],
                    derivative_markets=[market],
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
            self.exchange._data_source.derivative_market_info_for_id(market_id=self.market_id)
        )
        try:
            self.async_run_with_timeout(
                self.exchange._data_source._listen_to_chain_updates(
                    spot_markets=[],
                    derivative_markets=[market],
                    subaccount_ids=[self.portfolio_account_subaccount_id]
                )
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
            self.exchange._data_source.derivative_market_info_for_id(market_id=self.market_id)
        )
        tasks = [
            asyncio.get_event_loop().create_task(
                self.exchange._data_source._listen_to_chain_updates(
                    spot_markets=[],
                    derivative_markets=[market],
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
        self.assertNotIn(order.client_order_id, self.exchange._order_tracker.all_fillable_orders)
        self.assertFalse(
            self.is_logged(
                "INFO",
                f"BUY order {order.client_order_id} completely filled."
            )
        )

    @aioresponses()
    def test_invalid_trading_pair_not_in_all_trading_pairs(self, mock_api):
        self.exchange._set_trading_pair_symbol_map(None)

        invalid_pair, response = self.all_symbols_including_invalid_pair_mock_response
        self.exchange._data_source._query_executor._spot_markets_responses.put_nowait(
            self.all_spot_markets_mock_response
        )
        self.exchange._data_source._query_executor._derivative_markets_responses.put_nowait(response)

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
        self.exchange._data_source._query_executor._derivative_trades_responses.put_nowait(response)

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

        market = list(self.all_derivative_markets_mock_response.values())[0]
        maker_fee_rate = market.maker_fee_rate
        taker_fee_rate = market.taker_fee_rate

        maker_fee = self.exchange.get_fee(
            base_currency=self.base_asset,
            quote_currency=self.quote_asset,
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            position_action=PositionAction.OPEN,
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
            position_action=PositionAction.OPEN,
            amount=Decimal("1000"),
            price=Decimal("5"),
            is_maker=False,
        )

        self.assertEqual(taker_fee_rate, taker_fee.percent)
        self.assertEqual(self.quote_asset, maker_fee.percent_token)

    def test_restore_tracking_states_only_registers_open_orders(self):
        orders = []
        orders.append(GatewayPerpetualInFlightOrder(
            client_order_id=self.client_order_id_prefix + "1",
            exchange_order_id=str(self.expected_exchange_order_id),
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1000.0"),
            price=Decimal("1.0"),
            creation_timestamp=1640001112.223,
        ))
        orders.append(GatewayPerpetualInFlightOrder(
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
        orders.append(GatewayPerpetualInFlightOrder(
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
        orders.append(GatewayPerpetualInFlightOrder(
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
    def test_set_position_mode_success(self, mock_api):
        # There's only ONEWAY position mode
        pass

    @aioresponses()
    def test_set_position_mode_failure(self, mock_api):
        # There's only ONEWAY position mode
        pass

    @aioresponses()
    def test_set_leverage_failure(self, mock_api):
        # Leverage is configured in a per order basis
        pass

    @aioresponses()
    def test_set_leverage_success(self, mock_api):
        # Leverage is configured in a per order basis
        pass

    @aioresponses()
    def test_funding_payment_polling_loop_sends_update_event(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()

        self.async_tasks.append(asyncio.get_event_loop().create_task(self.exchange._funding_payment_polling_loop()))

        funding_payments = {
            "payments": [{
                "marketId": self.market_id,
                "subaccountId": self.portfolio_account_subaccount_id,
                "amount": str(self.target_funding_payment_payment_amount),
                "timestamp": 1000 * 1e3,
            }],
            "paging": {
                "total": 1000
            }
        }
        self.exchange._data_source.query_executor._funding_payments_responses.put_nowait(funding_payments)

        funding_rate = {
            "fundingRates": [
                {
                    "marketId": self.market_id,
                    "rate": str(self.target_funding_payment_funding_rate),
                    "timestamp": "1690426800493"
                },
            ],
            "paging": {
                "total": "2370"
            }
        }
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = partial(
            self._callback_wrapper_with_response,
            callback=lambda args, kwargs: request_sent_event.set(),
            response=funding_rate
        )
        self.exchange._data_source.query_executor._funding_rates_responses = mock_queue

        self.exchange._funding_fee_poll_notifier.set()
        self.async_run_with_timeout(request_sent_event.wait())

        request_sent_event.clear()

        funding_payments = {
            "payments": [{
                "marketId": self.market_id,
                "subaccountId": self.portfolio_account_subaccount_id,
                "amount": str(self.target_funding_payment_payment_amount),
                "timestamp": self.target_funding_payment_timestamp * 1e3,
            }],
            "paging": {
                "total": 1000
            }
        }
        self.exchange._data_source.query_executor._funding_payments_responses.put_nowait(funding_payments)

        funding_rate = {
            "fundingRates": [
                {
                    "marketId": self.market_id,
                    "rate": str(self.target_funding_payment_funding_rate),
                    "timestamp": "1690426800493"
                },
            ],
            "paging": {
                "total": "2370"
            }
        }
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = partial(
            self._callback_wrapper_with_response,
            callback=lambda args, kwargs: request_sent_event.set(),
            response=funding_rate
        )
        self.exchange._data_source.query_executor._funding_rates_responses = mock_queue

        self.exchange._funding_fee_poll_notifier.set()
        self.async_run_with_timeout(request_sent_event.wait())

        self.assertEqual(1, len(self.funding_payment_logger.event_log))
        funding_event: FundingPaymentCompletedEvent = self.funding_payment_logger.event_log[0]
        self.assertEqual(self.target_funding_payment_timestamp, funding_event.timestamp)
        self.assertEqual(self.exchange.name, funding_event.market)
        self.assertEqual(self.trading_pair, funding_event.trading_pair)
        self.assertEqual(self.target_funding_payment_payment_amount, funding_event.amount)
        self.assertEqual(self.target_funding_payment_funding_rate, funding_event.funding_rate)

    def test_listen_for_funding_info_update_initializes_funding_info(self):
        self.exchange._data_source._spot_market_and_trading_pair_map = None
        self.exchange._data_source._derivative_market_and_trading_pair_map = None
        self.configure_all_symbols_response(mock_api=None)
        self.exchange._data_source._query_executor._derivative_market_responses.put_nowait(
            {
                "market": {
                    "marketId": self.market_id,
                    "marketStatus": "active",
                    "ticker": f"{self.base_asset}/{self.quote_asset} PERP",
                    "oracleBase": "0x2d9315a88f3019f8efa88dfe9c0f0843712da0bac814461e27733f6b83eb51b3",  # noqa: mock
                    "oracleQuote": "0x1fc18861232290221461220bd4e2acd1dcdfbc89c84092c93c18bdc7756c1588",  # noqa: mock
                    "oracleType": "pyth",
                    "oracleScaleFactor": 6,
                    "initialMarginRatio": "0.195",
                    "maintenanceMarginRatio": "0.05",
                    "quoteDenom": self.quote_asset_denom,
                    "quoteTokenMeta": {
                        "name": "Testnet Tether USDT",
                        "address": "0x0000000000000000000000000000000000000000",  # noqa: mock
                        "symbol": self.quote_asset,
                        "logo": "https://static.alchemyapi.io/images/assets/825.png",
                        "decimals": self.quote_decimals,
                        "updatedAt": "1687190809716"
                    },
                    "makerFeeRate": "-0.0003",
                    "takerFeeRate": "0.003",
                    "serviceProviderFee": "0.4",
                    "isPerpetual": True,
                    "minPriceTickSize": "100",
                    "minQuantityTickSize": "0.0001",
                    "perpetualMarketInfo": {
                        "hourlyFundingRateCap": "0.000625",
                        "hourlyInterestRate": "0.00000416666",
                        "nextFundingTimestamp": str(self.target_funding_info_next_funding_utc_timestamp),
                        "fundingInterval": "3600"
                    },
                    "perpetualMarketFunding": {
                        "cumulativeFunding": "81363.592243119007273334",
                        "cumulativePrice": "1.432536051546776736",
                        "lastTimestamp": "1689423842"
                    },
                    "minNotional": "1000000",
                }
            }
        )

        funding_rate = {
            "fundingRates": [
                {
                    "marketId": self.market_id,
                    "rate": str(self.target_funding_info_rate),
                    "timestamp": "1690426800493"
                },
            ],
            "paging": {
                "total": "2370"
            }
        }
        self.exchange._data_source.query_executor._funding_rates_responses.put_nowait(funding_rate)

        oracle_price = {
            "price": str(self.target_funding_info_mark_price)
        }
        self.exchange._data_source.query_executor._oracle_prices_responses.put_nowait(oracle_price)

        trades = {
            "trades": [
                {
                    "orderHash": "0xbe1db35669028d9c7f45c23d31336c20003e4f8879721bcff35fc6f984a6481a",  # noqa: mock
                    "cid": "",
                    "subaccountId": "0x16aef18dbaa341952f1af1795cb49960f68dfee3000000000000000000000000",  # noqa: mock
                    "marketId": self.market_id,
                    "tradeExecutionType": "market",
                    "positionDelta": {
                        "tradeDirection": "buy",
                        "executionPrice": str(
                            self.target_funding_info_index_price * Decimal(f"1e{self.quote_decimals}")),
                        "executionQuantity": "3",
                        "executionMargin": "5472660"
                    },
                    "payout": "0",
                    "fee": "81764.1",
                    "executedAt": "1689423842613",
                    "feeRecipient": "inj1zyg3zyg3zyg3zyg3zyg3zyg3zyg3zyg3t5qxqh",  # noqa: mock
                    "tradeId": "13659264_800_0",
                    "executionSide": "taker"
                }
            ],
            "paging": {
                "total": "1000",
                "from": 1,
                "to": 1
            }
        }
        self.exchange._data_source.query_executor._derivative_trades_responses.put_nowait(trades)

        funding_info_update = FundingInfoUpdate(
            trading_pair=self.trading_pair,
            index_price=Decimal("29423.16356086"),
            mark_price=Decimal("9084900"),
            next_funding_utc_timestamp=1690426800,
            rate=Decimal("0.000004"),
        )
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [funding_info_update, asyncio.CancelledError]
        self.exchange.order_book_tracker.data_source._message_queue[
            self.exchange.order_book_tracker.data_source._funding_info_messages_queue_key
        ] = mock_queue

        try:
            self.async_run_with_timeout(self.exchange._listen_for_funding_info())
        except asyncio.CancelledError:
            pass

        funding_info: FundingInfo = self.exchange.get_funding_info(self.trading_pair)

        self.assertEqual(self.trading_pair, funding_info.trading_pair)
        self.assertEqual(self.target_funding_info_index_price, funding_info.index_price)
        self.assertEqual(self.target_funding_info_mark_price, funding_info.mark_price)
        self.assertEqual(
            self.target_funding_info_next_funding_utc_timestamp, funding_info.next_funding_utc_timestamp
        )
        self.assertEqual(self.target_funding_info_rate, funding_info.rate)

    def test_listen_for_funding_info_update_updates_funding_info(self):
        self.exchange._data_source._spot_market_and_trading_pair_map = None
        self.exchange._data_source._derivative_market_and_trading_pair_map = None
        self.configure_all_symbols_response(mock_api=None)
        self.exchange._data_source._query_executor._derivative_market_responses.put_nowait(
            {
                "market": {
                    "marketId": self.market_id,
                    "marketStatus": "active",
                    "ticker": f"{self.base_asset}/{self.quote_asset} PERP",
                    "oracleBase": "0x2d9315a88f3019f8efa88dfe9c0f0843712da0bac814461e27733f6b83eb51b3",  # noqa: mock
                    "oracleQuote": "0x1fc18861232290221461220bd4e2acd1dcdfbc89c84092c93c18bdc7756c1588",  # noqa: mock
                    "oracleType": "pyth",
                    "oracleScaleFactor": 6,
                    "initialMarginRatio": "0.195",
                    "maintenanceMarginRatio": "0.05",
                    "quoteDenom": self.quote_asset_denom,
                    "quoteTokenMeta": {
                        "name": "Testnet Tether USDT",
                        "address": "0x0000000000000000000000000000000000000000",  # noqa: mock
                        "symbol": self.quote_asset,
                        "logo": "https://static.alchemyapi.io/images/assets/825.png",
                        "decimals": self.quote_decimals,
                        "updatedAt": "1687190809716"
                    },
                    "makerFeeRate": "-0.0003",
                    "takerFeeRate": "0.003",
                    "serviceProviderFee": "0.4",
                    "isPerpetual": True,
                    "minPriceTickSize": "100",
                    "minQuantityTickSize": "0.0001",
                    "perpetualMarketInfo": {
                        "hourlyFundingRateCap": "0.000625",
                        "hourlyInterestRate": "0.00000416666",
                        "nextFundingTimestamp": str(self.target_funding_info_next_funding_utc_timestamp),
                        "fundingInterval": "3600"
                    },
                    "perpetualMarketFunding": {
                        "cumulativeFunding": "81363.592243119007273334",
                        "cumulativePrice": "1.432536051546776736",
                        "lastTimestamp": "1689423842"
                    },
                    "minNotional": "1000000",
                }
            }
        )

        funding_rate = {
            "fundingRates": [
                {
                    "marketId": self.market_id,
                    "rate": str(self.target_funding_info_rate),
                    "timestamp": "1690426800493"
                },
            ],
            "paging": {
                "total": "2370"
            }
        }
        self.exchange._data_source.query_executor._funding_rates_responses.put_nowait(funding_rate)

        oracle_price = {
            "price": str(self.target_funding_info_mark_price)
        }
        self.exchange._data_source.query_executor._oracle_prices_responses.put_nowait(oracle_price)

        trades = {
            "trades": [
                {
                    "orderHash": "0xbe1db35669028d9c7f45c23d31336c20003e4f8879721bcff35fc6f984a6481a",  # noqa: mock
                    "cid": "",
                    "subaccountId": "0x16aef18dbaa341952f1af1795cb49960f68dfee3000000000000000000000000",  # noqa: mock
                    "marketId": self.market_id,
                    "tradeExecutionType": "market",
                    "positionDelta": {
                        "tradeDirection": "buy",
                        "executionPrice": str(
                            self.target_funding_info_index_price * Decimal(f"1e{self.quote_decimals}")),
                        "executionQuantity": "3",
                        "executionMargin": "5472660"
                    },
                    "payout": "0",
                    "fee": "81764.1",
                    "executedAt": "1689423842613",
                    "feeRecipient": "inj1zyg3zyg3zyg3zyg3zyg3zyg3zyg3zyg3t5qxqh",  # noqa: mock
                    "tradeId": "13659264_800_0",
                    "executionSide": "taker"
                }
            ],
            "paging": {
                "total": "1000",
                "from": 1,
                "to": 1
            }
        }
        self.exchange._data_source.query_executor._derivative_trades_responses.put_nowait(trades)

        funding_info_update = FundingInfoUpdate(
            trading_pair=self.trading_pair,
            index_price=Decimal("29423.16356086"),
            mark_price=Decimal("9084900"),
            next_funding_utc_timestamp=1690426800,
            rate=Decimal("0.000004"),
        )
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [funding_info_update, asyncio.CancelledError]
        self.exchange.order_book_tracker.data_source._message_queue[
            self.exchange.order_book_tracker.data_source._funding_info_messages_queue_key
        ] = mock_queue

        try:
            self.async_run_with_timeout(
                self.exchange._listen_for_funding_info())
        except asyncio.CancelledError:
            pass

        self.assertEqual(1, self.exchange._perpetual_trading.funding_info_stream.qsize())  # rest in OB DS tests

    def test_existing_account_position_detected_on_positions_update(self):
        self._simulate_trading_rules_initialized()
        self.configure_all_symbols_response(mock_api=None)

        position_data = {
            "ticker": "BTC/USDT PERP",
            "marketId": self.market_id,
            "subaccountId": self.portfolio_account_subaccount_id,
            "direction": "long",
            "quantity": "0.01",
            "entryPrice": "25000000000",
            "margin": "248483436.058851",
            "liquidationPrice": "47474612957.985809",
            "markPrice": "28984256513.07",
            "aggregateReduceOnlyQuantity": "0",
            "updatedAt": "1691077382583",
            "createdAt": "-62135596800000"
        }
        positions = {
            "positions": [position_data],
            "paging": {
                "total": "1",
                "from": 1,
                "to": 1
            }
        }
        self.exchange._data_source._query_executor._derivative_positions_responses.put_nowait(positions)

        self.async_run_with_timeout(self.exchange._update_positions())

        self.assertEqual(len(self.exchange.account_positions), 1)
        pos = list(self.exchange.account_positions.values())[0]
        self.assertEqual(self.trading_pair, pos.trading_pair)
        self.assertEqual(PositionSide.LONG, pos.position_side)
        self.assertEqual(Decimal(position_data["quantity"]), pos.amount)
        entry_price = Decimal(position_data["entryPrice"]) * Decimal(f"1e{-self.quote_decimals}")
        self.assertEqual(entry_price, pos.entry_price)
        expected_leverage = ((Decimal(position_data["entryPrice"]) * Decimal(position_data["quantity"]))
                             / Decimal(position_data["margin"]))
        self.assertEqual(expected_leverage, pos.leverage)
        mark_price = Decimal(position_data["markPrice"]) * Decimal(f"1e{-self.quote_decimals}")
        expected_unrealized_pnl = (mark_price - entry_price) * Decimal(position_data["quantity"])
        self.assertEqual(expected_unrealized_pnl, pos.unrealized_pnl)

    def test_user_stream_position_update(self):
        self.configure_all_symbols_response(mock_api=None)
        self.exchange._set_current_timestamp(1640780000)

        oracle_price = {
            "price": "294.16356086"
        }
        self.exchange._data_source._query_executor._oracle_prices_responses.put_nowait(oracle_price)

        position_data = {
            "blockHeight": "20583",
            "blockTime": "1640001112223",
            "subaccountDeposits": [],
            "spotOrderbookUpdates": [],
            "derivativeOrderbookUpdates": [],
            "bankBalances": [],
            "spotTrades": [],
            "derivativeTrades": [],
            "spotOrders": [],
            "derivativeOrders": [],
            "positions": [
                {
                    "marketId": self.market_id,
                    "subaccountId": self.portfolio_account_subaccount_id,
                    "quantity": "25000000000000000000",
                    "entryPrice": "214151864000000000000000000",
                    "margin": "1191084296676205949365390184",
                    "cumulativeFundingEntry": "-10673348771610276382679388",
                    "isLong": True
                },
            ],
            "oraclePrices": [],
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [position_data, asyncio.CancelledError]
        self.exchange._data_source._query_executor._chain_stream_events = mock_queue

        self.async_tasks.append(
            asyncio.get_event_loop().create_task(
                self.exchange._user_stream_event_listener()
            )
        )

        market = self.async_run_with_timeout(
            self.exchange._data_source.derivative_market_info_for_id(market_id=self.market_id)
        )
        try:
            self.async_run_with_timeout(
                self.exchange._data_source._listen_to_chain_updates(
                    spot_markets=[],
                    derivative_markets=[market],
                    subaccount_ids=[self.portfolio_account_subaccount_id]
                ),
            )
        except asyncio.CancelledError:
            pass

        self.assertEqual(len(self.exchange.account_positions), 1)
        pos = list(self.exchange.account_positions.values())[0]
        self.assertEqual(self.trading_pair, pos.trading_pair)
        self.assertEqual(PositionSide.LONG, pos.position_side)
        quantity = Decimal(position_data["positions"][0]["quantity"]) * Decimal("1e-18")
        self.assertEqual(quantity, pos.amount)
        entry_price = Decimal(position_data["positions"][0]["entryPrice"]) * Decimal(f"1e{-self.quote_decimals-18}")
        self.assertEqual(entry_price, pos.entry_price)
        margin = Decimal(position_data["positions"][0]["margin"]) * Decimal(f"1e{-self.quote_decimals - 18}")
        expected_leverage = ((entry_price * quantity) / margin)
        self.assertEqual(expected_leverage, pos.leverage)
        mark_price = Decimal(oracle_price["price"])
        expected_unrealized_pnl = (mark_price - entry_price) * quantity
        self.assertEqual(expected_unrealized_pnl, pos.unrealized_pnl)

    def test_order_found_in_its_creating_transaction_not_marked_as_failed_during_order_creation_check(self):
        self.configure_all_symbols_response(mock_api=None)
        self.exchange._set_current_timestamp(1640780000.0)

        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "1",
            exchange_order_id="0x9f94598b4842ab66037eaa7c64ec10ae16dcf196e61db8522921628522c0f62e",  # noqa: mock
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("100"),
            position_action=PositionAction.OPEN,
        )

        self.assertIn(self.client_order_id_prefix + "1", self.exchange.in_flight_orders)
        order: GatewayPerpetualInFlightOrder = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]
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
                "txhash": "7CC335E98486A7C13133E04561A61930F9F7AD34E6A14A72BC25956F2495CE33",  # noqa: mock
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
                                "value": "inj1jtcvrdguuyx6dwz6xszpvkucyplw7z94vxlu07",  # noqa: mock
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
                                "value": "inj17xpfvakm2amg962yls6f84z3kell8c5l6s5ye9",  # noqa: mock
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
                                "value": "inj17xpfvakm2amg962yls6f84z3kell8c5l6s5ye9",  # noqa: mock
                                "index": True
                            },
                            {
                                "key": "sender",
                                "value": "inj1jtcvrdguuyx6dwz6xszpvkucyplw7z94vxlu07",  # noqa: mock
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
                                "value": "inj1jtcvrdguuyx6dwz6xszpvkucyplw7z94vxlu07",  # noqa: mock
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
                                "value": "inj1jtcvrdguuyx6dwz6xszpvkucyplw7z94vxlu07",  # noqa: mock
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
                                "value": "inj1jtcvrdguuyx6dwz6xszpvkucyplw7z94vxlu07",  # noqa: mock
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
                        "type": "injective.exchange.v1beta1.EventNewDerivativeOrders",
                        "attributes": [
                            {
                                "key": "buy_orders",
                                "value": json.dumps(
                                    [
                                        {
                                            "order_info": {
                                                "subaccount_id": "0xece2f1eea8b02ed71a06c2c9a18e5e56d5e59300000000000000000000000000",  # noqa: mock
                                                "fee_recipient": "inj1an30rm4gkqhdwxsxcty6rrj72m27tycqh2qy8v",  # noqa: mock
                                                "price": "50000000000.000000000000000000",
                                                "quantity": "0.010000000000000000",
                                                "cid": order.client_order_id
                                            },
                                            "order_type": "BUY_PO",
                                            "margin": "500000000.000000000000000000",
                                            "fillable": "0.010000000000000000",
                                            "trigger_price": "0.000000000000000000",
                                            "order_hash": base64.b64encode(order.exchange_order_id.encode()).decode()
                                        }
                                    ]
                                ),
                                "index": True
                            },
                            {
                                "key": "market_id",
                                "value": "\"0x17ef48032cb24375ba7c2e39f384e56433bcab20cbee9a7357e4cba2eb00abe6\"",  # noqa: mock"
                                "index": True
                            },
                            {
                                "key": "sell_orders",
                                "value": "[{\"order_info\":{\"subaccount_id\":\"0xece2f1eea8b02ed71a06c2c9a18e5e56d5e59300000000000000000000000000\",\"fee_recipient\":\"inj1an30rm4gkqhdwxsxcty6rrj72m27tycqh2qy8v\",\"price\":\"50000000000.000000000000000000\",\"quantity\":\"0.010000000000000000\",\"cid\":\"d4bfca07-d803-4444-809b-24e2c79d5491\"},\"order_type\":\"SELL_PO\",\"margin\":\"500000000.000000000000000000\",\"fillable\":\"0.010000000000000000\",\"trigger_price\":\"0.000000000000000000\",\"order_hash\":\"b55V8vJGE8L8f5s7iJ1HJV276+V8OsLe3N1NN4ddOWg=\"}]",  # noqa: mock"
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
    #         order_type=OrderType.LIMIT,
    #         trade_type=TradeType.BUY,
    #         price=Decimal("10000"),
    #         amount=Decimal("100"),
    #         position_action=PositionAction.OPEN,
    #     )
    #
    #     self.assertIn(self.client_order_id_prefix + "1", self.exchange.in_flight_orders)
    #     order: GatewayPerpetualInFlightOrder = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]
    #
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
    #             "txhash": "7CC335E98486A7C13133E04561A61930F9F7AD34E6A14A72BC25956F2495CE33",  # noqa: mock
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
    #                             "value": "inj1jtcvrdguuyx6dwz6xszpvkucyplw7z94vxlu07",  # noqa: mock
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
    #                             "value": "inj17xpfvakm2amg962yls6f84z3kell8c5l6s5ye9",  # noqa: mock
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
    #                             "value": "inj17xpfvakm2amg962yls6f84z3kell8c5l6s5ye9",  # noqa: mock
    #                             "index": True
    #                         },
    #                         {
    #                             "key": "sender",
    #                             "value": "inj1jtcvrdguuyx6dwz6xszpvkucyplw7z94vxlu07",  # noqa: mock
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
    #                             "value": "inj1jtcvrdguuyx6dwz6xszpvkucyplw7z94vxlu07",  # noqa: mock
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
    #                             "value": "inj1jtcvrdguuyx6dwz6xszpvkucyplw7z94vxlu07",  # noqa: mock
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
    #                             "value": "inj1jtcvrdguuyx6dwz6xszpvkucyplw7z94vxlu07",  # noqa: mock
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
    #                     "type": "injective.exchange.v1beta1.EventNewDerivativeOrders",
    #                     "attributes": [
    #                         {
    #                             "key": "buy_orders",
    #                             "value": json.dumps(
    #                                 [
    #                                     {
    #                                         "order_info": {
    #                                             "subaccount_id": "0xece2f1eea8b02ed71a06c2c9a18e5e56d5e59300000000000000000000000000",  # noqa: mock
    #                                             "fee_recipient": "inj1an30rm4gkqhdwxsxcty6rrj72m27tycqh2qy8v",  # noqa: mock
    #                                             "price": "50000000000.000000000000000000",
    #                                             "quantity": "0.010000000000000000",
    #                                             "cid": "d4bfca07-d803-4444-809b-24e2c79d5491"
    #                                         },
    #                                         "order_type": "BUY_PO",
    #                                         "margin": "500000000.000000000000000000",
    #                                         "fillable": "0.010000000000000000",
    #                                         "trigger_price": "0.000000000000000000",
    #                                         "order_hash": "b55V8vJGE8L8f5s7iJ1HJV276+V8OsLe3N1NN4ddOWg="
    #                                     }
    #                                 ]
    #                             ),
    #                             "index": True
    #                         },
    #                         {
    #                             "key": "market_id",
    #                             "value": "\"0x17ef48032cb24375ba7c2e39f384e56433bcab20cbee9a7357e4cba2eb00abe6\"",  # noqa: mock"
    #                             "index": True
    #                         },
    #                         {
    #                             "key": "sell_orders",
    #                             "value": "[{\"order_info\":{\"subaccount_id\":\"0xece2f1eea8b02ed71a06c2c9a18e5e56d5e59300000000000000000000000000\",\"fee_recipient\":\"inj1an30rm4gkqhdwxsxcty6rrj72m27tycqh2qy8v\",\"price\":\"50000000000.000000000000000000\",\"quantity\":\"0.010000000000000000\",\"cid\":\"d4bfca07-d803-4444-809b-24e2c79d5491\"},\"order_type\":\"SELL_PO\",\"margin\":\"500000000.000000000000000000\",\"fillable\":\"0.010000000000000000\",\"trigger_price\":\"0.000000000000000000\",\"order_hash\":\"b55V8vJGE8L8f5s7iJ1HJV276+V8OsLe3N1NN4ddOWg=\"}]",  # noqa: mock"
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
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("100"),
            position_action=PositionAction.OPEN,
        )

        self.assertIn(self.client_order_id_prefix + "1", self.exchange.in_flight_orders)
        order: GatewayPerpetualInFlightOrder = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

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
                "txhash": "7CC335E98486A7C13133E04561A61930F9F7AD34E6A14A72BC25956F2495CE33",  # noqa: mock
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
        self.configure_all_symbols_response(mock_api=mock_api)
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
                # noqa: mock
                "log": "",
                "events": [],
                "msgResponses": [
                    OrderedDict([
                        ("@type", "/cosmos.authz.v1beta1.MsgExecResponse"),
                        ("results", [
                            "CkIweGYxNGU5NGMxZmQ0MjE0M2I3ZGRhZjA4ZDE3ZWMxNzAzZGMzNzZlOWU2YWI0YjY0MjBhMzNkZTBhZmFlYzJjMTA="])
                        # noqa: mock
                    ])
                ]
            }
        }

    def _order_cancelation_request_successful_mock_response(self, order: InFlightOrder) -> Dict[str, Any]:
        return {"txhash": "79DBF373DE9C534EE2DC9D009F32B850DA8D0C73833FAA0FD52C6AE8989EC659",  # noqa: mock
                "rawLog": "[]",
                "code": 0}

    def _order_cancelation_request_erroneous_mock_response(self, order: InFlightOrder) -> Dict[str, Any]:
        return {"txhash": "79DBF373DE9C534EE2DC9D009F32B850DA8D0C73833FAA0FD52C6AE8989EC659",  # noqa: mock
                "rawLog": "Error",
                "code": 11}

    def _order_status_request_open_mock_response(self, order: GatewayPerpetualInFlightOrder) -> Dict[str, Any]:
        return {
            "orders": [
                {
                    "orderHash": order.exchange_order_id,
                    "cid": order.client_order_id,
                    "marketId": self.market_id,
                    "subaccountId": self.portfolio_account_subaccount_id,
                    "executionType": "market" if order.order_type == OrderType.MARKET else "limit",
                    "orderType": order.trade_type.name.lower(),
                    "price": str(order.price * Decimal(f"1e{self.quote_decimals}")),
                    "triggerPrice": "0",
                    "quantity": str(order.amount),
                    "filledQuantity": "0",
                    "state": "booked",
                    "createdAt": "1688476825015",
                    "updatedAt": "1688476825015",
                    "isReduceOnly": True,
                    "direction": order.trade_type.name.lower(),
                    "margin": "7219676852.725",
                    "txHash": order.creation_transaction_hash,
                },
            ],
            "paging": {
                "total": "1"
            },
        }

    def _order_status_request_partially_filled_mock_response(
        self, order: GatewayPerpetualInFlightOrder
    ) -> Dict[str, Any]:
        return {
            "orders": [
                {
                    "orderHash": order.exchange_order_id,
                    "cid": order.client_order_id,
                    "marketId": self.market_id,
                    "subaccountId": self.portfolio_account_subaccount_id,
                    "executionType": "market" if order.order_type == OrderType.MARKET else "limit",
                    "orderType": order.trade_type.name.lower(),
                    "price": str(order.price * Decimal(f"1e{self.quote_decimals}")),
                    "triggerPrice": "0",
                    "quantity": str(order.amount),
                    "filledQuantity": str(self.expected_partial_fill_amount),
                    "state": "partial_filled",
                    "createdAt": "1688476825015",
                    "updatedAt": "1688476825015",
                    "isReduceOnly": True,
                    "direction": order.trade_type.name.lower(),
                    "margin": "7219676852.725",
                    "txHash": order.creation_transaction_hash,
                },
            ],
            "paging": {
                "total": "1"
            },
        }

    def _order_status_request_completely_filled_mock_response(
        self, order: GatewayPerpetualInFlightOrder
    ) -> Dict[str, Any]:
        return {
            "orders": [
                {
                    "orderHash": order.exchange_order_id,
                    "cid": order.client_order_id,
                    "marketId": self.market_id,
                    "subaccountId": self.portfolio_account_subaccount_id,
                    "executionType": "market" if order.order_type == OrderType.MARKET else "limit",
                    "orderType": order.trade_type.name.lower(),
                    "price": str(order.price * Decimal(f"1e{self.quote_decimals}")),
                    "triggerPrice": "0",
                    "quantity": str(order.amount),
                    "filledQuantity": str(order.amount),
                    "state": "filled",
                    "createdAt": "1688476825015",
                    "updatedAt": "1688476825015",
                    "isReduceOnly": True,
                    "direction": order.trade_type.name.lower(),
                    "margin": "7219676852.725",
                    "txHash": order.creation_transaction_hash,
                },
            ],
            "paging": {
                "total": "1"
            },
        }

    def _order_status_request_canceled_mock_response(self, order: GatewayPerpetualInFlightOrder) -> Dict[str, Any]:
        return {
            "orders": [
                {
                    "orderHash": order.exchange_order_id,
                    "cid": order.client_order_id,
                    "marketId": self.market_id,
                    "subaccountId": self.portfolio_account_subaccount_id,
                    "executionType": "market" if order.order_type == OrderType.MARKET else "limit",
                    "orderType": order.trade_type.name.lower(),
                    "price": str(order.price * Decimal(f"1e{self.quote_decimals}")),
                    "triggerPrice": "0",
                    "quantity": str(order.amount),
                    "filledQuantity": "0",
                    "state": "canceled",
                    "createdAt": "1688476825015",
                    "updatedAt": "1688476825015",
                    "isReduceOnly": True,
                    "direction": order.trade_type.name.lower(),
                    "margin": "7219676852.725",
                    "txHash": order.creation_transaction_hash,
                },
            ],
            "paging": {
                "total": "1"
            },
        }

    def _order_status_request_not_found_mock_response(self, order: GatewayPerpetualInFlightOrder) -> Dict[str, Any]:
        return {
            "orders": [],
            "paging": {
                "total": "0"
            },
        }

    def _order_fills_request_partial_fill_mock_response(self, order: GatewayPerpetualInFlightOrder) -> Dict[str, Any]:
        return {
            "trades": [
                {
                    "orderHash": order.exchange_order_id,
                    "cid": order.client_order_id,
                    "subaccountId": self.portfolio_account_subaccount_id,
                    "marketId": self.market_id,
                    "tradeExecutionType": "limitFill",
                    "positionDelta": {
                        "tradeDirection": order.trade_type.name.lower,
                        "executionPrice": str(self.expected_partial_fill_price * Decimal(f"1e{self.quote_decimals}")),
                        "executionQuantity": str(self.expected_partial_fill_amount),
                        "executionMargin": "1245280000"
                    },
                    "payout": "1187984833.579447998034818126",
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

    def _order_fills_request_full_fill_mock_response(self, order: GatewayPerpetualInFlightOrder) -> Dict[str, Any]:
        return {
            "trades": [
                {
                    "orderHash": order.exchange_order_id,
                    "cid": order.client_order_id,
                    "subaccountId": self.portfolio_account_subaccount_id,
                    "marketId": self.market_id,
                    "tradeExecutionType": "limitFill",
                    "positionDelta": {
                        "tradeDirection": order.trade_type.name.lower,
                        "executionPrice": str(order.price * Decimal(f"1e{self.quote_decimals}")),
                        "executionQuantity": str(order.amount),
                        "executionMargin": "1245280000"
                    },
                    "payout": "1187984833.579447998034818126",
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
