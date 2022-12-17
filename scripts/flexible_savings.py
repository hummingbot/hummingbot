# Requires additional Python dependencies to be installed:
#
# - aiolimiter
# - asyncstdlib
# - tenacity
#
# Additionally, the following dev dependencies can be installed:
#
# - types-simplejson

import asyncio
import logging
from collections import defaultdict
from decimal import Decimal
from typing import Dict, List, Literal, Optional

from hummingbot.client.settings import ConnectorSetting
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.core.clock import Clock
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.event.events import BuyOrderCompletedEvent, SellOrderCompletedEvent
from hummingbot.core.rate_oracle.rate_oracle import RateOracle
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from juno import Chandler, time
from juno.connectors import BinanceConnector, BinancePaperTradeConnector, Connector
from juno.custodians import Custodian, SavingsCustodian, SpotCustodian
from juno.indicators import FourWeekRule
from juno.models import Candle
from juno.storages import SQLite


class FlexibleSavings(ScriptStrategyBase):
    """
    NB! Currently only works with Binance.

    A directional strategy. However, the purpose of this script is not the strategy itself but the usage of a
    *custodian*. A custodian is a component that is responsible for holding your assets while they are not in active
    use, such as required for an open order. This is useful mainly when dealing with low-frequency strategies that
    operate on daily candles, for example.

    An example of a custodian can be Binance's savings custodian. When trading BTC-USDT, instead of holding your assets
    in a spot account, it may decide to hold them in a flexible savings account instead. A flexible savings account
    does not lock up the assets so that they can be redeemed for trading immediately at any point in time. This allows,
    in addition to the profits from the strategy itself, to also earn daily interest on the assets.

    Another example could be a Cardano custodian. The staking on the Cardano blockchain is unique in the sense that to
    earn staking rewards, you only need to have ADA in your wallet during the beginning of an epoch for the staking
    snapshot. This means that every 5 days when the snapshot is about to happen, the custodian could withdraw your
    ADA, lock in the staking rewards and deposit the ADA back to the exchange for trading.

    The strategy implemented here is called the Four-Week Rule strategy. In its original form, it looks at the closing
    prices of daily candles. If the current price is higher than the maximum of the past 4 weeks, it opens a long
    position. If the current price is lower than the minimum of the past 4 weeks, it opens a short position. This makes
    it a "breakout" strategy that tries to catch big price moves. Works well in a trending market. Not so well in a
    side-ways market. Additionally, a simple moving average is used to exit positions early and lock in profits and
    minimizelosses. The moving average is typically half the duration, which is 2 weeks long. More info can be found at
    https://www.investopedia.com/articles/technical/02/052102.asp.
    """

    # Config.
    connector_name: Literal["binance", "binance_paper_trade"] = "binance"
    custodian_name: Literal["spot", "savings"] = "savings"
    base_asset = "BTC"
    quote_asset = "USDT"
    four_week_rule_period = 4
    four_week_rule_moving_average_period = 2
    four_week_rule_interval = time.MIN_MS

    # Computed.
    trading_pair = f"{base_asset}-{quote_asset}"

    # Lifecycle params.
    async_task: Optional[asyncio.Task] = None
    is_script_ready: asyncio.Event

    # Strategy.
    four_week_rule: FourWeekRule

    custodian: Custodian
    juno_connector: Connector

    completed_orders: Dict[str, asyncio.Event] = defaultdict(asyncio.Event)

    current_open_position: Optional[Literal["Long", "Short"]] = None
    closed_position_count = 0

    initial_asset_amounts: Dict[str, Decimal] = {}

    # Script params.
    markets = {connector_name: {trading_pair}}

    @property
    def connector(self) -> ExchangeBase:
        return self.connectors[self.connector_name]

    @property
    def order_book(self) -> OrderBook:
        return self.connector.order_books[self.trading_pair]

    def __init__(self, connectors: Dict[str, ConnectorSetting]) -> None:
        super().__init__(connectors)

        self.is_script_ready = asyncio.Event()

        self.four_week_rule = FourWeekRule(
            period=self.four_week_rule_period,
            moving_average_period=self.four_week_rule_moving_average_period,
        )
        self.log_with_clock(logging.INFO, f"{type(self.four_week_rule).__name__} strategy ready.")

        # Setup juno connector.
        if self.connector_name == "binance_paper_trade":
            self.juno_connector = BinancePaperTradeConnector()
        elif self.connector_name == "binance":
            self.juno_connector = BinanceConnector(
                api_key=self.connector.authenticator.api_key,
                secret_key=self.connector.authenticator.secret_key,
            )
        else:
            raise NotImplementedError()
        self.log_with_clock(logging.INFO, f"{type(self.juno_connector).__name__} connector ready.")

        # Setup custodian.
        if self.custodian_name == "spot":
            self.custodian = SpotCustodian()
        elif self.custodian_name == "savings":
            self.custodian = SavingsCustodian(
                connectors={self.connector_name: self.juno_connector},
                hb_connectors=self.connectors,
            )
        else:
            raise NotImplementedError()
        self.log_with_clock(logging.INFO, f"{type(self.custodian).__name__} custodian ready.")

    def start(self, clock: Clock, timestamp: float) -> None:
        super().start(clock, timestamp)
        self.async_task = safe_ensure_future(self.setup())

    def on_tick(self) -> None:
        self.is_script_ready.set()

    def stop(self, clock: Clock) -> None:
        if self.async_task:
            self.async_task.cancel()
        super().stop(clock)

    def did_complete_buy_order(self, event: BuyOrderCompletedEvent) -> None:
        self.completed_orders[event.order_id].set()

    def did_complete_sell_order(self, event: SellOrderCompletedEvent) -> None:
        self.completed_orders[event.order_id].set()

    async def setup(self) -> None:
        # Setup before the script is ready.
        chandler = Chandler(storage=SQLite(), connectors={self.connector_name: self.juno_connector})
        async with self.juno_connector:

            # Wait for connectors, etc, to be loaded.
            await self.is_script_ready.wait()

            # Store initial total assets for profit calculation later on.
            self.initial_asset_amounts = self.get_asset_amounts()

            try:
                # Move all funds to savings account.
                base_amount = self.connector.get_available_balance(self.base_asset)
                quote_amount = self.connector.get_available_balance(self.quote_asset)
                await asyncio.gather(
                    self.custodian.release(self.connector_name, self.base_asset, base_amount),
                    self.custodian.release(self.connector_name, self.quote_asset, quote_amount),
                )

                # Stream candles.
                now = time.now()
                warmup_start = now - self.four_week_rule_period * self.four_week_rule_interval
                real_start = time.floor_timestamp(now, self.four_week_rule_interval)
                async for candle in chandler.stream_candles(
                    connector_name=self.connector_name,
                    trading_pair=self.trading_pair,
                    interval=self.four_week_rule_interval,
                    start=warmup_start,
                ):
                    await self.on_candle(candle=candle, is_warmup=candle.time < real_start)
            finally:
                # Close any open position.
                if self.current_open_position is not None:
                    await self.close_position()

                # Move all funds back to spot account.
                base_savings_asset = self.custodian.to_savings_asset(self.base_asset)
                quote_savings_asset = self.custodian.to_savings_asset(self.quote_asset)
                base_amount = self.connector.get_available_balance(base_savings_asset)
                quote_amount = self.connector.get_available_balance(quote_savings_asset)
                await asyncio.gather(
                    self.custodian.acquire(self.connector_name, self.base_asset, base_amount),
                    self.custodian.acquire(self.connector_name, self.quote_asset, quote_amount),
                )

    async def on_candle(self, candle: Candle, is_warmup: bool) -> None:
        self.log_with_clock(logging.INFO, f"Received candle with time {time.format_timestamp(candle.time)}.")

        # Update strategy for new advice.
        advice = self.four_week_rule.update(candle)

        # Do not open any position while processing historical "warm-up" candles.
        if is_warmup:
            return

        self.log_with_clock(logging.INFO, f"Received advice: {advice}.")

        # Close any open position if necessary.
        if (self.current_open_position == "Long" and advice in {"Liquidate", "Short"}) or (
            self.current_open_position == "Short" and advice in {"Liquidate", "Long"}
        ):
            await self.close_position()

        # Open new positions if necessary.
        # We would use `advice in {"Long", "Short"}` here but mypy doesn't infer type correctly when opening position.
        if self.current_open_position is None and (advice == "Long" or advice == "Short"):
            await self.open_position(advice)

    async def open_position(self, type: Literal["Long", "Short"]) -> None:
        if type == "Short":
            self.log_with_clock(logging.INFO, "Would have opened short position but currently not supported.")
            return

        self.log_with_clock(logging.INFO, f"Opening {type} position.")

        self.current_open_position = "Long"

        # Acquire funds from custodian.
        quote_amount = self.connector.get_available_balance(self.custodian.to_savings_asset(self.quote_asset))
        await self.custodian.acquire(self.connector_name, self.quote_asset, quote_amount)

        # Buy.
        result = self.order_book.get_price_for_quote_volume(
            is_buy=True,
            quote_volume=quote_amount,
        )
        price = Decimal(result.result_price)
        order_candidate = OrderCandidate(
            trading_pair=self.trading_pair,
            is_maker=False,
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            amount=quote_amount / price,
            price=price,
        )
        (order,) = self.connector.budget_checker.adjust_candidates([order_candidate], all_or_none=False)
        client_order_id = self.buy(
            connector_name=self.connector_name,
            trading_pair=order.trading_pair,
            amount=order.amount,
            price=order.price,
            order_type=order.order_type,
        )
        await self.wait_order_completed(client_order_id)

        # Release funds to custodian.
        base_amount = self.connector.get_available_balance(self.base_asset)
        await self.custodian.release(self.connector_name, self.base_asset, base_amount)

        self.log_with_clock(logging.INFO, f"Opened {type} position.")

    async def close_position(self) -> None:
        self.log_with_clock(logging.INFO, "Closing long position.")

        # Acquire funds from custodian.
        base_amount = self.connector.get_available_balance(self.custodian.to_savings_asset(self.base_asset))
        await self.custodian.acquire(self.connector_name, self.base_asset, base_amount)

        # Sell.
        amount = self.connector.quantize_order_amount(self.trading_pair, base_amount)
        result = self.order_book.get_price_for_volume(is_buy=False, volume=amount)
        price = Decimal(result.result_price)
        order_candidate = OrderCandidate(
            trading_pair=self.trading_pair,
            is_maker=False,
            order_type=OrderType.LIMIT,
            order_side=TradeType.SELL,
            amount=amount,
            price=price,
        )
        (order,) = self.connector.budget_checker.adjust_candidates([order_candidate], all_or_none=False)
        client_order_id = self.sell(
            connector_name=self.connector_name,
            trading_pair=order.trading_pair,
            order_type=order.order_type,
            amount=order.amount,
            price=order.price,
        )
        await self.wait_order_completed(client_order_id)

        # Release funds to custodian.
        quote_amount = self.connector.get_available_balance(self.quote_asset)
        await self.custodian.release(self.connector_name, self.quote_asset, quote_amount)

        self.current_open_position = None
        self.closed_position_count += 1

        self.log_with_clock(logging.INFO, "Closed long position.")

    async def wait_order_completed(self, client_order_id: str) -> None:
        await asyncio.wait_for(
            self.completed_orders[client_order_id].wait(),
            timeout=10.0,
        )

    def format_status(self) -> str:
        if not self.ready_to_trade:
            return "Market connectors are not ready."

        lines = [""]

        # Balances.
        lines.extend(
            ["  Balances:"]
            + ["    " + line for line in self.get_balance_df().to_string(index=False).split("\n")]
            + [""]
        )

        # Open positions.
        lines.extend(
            [
                f"  Currently Open Position: {str(self.current_open_position)}",
                f"  Number of Positions Closed: {self.closed_position_count}",
                "",
            ]
        )

        # Profit and loss.
        initial_assets_value = self.calculate_assets_value(self.initial_asset_amounts)
        current_assets_value = self.calculate_assets_value(self.get_asset_amounts())
        display_decimals = 2
        if initial_assets_value > 0:
            profit_percentage = round(((current_assets_value / initial_assets_value) - 1) * 100, display_decimals)
            lines.extend(
                [
                    "  Profit & Loss:",
                    f"    Initial Portfolio Value: {round(initial_assets_value, display_decimals)} {self.quote_asset}",
                    f"    Current Portfolio Value: {round(current_assets_value, display_decimals)} {self.quote_asset}",
                    f"    Profit: {profit_percentage}%",
                    "",
                ]
            )

        # Warnings.
        warning_lines = []
        warning_lines.extend(self.network_warning(self.get_market_trading_pair_tuples()))
        if len(warning_lines) > 0:
            lines.extend(["", "*** WARNINGS ***"] + warning_lines)

        return "\n".join(lines)

    def get_assets(self, connector_name: str) -> List[str]:
        assets = super().get_assets(connector_name)
        assets.extend([self.custodian.to_savings_asset(asset) for asset in assets])
        return sorted(set(assets))

    def get_asset_amounts(self) -> Dict[str, Decimal]:
        return {asset: self.connector.get_balance(asset) for asset in self.get_assets(self.connector_name)}

    def calculate_assets_value(self, asset_amounts: Dict[str, Decimal]) -> Decimal:
        conversion_rate = RateOracle.get_instance().get_pair_rate(self.trading_pair)
        total = Decimal("0.0")
        for asset, amount in asset_amounts.items():
            asset = self.custodian.from_savings_asset(asset)
            if asset == self.quote_asset:
                total += amount
            elif asset == self.base_asset:
                total += amount * conversion_rate
            else:
                raise NotImplementedError()
        return total
