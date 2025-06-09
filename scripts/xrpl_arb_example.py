import logging
import os
import time
from decimal import Decimal
from typing import Any, Dict

import pandas as pd
from pydantic import Field

from hummingbot.client.config.config_data_types import BaseClientModel
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.connector.exchange.xrpl.xrpl_exchange import XrplExchange
from hummingbot.connector.exchange.xrpl.xrpl_utils import PoolInfo
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.event.events import OrderFilledEvent
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class XRPLSimpleArbConfig(BaseClientModel):
    script_file_name: str = Field(default_factory=lambda: os.path.basename(__file__))
    trading_pair_xrpl: str = Field(
        "XRP-RLUSD", json_schema_extra={"prompt": "Trading pair on XRPL(e.g. XRP-RLUSD)", "prompt_on_new": True}
    )
    cex_exchange: str = Field(
        "binance", json_schema_extra={"prompt": "CEX exchange(e.g. binance)", "prompt_on_new": True}
    )
    trading_pair_cex: str = Field(
        "XRP-FDUSD", json_schema_extra={"prompt": "Trading pair on CEX(e.g. XRP-FDUSD)", "prompt_on_new": True}
    )
    order_amount_in_base: Decimal = Field(
        Decimal("1.0"), json_schema_extra={"prompt": "Order amount in base", "prompt_on_new": True}
    )
    min_profitability: Decimal = Field(
        Decimal("0.01"), json_schema_extra={"prompt": "Minimum profitability", "prompt_on_new": True}
    )
    refresh_interval_secs: int = Field(
        1,
        json_schema_extra={
            "prompt": "Refresh interval in seconds",
            "prompt_on_new": True,
        },
    )
    test_xrpl_order: bool = Field(False, json_schema_extra={"prompt": "Test XRPL order", "prompt_on_new": True})


class XRPLSimpleArb(ScriptStrategyBase):
    """
    This strategy monitors XRPL DEX prices and add liquidity to AMM Pools when the price is within a certain range.
    Remove liquidity if the price is outside the range.
    It uses a connector to get the current price and manage liquidity in AMM Pools
    """

    @classmethod
    def init_markets(cls, config: XRPLSimpleArbConfig):
        cls.markets = {"xrpl": {config.trading_pair_xrpl}, config.cex_exchange: {config.trading_pair_cex}}

    def __init__(self, connectors: Dict[str, ConnectorBase], config: XRPLSimpleArbConfig):
        super().__init__(connectors)
        self.config = config
        self.exchange_xrpl = "xrpl"
        self.exchange_cex = config.cex_exchange
        self.base_xrpl, self.quote_xrpl = self.config.trading_pair_xrpl.split("-")
        self.base_cex, self.quote_cex = self.config.trading_pair_cex.split("-")

        # State tracking
        self.connectors_ready = False
        self.connector_instance_xrpl: XrplExchange = self.connectors[self.exchange_xrpl]
        self.connector_instance_cex: ExchangePyBase = self.connectors[self.exchange_cex]
        self.last_refresh_time = 0  # Track last refresh time
        self.amm_info: PoolInfo | None = None

        # Log startup information
        self.logger().info("Starting XRPLTriggeredLiquidity strategy")

        # Check connector status
        self.check_connector_status()

    def check_connector_status(self):
        """Check if the connector is ready"""
        if not self.connector_instance_xrpl.ready:
            self.logger().info("XRPL connector not ready yet, waiting...")
            self.connectors_ready = False
            return
        else:
            self.connectors_ready = True
            self.logger().info("XRPL connector ready")

        if not self.connector_instance_cex.ready:
            self.logger().info("CEX connector not ready yet, waiting...")
            self.connectors_ready = False
            return
        else:
            self.connectors_ready = True
            self.logger().info("CEX connector ready")

    def on_tick(self):
        """Main loop to check price and manage liquidity"""
        current_time = time.time()
        if current_time - self.last_refresh_time < self.config.refresh_interval_secs:
            return
        self.last_refresh_time = current_time

        if not self.connectors_ready:
            self.check_connector_status()
            return

        if self.connector_instance_xrpl is None:
            self.logger().error("XRPL connector instance is not available.")
            return

        if self.connector_instance_cex is None:
            self.logger().error("CEX connector instance is not available.")
            return

        safe_ensure_future(self.get_amm_info())

        if self.amm_info is None:
            return

        # Test XRPL order
        if self.config.test_xrpl_order:
            if not hasattr(self, "_test_order_placed"):
                self.test_place_order()
            self._test_order_placed = True
            return

        vwap_prices = self.get_vwap_prices_for_amount(self.config.order_amount_in_base)
        proposal = self.check_profitability_and_create_proposal(vwap_prices)
        if len(proposal) > 0:
            proposal_adjusted: Dict[str, OrderCandidate] = self.adjust_proposal_to_budget(proposal)
            # self.place_orders(proposal_adjusted)

            self.logger().info(f"Proposal: {proposal}")
            self.logger().info(f"Proposal adjusted: {proposal_adjusted}")

    async def on_stop(self):
        """Stop the strategy and close any open positions"""
        pass

    async def get_amm_info(self):
        self.amm_info = await self.connector_instance_xrpl.amm_get_pool_info(trading_pair=self.config.trading_pair_xrpl)

    def format_status(self) -> str:
        """
        Returns status of the current strategy on user balances and current active orders. This function is called
        when status command is issued. Override this function to create custom status display output.
        """
        if not self.ready_to_trade:
            return "Market connectors are not ready."

        if self.amm_info is None:
            return "XRPL AMM info not available."

        lines = []
        warning_lines = []
        warning_lines.extend(self.network_warning(self.get_market_trading_pair_tuples()))

        balance_df = self.get_balance_df()
        lines.extend(["", "  Balances:"] + ["    " + line for line in balance_df.to_string(index=False).split("\n")])

        vwap_prices = self.get_vwap_prices_for_amount(self.config.order_amount_in_base)

        # Display VWAP prices (formatted)
        if vwap_prices:  # Check if vwap_prices dictionary is populated
            df_vwap_display_data = {}
            for ex, pr_data in vwap_prices.items():
                bid_price = pr_data.get("bid", Decimal("0"))  # Use .get for safety
                ask_price = pr_data.get("ask", Decimal("0"))
                df_vwap_display_data[ex] = {"bid": f"{bid_price:.6f}", "ask": f"{ask_price:.6f}"}
            lines.extend(
                ["", "  VWAP Prices for amount (Quote/Base)"]
                + ["     " + line for line in pd.DataFrame(df_vwap_display_data).to_string().split("\\n")]
            )

            # Display VWAP Prices with Fees
            # self.amm_info is guaranteed to be not None here due to the early return in format_status.
            fees = self.get_fees_percentages(vwap_prices)
            if fees:  # Check if fees dict is populated
                vwap_prices_with_fees_display_data = {}
                for exchange, prices_data in vwap_prices.items():
                    # Ensure the exchange exists in fees; if not, fee is 0, which is a safe default.
                    fee = fees.get(exchange, Decimal("0"))
                    raw_bid = prices_data.get("bid", Decimal("0"))  # Use .get for safety
                    raw_ask = prices_data.get("ask", Decimal("0"))
                    vwap_prices_with_fees_display_data[exchange] = {
                        "bid_w_fee": f"{raw_bid * (1 - fee):.6f}",
                        "ask_w_fee": f"{raw_ask * (1 + fee):.6f}",
                    }
                # Ensure the dictionary is not empty before creating DataFrame
                if vwap_prices_with_fees_display_data:
                    lines.extend(
                        ["", "  VWAP Prices with Fees (Quote/Base)"]
                        + [
                            "     " + line
                            for line in pd.DataFrame(vwap_prices_with_fees_display_data).to_string().split("\\n")
                        ]
                    )
                else:  # This case should ideally not be hit if vwap_prices and fees are present
                    lines.extend(["", "  VWAP Prices with Fees (Quote/Base): Data processing error."])
            else:  # fees is empty, implies issue with get_fees_percentages (e.g. CEX fee part)
                lines.extend(["", "  VWAP Prices with Fees (Quote/Base): Fee data not available."])
        else:  # vwap_prices is empty
            lines.extend(["", "  VWAP Prices for amount (Quote/Base): Not available."])
            # If vwap_prices is empty, can't calculate with fees either.
            lines.extend(["", "  VWAP Prices with Fees (Quote/Base): Not available (dependent on VWAP data)."])

        profitability_analysis = self.get_profitability_analysis(vwap_prices)
        lines.extend(
            ["", "  Profitability (%)"]
            + [f"     Buy XRPL: {self.exchange_xrpl} --> Sell CEX: {self.exchange_cex}"]
            + [f"          Quote Diff: {profitability_analysis['buy_xrpl_sell_cex']['quote_diff']:.7f}"]
            + [f"          Base Diff: {profitability_analysis['buy_xrpl_sell_cex']['base_diff']:.7f}"]
            + [f"          Percentage: {profitability_analysis['buy_xrpl_sell_cex']['profitability_pct'] * 100:.4f} %"]
            + [f"     Buy CEX: {self.exchange_cex} --> Sell XRPL: {self.exchange_xrpl}"]
            + [f"          Quote Diff: {profitability_analysis['buy_cex_sell_xrpl']['quote_diff']:.7f}"]
            + [f"          Base Diff: {profitability_analysis['buy_cex_sell_xrpl']['base_diff']:.7f}"]
            + [f"          Percentage: {profitability_analysis['buy_cex_sell_xrpl']['profitability_pct'] * 100:.4f} %"]
        )

        warning_lines.extend(self.balance_warning(self.get_market_trading_pair_tuples()))
        if len(warning_lines) > 0:
            lines.extend(["", "*** WARNINGS ***"] + warning_lines)
        return "\n".join(lines)

    def get_vwap_prices_for_amount(self, base_amount: Decimal):
        if self.amm_info is None:
            return {}

        base_reserve = self.amm_info.base_token_amount
        quote_reserve = self.amm_info.quote_token_amount

        bid_xrpl_price = self.get_amm_vwap_for_volume(base_reserve, quote_reserve, base_amount, False)
        ask_xrpl_price = self.get_amm_vwap_for_volume(base_reserve, quote_reserve, base_amount, True)

        bid_cex = self.connector_instance_cex.get_vwap_for_volume(self.config.trading_pair_cex, False, base_amount)
        ask_cex = self.connector_instance_cex.get_vwap_for_volume(self.config.trading_pair_cex, True, base_amount)

        vwap_prices = {
            self.exchange_xrpl: {"bid": bid_xrpl_price, "ask": ask_xrpl_price},
            self.exchange_cex: {"bid": bid_cex.result_price, "ask": ask_cex.result_price},
        }

        return vwap_prices

    def get_fees_percentages(self, vwap_prices: Dict[str, Any]) -> Dict:
        # We assume that the fee percentage for buying or selling is the same
        if self.amm_info is None:
            return {}

        xrpl_fee = self.amm_info.fee_pct / Decimal(100)

        cex_fee = self.connector_instance_cex.get_fee(
            base_currency=self.base_cex,
            quote_currency=self.quote_cex,
            order_type=OrderType.MARKET,
            order_side=TradeType.BUY,
            amount=self.config.order_amount_in_base,
            price=vwap_prices[self.exchange_cex]["ask"],
            is_maker=False,
        ).percent

        return {self.exchange_xrpl: xrpl_fee, self.exchange_cex: cex_fee}

    def get_profitability_analysis(self, vwap_prices: Dict[str, Any]) -> Dict:
        if self.amm_info is None:
            return {}

        fees = self.get_fees_percentages(vwap_prices)

        # Profit from buying on XRPL (A) and selling on CEX (B)
        # Profit_quote = (Amount_Base * P_bid_B * (1 - fee_B)) - (Amount_Base * P_ask_A * (1 + fee_A))
        buy_a_sell_b_quote = self.config.order_amount_in_base * vwap_prices[self.exchange_cex]["bid"] * (
            1 - fees[self.exchange_cex]
        ) - self.config.order_amount_in_base * vwap_prices[self.exchange_xrpl]["ask"] * (1 + fees[self.exchange_xrpl])
        buy_a_sell_b_base = buy_a_sell_b_quote / (
            (vwap_prices[self.exchange_xrpl]["ask"] + vwap_prices[self.exchange_cex]["bid"]) / 2
        )

        # Profit from buying on CEX (B) and selling on XRPL (A)
        # Profit_quote = (Amount_Base * P_bid_A * (1 - fee_A)) - (Amount_Base * P_ask_B * (1 + fee_B))
        buy_b_sell_a_quote = self.config.order_amount_in_base * vwap_prices[self.exchange_xrpl]["bid"] * (
            1 - fees[self.exchange_xrpl]
        ) - self.config.order_amount_in_base * vwap_prices[self.exchange_cex]["ask"] * (1 + fees[self.exchange_cex])
        buy_b_sell_a_base = buy_b_sell_a_quote / (
            (vwap_prices[self.exchange_cex]["ask"] + vwap_prices[self.exchange_xrpl]["bid"]) / 2
        )

        return {
            "buy_xrpl_sell_cex": {
                "quote_diff": buy_a_sell_b_quote,
                "base_diff": buy_a_sell_b_base,
                "profitability_pct": buy_a_sell_b_base / self.config.order_amount_in_base,
            },
            "buy_cex_sell_xrpl": {
                "quote_diff": buy_b_sell_a_quote,
                "base_diff": buy_b_sell_a_base,
                "profitability_pct": buy_b_sell_a_base / self.config.order_amount_in_base,
            },
        }

    def check_profitability_and_create_proposal(self, vwap_prices: Dict[str, Any]) -> Dict:
        if self.amm_info is None:
            return {}

        proposal = {}
        profitability_analysis = self.get_profitability_analysis(vwap_prices)

        if profitability_analysis["buy_xrpl_sell_cex"]["profitability_pct"] > self.config.min_profitability:
            # This means that the ask of the first exchange is lower than the bid of the second one
            proposal[self.exchange_xrpl] = OrderCandidate(
                trading_pair=self.config.trading_pair_xrpl,
                is_maker=False,
                order_type=OrderType.AMM_SWAP,
                order_side=TradeType.BUY,
                amount=self.config.order_amount_in_base,
                price=vwap_prices[self.exchange_xrpl]["ask"],
            )
            proposal[self.exchange_cex] = OrderCandidate(
                trading_pair=self.config.trading_pair_cex,
                is_maker=False,
                order_type=OrderType.MARKET,
                order_side=TradeType.SELL,
                amount=Decimal(self.config.order_amount_in_base),
                price=vwap_prices[self.exchange_cex]["bid"],
            )
        elif profitability_analysis["buy_cex_sell_xrpl"]["profitability_pct"] > self.config.min_profitability:
            # This means that the ask of the second exchange is lower than the bid of the first one
            proposal[self.exchange_cex] = OrderCandidate(
                trading_pair=self.config.trading_pair_cex,
                is_maker=False,
                order_type=OrderType.MARKET,
                order_side=TradeType.BUY,
                amount=self.config.order_amount_in_base,
                price=vwap_prices[self.exchange_cex]["ask"],
            )
            proposal[self.exchange_xrpl] = OrderCandidate(
                trading_pair=self.config.trading_pair_xrpl,
                is_maker=False,
                order_type=OrderType.AMM_SWAP,
                order_side=TradeType.SELL,
                amount=self.config.order_amount_in_base,
                price=vwap_prices[self.exchange_xrpl]["bid"],
            )

        return proposal

    def adjust_proposal_to_budget(self, proposal: Dict[str, OrderCandidate]) -> Dict[str, OrderCandidate]:
        for connector, order in proposal.items():
            proposal[connector] = self.connectors[connector].budget_checker.adjust_candidate(order, all_or_none=True)
        return proposal

    def place_orders(self, proposal: Dict[str, OrderCandidate]) -> None:
        for connector, order in proposal.items():
            self.place_order(connector_name=connector, order=order)

    def place_order(self, connector_name: str, order: OrderCandidate):
        if order.order_side == TradeType.SELL:
            self.sell(
                connector_name=connector_name,
                trading_pair=order.trading_pair,
                amount=order.amount,
                order_type=order.order_type,
                price=order.price,
            )
        elif order.order_side == TradeType.BUY:
            self.buy(
                connector_name=connector_name,
                trading_pair=order.trading_pair,
                amount=order.amount,
                order_type=order.order_type,
                price=order.price,
            )

    def test_place_order(self) -> None:
        # Method to test the place order function on XRPL AMM Pools
        vwap_prices = self.get_vwap_prices_for_amount(self.config.order_amount_in_base)

        # # create a proposal to buy 1 XRPL on xrpl, use vwap price
        buy_proposal = {
            self.exchange_xrpl: OrderCandidate(
                trading_pair=self.config.trading_pair_xrpl,
                is_maker=False,
                order_type=OrderType.AMM_SWAP,
                order_side=TradeType.BUY,
                amount=Decimal("1.0"),
                price=vwap_prices[self.exchange_xrpl]["ask"],
            )
        }

        self.place_orders(buy_proposal)
        # create a proposal to sell 1 XRPL on xrpl, use vwap price

        sell_proposal = {
            self.exchange_xrpl: OrderCandidate(
                trading_pair=self.config.trading_pair_xrpl,
                is_maker=False,
                order_type=OrderType.AMM_SWAP,
                order_side=TradeType.SELL,
                amount=Decimal("1.0"),
                price=vwap_prices[self.exchange_xrpl]["bid"],
            )
        }

        self.place_orders(sell_proposal)

    def did_fill_order(self, event: OrderFilledEvent):
        msg = f"{event.trade_type.name} {round(event.amount, 2)} {event.trading_pair} at {round(event.price, 2)}"
        self.log_with_clock(logging.INFO, msg)
        self.notify_hb_app_with_timestamp(msg)

    def calculate_amm_price_impact(
        self,
        initial_base_reserve: Decimal,
        initial_quote_reserve: Decimal,
        trade_amount: Decimal,
        is_selling_base: bool,
    ) -> Decimal:
        """
        Calculates the price impact for a trade on a constant product AMM,
        where trade_amount always refers to an amount of the base asset.

        The price impact formula used is:
        Price Impact (%) = (Amount_Token_In / (Initial_Reserve_Token_In + Amount_Token_In)) * 100

        Args:
            initial_base_reserve: The initial amount of base token in the liquidity pool.
            initial_quote_reserve: The initial amount of quote token in the liquidity pool.
            trade_amount: The amount of BASE ASSET being traded.
                        If is_selling_base is True, this is the amount of base asset the user SELLS.
                        If is_selling_base is False, this is the amount of base asset the user BUYS.
            is_selling_base: True if the trade_amount (of base asset) is being SOLD by the user.
                            False if the trade_amount (of base asset) is being BOUGHT by the user
                            (by inputting quote asset).

        Returns:
            The price impact as a percentage (e.g., Decimal('5.25') for 5.25%).
            Returns Decimal('0') if trade_amount is zero.
            Returns Decimal('100') if the trade is impossible or would deplete the pool entirely.
        """
        if trade_amount <= Decimal("0"):
            return Decimal("0")

        amount_token_in: Decimal
        initial_reserve_of_token_in: Decimal

        if is_selling_base:
            # User is selling 'trade_amount' of base asset.
            # Token_In is the base asset.
            amount_token_in = trade_amount
            initial_reserve_of_token_in = initial_base_reserve

            if initial_base_reserve < Decimal("0"):
                raise ValueError("Initial base reserve cannot be negative when selling base.")

        else:  # User is buying 'trade_amount' of base asset (by inputting quote asset)
            # Token_In is the quote asset.
            # 'trade_amount' here is delta_x_out (amount of base user receives from the pool)
            delta_x_out = trade_amount

            if initial_base_reserve <= Decimal("0") or initial_quote_reserve <= Decimal("0"):
                raise ValueError("Initial pool reserves (base and quote) must be positive for buying base.")

            if delta_x_out >= initial_base_reserve:
                # Cannot buy more base asset than available or exactly deplete the base reserve,
                # as it would require infinite quote or result in division by zero.
                # Impact is effectively 100% or the trade is impossible.
                return Decimal("100")

            # Calculate amount_token_in (which is delta_y_in, the quote amount paid by the user)
            # delta_y_in = y0 * delta_x_out / (x0 - delta_x_out)
            amount_token_in = initial_quote_reserve * delta_x_out / (initial_base_reserve - delta_x_out)
            initial_reserve_of_token_in = initial_quote_reserve

            if amount_token_in < Decimal("0"):
                # This should theoretically not happen if delta_x_out < initial_base_reserve
                # and reserves are positive. Added as a safeguard.
                raise ValueError("Calculated quote input amount is negative, which indicates an issue.")

        # Denominator for the price impact formula: Initial_Reserve_Token_In + Amount_Token_In
        denominator = initial_reserve_of_token_in + amount_token_in

        if denominator == Decimal("0"):
            # This case implies initial_reserve_of_token_in was 0 and amount_token_in is also 0.
            # (trade_amount <= 0 is handled at the start).
            # If amount_token_in > 0 and initial_reserve_of_token_in == 0:
            #   - Selling base to an empty base pool: amount_token_in = trade_amount, denom = trade_amount => 100% impact.
            #   - Buying base: initial_reserve_of_token_in (quote) must be > 0 based on earlier checks.
            # This primarily covers the selling to an empty pool scenario.
            if amount_token_in > Decimal("0") and initial_reserve_of_token_in == Decimal("0"):
                return Decimal("100")
            # For other unexpected zero denominator cases.
            return Decimal("100")  # Or raise an error, as this state might be ambiguous.

        price_impact_ratio = amount_token_in / denominator
        price_impact_percentage = price_impact_ratio * Decimal("100")

        return price_impact_percentage

    def get_amm_vwap_for_volume(
        self,
        initial_base_reserve: Decimal,
        initial_quote_reserve: Decimal,
        base_amount_to_trade: Decimal,
        is_buy_base: bool,
    ) -> Decimal:
        """
        Calculates the Volume Weighted Average Price (VWAP) or effective price for trading a specific
        amount of base asset on a constant product AMM.

        This price is in terms of quote_asset / base_asset.
        This calculation does not include any trading fees.

        Args:
            initial_base_reserve: The initial amount of base token in the liquidity pool (x0).
            initial_quote_reserve: The initial amount of quote token in the liquidity pool (y0).
            base_amount_to_trade: The amount of base asset to be bought from or sold to the pool (delta_x).
            is_buy_base: True if buying the base_amount_to_trade from the pool (paying with quote).
                        False if selling the base_amount_to_trade to the pool (receiving quote).

        Returns:
            The effective price (VWAP) as a Decimal.

        Raises:
            ValueError: If trade volume or reserves are non-positive, or if a trade
                        would deplete the pool or lead to division by zero.
        """
        if base_amount_to_trade <= Decimal("0"):
            raise ValueError("Trade volume (base_amount_to_trade) must be positive.")
        if initial_base_reserve <= Decimal("0") or initial_quote_reserve <= Decimal("0"):
            raise ValueError("Initial pool reserves (base and quote) must be positive.")

        if is_buy_base:
            # Buying base_amount_to_trade FROM the pool (delta_x_out)
            # Effective price = y0 / (x0 - delta_x_out)
            if base_amount_to_trade >= initial_base_reserve:
                raise ValueError(
                    "Cannot buy more base asset than available or exactly deplete the pool "
                    "(would result in zero or negative denominator)."
                )
            effective_price = initial_quote_reserve / (initial_base_reserve - base_amount_to_trade)
        else:
            # Selling base_amount_to_trade TO the pool (delta_x_in)
            # Effective price = y0 / (x0 + delta_x_in)
            effective_price = initial_quote_reserve / (initial_base_reserve + base_amount_to_trade)

        return effective_price
