# Troubleshooting Guide - Coins.xyz Connector

This guide helps you diagnose and resolve common issues when using the Coins.xyz connector with Hummingbot.

## 📋 Table of Contents

1. [Quick Diagnostics](#quick-diagnostics)
2. [Connection Issues](#connection-issues)
3. [Authentication Problems](#authentication-problems)
4. [Trading Issues](#trading-issues)
5. [Performance Problems](#performance-problems)
6. [Known Limitations](#known-limitations)
7. [Error Codes Reference](#error-codes-reference)
8. [Getting Help](#getting-help)

## 🔍 Quick Diagnostics

### Health Check Script

```python
import asyncio
from hummingbot.connector.exchange.coinsxyz.coinsxyz_exchange import CoinsxyzExchange

async def health_check():
    """Quick health check for Coins.xyz connector"""
    print("🔍 Coins.xyz Connector Health Check")
    print("=" * 50)
    
    try:
        # Test 1: Connector initialization
        print("1. Testing connector initialization...")
        exchange = CoinsxyzExchange(
            client_config_map=config,
            coinsxyz_api_key="test_key",
            coinsxyz_secret_key="test_secret",
            trading_pairs=["BTC-USDT"]
        )
        print("✅ Connector initialized successfully")
        
        # Test 2: Network connectivity
        print("2. Testing network connectivity...")
        await exchange.start_network()
        print("✅ Network connection established")
        
        # Test 3: API connectivity
        print("3. Testing API connectivity...")
        server_time = await exchange.get_server_time()
        print(f"✅ API accessible - Server time: {server_time}")
        
        # Test 4: Trading pairs
        print("4. Testing trading pairs...")
        pairs = await exchange.get_trading_pairs()
        print(f"✅ Found {len(pairs)} trading pairs")
        
        await exchange.stop_network()
        print("\n🎉 All health checks passed!")
        
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False
    
    return True

# Run health check
asyncio.run(health_check())
```

### Log Analysis

```bash
# Check Hummingbot logs for Coins.xyz related errors
tail -f logs/hummingbot_logs.log | grep -i coinsxyz

# Filter for specific error types
grep -i "error\|exception\|failed" logs/hummingbot_logs.log | grep -i coinsxyz
```

## 🌐 Connection Issues

### Issue: "Unable to connect to Coins.xyz API"

**Symptoms:**
- Connection timeout errors
- "Network unreachable" messages
- WebSocket connection failures

**Solutions:**

1. **Check Internet Connection**
   ```bash
   # Test basic connectivity
   ping api.coins.xyz
   
   # Test HTTPS connectivity
   curl -I https://api.coins.xyz/openapi/v1/ping
   ```

2. **Verify API Endpoints**
   ```python
   # Test API endpoint accessibility
   import requests
   
   try:
       response = requests.get("https://api.coins.xyz/openapi/v1/ping", timeout=10)
       print(f"API Status: {response.status_code}")
   except requests.exceptions.RequestException as e:
       print(f"Connection failed: {e}")
   ```

3. **Check Firewall/Proxy Settings**
   ```bash
   # If behind corporate firewall, check proxy settings
   export https_proxy=http://your-proxy:port
   export http_proxy=http://your-proxy:port
   ```

4. **DNS Resolution Issues**
   ```bash
   # Check DNS resolution
   nslookup api.coins.xyz
   
   # Try alternative DNS
   echo "nameserver 8.8.8.8" >> /etc/resolv.conf
   ```

### Issue: "WebSocket connection failed"

**Solutions:**

1. **Check WebSocket Endpoint**
   ```python
   import websocket
   
   def on_message(ws, message):
       print(f"Received: {message}")
   
   def on_error(ws, error):
       print(f"WebSocket error: {error}")
   
   # Test WebSocket connection
   ws = websocket.WebSocketApp(
       "wss://stream.coins.xyz/openapi/ws",
       on_message=on_message,
       on_error=on_error
   )
   ws.run_forever()
   ```

2. **Proxy Configuration for WebSocket**
   ```python
   # Configure WebSocket proxy
   ws = websocket.WebSocketApp(
       "wss://stream.coins.xyz/openapi/ws",
       http_proxy_host="proxy.company.com",
       http_proxy_port=8080
   )
   ```

## 🔐 Authentication Problems

### Issue: "Invalid API signature"

**Symptoms:**
- 401 Unauthorized errors
- "Signature verification failed" messages
- Authentication-related API errors

**Solutions:**

1. **Verify API Credentials**
   ```python
   # Test credential format
   api_key = "your_api_key"
   secret_key = "your_secret_key"
   
   print(f"API Key length: {len(api_key)}")
   print(f"Secret Key length: {len(secret_key)}")
   print(f"API Key format: {'✅' if api_key.isalnum() else '❌'}")
   ```

2. **Check Time Synchronization**
   ```python
   import time
   import requests
   
   # Get local time
   local_time = int(time.time() * 1000)
   
   # Get server time
   response = requests.get("https://api.coins.xyz/openapi/v1/time")
   server_time = response.json()["serverTime"]
   
   time_diff = abs(local_time - server_time)
   print(f"Time difference: {time_diff}ms")
   
   if time_diff > 5000:  # 5 seconds
       print("⚠️ Time synchronization issue detected")
   ```

3. **Test Signature Generation**
   ```python
   from hummingbot.connector.exchange.coinsxyz.coinsxyz_auth import CoinsxyzAuth
   
   # Test signature generation
   auth = CoinsxyzAuth(api_key, secret_key, time_provider)
   
   test_params = {"symbol": "BTCUSDT", "side": "BUY"}
   signature = auth._generate_signature(test_params)
   print(f"Generated signature: {signature}")
   ```

### Issue: "API key permissions insufficient"

**Solutions:**

1. **Check API Key Permissions**
   - Log into Coins.xyz account
   - Navigate to API Management
   - Verify permissions: "Read", "Trade", "Withdraw" (if needed)

2. **Test Permission Levels**
   ```python
   # Test read permissions
   try:
       balances = await exchange.get_all_balances()
       print("✅ Read permissions working")
   except Exception as e:
       print(f"❌ Read permissions failed: {e}")
   
   # Test trade permissions
   try:
       # Small test order (will likely fail due to insufficient balance)
       await exchange.buy("BTC-USDT", Decimal("0.001"), OrderType.LIMIT, Decimal("1"))
   except Exception as e:
       if "insufficient" in str(e).lower():
           print("✅ Trade permissions working (insufficient balance)")
       else:
           print(f"❌ Trade permissions failed: {e}")
   ```

## 💰 Trading Issues

### Issue: "Order placement failed"

**Common Causes & Solutions:**

1. **Insufficient Balance**
   ```python
   # Check balance before placing order
   def check_balance_for_order(trading_pair, amount, price, side):
       base, quote = trading_pair.split("-")
       
       if side == "BUY":
           required = amount * price
           available = exchange.get_available_balance(quote)
           asset = quote
       else:
           required = amount
           available = exchange.get_available_balance(base)
           asset = base
       
       print(f"Required {asset}: {required}")
       print(f"Available {asset}: {available}")
       
       return available >= required
   ```

2. **Invalid Order Parameters**
   ```python
   # Validate order parameters
   def validate_order_params(trading_pair, amount, price):
       trading_rule = exchange.get_trading_rule(trading_pair)
       
       errors = []
       
       if amount < trading_rule.min_order_size:
           errors.append(f"Amount {amount} below minimum {trading_rule.min_order_size}")
       
       if amount > trading_rule.max_order_size:
           errors.append(f"Amount {amount} above maximum {trading_rule.max_order_size}")
       
       if price % trading_rule.min_price_increment != 0:
           errors.append(f"Price increment invalid. Must be multiple of {trading_rule.min_price_increment}")
       
       return errors
   ```

3. **Market Closed/Suspended**
   ```python
   # Check trading pair status
   async def check_trading_status(trading_pair):
       try:
           ticker = await exchange.get_ticker_data(trading_pair)
           print(f"Trading pair {trading_pair} is active")
           return True
       except Exception as e:
           print(f"Trading pair {trading_pair} may be suspended: {e}")
           return False
   ```

### Issue: "Order not filling"

**Diagnostic Steps:**

1. **Check Order Status**
   ```python
   # Monitor order status
   order = exchange.get_order(order_id)
   print(f"Order status: {order.current_state}")
   print(f"Filled: {order.executed_amount_base}/{order.amount}")
   ```

2. **Check Market Conditions**
   ```python
   # Analyze order book
   order_book = exchange.get_order_book(trading_pair)
   best_bid = order_book.get_best_bid()
   best_ask = order_book.get_best_ask()
   
   print(f"Best bid: {best_bid}")
   print(f"Best ask: {best_ask}")
   print(f"Your order price: {order.price}")
   ```

## ⚡ Performance Problems

### Issue: "Slow order execution"

**Optimization Strategies:**

1. **Connection Optimization**
   ```python
   # Use connection pooling
   import aiohttp
   
   connector = aiohttp.TCPConnector(
       limit=100,  # Total connection pool size
       limit_per_host=30,  # Per-host connection limit
       keepalive_timeout=30,
       enable_cleanup_closed=True
   )
   ```

2. **Reduce API Calls**
   ```python
   # Batch operations where possible
   async def batch_cancel_orders(order_ids):
       # Cancel all orders for a trading pair at once
       return await exchange.cancel_all(trading_pair)
   ```

3. **Optimize WebSocket Usage**
   ```python
   # Subscribe only to necessary streams
   essential_pairs = ["BTC-USDT", "ETH-USDT"]  # Only pairs you're trading
   ```

### Issue: "High memory usage"

**Memory Optimization:**

1. **Limit Cache Size**
   ```python
   # Configure cache limits in connector
   exchange._order_book_tracker.set_cache_limit(1000)
   ```

2. **Regular Cleanup**
   ```python
   # Periodic cleanup of old data
   async def cleanup_old_data():
       # Clear old trade history
       exchange._trade_history.clear_old_entries(hours=24)
   ```

## ⚠️ Known Limitations

### Current Limitations

1. **Trading Pairs**
   - Limited to spot trading pairs available on Coins.xyz
   - No futures or margin trading support
   - Some pairs may have minimum order size restrictions

2. **Order Types**
   - Supported: LIMIT, MARKET, LIMIT_MAKER
   - Not supported: STOP_LOSS, TAKE_PROFIT, OCO orders

3. **Rate Limits**
   - API: 1200 requests per minute
   - Orders: 10 orders per second
   - WebSocket: 5 connections per IP

4. **WebSocket Limitations**
   - Maximum 1024 subscriptions per connection
   - Automatic reconnection with exponential backoff
   - No guaranteed message ordering during reconnection

### Workarounds

1. **For High-Frequency Trading**
   ```python
   # Implement local order management
   class LocalOrderManager:
       def __init__(self):
           self.pending_orders = {}
           self.order_queue = asyncio.Queue()
       
       async def queue_order(self, order_params):
           await self.order_queue.put(order_params)
       
       async def process_orders(self):
           while True:
               order_params = await self.order_queue.get()
               # Process with rate limiting
               await asyncio.sleep(0.1)  # 100ms between orders
               await self.place_order(order_params)
   ```

2. **For Large Orders**
   ```python
   # Split large orders into smaller chunks
   async def split_large_order(trading_pair, total_amount, chunk_size):
       chunks = []
       remaining = total_amount
       
       while remaining > 0:
           chunk = min(chunk_size, remaining)
           chunks.append(chunk)
           remaining -= chunk
       
       return chunks
   ```

## 📚 Error Codes Reference

### HTTP Error Codes

| Code | Description | Solution |
|------|-------------|----------|
| 400 | Bad Request | Check request parameters |
| 401 | Unauthorized | Verify API credentials |
| 403 | Forbidden | Check API key permissions |
| 429 | Rate Limited | Implement rate limiting |
| 500 | Server Error | Retry with exponential backoff |
| 503 | Service Unavailable | Check Coins.xyz status |

### Coins.xyz Specific Errors

| Error Code | Description | Solution |
|------------|-------------|----------|
| -1000 | Unknown error | Contact support |
| -1001 | Disconnected | Reconnect to API |
| -1002 | Unauthorized | Check credentials |
| -1003 | Too many requests | Reduce request rate |
| -2010 | New order rejected | Check order parameters |
| -2011 | Cancel rejected | Order may already be filled |

### WebSocket Error Codes

| Code | Description | Solution |
|------|-------------|----------|
| 1000 | Normal closure | Reconnect if needed |
| 1006 | Abnormal closure | Check network connection |
| 1011 | Server error | Retry connection |

## 🆘 Getting Help

### Before Seeking Help

1. **Check Logs**
   ```bash
   # Recent errors
   tail -100 logs/hummingbot_logs.log | grep -i error
   
   # Specific connector errors
   grep -i coinsxyz logs/hummingbot_logs.log | tail -50
   ```

2. **Run Diagnostics**
   ```python
   # Generate diagnostic report
   async def generate_diagnostic_report():
       report = {
           "connector_version": exchange.__version__,
           "python_version": sys.version,
           "hummingbot_version": hummingbot.__version__,
           "system_info": platform.platform(),
           "network_status": await test_connectivity(),
           "auth_status": auth.validate_credentials(),
           "recent_errors": get_recent_errors()
       }
       return report
   ```

### Support Channels

1. **GitHub Issues**: [Report bugs](https://github.com/your-repo/hummingbot-connector-coinsxyz/issues)
2. **Hummingbot Discord**: [Community support](https://discord.gg/hummingbot)
3. **Documentation**: [Official docs](https://docs.hummingbot.org/)

### When Reporting Issues

Include the following information:

1. **Environment Details**
   - Operating system and version
   - Python version
   - Hummingbot version
   - Connector version

2. **Error Information**
   - Complete error message
   - Stack trace
   - Steps to reproduce
   - Expected vs actual behavior

3. **Configuration**
   - Trading pairs used
   - Strategy configuration (sanitized)
   - Any custom modifications

4. **Logs**
   - Relevant log entries (sanitize sensitive data)
   - Timestamp of the issue
   - Frequency of occurrence

---

**💡 Remember**: Most issues can be resolved by checking credentials, network connectivity, and API rate limits. Always test with small amounts first!
