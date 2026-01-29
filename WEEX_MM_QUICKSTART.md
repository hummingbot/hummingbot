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
