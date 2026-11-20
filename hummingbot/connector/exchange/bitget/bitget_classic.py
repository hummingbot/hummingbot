import asyncio
from decimal import ROUND_UP, Decimal
from typing import Any, Dict, List, Literal, Optional, Tuple, Union

import hummingbot.connector.exchange.bitget.bitget_constants as CONSTANTS
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase, TradeFeeSchema


class BitgetClassicAccountMixin:
    """
    The private calls of a Classic Bitget account (one not upgraded to the Unified Trading Account), which still
    trades through the V2 API. BitgetExchange routes to these once it has found the account is Classic; the
    market data and everything else is shared with the UTA path.
    """

    async def _classic_place_cancel(self, order_id: str, tracked_order: InFlightOrder) -> bool:
        cancel_order_response = await self._api_post(
            path_url=CONSTANTS.CLASSIC_CANCEL_ORDER_ENDPOINT,
            data={
                "symbol": await self.exchange_symbol_associated_to_pair(tracked_order.trading_pair),
                "clientOid": tracked_order.client_order_id
            },
            is_auth_required=True,
        )
        response_code = cancel_order_response["code"]

        if response_code != CONSTANTS.RET_CODE_OK:
            raise IOError(self._formatted_error(
                response_code,
                f"Can't cancel order {order_id}: {cancel_order_response}"
            ))

        self._expected_market_amounts.pop(tracked_order.client_order_id, None)

        return True

    async def _classic_place_order(
        self,
        order_id: str,
        trading_pair: str,
        amount: Decimal,
        trade_type: TradeType,
        order_type: OrderType,
        price: Decimal,
    ) -> Tuple[str, float]:
        if order_type is OrderType.MARKET and trade_type is TradeType.BUY:
            current_price: Decimal = self.get_price(trading_pair, True)
            step_size = Decimal(self.trading_rules[trading_pair].min_base_amount_increment)
            amount = (amount * current_price).quantize(step_size, rounding=ROUND_UP)
            self._expected_market_amounts[order_id] = amount
        # LIMIT_MAKER maps to a post-only limit order (orderType "limit" + force "post_only").
        force = (
            CONSTANTS.POST_ONLY_TIME_IN_FORCE
            if order_type is OrderType.LIMIT_MAKER
            else CONSTANTS.DEFAULT_TIME_IN_FORCE
        )
        data = {
            "side": CONSTANTS.TRADE_TYPES[trade_type],
            "symbol": await self.exchange_symbol_associated_to_pair(trading_pair),
            "size": str(amount),
            "orderType": CONSTANTS.ORDER_TYPES[order_type],
            "force": force,
            "clientOid": order_id,
        }
        if order_type.is_limit_type():
            data["price"] = str(price)

        create_order_response = await self._api_post(
            path_url=CONSTANTS.CLASSIC_PLACE_ORDER_ENDPOINT,
            data=data,
            is_auth_required=True,
            headers={
                "X-CHANNEL-API-CODE": CONSTANTS.API_CODE,
            }
        )
        response_code = create_order_response["code"]

        if response_code != CONSTANTS.RET_CODE_OK:
            raise IOError(self._formatted_error(
                response_code,
                f"Error submitting order {order_id}: {create_order_response}"
            ))

        return str(create_order_response["data"]["orderId"]), self.current_timestamp

    async def _classic_update_trading_fees(self) -> None:
        # A Classic account's rates are published with the V2 symbol list.
        exchange_info = await self._api_get(path_url=CONSTANTS.CLASSIC_PUBLIC_SYMBOLS_ENDPOINT)
        symbol_map = await self.trading_pair_symbol_map()

        for symbol_details in exchange_info["data"]:
            trading_pair = symbol_map.get(symbol_details.get("symbol"))
            if trading_pair is None:
                continue
            self._trading_fees[trading_pair] = TradeFeeSchema(
                maker_percent_fee_decimal=Decimal(symbol_details["makerFeeRate"]),
                taker_percent_fee_decimal=Decimal(symbol_details["takerFeeRate"]),
                buy_percent_fee_deducted_from_returns=True,
            )

    async def _classic_update_balances(self) -> None:
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        wallet_balance_response: Dict[str, Union[str, List[Dict[str, Any]]]] = await self._api_get(
            path_url=CONSTANTS.CLASSIC_ASSETS_ENDPOINT,
            is_auth_required=True,
        )
        response_code = wallet_balance_response["code"]

        if response_code != CONSTANTS.RET_CODE_OK:
            raise IOError(self._formatted_error(
                response_code,
                f"Error while balance update: {wallet_balance_response}"
            ))

        for balance_data in wallet_balance_response["data"]:
            self._classic_set_account_balances(balance_data)
            remote_asset_names.add(balance_data["coin"])

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    async def _classic_all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        trade_updates = []

        if order.exchange_order_id is not None:
            try:
                all_fills_response = await self._classic_request_order_fills(order=order)
                fills_data = all_fills_response.get("data", [])

                for fill_data in fills_data:
                    trade_update = self._classic_parse_trade_update(
                        trade_msg=fill_data,
                        tracked_order=order,
                        source_type="rest"
                    )
                    trade_updates.append(trade_update)
            except IOError as ex:
                if not self._is_request_exception_related_to_time_synchronizer(
                    request_exception=ex
                ):
                    raise
        if len(trade_updates) > 0:
            self.logger().info(
                f"{len(trade_updates)} trades updated for order {order.client_order_id}"
            )

        return trade_updates

    async def _classic_request_order_fills(self, order: InFlightOrder) -> Dict[str, Any]:
        order_fills_response = await self._api_get(
            path_url=CONSTANTS.CLASSIC_USER_FILLS_ENDPOINT,
            params={
                "orderId": order.exchange_order_id
            },
            is_auth_required=True,
        )

        return order_fills_response

    async def _classic_request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        order_info_response = await self._api_get(
            path_url=CONSTANTS.CLASSIC_ORDER_INFO_ENDPOINT,
            params={
                "clientOid": tracked_order.client_order_id
            },
            is_auth_required=True,
        )

        return self._classic_create_order_update(
            order=tracked_order,
            order_update_response=order_info_response
        )

    def _classic_create_order_update(
        self, order: InFlightOrder, order_update_response: Dict[str, Any]
    ) -> OrderUpdate:
        updated_order_data = order_update_response["data"]

        if not updated_order_data:
            raise ValueError(f"Can't parse order status data. Data: {updated_order_data}")

        updated_info = updated_order_data[0]

        if (
            order.trade_type is TradeType.BUY
            and order.order_type is OrderType.MARKET
            and order.client_order_id not in self._expected_market_amounts
        ):
            self._expected_market_amounts[order.client_order_id] = Decimal(updated_info["size"])

        new_state = self._order_state_for(updated_info.get("status"))
        if new_state is None:
            # As on a Unified Trading Account: an unmapped status is not a missing order, so hold
            # the state already known rather than raise; _order_state_for has logged it.
            new_state = order.current_state
        order_update = OrderUpdate(
            trading_pair=order.trading_pair,
            update_timestamp=self.current_timestamp,
            new_state=new_state,
            client_order_id=order.client_order_id,
            exchange_order_id=order.exchange_order_id,
        )

        return order_update

    def _classic_parse_trade_update(
        self,
        trade_msg: Dict,
        tracked_order: InFlightOrder,
        source_type: Literal["websocket", "rest"]
    ) -> Optional[TradeUpdate]:
        self.logger().debug(f"Data for {source_type} trade update: {trade_msg}")

        fee_detail = trade_msg["feeDetail"]
        trade_fee_data = fee_detail[0] if isinstance(fee_detail, list) else fee_detail
        fee_amount = abs(Decimal(trade_fee_data["totalFee"]))
        fee_coin = trade_fee_data["feeCoin"]
        side = TradeType.BUY if trade_msg["side"] == "buy" else TradeType.SELL

        fee = TradeFeeBase.new_spot_fee(
            fee_schema=self.trade_fee_schema(),
            trade_type=side,
            flat_fees=[TokenAmount(amount=fee_amount, token=fee_coin)],
        )

        trade_id: str = trade_msg["tradeId"]
        trading_pair = tracked_order.trading_pair
        fill_price = Decimal(trade_msg["priceAvg"])
        base_amount = Decimal(trade_msg["size"])
        quote_amount = Decimal(trade_msg["amount"])

        if (
            tracked_order.trade_type is TradeType.BUY
            and tracked_order.order_type is OrderType.MARKET
        ):
            expected_price = (
                self._expected_market_amounts[tracked_order.client_order_id] / tracked_order.amount
            )
            base_amount = (quote_amount / expected_price).quantize(
                Decimal(self.trading_rules[trading_pair].min_base_amount_increment),
                rounding=ROUND_UP
            )

        trade_update: TradeUpdate = TradeUpdate(
            trade_id=trade_id,
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=str(trade_msg["orderId"]),
            trading_pair=trading_pair,
            fill_timestamp=int(trade_msg["uTime"]) * 1e-3,
            fill_price=fill_price,
            fill_base_amount=base_amount,
            fill_quote_amount=quote_amount,
            fee=fee
        )

        return trade_update

    async def _classic_user_stream_event_listener(self) -> None:
        async for event_message in self._iter_user_event_queue():
            try:
                channel = event_message["arg"]["channel"]
                data = event_message["data"]

                self.logger().debug(f"Channel: {channel} - Data: {data}")

                if channel == CONSTANTS.CLASSIC_WS_ORDERS_ENDPOINT:
                    for order_msg in data:
                        self._classic_process_order_event_message(order_msg)
                elif channel == CONSTANTS.CLASSIC_WS_FILL_ENDPOINT:
                    for fill_msg in data:
                        self._classic_process_fill_event_message(fill_msg)
                elif channel == CONSTANTS.CLASSIC_WS_ACCOUNT_ENDPOINT:
                    for wallet_msg in data:
                        self._classic_set_account_balances(wallet_msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error in user stream listener loop.")

    def _classic_process_order_event_message(self, order_msg: Dict[str, Any]) -> None:
        """
        Updates in-flight order and triggers cancellation or failure event if needed.
        :param order_msg: The order event message payload
        """
        order_status = self._order_state_for(order_msg.get("status"))
        if order_status is None:
            return
        client_order_id = str(order_msg["clientOid"])
        updatable_order = self._order_tracker.all_updatable_orders.get(client_order_id)

        if updatable_order is not None:
            if (
                updatable_order.trade_type is TradeType.BUY
                and updatable_order.order_type is OrderType.MARKET
                and client_order_id not in self._expected_market_amounts
            ):
                self._expected_market_amounts[client_order_id] = Decimal(order_msg["notional"])

            if order_status is OrderState.PARTIALLY_FILLED:
                side = TradeType.BUY if order_msg["side"] == "buy" else TradeType.SELL
                fee_amount = abs(Decimal(order_msg["fillFee"]))
                fee_coin = order_msg["fillFeeCoin"]

                fee = TradeFeeBase.new_spot_fee(
                    fee_schema=self.trade_fee_schema(),
                    trade_type=side,
                    flat_fees=[TokenAmount(amount=fee_amount, token=fee_coin)],
                )
                trading_pair = updatable_order.trading_pair
                fill_price = Decimal(order_msg["fillPrice"])
                base_amount = Decimal(order_msg["baseVolume"])
                quote_amount = base_amount * fill_price

                if (
                    updatable_order.trade_type is TradeType.BUY
                    and updatable_order.order_type is OrderType.MARKET
                ):
                    expected_price = Decimal(order_msg["notional"]) / updatable_order.amount
                    base_amount = (quote_amount / expected_price).quantize(
                        Decimal(self.trading_rules[trading_pair].min_base_amount_increment),
                        rounding=ROUND_UP
                    )

                new_trade_update: TradeUpdate = TradeUpdate(
                    trade_id=order_msg["tradeId"],
                    client_order_id=client_order_id,
                    exchange_order_id=updatable_order.exchange_order_id,
                    trading_pair=updatable_order.trading_pair,
                    fill_timestamp=int(order_msg["fillTime"]) * 1e-3,
                    fill_price=fill_price,
                    fill_base_amount=base_amount,
                    fill_quote_amount=quote_amount,
                    fee=fee
                )
                self._order_tracker.process_trade_update(new_trade_update)

            new_order_update: OrderUpdate = OrderUpdate(
                trading_pair=updatable_order.trading_pair,
                update_timestamp=int(order_msg["uTime"]) * 1e-3,
                new_state=order_status,
                client_order_id=client_order_id,
                exchange_order_id=order_msg["orderId"],
            )
            self._order_tracker.process_order_update(new_order_update)

    def _classic_process_fill_event_message(self, fill_msg: Dict[str, Any]) -> None:
        try:
            order_id = str(fill_msg.get("orderId", ""))
            trade_id = str(fill_msg.get("tradeId", ""))
            # Match on clientOid first, as on a Unified Trading Account: a market order can fill
            # before its place-order response arrives, and until then the tracked order has no
            # exchange order id to match on.
            client_order_id = fill_msg.get("clientOid")
            fillable_order = (
                self._order_tracker.all_fillable_orders.get(str(client_order_id)) if client_order_id else None
            ) or self._order_tracker.all_fillable_orders_by_exchange_order_id.get(order_id)

            if not fillable_order:
                self.logger().debug(
                    f"Ignoring fill message for order {order_id}: not in in_flight_orders."
                )
                return

            trade_update = self._classic_parse_trade_update(
                trade_msg=fill_msg,
                tracked_order=fillable_order,
                source_type="websocket"
            )
            if trade_update:
                self._order_tracker.process_trade_update(trade_update)

                self.logger().debug(
                    f"Processed fill event for order {fillable_order.client_order_id}: "
                    f"Trade {trade_id}: {fill_msg.get('size')} at {fill_msg.get('priceAvg')}."
                )
        except Exception as e:
            self.logger().error(f"Error processing fill event: {e}", exc_info=True)

    def _classic_set_account_balances(self, data: Dict[str, Any]) -> None:
        symbol = data["coin"]
        available = Decimal(str(data["available"]))
        frozen = Decimal(str(data["frozen"]))
        self._account_balances[symbol] = frozen + available
        self._account_available_balances[symbol] = available
