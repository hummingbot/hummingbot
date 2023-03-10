import asyncio
from collections import defaultdict
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple, Union

import pandas as pd

from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.gateway.clob_spot.data_sources.dexalot import dexalot_constants as CONSTANTS
from hummingbot.connector.gateway.clob_spot.data_sources.dexalot.dexalot_auth import DexalotAuth, WalletSigner
from hummingbot.connector.gateway.clob_spot.data_sources.dexalot.dexalot_constants import (
    CONNECTOR_NAME,
    DEXALOT_TO_HB_NUMERIC_STATUS_MAP,
    DEXALOT_TO_HB_STATUS_MAP,
    ORDER_SIDE_MAP,
)
from hummingbot.connector.gateway.clob_spot.data_sources.dexalot.dexalot_web_utils import build_api_factory
from hummingbot.connector.gateway.clob_spot.data_sources.gateway_clob_api_data_source_base import (
    GatewayCLOBAPIDataSourceBase,
)
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair, get_new_numeric_client_order_id
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.common import OrderType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.trade_fee import MakerTakerExchangeFeeRates, TokenAmount, TradeFeeBase, TradeFeeSchema
from hummingbot.core.event.events import MarketEvent, OrderBookDataSourceEvent
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.utils.tracking_nonce import NonceCreator
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger


class DexalotAPIDataSource(GatewayCLOBAPIDataSourceBase):
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
        self._api_key = connector_spec["additional_prompt_values"]["api_key"]
        self._api_factory: Optional[WebAssistantsFactory] = None
        self._stream_listener: Optional[asyncio.Task] = None
        self._client_order_id_nonce_provider = NonceCreator.for_microseconds()
        self._max_id_hex_digits = 64
        self._max_id_bit_count = self._max_id_hex_digits * 4
        self._last_traded_price_map = defaultdict(lambda: Decimal("0"))
        self._snapshots_id_nonce_provider = NonceCreator.for_milliseconds()

    @property
    def connector_name(self) -> str:
        return CONNECTOR_NAME

    @property
    def events_are_streamed(self) -> bool:
        return False

    @property
    def current_block_time(self) -> float:
        return 5  # ~2s for Gateway submission + 2s for block inclusion + 1s buffer

    async def start(self):
        signer = WalletSigner(
            chain=self._chain,
            network=self._network,
            address=self._account_id,
            gateway_instance=self._get_gateway_instance(),
        )
        auth = DexalotAuth(signer=signer, address=self._account_id)
        throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        self._api_factory = build_api_factory(throttler=throttler, api_key=self._api_key, auth=auth)
        self._stream_listener = safe_ensure_future(self._listen_to_streams())
        await super().start()

    async def stop(self):
        await super().stop()
        self._stream_listener is not None and self._stream_listener.cancel()

    def get_supported_order_types(self) -> List[OrderType]:
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER]

    def get_client_order_id(
        self, is_buy: bool, trading_pair: str, hbot_order_id_prefix: str, max_id_len: Optional[int]
    ) -> str:
        decimal_id = get_new_numeric_client_order_id(
            nonce_creator=self._client_order_id_nonce_provider, max_id_bit_count=self._max_id_bit_count
        )
        return "{0:#0{1}x}".format(  # https://stackoverflow.com/a/12638477/6793798
            decimal_id, self._max_id_hex_digits + 2
        )

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
        for exchange_token, total_balance in result["balances"]["total"].items():
            token = self._hb_to_exchange_tokens_map.inverse[exchange_token]
            balance_value = Decimal(total_balance)
            if balance_value != 0:
                balances[token]["total_balance"] = balance_value
        for exchange_token, available_balance in result["balances"]["available"].items():
            token = self._hb_to_exchange_tokens_map.inverse[exchange_token]
            if token in balances:
                balances[token]["available_balance"] = Decimal(available_balance)
        return balances

    async def get_order_status_update(self, in_flight_order: InFlightOrder) -> OrderUpdate:
        if in_flight_order.exchange_order_id is None:
            status_update = await self._get_order_status_update_with_batch_request(in_flight_order=in_flight_order)
        else:
            status_update = await self._get_order_status_update_with_order_id(in_flight_order=in_flight_order)

        if status_update is None:
            raise IOError(f"No update found for order {in_flight_order.client_order_id}")

        if in_flight_order.current_state == OrderState.PENDING_CREATE and status_update.new_state != OrderState.OPEN:
            open_update = OrderUpdate(
                trading_pair=in_flight_order.trading_pair,
                update_timestamp=status_update.update_timestamp,
                new_state=OrderState.OPEN,
                client_order_id=in_flight_order.client_order_id,
                exchange_order_id=status_update.exchange_order_id,
            )
            self._publisher.trigger_event(event_tag=MarketEvent.OrderUpdate, message=open_update)
        self._publisher.trigger_event(event_tag=MarketEvent.OrderUpdate, message=status_update)

        return status_update

    async def get_all_order_fills(self, in_flight_order: InFlightOrder) -> List[TradeUpdate]:
        self._check_markets_initialized() or await self._update_markets()

        if in_flight_order.exchange_order_id is None:  # we still haven't received an order status update
            await self.get_order_status_update(in_flight_order=in_flight_order)

        request_params = {
            "orderid": await in_flight_order.get_exchange_order_id(),
        }

        resp = await self._api_get(
            path_url=CONSTANTS.EXECUTIONS_PATH,
            throttler_limit_id=CONSTANTS.EXECUTIONS_RATE_LIMIT_ID,
            params=request_params,
            is_auth_required=True,
        )

        trade_updates = []
        for fill_data in resp:
            fill_price = Decimal(fill_data["price"])
            fill_size = Decimal(fill_data["quantity"])
            fee_token = self._hb_to_exchange_tokens_map.inverse[fill_data["feeunit"]]
            fee = TradeFeeBase.new_spot_fee(
                fee_schema=TradeFeeSchema(),
                trade_type=ORDER_SIDE_MAP[fill_data["side"]],
                flat_fees=[TokenAmount(token=fee_token, amount=Decimal(fill_data["fee"]))]
            )
            trade_update = TradeUpdate(
                trade_id=fill_data["execid"],
                client_order_id=in_flight_order.client_order_id,
                exchange_order_id=fill_data["orderid"],
                trading_pair=in_flight_order.trading_pair,
                fill_timestamp=self._dexalot_timestamp_to_timestamp(period_str=fill_data["ts"]),
                fill_price=fill_price,
                fill_base_amount=fill_size,
                fill_quote_amount=fill_price * fill_size,
                fee=fee,
                is_taker=fill_data["type"] == "T",
            )
            trade_updates.append(trade_update)

        return trade_updates

    async def get_last_traded_price(self, trading_pair: str) -> Decimal:
        return self._last_traded_price_map[trading_pair]

    async def _update_snapshots_loop(self):
        pass  # Dexalot streams the snapshots via websocket

    async def _get_order_status_update_with_batch_request(
        self, in_flight_order: InFlightOrder
    ) -> Optional[OrderUpdate]:
        status_update = None
        page_length = 50
        period_from = self._timestamp_to_dexalot_timestamp(
            timestamp=in_flight_order.creation_timestamp - 1
        )

        done = False
        page = 0
        while not done:
            page += 1
            request_params = {
                "itemsperpage": page_length,
                "pageno": page,
                "periodfrom": period_from,
            }

            resp = await self._api_get(
                path_url=CONSTANTS.ORDERS_PATH,
                throttler_limit_id=CONSTANTS.ORDERS_RATE_LIMIT_ID,
                params=request_params,
                is_auth_required=True,
            )
            status_update = self._parse_order_status_response_for_order_update(
                in_flight_order=in_flight_order, response=resp
            )
            done = status_update is not None or len(resp["rows"]) < page_length

        return status_update

    @staticmethod
    def _parse_order_status_response_for_order_update(
        in_flight_order: InFlightOrder, response: Dict[str, Any]
    ) -> Optional[OrderUpdate]:
        order_update = None

        for row in response["rows"]:
            if row["clientordid"] == in_flight_order.client_order_id:
                order_update = OrderUpdate(
                    trading_pair=in_flight_order.trading_pair,
                    update_timestamp=pd.Timestamp(row["update_ts"]).timestamp(),
                    new_state=DEXALOT_TO_HB_NUMERIC_STATUS_MAP[row["status"]],
                    client_order_id=in_flight_order.client_order_id,
                    exchange_order_id=row["id"],
                )
                break

        return order_update

    async def _get_order_status_update_with_order_id(self, in_flight_order: InFlightOrder) -> Optional[OrderUpdate]:
        url = f"{CONSTANTS.ORDERS_PATH}/{in_flight_order.exchange_order_id}"
        resp = await self._api_get(
            path_url=url, throttler_limit_id=CONSTANTS.ORDERS_RATE_LIMIT_ID, is_auth_required=True
        )

        if resp.get("message") == "":
            status_update = None
        else:
            status_update = OrderUpdate(
                trading_pair=in_flight_order.trading_pair,
                update_timestamp=pd.Timestamp(resp["updateTs"]).timestamp(),
                new_state=DEXALOT_TO_HB_STATUS_MAP[resp["status"]],
                client_order_id=in_flight_order.client_order_id,
                exchange_order_id=resp["id"],
            )

        return status_update

    def _parse_trading_rule(self, trading_pair: str, market_info: Dict[str, Any]) -> TradingRule:
        base = market_info["baseSymbol"].upper()
        quote = market_info["quoteSymbol"].upper()
        quote_scaler = Decimal(f"1e-{market_info['quoteDecimals']}")
        return TradingRule(
            trading_pair=combine_to_hb_trading_pair(base=base, quote=quote),
            min_order_size=Decimal(f"1e-{market_info['quoteDisplayDecimals']}"),
            min_price_increment=Decimal(f"1e-{market_info['baseDisplayDecimals']}"),
            min_quote_amount_increment=Decimal(f"1e-{market_info['baseDisplayDecimals']}"),
            min_base_amount_increment=Decimal(f"1e-{market_info['quoteDisplayDecimals']}"),
            min_notional_size=Decimal(market_info["minTradeAmount"]) * quote_scaler,
            min_order_value=Decimal(market_info["minTradeAmount"]) * quote_scaler,
        )

    def _get_trading_pair_from_market_info(self, market_info: Dict[str, Any]) -> str:
        base = market_info["baseSymbol"].upper()
        quote = market_info["quoteSymbol"].upper()
        trading_pair = combine_to_hb_trading_pair(base=base, quote=quote)
        return trading_pair

    def _get_exchange_base_quote_tokens_from_market_info(self, market_info: Dict[str, Any]) -> Tuple[str, str]:
        base = market_info["baseSymbol"]
        quote = market_info["quoteSymbol"]
        return base, quote

    def _get_exchange_trading_pair_from_market_info(self, market_info: Dict[str, Any]) -> str:
        exchange_trading_pair = f"{market_info['baseSymbol']}/{market_info['quoteSymbol']}"
        return exchange_trading_pair

    def _get_last_trade_price_from_ticker_data(self, ticker_data: List[Dict[str, Any]]) -> Decimal:
        raise NotImplementedError

    def _get_maker_taker_exchange_fee_rates_from_market_info(
        self, market_info: Dict[str, Any]
    ) -> MakerTakerExchangeFeeRates:
        rate_scaler = Decimal(f"1e-{market_info['quoteDisplayDecimals']}")
        maker_taker_exchange_fee_rates = MakerTakerExchangeFeeRates(
            maker=Decimal(str(market_info["makerRate"])) * rate_scaler / Decimal("100"),
            taker=Decimal(str(market_info["takerRate"])) * rate_scaler / Decimal("100"),
            maker_flat_fees=[],
            taker_flat_fees=[],
        )
        return maker_taker_exchange_fee_rates

    @staticmethod
    def _timestamp_to_dexalot_timestamp(timestamp: float) -> str:
        dt_str = str(pd.Timestamp.utcfromtimestamp(ts=timestamp).tz_localize("UTC"))
        return dt_str

    @staticmethod
    def _dexalot_timestamp_to_timestamp(period_str: str) -> float:
        ts = pd.Timestamp(period_str).timestamp()
        return ts

    # REST methods

    async def _api_get(self, *args, **kwargs) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        kwargs["method"] = RESTMethod.GET
        return await self._api_request(*args, **kwargs)

    async def _api_post(self, *args, **kwargs) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        kwargs["method"] = RESTMethod.POST
        return await self._api_request(*args, **kwargs)

    async def _api_put(self, *args, **kwargs) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        kwargs["method"] = RESTMethod.PUT
        return await self._api_request(*args, **kwargs)

    async def _api_delete(self, *args, **kwargs) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        kwargs["method"] = RESTMethod.DELETE
        return await self._api_request(*args, **kwargs)

    async def _api_request(
        self,
        path_url,
        throttler_limit_id: str,
        is_auth_required: bool = False,
        method: RESTMethod = RESTMethod.GET,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        rest_assistant = await self._api_factory.get_rest_assistant()
        url = CONSTANTS.BASE_PATH_URL[self._network] + path_url

        request_result = await rest_assistant.execute_request(
            url=url,
            params=params,
            data=data,
            method=method,
            is_auth_required=is_auth_required,
            throttler_limit_id=throttler_limit_id,
        )

        return request_result

    async def _listen_to_streams(self):
        while True:
            try:
                ws_assistant = await self._connected_websocket_assistant()
                await self._subscribe_to_pairs(ws_assistant)
                await self._process_websocket_messages(ws_assistant)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error while listening to user stream. Reconnecting...")
                await self._sleep(1.0)

    async def _connected_websocket_assistant(self) -> WSAssistant:
        auth_response = await self._api_get(
            path_url=CONSTANTS.WS_AUTH_PATH,
            throttler_limit_id=CONSTANTS.WS_AUTH_RATE_LIMIT_ID,
            is_auth_required=True,
        )
        token = auth_response["token"]
        ws_url = f"{CONSTANTS.WS_PATH_URL[self._network]}?wstoken={token}"
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=ws_url, ping_timeout=CONSTANTS.HEARTBEAT_TIME_INTERVAL)
        return ws

    async def _subscribe_to_pairs(self, ws_assistant: WSAssistant):
        trading_pairs_map = await self.get_symbol_map()
        for trading_pair in self._trading_pairs:
            exchange_trading_pair = trading_pairs_map.inverse[trading_pair]
            market_info = self._markets_info[trading_pair]
            pair_sub_request = {
                "data": exchange_trading_pair,
                "pair": exchange_trading_pair,
                "type": "subscribe",
                "decimal": market_info["quoteDisplayDecimals"],
            }
            request = WSJSONRequest(payload=pair_sub_request, throttler_limit_id=CONSTANTS.WS_SUB_RATE_LIMIT_ID)
            await ws_assistant.send(request)

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant):
        async for ws_response in websocket_assistant.iter_messages():
            data = ws_response.data
            await self._process_event_message(event_message=data)

    async def _process_event_message(self, event_message: Dict[str, Any]):
        if event_message["type"] == "lastTrade":
            await self._process_last_traded_price(price_message=event_message)
        elif event_message["type"] == "orderBooks":
            await self._process_snapshot_message(snapshot_message=event_message)

    async def _process_last_traded_price(self, price_message: Dict[str, Any]):
        data = price_message["data"]
        last_price_message = data[-1]
        price = Decimal(last_price_message["price"])
        trading_pairs_map = await self.get_symbol_map()
        exchange_pair = price_message["pair"]
        trading_pair = trading_pairs_map[exchange_pair]
        self._last_traded_price_map[trading_pair] = price

    async def _process_snapshot_message(self, snapshot_message: Dict[str, Any]):
        data = snapshot_message["data"]
        trading_pairs_map = await self.get_symbol_map()
        exchange_trading_pair = snapshot_message["pair"]
        trading_pair = trading_pairs_map[exchange_trading_pair]
        market_info = self._markets_info[trading_pair]
        price_scaler = Decimal(f"1e-{market_info['quoteDecimals']}")
        size_scaler = Decimal(f"1e-{market_info['baseDecimals']}")

        bid_price_strings = data["buyBook"][0]["prices"].split(",")
        bid_size_strings = data["buyBook"][0]["quantities"].split(",")
        bids = [
            (Decimal(price) * price_scaler, Decimal(size) * size_scaler)
            for price, size in zip(bid_price_strings, bid_size_strings)
        ]

        ask_price_strings = data["sellBook"][0]["prices"].split(",")
        ask_size_strings = data["sellBook"][0]["quantities"].split(",")
        asks = [
            (Decimal(price) * price_scaler, Decimal(size) * size_scaler)
            for price, size in zip(ask_price_strings, ask_size_strings)
        ]

        timestamp = self._time()
        update_id = self._snapshots_id_nonce_provider.get_tracking_nonce(timestamp=timestamp)
        snapshot_msg = OrderBookMessage(
            message_type=OrderBookMessageType.SNAPSHOT,
            content={
                "trading_pair": trading_pair,
                "update_id": update_id,
                "bids": bids,
                "asks": asks,
            },
            timestamp=timestamp,
        )
        self._publisher.trigger_event(event_tag=OrderBookDataSourceEvent.SNAPSHOT_EVENT, message=snapshot_msg)
