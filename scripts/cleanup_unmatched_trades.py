#!/usr/bin/env python3
"""
Clean up unmatched trades from database while preserving matched positions.
Keeps WBTC trades intact (including open position).
Removes only unmatched trades for BTC, HYPE, SOL.

Usage:
    python cleanup_unmatched_trades.py          # Interactive (asks for confirmation)
    python cleanup_unmatched_trades.py --yes    # Auto-confirm deletion
"""
import argparse
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# Add hummingbot to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from hummingbot import data_path  # noqa: E402
from reporting.database.connection import DatabaseManager  # noqa: E402
from reporting.matching.trade_matcher import MatchingMethod, TradeMatcher  # noqa: E402
from reporting.normalization.trade_normalizer import TradeNormalizer  # noqa: E402


def main():
    """Main cleanup function"""
    # Parse arguments
    parser = argparse.ArgumentParser(description='Clean up unmatched trades from database')
    parser.add_argument('--yes', action='store_true', help='Auto-confirm deletion without prompting')
    args = parser.parse_args()

    # Get database path
    db_path = Path(data_path()) / "mqtt_webhook_strategy_w_cex.sqlite"

    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        sys.exit(1)

    print(f"✅ Found database: {db_path}\n")

    # Create backup first
    backup_path = db_path.parent / f"mqtt_webhook_strategy_w_cex_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sqlite"
    print(f"📦 Creating backup: {backup_path}")
    import shutil
    shutil.copy2(db_path, backup_path)
    print("✅ Backup created\n")

    # Load trades
    db = DatabaseManager(str(db_path))
    all_trades = db.get_all_trades()

    print(f"✅ Loaded {len(all_trades)} total trades\n")

    # Normalize and match
    normalizer = TradeNormalizer()
    normalized_trades = normalizer.normalize_trades(all_trades)

    matcher = TradeMatcher(method=MatchingMethod.FIFO)
    result = matcher.match_trades(normalized_trades)

    print("=" * 80)
    print("MATCHED POSITIONS BY ASSET")
    print("=" * 80)

    # Build sets of matched trade IDs
    matched_trade_ids = set()
    for matched_pos in result['matched_positions']:
        matched_trade_ids.add(matched_pos.buy_trade.original_trade.exchange_trade_id)
        matched_trade_ids.add(matched_pos.sell_trade.original_trade.exchange_trade_id)

    # Count matched by asset
    matched_by_asset = defaultdict(int)
    for matched_pos in result['matched_positions']:
        asset = matched_pos.buy_trade.base_asset
        matched_by_asset[asset] += 1

    for asset, count in sorted(matched_by_asset.items()):
        print(f"  {asset}: {count} matched positions")

    print("\n" + "=" * 80)
    print("OPEN POSITIONS BY ASSET")
    print("=" * 80)

    open_by_asset = defaultdict(list)
    for open_pos in result['open_positions']:
        asset = open_pos.trade.base_asset
        open_by_asset[asset].append(open_pos.trade)

    for asset, trades in sorted(open_by_asset.items()):
        print(f"  {asset}: {len(trades)} open positions ({trades[0].trade_type.value if trades else 'N/A'})")

    # Identify trades to delete (unmatched for BTC, HYPE, SOL only)
    print("\n" + "=" * 80)
    print("CLEANUP PLAN")
    print("=" * 80)

    assets_to_clean = ['BTC', 'HYPE', 'SOL']
    trades_to_delete = []

    for asset in assets_to_clean:
        if asset in open_by_asset:
            open_trades = open_by_asset[asset]
            print(f"  {asset}: Delete {len(open_trades)} unmatched trades")
            trades_to_delete.extend(open_trades)
        else:
            print(f"  {asset}: No unmatched trades")

    if 'WBTC' in open_by_asset:
        print(f"  WBTC: Keep {len(open_by_asset['WBTC'])} open position(s) (protected)")

    print(f"\n📊 Total trades to delete: {len(trades_to_delete)}")

    if not trades_to_delete:
        print("✅ No trades to delete. Database is clean!")
        sys.exit(0)

    # Show details of trades to delete
    print("\n" + "=" * 80)
    print("TRADES TO DELETE (Details)")
    print("=" * 80)

    for trade in sorted(trades_to_delete, key=lambda t: (t.base_asset, t.timestamp)):
        trade_id = trade.original_trade.exchange_trade_id
        print(f"  {trade.base_asset}: {trade.trade_type.value} - ID: {trade_id[:16]}... - Time: {datetime.fromtimestamp(trade.timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S')}")

    # Confirm deletion
    print("\n" + "=" * 80)

    if not args.yes:
        response = input("⚠️  Proceed with deletion? (yes/no): ")

        if response.lower() != 'yes':
            print("❌ Cleanup cancelled")
            sys.exit(0)
    else:
        print("⚠️  Auto-confirming deletion (--yes flag provided)")

    # Delete trades from database
    print("\n🗑️  Deleting trades...")

    deleted_count = 0
    with db.get_connection() as conn:
        cursor = conn.cursor()

        for trade in trades_to_delete:
            try:
                # Delete by exchange_trade_id (unique identifier)
                trade_id = trade.original_trade.exchange_trade_id
                cursor.execute("DELETE FROM TradeFill WHERE exchange_trade_id = ?", (trade_id,))
                deleted_count += 1
                print(f"  ✅ Deleted {trade.base_asset} {trade.trade_type.value} (ID: {trade_id[:16]}...)")
            except Exception as e:
                print(f"  ❌ Failed to delete {trade.base_asset} trade: {e}")

        conn.commit()

    print(f"\n✅ Deleted {deleted_count} trades")

    # Verify final state
    print("\n" + "=" * 80)
    print("FINAL STATE VERIFICATION")
    print("=" * 80)

    final_trades = db.get_all_trades()
    print(f"Total trades remaining: {len(final_trades)}")

    # Count by asset
    final_counts = defaultdict(lambda: {'BUY': 0, 'SELL': 0})
    for trade in final_trades:
        base = trade.base_asset if hasattr(trade, 'base_asset') else 'UNKNOWN'
        trade_type = trade.trade_type if hasattr(trade, 'trade_type') else 'UNKNOWN'
        final_counts[base][trade_type] += 1

    print("\nFinal trade counts by asset:")
    for asset, counts in sorted(final_counts.items()):
        total = counts['BUY'] + counts['SELL']
        buy_sell_diff = counts['BUY'] - counts['SELL']
        status = f"({abs(buy_sell_diff)} open {'BUY' if buy_sell_diff > 0 else 'SELL'})" if buy_sell_diff != 0 else "(all matched)"
        print(f"  {asset}: {counts['BUY']} BUY, {counts['SELL']} SELL (Total: {total}) {status}")

    print("\n✅ Cleanup complete!")
    print(f"📦 Backup saved to: {backup_path}")


if __name__ == "__main__":
    main()
