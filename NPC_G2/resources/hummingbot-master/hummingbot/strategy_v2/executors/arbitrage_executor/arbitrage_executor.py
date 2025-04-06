import asyncio
import logging
from decimal import Decimal
from typing import Dict, Union

from hummingbot.connector.utils import split_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.event.events import BuyOrderCreatedEvent, MarketOrderFailureEvent, SellOrderCreatedEvent
from hummingbot.core.rate_oracle.rate_oracle import RateOracle
from hummingbot.logger import HummingbotLogger
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from hummingbot.strategy_v2.executors.arbitrage_executor.data_types import ArbitrageExecutorConfig
from hummingbot.strategy_v2.executors.executor_base import ExecutorBase
from hummingbot.strategy_v2.models.base import RunnableStatus
from hummingbot.strategy_v2.models.executors import CloseType, TrackedOrder


class ArbitrageExecutor(ExecutorBase):
    _logger = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    @staticmethod
    def _are_tokens_interchangeable(first_token: str, second_token: str):
        interchangeable_tokens = [
            {"WETH", "ETH"},
            {"WBTC", "BTC"},
            {"WBNB", "BNB"},
            {"WPOL", "POL"},
            {"WAVAX", "AVAX"},
            {"WONE", "ONE"},
        ]
        same_token_condition = first_token == second_token
        tokens_interchangeable_condition = any(({first_token, second_token} <= interchangeable_pair
                                                for interchangeable_pair
                                                in interchangeable_tokens))
        # for now, we will consider all the stablecoins interchangeable
        stable_coins_condition = "USD" in first_token and "USD" in second_token
        return same_token_condition or tokens_interchangeable_condition or stable_coins_condition

    def __init__(self, strategy: ScriptStrategyBase, config: ArbitrageExecutorConfig, update_interval: float = 1.0):
        if not self.is_arbitrage_valid(pair1=config.buying_market.trading_pair,
                                       pair2=config.selling_market.trading_pair):
            raise Exception("Arbitrage is not valid since the trading pairs are not interchangeable.")
        super().__init__(strategy=strategy,
                         connectors=[config.buying_market.connector_name, config.selling_market.connector_name],
                         config=config, update_interval=update_interval)
        self.config = config
        self.buying_market = config.buying_market
        self.selling_market = config.selling_market
        self.min_profitability = config.min_profitability
        self.order_amount = config.order_amount
        self.max_retries = config.max_retries

        # Order tracking
        self._buy_order: TrackedOrder = TrackedOrder()
        self._sell_order: TrackedOrder = TrackedOrder()

        self._last_buy_price = Decimal("1")
        self._last_sell_price = Decimal("1")
        self._trade_pnl_pct = Decimal("0")
        self._last_tx_cost = Decimal("0")
        self._last_buy_fee = Decimal("0")
        self._last_sell_fee = Decimal("0")
        self._current_profitability = Decimal("0")
        self._amm_gas_amount = Decimal("0")
        self._amm_gas_cost = Decimal("0")

        # Quote asset conversion rate
        _, buy_quote_asset = split_hb_trading_pair(self.buying_market.trading_pair)
        _, sell_quote_asset = split_hb_trading_pair(self.selling_market.trading_pair)

        # Define the conversion trading pair (e.g., SOL/USDT or USDT/SOL)
        self.quote_conversion_pair = f"{sell_quote_asset}-{buy_quote_asset}"
        self.rate_oracle = RateOracle.get_instance()
        self._cumulative_failures = 0

    async def validate_sufficient_balance(self):
        base_asset_for_selling_exchange = self.connectors[self.selling_market.connector_name].get_available_balance(
            self.selling_market.trading_pair.split("-")[0])
        if self.order_amount > base_asset_for_selling_exchange:
            self.logger().info(f"Insufficient balance in exchange {self.selling_market.connector_name} "
                               f"to sell {self.selling_market.trading_pair.split('-')[0]} "
                               f"Actual: {base_asset_for_selling_exchange} --> Needed: {self.order_amount}")
            self.close_type = CloseType.INSUFFICIENT_BALANCE
            self.logger().error("Not enough budget to open position.")
            self.stop()
            return

        price = await self.get_resulting_price_for_amount(
            exchange=self.buying_market.connector_name,
            trading_pair=self.buying_market.trading_pair,
            is_buy=True,
            order_amount=self.order_amount)
        quote_asset_for_buying_exchange = self.connectors[self.buying_market.connector_name].get_available_balance(
            self.buying_market.trading_pair.split("-")[1])
        if self.order_amount * price > quote_asset_for_buying_exchange:
            self.logger().info(f"Insufficient balance in exchange {self.buying_market.connector_name} "
                               f"to buy {self.buying_market.trading_pair.split('-')[1]} "
                               f"Actual: {quote_asset_for_buying_exchange} --> Needed: {self.order_amount * price}")
            self.close_type = CloseType.INSUFFICIENT_BALANCE
            self.logger().error("Not enough budget to open position.")
            self.stop()
            return

    def is_arbitrage_valid(self, pair1, pair2):
        base_asset1, quote_asset1 = split_hb_trading_pair(pair1)
        base_asset2, quote_asset2 = split_hb_trading_pair(pair2)
        return self._are_tokens_interchangeable(base_asset1, base_asset2)

    def get_net_pnl_quote(self) -> Decimal:
        if self.close_type == CloseType.COMPLETED:
            sell_quote_amount = self.sell_order.order.executed_amount_base * self.sell_order.average_executed_price
            buy_quote_amount = self.buy_order.order.executed_amount_base * self.buy_order.average_executed_price
            return sell_quote_amount - buy_quote_amount - self.cum_fees_quote
        else:
            return Decimal("0")

    def get_net_pnl_pct(self) -> Decimal:
        if self.is_closed:
            if self.buy_order.order and self.buy_order.order.executed_amount_base > 0:
                return self.net_pnl_quote / self.buy_order.order.executed_amount_base
            else:
                return Decimal("0")
        else:
            return Decimal("0")

    def get_cum_fees_quote(self) -> Decimal:
        return self.buy_order.cum_fees_quote + self.sell_order.cum_fees_quote

    @property
    def buy_order(self) -> TrackedOrder:
        return self._buy_order

    @buy_order.setter
    def buy_order(self, value: TrackedOrder):
        self._buy_order = value

    @property
    def sell_order(self) -> TrackedOrder:
        return self._sell_order

    @sell_order.setter
    def sell_order(self, value: TrackedOrder):
        self._sell_order = value

    async def get_resulting_price_for_amount(self, exchange: str, trading_pair: str, is_buy: bool,
                                             order_amount: Decimal):
        return await self.connectors[exchange].get_quote_price(trading_pair, is_buy, order_amount)

    async def control_task(self):
        if self.status == RunnableStatus.RUNNING:
            try:
                await self.update_trade_pnl_pct()
                await self.update_tx_cost()
                self._current_profitability = (self._trade_pnl_pct * self.order_amount - self._last_tx_cost) / self.order_amount
                if self._current_profitability > self.min_profitability:
                    await self.execute_arbitrage()
            except Exception as e:
                self.logger().error(f"Error calculating profitability: {e}")
        elif self.status == RunnableStatus.SHUTTING_DOWN:
            if self._cumulative_failures > self.max_retries:
                self.close_type = CloseType.FAILED
                self.stop()
            else:
                self.check_order_status()

    def early_stop(self, keep_position: bool = False):
        self.close_type = CloseType.EARLY_STOP
        self.stop()

    def check_order_status(self):
        if self.buy_order.order and self.buy_order.order.is_filled and \
                self.sell_order.order and self.sell_order.order.is_filled:
            self.close_type = CloseType.COMPLETED
            self.stop()

    async def execute_arbitrage(self):
        self._status = RunnableStatus.SHUTTING_DOWN
        self.place_buy_arbitrage_order()
        self.place_sell_arbitrage_order()

    def place_buy_arbitrage_order(self):
        self.buy_order.order_id = self.place_order(
            connector_name=self.buying_market.connector_name,
            trading_pair=self.buying_market.trading_pair,
            order_type=OrderType.MARKET,
            side=TradeType.BUY,
            amount=self.order_amount,
            price=self._last_buy_price,
        )

    def place_sell_arbitrage_order(self):
        self.sell_order.order_id = self.place_order(
            connector_name=self.selling_market.connector_name,
            trading_pair=self.selling_market.trading_pair,
            order_type=OrderType.MARKET,
            side=TradeType.SELL,
            amount=self.order_amount,
            price=self._last_sell_price,
        )

    async def update_tx_cost(self):
        base, quote = split_hb_trading_pair(trading_pair=self.buying_market.trading_pair)
        # TODO: also due the fact that we don't have a good rate oracle source we have to use a fixed token
        base_without_wrapped = base[1:] if base.startswith("W") else base
        buy_fee = await self.get_tx_cost_in_asset(
            exchange=self.buying_market.connector_name,
            trading_pair=self.buying_market.trading_pair,
            is_buy=True,
            order_amount=self.order_amount,
            asset=base_without_wrapped
        )
        sell_fee = await self.get_tx_cost_in_asset(
            exchange=self.selling_market.connector_name,
            trading_pair=self.selling_market.trading_pair,
            is_buy=False,
            order_amount=self.order_amount,
            asset=base_without_wrapped)
        self._last_buy_fee = buy_fee
        self._last_sell_fee = sell_fee
        self._last_tx_cost = self._last_buy_fee + self._last_sell_fee

    async def get_buy_and_sell_prices(self):
        buy_price_task = asyncio.create_task(self.get_resulting_price_for_amount(
            exchange=self.buying_market.connector_name,
            trading_pair=self.buying_market.trading_pair,
            is_buy=True,
            order_amount=self.order_amount))
        sell_price_task = asyncio.create_task(self.get_resulting_price_for_amount(
            exchange=self.selling_market.connector_name,
            trading_pair=self.selling_market.trading_pair,
            is_buy=False,
            order_amount=self.order_amount))

        buy_price, sell_price = await asyncio.gather(buy_price_task, sell_price_task)
        return buy_price, sell_price

    async def update_trade_pnl_pct(self):
        self._last_buy_price, self._last_sell_price = await self.get_buy_and_sell_prices()

        if not self._last_buy_price or not self._last_sell_price:
            raise Exception("Could not get buy and sell prices")

        # Fetch the conversion rate between quote assets
        conversion_rate = await self.get_quote_asset_conversion_rate()

        # Normalize the sell price to the same quote asset as the buy price
        normalized_sell_price = self._last_sell_price * conversion_rate

        # Calculate the profitability (PnL percentage)
        self._trade_pnl_pct = (normalized_sell_price - self._last_buy_price) / self._last_buy_price

    async def get_quote_asset_conversion_rate(self) -> Decimal:
        """
        Fetch the conversion rate between the quote assets of the buying and selling markets.
        Example: For M3M3/USDT and M3M3/SOL, fetch the SOL/USDT rate.
        """
        # Fetch the conversion rate from the connector
        try:
            conversion_rate = self.rate_oracle.get_pair_rate(self.quote_conversion_pair)
            return conversion_rate
        except Exception as e:
            self.logger().error(f"Error fetching conversion rate for {self.quote_conversion_pair}: {e}")
            raise

    async def get_tx_cost_in_asset(self, exchange: str, trading_pair: str, is_buy: bool, order_amount: Decimal,
                                   asset: str):
        connector = self.connectors[exchange]
        price = await self.get_resulting_price_for_amount(exchange, trading_pair, is_buy, order_amount)
        if self.is_amm_connector(exchange=exchange):
            gas_cost = connector.network_transaction_fee
            return gas_cost.amount / self.config.gas_conversion_price
        else:
            fee = connector.get_fee(
                base_currency=asset,
                quote_currency=asset,
                order_type=OrderType.MARKET,
                order_side=TradeType.BUY if is_buy else TradeType.SELL,
                amount=order_amount,
                price=price,
                is_maker=False
            )
            return fee.fee_amount_in_token(
                trading_pair=trading_pair,
                price=price,
                order_amount=order_amount,
                token=asset,
                exchange=connector,
            )

    def process_order_created_event(self, _, market, event: Union[BuyOrderCreatedEvent, SellOrderCreatedEvent]):
        if self.buy_order.order_id == event.order_id:
            self.buy_order.order = self.get_in_flight_order(self.buying_market.connector_name, event.order_id)
            self.logger().info("Buy Order Created")
        elif self.sell_order.order_id == event.order_id:
            self.logger().info("Sell Order Created")
            self.sell_order.order = self.get_in_flight_order(self.selling_market.connector_name, event.order_id)

    def process_order_failed_event(self, _, market, event: MarketOrderFailureEvent):
        if self.buy_order.order_id == event.order_id:
            self.place_buy_arbitrage_order()
            self._cumulative_failures += 1
        elif self.sell_order.order_id == event.order_id:
            self.place_sell_arbitrage_order()
            self._cumulative_failures += 1

    def get_custom_info(self) -> Dict:
        return {
            "buy_connector": self.buying_market.connector_name,
            "sell_connector": self.selling_market.connector_name,
            "buy_pair": self.buying_market.trading_pair,
            "sell_pair": self.selling_market.trading_pair,
            "buy_price": self._last_buy_price,
            "sell_price": self._last_sell_price,
            "trade_pnl_pct": self._trade_pnl_pct,
            # "amm_gas_price": self.config.gas_conversion_price,
            # "amm_gas_amount": self._amm_gas_amount,
            # "amm_gas_cost": self._amm_gas_cost,
            # "buy_fee": self._last_buy_fee,
            # "sell_fee": self._last_sell_fee,
            # "total_fee": self._last_tx_cost,
            "tx_cost_pct": self._last_tx_cost / self.order_amount,
            "profit_pct": self._current_profitability,
            "failures": self._cumulative_failures,
        }

    def to_format_status(self):
        lines = []
        if self._last_buy_price and self._last_sell_price:
            trade_pnl_pct = (self._last_sell_price - self._last_buy_price) / self._last_buy_price
            tx_cost_pct = self._last_tx_cost / self.order_amount
            base, quote = split_hb_trading_pair(trading_pair=self.buying_market.trading_pair)
            lines.extend([f"""
    Arbitrage Status: {self.status} | Close Type: {self.close_type}
    - BUY: {self.buying_market.connector_name}:{self.buying_market.trading_pair}  --> SELL: {self.selling_market.connector_name}:{self.selling_market.trading_pair} | Amount: {self.order_amount:.2f}
    - Trade PnL (%): {trade_pnl_pct * 100:.2f} % | TX Cost (%): -{tx_cost_pct * 100:.2f} % | Net PnL (%): {(trade_pnl_pct - tx_cost_pct) * 100:.2f} %
    -------------------------------------------------------------------------------
    """])
            if self.close_type == CloseType.COMPLETED:
                lines.extend([f"Total Profit (%): {self.net_pnl_pct * 100:.2f} | Total Profit ({quote}): {self.net_pnl_quote:.4f}"])
            return lines
        else:
            msg = ["There was an error while formatting the status for the executor."]
            self.logger().warning(msg)
            return lines.extend(msg)
