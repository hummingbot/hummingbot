# import asyncio
# from collections import defaultdict
from decimal import Decimal

# from itertools import chain
from typing import Any, Dict, List, Optional

import pandas as pd
from xrpl.clients import JsonRpcClient
from xrpl.models import Tx

from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.gateway.clob_spot.data_sources.gateway_clob_api_data_source_base import (
    GatewayCLOBAPIDataSourceBase,
)

# from hummingbot.connector.gateway.clob_spot.data_sources.xrpl import xrpl_constants as CONSTANTS
from hummingbot.connector.gateway.clob_spot.data_sources.xrpl.xrpl_constants import (
    BASE_PATH_URL,
    CONNECTOR_NAME,
    ORDER_SIDE_MAP,
    WS_PATH_URL,
    XRPL_TO_HB_STATUS_MAP,
)

# from hummingbot.connector.gateway.common_types import CancelOrderResult, PlaceOrderResult
from hummingbot.connector.gateway.gateway_in_flight_order import GatewayInFlightOrder

# from hummingbot.connector.trading_rule import TradingRule
# from hummingbot.connector.utils import combine_to_hb_trading_pair, get_new_numeric_client_order_id
# from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.common import OrderType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, TradeUpdate

# from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase, TradeFeeSchema
from hummingbot.core.event.events import MarketEvent

# from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
# from hummingbot.core.utils.tracking_nonce import NonceCreator
# from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
# from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
# from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger


class XRPLAPIDataSource(GatewayCLOBAPIDataSourceBase):
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

    @property
    def connector_name(self) -> str:
        return CONNECTOR_NAME

    async def start(self):
        await super().start()

    async def stop(self):
        await super().stop()

    def get_supported_order_types(self) -> List[OrderType]:
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER]

    async def get_order_status_update(self, in_flight_order: GatewayInFlightOrder) -> OrderUpdate:
        await in_flight_order.get_creation_transaction_hash()

        if in_flight_order.exchange_order_id is None:
            in_flight_order.exchange_order_id = self._get_exchange_order_id_from_transaction(in_flight_order=in_flight_order)

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

        fill_datas = resp.get("associatedFills")

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

    def _get_exchange_order_id_from_transaction(self, in_flight_order: GatewayInFlightOrder) -> Optional[str]:
        tx_request = Tx(transaction=in_flight_order.creation_transaction_hash)
        tx_response = self._client.request(tx_request)

        return tx_response.result.get('Sequence')

    async def _get_order_status_update_with_order_id(self, in_flight_order: InFlightOrder) -> Optional[OrderUpdate]:
        try:
            resp = await self._get_gateway_instance().get_clob_order_status_updates(trading_pair=in_flight_order.trading_pair,
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
            status_update = OrderUpdate(
                trading_pair=in_flight_order.trading_pair,
                update_timestamp=pd.Timestamp(resp["timestamp"]).timestamp(),
                new_state=XRPL_TO_HB_STATUS_MAP[resp[in_flight_order.exchange_order_id]["state"]],
                client_order_id=in_flight_order.client_order_id,
                exchange_order_id=resp[in_flight_order.exchange_order_id]["hash"],
            )

        return status_update

    async def _get_ticker_data(self, trading_pair: str) -> List[Dict[str, Any]]:
        ticker_data = await self._get_gateway_instance().get_clob_ticker(
            connector=self.connector_name,
            chain=self._chain,
            network=self._network,
            trading_pair=trading_pair,
        )
        return ticker_data["markets"]

    def _get_last_trade_price_from_ticker_data(self, ticker_data: List[Dict[str, Any]]) -> Decimal:
        # Get mid price from order book for now since there is no easy way to get last trade price from ticker data
        raise NotImplementedError

    @staticmethod
    def _xrpl_timestamp_to_timestamp(period_str: str) -> float:
        ts = pd.Timestamp(period_str).timestamp()
        return ts
