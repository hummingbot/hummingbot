# 10-Minute Quick Start Guide: Running & Backtesting Your Strategy

## Quick Setup (2 minutes)

1. **Open Terminal & Navigate to Project**:
```bash
cd /path/to/NPC_G3
```

2. **Create & Activate Virtual Environment**:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: .\venv\Scripts\activate
```

3. **Install Dependencies**:
```bash
pip install -r requirements.txt
```

## Run Your Strategy (3 minutes)

1. **Quick Test Run**:
```bash
python hummingbot/scripts/run_strategy_example.py
```

This will:
- Load the example adaptive market making strategy
- Connect to Binance (paper trading)
- Start running with default parameters
- Show real-time logs of trades and performance

2. **Monitor Output**:
- Watch for "Strategy initialized" message
- Observe indicator calculations (RSI, EMA)
- Check for trade signals and executions
- Monitor performance metrics

3. **Key Metrics to Watch**:
- Position size
- Entry/Exit prices
- PnL (Profit and Loss)
- Win rate
- Maximum drawdown

## Backtest Your Strategy (5 minutes)

1. **Prepare Historical Data**:
```python
# In hummingbot/scripts/backtest_strategy.py
from hummingbot.scripts.run_strategy_example import MarketDataFeed

# Get historical data
data_feed = MarketDataFeed(
    exchange_id="binance",
    symbol="BTC/USDT"
)

# Fetch last 1000 candles of 1-minute data
historical_data = data_feed.get_historical_data(
    timeframe='1m',
    limit=1000
)
```

2. **Run Backtest**:
```python
from hummingbot.scripts.simple_example import SimpleExampleStrategy, SimpleExampleConfig

# Create strategy instance
config = SimpleExampleConfig()
strategy = SimpleExampleStrategy(config)

# Feed historical data
for _, row in historical_data.iterrows():
    strategy.on_tick(row.to_dict())
    
# Get results
metrics = strategy.get_performance_metrics()
trades = strategy.get_trade_history()
```

3. **Analyze Results**:
```python
print(f"Total Trades: {len(trades)}")
print(f"Total PnL: {metrics['total_pnl']*100:.2f}%")
print(f"Win Rate: {metrics['win_rate']*100:.2f}%")
print(f"Max Drawdown: {metrics['max_drawdown']*100:.2f}%")
```

## Modify Strategy Parameters (2 minutes)

1. **Quick Parameter Adjustments**:
Open `hummingbot/scripts/simple_example.py` and modify:
```python
class SimpleExampleConfig:
    def __init__(self):
        # Adjust these parameters
        self.rsi_oversold = 30    # Buy signal
        self.rsi_overbought = 70  # Sell signal
        self.stop_loss = 0.02     # 2% stop loss
        self.take_profit = 0.03   # 3% take profit
```

2. **Run Modified Strategy**:
```bash
python hummingbot/scripts/run_strategy_example.py
```

## Common Issues & Quick Fixes

1. **Strategy Not Starting**:
- Check exchange connection
- Verify API keys (if using real trading)
- Ensure sufficient balance (paper trading uses simulated balance)

2. **No Trades Executing**:
- Check if indicators have enough data
- Verify signal thresholds aren't too strict
- Confirm market data is being received

3. **Error Messages**:
- "Historical data fetch failed": Check internet connection
- "Invalid configuration": Verify all required parameters
- "Position error": Check position size calculations

## Next Steps

1. **Optimize Your Strategy**:
- Adjust indicator parameters
- Fine-tune entry/exit conditions
- Modify risk management settings

2. **Advanced Features**:
- Add more technical indicators
- Implement multi-timeframe analysis
- Enhance risk management rules

3. **Production Deployment**:
- Test thoroughly with paper trading
- Start with small position sizes
- Monitor performance closely

Remember:
- Always test with paper trading first
- Start with small positions when going live
- Keep track of all trades and performance
- Monitor system logs for issues

Need help? Check:
1. Strategy logs (INFO level)
2. Performance metrics
3. Trade history
4. System status 