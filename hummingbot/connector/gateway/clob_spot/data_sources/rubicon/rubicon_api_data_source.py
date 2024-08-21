from collections import defaultdict
from decimal import Decimal
from time import time
from typing import Any, Dict, List, Optional, Tuple

from dotmap import DotMap

from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.gateway.clob_spot.data_sources.gateway_clob_api_data_source_base import (
    GatewayCLOBAPIDataSourceBase,
)
from hummingbot.connector.gateway.clob_spot.data_sources.rubicon.rubicon_constants import CONNECTOR_NAME
from hummingbot.connector.gateway.clob_spot.data_sources.rubicon.rubicon_types import OrderStatus as RubiconOrderStatus
from hummingbot.connector.gateway.gateway_in_flight_order import GatewayInFlightOrder
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.common import OrderType
from hummingbot.core.data_type.in_flight_order import OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.trade_fee import MakerTakerExchangeFeeRates, TokenAmount, TradeFeeBase, TradeFeeSchema
from hummingbot.logger import HummingbotLogger


class RubiconAPIDataSource(GatewayCLOBAPIDataSourceBase):
    _logger: Optional[HummingbotLogger] = None

    def __init__(
            self,
            trading_pairs: List[str],
            connector_spec: Dict[str, Any],
            client_config_map: ClientConfigAdapter,
    ):
        super().__init__(
            trading_pairs=trading_pairs,
            connector_spec=connector_spec,
            client_config_map=client_config_map
        )

    @property
    def connector_name(self) -> str:
        return CONNECTOR_NAME

    @property
    def events_are_streamed(self) -> bool:
        return False

    def get_supported_order_types(self) -> List[OrderType]:
        return [OrderType.LIMIT, OrderType.MARKET]

    def _get_exchange_base_quote_tokens_from_market_info(self, market_info: Dict[str, Any]) -> Tuple[str, str]:
        base = market_info["baseSymbol"]
        quote = market_info["quoteSymbol"]
        return base, quote

    def _get_exchange_trading_pair_from_market_info(self, market_info: Dict[str, Any]) -> str:
        exchange_trading_pair = f"{market_info['baseSymbol']}/{market_info['quoteSymbol']}"
        return exchange_trading_pair

    def _get_trading_pair_from_market_info(self, market_info: Dict[str, Any]) -> str:
        base = market_info["baseSymbol"].upper()
        quote = market_info["quoteSymbol"].upper()
        trading_pair = combine_to_hb_trading_pair(base=base, quote=quote)
        return trading_pair

    def _parse_trading_rule(self, trading_pair: str, market_info: Dict[str, Any]) -> TradingRule:
        base = market_info["baseSymbol"].upper()
        quote = market_info["quoteSymbol"].upper()
        return TradingRule(
            trading_pair=combine_to_hb_trading_pair(base=base, quote=quote),
            min_order_size=Decimal(f"1e-{market_info['baseDecimals']}"),
            min_price_increment=Decimal(f"1e-{market_info['quoteDecimals']}"),
            min_quote_amount_increment=Decimal(f"1e-{market_info['quoteDecimals']}"),
            min_base_amount_increment=Decimal(f"1e-{market_info['baseDecimals']}"),
            min_notional_size=Decimal(f"1e-{market_info['quoteDecimals']}"),
            min_order_value=Decimal(f"1e-{market_info['quoteDecimals']}"),
        )

    def is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return str(status_update_exception).startswith("No update found for order")

    def is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return False

    async def get_order_status_update(self, in_flight_order: GatewayInFlightOrder) -> OrderUpdate:
        active_order = self.gateway_order_tracker.active_orders.get(in_flight_order.client_order_id)

        if active_order:
            self.logger().debug("get_order_status_update: start")

            if active_order.current_state != OrderState.CANCELED:
                await in_flight_order.get_exchange_order_id()

                request = {
                    "trading_pair": in_flight_order.trading_pair,
                    "chain": self._chain,
                    "network": self._network,
                    "connector": CONNECTOR_NAME,
                    "address": self._account_id,
                    "exchange_order_id": in_flight_order.exchange_order_id,
                }

                self.logger().debug(f"""get_clob_order_status_updates request:\n "{self._dump(request)}".""")

                response = await self._get_gateway_instance().get_clob_order_status_updates(**request)

                self.logger().debug(f"""get_clob_order_status_updates response:\n "{self._dump(response)}".""")

                order_response = DotMap(response, _dynamic=False)["orders"]
                order_update: OrderUpdate
                if order_response:
                    order = order_response[0]
                    if order:
                        order_status = RubiconOrderStatus.to_hummingbot(RubiconOrderStatus.from_name(order.state))
                    else:
                        order_status = in_flight_order.current_state

                    open_update = OrderUpdate(
                        trading_pair=in_flight_order.trading_pair,
                        update_timestamp=time(),
                        new_state=order_status,
                        client_order_id=in_flight_order.client_order_id,
                        exchange_order_id=in_flight_order.exchange_order_id,
                        misc_updates={
                            "creation_transaction_hash": in_flight_order.creation_transaction_hash,
                            "cancelation_transaction_hash": in_flight_order.cancel_tx_hash,
                        },
                    )

                    order_update = open_update
                else:
                    canceled_update = OrderUpdate(
                        trading_pair=in_flight_order.trading_pair,
                        update_timestamp=time(),
                        new_state=OrderState.CANCELED,
                        client_order_id=in_flight_order.client_order_id,
                        exchange_order_id=in_flight_order.exchange_order_id,
                        misc_updates={
                            "creation_transaction_hash": in_flight_order.creation_transaction_hash,
                            "cancelation_transaction_hash": in_flight_order.cancel_tx_hash,
                        },
                    )

                    order_update = canceled_update

                self.logger().debug("get_order_status_update: end")
                return order_update

        no_update = OrderUpdate(
            trading_pair=in_flight_order.trading_pair,
            update_timestamp=time(),
            new_state=in_flight_order.current_state,
            client_order_id=in_flight_order.client_order_id,
            exchange_order_id=in_flight_order.exchange_order_id,
            misc_updates={
                "creation_transaction_hash": in_flight_order.creation_transaction_hash,
                "cancelation_transaction_hash": in_flight_order.cancel_tx_hash,
            },
        )
        self.logger().debug("get_order_status_update: end")
        return no_update

    def _get_last_trade_price_from_ticker_data(self, ticker_data: List[Dict[str, Any]]) -> Decimal:
        self.logger().debug("get_last_traded_price: start")

        self.logger().debug(ticker_data)

        return Decimal(ticker_data["price"])

    def _get_maker_taker_exchange_fee_rates_from_market_info(self, market_info: Any) -> MakerTakerExchangeFeeRates:
        output = MakerTakerExchangeFeeRates(
            maker=Decimal(0),
            taker=Decimal(0),
            maker_flat_fees=[],
            taker_flat_fees=[]
        )
        return output

    async def get_all_order_fills(self, in_flight_order: GatewayInFlightOrder) -> List[TradeUpdate]:
        if in_flight_order.exchange_order_id:
            active_order = self.gateway_order_tracker.active_orders.get(in_flight_order.client_order_id)

            if active_order:
                if active_order.current_state != OrderState.CANCELED:
                    self.logger().debug("get_all_order_fills: start")

                    trade_update = None

                    request = {
                        "trading_pair": in_flight_order.trading_pair,
                        "chain": self._chain,
                        "network": self._network,
                        "connector": CONNECTOR_NAME,
                        "address": self._account_id,
                        "exchange_order_id": in_flight_order.exchange_order_id,
                    }

                    self.logger().debug(f"""get_clob_order_status_updates request:\n "{self._dump(request)}".""")

                    response = await self._get_gateway_instance().get_clob_order_status_updates(**request)

                    self.logger().debug(f"""get_clob_order_status_updates response:\n "{self._dump(response)}".""")

                    orders = DotMap(response, _dynamic=False)["orders"]

                    order = None
                    if len(orders):
                        order = orders[0]

                    if order is not None:
                        order_status = RubiconOrderStatus.to_hummingbot(RubiconOrderStatus.from_name(order.state))
                    else:
                        order_status = in_flight_order.current_state

                    if order and order_status == OrderState.FILLED:
                        timestamp = time()
                        trade_id = str(timestamp)

                        market = self._markets_info[in_flight_order.trading_pair]

                        trade_update = TradeUpdate(
                            trade_id=trade_id,
                            client_order_id=in_flight_order.client_order_id,
                            exchange_order_id=in_flight_order.exchange_order_id,
                            trading_pair=in_flight_order.trading_pair,
                            fill_timestamp=timestamp,
                            fill_price=in_flight_order.price,
                            fill_base_amount=in_flight_order.amount,
                            fill_quote_amount=in_flight_order.price * in_flight_order.amount,
                            fee=TradeFeeBase.new_spot_fee(
                                fee_schema=TradeFeeSchema(),
                                trade_type=in_flight_order.trade_type,
                                flat_fees=[TokenAmount(
                                    amount=Decimal(market.fees.taker),
                                    token=market.quoteToken.symbol
                                )]
                            ),
                        )

                    self.logger().debug("get_all_order_fills: end")

                    if trade_update:
                        return [trade_update]

        return []

    async def get_account_balances(self) -> Dict[str, Dict[str, Decimal]]:
        self._check_markets_initialized() or await self._update_markets()

        result = await self._get_gateway_instance().get_balances(
            chain=self.chain,
            network=self._network,
            address=self._account_id,
            token_symbols=list(self._hb_to_exchange_tokens_map.values()),
            connector=self.connector_name,
        )

        balances = defaultdict(dict)

        if result.get("balances") is None:
            raise ValueError(f"Error fetching balances for {self._account_id}.")

        for token, value in result["balances"].items():
            client_token = self._hb_to_exchange_tokens_map.inverse[token]
            # balance_value = value["total_balance"]
            balances[client_token]["total_balance"] = Decimal(value)
            balances[client_token]["available_balance"] = Decimal(value)

        return balances

    async def place_order(
        self, order: GatewayInFlightOrder, **kwargs
    ) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:

        order_result = await self._get_gateway_instance().clob_place_order(
            connector=self.connector_name,
            chain=self._chain,
            network=self._network,
            trading_pair=order.trading_pair,
            address=self._account_id,
            trade_type=order.trade_type,
            order_type=order.order_type,
            price=order.price,
            size=order.amount,
            client_order_id=order.client_order_id,
        )

        order_hash: Optional[str] = order_result.get("id")

        if order_hash is None:
            await self._on_create_order_transaction_failure(order=order, order_result=order_result)

        order_hash = order_hash.lower()

        misc_updates = {
            "creation_transaction_hash": "",
        }

        return order_hash, misc_updates
