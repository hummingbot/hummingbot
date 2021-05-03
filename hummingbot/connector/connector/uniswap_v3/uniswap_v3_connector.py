import asyncio
from decimal import Decimal
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.connector.connector.uniswap.uniswap_connector import UniswapConnector
from hummingbot.core.event.events import (
    MarketEvent,
    RangePositionCreatedEvent,
    RangePositionRemovedEvent,
    RangePositionLiquidityAdjustedEvent
)
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce


class UniswapV3Connector(UniswapConnector):
    """
    UniswapV3Connector extends UniswapConnector to provide v3 specific functionality, e.g. ranged positions
    """

    # @property
    # def version(self) -> int:
    #     return 3

    @property
    def name(self) -> str:
        return "uniswap_v3"

    def add_position(self,
                     trading_pair: str,
                     fee_pct: Decimal,
                     base_amount: Decimal,
                     quote_amount: Decimal,
                     lower_price: Decimal,
                     upper_price: Decimal):
        hb_id = f"{trading_pair}-{get_tracking_nonce()}"
        safe_ensure_future(self._add_position(hb_id, trading_pair, fee_pct, base_amount, quote_amount,
                                              lower_price, upper_price))
        return hb_id

    async def _add_position(self,
                            hb_id: str,
                            trading_pair: str,
                            fee_pct: Decimal,
                            base_amount: Decimal,
                            quote_amount: Decimal,
                            lower_price: Decimal,
                            upper_price: Decimal):
        """
        Calls add position end point to create a new range position.
        :param hb_id: Internal Hummingbot id
        :param trading_pair: The market trading pair of the pool
        :param fee_pct: The expected fee in percentage value
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
                      "fee": str(fee_pct),
                      "tickLower": str(lower_price),
                      "tickUpper": str(upper_price),
                      "amount0": str(base_amount),
                      "amount1": str(quote_amount),
                      }
        try:
            order_result = await self._api_request("post", "uniswap/v3/add-position", api_params)
            token_id = order_result.get("tokenId")
            # gas_price = order_result.get("gasPrice")
            # gas_limit = order_result.get("gasLimit")
            # gas_cost = order_result.get("gasCost")
            # self.start_tracking_order(order_id, None, trading_pair, trade_type, price, amount, gas_price)
            # tracked_order = self._in_flight_orders.get(order_id)
            # if tracked_order is not None:
            self.logger().info(f"Created range position for {trading_pair}, hb_id: {hb_id}, token_id: {token_id} "
                               f"amount: {base_amount} ({base}) {quote_amount}) ({quote}), "
                               f"range: {lower_price} - {upper_price}")
            # f"Estimated Gas Cost: {gas_cost} ETH "
            # f" (gas limit: {gas_limit}, gas price: {gas_price})")
            # tracked_order.update_exchange_order_id(hash)
            # tracked_order.gas_price = gas_price
            if token_id is not None:
                # tracked_order.fee_asset = "ETH"
                # tracked_order.executed_amount_base = amount
                # tracked_order.executed_amount_quote = amount * price
                self.trigger_event(
                    MarketEvent.RangePositionCreated,
                    RangePositionCreatedEvent(
                        self.current_timestamp,
                        hb_id,
                        token_id,
                        trading_pair,
                        fee_pct,
                        lower_price,
                        upper_price,
                        base_amount,
                        quote_amount
                    )
                )
            # else:
            #     self.trigger_event(MarketEvent.OrderFailure,
            #                        MarketOrderFailureEvent(self.current_timestamp, order_id, OrderType.LIMIT))
        except asyncio.CancelledError:
            raise
        except Exception as e:
            # self.stop_tracking_order(order_id)
            self.logger().network(
                f"Error submitting range position to Uniswap for {trading_pair} "
                "hb_id: {hb_id}, token_id: {token_id} "
                f"amount: {base_amount} ({base}) {quote_amount}) ({quote}), "
                f"range: {lower_price} - {upper_price}",
                exc_info=True,
                app_warning_msg=str(e)
            )
            # self.trigger_event(MarketEvent.OrderFailure,
            #                    MarketOrderFailureEvent(self.current_timestamp, order_id, OrderType.LIMIT))

    def remove_position(self, hb_id: str, token_id: str):
        safe_ensure_future(self._remove_position(hb_id, token_id))

    async def _remove_position(self, hb_id: str, token_id: str):
        result = await self._api_request("post", "uniswap/v3/remove-position", {"tokenId": token_id})
        if result.get("success", False):
            self.logger().info(f"Successfully removed position {token_id}.")
            # self.c_stop_tracking_order(order_id)
            self.trigger_event(MarketEvent.RangePositionRemoved,
                               RangePositionRemovedEvent(self.current_timestamp, hb_id, token_id))
        return result

    def adjust_liquidity(self, hb_id: str, token_id: str, base_amount: Decimal, quote_amount: Decimal):
        safe_ensure_future(self._adjust_liquidity(hb_id, token_id, base_amount, quote_amount))

    async def _adjust_liquidity(self, hb_id: str, token_id: str, base_amount: Decimal, quote_amount: Decimal):
        result = await self._api_request("post", "uniswap/v3/adjust-liquidity",
                                         {
                                             "tokenId": token_id,
                                             "amount0": base_amount,
                                             "amount1": quote_amount
                                         })
        if result.get("success", False):
            self.logger().info(f"Successfully adjusted position liquidty {token_id}.")
            # self.c_stop_tracking_order(order_id)
            self.trigger_event(MarketEvent.RangePositionLiquidityAdjusted,
                               RangePositionLiquidityAdjustedEvent(self.current_timestamp, hb_id, token_id))
        return result

    async def get_position(self, token_id: str):
        result = await self._api_request("post", "uniswap/v3/position", {"tokenId": token_id})
        return result

    async def collect_fees(self, token_id: str):
        result = await self._api_request("post", "uniswap/v3/collect-fees", {"tokenId": token_id})
        return result
