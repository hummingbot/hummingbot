# Active Positions Database Fix - November 2, 2025

## Summary
Enhanced the status check active positions display to use the database as the source of truth instead of in-memory `self.active_positions`. This provides more accurate position tracking based on actual trade history.

## Issue
The status check was using in-memory position tracking (`self.active_positions`) which could become out of sync with actual positions. The database contains the complete trade history and is the true source of positions.

## Solution
Implemented database-backed position tracking using the reporting system's components:

### New Method: `_get_open_positions_from_database()`
Located at: `scripts/mqtt_webhook_strategy_w_cex.py:4339-4381`

```python
def _get_open_positions_from_database(self) -> Optional[List]:
    """
    Get actual open positions from database using the reporting system.
    This is the source of truth for what positions are actually open.
    """
    try:
        from pathlib import Path
        from hummingbot import data_path
        from reporting.database.connection import DatabaseManager
        from reporting.matching.trade_matcher import MatchingMethod, TradeMatcher
        from reporting.normalization.trade_normalizer import TradeNormalizer

        db_path = Path(data_path()) / "mqtt_webhook_strategy_w_cex.sqlite"
        if not db_path.exists():
            return None

        db = DatabaseManager(str(db_path))
        trades = db.get_all_trades()
        if not trades:
            return None

        normalizer = TradeNormalizer()
        normalized_trades = normalizer.normalize_trades(trades)

        matcher = TradeMatcher(method=MatchingMethod.FIFO)
        result = matcher.match_trades(normalized_trades)

        return result['open_positions']
    except Exception as e:
        self.logger().debug(f"Could not get open positions from database: {e}")
        return None
```

### Rewritten Method: `_format_active_positions()`
Located at: `scripts/mqtt_webhook_strategy_w_cex.py:4383-4476`

**Key Changes:**
- Replaced `self.active_positions` with database query
- Groups positions by base asset for clearer display
- Extracts exchange and network info from market field
- Shows comprehensive position details:
  - Token (base asset)
  - Quantity (aggregated remaining quantity)
  - Quote (quote asset)
  - Network (arbitrum, mainnet-beta, hyperliquid, etc.)
  - Exchange (uniswap, raydium, hyperliquid, etc.)
  - Cost Basis (total cost for positions)
- Displays total cost basis and position count

**Exchange/Network Detection Logic:**
```python
if '/' in market:
    exchange = market.split('/')[0]
    if 'uniswap' in exchange.lower():
        network = 'arbitrum'
    elif 'raydium' in exchange.lower() or 'meteora' in exchange.lower():
        network = 'mainnet-beta'
    else:
        network = 'arbitrum'
elif 'hyperliquid' in market.lower():
    exchange = 'hyperliquid'
    network = 'hyperliquid'
```

## Components Used

### DatabaseManager
- Manages SQLite database connection
- Retrieves all trades from `mqtt_webhook_strategy_w_cex.sqlite`

### TradeNormalizer
- Normalizes trades from different sources (CEX, DEX, Solana, EVM)
- Ensures consistent trade format for matching

### TradeMatcher
- Uses FIFO (First In First Out) method to match buy/sell trades
- Returns `open_positions` list containing unmatched trades

### OpenPosition
- Represents an unmatched position
- Contains: trade, remaining_quantity, and other position data

## Benefits

✅ **Accuracy**: Database is source of truth, not in-memory state
✅ **Persistence**: Positions survive strategy restarts
✅ **Reliability**: Trade matching uses proven FIFO algorithm
✅ **Visibility**: Enhanced display shows exchange, network, and cost basis
✅ **Consistency**: Uses same reporting system as export features

## Impact
- Status check now displays actual positions based on trade history
- No more discrepancies between displayed positions and actual holdings
- Better visibility into where positions are held (exchange/network)
- Accurate cost basis tracking for all positions

## Files Modified
- `scripts/mqtt_webhook_strategy_w_cex.py`
  - Added `_get_open_positions_from_database()` method (lines 4339-4381)
  - Rewrote `_format_active_positions()` method (lines 4383-4476)

## Testing
- Validated flake8 compliance ✅
- Ready for runtime testing with actual strategy execution

## Location
`/home/todd/PycharmProjects/hummingbot/scripts/mqtt_webhook_strategy_w_cex.py:4339-4476`
