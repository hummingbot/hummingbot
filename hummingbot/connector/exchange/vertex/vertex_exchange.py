import asyncio
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple
import time

from bidict import bidict

from hummingbot.connector.exchange.vertex import (
    vertex_constants as CONSTANTS,
    vertex_utils as utils,
    vertex_web_utils as web_utils,
    vertex_eip712_structs as vertex_eip712_structs
)
from hummingbot.core.data_type.in_flight_order import OrderState
from hummingbot.connector.exchange.vertex.vertex_api_order_book_data_source import VertexAPIOrderBookDataSource
from hummingbot.connector.exchange.vertex.vertex_api_user_stream_data_source import VertexAPIUserStreamDataSource
from hummingbot.connector.exchange.vertex.vertex_auth import VertexAuth
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.constants import s_decimal_0, s_decimal_NaN
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter

s_logger = None
s_decimal_NaN = Decimal("nan")


class VertexExchange(ExchangePyBase):
    web_utils = web_utils

    def __init__(
        self,
        client_config_map: "ClientConfigAdapter",
        vertex_arbitrum_address: str,
        vertex_arbitrum_private_key: str,
        vertex_spot_leverage: bool = False,
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        self.sender_address = utils.convert_address_to_sender(vertex_arbitrum_address)
        self.private_key = vertex_arbitrum_private_key
        self._use_spot_leverage = vertex_spot_leverage
        # NOTE: Vertex doesn't submit all balance updates, instead it only updates the product on position change (not cancel)
        self.real_time_balance_update = False
        self._domain = domain
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._chain_id = CONSTANTS.CHAIN_IDS[self.domain]
        super().__init__(client_config_map)

    @staticmethod
    def vertex_order_type(order_type: OrderType) -> str:
        return order_type.name.upper()

    @staticmethod
    def to_hb_order_type(vertex_type: str) -> OrderType:
        return OrderType[vertex_type]

    @property
    def authenticator(self):
        return VertexAuth(vertex_arbitrum_address=self.sender_address, vertex_arbitrum_private_key=self.private_key)

    @property
    def name(self) -> str:
        return self._domain

    @property
    def rate_limits_rules(self):
        return CONSTANTS.RATE_LIMITS

    @property
    def domain(self):
        return self._domain

    @property
    def client_order_id_max_length(self):
        return CONSTANTS.MAX_ORDER_ID_LEN

    @property
    def client_order_id_prefix(self):
        return CONSTANTS.HBOT_BROKER_ID

    @property
    def trading_rules_request_path(self):
        return CONSTANTS.QUERY_PATH_URL + "?type=" + CONSTANTS.ALL_PRODUCTS_REQUEST_TYPE

    @property
    def trading_pairs_request_path(self):
        return CONSTANTS.QUERY_PATH_URL + "?type=" + CONSTANTS.ALL_PRODUCTS_REQUEST_TYPE

    @property
    def check_network_request_path(self):
        return CONSTANTS.QUERY_PATH_URL + "?type=" + CONSTANTS.STATUS_REQUEST_TYPE

    @property
    def trading_pairs(self):
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return True

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    def supported_order_types(self):
        return [OrderType.MARKET, OrderType.LIMIT, OrderType.LIMIT_MAKER]

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception) -> bool:
        # TODO: implement this method correctly for the connector
        # The default implementation was added when the functionality to detect not found orders was introduced in the
        # ExchangePyBase class. Also fix the unit test test_lost_order_removed_if_not_found_during_order_status_update
        # when replacing the dummy implementation
        return False

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        # TODO: implement this method correctly for the connector
        # The default implementation was added when the functionality to detect not found orders was introduced in the
        # ExchangePyBase class. Also fix the unit test test_lost_order_removed_if_not_found_during_order_status_update
        # when replacing the dummy implementation
        return False

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        # TODO: implement this method correctly for the connector
        # The default implementation was added when the functionality to detect not found orders was introduced in the
        # ExchangePyBase class. Also fix the unit test test_lost_order_removed_if_not_found_during_order_status_update
        # when replacing the dummy implementation
        return False

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(throttler=self._throttler, auth=self._auth)

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return VertexAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            domain=self.domain,
            api_factory=self._web_assistants_factory,
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return VertexAPIUserStreamDataSource(
            auth=self._auth,
            trading_pairs=self._trading_pairs,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    def _get_fee(
        self,
        base_currency: str,
        quote_currency: str,
        order_type: OrderType,
        order_side: TradeType,
        amount: Decimal,
        price: Decimal = s_decimal_NaN,
        is_maker: Optional[bool] = None,
    ) -> TradeFeeBase:
        trading_pair = f"{base_currency}-{quote_currency}"
        is_maker = is_maker or False
        if trading_pair not in self._trading_fees:
            fee = build_trade_fee(
                exchange=self.name,
                is_maker=is_maker,
                order_side=order_side,
                order_type=order_type,
                amount=amount,
                price=price,
                base_currency=base_currency,
                quote_currency=quote_currency,
            )
        else:
            fee_data = self._trading_fees[trading_pair]
            if is_maker:
                fee_value = fee_data["maker"]
            else:
                fee_value =fee_data["taker"]
            fee = AddedToCostTradeFee(percent=fee_value)
        return fee

    async def _place_order(
        self,
        order_id: str,
        trading_pair: str,
        amount: Decimal,
        trade_type: TradeType,
        order_type: OrderType,
        price: Decimal,
        **kwargs,
    ) -> Tuple[str, float]:
        # NOTE: A positive amount indicates a buy, and a negative amount indicates a sell.
        if trade_type == TradeType.SELL:
            amount = -amount

        trading_rules = self.trading_rules[trading_pair]
        amount_str = utils.convert_to_x18(amount, trading_rules.min_base_amount_increment)
        price_str = utils.convert_to_x18(price, trading_rules.min_price_increment)

        if order_type and order_type == OrderType.LIMIT_MAKER:
            _order_type = CONSTANTS.TIME_IN_FORCE_POSTONLY
        else:
            _order_type = CONSTANTS.TIME_IN_FORCE_GTC

        expiration = utils.generate_expiration(time.time(), order_type=_order_type)
        product_id = utils.trading_pair_to_product_id(trading_pair)
        nonce = utils.generate_nonce(time.time())
        contract = CONSTANTS.PRODUCTS[product_id][self.domain]

        sender = utils.hex_to_bytes32(self.sender_address)

        order = vertex_eip712_structs.Order(
            sender=sender, priceX18=int(price_str), amount=int(amount_str), expiration=int(expiration), nonce=nonce
        )

        signature, digest = self.authenticator.sign_payload(order, contract, self._chain_id)

        place_order = {
            "place_order": {
                "product_id": product_id,
                "order": {
                    "sender": self.sender_address,
                    "priceX18": price_str,
                    "amount": amount_str,
                    "expiration": expiration,
                    "nonce": str(nonce),
                },
                "signature": signature,
                "spot_leverage": self._use_spot_leverage,
            }
        }

        try:
            # NOTE: There are two differen't limits depending on the use of leverage
            limit_id = CONSTANTS.PLACE_ORDER_METHOD_NO_LEVERAGE
            if self._use_spot_leverage:
                limit_id = CONSTANTS.PLACE_ORDER_METHOD

            order_result = await self._api_post(path_url=CONSTANTS.POST_PATH_URL, data=place_order, limit_id=limit_id)
            if order_result.get("status") == "failure":
                raise Exception(f"Failed to create order {order_result}")

        except IOError as e:
            raise

        o_id = digest
        transact_time = int(time.time())
        return o_id, transact_time

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        sender = utils.hex_to_bytes32(self.sender_address)
        product_id = utils.trading_pair_to_product_id(tracked_order.trading_pair)
        nonce = utils.generate_nonce(time.time())
        endpoint_contract = CONSTANTS.CONTRACTS[self.domain]

        if tracked_order.exchange_order_id:
            order_id = tracked_order.exchange_order_id
        else:
            order_id = tracked_order.client_order_id

        order_id_bytes = utils.hex_to_bytes32(order_id)

        cancel = vertex_eip712_structs.Cancellation(
            sender=sender, productIds=[int(product_id)], digests=[order_id_bytes], nonce=nonce
        )
        signature, digest = self.authenticator.sign_payload(cancel, endpoint_contract, self._chain_id)

        cancel_orders = {
            "cancel_orders": {
                "tx": {
                    "sender": self.sender_address,
                    "productIds": [product_id],
                    "digests": [order_id],
                    "nonce": str(nonce),
                },
                "signature": signature,
            }
        }

        cancel_result = await self._api_post(path_url=CONSTANTS.POST_PATH_URL, data=cancel_orders, limit_id=CONSTANTS.CANCEL_ORDERS_METHOD)
        if cancel_result.get("status") == "failure":
            if cancel_result.get("error_code") and cancel_result["error_code"] == 2020:
                # NOTE: This is the most elegant handling outside of passing through restrictive lost order limit to 0
                self._order_tracker._trigger_cancelled_event(tracked_order)
                self._order_tracker._trigger_order_completion(tracked_order)
                self.logger().warning(f"Marked order canceled as the exchange holds no record: {order_id}")
                return True
  
        if isinstance(cancel_result, dict) and cancel_result["status"] == "success":
            return True
        return False

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        """
        Example:
             "spot_products": [
                {
                    "product_id": 1,
                    "oracle_price_x18": "25741837349502615455138",
                    "risk": {
                        "long_weight_initial_x18": "900000000000000000",
                        "short_weight_initial_x18": "1100000000000000000",
                        "long_weight_maintenance_x18": "950000000000000000",
                        "short_weight_maintenance_x18": "1050000000000000000",
                        "large_position_penalty_x18": "0"
                    },
                    "config": {
                        "token": "0x5cc7c91690b2cbaee19a513473d73403e13fb431",
                        "interest_inflection_util_x18": "800000000000000000",
                        "interest_floor_x18": "10000000000000000",
                        "interest_small_cap_x18": "40000000000000000",
                        "interest_large_cap_x18": "1000000000000000000"
                    },
                    "state": {
                        "cumulative_deposits_multiplier_x18": "1001477610660740732",
                        "cumulative_borrows_multiplier_x18": "1005360996332066877",
                        "total_deposits_normalized": "336131479261252096179100",
                        "total_borrows_normalized": "106663044719707335242158"
                    },
                    "lp_state": {
                        "supply": "62623749006749305149587800",
                        "quote": {
                            "amount": "90948379767723832838627925",
                            "last_cumulative_multiplier_x18": "1000000008171891309"
                        },
                        "base": {
                            "amount": "3549779755052134826620",
                            "last_cumulative_multiplier_x18": "1001477610660740732"
                        }
                    },
                    "book_info": {
                        "size_increment": "1000000000000000",
                        "price_increment_x18": "1000000000000000000",
                        "min_size": "10000000000000000",
                        "collected_fees": "41050488980466524595135",
                        "lp_spread_x18": "3000000000000000"
                    }
                },
            ]
        """
        trading_pair_rules = exchange_info_dict.get("data", [])
        if len(trading_pair_rules) > 0:
            trading_pair_rules = trading_pair_rules["spot_products"]
        retval = []
        for rule in trading_pair_rules:
            try:
                if rule["product_id"] == 0:
                    # NOTE: USDC product doesn't have a market
                    continue
                trading_pair = utils.product_id_to_trading_pair(rule["product_id"])
                rule_set = rule["book_info"]
                min_order_size = utils.convert_from_x18(rule_set.get("min_size"))
                min_price_increment = utils.convert_from_x18(rule_set.get("price_increment_x18"))
                min_base_amount_increment = utils.convert_from_x18(rule_set.get("size_increment"))
                retval.append(
                    TradingRule(
                        trading_pair,
                        min_order_size=Decimal(min_order_size),
                        min_price_increment=Decimal(min_price_increment),
                        min_base_amount_increment=Decimal(min_base_amount_increment),
                        min_notional_size=Decimal("0.01"), # NOTE: added to ensure proper functioning with strategies.
                    )
                )

            except Exception:
                self.logger().exception(f"Error parsing the trading pair rule {rule.get('name')}. Skipping.")
        return retval

    async def _update_trading_fees(self):
        """
        Update fees information from the exchange
        """
        """
        {
        "status": "success",
        "data": {
            "taker_fee_rates_x18": [
            "0",
            "300000000000000",
            "200000000000000",
            "300000000000000",
            "200000000000000"
            ],
            "maker_fee_rates_x18": [
            "0",
            "0",
            "0",
            "0",
            "0"
            ],
            "liquidation_sequencer_fee": "250000000000000000",
            "health_check_sequencer_fee": "100000000000000000",
            "taker_sequencer_fee": "25000000000000000",
            "withdraw_sequencer_fees": [
            "10000000000000000",
            "40000000000000",
            "0",
            "600000000000000",
            "0"
            ]
        }
        }
        """
        try:
            fee_rates = await self._get_fee_rates()
            taker_fees = {idx: fee_rate for idx, fee_rate in enumerate(fee_rates["taker_fee_rates_x18"])}
            maker_fees = {idx: fee_rate for idx, fee_rate in enumerate(fee_rates["maker_fee_rates_x18"])}
            # NOTE: This builds our fee rates based on indexed product_id
            for trading_pair in self._trading_pairs:
                product_id = utils.trading_pair_to_product_id(trading_pair=trading_pair)
                self._trading_fees[trading_pair] = {
                    "maker": Decimal(utils.convert_from_x18(maker_fees[product_id])),
                    "taker": Decimal(utils.convert_from_x18(taker_fees[product_id])),
                }
        except Exception:
            # NOTE: If failure to fetch, build default fees
            for trading_pair in self._trading_pairs:
                self._trading_fees[trading_pair] = {
                    "maker": utils.DEFAULT_FEES.maker_percent_fee_decimal,
                    "taker": utils.DEFAULT_FEES.taker_percent_fee_decimal,
                }

    async def _user_stream_event_listener(self):
        """
        This functions runs in background continuously processing the events received from the exchange by the user
        stream data source. It keeps reading events from the queue until the task is interrupted.
        The events received are fill and position change events.
        """

        async for event_message in self._iter_user_event_queue():
            try:
                event_type = event_message.get("type")

                if event_type == CONSTANTS.FILL_EVENT_TYPE:
                    exchange_order_id = event_message.get("order_digest")
                    execution_type = (
                        OrderState.PARTIALLY_FILLED
                        if Decimal(utils.convert_from_x18(event_message["remaining_qty"])) > Decimal("0.0")
                        else OrderState.FILLED
                    )
                    tracked_order = self._order_tracker.fetch_order(exchange_order_id=exchange_order_id)
                    if tracked_order is not None:
                        if execution_type in [OrderState.PARTIALLY_FILLED, OrderState.FILLED]:
                            amount = abs(Decimal(utils.convert_from_x18(event_message["filled_qty"])))
                            price = Decimal(utils.convert_from_x18(event_message["price"]))
                            fee_rate = self._trading_fees[tracked_order.trading_pair]["maker"]
                            if event_message["is_taker"]:
                                fee_rate = self._trading_fees[tracked_order.trading_pair]["taker"]
                            fee = TradeFeeBase.new_spot_fee(
                                fee_schema=self.trade_fee_schema(),
                                trade_type=tracked_order.trade_type,
                                percent=fee_rate,
                                percent_token="USDC", # NOTE: All fees are denominated in USDC
                            )
                            trade_update = TradeUpdate(
                                trade_id=str(event_message["timestamp"]),
                                client_order_id=tracked_order.client_order_id,
                                exchange_order_id=str(exchange_order_id),
                                trading_pair=tracked_order.trading_pair,
                                fee=fee,
                                fill_base_amount=amount,
                                fill_quote_amount=amount * price,
                                fill_price=price,
                                fill_timestamp=int(event_message["timestamp"]) * 1e-9,
                            )
                            self._order_tracker.process_trade_update(trade_update)

                        order_update = OrderUpdate(
                            trading_pair=tracked_order.trading_pair,
                            update_timestamp=int(event_message["timestamp"]) * 1e-9,
                            new_state=execution_type,
                            client_order_id=tracked_order.client_order_id,
                            exchange_order_id=str(exchange_order_id),
                        )

                        self._order_tracker.process_order_update(order_update=order_update)

                elif event_type == CONSTANTS.POSITION_CHANGE_EVENT_TYPE:
                    await self._update_balances()
                    # NOTE: Without balance update, we just call the API endpoint to update all balances.
                    product_id = event_message["product_id"]
                    amount = utils.convert_from_x18(event_message["amount"])
                    asset_name = CONSTANTS.PRODUCTS[product_id]["symbol"]
                    free_balance = Decimal(amount)
                    total_balance = Decimal(amount)
                    self._account_available_balances[asset_name] = free_balance
                    self._account_balances[asset_name] = total_balance
                    

            except asyncio.CancelledError:
                self.logger().error(f"An Asyncio.CancelledError occurs when process message: {event_message}.", exc_info=True)
                raise
            except Exception:
                self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
                await self._sleep(5.0)

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        trade_updates = []
        if order.exchange_order_id is not None:
            exchange_order_id = order.exchange_order_id
            trading_pair = order.trading_pair
            product_id = utils.trading_pair_to_product_id(order.trading_pair)

            matches_response = await self._api_post(
                path_url=CONSTANTS.INDEXER_PATH_URL,
                data={
                    "matches": {
                        "product_ids": [product_id],
                        "subaccount": self.sender_address
                    }
                },
                limit_id=CONSTANTS.INDEXER_PATH_URL,
            )

            matches_data = matches_response.get("matches", [])
            if matches_data is not None:
                for trade in matches_data:
                    # NOTE: Vertex returns all orders and matches.
                    if trade["digest"] != order.exchange_order_id:
                        continue
                   
                    exchange_order_id = str(trade["digest"])
                    # NOTE: Matches can be composed of multiple trade transactions.
                    # https://vertex-protocol.gitbook.io/docs/developer-resources/api/indexer-api/matches
                    submission_idx = str(trade["submission_idx"])
                    trade_fee = utils.convert_from_x18(trade["fee"])
                    trade_amount = utils.convert_from_x18(trade["order"]["amount"])
                    fee = TradeFeeBase.new_spot_fee(
                        fee_schema=self.trade_fee_schema(),
                        trade_type=TradeType.SELL if Decimal(trade_amount) < s_decimal_0 else TradeType.BUY,
                        flat_fees=[TokenAmount(amount=Decimal(trade_fee), token="USDC")],
                    )
                    fill_base_amount = utils.convert_from_x18(trade["base_filled"])
                    converted_price = utils.convert_from_x18(trade["order"]["priceX18"])
                    fill_quote_amount = utils.convert_from_x18(trade["base_filled"])
                    # NOTE: Matches can be composed of multiple trade transactions..
                    matches_transactions_data = matches_response.get("txs", [])
                    trade_timestamp = int(time.time())
                    for transaction in matches_transactions_data:
                        if str(transaction["submission_idx"]) != submission_idx:
                            continue
                        trade_timestamp = transaction["timestamp"]
                        break
                    trade_update = TradeUpdate(
                        trade_id=submission_idx,
                        client_order_id=order.client_order_id,
                        exchange_order_id=exchange_order_id,
                        trading_pair=trading_pair,
                        fee=fee,
                        fill_base_amount=abs(Decimal(fill_base_amount)),
                        fill_quote_amount=Decimal(converted_price) * abs(Decimal(fill_quote_amount)),
                        fill_price=Decimal(converted_price),
                        fill_timestamp=int(trade_timestamp),
                    )
                    trade_updates.append(trade_update)

        return trade_updates

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        """
        This requests the order from the live squencer, then if it cannot locate it, it attempts to locate it with the indexer
        """
        live_order = True
        try:
            order_request_response = await self._api_get(
                path_url=CONSTANTS.QUERY_PATH_URL,
                params={
                    "type": CONSTANTS.ORDER_REQUEST_TYPE,
                    "product_id": utils.trading_pair_to_product_id(tracked_order.trading_pair),
                    "digest": tracked_order.exchange_order_id,
                },
                limit_id=CONSTANTS.ORDER_REQUEST_TYPE,
            )
            if order_request_response.get("status") == "failure":
                updated_order_data = {"status": "failure", "data": {"unfilled_amount": 100000000000, "amount": 1000000000000}}
            else:
                updated_order_data = order_request_response
        except Exception as e:
            self.logger().warning(f"Error requesting orders from Vertex sequencer: {e}")

        # NOTE: Try to fetch order details from indexer
        if updated_order_data.get("status") == "failure":
            live_order = False
            try:
                data = {
                    "orders": {
                        "digests": [tracked_order.exchange_order_id]
                        },
                    }
                indexed_order_data = await self._api_post(
                    path_url=CONSTANTS.INDEXER_PATH_URL,
                    data=data,
                    limit_id=CONSTANTS.INDEXER_PATH_URL
                )
                orders = indexed_order_data.get("orders", [])
                if len(orders) > 0:
                    updated_order_data["data"] = orders[0]
                    updated_order_data["data"]["unfilled_amount"] = float(updated_order_data["data"]["amount"]) - float(
                        updated_order_data["data"]["base_filled"]
                    )

            except Exception as e:
                self.logger().warning(f"Error requesting orders from Vertex indexer: {e}")

        unfilled_amount = Decimal(utils.convert_from_x18(updated_order_data["data"]["unfilled_amount"]))
        order_amount = Decimal(utils.convert_from_x18(updated_order_data["data"]["amount"]))
        filled_amount = abs(Decimal(order_amount - unfilled_amount))

        if filled_amount == s_decimal_0:
            new_state = OrderState.OPEN
        if filled_amount > s_decimal_0:
            new_state = OrderState.PARTIALLY_FILLED
        # NOTE: Default to canceled if this is queried against indexer
        if not live_order:
            new_state = OrderState.CANCELED
        if unfilled_amount == s_decimal_0:
            if live_order:
                new_state = OrderState.FILLED
            else:
                # Override default canceled with complete if complete
                new_state = OrderState.COMPLETED
        
        order_update = OrderUpdate(
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=str(tracked_order.exchange_order_id),
            trading_pair=tracked_order.trading_pair,
            update_timestamp=int(time.time()),
            new_state=new_state,
        )

        return order_update

    async def _update_balances(self):
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()
        account = await self._get_account()
        quote = "USDC"
        total_usdc_account_value = s_decimal_0
        self._allocated_collateral_sum = s_decimal_0

        spot_product_map = {product["product_id"]: product for product in account["spot_products"]}
        perp_product_map = {product["product_id"]: product for product in account["perp_products"]}

        for spot_balance in account["spot_balances"]:
            product_id = spot_balance["product_id"]
            balance = Decimal(utils.convert_from_x18(spot_balance["balance"]["amount"]))
            oracle_price = Decimal(utils.convert_from_x18(spot_product_map[product_id]["oracle_price_x18"]))
            total_usdc_account_value = total_usdc_account_value + (balance * oracle_price)
            asset_name = CONSTANTS.PRODUCTS[product_id]["symbol"]
            
            free_balance = Decimal(utils.convert_from_x18(spot_balance["balance"]["amount"]))
            total_balance = Decimal(
                utils.convert_from_x18(
                    spot_balance["balance"]["amount"],
                )
            )
            self._account_available_balances[asset_name] = free_balance
            self._account_balances[asset_name] = total_balance
            remote_asset_names.add(asset_name)

        # NOTE: The entire account is cross margin, therefore we need to ensure we account for perp positions.
        for perp_balance in account["perp_balances"]:
            product_id = perp_balance["product_id"]
            balance = Decimal(utils.convert_from_x18(perp_balance["balance"]["amount"]))

            balance = Decimal(utils.convert_from_x18(perp_balance["balance"]["amount"]))
            oracle_price = Decimal(utils.convert_from_x18(perp_product_map[product_id]["oracle_price_x18"]))
            self._allocated_collateral_sum = self._allocated_collateral_sum + (balance * oracle_price)

        self._account_available_balances[quote] = self._account_available_balances[quote] - abs(
            self._allocated_collateral_sum
        )

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        mapping = bidict()
        for symbol_data in filter(utils.is_exchange_information_valid, exchange_info["data"]["spot_products"]):
            trading_pair = CONSTANTS.PRODUCTS[symbol_data["product_id"]]["market"]
            # NOTE: USDC is an asset, however it doesn't have a "market"
            if symbol_data["product_id"] == 0:
                continue
            base = trading_pair.split("/")[0]
            quote = trading_pair.split("/")[1]
            mapping[trading_pair] = combine_to_hb_trading_pair(base=base, quote=quote)
        self._set_trading_pair_symbol_map(mapping)

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        product_id = utils.trading_pair_to_product_id(trading_pair)

        try:
            data = {
                "matches": {
                    "product_ids": [product_id],
                    "limit": 5
                }
            }
            matches_response = await self._api_post(
                path_url=CONSTANTS.INDEXER_PATH_URL,
                data=data,
                limit_id=CONSTANTS.INDEXER_PATH_URL,
            )
            matches = matches_response.get("matches", [])
            if matches and len(matches) > 0:
                last_price = float(utils.convert_from_x18(matches[0]["order"]["priceX18"]))
                return last_price

        except Exception as e:
            self.logger().warning(f"Failed to get last traded price, using mid price instead, error: {e}")

        params = {"type": CONSTANTS.MARKET_PRICE_REQUEST_TYPE, "product_id": product_id}
        resp_json = await self._api_get(
            path_url=CONSTANTS.QUERY_PATH_URL,
            params=params,
            limit_id=CONSTANTS.MARKET_PRICE_REQUEST_TYPE,
        )
        trading_rules = self.trading_rules[trading_pair]
        mid_price = float(
            str(
                (
                    (
                        Decimal(utils.convert_from_x18(resp_json["data"]["bid_x18"]))
                        + Decimal(utils.convert_from_x18(resp_json["data"]["ask_x18"]))
                    )
                    / Decimal("2.0")
                ).quantize(trading_rules.min_price_increment)
            )
        )
        return mid_price

    async def _get_account(self):
        sender_address = self.sender_address
        response: Dict[str, Dict[str, Any]] = await self._api_get(
            path_url=CONSTANTS.QUERY_PATH_URL,
            params={"type": CONSTANTS.SUBACCOUNT_INFO_REQUEST_TYPE, "subaccount": sender_address},
            limit_id=CONSTANTS.SUBACCOUNT_INFO_REQUEST_TYPE,
        )

        if response == None or "failure" in response["status"] or "data" not in response:
            raise IOError(f"Unable to get account info for sender address {sender_address}")

        return response["data"]

    async def _get_fee_rates(self):
        sender_address = self.sender_address
        response: Dict[str, Dict[str, Any]] = await self._api_get(
            path_url=CONSTANTS.QUERY_PATH_URL,
            params={
                "type": CONSTANTS.FEE_RATES_REQUEST_TYPE,
                "sender": sender_address,
            },
            is_auth_required=False,
            limit_id=CONSTANTS.FEE_RATES_REQUEST_TYPE,
        )

        if response == None or "failure" in response["status"] or "data" not in response:
            raise IOError(f"Unable to get trading fees sender address {sender_address}")
        
        return response["data"]
    
    async def _api_request(
        self,
        path_url,
        method: RESTMethod = RESTMethod.GET,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        is_auth_required: bool = False,
        return_err: bool = False,
        limit_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        last_exception = None
        rest_assistant = await self._web_assistants_factory.get_rest_assistant()
        url = web_utils.public_rest_url(path_url, domain=self.domain)
        local_headers = {"Content-Type": "application/json"}
        for _ in range(2):
            try:
                request_result = await rest_assistant.execute_request(
                    url=url,
                    params=params,
                    data=data,
                    method=method,
                    is_auth_required=is_auth_required,
                    return_err=return_err,
                    headers=local_headers,
                    throttler_limit_id=limit_id if limit_id else CONSTANTS.ALL_ENDPOINTS_LIMIT,
                )
                return request_result
            except IOError as request_exception:
                last_exception = request_exception
                raise

        # Failed even after the last retry
        raise last_exception