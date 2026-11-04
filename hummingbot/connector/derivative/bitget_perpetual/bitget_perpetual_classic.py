import asyncio
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

import hummingbot.connector.derivative.bitget_perpetual.bitget_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.bitget_perpetual.bitget_perpetual_constants import MarginMode
from hummingbot.connector.derivative.position import Position
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase, TradeFeeSchema

s_decimal_0 = Decimal(0)

POSITION_SIDES = {
    "long": PositionSide.LONG,
    "short": PositionSide.SHORT,
}


class BitgetPerpetualClassicAccountMixin:
    """
    The private calls of a Classic Bitget account (one not upgraded to the Unified Trading Account), which still
    trades futures through the V2 API. BitgetPerpetualDerivative routes to these once it has found the account is
    Classic; the market data and everything else is shared with the UTA path.
    """

    async def _classic_fetch_account_position_mode(self) -> Optional[PositionMode]:
        if not self.trading_pairs:
            return None
        trading_pair = self.trading_pairs[0]
        product_type = await self.product_type_associated_to_trading_pair(trading_pair)
        account_info_response: Dict[str, Any] = await self._api_get(
            path_url=CONSTANTS.CLASSIC_ACCOUNT_INFO_ENDPOINT,
            params={
                "symbol": await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair),
                "productType": product_type,
                "marginCoin": self.get_buy_collateral_token(trading_pair),
            },
            is_auth_required=True,
        )
        if account_info_response["code"] != CONSTANTS.RET_CODE_OK:
            self.logger().error(self._formatted_error(
                account_info_response["code"],
                f"Error getting position mode for {trading_pair}: {account_info_response['msg']}"
            ))
            return None

        position_modes = {
            "one_way_mode": PositionMode.ONEWAY,
            "hedge_mode": PositionMode.HEDGE,
        }

        position_mode = position_modes[account_info_response["data"]["posMode"]]
        self.logger().info(f"Position mode for {trading_pair}: {position_mode}")
        return position_mode

    async def _classic_place_cancel(self, order_id: str, tracked_order: InFlightOrder) -> bool:
        symbol = await self.exchange_symbol_associated_to_pair(tracked_order.trading_pair)
        product_type = await self.product_type_associated_to_trading_pair(tracked_order.trading_pair)
        cancel_result = await self._api_post(
            path_url=CONSTANTS.CLASSIC_CANCEL_ORDER_ENDPOINT,
            data={
                "symbol": symbol,
                "productType": product_type,
                "marginCoin": self.get_buy_collateral_token(tracked_order.trading_pair),
                # clientOid exists before the place-order response does, so a racing cancel still names the order
                "clientOid": tracked_order.client_order_id,
            },
            is_auth_required=True,
        )
        response_code = cancel_result["code"]

        if response_code != CONSTANTS.RET_CODE_OK:
            raise IOError(self._formatted_error(response_code, cancel_result["msg"]))

        return True

    async def _classic_place_order(
        self,
        order_id: str,
        trading_pair: str,
        amount: Decimal,
        trade_type: TradeType,
        order_type: OrderType,
        price: Decimal,
        position_action: PositionAction,
    ) -> Tuple[str, float]:
        product_type = await self.product_type_associated_to_trading_pair(trading_pair)
        margin_modes = {
            MarginMode.CROSS: "crossed",
            MarginMode.ISOLATED: "isolated"
        }
        # LIMIT_MAKER maps to a post-only limit order (orderType "limit" + force "post_only").
        force = (
            CONSTANTS.POST_ONLY_TIME_IN_FORCE
            if order_type is OrderType.LIMIT_MAKER
            else CONSTANTS.DEFAULT_TIME_IN_FORCE
        )
        data = {
            "marginCoin": self.get_buy_collateral_token(trading_pair),
            "symbol": await self.exchange_symbol_associated_to_pair(trading_pair),
            "productType": product_type,
            "size": str(amount),
            "force": force,
            "clientOid": order_id,
            "side": trade_type.name.lower(),
            "marginMode": margin_modes[self._margin_mode],
            "orderType": "limit" if order_type.is_limit_type() else "market",
        }
        if order_type.is_limit_type():
            data["price"] = str(price)

        if self.position_mode is PositionMode.HEDGE:
            if position_action is PositionAction.CLOSE:
                data["side"] = "sell" if trade_type is TradeType.BUY else "buy"
            data["tradeSide"] = position_action.name.lower()

        resp = await self._api_post(
            path_url=CONSTANTS.CLASSIC_PLACE_ORDER_ENDPOINT,
            data=data,
            is_auth_required=True,
            headers={
                "X-CHANNEL-API-CODE": CONSTANTS.API_CODE,
            }
        )

        if resp["code"] != CONSTANTS.RET_CODE_OK:
            raise IOError(self._formatted_error(
                resp["code"],
                f"Error submitting order {order_id}: {resp['msg']}"
            ))

        return str(resp["data"]["orderId"]), self.current_timestamp

    async def _classic_update_trading_fees(self) -> None:
        # A Classic account's rates are published with the V2 contract list.
        symbol_map = await self.trading_pair_symbol_map()

        for product_type in CONSTANTS.ALL_PRODUCT_TYPES:
            exchange_info = await self._api_get(
                path_url=CONSTANTS.CLASSIC_PUBLIC_CONTRACTS_ENDPOINT,
                params={"productType": product_type},
            )
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
        balances = []
        product_types: set[str] = {
            await self.product_type_associated_to_trading_pair(trading_pair)
            for trading_pair in self._trading_pairs
        } or CONSTANTS.ALL_PRODUCT_TYPES

        for product_type in product_types:
            accounts_info_response: Dict[str, Any] = await self._api_get(
                path_url=CONSTANTS.CLASSIC_ACCOUNTS_INFO_ENDPOINT,
                params={
                    "productType": product_type
                },
                is_auth_required=True,
            )

            if accounts_info_response["code"] != CONSTANTS.RET_CODE_OK:
                raise IOError(
                    self._formatted_error(
                        accounts_info_response["code"],
                        accounts_info_response["msg"]
                    )
                )

            balances.extend(accounts_info_response["data"])

        self._account_available_balances.clear()
        self._account_balances.clear()

        for balance_data in balances:
            self._accumulate_balance(
                balance_data["marginCoin"],
                Decimal(balance_data["crossedMaxAvailable"]),
                Decimal(balance_data["accountEquity"]),
            )
            for base_asset in balance_data.get("assetList", []):
                self._accumulate_balance(
                    base_asset["coin"],
                    Decimal(base_asset["available"]),
                    Decimal(base_asset["balance"]),
                )

    async def _classic_update_positions(self) -> None:
        product_types: set[str] = {
            await self.product_type_associated_to_trading_pair(trading_pair)
            for trading_pair in self._trading_pairs
        }
        symbol_map = await self.trading_pair_symbol_map()

        for product_type in product_types:
            all_positions_response: Dict[str, Any] = await self._api_get(
                path_url=CONSTANTS.CLASSIC_ALL_POSITIONS_ENDPOINT,
                params={
                    "productType": product_type
                },
                is_auth_required=True,
            )

            for position in all_positions_response["data"]:
                trading_pair = symbol_map.get(position["symbol"])
                if trading_pair is None:
                    # Dated futures share these product types but are kept out of the symbol map.
                    continue
                self._classic_apply_position(
                    trading_pair=trading_pair,
                    position_side=POSITION_SIDES[position["holdSide"]],
                    unrealized_pnl=Decimal(position["unrealizedPL"]),
                    entry_price=Decimal(position["openPriceAvg"]),
                    amount=Decimal(position["total"]),
                    leverage=Decimal(position["leverage"]),
                )

    def _classic_apply_position(
        self,
        trading_pair: str,
        position_side: PositionSide,
        unrealized_pnl: Decimal,
        entry_price: Decimal,
        amount: Decimal,
        leverage: Decimal,
    ) -> str:
        pos_key = self._perpetual_trading.position_key(trading_pair, position_side)
        if amount != s_decimal_0:
            signed_amount = amount * (Decimal("-1.0") if position_side == PositionSide.SHORT else Decimal("1.0"))
            self._perpetual_trading.set_position(pos_key, Position(
                trading_pair=trading_pair,
                position_side=position_side,
                unrealized_pnl=unrealized_pnl,
                entry_price=entry_price,
                amount=signed_amount,
                leverage=leverage,
            ))
        else:
            self._perpetual_trading.remove_position(pos_key)
        return pos_key

    async def _classic_all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        trade_updates = []

        if order.exchange_order_id is not None:
            try:
                all_fills_response = await self._api_get(
                    path_url=CONSTANTS.CLASSIC_ORDER_FILLS_ENDPOINT,
                    params={
                        "orderId": order.exchange_order_id,
                        "productType": await self.product_type_associated_to_trading_pair(order.trading_pair),
                        "symbol": await self.exchange_symbol_associated_to_pair(order.trading_pair),
                    },
                    is_auth_required=True,
                )
                for fill_data in all_fills_response["data"]["fillList"]:
                    trade_updates.append(self._classic_parse_trade_update(trade_msg=fill_data, tracked_order=order))
            except IOError as ex:
                if not self._is_request_exception_related_to_time_synchronizer(request_exception=ex):
                    raise

        return trade_updates

    async def _classic_request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        try:
            query_params = {
                "symbol": await self.exchange_symbol_associated_to_pair(tracked_order.trading_pair),
                "productType": await self.product_type_associated_to_trading_pair(tracked_order.trading_pair),
            }
            if tracked_order.exchange_order_id:
                query_params["orderId"] = tracked_order.exchange_order_id
            else:
                query_params["clientOid"] = tracked_order.client_order_id

            order_status_data = await self._api_get(
                path_url=CONSTANTS.CLASSIC_ORDER_DETAIL_ENDPOINT,
                params=query_params,
                is_auth_required=True,
            )
            updated_order_data = order_status_data["data"]

            if len(updated_order_data) == 0:
                raise ValueError(f"Can't parse order status data. Data: {updated_order_data}")

            new_state = self._order_state_for(updated_order_data.get("state"))
            if new_state is None:
                # As on a Unified Trading Account: an unmapped status is not a missing order, so
                # hold the state already known rather than raise; _order_state_for has logged it.
                new_state = tracked_order.current_state

            return OrderUpdate(
                trading_pair=tracked_order.trading_pair,
                update_timestamp=self.current_timestamp,
                new_state=new_state,
                client_order_id=str(updated_order_data["clientOid"]),
                exchange_order_id=updated_order_data["orderId"],
            )
        except IOError as ex:
            if not self._is_request_exception_related_to_time_synchronizer(request_exception=ex):
                raise
            return OrderUpdate(
                client_order_id=tracked_order.client_order_id,
                trading_pair=tracked_order.trading_pair,
                update_timestamp=self.current_timestamp,
                new_state=tracked_order.current_state,
            )

    async def _classic_set_margin_mode(self, mode: MarginMode) -> None:
        margin_mode = CONSTANTS.MARGIN_MODE_TYPES[mode]

        for trading_pair in self.trading_pairs:
            product_type = await self.product_type_associated_to_trading_pair(trading_pair)

            response = await self._api_post(
                path_url=CONSTANTS.CLASSIC_SET_MARGIN_MODE_ENDPOINT,
                data={
                    "symbol": await self.exchange_symbol_associated_to_pair(trading_pair),
                    "productType": product_type,
                    "marginMode": margin_mode,
                    "marginCoin": self.get_buy_collateral_token(trading_pair),
                },
                is_auth_required=True,
            )

            if response["code"] != CONSTANTS.RET_CODE_OK:
                self.logger().error(
                    self._formatted_error(
                        response["code"],
                        f"There was an error changing the margin mode ({response['msg']})"
                    )
                )
                return

            self.logger().info(f"Margin mode set to {margin_mode}")

    async def _classic_trading_pair_position_mode_set(self, mode: PositionMode, trading_pair: str) -> Tuple[bool, str]:
        if len(self.account_positions) > 0:
            return False, "Cannot change position because active positions exist"

        try:
            response = await self._api_post(
                path_url=CONSTANTS.CLASSIC_SET_POSITION_MODE_ENDPOINT,
                data={
                    "productType": await self.product_type_associated_to_trading_pair(trading_pair),
                    "posMode": CONSTANTS.POSITION_MODE_TYPES[mode],
                },
                is_auth_required=True,
            )

            if response["code"] != CONSTANTS.RET_CODE_OK:
                return False, self._formatted_error(response["code"], response["msg"])
        except Exception as exception:
            return False, f"There was an error changing the position mode ({exception})"

        return True, ""

    async def _classic_set_trading_pair_leverage(self, trading_pair: str, leverage: int) -> Tuple[bool, str]:
        if len(self.account_positions) > 0:
            return False, "cannot change leverage because active positions exist"

        try:
            response: Dict[str, Any] = await self._api_post(
                path_url=CONSTANTS.CLASSIC_SET_LEVERAGE_ENDPOINT,
                data={
                    "symbol": await self.exchange_symbol_associated_to_pair(trading_pair),
                    "productType": await self.product_type_associated_to_trading_pair(trading_pair),
                    "marginCoin": self.get_buy_collateral_token(trading_pair),
                    "leverage": str(leverage)
                },
                is_auth_required=True,
            )

            if response["code"] != CONSTANTS.RET_CODE_OK:
                return False, self._formatted_error(response["code"], response["msg"])
        except Exception as exception:
            return False, f"There was an error setting the leverage for {trading_pair} ({exception})"

        return True, ""

    async def _classic_fetch_last_fee_payment(self, trading_pair: str) -> Tuple[float, Decimal, Decimal]:
        timestamp, funding_rate, payment = 0, Decimal("-1"), Decimal("-1")

        payment_response: Dict[str, Any] = await self._api_get(
            path_url=CONSTANTS.CLASSIC_ACCOUNT_BILLS_ENDPOINT,
            params={
                "productType": await self.product_type_associated_to_trading_pair(trading_pair),
                "businessType": "contract_settle_fee",
            },
            is_auth_required=True,
        )
        payment_data: Dict[str, Any] = payment_response["data"]["bills"]

        if payment_data:
            last_data = payment_data[0]
            funding_info = self._perpetual_trading._funding_info.get(trading_pair)
            payment = Decimal(last_data["amount"])
            funding_rate = funding_info.rate if funding_info is not None else Decimal(0)
            timestamp = int(last_data["cTime"]) * 1e-3

        return timestamp, funding_rate, payment

    async def _classic_user_stream_event_listener(self) -> None:
        async for event_message in self._iter_user_event_queue():
            try:
                channel = event_message["arg"]["channel"]
                data = event_message["data"]

                if channel == CONSTANTS.CLASSIC_WS_POSITIONS_ENDPOINT:
                    await self._classic_process_account_position_event(data)
                elif channel == CONSTANTS.CLASSIC_WS_ORDERS_ENDPOINT:
                    for order_msg in data:
                        self._classic_process_trade_event_message(order_msg)
                        self._classic_process_order_event_message(order_msg)
                        self._classic_process_balance_update_from_order_event(order_msg)
                elif channel == CONSTANTS.CLASSIC_WS_ACCOUNT_ENDPOINT:
                    for wallet_msg in data:
                        self._classic_process_wallet_event_message(wallet_msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error in user stream listener loop.")

    async def _classic_process_account_position_event(self, position_entries: List[Dict[str, Any]]) -> None:
        all_position_keys = []
        symbol_map = await self.trading_pair_symbol_map()

        for position in position_entries:
            trading_pair = symbol_map.get(position["instId"])
            if trading_pair is None:
                # Dated futures share the account but are kept out of the symbol map.
                continue
            all_position_keys.append(self._classic_apply_position(
                trading_pair=trading_pair,
                position_side=POSITION_SIDES[position["holdSide"]],
                unrealized_pnl=Decimal(position["unrealizedPL"]),
                entry_price=Decimal(position["openPriceAvg"]),
                amount=Decimal(position["total"]),
                leverage=Decimal(position["leverage"]),
            ))

        # Bitget sends position events as snapshots: a closed position is simply not included.
        for position_key in list(self.account_positions.keys()):
            if position_key not in all_position_keys:
                self._perpetual_trading.remove_position(position_key)

    def _classic_process_order_event_message(self, order_msg: Dict[str, Any]) -> None:
        order_status = self._order_state_for(order_msg.get("status"))
        if order_status is None:
            return
        client_order_id = str(order_msg["clientOid"])
        updatable_order = self._order_tracker.all_updatable_orders.get(client_order_id)

        if updatable_order is not None:
            self._order_tracker.process_order_update(OrderUpdate(
                trading_pair=updatable_order.trading_pair,
                update_timestamp=self.current_timestamp,
                new_state=order_status,
                client_order_id=client_order_id,
                exchange_order_id=order_msg["orderId"],
            ))

    def _classic_process_balance_update_from_order_event(self, order_msg: Dict[str, Any]) -> None:
        # As on a Unified Trading Account, this only adjusts the cached available balance for
        # opening orders; the REST balance poll is the source of truth, so bail out rather than
        # raise when the event does not apply or a numeric field is missing or empty.
        order_status = self._order_state_for(order_msg.get("status"))
        symbol = order_msg.get("marginCoin")
        is_opening = order_msg.get("tradeSide") in ["open", "buy_single", "sell_single"]

        if not (
            symbol in self._account_available_balances
            and order_status in [OrderState.OPEN, OrderState.CANCELED]
            and is_opening
        ):
            return

        try:
            order_amount = Decimal(str(order_msg["size"]))
            order_price = Decimal(str(order_msg["price"]))
            leverage = Decimal(str(order_msg["leverage"]))
        except (KeyError, TypeError, ArithmeticError):
            return
        if leverage == Decimal(0):
            return

        margin_amount = (order_amount * order_price) / leverage
        multiplier = Decimal(-1) if order_status == OrderState.OPEN else Decimal(1)
        self._account_available_balances[symbol] += margin_amount * multiplier

    def _classic_process_trade_event_message(self, trade_msg: Dict[str, Any]) -> None:
        fillable_order = self._order_tracker.all_fillable_orders.get(str(trade_msg["clientOid"]))

        if fillable_order and "tradeId" in trade_msg:
            trade_update = self._classic_parse_websocket_trade_update(trade_msg=trade_msg, tracked_order=fillable_order)
            if trade_update:
                self._order_tracker.process_trade_update(trade_update)

    def _classic_parse_websocket_trade_update(self, trade_msg: Dict, tracked_order: InFlightOrder) -> TradeUpdate:
        trade_id: str = trade_msg["tradeId"]

        if trade_id is not None:
            fee_asset = trade_msg["fillFeeCoin"]
            fee_amount = -Decimal(trade_msg["fillFee"])
            position_actions = {
                "open": PositionAction.OPEN,
                "close": PositionAction.CLOSE,
            }
            fee = TradeFeeBase.new_perpetual_fee(
                fee_schema=self.trade_fee_schema(),
                position_action=position_actions.get(trade_msg["tradeSide"], PositionAction.NIL),
                percent_token=fee_asset,
                flat_fees=[] if fee_amount == Decimal("0") else [TokenAmount(amount=fee_amount, token=fee_asset)],
            )
            exec_price = Decimal(trade_msg["fillPrice"]) if "fillPrice" in trade_msg else Decimal(trade_msg["price"])

            return TradeUpdate(
                trade_id=str(trade_id),
                client_order_id=tracked_order.client_order_id,
                exchange_order_id=str(trade_msg["orderId"]),
                trading_pair=tracked_order.trading_pair,
                fill_timestamp=int(trade_msg["fillTime"]) * 1e-3,
                fill_price=exec_price,
                fill_base_amount=Decimal(trade_msg["baseVolume"]),
                fill_quote_amount=exec_price * Decimal(trade_msg["baseVolume"]),
                fee=fee,
            )

    def _classic_parse_trade_update(self, trade_msg: Dict, tracked_order: InFlightOrder) -> TradeUpdate:
        fee_detail = trade_msg["feeDetail"][0]
        fee_asset = fee_detail["feeCoin"]
        fee_amount = abs(Decimal((
            fee_detail["totalDeductionFee"]
            if fee_detail.get("deduction") == "yes"
            else fee_detail["totalFee"]
        )))
        position_actions = {
            "open": PositionAction.OPEN,
            "close": PositionAction.CLOSE,
        }
        fee = TradeFeeBase.new_perpetual_fee(
            fee_schema=self.trade_fee_schema(),
            position_action=position_actions.get(trade_msg["tradeSide"], PositionAction.NIL),
            percent_token=fee_asset,
            flat_fees=[] if fee_amount == Decimal("0") else [TokenAmount(amount=fee_amount, token=fee_asset)],
        )
        exec_price = Decimal(trade_msg["price"])

        return TradeUpdate(
            trade_id=trade_msg["tradeId"],
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=trade_msg["orderId"],
            trading_pair=tracked_order.trading_pair,
            fill_timestamp=int(trade_msg["cTime"]) * 1e-3,
            fill_price=exec_price,
            fill_base_amount=Decimal(trade_msg["baseVolume"]),
            fill_quote_amount=exec_price * Decimal(trade_msg["baseVolume"]),
            fee=fee,
        )

    def _classic_process_wallet_event_message(self, wallet_msg: Dict[str, Any]) -> None:
        symbol = wallet_msg["marginCoin"]
        self._account_balances[symbol] = Decimal(wallet_msg["equity"])
        self._account_available_balances[symbol] = Decimal(wallet_msg["maxOpenPosAvailable"])
