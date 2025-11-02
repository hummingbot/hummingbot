#!/usr/bin/env python3
"""
Debug script to understand why HYPE is not appearing in Top Assets
"""
import sys
from collections import defaultdict
from pathlib import Path

# Add hummingbot to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from hummingbot import data_path  # noqa: E402
from reporting.analysis.pnl_calculator import PnLCalculator  # noqa: E402
from reporting.database.connection import DatabaseManager  # noqa: E402
from reporting.matching.trade_matcher import MatchingMethod, TradeMatcher  # noqa: E402
from reporting.normalization.trade_normalizer import TradeNormalizer  # noqa: E402


def main():
    """Main debug function"""
    # Get database path
    db_path = Path(data_path()) / "mqtt_webhook_strategy_w_cex.sqlite"

    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        sys.exit(1)

    print(f"✅ Found database: {db_path}\n")

    # Load trades
    db = DatabaseManager(str(db_path))
    trades = db.get_all_trades()

    if not trades:
        print("❌ No trades found in database")
        sys.exit(1)

    print(f"✅ Loaded {len(trades)} trades from database\n")

    # ============================================================================
    # STEP 1: Raw trades from database
    # ============================================================================
    print("=" * 80)
    print("STEP 1: Raw trades from database")
    print("=" * 80)

    trade_counts = defaultdict(lambda: {'BUY': 0, 'SELL': 0})
    for trade in trades:
        base = trade.base_asset if hasattr(trade, 'base_asset') else 'UNKNOWN'
        trade_type = trade.trade_type if hasattr(trade, 'trade_type') else 'UNKNOWN'
        trade_counts[base][trade_type] += 1

    for asset, counts in sorted(trade_counts.items(), key=lambda x: sum(x[1].values()), reverse=True):
        total = counts['BUY'] + counts['SELL']
        print(f"  {asset}: {counts['BUY']} BUY, {counts['SELL']} SELL (Total: {total})")

    # ============================================================================
    # STEP 2: After normalization
    # ============================================================================
    print("\n" + "=" * 80)
    print("STEP 2: After normalization")
    print("=" * 80)

    normalizer = TradeNormalizer()
    normalized_trades = normalizer.normalize_trades(trades)

    print(f"✅ Normalized {len(normalized_trades)} trades\n")

    norm_counts = defaultdict(lambda: {'BUY': 0, 'SELL': 0})
    for trade in normalized_trades:
        norm_counts[trade.base_asset][trade.trade_type.value] += 1

    for asset, counts in sorted(norm_counts.items(), key=lambda x: sum(x[1].values()), reverse=True):
        total = counts['BUY'] + counts['SELL']
        print(f"  {asset}: {counts['BUY']} BUY, {counts['SELL']} SELL (Total: {total})")

    # Check if HYPE was affected by normalization
    hype_before = trade_counts.get('HYPE', {'BUY': 0, 'SELL': 0})
    hype_after = norm_counts.get('HYPE', {'BUY': 0, 'SELL': 0})

    if hype_before != hype_after:
        print("\n⚠️  HYPE changed during normalization:")
        print(f"   Before: {hype_before}")
        print(f"   After: {hype_after}")

    # ============================================================================
    # STEP 3: After matching
    # ============================================================================
    print("\n" + "=" * 80)
    print("STEP 3: After matching (FIFO)")
    print("=" * 80)

    matcher = TradeMatcher(method=MatchingMethod.FIFO)
    result = matcher.match_trades(normalized_trades)

    print(f"✅ Matched {len(result['matched_positions'])} positions")
    print(f"✅ Found {len(result['open_positions'])} open positions\n")

    # Count matched positions by asset
    match_counts = defaultdict(int)
    for matched_pos in result['matched_positions']:
        asset = matched_pos.buy_trade.base_asset
        match_counts[asset] += 1

    print("Matched positions by asset:")
    for asset, count in sorted(match_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {asset}: {count} matched positions")

    # Count open positions by asset
    open_counts = defaultdict(int)
    for open_pos in result['open_positions']:
        asset = open_pos.trade.base_asset
        open_counts[asset] += 1

    print("\nOpen positions by asset:")
    for asset, count in sorted(open_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {asset}: {count} open positions")

    # Check HYPE matching
    hype_matched = match_counts.get('HYPE', 0)
    hype_open = open_counts.get('HYPE', 0)

    print("\n🔍 HYPE Status:")
    print(f"   Raw DB: {hype_before['BUY']} BUY, {hype_before['SELL']} SELL")
    print(f"   Normalized: {hype_after['BUY']} BUY, {hype_after['SELL']} SELL")
    print(f"   Matched: {hype_matched} positions")
    print(f"   Open: {hype_open} positions")

    # ============================================================================
    # STEP 4: PnL Calculation
    # ============================================================================
    print("\n" + "=" * 80)
    print("STEP 4: PnL Calculation")
    print("=" * 80)

    calculator = PnLCalculator()
    report = calculator.calculate(
        matched_positions=result['matched_positions'],
        open_positions=result['open_positions'],
        all_trades=normalized_trades
    )

    print(f"✅ Calculated PnL for {len(report.by_asset)} assets\n")

    print("Assets in report.by_asset:")
    for asset, pnl in sorted(report.by_asset.items(), key=lambda x: x[1].total_realized_pnl, reverse=True):
        print(f"  {asset}: {pnl.total_trades} matched, {pnl.open_positions} open, PnL: ${pnl.total_realized_pnl:.2f}")

    # ============================================================================
    # DIAGNOSIS
    # ============================================================================
    print("\n" + "=" * 80)
    print("DIAGNOSIS")
    print("=" * 80)

    if 'HYPE' not in report.by_asset:
        print("❌ HYPE is NOT in report.by_asset")
        print("\nPossible reasons:")

        if hype_matched == 0:
            print("  1. HYPE has 0 matched positions (no completed buy-sell pairs)")
            print("     → This means all HYPE trades are open positions")

        if hype_after != hype_before:
            print("  2. HYPE trades were modified during normalization")
            print("     → Check normalization logic")

        # Check if there's an issue with the asset name
        for asset in report.by_asset.keys():
            if 'HYPE' in asset.upper():
                print(f"  3. Found similar asset: '{asset}' (case/name mismatch?)")
    else:
        print("✅ HYPE is in report.by_asset")
        hype_pnl = report.by_asset['HYPE']
        print(f"   Total trades: {hype_pnl.total_trades}")
        print(f"   Open positions: {hype_pnl.open_positions}")
        print(f"   Realized PnL: ${hype_pnl.total_realized_pnl:.2f}")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
