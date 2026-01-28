# WEEX Connector Testing Checklist
## Date: January 28, 2026

### Phase 1: Connection & Authentication ✅
- [x] API keys configured
- [x] IP whitelisting confirmed
- [ ] **Test connection: `connect weex`**
- [ ] **Verify balance display: `balance`**

### Phase 2: Market Data (Currently Testing)
- [ ] Trading pairs fetched successfully
- [ ] Order book data streaming
- [ ] Trade data streaming
- [ ] Ticker prices updating

### Phase 3: Order Placement (Critical for Go-Live)
Test with MINIMUM order sizes to avoid significant capital risk:

#### Buy Order Test
```
Command: buy weex [TRADING_PAIR] [MIN_AMOUNT]
Example: buy weex WXT-USDT 10
```
- [ ] Order placed successfully
- [ ] Order appears in `open_orders`
- [ ] Order ID returned correctly
- [ ] Balance updates reflected

#### Sell Order Test
```
Command: sell weex [TRADING_PAIR] [MIN_AMOUNT]
Example: sell weex WXT-USDT 100
```
- [ ] Order placed successfully
- [ ] Order appears in `open_orders`
- [ ] Order ID returned correctly
- [ ] Balance updates reflected

### Phase 4: Order Management
#### Cancel Order Test
```
Command: cancel weex [ORDER_ID]
```
- [ ] Order cancelled successfully
- [ ] Order removed from `open_orders`
- [ ] Balance returned to available

#### Order Status Test
```
Command: order_status weex [ORDER_ID]
```
- [ ] Order details displayed correctly
- [ ] Status updates properly (PENDING/NEW/FILLED/CANCELED)

### Phase 5: Error Handling
- [ ] Invalid trading pair error handled
- [ ] Insufficient balance error handled
- [ ] API rate limiting respected
- [ ] Network disconnection recovery

### Current Issues to Resolve:

1. **Exchange Info Error** (from logs):
   - "There was an error requesting exchange info"
   - Need to check WEEX API endpoint response format
   - May need to adjust trading pairs parsing

2. **Binance Errors** (can ignore):
   - Binance showing geo-restriction errors
   - This is expected and doesn't affect WEEX

### Next Steps:

1. **Connect to WEEX in Hummingbot**:
   ```
   connect weex
   ```

2. **Check balance**:
   ```
   balance
   ```

3. **If successful, check available trading pairs**:
   ```
   list weex
   ```

4. **Test minimum order placement** (CAUTIOUSLY):
   - Find minimum order size from WEEX documentation
   - Place one small test order far from market price
   - Immediately cancel to verify cancellation works

### Important Notes for Go-Live (Jan 31):

⚠️ **Before running market making**:
- [ ] Verify all order operations work (place/cancel/status)
- [ ] Test with multiple trading pairs if needed
- [ ] Configure kill switch (-3% loss threshold)
- [ ] Set up Telegram notifications
- [ ] Configure inventory skew management
- [ ] Document all trading pair minimums
- [ ] Create systemd service for auto-restart
- [ ] Plan monitoring schedule (first 4-6 hours active monitoring)

### Trading Pair Information Needed:
- [ ] WXT-USDT minimum order size
- [ ] WXT-USDT tick size (price precision)
- [ ] WXT-USDT lot size (quantity precision)
- [ ] Other trading pairs to support

### Strategy Configuration Checklist:
- [ ] Choose strategy: Pure Market Making (recommended for start)
- [ ] Set bid/ask spreads: 0.5% (adjust based on volatility)
- [ ] Set order amount: 1-2% of available liquidity
- [ ] Set order levels: 3-5 levels
- [ ] Set order refresh time: 300 seconds (5 minutes)
- [ ] Enable inventory skew
- [ ] Set kill switch threshold: -3%
