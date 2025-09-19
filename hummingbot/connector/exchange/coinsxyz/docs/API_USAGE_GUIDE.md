# Coins.xyz Connector API Usage Guide

This comprehensive guide covers all aspects of using the Coins.xyz connector with the Hummingbot framework, including code examples, best practices, and advanced usage patterns.

## 📋 Table of Contents

1. [Quick Start](#quick-start)
2. [Authentication](#authentication)
3. [Market Data](#market-data)
4. [Trading Operations](#trading-operations)
5. [Account Management](#account-management)
6. [WebSocket Streams](#websocket-streams)
7. [Error Handling](#error-handling)
8. [Best Practices](#best-practices)
9. [Advanced Usage](#advanced-usage)

## 🚀 Quick Start

### Basic Connector Initialization

```python
from hummingbot.connector.exchange.coinsxyz.coinsxyz_exchange import CoinsxyzExchange
from hummingbot.client.config.config_helpers import ClientConfigAdapter

# Initialize the connector
config = ClientConfigAdapter()
exchange = CoinsxyzExchange(
    client_config_map=config,
    coinsxyz_api_key="your_api_key",
    coinsxyz_secret_key="your_secret_key",
    trading_pairs=["BTC-USDT", "ETH-USDT"],
    trading_required=True
)

# Start the connector
await exchange.start_network()
```

### Simple Trading Example

```python
from decimal import Decimal
from hummingbot.core.data_type.common import OrderType, TradeType

# Place a limit buy order
order_id = await exchange.buy(
    trading_pair="BTC-USDT",
    amount=Decimal("0.01"),
    order_type=OrderType.LIMIT,
    price=Decimal("45000")
)

print(f"Order placed with ID: {order_id}")
```

## 🔐 Authentication

### API Credentials Setup

```python
from hummingbot.connector.exchange.coinsxyz.coinsxyz_auth import CoinsxyzAuth
from hummingbot.core.utils.time_synchronizer import TimeSynchronizer

# Initialize authentication
time_sync = TimeSynchronizer()
auth = CoinsxyzAuth(
    api_key="your_api_key",
    secret_key="your_secret_key",
    time_provider=time_sync
)

# Validate credentials
if auth.validate_credentials():
    print("✅ Credentials are valid")
else:
    print("❌ Invalid credentials")
```

### Manual Request Signing

```python
# Generate authentication headers
headers = auth.get_auth_headers(
    method="POST",
    url="/api/v1/order",
    data={"symbol": "BTCUSDT", "side": "BUY", "quantity": "0.01"}
)

print("Authentication headers:", headers)
```

## 📊 Market Data

### Get Trading Pairs

```python
# Get all available trading pairs
trading_pairs = await exchange.get_trading_pairs()
print(f"Available pairs: {trading_pairs}")

# Check if a specific pair is supported
is_supported = exchange.is_trading_pair_supported("BTC-USDT")
print(f"BTC-USDT supported: {is_supported}")
```

### Order Book Data

```python
# Get order book snapshot
order_book = exchange.get_order_book("BTC-USDT")
print(f"Best bid: {order_book.get_best_bid()}")
print(f"Best ask: {order_book.get_best_ask()}")

# Get order book depth
bids = order_book.bid_entries()[:5]  # Top 5 bids
asks = order_book.ask_entries()[:5]  # Top 5 asks

for bid in bids:
    print(f"Bid: {bid.price} @ {bid.amount}")
```

### Price and Ticker Data

```python
# Get current price
price = await exchange.get_last_traded_price("BTC-USDT")
print(f"Last traded price: {price}")

# Get 24hr ticker statistics
ticker = await exchange.get_ticker_data("BTC-USDT")
print(f"24hr change: {ticker.price_change_percent}%")
print(f"24hr volume: {ticker.volume}")
```

### Historical Trade Data

```python
# Get recent trades
trades = await exchange.get_recent_trades("BTC-USDT", limit=10)
for trade in trades:
    print(f"Trade: {trade.price} @ {trade.amount} ({trade.timestamp})")
```

## 💰 Trading Operations

### Place Orders

```python
from hummingbot.core.data_type.common import OrderType, TradeType

# Limit Buy Order
buy_order_id = await exchange.buy(
    trading_pair="BTC-USDT",
    amount=Decimal("0.01"),
    order_type=OrderType.LIMIT,
    price=Decimal("45000")
)

# Market Sell Order
sell_order_id = await exchange.sell(
    trading_pair="BTC-USDT",
    amount=Decimal("0.01"),
    order_type=OrderType.MARKET
)

# Limit Maker Order (Post-only)
maker_order_id = await exchange.buy(
    trading_pair="ETH-USDT",
    amount=Decimal("0.1"),
    order_type=OrderType.LIMIT_MAKER,
    price=Decimal("3000")
)
```

### Cancel Orders

```python
# Cancel a specific order
success = await exchange.cancel(
    trading_pair="BTC-USDT",
    order_id=buy_order_id
)

if success:
    print("✅ Order cancelled successfully")

# Cancel all open orders for a trading pair
cancelled_orders = await exchange.cancel_all("BTC-USDT")
print(f"Cancelled {len(cancelled_orders)} orders")
```

### Order Status and Tracking

```python
# Get order status
order = exchange.get_order(buy_order_id)
if order:
    print(f"Order status: {order.current_state}")
    print(f"Filled amount: {order.executed_amount_base}")
    print(f"Remaining: {order.amount - order.executed_amount_base}")

# Get all open orders
open_orders = exchange.get_open_orders()
for order in open_orders:
    print(f"Open order: {order.client_order_id} - {order.current_state}")
```

## 👤 Account Management

### Balance Information

```python
# Get all balances
balances = exchange.get_all_balances()
for asset, balance in balances.items():
    if balance > 0:
        print(f"{asset}: {balance}")

# Get specific asset balance
btc_balance = exchange.get_balance("BTC")
usdt_balance = exchange.get_balance("USDT")

print(f"BTC Balance: {btc_balance}")
print(f"USDT Balance: {usdt_balance}")

# Get available balance (not locked in orders)
available_btc = exchange.get_available_balance("BTC")
print(f"Available BTC: {available_btc}")
```

### Trading Rules and Limits

```python
# Get trading rules for a pair
trading_rule = exchange.get_trading_rule("BTC-USDT")
print(f"Min order size: {trading_rule.min_order_size}")
print(f"Max order size: {trading_rule.max_order_size}")
print(f"Min price increment: {trading_rule.min_price_increment}")
print(f"Min base amount increment: {trading_rule.min_base_amount_increment}")

# Check if order meets requirements
amount = Decimal("0.001")
price = Decimal("45000")

if amount >= trading_rule.min_order_size:
    print("✅ Order amount meets minimum requirement")
else:
    print("❌ Order amount too small")
```

## 🌐 WebSocket Streams

### Market Data Streams

```python
# Subscribe to order book updates
def on_order_book_update(message):
    print(f"Order book update for {message.trading_pair}")
    print(f"Best bid: {message.bids[0] if message.bids else 'N/A'}")
    print(f"Best ask: {message.asks[0] if message.asks else 'N/A'}")

# The connector automatically handles WebSocket subscriptions
# Order book updates are processed internally and available via:
order_book = exchange.get_order_book("BTC-USDT")
```

### User Data Streams

```python
# Account updates are automatically processed
# Listen for balance updates
def on_balance_update(event):
    print(f"Balance update: {event.asset} = {event.total_balance}")

# Listen for order updates
def on_order_update(event):
    print(f"Order update: {event.client_order_id} - {event.new_state}")

# These events are handled internally by the connector
# Access current state via the exchange methods
```

## 🚨 Error Handling

### Exception Handling

```python
from hummingbot.connector.exchange.coinsxyz.coinsxyz_exceptions import (
    CoinsxyzAPIException,
    CoinsxyzNetworkException,
    CoinsxyzOrderException
)

try:
    order_id = await exchange.buy(
        trading_pair="BTC-USDT",
        amount=Decimal("0.01"),
        order_type=OrderType.LIMIT,
        price=Decimal("45000")
    )
except CoinsxyzAPIException as e:
    print(f"API Error: {e.message} (Code: {e.error_code})")
except CoinsxyzNetworkException as e:
    print(f"Network Error: {e}")
except CoinsxyzOrderException as e:
    print(f"Order Error: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

### Retry Logic

```python
import asyncio
from hummingbot.connector.exchange.coinsxyz.coinsxyz_retry_utils import CoinsxyzRetryUtils

# Use built-in retry utilities
retry_util = CoinsxyzRetryUtils()

async def place_order_with_retry():
    for attempt in range(3):
        try:
            order_id = await exchange.buy(
                trading_pair="BTC-USDT",
                amount=Decimal("0.01"),
                order_type=OrderType.LIMIT,
                price=Decimal("45000")
            )
            return order_id
        except Exception as e:
            if attempt < 2:  # Don't wait after last attempt
                wait_time = retry_util.calculate_backoff_delay(attempt)
                print(f"Attempt {attempt + 1} failed, retrying in {wait_time}s...")
                await asyncio.sleep(wait_time)
            else:
                raise e

order_id = await place_order_with_retry()
```

## 🎯 Best Practices

### 1. Connection Management

```python
# Always properly start and stop the connector
async def trading_session():
    try:
        # Start the connector
        await exchange.start_network()
        
        # Your trading logic here
        await your_trading_logic()
        
    finally:
        # Always stop the connector
        await exchange.stop_network()

# Use context manager for automatic cleanup
async with exchange:
    # Trading logic here
    pass
```

### 2. Rate Limiting

```python
# Respect rate limits
import asyncio

async def batch_orders():
    orders = []
    for i in range(10):
        try:
            order_id = await exchange.buy(
                trading_pair="BTC-USDT",
                amount=Decimal("0.001"),
                order_type=OrderType.LIMIT,
                price=Decimal(f"{45000 + i}")
            )
            orders.append(order_id)
            
            # Add delay between orders to respect rate limits
            await asyncio.sleep(0.1)  # 100ms delay
            
        except Exception as e:
            print(f"Failed to place order {i}: {e}")
    
    return orders
```

### 3. Balance Management

```python
# Always check balance before placing orders
async def safe_buy_order(trading_pair: str, amount: Decimal, price: Decimal):
    # Get quote asset (e.g., USDT for BTC-USDT)
    base, quote = trading_pair.split("-")
    
    # Check available balance
    available_balance = exchange.get_available_balance(quote)
    required_balance = amount * price
    
    if available_balance >= required_balance:
        return await exchange.buy(
            trading_pair=trading_pair,
            amount=amount,
            order_type=OrderType.LIMIT,
            price=price
        )
    else:
        raise ValueError(f"Insufficient balance: need {required_balance}, have {available_balance}")
```

### 4. Order Size Validation

```python
# Validate order parameters before placing
def validate_order(trading_pair: str, amount: Decimal, price: Decimal):
    trading_rule = exchange.get_trading_rule(trading_pair)
    
    # Check minimum order size
    if amount < trading_rule.min_order_size:
        raise ValueError(f"Order amount {amount} below minimum {trading_rule.min_order_size}")
    
    # Check maximum order size
    if amount > trading_rule.max_order_size:
        raise ValueError(f"Order amount {amount} above maximum {trading_rule.max_order_size}")
    
    # Check price increment
    price_increment = trading_rule.min_price_increment
    if price % price_increment != 0:
        adjusted_price = (price // price_increment) * price_increment
        print(f"Price adjusted from {price} to {adjusted_price}")
        return adjusted_price
    
    return price

# Use validation before placing orders
validated_price = validate_order("BTC-USDT", Decimal("0.01"), Decimal("45000.123"))
```

## 🔧 Advanced Usage

### Custom Event Handlers

```python
class CustomEventHandler:
    def __init__(self, exchange):
        self.exchange = exchange
        
    async def handle_order_fill(self, event):
        """Handle order fill events"""
        print(f"Order filled: {event.client_order_id}")
        print(f"Fill price: {event.price}")
        print(f"Fill amount: {event.amount}")
        
        # Custom logic after order fill
        await self.post_fill_logic(event)
    
    async def post_fill_logic(self, event):
        """Custom logic to execute after order fill"""
        # Example: Place a new order after fill
        if event.trade_type == TradeType.BUY:
            # Place a sell order at higher price
            sell_price = event.price * Decimal("1.01")  # 1% higher
            await self.exchange.sell(
                trading_pair=event.trading_pair,
                amount=event.amount,
                order_type=OrderType.LIMIT,
                price=sell_price
            )

# Register custom handler
handler = CustomEventHandler(exchange)
```

### Performance Monitoring

```python
import time
from collections import defaultdict

class PerformanceMonitor:
    def __init__(self):
        self.metrics = defaultdict(list)
    
    async def timed_operation(self, operation_name, operation_func, *args, **kwargs):
        """Time an operation and record metrics"""
        start_time = time.time()
        try:
            result = await operation_func(*args, **kwargs)
            success = True
        except Exception as e:
            result = None
            success = False
            raise e
        finally:
            duration = time.time() - start_time
            self.metrics[operation_name].append({
                'duration': duration,
                'success': success,
                'timestamp': start_time
            })
        
        return result
    
    def get_stats(self, operation_name):
        """Get performance statistics"""
        data = self.metrics[operation_name]
        if not data:
            return None
        
        durations = [d['duration'] for d in data]
        success_rate = sum(1 for d in data if d['success']) / len(data)
        
        return {
            'count': len(data),
            'avg_duration': sum(durations) / len(durations),
            'min_duration': min(durations),
            'max_duration': max(durations),
            'success_rate': success_rate
        }

# Usage
monitor = PerformanceMonitor()

# Time order placement
order_id = await monitor.timed_operation(
    'place_order',
    exchange.buy,
    trading_pair="BTC-USDT",
    amount=Decimal("0.01"),
    order_type=OrderType.LIMIT,
    price=Decimal("45000")
)

# Get performance stats
stats = monitor.get_stats('place_order')
print(f"Order placement stats: {stats}")
```

This API usage guide provides comprehensive examples and best practices for using the Coins.xyz connector effectively. For more specific use cases or advanced scenarios, refer to the test files and example strategies in the repository.
