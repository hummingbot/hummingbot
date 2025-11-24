#!/usr/bin/env python3
"""
Delete ALL unmatched trades for BTC, HYPE, SOL to balance buy/sell counts.
Keeps WBTC trades intact (including open position).

This is more aggressive than cleanup_unmatched_trades.py - it deletes enough
trades to make BUY and SELL counts equal for each asset.

Usage:
    python cleanup_all_unmatched.py          # Interactive
    python cleanup_all_unmatched.py --yes    # Auto-confirm
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path

# Add hummingbot to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from collections import defaultdict  # noqa: E402

from hummingbot import data_path  # noqa: E402
from reporting.database.connection import DatabaseManager  # noqa: E402


def main():
    """Main cleanup function"""
    # Parse arguments
    parser = argparse.ArgumentParser(description='Delete all unmatched trades to balance buy/sell counts')
    parser.add_argument('--yes', action='store_true', help='Auto-confirm deletion without prompting')
    args = parser.parse_args()

    # Get database path
    db_path = Path(data_path()) / "mqtt_webhook_strategy_w_cex.sqlite"

    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        sys.exit(1)

    print(f"✅ Found database: {db_path}\n")

    # Create backup first
    backup_path = db_path.parent / f"mqtt_webhook_strategy_w_cex_backup_full_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sqlite"
    print(f"📦 Creating backup: {backup_path}")
    import shutil
    shutil.copy2(db_path, backup_path)
    print("✅ Backup created\n")

    # Load all trades
    db = DatabaseManager(str(db_path))
    all_trades = db.get_all_trades()

    print(f"✅ Loaded {len(all_trades)} total trades\n")

    # Count trades by asset and type
    print("=" * 80)
    print("CURRENT STATE")
    print("=" * 80)

    trade_counts = defaultdict(lambda: {'BUY': [], 'SELL': []})
    for trade in all_trades:
        trade_type = trade.trade_type
        trade_counts[trade.base_asset][trade_type].append(trade)

    for asset in sorted(trade_counts.keys()):
        buy_count = len(trade_counts[asset]['BUY'])
        sell_count = len(trade_counts[asset]['SELL'])
        diff = buy_count - sell_count
        status = f"({abs(diff)} excess {'BUY' if diff > 0 else 'SELL'})" if diff != 0 else "(balanced)"
        print(f"  {asset}: {buy_count} BUY, {sell_count} SELL {status}")

    # Identify trades to delete (for BTC, HYPE, SOL only)
    print("\n" + "=" * 80)
    print("CLEANUP PLAN")
    print("=" * 80)

    assets_to_clean = ['BTC', 'HYPE', 'SOL']
    trades_to_delete = []

    for asset in assets_to_clean:
        if asset not in trade_counts:
            print(f"  {asset}: Not found in database")
            continue

        buy_trades = trade_counts[asset]['BUY']
        sell_trades = trade_counts[asset]['SELL']
        buy_count = len(buy_trades)
        sell_count = len(sell_trades)

        if buy_count > sell_count:
            # Delete excess BUYs (most recent first)
            excess = buy_count - sell_count
            trades_to_remove = sorted(buy_trades, key=lambda t: t.timestamp, reverse=True)[:excess]
            trades_to_delete.extend(trades_to_remove)
            print(f"  {asset}: Delete {excess} excess BUY trades (have {buy_count} BUY, {sell_count} SELL)")
        elif sell_count > buy_count:
            # Delete excess SELLs (most recent first)
            excess = sell_count - buy_count
            trades_to_remove = sorted(sell_trades, key=lambda t: t.timestamp, reverse=True)[:excess]
            trades_to_delete.extend(trades_to_remove)
            print(f"  {asset}: Delete {excess} excess SELL trades (have {buy_count} BUY, {sell_count} SELL)")
        else:
            print(f"  {asset}: Already balanced ({buy_count} BUY, {sell_count} SELL)")

    # Show WBTC status
    if 'WBTC' in trade_counts:
        wbtc_buy = len(trade_counts['WBTC']['BUY'])
        wbtc_sell = len(trade_counts['WBTC']['SELL'])
        wbtc_diff = wbtc_buy - wbtc_sell
        print(f"  WBTC: Keep all trades (protected) - {wbtc_buy} BUY, {wbtc_sell} SELL ({abs(wbtc_diff)} open)")

    print(f"\n📊 Total trades to delete: {len(trades_to_delete)}")

    if not trades_to_delete:
        print("✅ No trades to delete. All assets are balanced!")
        sys.exit(0)

    # Show details of trades to delete
    print("\n" + "=" * 80)
    print("TRADES TO DELETE (Details)")
    print("=" * 80)

    for trade in sorted(trades_to_delete, key=lambda t: (t.base_asset, t.timestamp)):
        print(f"  {trade.base_asset}: {trade.trade_type} - ID: {trade.exchange_trade_id[:16]}... - Time: {datetime.fromtimestamp(trade.timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S')}")

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
                cursor.execute("DELETE FROM TradeFill WHERE exchange_trade_id = ?", (trade.exchange_trade_id,))
                deleted_count += 1
                print(f"  ✅ Deleted {trade.base_asset} {trade.trade_type} (ID: {trade.exchange_trade_id[:16]}...)")
            except Exception as e:
                print(f"  ❌ Failed to delete {trade.base_asset} trade: {e}")

        conn.commit()

    print(f"\n✅ Deleted {deleted_count} trades")

    # Verify final state
    print("\n" + "=" * 80)
    print("FINAL STATE VERIFICATION")
    print("=" * 80)

    final_trades = db.get_all_trades()
    print(f"Total trades remaining: {len(final_trades)}\n")

    # Count by asset
    final_counts = defaultdict(lambda: {'BUY': 0, 'SELL': 0})
    for trade in final_trades:
        final_counts[trade.base_asset][trade.trade_type] += 1

    print("Final trade counts by asset:")
    for asset in sorted(final_counts.keys()):
        buy = final_counts[asset]['BUY']
        sell = final_counts[asset]['SELL']
        diff = buy - sell
        status = f"({abs(diff)} open {'BUY' if diff > 0 else 'SELL'})" if diff != 0 else "(all matched ✓)"
        print(f"  {asset}: {buy} BUY, {sell} SELL {status}")

    print("\n✅ Cleanup complete!")
    print(f"📦 Backup saved to: {backup_path}")


if __name__ == "__main__":
    main()
