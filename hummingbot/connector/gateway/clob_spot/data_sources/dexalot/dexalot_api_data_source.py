import asyncio
from collections import defaultdict
from decimal import Decimal
from itertools import chain
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
from hummingbot.connector.gateway.common_types import CancelOrderResult, PlaceOrderResult
from hummingbot.connector.gateway.gateway_in_flight_order import GatewayInFlightOrder
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair, get_new_numeric_client_order_id
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.common import OrderType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.trade_fee import MakerTakerExchangeFeeRates, TokenAmount, TradeFeeBase, TradeFeeSchema
from hummingbot.core.event.events import MarketEvent, OrderBookDataSourceEvent
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
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
        self._last_traded_price_map = defaultdict(lambda: Decimal("0"))
        self._snapshots_id_nonce_provider = NonceCreator.for_milliseconds()

    @property
    def connector_name(self) -> str:
        return CONNECTOR_NAME

    @property
    def events_are_streamed(self) -> bool:
        return False

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
        self._gateway_order_tracker.lost_order_count_limit = CONSTANTS.LOST_ORDER_COUNT_LIMIT
        await super().start()

    async def stop(self):
        await super().stop()
        self._stream_listener is not None and self._stream_listener.cancel()

    def get_supported_order_types(self) -> List[OrderType]:
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER]

    async def place_order(
        self, order: GatewayInFlightOrder, **kwargs
    ) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        place_order_results = await super().batch_order_create(orders_to_create=[order])
        result = place_order_results[0]
        if result.exception is not None:
            raise result.exception
        self.logger().debug(
            f"Order creation transaction hash for {order.client_order_id}:"
            f" {result.misc_updates['creation_transaction_hash']}"
        )
        return result.exchange_order_id, result.misc_updates

    async def batch_order_create(self, orders_to_create: List[GatewayInFlightOrder]) -> List[PlaceOrderResult]:
        super_batch_order_create = super().batch_order_create  # https://stackoverflow.com/a/31895448/6793798
        tasks = [
            super_batch_order_create(
                orders_to_create=orders_to_create[i: i + CONSTANTS.MAX_ORDER_CREATIONS_PER_BATCH]
            )
            for i in range(0, len(orders_to_create), CONSTANTS.MAX_ORDER_CREATIONS_PER_BATCH)
        ]
        results = await safe_gather(*tasks)
        flattened_results = list(chain(*results))
        self.logger().debug(
            f"Order creation transaction hashes for {', '.join([o.client_order_id for o in orders_to_create])}"
        )
        for result in flattened_results:
            self.logger().debug(f"Transaction hash: {result.misc_updates['creation_transaction_hash']}")
        return flattened_results

    async def cancel_order(self, order: GatewayInFlightOrder) -> Tuple[bool, Optional[Dict[str, Any]]]:
        cancel_order_results = await super().batch_order_cancel(orders_to_cancel=[order])
        self.logger().debug(
            f"cancel order transaction hash for {order.client_order_id}:"
            f" {cancel_order_results[0].misc_updates['cancelation_transaction_hash']}"
        )
        misc_updates = {}
        canceled = False
        if len(cancel_order_results) != 0:
            result = cancel_order_results[0]
            if result.exception is not None:
                raise result.exception
            misc_updates = result.misc_updates
            canceled = True
        return canceled, misc_updates

    async def batch_order_cancel(self, orders_to_cancel: List[GatewayInFlightOrder]) -> List[CancelOrderResult]:
        super_batch_order_cancel = super().batch_order_cancel  # https://stackoverflow.com/a/31895448/6793798
        tasks = [
            super_batch_order_cancel(
                orders_to_cancel=orders_to_cancel[i: i + CONSTANTS.MAX_ORDER_CANCELATIONS_PER_BATCH]
            )
            for i in range(0, len(orders_to_cancel), CONSTANTS.MAX_ORDER_CANCELATIONS_PER_BATCH)
        ]
        results = await safe_gather(*tasks)
        flattened_results = list(chain(*results))
        self.logger().debug(
            f"Order cancelation transaction hashes for {', '.join([o.client_order_id for o in orders_to_cancel])}"
        )
        for result in flattened_results:
            self.logger().debug(f"Transaction hash: {result.misc_updates['cancelation_transaction_hash']}")
        return flattened_results

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

    async def get_order_status_update(self, in_flight_order: GatewayInFlightOrder) -> OrderUpdate:
        await in_flight_order.get_creation_transaction_hash()
        status_update = None

        if in_flight_order.exchange_order_id is None:
            status_update = await self._get_order_status_update_from_transaction_status(in_flight_order=in_flight_order)
            if status_update is not None:
                in_flight_order.exchange_order_id = status_update.exchange_order_id
                self._publisher.trigger_event(event_tag=MarketEvent.OrderUpdate, message=status_update)

        if (
            in_flight_order.exchange_order_id is not None
            or (
                status_update is not None
                and status_update.new_state not in [OrderState.FAILED, OrderState.PENDING_CREATE]
            )
        ):
            status_update = await self._get_order_status_update_with_order_id(in_flight_order=in_flight_order)
            self._publisher.trigger_event(event_tag=MarketEvent.OrderUpdate, message=status_update)

        if status_update is None:
            raise ValueError(f"No update found for order {in_flight_order.client_order_id}.")

        return status_update

    async def get_all_order_fills(self, in_flight_order: GatewayInFlightOrder) -> List[TradeUpdate]:
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

    def is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return (
            str(status_update_exception).endswith("not found")  # transaction not found
            or str(status_update_exception).startswith("No update found for order")  # status update not found
        )

    def is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return False

    async def _update_snapshots_loop(self):
        pass  # Dexalot streams the snapshots via websocket

    async def _get_order_status_update_from_transaction_status(
        self, in_flight_order: GatewayInFlightOrder
    ) -> Optional[OrderUpdate]:
        """
        Transaction not yet listed
        {
          "network": "dexalot",
          "currentBlock": 1005813,
          "timestamp": 1678431621633,
          "txHash": "0xadaef9c4540192e45c991ffe6f12cc86be9c07b80b43487e5778d95c964405c7",  # noqa: documentation
          "txBlock": -1,
          "txStatus": -1,
          "txData": null,
          "txReceipt": null
        }

        ======================

        Transaction failed (abbreviated)
        {
          "timestamp": 1678431839032,
          "txHash": "0x34494d6c88e36415bbf3d1f44e648ed11bd952380743395f950c242cded147d1",  # noqa: documentation
          "txStatus": 1,
          "txData": {
            ...
          },
          "txReceipt": {
            "status": 0,
          }
        }

        ======================

        Transaction success (abbreviated)
        {
          "txStatus": 1,
          "timestamp": 1678440295386,
          "txHash": "0x6aca797aa30636c3285c5ecaee76fe85a9ee2ac60d74af64b8d6660a6f4f0f27",  # noqa: documentation
          "txData": {
            ...
          },
          "txReceipt": {
            "transactionHash": "...",
            "logs": [
              {                                                   # SUCCESS
                "name": "OrderStatusChanged",
                "events": [
                  { ... },
                  { ... },
                  { ... },
                  {
                    "name": "orderId",
                    "type": "bytes32",
                    "value": "0x0000000000000000000000000000000000000000000000000000000063d84143"  # noqa: documentation
                  },
                  {
                    "name": "clientOrderId",
                    "type": "bytes32",
                    "value": "0xb71309b1a16b7903ffc817f256d1f4d42602d402bd81001feb29fd067e69013b"  # noqa: documentation
                  },
                  {
                    "name": "price",
                    "type": "uint256",
                    "value": "15000000"
                  },
                  { ... },
                  {
                    "name": "quantity",
                    "type": "uint256",
                    "value": "500000000000000000"
                  },
                  { ... },
                  { ... },
                  { ... },
                  {
                    "name": "status",
                    "type": "uint8",
                    "value": "0"
                  },
                  { ... },
                  { ... },
                  { ... },
                ],
                "address": "0x09383137C1eEe3E1A8bc781228E4199f6b4A9bbf"
              },
               {                                                   # FAILED
                "name": "OrderStatusChanged",
                "events": [
                  { ... },
                  { ... },
                  { ... },
                  {
                    "name": "orderId",
                    "type": "bytes32",
                    "value": "0x0000000000000000000000000000000000000000000000000000000000000000"  # noqa: documentation
                  },
                  {
                    "name": "clientOrderId",
                    "type": "bytes32",
                    "value": "0x936f0db5ba15ceaf9d6ee8fb6c1aeca01e67dfb3d061680a4ac3ce8ccb153072"  # noqa: documentation
                  },
                  {
                    "name": "price",
                    "type": "uint256",
                    "value": "15000000"
                  },
                  { ... },
                  {
                    "name": "quantity",
                    "type": "uint256",
                    "value": "0"
                  },
                  { ... },
                  { ... },
                  { ... },
                  {
                    "name": "status",
                    "type": "uint8",
                    "value": "1"
                  },
                  { ... },
                  { ... },
                  { ... },
                ],
               },
            ],
            "status": 1,
          },
        }
        """
        transaction_data = await self._get_gateway_instance().get_transaction_status(
            chain=self._chain,
            network=self._network,
            transaction_hash=in_flight_order.creation_transaction_hash,
            connector="dexalot",
        )
        if (
            transaction_data is not None
            and transaction_data["txStatus"] == 1
            and transaction_data.get("txReceipt", {}).get("status") == 1
        ):
            order_data = self._find_order_data_from_transaction_data(
                transaction_data=transaction_data, in_flight_order=in_flight_order
            )
            new_dexalot_numeric_state_event = next(filter(lambda event: event["name"] == "status", order_data))
            new_dexalot_numeric_state = new_dexalot_numeric_state_event["value"]
            exchange_order_id_event = next(filter(lambda event: event["name"] == "orderId", order_data))
            exchange_order_id = exchange_order_id_event["value"]
            timestamp = transaction_data["timestamp"] * 1e-3
            order_update = OrderUpdate(
                trading_pair=in_flight_order.trading_pair,
                update_timestamp=timestamp,
                new_state=DEXALOT_TO_HB_NUMERIC_STATUS_MAP[int(new_dexalot_numeric_state)],
                client_order_id=in_flight_order.client_order_id,
                exchange_order_id=exchange_order_id,
            )
        elif (
            transaction_data is not None
            and (
                transaction_data["txStatus"] == -1
                or transaction_data.get("txReceipt", {}).get("status") == 0
            )
        ):
            order_update = None  # transaction data not found
        else:  # transaction is still being processed
            order_update = OrderUpdate(
                trading_pair=in_flight_order.trading_pair,
                update_timestamp=self._time(),
                new_state=OrderState.PENDING_CREATE,
                client_order_id=in_flight_order.client_order_id,
            )

        return order_update

    @staticmethod
    def _find_order_data_from_transaction_data(
        transaction_data: Dict[str, Any], in_flight_order: GatewayInFlightOrder
    ) -> List[Dict[str, str]]:
        log_items = transaction_data["txReceipt"]["logs"]

        def log_items_filter(log_event_: Dict[str, Any]) -> bool:
            target_hit = False
            if log_event_["name"] == "OrderStatusChanged":
                client_order_id_event = next(
                    filter(
                        lambda event: event["name"] == "clientOrderId",
                        log_event_["events"],
                    ),
                )
                client_order_id = client_order_id_event["value"]
                if client_order_id == in_flight_order.client_order_id:
                    target_hit = True
            return target_hit

        log_item = next(filter(log_items_filter, log_items))
        log_event = log_item["events"]

        return log_event

    async def _get_order_status_update_with_order_id(self, in_flight_order: InFlightOrder) -> Optional[OrderUpdate]:
        url = f"{CONSTANTS.ORDERS_PATH}/{in_flight_order.exchange_order_id}"

        try:
            resp = await self._api_get(
                path_url=url, throttler_limit_id=CONSTANTS.ORDERS_RATE_LIMIT_ID, is_auth_required=True
            )
        except OSError as e:
            if "HTTP status is 404" in str(e):
                raise ValueError(f"No update found for order {in_flight_order.exchange_order_id}.")
            raise e

        if resp.get("message") == "":
            raise ValueError(f"No update found for order {in_flight_order.exchange_order_id}.")
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
            min_order_size=Decimal(f"1e-{market_info['baseDisplayDecimals']}"),
            min_price_increment=Decimal(f"1e-{market_info['quoteDisplayDecimals']}"),
            min_quote_amount_increment=Decimal(f"1e-{market_info['quoteDisplayDecimals']}"),
            min_base_amount_increment=Decimal(f"1e-{market_info['baseDisplayDecimals']}"),
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
        maker_taker_exchange_fee_rates = MakerTakerExchangeFeeRates(
            maker=Decimal(str(market_info["makerRate"])),
            taker=Decimal(str(market_info["takerRate"])),
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
        ws_url = CONSTANTS.WS_PATH_URL[self._network]
        if self._api_key is not None and len(self._api_key) > 0:
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
