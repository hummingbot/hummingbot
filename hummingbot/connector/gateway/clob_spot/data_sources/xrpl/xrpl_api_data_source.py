import asyncio
from collections import defaultdict
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from xrpl.clients import JsonRpcClient

from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.gateway.clob_spot.data_sources.gateway_clob_api_data_source_base import (
    GatewayCLOBAPIDataSourceBase,
)
from hummingbot.connector.gateway.clob_spot.data_sources.xrpl import xrpl_constants as CONSTANTS
from hummingbot.connector.gateway.clob_spot.data_sources.xrpl.xrpl_constants import (
    BASE_PATH_URL,
    CONNECTOR_NAME,
    ORDER_SIDE_MAP,
    WS_PATH_URL,
    XRPL_TO_HB_STATUS_MAP,
)
from hummingbot.connector.gateway.common_types import CancelOrderResult, PlaceOrderResult
from hummingbot.connector.gateway.gateway_in_flight_order import GatewayInFlightOrder
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair, get_new_numeric_client_order_id
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.common import OrderType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.trade_fee import MakerTakerExchangeFeeRates, TokenAmount, TradeFeeBase, TradeFeeSchema
from hummingbot.core.event.events import MarketEvent
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.core.rate_oracle.rate_oracle import RateOracle
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.core.utils.tracking_nonce import NonceCreator
from hummingbot.logger import HummingbotLogger


class XrplAPIDataSource(GatewayCLOBAPIDataSourceBase):
    """An interface class to the XRPL blockchain.
    """

    _logger: Optional[HummingbotLogger] = None

    def __init__(
            self,
            trading_pairs: List[str],
            connector_spec: Dict[str, Any],
            client_config_map: ClientConfigAdapter,
    ):
        super().__init__(
            trading_pairs=trading_pairs, connector_spec=connector_spec, client_config_map=client_config_map
        )
        self._chain = 'xrpl'
        if self._network == "mainnet":
            self._base_url = BASE_PATH_URL["mainnet"]
            self._base_ws_url = WS_PATH_URL["mainnet"]
        elif self._network == "testnet":
            self._base_url = BASE_PATH_URL["testnet"]
            self._base_ws_url = WS_PATH_URL["testnet"]
        else:
            raise ValueError(f"Invalid network: {self._network}")

        self._client = JsonRpcClient(self._base_url)
        self._client_order_id_nonce_provider = NonceCreator.for_microseconds()
        self._throttler = AsyncThrottler(rate_limits=CONSTANTS.RATE_LIMITS)
        self.max_snapshots_update_interval = 15
        self.min_snapshots_update_interval = 5

    @property
    def connector_name(self) -> str:
        return CONNECTOR_NAME

    @property
    def events_are_streamed(self) -> bool:
        return False

    async def start(self):
        await super().start()

    async def stop(self):
        await super().stop()

    def get_supported_order_types(self) -> List[OrderType]:
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    async def batch_order_create(self, orders_to_create: List[GatewayInFlightOrder]) -> List[PlaceOrderResult]:
        place_order_results = []

        for order in orders_to_create:
            _, misc_updates = await self.place_order(order)

            exception = None
            if misc_updates is None:
                self.logger().error("The batch order create transaction failed.")
                exception = ValueError(f"The creation transaction has failed for order: {order.client_order_id}.")

            place_order_results.append(
                PlaceOrderResult(
                    update_timestamp=self._time(),
                    client_order_id=order.client_order_id,
                    exchange_order_id=None,
                    trading_pair=order.trading_pair,
                    misc_updates={
                        "creation_transaction_hash": misc_updates["creation_transaction_hash"],
                    },
                    exception=exception,
                )
            )

        return place_order_results

    async def batch_order_cancel(self, orders_to_cancel: List[GatewayInFlightOrder]) -> List[CancelOrderResult]:
        in_flight_orders_to_cancel = [
            self._gateway_order_tracker.fetch_tracked_order(client_order_id=order.client_order_id)
            for order in orders_to_cancel
        ]
        cancel_order_results = []
        if len(in_flight_orders_to_cancel) != 0:
            exchange_order_ids_to_cancel = await safe_gather(
                *[order.get_exchange_order_id() for order in in_flight_orders_to_cancel],
                return_exceptions=True,
            )
            found_orders_to_cancel = [
                order
                for order, result in zip(orders_to_cancel, exchange_order_ids_to_cancel)
                if not isinstance(result, asyncio.TimeoutError)
            ]

            for order in found_orders_to_cancel:
                _, misc_updates = await self.cancel_order(order)

                exception = None
                if misc_updates is None:
                    self.logger().error("The batch order cancel transaction failed.")
                    exception = ValueError(
                        f"The cancellation transaction has failed for order: {order.client_order_id}")

                cancel_order_results.append(
                    CancelOrderResult(
                        client_order_id=order.client_order_id,
                        trading_pair=order.trading_pair,
                        misc_updates={
                            "cancelation_transaction_hash": misc_updates["cancelation_transaction_hash"],
                        },
                        exception=exception,
                    )
                )

        return cancel_order_results

    def get_client_order_id(
            self, is_buy: bool, trading_pair: str, hbot_order_id_prefix: str, max_id_len: Optional[int]
    ) -> str:
        decimal_id = get_new_numeric_client_order_id(
            nonce_creator=self._client_order_id_nonce_provider,
            max_id_bit_count=CONSTANTS.MAX_ID_BIT_COUNT,
        )
        return "{0:#0{1}x}".format(  # https://stackoverflow.com/a/12638477/6793798
            decimal_id, CONSTANTS.MAX_ID_HEX_DIGITS + 2
        )

    async def get_account_balances(self) -> Dict[str, Dict[str, Decimal]]:
        self._check_markets_initialized() or await self._update_markets()

        async with self._throttler.execute_task(limit_id=CONSTANTS.BALANCE_REQUEST_LIMIT_ID):
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
            if value.get("total_balance") is not None and value.get("available_balance") is not None:
                balances[client_token]["total_balance"] = Decimal(value.get("total_balance", 0))
                balances[client_token]["available_balance"] = Decimal(value.get("available_balance", 0))

        return balances

    async def get_order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        async with self._throttler.execute_task(limit_id=CONSTANTS.ORDERBOOK_REQUEST_LIMIT_ID):
            data = await self._get_gateway_instance().get_clob_orderbook_snapshot(
                trading_pair=trading_pair, connector=self.connector_name, chain=self._chain, network=self._network
            )

        bids = [
            (Decimal(bid["price"]), Decimal(bid["quantity"]))
            for bid in data["buys"]
            if Decimal(bid["quantity"]) != 0
        ]
        asks = [
            (Decimal(ask["price"]), Decimal(ask["quantity"]))
            for ask in data["sells"]
            if Decimal(ask["quantity"]) != 0
        ]
        snapshot_msg = OrderBookMessage(
            message_type=OrderBookMessageType.SNAPSHOT,
            content={
                "trading_pair": trading_pair,
                "update_id": self._time() * 1e3,
                "bids": bids,
                "asks": asks,
            },
            timestamp=data["timestamp"],
        )
        return snapshot_msg

    async def get_order_status_update(self, in_flight_order: GatewayInFlightOrder) -> OrderUpdate:
        await in_flight_order.get_creation_transaction_hash()

        if in_flight_order.exchange_order_id is None:
            in_flight_order.exchange_order_id = await self._get_exchange_order_id_from_transaction(
                in_flight_order=in_flight_order)

            if in_flight_order.exchange_order_id is None:
                raise ValueError(f"Order {in_flight_order.client_order_id} not found on exchange.")

        status_update = await self._get_order_status_update_with_order_id(in_flight_order=in_flight_order)
        self._publisher.trigger_event(event_tag=MarketEvent.OrderUpdate, message=status_update)

        if status_update is None:
            raise ValueError(f"No update found for order {in_flight_order.exchange_order_id}.")

        return status_update

    async def get_last_traded_price(self, trading_pair: str) -> Decimal:
        ticker_data = await self._get_ticker_data(trading_pair=trading_pair)
        last_traded_price = self._get_last_trade_price_from_ticker_data(ticker_data=ticker_data)
        return last_traded_price

    async def get_all_order_fills(self, in_flight_order: GatewayInFlightOrder) -> List[TradeUpdate]:
        self._check_markets_initialized() or await self._update_markets()

        if in_flight_order.exchange_order_id is None:  # we still haven't received an order status update
            await self.get_order_status_update(in_flight_order=in_flight_order)

        resp = await self._get_gateway_instance().get_clob_order_status_updates(
            trading_pair=in_flight_order.trading_pair,
            chain=self._chain,
            network=self._network,
            connector=self.connector_name,
            address=self._account_id,
            exchange_order_id=in_flight_order.exchange_order_id)

        orders = resp.get("orders")

        if len(orders) == 0:
            return []

        fill_datas = orders[0].get("associatedFills")

        trade_updates = []
        for fill_data in fill_datas:
            fill_price = Decimal(fill_data["price"])
            fill_size = Decimal(fill_data["quantity"])
            fee_token = self._hb_to_exchange_tokens_map.inverse[fill_data["feeToken"]]
            fee = TradeFeeBase.new_spot_fee(
                fee_schema=TradeFeeSchema(),
                trade_type=ORDER_SIDE_MAP[fill_data["side"]],
                flat_fees=[TokenAmount(token=fee_token, amount=Decimal(fill_data["fee"]))]
            )
            trade_update = TradeUpdate(
                trade_id=fill_data["tradeId"],
                client_order_id=in_flight_order.client_order_id,
                exchange_order_id=fill_data["orderHash"],
                trading_pair=in_flight_order.trading_pair,
                fill_timestamp=self._xrpl_timestamp_to_timestamp(period_str=fill_data["timestamp"]),
                fill_price=fill_price,
                fill_base_amount=fill_size,
                fill_quote_amount=fill_price * fill_size,
                fee=fee,
                is_taker=fill_data["type"] == "Taker",
            )
            trade_updates.append(trade_update)

        return trade_updates

    def _get_exchange_base_quote_tokens_from_market_info(self, market_info: Dict[str, Any]) -> Tuple[str, str]:
        # get base and quote tokens from market info "marketId" field which has format "baseCurrency-quoteCurrency"
        base, quote = market_info["marketId"].split("-")
        return base, quote

    def _get_exchange_trading_pair_from_market_info(self, market_info: Dict[str, Any]) -> str:
        base, quote = market_info["marketId"].split("-")
        exchange_trading_pair = f"{base}/{quote}"
        return exchange_trading_pair

    def _get_maker_taker_exchange_fee_rates_from_market_info(
            self, market_info: Dict[str, Any]
    ) -> MakerTakerExchangeFeeRates:
        # Currently, trading fees on XRPL dex are not following maker/taker model, instead they based on transfer fees
        # https://xrpl.org/transfer-fees.html
        maker_taker_exchange_fee_rates = MakerTakerExchangeFeeRates(
            maker=Decimal(0),
            taker=Decimal(0),
            maker_flat_fees=[],
            taker_flat_fees=[],
        )
        return maker_taker_exchange_fee_rates

    def _get_trading_pair_from_market_info(self, market_info: Dict[str, Any]) -> str:
        base, quote = market_info["marketId"].split("-")
        trading_pair = combine_to_hb_trading_pair(base=base, quote=quote)
        return trading_pair

    def _parse_trading_rule(self, trading_pair: str, market_info: Dict[str, Any]) -> TradingRule:
        base, quote = market_info["marketId"].split("-")
        return TradingRule(
            trading_pair=combine_to_hb_trading_pair(base=base, quote=quote),
            min_order_size=Decimal(f"1e-{market_info['baseTickSize']}"),
            min_price_increment=Decimal(f"1e-{market_info['quoteTickSize']}"),
            min_quote_amount_increment=Decimal(f"1e-{market_info['quoteTickSize']}"),
            min_base_amount_increment=Decimal(f"1e-{market_info['baseTickSize']}"),
            min_notional_size=Decimal(f"1e-{market_info['quoteTickSize']}"),
            min_order_value=Decimal(f"1e-{market_info['quoteTickSize']}"))

    def is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return str(status_update_exception).startswith("No update found for order")

    def is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return False

    async def _get_exchange_order_id_from_transaction(self, in_flight_order: GatewayInFlightOrder) -> Optional[str]:
        resp = await self._get_gateway_instance().get_transaction_status(
            chain=self._chain,
            network=self._network,
            transaction_hash=in_flight_order.creation_transaction_hash,
            connector=self.connector_name,
            address=self._account_id,
        )

        exchange_order_id = str(resp.get("sequence"))

        return exchange_order_id

    async def _get_order_status_update_with_order_id(self, in_flight_order: InFlightOrder) -> Optional[OrderUpdate]:
        try:
            resp = await self._get_gateway_instance().get_clob_order_status_updates(
                trading_pair=in_flight_order.trading_pair,
                chain=self._chain,
                network=self._network,
                connector=self.connector_name,
                address=self._account_id,
                exchange_order_id=in_flight_order.exchange_order_id)

        except OSError as e:
            if "HTTP status is 404" in str(e):
                raise ValueError(f"No update found for order {in_flight_order.exchange_order_id}.")
            raise e

        if resp.get("orders") == "":
            raise ValueError(f"No update found for order {in_flight_order.exchange_order_id}.")
        else:
            orders = resp.get("orders")

            if len(orders) == 0:
                return None

            status_update = OrderUpdate(
                trading_pair=in_flight_order.trading_pair,
                update_timestamp=pd.Timestamp(resp["timestamp"]).timestamp(),
                new_state=XRPL_TO_HB_STATUS_MAP[orders[0]["state"]],
                client_order_id=in_flight_order.client_order_id,
                exchange_order_id=orders[0]["hash"],
            )

        return status_update

    async def _get_ticker_data(self, trading_pair: str) -> Dict[str, Any]:
        async with self._throttler.execute_task(limit_id=CONSTANTS.TICKER_REQUEST_LIMIT_ID):
            ticker_data = await self._get_gateway_instance().get_clob_ticker(
                connector=self.connector_name,
                chain=self._chain,
                network=self._network,
                trading_pair=trading_pair,
            )

        for market in ticker_data["markets"]:
            if market["marketId"] == trading_pair:
                return market

        raise ValueError(f"Ticker data not found for trading pair {trading_pair}.")

    def _get_last_trade_price_from_ticker_data(self, ticker_data: Dict[str, Any]) -> Decimal:
        # Get mid-price from order book for now since there is no easy way to get last trade price from ticker data
        RateOracle.get_instance().set_price(pair=ticker_data["marketId"], price=Decimal(ticker_data["midprice"]))

        return ticker_data["midprice"]

    @staticmethod
    def _xrpl_timestamp_to_timestamp(period_str: str) -> float:
        ts = pd.Timestamp(period_str).timestamp()
        return ts

    def _get_gateway_instance(self) -> GatewayHttpClient:
        gateway_instance = GatewayHttpClient.get_instance(self._client_config)
        return gateway_instance
