# Hummingbot Configuration Guide
## Comprehensive Configuration Documentation

## Configuration Hierarchy

```plaintext
hummingbot/
├── conf/                      # Configuration directory
│   ├── strategy_config/      # Strategy-specific configurations
│   ├── connector_config/     # Exchange connector configurations
│   └── global_config.yml     # Global settings
```

## 1. Global Configuration

### 1.1 Basic Settings
```yaml
# global_config.yml

# Instance ID for multiple bot management
instance_id: "bot_1"

# Logging configuration
log_level: INFO
log_file_path: "/logs"

# Database settings
db_engine: "sqlite"
db_path: "data/hummingbot.db"

# Kill switch settings
kill_switch_enabled: true
kill_switch_rate: -5.0  # Stop bot if portfolio drops by 5%

# Paper trading settings
paper_trade_enabled: true
paper_trade_account_balance:
  BTC: 1.0
  USDT: 10000.0
```

### 1.2 Risk Management
```yaml
# risk_config.yml

# Position limits
position_limits:
  BTC-USDT:
    max_position_size: 0.1
    max_notional_size: 5000

# Trading limits
trading_limits:
  max_orders_per_minute: 60
  max_order_size: 0.01
  min_order_size: 0.001

# Risk parameters
risk_parameters:
  max_drawdown: 0.1  # 10% maximum drawdown
  stop_loss: 0.02    # 2% stop loss
  take_profit: 0.03  # 3% take profit
```

## 2. Strategy Configuration

### 2.1 Pure Market Making
```yaml
# pure_market_making_config.yml

# Market parameters
exchange: "binance"
trading_pair: "BTC-USDT"
bid_spread: 0.01
ask_spread: 0.01
minimum_spread: 0.005
order_refresh_time: 30.0

# Order sizing
order_amount: 0.001
order_levels: 3
order_level_spread: 0.005
order_level_amount: 0.001

# Advanced parameters
inventory_skew_enabled: true
inventory_target_base_pct: 0.5
inventory_range_multiplier: 1.0
```

### 2.2 Cross-Exchange Market Making
```yaml
# cross_exchange_config.yml

# Markets configuration
maker_market: "binance"
taker_market: "kucoin"
maker_market_trading_pair: "BTC-USDT"
taker_market_trading_pair: "BTC-USDT"

# Profitability configuration
min_profitability: 0.01
order_size_taker_volume_factor: 0.25
order_size_taker_balance_factor: 0.9
order_size_portfolio_ratio_limit: 0.1

# Risk parameters
top_depth_tolerance: 0.01
anti_hysteresis_duration: 60
```

### 2.3 Advanced Market Making
```yaml
# advanced_market_making_config.yml

# Basic parameters
exchange: "binance"
trading_pair: "BTC-USDT"
order_amount: 0.001

# Spread configuration
bid_spread: 0.01
ask_spread: 0.01
minimum_spread: 0.005

# Dynamic spread parameters
dynamic_spread_enabled: true
dynamic_spread_parameters:
  volatility_multiplier: 1.5
  mean_reversion_strength: 0.5

# Position management
position_management:
  target_base_position: 0.5
  position_adjustment_speed: 0.1
  emergency_rebalance_threshold: 0.2

# Advanced execution
execution_parameters:
  order_optimization_enabled: true
  price_improvement_threshold: 0.0001
  cool_off_time: 5
  failed_order_tolerance: 3
```

## 3. Exchange Configuration

### 3.1 Exchange API Settings
```yaml
# exchange_config.yml

binance_paper_trade:
  api_key: "your_api_key"
  secret_key: "your_secret_key"
  
binance_perpetual:
  api_key: "your_perpetual_api_key"
  secret_key: "your_perpetual_secret_key"
  
kucoin:
  api_key: "your_kucoin_api_key"
  secret_key: "your_kucoin_secret_key"
  passphrase: "your_passphrase"
```

### 3.2 Exchange-Specific Parameters
```yaml
# exchange_parameters.yml

binance:
  rate_limits:
    orders_per_second: 10
    orders_per_day: 200000
  trading_fees:
    maker: 0.001
    taker: 0.001
  minimum_order_sizes:
    BTC: 0.001
    ETH: 0.01
    
kucoin:
  rate_limits:
    orders_per_second: 5
    orders_per_day: 100000
  trading_fees:
    maker: 0.001
    taker: 0.001
```

## 4. Script Configuration

### 4.1 Custom Script Parameters
```python
class CustomScriptConfig:
    def __init__(self):
        # Strategy parameters
        self.trading_pair = "BTC-USDT"
        self.order_amount = 0.001
        self.min_spread = 0.002
        self.max_spread = 0.05
        
        # Risk parameters
        self.max_position = 0.1
        self.stop_loss = 0.02
        self.take_profit = 0.03
        
        # Technical indicators
        self.ema_short = 10
        self.ema_long = 20
        self.rsi_period = 14
        self.rsi_oversold = 30
        self.rsi_overbought = 70
        
        # Execution parameters
        self.order_refresh_time = 30
        self.cool_off_time = 5
        self.max_orders_per_minute = 60
```

## 5. Advanced Configuration

### 5.1 Performance Optimization
```yaml
# performance_config.yml

# Memory management
memory_limit: 4096  # MB
garbage_collection_interval: 300  # seconds

# Database optimization
db_batch_size: 100
db_commit_interval: 60

# Network optimization
websocket_connection_timeout: 30
http_connection_timeout: 10
connection_retry_interval: 5
```

### 5.2 Logging Configuration
```yaml
# logging_config.yml

log_level: INFO
log_file_path: "logs/"
log_file_prefix: "hummingbot_"

# Component-specific logging
component_log_levels:
  trading_strategy: DEBUG
  order_tracker: INFO
  market_data: INFO
  risk_manager: DEBUG

# Log rotation
max_log_file_size: 20971520  # 20MB
backup_count: 5
```

## Usage Examples

### 1. Basic Market Making
```bash
# Start with basic market making configuration
python hummingbot/scripts/run_strategy.py \
  --strategy pure_market_making \
  --config-file pure_market_making_config.yml
```

### 2. Advanced Strategy with Custom Parameters
```python
# In your strategy script
from hummingbot.strategy import BaseStrategy
from .config import CustomScriptConfig

class AdvancedTradingStrategy(BaseStrategy):
    def __init__(self):
        config = CustomScriptConfig()
        super().__init__(config)
        
        # Initialize strategy with configuration
        self.initialize_strategy(config)
```

### 3. Configuration Validation
```python
def validate_config(config):
    """Validate strategy configuration"""
    assert config.order_amount > 0, "Order amount must be positive"
    assert 0 < config.min_spread < config.max_spread, "Invalid spread configuration"
    assert 0 < config.stop_loss < 1, "Stop loss must be between 0 and 1"
    assert config.ema_short < config.ema_long, "EMA short period must be less than long period"
```

## Best Practices

1. **Security**
   - Never commit API keys to version control
   - Use environment variables for sensitive data
   - Regularly rotate API keys

2. **Performance**
   - Optimize database settings for your hardware
   - Monitor memory usage and adjust limits
   - Use appropriate logging levels

3. **Risk Management**
   - Always start with paper trading
   - Set conservative position limits
   - Implement kill switches

4. **Maintenance**
   - Regular configuration backups
   - Monitor log files
   - Update exchange parameters

## Troubleshooting

1. **Common Issues**
   - Configuration validation errors
   - Exchange connection issues
   - Order execution failures

2. **Solutions**
   - Verify configuration syntax
   - Check API key permissions
   - Monitor exchange status
   - Review log files

## Configuration Updates

Keep your configurations up to date with:
1. Exchange API changes
2. Trading parameter adjustments
3. Risk management updates
4. Performance optimizations

[Source: Hummingbot Documentation](https://hummingbot.org/developers/strategies/tutorial/) 