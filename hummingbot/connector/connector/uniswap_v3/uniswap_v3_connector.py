import asyncio
from decimal import Decimal
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.connector.connector.uniswap.uniswap_connector import UniswapConnector
from hummingbot.core.event.events import RangePositionCreatedEvent, MarketEvent
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce


class UniswapV3Connector(UniswapConnector):
    """
    UniswapV3Connector extends UniswapConnector to provide v3 specific functionality, e.g. ranged positions
    """

    @property
    def name(self):
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
