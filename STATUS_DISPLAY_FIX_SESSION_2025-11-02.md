# Status Display Fix - Show All Assets Session
**Date:** 2025-11-02
**Objective:** Fix status display to show ALL trading assets regardless of PnL ranking

## Problem Identified

The status display was only showing top 3 assets by PnL, hiding assets with poor performance (like HYPE with 110 trades but -$2.77 PnL). This made it impossible to identify which TradingView models needed optimization or removal.

### Database Investigation

Using diagnostic script, confirmed HYPE data exists:
- **Raw DB:** 60 BUY, 58 SELL trades
- **Normalized:** 60 BUY, 58 SELL (unchanged)
- **Matched:** 110 positions
- **Open:** 1 position
- **PnL:** -$2.77

### Root Cause

In `mqtt_webhook_strategy_w_cex.py` line 4638, the code limited display to top 3 assets:

```python
sorted_assets = sorted(
    db_pnl['by_asset'].items(),
    key=lambda x: x[1].get('realized_pnl', 0),
    reverse=True
)[:3]  # ← Only top 3!
```

**PnL Ranking:**
1. WBTC: $1.12 (219 trades) ✅ Shown
2. SOL: $0.05 (3 trades) ✅ Shown
3. BTC: -$0.77 (42 trades) ✅ Shown
4. **HYPE: -$2.77 (110 trades)** ❌ Hidden (4th place)

## Solution Implemented

**File:** `scripts/mqtt_webhook_strategy_w_cex.py`
**Lines:** 4630-4644

### Changes Made

1. **Removed** `[:3]` slice to show ALL assets
2. **Updated** label from "Top Assets:" to "All Assets (sorted by PnL):"
3. **Kept** PnL sorting (best to worst) for easy performance analysis

```python
# Show all matched assets sorted by PnL (best to worst)
if db_pnl['by_asset']:
    lines.append("")
    lines.append("  All Assets (sorted by PnL):")  # ← Updated label
    sorted_assets = sorted(
        db_pnl['by_asset'].items(),
        key=lambda x: x[1].get('realized_pnl', 0),
        reverse=True
    )  # ← Removed [:3] slice
    for asset, metrics in sorted_assets:
        pnl = metrics.get('realized_pnl', 0)
        trades = metrics.get('total_trades', 0)
        exchange = metrics.get('exchange', 'N/A')
        network = metrics.get('network', 'N/A')
        lines.append(f"    {asset} ({exchange}/{network}): ${pnl:.2f} ({trades} trades)")
```

## Expected Output

After fix, `status` command now shows:

```
All Assets (sorted by PnL):
  WBTC (uniswap/arbitrum): $1.12 (219 trades)
  SOL (raydium/mainnet-beta): $0.05 (3 trades)
  BTC (hyperliquid_perpetual/hyperliquid): $-0.77 (42 trades)
  HYPE (hyperliquid_perpetual/hyperliquid): $-2.77 (110 trades)  ← Now visible!
```

## Benefits

- ✅ **Full visibility** into ALL trading models/assets
- ✅ **Easy identification** of underperforming models
- ✅ **Informed decisions** about which TradingView models to optimize or disable
- ✅ **PnL-sorted display** makes it easy to spot best and worst performers

## Testing

Diagnostic script (`scripts/debug_hype_missing.py`) confirmed:
- HYPE data exists in database (118 trades total)
- HYPE is properly included in PnL calculations (110 matched positions)
- HYPE was only missing from display due to [:3] limit

## Files Modified

- `scripts/mqtt_webhook_strategy_w_cex.py` (lines 4630-4644)

## Related Work

This fix complements the exchange/network display fix from the previous session, providing complete visibility into:
- Which assets are being traded
- Where they're being traded (exchange/network)
- How they're performing (PnL sorted)
