import asyncio
import json
from decimal import Decimal
from typing import Dict, List

from hummingbot.connector.connector.uniswap.uniswap_connector import UniswapConnector
from hummingbot.connector.connector.uniswap.uniswap_in_flight_order import UniswapInFlightOrder
from hummingbot.connector.connector.uniswap_v3.uniswap_v3_in_flight_position import UniswapV3InFlightPosition, UniswapV3PositionStatus
from hummingbot.core.event.events import (
    MarketEvent,
    BuyOrderCreatedEvent,
    SellOrderCreatedEvent,
    BuyOrderCompletedEvent,
    SellOrderCompletedEvent,
    MarketOrderFailureEvent,
    OrderFilledEvent,
    RangePositionInitiatedEvent,
    RangePositionCreatedEvent,
    RangePositionRemovedEvent,
    RangePositionFailureEvent,
    RangePositionUpdatedEvent,
    OrderType,
    TradeType,
    TradeFee
)
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce

s_logger = None
s_decimal_0 = Decimal("0")
s_decimal_NaN = Decimal("nan")


class UniswapV3Connector(UniswapConnector):
    """
    UniswapV3Connector extends UniswapConnector to provide v3 specific functionality, e.g. ranged positions
    """

    def __init__(self,
                 trading_pairs: List[str],
                 wallet_private_key: str,
                 ethereum_rpc_url: str,
                 trading_required: bool = True
                 ):
        """
        :param trading_pairs: a list of trading pairs
        :param wallet_private_key: a private key for eth wallet
        :param ethereum_rpc_url: this is usually infura RPC URL
        :param trading_required: Whether actual trading is needed.
        """
        super().__init__(trading_pairs, wallet_private_key, ethereum_rpc_url, trading_required)
        self._in_flight_positions: Dict[str, UniswapV3InFlightPosition] = {}

    @property
    def name(self) -> str:
        return "uniswap_v3"

    def get_order_price_quantum(self, trading_pair: str, price: Decimal) -> Decimal:
        return Decimal("1e-6")

    def get_order_size_quantum(self, trading_pair: str, order_size: Decimal) -> Decimal:
        return Decimal("1e-6")

    def restore_tracking_states(self, saved_states: Dict[str, any]):
        self.logger().info("Restoring existing orders and positions to inflight tracker.")
        if saved_states.get("orders", False):
            self._in_flight_orders.update({
                key: UniswapV3InFlightPosition.from_json(value)
                for key, value in saved_states["orders"].items()
            })
        if saved_states.get("positions", False):
            self._in_flight_positions.update({
                key: UniswapV3InFlightPosition.from_json(value)
                for key, value in saved_states["positions"].items()
            })

    @property
    def tracking_states(self) -> Dict[str, any]:
        """
        :return active in-flight orders and in-flight positions in json format, is used to save in sqlite db.
        """
        orders = {
            key: value.to_json()
            for key, value in self._in_flight_orders.items()
            if not value.is_done
        }
        positions = {
            key: value.to_json()
            for key, value in self._in_flight_positions.items()
            if not value.last_status.is_done()
        }
        return {"orders": orders, "positions": positions}

    def parse_liquidity_events(self, events):
        token_id = amount0 = amount1 = 0
        for event in events:
            if event["name"] == "tokenId":
                token_id = event["value"]
            elif event["name"] == "amount0":
                amount0 = event["value"]
            elif event["name"] == "amount1":
                amount1 = event["value"]
        return token_id, amount0, amount1

    async def update_swap_order(self, update_result: Dict[str, any], tracked_order: UniswapInFlightOrder):
        if update_result.get("confirmed", False):
            if update_result["receipt"].get("status", 0) == 1:
                order_id = await tracked_order.get_exchange_order_id()
                gas_used = update_result["receipt"]["gasUsed"]
                gas_price = tracked_order.gas_price
                fee = Decimal(str(gas_used)) * Decimal(str(gas_price)) / Decimal(str(1e9))
                self.trigger_event(
                    MarketEvent.OrderFilled,
                    OrderFilledEvent(
                        self.current_timestamp,
                        tracked_order.client_order_id,
                        tracked_order.trading_pair,
                        tracked_order.trade_type,
                        tracked_order.order_type,
                        Decimal(str(tracked_order.price)),
                        Decimal(str(tracked_order.amount)),
                        TradeFee(0.0, [(tracked_order.fee_asset, Decimal(str(fee)))]),
                        exchange_trade_id=order_id
                    )
                )
                tracked_order.last_state = "FILLED"
                self.logger().info(f"The {tracked_order.trade_type.name} order "
                                   f"{tracked_order.client_order_id} has completed "
                                   f"according to order status API.")
                event_tag = MarketEvent.BuyOrderCompleted if tracked_order.trade_type is TradeType.BUY \
                    else MarketEvent.SellOrderCompleted
                event_class = BuyOrderCompletedEvent if tracked_order.trade_type is TradeType.BUY \
                    else SellOrderCompletedEvent
                self.trigger_event(event_tag,
                                   event_class(self.current_timestamp,
                                               tracked_order.client_order_id,
                                               tracked_order.base_asset,
                                               tracked_order.quote_asset,
                                               tracked_order.fee_asset,
                                               tracked_order.executed_amount_base,
                                               tracked_order.executed_amount_quote,
                                               float(fee),
                                               tracked_order.order_type))
                self.stop_tracking_order(tracked_order.client_order_id)
            else:
                self.logger().info(
                    f"The {tracked_order.type} order {tracked_order.client_order_id} has failed according to order status API. ")
                self.trigger_event(MarketEvent.OrderFailure,
                                   MarketOrderFailureEvent(
                                       self.current_timestamp,
                                       tracked_order.client_order_id,
                                       tracked_order.order_type
                                   ))
                self.stop_tracking_order(tracked_order.client_order_id)

    async def update_lp_order(self, update_result: Dict[str, any], tracked_pos: UniswapV3InFlightPosition):
        """
        Unlike swap orders, lp orders only stop tracking when a remove position is detected.
        """
        if update_result.get("confirmed", False):
            if update_result["receipt"].get("status", 0) == 1:
                transaction_results = await self._api_request("post",
                                                              "eth/uniswap/v3/result",
                                                              {"logs": json.dumps(update_result["receipt"]["logs"])})
                for result in transaction_results["info"]:
                    if result["name"] == "IncreaseLiquidity" and tracked_pos.last_status == UniswapV3PositionStatus.PENDING_CREATE:
                        token_id, amount0, amount1 = self.parse_liquidity_events(result["events"])
                        tracked_pos.token_id = token_id
                        tracked_pos.base_amount = amount0
                        tracked_pos.quote_amount = amount1
                        tracked_pos.last_status = UniswapV3PositionStatus.OPEN
                        self.logger().info(f"Liquidity added for tokenID - {token_id}.")
                        self.trigger_event(MarketEvent.RangePositionUpdated,
                                           RangePositionUpdatedEvent(self.current_timestamp,
                                                                     tracked_pos.hb_id,
                                                                     tracked_pos.last_tx_hash,
                                                                     tracked_pos.token_id,
                                                                     tracked_pos.base_amount,
                                                                     tracked_pos.quote_amount,
                                                                     tracked_pos.last_status.name
                                                                     ))
                        self.trigger_event(MarketEvent.RangePositionCreated,
                                           RangePositionCreatedEvent(self.current_timestamp,
                                                                     tracked_pos.hb_id,
                                                                     tracked_pos.last_tx_hash,
                                                                     tracked_pos.token_id,
                                                                     tracked_pos.trading_pair,
                                                                     tracked_pos.fee_tier,
                                                                     tracked_pos.lower_price,
                                                                     tracked_pos.upper_price,
                                                                     tracked_pos.base_amount,
                                                                     tracked_pos.quote_amount,
                                                                     tracked_pos.last_status.name,
                                                                     tracked_pos.gas_price
                                                                     ))
                    elif result["name"] == "DecreaseLiquidity" and tracked_pos.last_status == UniswapV3PositionStatus.PENDING_REMOVE:
                        token_id, amount0, amount1 = self.parse_liquidity_events(result["events"])
                        tracked_pos.token_id = token_id
                        tracked_pos.last_status = UniswapV3PositionStatus.REMOVED
                        self.logger().info(f"Liquidity decreased for tokenID - {token_id}.")
                        self.trigger_event(MarketEvent.RangePositionUpdated,
                                           RangePositionUpdatedEvent(self.current_timestamp,
                                                                     tracked_pos.hb_id,
                                                                     tracked_pos.last_tx_hash,
                                                                     tracked_pos.token_id,
                                                                     tracked_pos.base_amount,
                                                                     tracked_pos.quote_amount,
                                                                     tracked_pos.last_status.name
                                                                     ))
                        self.trigger_event(MarketEvent.RangePositionRemoved,
                                           RangePositionRemovedEvent(self.current_timestamp, tracked_pos.hb_id,
                                                                     tracked_pos.token_id))
                        self.stop_tracking_position(tracked_pos.hb_id)
                    elif result["name"] == "Collect":
                        pass
                        # not sure how to handle this at the moment
                        # token_id, amount0, amount1 = self.parse_liquidity_events(result["events"])
                        # tracked_order.update_exchange_order_id(token_id)
                        # self.logger().info(f"Liquidity removed for tokenID - {token_id}.")
            else:
                self.logger().info(
                    f"Error updating range position, token_id: {tracked_pos.token_id}, hb_id: {tracked_pos.hb_id}"
                )
                self.trigger_event(MarketEvent.RangePositionFailure,
                                   RangePositionFailureEvent(self.current_timestamp, tracked_pos.hb_id))
                self.stop_tracking_position(tracked_pos.hb_id)
                tracked_pos.last_status = UniswapV3PositionStatus.FAILED

    async def _update_order_status(self):
        """
        Calls REST API to get status update for each in-flight order.
        """
        tasks, tracked_orders, tracked_positions = [], [], []
        if len(self._in_flight_orders) > 0:
            tracked_orders = list(self._in_flight_orders.values())
            for tracked_order in tracked_orders:
                order_id = await tracked_order.get_exchange_order_id()
                tasks.append(self._api_request("post",
                                               "eth/poll",
                                               {"txHash": order_id}))
        if len(self._in_flight_positions) > 0:
            tracked_positions = list(self._in_flight_positions.values())
            for tracked_pos in tracked_positions:
                last_hash = await tracked_pos.get_last_tx_hash()
                tasks.append(self._api_request("post",
                                               "eth/poll",
                                               {"txHash": last_hash}))
        if not tasks:
            return
        update_results = await safe_gather(*tasks, return_exceptions=True)
        for update_result, tracked_item in zip(update_results, tracked_orders + tracked_positions):
            self.logger().info(f"Polling for order status updates of {len(tasks)} orders.")
            if isinstance(update_result, Exception):
                raise update_result
            if "txHash" not in update_result:
                self.logger().info(f"Update_order_status txHash not in resp: {update_result}")
                continue
            if isinstance(tracked_item, UniswapInFlightOrder):
                await self.update_swap_order(update_result, tracked_item)
            else:
                await self.update_lp_order(update_result, tracked_item)

    def add_position(self,
                     trading_pair: str,
                     fee_tier: Decimal,
                     base_amount: Decimal,
                     quote_amount: Decimal,
                     lower_price: Decimal,
                     upper_price: Decimal):
        hb_id = f"{trading_pair}-{get_tracking_nonce()}"
        safe_ensure_future(self._add_position(hb_id, trading_pair, fee_tier, base_amount, quote_amount,
                                              lower_price, upper_price))
        return hb_id

    def start_tracking_position(self,
                                hb_id: str,
                                trading_pair: str,
                                fee_tier: Decimal,
                                base_amount: Decimal,
                                quote_amount: Decimal,
                                lower_price: Decimal,
                                upper_price: Decimal):
        """
        Starts tracking a range position by simply adding it into _in_flight_positions dictionary.
        """
        self._in_flight_positions[hb_id] = UniswapV3InFlightPosition(
            hb_id=hb_id,
            token_id=None,
            trading_pair=trading_pair,
            fee_tier=fee_tier,
            base_amount=base_amount,
            quote_amount=quote_amount,
            lower_price=lower_price,
            upper_price=upper_price,
        )

    def stop_tracking_position(self, hb_id: str):
        """
        Stops tracking a position by simply removing it from _in_flight_positions dictionary.
        """
        if hb_id in self._in_flight_positions:
            del self._in_flight_positions[hb_id]

    async def _add_position(self,
                            hb_id: str,
                            trading_pair: str,
                            fee_tier: Decimal,
                            base_amount: Decimal,
                            quote_amount: Decimal,
                            lower_price: Decimal,
                            upper_price: Decimal):
        """
        Calls add position end point to create a new range position.
        :param hb_id: Internal Hummingbot id
        :param trading_pair: The market trading pair of the pool
        :param fee_tier: The expected fee
        :param base_amount: The amount of base token to put into the pool
        :param lower_price: The lower bound of the price range
        :param upper_price: The upper bound of the price range
        """
        base_amount = self.quantize_order_amount(trading_pair, base_amount)
        quote_amount = self.quantize_order_amount(trading_pair, quote_amount)
        lower_price = self.quantize_order_price(trading_pair, lower_price)
        upper_price = self.quantize_order_price(trading_pair, upper_price)
        base, quote = trading_pair.split("-")
        api_params = {"token0": base,
                      "token1": quote,
                      "fee": str(fee_tier),
                      "lowerPrice": str(lower_price),
                      "upperPrice": str(upper_price),
                      "amount0": str(base_amount),
                      "amount1": str(quote_amount),
                      }
        self.start_tracking_position(hb_id, trading_pair, fee_tier, base_amount, quote_amount,
                                     lower_price, upper_price)
        try:
            order_result = await self._api_request("post", "eth/uniswap/v3/add-position", api_params)
            tracked_pos = self._in_flight_positions[hb_id]
            tx_hash = order_result.get("hash")
            tracked_pos.update_last_tx_hash(tx_hash)
            tracked_pos.gas_price = order_result.get("gasPrice")
            tracked_pos.last_status = UniswapV3PositionStatus.PENDING_CREATE
            self.logger().info(f"Created range position for {trading_pair}, hb_id: {hb_id}, tx_hash: {tx_hash} "
                               f"amount: {base_amount} ({base}), "
                               f"range: {lower_price} - {upper_price}")
            self.trigger_event(
                MarketEvent.RangePositionInitiated,
                RangePositionInitiatedEvent(
                    timestamp=self.current_timestamp,
                    hb_id=hb_id,
                    tx_hash=tx_hash,
                    trading_pair=trading_pair,
                    fee_tier=fee_tier,
                    lower_price=lower_price,
                    upper_price=upper_price,
                    base_amount=base_amount,
                    quote_amount=quote_amount,
                    gas_price=tracked_pos.gas_price,
                    status=UniswapV3PositionStatus.PENDING_CREATE.name,
                )
            )
        except Exception as e:
            self.stop_tracking_order(hb_id)
            self.logger().network(
                f"Error submitting range position to Uniswap V3 for {trading_pair} "
                f"hb_id: {hb_id},"
                f"amount: {base_amount} ({base}) {quote_amount}) ({quote}), "
                f"range: {lower_price} - {upper_price}",
                exc_info=True,
                app_warning_msg=str(e)
            )
            self.trigger_event(MarketEvent.RangePositionFailure,
                               RangePositionFailureEvent(self.current_timestamp, hb_id))

    def remove_position(self, hb_id: str, token_id: str):
        safe_ensure_future(self._remove_position(hb_id, token_id))
        # get the inflight order that has this token_id
        return hb_id

    async def _remove_position(self, hb_id: str, token_id: str):
        tracked_pos = self._in_flight_positions.get(hb_id)
        await tracked_pos.get_last_tx_hash()
        tracked_pos.last_status = UniswapV3PositionStatus.PENDING_REMOVE
        tracked_pos.update_last_tx_hash(None)
        try:
            result = await self._api_request("post", "eth/uniswap/v3/remove-position", {"tokenId": token_id})
            hash = result.get("hash")
            self.logger().info(f"Initiated removal of position with ID - {token_id}.")
            tracked_pos.update_last_tx_hash(hash)
            self.trigger_event(MarketEvent.RangePositionUpdated,
                               RangePositionUpdatedEvent(self.current_timestamp, tracked_pos.hb_id,
                                                         tracked_pos.last_tx_hash, tracked_pos.token_id,
                                                         tracked_pos.base_amount, tracked_pos.quote_amount,
                                                         tracked_pos.last_status.name))
        except Exception as e:
            self.stop_tracking_position(hb_id)
            self.logger().network(
                f"Error removing range position, token_id: {token_id}, hb_id: {hb_id}",
                exc_info=True,
                app_warning_msg=str(e)
            )
            self.trigger_event(MarketEvent.RangePositionFailure,
                               RangePositionFailureEvent(self.current_timestamp, hb_id))

    def replace_position(self,
                         token_id: str,
                         trading_pair: str,
                         fee_tier: Decimal,
                         base_amount: Decimal,
                         quote_amount: Decimal,
                         lower_price: Decimal,
                         upper_price: Decimal):
        hb_id = f"{trading_pair}-{get_tracking_nonce()}"
        safe_ensure_future(self._replace_position(hb_id, token_id, trading_pair, fee_tier, base_amount, quote_amount, lower_price, upper_price))
        return hb_id

    async def _replace_position(self,
                                hb_id: str,
                                token_id: str,
                                trading_pair: str,
                                fee_tier: Decimal,
                                base_amount: Decimal,
                                quote_amount: Decimal,
                                lower_price: Decimal,
                                upper_price: Decimal):
        """
        Calls add position end point to create a new range position.
        :param hb_id: Internal Hummingbot id
        :param trading_pair: The market trading pair of the pool
        :param fee_tier: The expected fee
        :param base_amount: The amount of base token to put into the pool
        :param lower_price: The lower bound of the price range
        :param upper_price: The upper bound of the price range
        """
        base_amount = self.quantize_order_amount(trading_pair, base_amount)
        quote_amount = self.quantize_order_amount(trading_pair, quote_amount)
        lower_price = self.quantize_order_price(trading_pair, lower_price)
        upper_price = self.quantize_order_price(trading_pair, upper_price)
        base, quote = trading_pair.split("-")
        tracked_pos = self._in_flight_positions.get(hb_id)
        await tracked_pos.get_last_tx_hash()
        tracked_pos.last_status = UniswapV3PositionStatus.PENDING_REMOVE
        tracked_pos.update_last_tx_hash(None)

        new_hb_id = f"{trading_pair}-{get_tracking_nonce()}"
        self.start_tracking_position(new_hb_id, trading_pair, fee_tier, base_amount, quote_amount,
                                     lower_price, upper_price)
        try:
            order_result = await self._api_request("post", "eth/uniswap/v3/replace-position",
                                                   {"tokenId": token_id,
                                                    "token0": base,
                                                    "token1": quote,
                                                    "fee": str(fee_tier),
                                                    "lowerPrice": str(lower_price),
                                                    "upperPrice": str(upper_price),
                                                    "amount0": str(base_amount),
                                                    "amount1": str(quote_amount),
                                                    })
            tracked_pos = self._in_flight_positions.get(new_hb_id)
            tracked_pos.token_id = order_result.get("tokenId")
            tracked_pos.gas_price = Decimal(str(order_result.get("gasPrice")))
            tracked_pos.update_last_tx_hash(order_result.get("hash"))
            self.logger().info(f"Initiated replacement of position with ID - {token_id}.")
        except Exception as e:
            self.stop_tracking_order(hb_id)
            self.logger().network(
                f"Error replacing range position to Uniswap with ID - {token_id} "
                f"hb_id: {hb_id}",
                exc_info=True,
                app_warning_msg=str(e)
            )
            self.trigger_event(MarketEvent.RangePositionFailure,
                               RangePositionFailureEvent(self.current_timestamp, hb_id))

    async def get_position(self, token_id: str):
        result = await self._api_request("post", "eth/uniswap/v3/position", {"tokenId": token_id})
        return result

    async def collect_fees(self, token_id: str):  # not used yet, but should be refactored to return an order_id and also track transaction
        result = await self._api_request("post", "eth/uniswap/v3/collect-fees", {"tokenId": token_id})
        return result

    async def get_price_by_fee_tier(self, trading_pair: str, tier: str):
        """
        Get price on a specific fee tier.
        :param trading_pair: trading pair to fetch
        :param tier: tier to return
        """
        try:
            base, quote = trading_pair.split("-")
            resp = await self._api_request("post",
                                           "eth/uniswap/v3/price",
                                           {"base": base,
                                            "quote": quote})

            return Decimal(str(resp["prices"][tier.upper()]))
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().network(
                f"Error getting price for {trading_pair}.",
                exc_info=True,
                app_warning_msg=str(e)
            )

    def get_token_id(self, client_order_id):  # to be refactored to fetch from databse in subsequent releases
        return self._in_flight_positions.get(client_order_id, 0)

    async def approve_uniswap_spender(self, token_symbol: str) -> Decimal:
        """
        Approves Uniswap contract as a spender for a token.
        :param token_symbol: token to approve.
        """
        spender = "uniswapV3Router" if token_symbol[:1] == "R" else "uniswapV3NFTManager"
        token_symbol = token_symbol[1:]
        resp = await self._api_request("post",
                                       "eth/approve",
                                       {"token": token_symbol,
                                        "connector": spender})
        amount_approved = Decimal(str(resp["amount"]))
        if amount_approved > 0:
            self.logger().info(f"Approved Uniswap {spender} contract for {token_symbol}.")
        else:
            self.logger().info(f"Uniswap spender contract approval failed on {token_symbol}.")
        return amount_approved

    async def get_allowances(self) -> Dict[str, Decimal]:
        """
        Retrieves allowances for token in trading_pairs
        :return: A dictionary of token and its allowance (how much Uniswap can spend).
        """
        ret_val = {}
        router_allowances = await self._api_request("post", "eth/allowances",
                                                    {"tokenList": "[" + (",".join(['"' + t + '"' for t in self._tokens])) + "]",
                                                     "connector": "uniswapV3Router"})
        nft_allowances = await self._api_request("post", "eth/allowances",
                                                 {"tokenList": "[" + (",".join(['"' + t + '"' for t in self._tokens])) + "]",
                                                  "connector": "uniswapV3NFTManager"})
        for token, amount in router_allowances["approvals"].items():
            ret_val["R" + token] = Decimal(str(amount))
        for token, amount in nft_allowances["approvals"].items():
            ret_val["N" + token] = Decimal(str(amount))
        return ret_val

    def has_allowances(self) -> bool:
        """
        Checks if all tokens have allowance (an amount approved)
        """
        return len(self._allowances.values()) == (len(self._tokens) * 2) and \
            all(amount > s_decimal_0 for amount in self._allowances.values())

    async def _create_order(self,
                            trade_type: TradeType,
                            order_id: str,
                            trading_pair: str,
                            amount: Decimal,
                            price: Decimal):
        """
        Calls buy or sell API end point to place an order, starts tracking the order and triggers relevant order events.
        :param trade_type: BUY or SELL
        :param order_id: Internal order id (also called client_order_id)
        :param trading_pair: The market to place order
        :param amount: The order amount (in base token value)
        :param price: The order price
        """

        amount = self.quantize_order_amount(trading_pair, amount)
        price = self.quantize_order_price(trading_pair, price)
        base, quote = trading_pair.split("-")
        api_params = {"base": base,
                      "quote": quote,
                      "side": trade_type.name.upper(),
                      "amount": str(amount),
                      "limitPrice": str(price),
                      }
        try:
            order_result = await self._api_request("post", "eth/uniswap/v3/trade", api_params)
            hash = order_result.get("hash")
            gas_price = order_result.get("gasPrice")
            gas_limit = order_result.get("gasLimit")
            gas_cost = order_result.get("gasCost")
            self.start_tracking_order(order_id, None, trading_pair, trade_type, price, amount, gas_price)
            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is not None:
                self.logger().info(f"Created {trade_type.name} order {order_id} txHash: {hash} "
                                   f"for {amount} {trading_pair}. Estimated Gas Cost: {gas_cost} ETH "
                                   f" (gas limit: {gas_limit}, gas price: {gas_price})")
                tracked_order.update_exchange_order_id(hash)
                tracked_order.gas_price = gas_price
            if hash is not None:
                tracked_order.fee_asset = "ETH"
                tracked_order.executed_amount_base = amount
                tracked_order.executed_amount_quote = amount * price
                event_tag = MarketEvent.BuyOrderCreated if trade_type is TradeType.BUY else MarketEvent.SellOrderCreated
                event_class = BuyOrderCreatedEvent if trade_type is TradeType.BUY else SellOrderCreatedEvent
                self.trigger_event(event_tag, event_class(self.current_timestamp, OrderType.LIMIT, trading_pair, amount,
                                                          price, order_id, hash))
            else:
                self.stop_tracking_order(order_id)
                self.trigger_event(MarketEvent.OrderFailure,
                                   MarketOrderFailureEvent(self.current_timestamp, order_id, OrderType.LIMIT))
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.stop_tracking_order(order_id)
            self.logger().network(
                f"Error submitting {trade_type.name} order to Uniswap for "
                f"{amount} {trading_pair} "
                f"{price}.",
                exc_info=True,
                app_warning_msg=str(e)
            )
            self.trigger_event(MarketEvent.OrderFailure,
                               MarketOrderFailureEvent(self.current_timestamp, order_id, OrderType.LIMIT))

    async def start_network(self):
        if self._trading_required:
            self._status_polling_task = safe_ensure_future(self._status_polling_loop())
            self._auto_approve_task = safe_ensure_future(self.auto_approve())

    async def stop_network(self):
        if self._status_polling_task is not None:
            self._status_polling_task.cancel()
            self._status_polling_task = None
        if self._auto_approve_task is not None:
            self._auto_approve_task.cancel()
            self._auto_approve_task = None
