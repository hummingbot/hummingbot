import asyncio
import json
from decimal import Decimal
from typing import Dict, List, Optional

from hummingbot.core.utils import async_ttl_cache
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
    TradeType
)
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce
from hummingbot.core.utils.ethereum import check_transaction_exceptions
from hummingbot.client.config.fee_overrides_config_map import fee_overrides_config_map

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

    async def initiate_pool(self) -> str:
        """
        Initiate connector and start caching paths for trading_pairs
        """
        while True:
            try:
                # self.logger().info(f"Initializing Uniswap connector and paths for {self._trading_pairs} pairs.")
                resp = await self._api_request("get", "eth/uniswap/v3/start",
                                               {"pairs": json.dumps(self._trading_pairs)})
                status = bool(str(resp["success"]))
                if status:
                    self._initiate_pool_status = status
                    self._trading_pairs = resp["pairs"]
                    await asyncio.sleep(60)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().network(
                    f"Error initializing {self._trading_pairs} ",
                    exc_info=True,
                    app_warning_msg=str(e)
                )

    def restore_tracking_states(self, saved_states: Dict[str, any]):
        self.logger().info("Restoring existing orders and positions to inflight tracker.")
        if saved_states.get("orders", False):
            self._in_flight_orders.update({
                key: UniswapV3InFlightPosition.from_json(value)
                for key, value in saved_states["orders"].items()
            })
        if saved_states.get("positions", False):
            for key, value in saved_states["positions"].items():
                self._in_flight_positions.update({
                    key: UniswapV3InFlightPosition.from_json(value)
                })
                self.logger().info(f"Position with id: {value['token_id']} restored.")

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

    def parse_liquidity_events(self, events, base_decimals, quote_decimals):
        token_id = amount0 = amount1 = 0
        for event in events:
            if event["name"] == "tokenId":
                token_id = event["value"]
            elif event["name"] == "amount0":
                amount0 = Decimal(event["value"]) / 10 ** base_decimals
            elif event["name"] == "amount1":
                amount1 = Decimal(event["value"]) / 10 ** quote_decimals
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
                        AddedToCostTradeFee(flat_fees=[TokenAmount(tracked_order.fee_asset, Decimal(str(fee)))]),
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
                gas_used = update_result["receipt"]["gasUsed"]
                gas_price = tracked_pos.gas_price
                fee = Decimal(str(gas_used)) * Decimal(str(gas_price)) / Decimal(str(1e9))
                tracked_pos.tx_fees.append(fee)
                transaction_results = await self._api_request("post",
                                                              "eth/uniswap/v3/result",
                                                              {"logs": json.dumps(update_result["receipt"]["logs"]),
                                                               "pair": tracked_pos.trading_pair})
                for result in transaction_results["info"]:
                    if result["name"] == "IncreaseLiquidity" and tracked_pos.last_status == UniswapV3PositionStatus.PENDING_CREATE:
                        token_id, amount0, amount1 = self.parse_liquidity_events(result["events"],
                                                                                 transaction_results["baseDecimal"],
                                                                                 transaction_results["quoteDecimal"])
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
                        token_id, amount0, amount1 = self.parse_liquidity_events(result["events"],
                                                                                 transaction_results["baseDecimal"],
                                                                                 transaction_results["quoteDecimal"])
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
        tasks, tracked_orders, tracked_positions, open_positions = [], [], [], []
        if len(self._in_flight_orders) > 0:
            tracked_orders = list(self._in_flight_orders.values())
            for tracked_order in tracked_orders:
                order_id = await tracked_order.get_exchange_order_id()
                tasks.append(self._api_request("post",
                                               "eth/poll",
                                               {"txHash": order_id}))
        if len(self._in_flight_positions) > 0:
            tracked_positions = [pos for pos in self._in_flight_positions.values() if pos.last_status.is_pending()]  # We only want to poll update for pending positions
            open_positions = [pos for pos in self._in_flight_positions.values() if pos.last_status.is_active()]
            for tracked_pos in tracked_positions:
                last_hash = await tracked_pos.get_last_tx_hash()
                tasks.append(self._api_request("post",
                                               "eth/poll",
                                               {"txHash": last_hash}))
        if tasks:
            update_results = await safe_gather(*tasks, return_exceptions=True)
            for update_result, tracked_item in zip(update_results, tracked_orders + tracked_positions):
                self.logger().debug(f"Polling for order status updates of {len(tasks)} orders.")
                if isinstance(update_result, Exception):
                    raise update_result
                if "txHash" not in update_result:
                    self.logger().info(f"Update_order_status txHash not in resp: {update_result}")
                    continue
                if isinstance(tracked_item, UniswapInFlightOrder):
                    await self.update_swap_order(update_result, tracked_item)
                else:
                    await self.update_lp_order(update_result, tracked_item)

        # update info for each positions as well
        tasks = []
        if len(open_positions) > 0:
            for tracked_pos in open_positions:
                tasks.append(self.get_position(tracked_pos.token_id))
        if tasks:
            position_results = await safe_gather(*tasks, return_exceptions=True)
            for update_result, tracked_item in zip(position_results, open_positions):
                if not isinstance(update_result, Exception) and len(update_result.get("position", {})) > 0:
                    tracked_item.lower_price = Decimal(update_result["position"].get("lowerPrice", "0"))
                    tracked_item.upper_price = Decimal(update_result["position"].get("upperPrice", "0"))
                    amount0 = Decimal(update_result["position"].get("amount0", "0"))
                    amount1 = Decimal(update_result["position"].get("amount1", "0"))
                    unclaimedToken0 = Decimal(update_result["position"].get("unclaimedToken0", "0"))
                    unclaimedToken1 = Decimal(update_result["position"].get("unclaimedToken1", "0"))
                    if amount0 == amount1 == unclaimedToken0 == unclaimedToken1 == s_decimal_0:
                        self.logger().info(f"Detected that position with id: {tracked_item.token_id} is closed.")
                        tracked_item.last_status = UniswapV3PositionStatus.REMOVED  # this will prevent it from being restored on next import
                        self.trigger_event(MarketEvent.RangePositionUpdated,
                                           RangePositionUpdatedEvent(self.current_timestamp,
                                                                     tracked_item.hb_id,
                                                                     tracked_item.last_tx_hash,
                                                                     tracked_item.token_id,
                                                                     tracked_item.base_amount,
                                                                     tracked_item.quote_amount,
                                                                     tracked_item.last_status.name
                                                                     ))
                        self.trigger_event(MarketEvent.RangePositionRemoved,
                                           RangePositionRemovedEvent(self.current_timestamp, tracked_item.hb_id,
                                                                     tracked_item.token_id))
                        self.stop_tracking_position(tracked_item.hb_id)

                    else:
                        if tracked_item.trading_pair.split("-")[0] == update_result["position"]["token0"]:
                            tracked_item.current_base_amount = amount0
                            tracked_item.current_quote_amount = amount1
                            tracked_item.unclaimed_base_amount = unclaimedToken0
                            tracked_item.unclaimed_quote_amount = unclaimedToken1
                        else:
                            tracked_item.current_base_amount = amount1
                            tracked_item.current_quote_amount = amount0
                            tracked_item.unclaimed_base_amount = unclaimedToken1
                            tracked_item.unclaimed_quote_amount = unclaimedToken0

    def add_position(self,
                     trading_pair: str,
                     fee_tier: Decimal,
                     base_amount: Decimal,
                     quote_amount: Decimal,
                     lower_price: Decimal,
                     upper_price: Decimal,
                     token_id: int = 0):
        hb_id = f"{trading_pair}-{get_tracking_nonce()}"
        safe_ensure_future(self._add_position(hb_id, trading_pair, fee_tier, base_amount, quote_amount,
                                              lower_price, upper_price, token_id))
        return hb_id

    def start_tracking_position(self,
                                hb_id: str,
                                trading_pair: str,
                                fee_tier: str,
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
                            fee_tier: str,
                            base_amount: Decimal,
                            quote_amount: Decimal,
                            lower_price: Decimal,
                            upper_price: Decimal,
                            token_id: int):
        """
        Calls add position end point to create/increase a range position.
        :param hb_id: Internal Hummingbot id
        :param trading_pair: The market trading pair of the pool
        :param fee_tier: The expected fee
        :param base_amount: The amount of base token to put into the pool
        :param lower_price: The lower bound of the price range
        :param upper_price: The upper bound of the price range
        :param token_id: The token id of position to be increased
        """
        base_amount = self.quantize_order_amount(trading_pair, base_amount)
        quote_amount = self.quantize_order_amount(trading_pair, quote_amount)
        lower_price = self.quantize_order_price(trading_pair, lower_price)
        upper_price = self.quantize_order_price(trading_pair, upper_price)
        base, quote = trading_pair.split("-")
        api_params = {"token0": base,
                      "token1": quote,
                      "fee": fee_tier,
                      "lowerPrice": str(lower_price),
                      "upperPrice": str(upper_price),
                      "amount0": str(base_amount),
                      "amount1": str(quote_amount),
                      "tokenId": token_id
                      }
        self.start_tracking_position(hb_id, trading_pair, fee_tier, base_amount, quote_amount,
                                     lower_price, upper_price)
        try:
            order_result = await self._api_request("post", "eth/uniswap/v3/add-position", api_params)
            tracked_pos = self._in_flight_positions[hb_id]
            tx_hash = order_result["hash"]
            tracked_pos.update_last_tx_hash(tx_hash)
            tracked_pos.gas_price = order_result.get("gasPrice")
            tracked_pos.last_status = UniswapV3PositionStatus.PENDING_CREATE
            self.logger().info(f"Adding liquidity for {trading_pair}, hb_id: {hb_id}, tx_hash: {tx_hash} "
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

    def remove_position(self, hb_id: str, token_id: str, reducePercent: Decimal = Decimal("100.0"), fee_estimate: bool = False):
        safe_ensure_future(self._remove_position(hb_id, token_id, reducePercent, fee_estimate))
        return hb_id

    async def _remove_position(self, hb_id: str, token_id: str, reducePercent: Decimal, fee_estimate: bool):
        """
        Calls remove position end point to remove/decrease a range position.
        :param hb_id: Internal Hummingbot id
        :param token_id: The token id of position to be increased
        :param reducePercent: The percentage of liquidity to remove from position with the specified token id
        :param fee_estimate: True if to get fee estimate to remove lp
        """
        tracked_pos = self._in_flight_positions.get(hb_id)
        await tracked_pos.get_last_tx_hash()
        tracked_pos.last_status = UniswapV3PositionStatus.PENDING_REMOVE
        tracked_pos.update_last_tx_hash(None)
        try:
            result = await self._api_request("post",
                                             "eth/uniswap/v3/remove-position",
                                             {"tokenId": token_id, "reducePercent": reducePercent, "getFee": str(fee_estimate)})
            if fee_estimate:
                return Decimal(str(result.get("gasFee")))
            else:
                hash = result.get("hash")
                action = "removal of" if reducePercent == Decimal("100.0") else \
                         f"{reducePercent}% reduction of liquidity for"
                self.logger().info(f"Initiated {action} of position with ID - {token_id}.")
                tracked_pos.update_last_tx_hash(hash)
                self.trigger_event(MarketEvent.RangePositionUpdated,
                                   RangePositionUpdatedEvent(self.current_timestamp, tracked_pos.hb_id,
                                                             tracked_pos.last_tx_hash, tracked_pos.token_id,
                                                             tracked_pos.base_amount, tracked_pos.quote_amount,
                                                             tracked_pos.last_status.name))
        except Exception as e:
            # self.stop_tracking_position(hb_id)
            if not fee_estimate:
                self.logger().network(
                    f"Error removing range position, token_id: {token_id}, hb_id: {hb_id}",
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

    async def get_price_by_fee_tier(self, trading_pair: str, tier: str, seconds: int = 1, twap: bool = False):
        """
        Get price on a specific fee tier.
        :param trading_pair: trading pair to fetch
        :param tier: tier to return
        :param seconds: number of seconds to get historical prices
        :param twap: if to return historical price from pool or current price over multiple pools
        """
        try:
            base, quote = trading_pair.split("-")
            resp = await self._api_request("post",
                                           "eth/uniswap/v3/price",
                                           {"base": base,
                                            "quote": quote,
                                            "tier": tier.upper(),
                                            "seconds": seconds})

            return resp.get("prices", []) if twap else Decimal(str(resp.get("price", "0")))
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().network(
                f"Error getting price for {trading_pair}.",
                exc_info=True,
                app_warning_msg=str(e)
            )

    @async_ttl_cache(ttl=5, maxsize=10)
    async def get_quote_price(self, trading_pair: str, is_buy: bool, amount: Decimal) -> Optional[Decimal]:
        """
        Retrieves a quote price.
        :param trading_pair: The market trading pair
        :param is_buy: True for an intention to buy, False for an intention to sell
        :param amount: The amount required (in base token unit)
        :return: The quote price.
        """

        try:
            base, quote = trading_pair.split("-")
            side = "buy" if is_buy else "sell"
            resp = await self._api_request("post",
                                           "eth/uniswap/price",
                                           {"base": base,
                                            "quote": quote,
                                            "side": side.upper(),
                                            "amount": amount})
            required_items = ["price", "gasLimit", "gasPrice", "gasCost"]
            if any(item not in resp.keys() for item in required_items):
                if "info" in resp.keys():
                    self.logger().info(f"Unable to get price. {resp['info']}")
                else:
                    self.logger().info(f"Missing data from price result. Incomplete return result for ({resp.keys()})")
            else:
                gas_limit = resp["gasLimit"]
                gas_price = resp["gasPrice"]
                gas_cost = resp["gasCost"]
                price = resp["price"]
                account_standing = {
                    "allowances": self._allowances,
                    "balances": self._account_balances,
                    "base": base,
                    "quote": quote,
                    "amount": amount,
                    "side": side,
                    "gas_limit": gas_limit,
                    "gas_price": gas_price,
                    "gas_cost": gas_cost,
                    "price": price
                }
                exceptions = check_transaction_exceptions(account_standing)
                for index in range(len(exceptions)):
                    self.logger().info(f"Warning! [{index+1}/{len(exceptions)}] {side} order - {exceptions[index]}")

                if price is not None and len(exceptions) == 0:
                    fee_overrides_config_map["uniswap_v3_maker_fixed_fees"].value = [
                        TokenAmount("ETH", Decimal(str(gas_cost)))
                    ]
                    fee_overrides_config_map["uniswap_v3_taker_fixed_fees"].value = [
                        TokenAmount("ETH", Decimal(str(gas_cost)))
                    ]
                    return Decimal(str(price))
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().network(
                f"Error getting quote price for {trading_pair}  {side} order for {amount} amount.",
                exc_info=True,
                app_warning_msg=str(e)
            )

    async def get_order_price(self, trading_pair: str, is_buy: bool, amount: Decimal) -> Decimal:
        """
        This is simply the quote price
        """
        return await self.get_quote_price(trading_pair, is_buy, amount)

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
        amount_approved = Decimal(str(resp.get("amount", "0")))
        if amount_approved > s_decimal_0:
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
        """router_allowances = await self._api_request("post", "eth/allowances",
                                                    {"tokenList": "[" + (",".join(['"' + t + '"' for t in self._tokens])) + "]",
                                                     "connector": "uniswapV3Router"})"""
        nft_allowances = await self._api_request("post", "eth/allowances",
                                                 {"tokenList": "[" + (",".join(['"' + t + '"' for t in self._tokens])) + "]",
                                                  "connector": "uniswapV3NFTManager"})
        """for token, amount in router_allowances["approvals"].items():
            try:
                ret_val["R" + token] = Decimal(str(amount))
            except Exception:
                ret_val["R" + token] = s_decimal_0"""
        for token, amount in nft_allowances["approvals"].items():
            try:
                ret_val["N" + token] = Decimal(str(amount))
            except Exception:
                ret_val["N" + token] = s_decimal_0
        return ret_val

    def has_allowances(self) -> bool:
        """
        Checks if all tokens have allowance (an amount approved)
        """
        return len(self._allowances.values()) == len(self._tokens) and \
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
