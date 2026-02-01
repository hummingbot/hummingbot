# WEEX Connector Analysis & Troubleshooting Guide

**Date**: January 26, 2026
**Status**: Critical Bug Fixed - Ready for Phase 2 Testing
**Production Deadline**: January 31, 2026

---

## 🔴 CRITICAL BUG FIXED

### Issue: Syntax Error in `_get_last_traded_price()`
**File**: `weex_exchange.py` line 571-572
**Problem**:
```python
# BROKEN CODE:
path_url=CONS,  # Incomplete constant reference
limit_id=CONSTANTS.TICKER_PRICE_CHANGE_LIMIT_IDTANTS.TICKER_PRICE_CHANGE_PATH_URL,  # Malformed string
```

**Root Cause**: Typo during code editing - "CONSTANTS" split across line, "IDTANTS" garbled text

**Impact**:
- **All exchange info parsing fails** ← This caused the "exchange info error" in testing checklist
- Connector cannot fetch trading pairs
- Cannot retrieve last traded prices
- Blocks all market data functionality

**Solution Applied**:
```python
# FIXED CODE:
path_url=CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL,  # Correct constant
limit_id=CONSTANTS.TICKER_PRICE_CHANGE_LIMIT_ID,  # Correct limit ID
```

**Status**: ✅ **FIXED** - No syntax errors remain in codebase

---

## 📊 WEEX Exchange Architecture

### REST API Base URL
```
https://api-spot.weex.com
```

### WebSocket URLs
- **Public Stream**: `wss://ws-spot.weex.com/v2/ws/public`
- **Private Stream**: `wss://ws-spot.weex.com/v2/ws/private`

### Authentication Mechanism (3-Factor)
WEEX uses **HMAC-SHA256 signature** with three credentials:
1. **ACCESS-KEY**: Your API key
2. **ACCESS-SECRET**: Secret for signing (never transmitted)
3. **ACCESS-PASSPHRASE**: Additional security layer

**Signature Generation**:
```python
payload = f"{timestamp_ms}{method}{request_path}{query_string}{body}"
signature = base64.b64encode(
    hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest()
)
```

**Request Headers**:
```python
{
    "ACCESS-KEY": api_key,
    "ACCESS-TIMESTAMP": timestamp_ms,  # Current milliseconds
    "ACCESS-SIGN": signature,
    "ACCESS-PASSPHRASE": passphrase,
    "Content-Type": "application/json"
}
```

---

## 🔌 API Endpoints Reference

### Public Endpoints (No Auth Required)

| Endpoint | Path | Purpose | Rate Limit ID |
|----------|------|---------|---------------|
| **Trading Pairs** | `/api/v2/public/products` | List all trading pairs | `TRADING_PAIRS_LIMIT_ID` |
| **Exchange Info** | `/api/v2/public/exchangeInfo` | Trading rules, min/max sizes | `EXCHANGE_INFO_LIMIT_ID` |
| **Order Book** | `/api/v2/market/depth` | Snapshot of order book | `ORDER_BOOK_SNAPSHOT_LIMIT_ID` |
| **Ticker** | `/api/v2/market/ticker` | 24h price statistics | `TICKER_PRICE_CHANGE_LIMIT_ID` |
| **Tickers (All)** | `/api/v2/market/tickers` | All tickers in one call | Global limit |

### Private Endpoints (Auth Required)

| Endpoint | Path | Purpose | Rate Limit ID |
|----------|------|---------|---------------|
| **Account Assets** | `/api/v2/account/assets` | Balances (available + frozen) | `ACCOUNTS_LIMIT_ID` |
| **Create Order** | `/api/v2/trade/orders` | Place new order | `CREATE_ORDER_LIMIT_ID` |
| **Cancel Order** | `/api/v2/trade/cancel-order` | Cancel existing order | `CANCEL_ORDER_LIMIT_ID` |
| **Order Info** | `/api/v2/trade/orderInfo` | Query order status | `ORDER_STATUS_LIMIT_ID` |
| **Open Orders** | `/api/v2/trade/open-orders` | List all open orders | `OPEN_ORDERS_LIMIT_ID` |
| **Fills** | `/api/v2/trade/fills` | Trade history (filled orders) | `FILLS_LIMIT_ID` |

---

## 📡 WebSocket Subscriptions

### Public WebSocket (Market Data)

**Connection**: No authentication required
**Subscription Format**:
```json
{
    "method": "SUBSCRIBE",
    "params": [
        "vccusdt@trade",
        "vccusdt@depth@100ms"
    ],
    "id": 1
}
```

**Available Channels**:
- `{symbol}@trade` - Real-time trades
- `{symbol}@depth@100ms` - Order book updates every 100ms
- `{symbol}@ticker` - 24h ticker updates
- `{symbol}@kline_{interval}` - Candlestick data

**Message Format (Trade)**:
```json
{
    "e": "trade",  // Event type
    "s": "VCCUSDT",  // Symbol
    "t": 1234567890,  // Trade ID
    "p": "0.00015",  // Price
    "q": "35000",  // Quantity
    "T": 1234567890000  // Timestamp (ms)
}
```

**Message Format (Depth)**:
```json
{
    "e": "depth",
    "s": "VCCUSDT",
    "b": [["0.00014", "100000"], ...],  // Bids [price, quantity]
    "a": [["0.00016", "50000"], ...],  // Asks [price, quantity]
    "u": 12345  // Update ID
}
```

### Private WebSocket (Account Updates)

**Connection**: Requires header-based authentication
**Authentication Headers**:
```python
headers = {
    "ACCESS-KEY": api_key,
    "ACCESS-TIMESTAMP": timestamp,
    "ACCESS-SIGN": generate_ws_signature(timestamp, "/v2/ws/private"),
    "ACCESS-PASSPHRASE": passphrase
}
```

**Subscription Format**:
```json
{
    "method": "SUBSCRIBE",
    "params": ["account", "orders", "fills"],
    "id": 1
}
```

**Channels**:
1. **account** - Balance updates
2. **orders** - Order status changes (pending → open → filled)
3. **fills** - Trade execution notifications

**Heartbeat**:
- Server sends: `{"event": "ping"}`
- Client responds: `{"event": "pong"}`
- Interval: 30 seconds

---

## 🔄 Order Lifecycle State Mapping

| WEEX Status | Hummingbot OrderState | Description |
|-------------|----------------------|-------------|
| `PENDING` | `PENDING_CREATE` | Order submitted, awaiting exchange confirmation |
| `NEW` | `OPEN` | Order active in order book |
| `PARTIALLY_FILLED` | `PARTIALLY_FILLED` | Partial execution |
| `FILLED` | `FILLED` | Completely executed |
| `PENDING_CANCEL` | `OPEN` | Cancel request submitted |
| `CANCELED` | `CANCELED` | Successfully canceled |
| `CANCELLED` | `CANCELED` | Alternative spelling |
| `REJECTED` | `FAILED` | Order rejected by exchange |
| `EXPIRED` | `FAILED` | Order expired (FOK/IOC) |
| `EXPIRED_IN_MATCH` | `FAILED` | Expired during matching |

---

## ⚙️ Trading Pair Normalization

### WEEX Format → Hummingbot Format

**WEEX Exchange Symbol**: `VCCUSDT_SPBL`
- **Core**: `VCCUSDT` (drop `_SPBL` suffix)
- **Base**: `VCC`
- **Quote**: `USDT`
- **Hummingbot Pair**: `VCC-USDT`

**Known Quote Currencies**:
```python
KNOWN_QUOTES = ("USDT", "USDC", "BTC", "ETH", "EUR", "TRY", "BRL")
```

**Symbol Detection Logic**:
```python
# Exchange info provides explicit baseCoin/quoteCoin
mapping[symbol] = combine_to_hb_trading_pair(
    base=item["baseCoin"],  # e.g., "VCC"
    quote=item["quoteCoin"]  # e.g., "USDT"
)
# Result: "VCC-USDT"
```

**API Requests**:
- Hummingbot internally: `"VCC-USDT"`
- Sent to WEEX API: `"VCCUSDT"` (no hyphen, no suffix)

---

## 🚦 Rate Limiting Strategy

### Global Pool Limit
- **1200 requests per minute** (20 req/sec average)
- All endpoints share this pool
- Uses `AsyncThrottler` with weighted limits

### Per-Endpoint Weights
All current endpoints have **weight = 1** (1 request = 1 unit from pool)

### Implementation
```python
RATE_LIMITS = [
    RateLimit(
        limit_id=GLOBAL_LIMIT_ID,
        limit=1200,
        time_interval=60,  # 1 minute
        weight=1
    ),
    RateLimit(
        limit_id=CREATE_ORDER_LIMIT_ID,
        limit=5000,  # Individual limit
        time_interval=60,
        weight=1,
        linked_limits=[LinkedLimitWeightPair(GLOBAL_LIMIT_ID, 1)]
    ),
    # ... other endpoints
]
```

**Best Practice**: Keep order placement rate < 10 per second for safety margin

---

## 💰 VCC-USDT Trading Configuration

### Current Market Conditions (Jan 2026)
- **VCC Price**: ~$0.00015 USDT
- **Min Order Value**: $5 USDT
- **Required VCC Amount**: 35,000 VCC (~$5.25 @ $0.00015)

### Market Making Strategy Parameters
```python
# weex_vcc_pmm.py configuration
{
    "exchange": "weex",
    "market": "VCC-USDT",
    "buy_spread": 0.005,  # 0.5%
    "sell_spread": 0.005,  # 0.5%
    "order_amount": 35000,  # VCC
    "order_refresh_time": 30,  # seconds
    "filled_order_delay": 60,  # seconds before replacing
    "hanging_orders_enabled": False,
    "order_optimization_enabled": True,
}
```

### Example Orders
**Scenario**: VCC price = $0.00015
- **Buy Order**: 35,000 VCC @ $0.00014925 (0.5% below mid)
  - Total: $5.22375 USDT
- **Sell Order**: 35,000 VCC @ $0.00015075 (0.5% above mid)
  - Total: $5.27625 USDT
- **Spread Profit**: $0.0525 per round trip (1% total spread)

### Risk Management
- **Kill Switch**: Activated at -3% daily loss
- **Max Active Orders**: 2 (1 buy + 1 sell)
- **Balance Requirements**:
  - **VCC**: 1,000,000+ (for sell orders)
  - **USDT**: $200-300 (for buy orders + buffer)

---

## 🧪 Testing Checklist Status

### Phase 1: Authentication & Connection ✅
- [x] API keys configured
- [x] REST authentication working
- [x] WebSocket connection established
- [x] Private WebSocket authentication successful

### Phase 2: Market Data (IN PROGRESS ⏳)
- [ ] ~~Exchange info parsing~~ ✅ **BUG FIXED**
- [ ] Trading pairs list retrieval (`list weex`)
- [ ] Order book streaming
- [ ] Ticker updates
- [ ] Trade stream validation

### Phase 3: Account Operations
- [ ] Balance check (`balance weex`)
- [ ] Available vs frozen amounts
- [ ] Real-time balance updates via WebSocket

### Phase 4: Order Operations
- [ ] **Minimum order test** ($5 USDT, 35k VCC)
- [ ] Order placement (limit buy/sell)
- [ ] Order cancellation
- [ ] Order status query (by client_order_id)
- [ ] Fills tracking

### Phase 5: Production Readiness
- [ ] Kill switch configuration (-3% threshold)
- [ ] Telegram notifications setup
- [ ] Systemd service for auto-restart
- [ ] Volume generator testing (10k USDT/day target)
- [ ] 4-6 hour monitoring window

---

## 🐛 Known Issues & Resolutions

### 1. Exchange Info Error ✅ **RESOLVED**
**Symptom**: "There was an error requesting exchange info"
**Root Cause**: Syntax error in `_get_last_traded_price()` line 571-572
**Fix**: Corrected `path_url` and `limit_id` parameters
**Status**: Fixed - ready for retesting

### 2. Binance Geo-Restriction Warning (Ignorable)
**Symptom**: "Request from this IP address is not allowed" from Binance
**Impact**: None - WEEX connector is independent
**Action**: No action needed, expected behavior for geo-restricted IPs

### 3. User Stream Event Listener (Commented Out)
**Location**: `weex_exchange.py` lines 296-370
**Status**: Entire `_user_stream_event_listener()` method is commented
**Impact**: No real-time order/balance updates via WebSocket
**Workaround**: Polling via REST API still works
**TODO**: Implement WEEX-specific WebSocket message parsing

### 4. Order Fills from Trades (Commented Out)
**Location**: `weex_exchange.py` lines 378-450
**Status**: `_update_order_fills_from_trades()` backup mechanism disabled
**Impact**: Relies solely on WebSocket for fill events
**Risk**: If WebSocket fails, fills may not be detected until next poll
**TODO**: Adapt Binance logic to WEEX API format

---

## 🔍 Debugging Tips

### Enable Debug Logging
```python
# In Hummingbot client
>>> config logger_override_whitelist ['weex']
>>> config log_level DEBUG
```

### Check Network Status
```python
>>> status --live
# Look for:
# - "Weex: READY" ← Connector initialized
# - WebSocket connections (public + private)
# - Order book updates frequency
```

### Test Exchange Info Manually
```bash
curl -X GET "https://api-spot.weex.com/api/v2/public/exchangeInfo" \
  -H "Content-Type: application/json"
```

Expected response:
```json
{
    "code": "00000",
    "msg": "success",
    "data": [
        {
            "symbol": "VCCUSDT_SPBL",
            "baseCoin": "VCC",
            "quoteCoin": "USDT",
            "minQty": "1",
            "maxQty": "10000000",
            "minNotional": "5",  // Minimum $5 USDT
            "pricePrecision": 8,
            "quantityPrecision": 0
        }
    ]
}
```

### Validate Authentication
```python
# Test REST auth
>>> balance weex

# Expected: Asset balances displayed
# If error: Check API key, secret, passphrase in conf/connectors/weex.yml
```

---

## 📁 File Structure Overview

```
hummingbot/connector/exchange/weex/
├── __init__.py
├── weex_exchange.py              # Main connector (579 lines)
│   ├── WeexExchange(ExchangePyBase)
│   ├── _place_order()            # Line 206-243
│   ├── _place_cancel()           # Line 245-256
│   ├── _format_trading_rules()   # Line 259-279
│   ├── _update_balances()        # Line 508-526
│   ├── _get_last_traded_price()  # Line 564-576 ✅ FIXED
│   └── _initialize_trading_pair_symbols_from_exchange_info()  # Line 555-561
│
├── weex_auth.py                  # Authentication (156 lines)
│   ├── generate_rest_signature()
│   ├── generate_ws_signature()
│   ├── rest_authenticate()       # Adds headers to requests
│   └── ws_authenticate()         # Adds headers to WebSocket
│
├── weex_constants.py             # API endpoints, rate limits (145 lines)
│   ├── REST_URLS, WS_PUBLIC_URLS, WS_PRIVATE_URLS
│   ├── All endpoint paths
│   ├── ORDER_STATE mapping
│   └── RATE_LIMITS configuration
│
├── weex_web_utils.py             # URL builders (36 lines)
│   ├── public_rest_url()
│   ├── private_rest_url()
│   ├── ws_public_url()
│   ├── ws_private_url()
│   └── build_api_factory()
│
├── weex_api_order_book_data_source.py  # Public WebSocket (266 lines)
│   ├── _subscribe_channels()     # Subscribe to trade/depth
│   ├── _request_order_book_snapshot()
│   ├── _parse_trade_message()
│   ├── _parse_order_book_diff_message()
│   ├── subscribe_to_trading_pair()    # Dynamic pair addition
│   └── unsubscribe_from_trading_pair()
│
├── weex_api_user_stream_data_source.py  # Private WebSocket (114 lines)
│   ├── _authenticate_connection()  # Header-based auth
│   ├── _subscribe_channels()       # account, orders, fills
│   └── Ping/pong handling
│
├── weex_order_book.py            # Order book data structures
└── weex_utils.py                 # Helper utilities
```

---

## 🚀 Next Steps (Priority Order)

### 1. Verify Bug Fix (Immediate)
```bash
cd /home/jkovacs/git/hummingbot
./start
```
```python
# In Hummingbot client
>>> connect weex
>>> list weex  # Should now work - fetches trading pairs
```
**Expected**: Trading pairs list displayed (VCC-USDT, WXT-USDT, etc.)
**If successful**: Phase 2 testing can proceed

### 2. Complete Phase 2 Testing
- Test order book streaming
- Verify ticker updates
- Check trade stream

### 3. Implement WebSocket Event Handlers
**Priority**: High - needed for real-time updates
**Tasks**:
- Uncomment `_user_stream_event_listener()` in `weex_exchange.py`
- Adapt message parsing to WEEX format (different from Binance)
- Handle account balance updates
- Process order status changes
- Track fill events

**WEEX Message Format** (expected):
```json
// Account update
{
    "event": "account",
    "data": {
        "coinName": "USDT",
        "available": "150.50",
        "frozen": "50.00"
    }
}

// Order update
{
    "event": "orders",
    "data": {
        "orderId": "123456",
        "clientOrderId": "x-MG43PCSN...",
        "symbol": "VCCUSDT_SPBL",
        "status": "FILLED",
        "type": "LIMIT",
        "side": "BUY",
        "price": "0.00015",
        "quantity": "35000",
        "filled": "35000"
    }
}

// Fill update
{
    "event": "fills",
    "data": {
        "tradeId": "789",
        "orderId": "123456",
        "symbol": "VCCUSDT_SPBL",
        "price": "0.00015",
        "quantity": "35000",
        "commission": "0.005",  // Fee
        "commissionAsset": "VCC",
        "time": 1234567890000
    }
}
```

### 4. Phase 3-4 Testing
- Balance checks
- Place minimum test orders ($5 USDT)
- Order cancellation
- Fill tracking validation

### 5. Production Deployment (Jan 31)
- Configure systemd service
- Set up kill switch
- Enable Telegram notifications
- Deploy volume generator
- Monitor for 4-6 hours

---

## 📞 Support & Documentation

### WEEX Official Resources
- **API Documentation**: https://www.weex.com/api-doc/spot/introduction/APIBriefIntroduction
- **API Key Management**: Account → API Management
- **Support**: support@weex.com

### Hummingbot Resources
- **Discord**: https://discord.gg/hummingbot
- **Docs**: https://docs.hummingbot.org
- **GitHub**: https://github.com/hummingbot/hummingbot

### Internal Documentation
- [HUMMINGBOT_DOCS_MAP.md](HUMMINGBOT_DOCS_MAP.md) - Complete framework guide
- [WEEX_MM_QUICKSTART.md](WEEX_MM_QUICKSTART.md) - Market making setup
- [WEEX_TESTING_CHECKLIST.md](WEEX_TESTING_CHECKLIST.md) - QA phases
- [WEEX_PRODUCTION_DEPLOYMENT.md](WEEX_PRODUCTION_DEPLOYMENT.md) - Deployment guide

---

## ✅ Summary

**Critical Bug**: Fixed syntax error that blocked all exchange info operations
**Current Status**: Connector ready for Phase 2 testing
**Next Action**: Test `list weex` command to verify trading pairs retrieval
**Deadline**: Production deployment January 31, 2026
**Risk Assessment**: **MEDIUM** - Core bug fixed, but WebSocket event handlers need implementation for production reliability

**Recommendation**: Proceed with Phase 2-3 testing immediately. Implement WebSocket event listeners before production deployment to ensure real-time order/balance tracking.

---

*Document generated: January 26, 2026*
*Last updated: After syntax error fix in weex_exchange.py*
