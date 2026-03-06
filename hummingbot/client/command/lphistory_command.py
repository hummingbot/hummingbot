import threading
import time
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Dict, List, Optional, Set, Tuple

import pandas as pd

from hummingbot.core.rate_oracle.rate_oracle import RateOracle
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.model.range_position_update import RangePositionUpdate

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication  # noqa: F401


def get_timestamp(days_ago: float = 0.) -> float:
    return time.time() - (60. * 60. * 24. * days_ago)


def smart_round(value: Decimal, precision: Optional[int] = None) -> str:
    """Round decimal value smartly for display."""
    if precision is not None:
        return f"{float(value):.{precision}f}"
    # Auto precision based on magnitude
    abs_val = abs(float(value))
    if abs_val == 0:
        return "0"
    elif abs_val >= 1000:
        return f"{float(value):.2f}"
    elif abs_val >= 1:
        return f"{float(value):.4f}"
    else:
        return f"{float(value):.6f}"


class LPHistoryCommand:
    def lphistory(self,  # type: HummingbotApplication
                  days: float = 0,
                  verbose: bool = False,
                  precision: Optional[int] = None
                  ):
        """
        Display LP position history and performance metrics.
        Works with any LP strategy that writes RangePositionUpdate records.
        """
        if threading.current_thread() != threading.main_thread():
            self.ev_loop.call_soon_threadsafe(self.lphistory, days, verbose, precision)
            return

        if self.strategy_file_name is None:
            self.notify("\n  Please first import a strategy config file of which to show LP history.")
            return

        start_time = get_timestamp(days) if days > 0 else self.init_time

        with self.trading_core.trade_fill_db.get_new_session() as session:
            updates: List[RangePositionUpdate] = self._get_lp_updates_from_session(
                int(start_time * 1e3),
                session=session,
                config_file_path=self.strategy_file_name
            )
            if not updates:
                self.notify("\n  No LP position updates to report.")
                return

            if verbose:
                self._list_lp_updates(updates)

            safe_ensure_future(self._lp_performance_report(start_time, updates, precision))

    def _get_lp_updates_from_session(
        self,  # type: HummingbotApplication
        start_timestamp: int,
        session,
        config_file_path: str = None
    ) -> List[RangePositionUpdate]:
        """Query RangePositionUpdate records from database."""
        query = session.query(RangePositionUpdate).filter(
            RangePositionUpdate.timestamp >= start_timestamp
        )
        if config_file_path:
            query = query.filter(RangePositionUpdate.config_file_path == config_file_path)
        return query.order_by(RangePositionUpdate.timestamp).all()

    def _list_lp_updates(self,  # type: HummingbotApplication
                         updates: List[RangePositionUpdate]):
        """Display list of LP updates in a table."""
        lines = []

        if len(updates) > 0:
            data = []
            for u in updates:
                # Parse timestamp (stored in milliseconds)
                ts = datetime.fromtimestamp(u.timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S')
                data.append({
                    "Time": ts,
                    "Action": u.order_action or "",
                    "Pair": u.trading_pair or "",
                    "Position": (u.position_address[:8] + "...") if u.position_address else "",
                    "Base Amt": f"{u.base_amount:.4f}" if u.base_amount else "0",
                    "Quote Amt": f"{u.quote_amount:.4f}" if u.quote_amount else "0",
                    "Base Fee": f"{u.base_fee:.6f}" if u.base_fee else "-",
                    "Quote Fee": f"{u.quote_fee:.6f}" if u.quote_fee else "-",
                    "Tx Fee": f"{u.trade_fee_in_quote:.6f}" if u.trade_fee_in_quote else "-",
                })
            df = pd.DataFrame(data)
            lines.extend(["", "  LP Position Updates:"] +
                         ["    " + line for line in df.to_string(index=False).split("\n")])
        else:
            lines.extend(["\n  No LP position updates in this session."])

        self.notify("\n".join(lines))

    async def _get_current_price(self, trading_pair: str) -> Decimal:  # type: HummingbotApplication
        """Get current price from RateOracle (same as history command)."""
        try:
            price = await RateOracle.get_instance().stored_or_live_rate(trading_pair)
            if price is not None:
                return Decimal(str(price))
        except Exception:
            pass
        return Decimal("0")

    async def _lp_performance_report(self,  # type: HummingbotApplication
                                     start_time: float,
                                     updates: List[RangePositionUpdate],
                                     precision: Optional[int] = None):
        """Calculate and display LP performance metrics."""
        lines = []
        current_time = get_timestamp()

        # Header
        lines.extend([
            f"\nStart Time: {datetime.fromtimestamp(start_time).strftime('%Y-%m-%d %H:%M:%S')}",
            f"Current Time: {datetime.fromtimestamp(current_time).strftime('%Y-%m-%d %H:%M:%S')}",
            f"Duration: {pd.Timedelta(seconds=int(current_time - start_time))}"
        ])

        # Group by (market, trading_pair) like history command
        market_info: Set[Tuple[str, str]] = set((u.market or "unknown", u.trading_pair or "UNKNOWN") for u in updates)

        # Report for each market/trading pair
        for market, trading_pair in market_info:
            pair_updates = [u for u in updates if u.market == market and u.trading_pair == trading_pair]
            await self._report_pair_performance(lines, market, trading_pair, pair_updates, precision)

        self.notify("\n".join(lines))

    async def _report_pair_performance(self,  # type: HummingbotApplication
                                       lines: List[str],
                                       market: str,
                                       trading_pair: str,
                                       updates: List[RangePositionUpdate],
                                       precision: Optional[int] = None):
        """Calculate and format performance for a single trading pair (closed positions only)."""
        # Group updates by position_address
        positions: Dict[str, Dict[str, RangePositionUpdate]] = {}
        for u in updates:
            addr = u.position_address or "unknown"
            if addr not in positions:
                positions[addr] = {}
            positions[addr][u.order_action] = u

        # Only include closed positions (those with both ADD and REMOVE)
        closed_positions = {addr: pos for addr, pos in positions.items()
                            if "ADD" in pos and "REMOVE" in pos}

        if not closed_positions:
            lines.append(f"\n{market} / {trading_pair}")
            lines.append("\n  No closed positions to report.")
            return

        # Extract opens and closes from closed positions only
        opens = [pos["ADD"] for pos in closed_positions.values()]
        closes = [pos["REMOVE"] for pos in closed_positions.values()]

        # Parse tokens from trading pair
        parts = trading_pair.split("-")
        base = parts[0] if len(parts) >= 2 else "BASE"
        quote = parts[1] if len(parts) >= 2 else "QUOTE"

        # Get current price - try live first, fall back to most recent close
        current_price = await self._get_current_price(trading_pair)
        if current_price == 0:
            for u in reversed(closes):
                if u.mid_price:
                    current_price = Decimal(str(u.mid_price))
                    break

        # Calculate totals for opens
        total_open_base = sum(Decimal(str(u.base_amount or 0)) for u in opens)
        total_open_quote = sum(Decimal(str(u.quote_amount or 0)) for u in opens)

        # Calculate totals for closes
        total_close_base = sum(Decimal(str(u.base_amount or 0)) for u in closes)
        total_close_quote = sum(Decimal(str(u.quote_amount or 0)) for u in closes)

        # Calculate total fees collected
        total_fees_base = sum(Decimal(str(u.base_fee or 0)) for u in closes)
        total_fees_quote = sum(Decimal(str(u.quote_fee or 0)) for u in closes)

        # Calculate total rent
        total_position_rent = sum(Decimal(str(u.position_rent or 0)) for u in opens)
        total_position_rent_refunded = sum(Decimal(str(u.position_rent_refunded or 0)) for u in closes)
        net_rent = total_position_rent - total_position_rent_refunded

        # Calculate total transaction fees (from both ADD and REMOVE operations)
        total_tx_fees = sum(Decimal(str(u.trade_fee_in_quote or 0)) for u in opens)
        total_tx_fees += sum(Decimal(str(u.trade_fee_in_quote or 0)) for u in closes)

        # Calculate values using stored mid_price from each transaction (for accurate realized P&L)
        # Each ADD valued at its mid_price, each REMOVE valued at its mid_price
        total_open_value = Decimal("0")
        for u in opens:
            mid_price = Decimal(str(u.mid_price)) if u.mid_price else current_price
            base_amt = Decimal(str(u.base_amount or 0))
            quote_amt = Decimal(str(u.quote_amount or 0))
            total_open_value += base_amt * mid_price + quote_amt

        total_close_value = Decimal("0")
        total_fees_value = Decimal("0")
        for u in closes:
            mid_price = Decimal(str(u.mid_price)) if u.mid_price else current_price
            base_amt = Decimal(str(u.base_amount or 0))
            quote_amt = Decimal(str(u.quote_amount or 0))
            base_fee = Decimal(str(u.base_fee or 0))
            quote_fee = Decimal(str(u.quote_fee or 0))
            total_close_value += base_amt * mid_price + quote_amt
            total_fees_value += base_fee * mid_price + quote_fee

        # P&L calculation (including transaction fees)
        total_returned = total_close_value + total_fees_value
        gross_pnl = total_returned - total_open_value if total_open_value > 0 else Decimal("0")
        net_pnl = gross_pnl - total_tx_fees
        position_roi_pct = (net_pnl / total_open_value * 100) if total_open_value > 0 else Decimal("0")

        # Header with market info
        lines.append(f"\n{market} / {trading_pair}")

        # Count open and closed positions
        open_position_count = len([addr for addr, pos in positions.items() if "ADD" in pos and "REMOVE" not in pos])
        closed_position_count = len(closed_positions)
        lines.append(f"Positions Opened: {open_position_count + closed_position_count}  |  Positions Closed: {closed_position_count}")

        # Closed Positions table - grouped by side (buy=quote only, sell=base only, both=double-sided)
        # Determine side based on ADD amounts: base only=sell, quote only=buy, both=both
        buy_positions = [(o, c) for o, c in zip(opens, closes) if o.base_amount == 0 or o.base_amount is None]
        sell_positions = [(o, c) for o, c in zip(opens, closes) if o.quote_amount == 0 or o.quote_amount is None]
        both_positions = [(o, c) for o, c in zip(opens, closes)
                          if (o, c) not in buy_positions and (o, c) not in sell_positions]

        # Column order matches side values: both(0), buy(1), sell(2)
        pos_columns = ["", "both", "buy", "sell"]
        pos_data = [
            [f"{'Number of positions':<27}", len(both_positions), len(buy_positions), len(sell_positions)],
            [f"{f'Total volume ({base})':<27}",
             smart_round(sum(Decimal(str(o.base_amount or 0)) + Decimal(str(c.base_amount or 0)) for o, c in both_positions), precision),
             smart_round(sum(Decimal(str(o.base_amount or 0)) + Decimal(str(c.base_amount or 0)) for o, c in buy_positions), precision),
             smart_round(sum(Decimal(str(o.base_amount or 0)) + Decimal(str(c.base_amount or 0)) for o, c in sell_positions), precision)],
            [f"{f'Total volume ({quote})':<27}",
             smart_round(sum(Decimal(str(o.quote_amount or 0)) + Decimal(str(c.quote_amount or 0)) for o, c in both_positions), precision),
             smart_round(sum(Decimal(str(o.quote_amount or 0)) + Decimal(str(c.quote_amount or 0)) for o, c in buy_positions), precision),
             smart_round(sum(Decimal(str(o.quote_amount or 0)) + Decimal(str(c.quote_amount or 0)) for o, c in sell_positions), precision)],
        ]
        pos_df = pd.DataFrame(data=pos_data, columns=pos_columns)
        lines.extend(["", "  Closed Positions:"] + ["    " + line for line in pos_df.to_string(index=False).split("\n")])

        # Assets table
        assets_columns = ["", "add", "remove", "fees"]
        assets_data = [
            [f"{base:<17}",
             smart_round(total_open_base, precision),
             smart_round(total_close_base, precision),
             smart_round(total_fees_base, precision)],
            [f"{quote:<17}",
             smart_round(total_open_quote, precision),
             smart_round(total_close_quote, precision),
             smart_round(total_fees_quote, precision)],
        ]
        assets_df = pd.DataFrame(data=assets_data, columns=assets_columns)
        lines.extend(["", "  Assets:"] + ["    " + line for line in assets_df.to_string(index=False).split("\n")])

        # Performance table
        perf_data = [
            ["Total add value         ", f"{smart_round(total_open_value, precision)} {quote}"],
            ["Total remove value      ", f"{smart_round(total_close_value, precision)} {quote}"],
            ["Fees collected          ", f"{smart_round(total_fees_value, precision)} {quote}"],
            ["Transaction fees        ", f"{smart_round(total_tx_fees, precision)} {quote}"],
        ]
        if net_rent != 0:
            perf_data.append(["Rent paid (net)         ", f"{smart_round(net_rent, precision)} SOL"])
        perf_data.extend([
            ["Net P&L                 ", f"{smart_round(net_pnl, precision)} {quote}"],
            ["Return %                ", f"{float(position_roi_pct):.2f}%"],
        ])
        perf_df = pd.DataFrame(data=perf_data)
        lines.extend(["", "  Performance:"] +
                     ["    " + line for line in perf_df.to_string(index=False, header=False).split("\n")])

        # Note about open positions
        if open_position_count > 0:
            lines.append(f"\n  Note: {open_position_count} position(s) still open. P&L excludes unrealized gains/losses.")
