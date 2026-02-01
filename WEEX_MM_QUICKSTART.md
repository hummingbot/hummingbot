# WEEX VCC Market Making - Quick Start Guide

## Overview
Your custom market making strategy for WEEX VCC-USDT is ready to go!

## Files Created
1. **Strategy Script**: `scripts/weex_vcc_pmm.py`
2. **Configuration**: `conf/scripts/weex_vcc_pmm.yml`

## Current Configuration

### Trading Parameters
- **Exchange**: WEEX
- **Trading Pair**: VCCUSDT-SPBL
- **Order Size**: 35,000 VCC (~$5.25 at current price)
- **Bid Spread**: 0.5% below mid price
- **Ask Spread**: 0.5% above mid price
- **Order Refresh**: Every 30 seconds

### Example at Current Price (0.00015 USDT)
- **Mid Price**: 0.00015000 USDT
- **Buy Order**: 35,000 VCC @ 0.00014925 = $5.22
- **Sell Order**: 35,000 VCC @ 0.00015075 = $5.28
- **Spread Profit**: 1% (buy-sell difference)

## How to Run

### Step 1: Start Hummingbot
```bash
./start
```

### Step 2: Connect to WEEX
```
connect weex
```
- Enter your API key
- Enter your API secret
- Enter your API passphrase

### Step 3: Import the Strategy
```
import weex_vcc_pmm
```

### Step 4: Configure (if needed)
```
config
```
You can adjust:
- `order_amount`: VCC per order (default: 35000)
- `bid_spread`: Distance below mid (default: 0.005 = 0.5%)
- `ask_spread`: Distance above mid (default: 0.005 = 0.5%)
- `order_refresh_time`: Seconds between refreshes (default: 30)

### Step 5: Start the Bot
```
start
```

### Step 6: Monitor
```
status
```
Shows:
- Current market price
- Your balances
- Active orders
- Strategy parameters

## Risk Management

### Kill Switch (Recommended)
Set up automatic stop-loss:
```
config kill_switch_enabled
yes

config kill_switch_rate
-0.03
```
This stops the bot if you lose 3% of your portfolio value.

### Balance Requirements
At current price (~0.00015 USDT):
- **VCC needed**: ~35,000 per sell order
- **USDT needed**: ~$5.25 per buy order
- **Recommended**: Keep at least 10x minimum to handle multiple orders

### Monitoring Alerts
Enable Telegram notifications:
```
telegram
```
Get notified of:
- Order fills
- Errors
- Performance updates

## Adjusting Strategy

### Tighter Spreads (More Aggressive)
For faster fills but lower profit per trade:
```yml
bid_spread: 0.002  # 0.2%
ask_spread: 0.002  # 0.2%
```

### Wider Spreads (More Conservative)
For higher profit per trade but slower fills:
```yml
bid_spread: 0.01   # 1%
ask_spread: 0.01   # 1%
```

### Larger Orders
If you have more capital:
```yml
order_amount: 70000  # ~$10.50 at current price
```

### Faster Refresh
For more responsive pricing:
```yml
order_refresh_time: 15  # 15 seconds
```

## Performance Monitoring

### Check Trades
```
history
```

### Check PnL
```
pnl
```

### Export Trading History
```
export_trades
```

## Stopping the Bot

### Graceful Stop
```
stop
```
This cancels all orders and stops the strategy.

### Emergency Stop
Press `Ctrl+C` twice

### Exit Hummingbot
```
exit
```

## Troubleshooting

### Orders Not Placing
- Check balances: `balance`
- Check minimum $5 requirement
- Verify API keys: `connect weex`

### Price Errors
- Check ticker data is available
- Verify trading pair format: `VCCUSDT-SPBL`

### Orders Not Filling
- Spreads may be too wide
- Market may be illiquid
- Adjust spreads in config

## Volume Generation Strategy

### When to Use Volume Generator vs Market Maker

**Use Market Maker (`weex_vcc_pmm`)** when:
- You want to profit from bid-ask spreads
- Organic market activity provides fills
- You're providing liquidity and waiting for counterparties

**Use Volume Generator (`weex_volume_generator`)** when:
- You need to guarantee minimum daily volume (e.g., 10k USDT)
- Volume requirements must be met regardless of market activity
- You need predictable, consistent trading volume

### Running the Volume Generator

The volume generator actively trades to ensure minimum daily volume targets are met.

#### Step 1: Import the Strategy
```
import weex_volume_generator
```

#### Step 2: Configure Volume Target
Edit `conf/scripts/weex_volume_generator.yml`:
```yml
daily_volume_target_usdt: 10000  # $10k per day
trade_interval_seconds: 300      # Trade every 5 minutes (288 trades/day)
order_size_usdt: 35             # ~$35 per trade
```

#### Step 3: Start
```
start
```

#### How It Works
1. **Automated Trading**: Places trades every 5 minutes (configurable)
2. **Volume Target**: Ensures 10k USDT volume per day minimum
3. **Inventory Neutral**: Alternates BUY/SELL to maintain balanced inventory
4. **Spread Crossing**: Orders cross the spread to guarantee fills
5. **Daily Reset**: Volume counter resets at midnight

#### Balance Requirements
For 10k daily volume target:
- **USDT**: ~$200-300 (for buy orders)
- **VCC**: ~1,000,000 VCC (~$150-200 at $0.00015)
- Recommended: 2-3x minimum for safety buffer

#### Expected Costs
- Trading fees: ~0.2-0.4% of volume (~$20-40 per $10k)
- Spread crossing: ~0.2% (~$20 per $10k)
- **Total**: ~$40-60 per $10k volume

#### Monitoring
```
status  # Shows volume progress and inventory
```

Output shows:
- Today's volume vs target
- Trades completed
- Estimated time to target
- Inventory deviation
- Next trade timing

#### Key Configuration Options

**Trading Frequency**:
```yml
trade_interval_seconds: 180  # 480 trades/day (~$21/trade)
trade_interval_seconds: 300  # 288 trades/day (~$35/trade) - Default
trade_interval_seconds: 600  # 144 trades/day (~$70/trade)
```

**Order Type**:
```yml
order_type: limit_cross_spread  # Recommended - crosses spread with limit orders
order_type: market              # Alternative - uses market orders
```

**Inventory Management**:
```yml
rebalance_threshold: 150000     # Auto-rebalance when inventory deviates by 150k VCC
```

### Running Both Strategies Simultaneously

You can run volume generator AND market maker together:

**Option 1: Same Instance (Same Trading Pair)**
⚠️ Not recommended - strategies may conflict

**Option 2: Different Instances (Recommended)**
- Instance 1: Volume generator on VCC-USDT
- Instance 2: Market maker on VCC-USDT or other pairs
- Each maintains its own inventory and tracks separately

**Option 3: Different Trading Pairs**
- Instance 1: Volume generator on VCC-USDT
- Same instance: Market maker on WXT-USDT, etc.

## Advanced: Multiple Trading Pairs

To market make on multiple pairs, create copies:
```bash
cp scripts/weex_vcc_pmm.py scripts/weex_wxt_pmm.py
cp conf/scripts/weex_vcc_pmm.yml conf/scripts/weex_wxt_pmm.yml
```

Edit the new files to change the trading pair.

## Support
- Hummingbot Docs: https://docs.hummingbot.org
- Discord: https://discord.hummingbot.io
- Test thoroughly before deploying significant capital!

## Notes
- Strategy tested and validated on January 29, 2026
- All WEEX API endpoints verified working
- $5 USDT minimum order size confirmed
- Ready for production deployment
