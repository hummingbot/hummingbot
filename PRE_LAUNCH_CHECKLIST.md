# WEEX Market Making Pre-Launch Checklist
**Target Go-Live**: January 31, 2026
**Current Date**: January 29, 2026

## ✅ COMPLETED

### API & Connectivity
- [x] WEEX API endpoints tested (all 7 operations)
- [x] Signature authentication working
- [x] Order placement verified
- [x] Order cancellation verified
- [x] Balance retrieval working
- [x] Market data (ticker) working
- [x] Open orders list working
- [x] WEEX connector installed in Hummingbot

### Strategy Setup
- [x] Basic strategy created (`weex_vcc_pmm.py`)
- [x] Configuration file created (`weex_vcc_pmm.yml`)
- [x] Order size set (12,500 VCC)

---

## ⚠️ CRITICAL ITEMS TO ADDRESS

### 1. **Multiple Order Levels** - URGENT
**Status**: ❌ Not configured
**Current MM**: Uses 4 levels per side (8 total orders)
**Your config**: Uses 1 level per side (2 total orders)

**Action Needed**: Update strategy to place multiple order levels
- Level 1: ±0.66% (closest to mid)
- Level 2: ±1.31%
- Level 3: ±1.77%
- Level 4: ±2.22%

**Impact**: Without this, you'll only provide 25% of current liquidity depth

---

### 2. **API Key Permissions**
**Status**: ⚠️ Needs verification

**Check in WEEX dashboard**:
- [ ] Trading enabled
- [ ] Read permissions enabled
- [ ] IP whitelist configured (if required)
- [ ] 2FA/security settings reviewed

**How to verify**:
1. Log into WEEX
2. Go to API Management
3. Verify permissions on your API key

---

### 3. **Balance Check**
**Status**: ⚠️ Needs verification

**Minimum needed for 4-level strategy**:
- **VCC**: 50,000 (4 × 12,500 per side)
- **USDT**: $7.50 (4 × ~$1.88 per side)

**Recommended buffer**:
- **VCC**: 500,000+ (allows 10 full cycles)
- **USDT**: $75+ (allows 10 full cycles)

**How to check**:
```bash
./start
connect weex
balance
```

---

### 4. **Risk Management Setup**
**Status**: ❌ Not configured

#### Kill Switch (Mandatory!)
Automatically stops bot if losses exceed threshold:
```
config kill_switch_enabled
yes

config kill_switch_rate
-0.03
```
This stops the bot at -3% loss.

#### Inventory Skew Protection
Monitor if you accumulate too much VCC or USDT:
- Set max inventory: e.g., don't hold more than 2M VCC
- Set min inventory: e.g., keep at least 100k VCC

**Action**: Add inventory limits to strategy

---

### 5. **Monitoring & Alerts**
**Status**: ❌ Not configured

#### Telegram Notifications (Recommended)
Get instant alerts for:
- Order fills
- Errors
- Daily PnL summary

**Setup**:
```
telegram
```
Follow prompts to connect your Telegram account.

#### Log Monitoring
- [ ] Configure log level (INFO recommended)
- [ ] Set up log rotation
- [ ] Plan to check logs daily

---

### 6. **Dry Run Test**
**Status**: ❌ Not done

**Before going live**:
1. [ ] Start Hummingbot
2. [ ] Connect to WEEX
3. [ ] Import strategy
4. [ ] Start bot for 5-10 minutes
5. [ ] Verify:
   - Orders place correctly
   - Orders refresh properly
   - No errors in logs
   - Spreads match expectations
6. [ ] Stop bot
7. [ ] Review any issues

---

### 7. **Spread Verification**
**Status**: ⚠️ Needs validation

**Current MM spreads** (from orderbook analysis):
- Sell: +0.66%, +1.00%, +1.42%, +1.70%
- Buy: -0.66%, -1.31%, -1.77%, -2.22%

**Your config**: ±0.5%

**Action**: Decide if you want to:
- Match current MM exactly (safer transition)
- Use your own spreads (more aggressive/conservative)

---

### 8. **Order Refresh Rate**
**Status**: ✅ Set to 30 seconds

**Current config**: 30 seconds
**Typical for active markets**: 15-60 seconds

**Considerations**:
- Faster refresh = more responsive to price changes, more API calls
- Slower refresh = less overhead, may miss moves

**Action**: Test and adjust based on performance

---

### 9. **Failover Plan**
**Status**: ❌ Not documented

**What if bot crashes?**:
- [ ] Document how to restart quickly
- [ ] Set up automatic restart (systemd/supervisor)
- [ ] Have manual trading backup ready

**What if API keys compromised?**:
- [ ] Have process to rotate keys quickly
- [ ] Know how to cancel all orders manually

---

### 10. **Performance Baseline**
**Status**: ❌ Not set

**Before launch, document**:
- [ ] Current orderbook state
- [ ] Current spread levels
- [ ] Expected daily volume
- [ ] Target daily profit

**After 24 hours, compare**:
- Orders filled
- Average spread captured
- Inventory drift
- PnL vs. baseline

---

## 📊 RECOMMENDED TESTING SEQUENCE

### Day 1 (Today - Jan 29):
1. [ ] Fix multiple order levels in strategy
2. [ ] Verify API permissions
3. [ ] Check balances meet minimums
4. [ ] Configure kill switch

### Day 2 (Jan 30):
1. [ ] Set up Telegram notifications
2. [ ] Do 1-hour dry run test
3. [ ] Review logs for errors
4. [ ] Adjust spreads if needed

### Day 3 (Jan 31 - Go Live):
1. [ ] Final balance check
2. [ ] Start bot in morning
3. [ ] Monitor first hour closely
4. [ ] Check every 4 hours Day 1
5. [ ] Review end-of-day performance

---

## 🚨 PRE-FLIGHT FINAL CHECKS

**30 minutes before launch**:
- [ ] Balances confirmed
- [ ] API keys working
- [ ] Kill switch enabled
- [ ] Telegram connected
- [ ] Logs configured
- [ ] Strategy tested in dry run

**Launch sequence**:
```bash
./start
connect weex
balance           # Verify funds
import weex_vcc_pmm
config            # Review settings one last time
start             # GO LIVE
status            # Verify orders placed
```

---

## 📞 SUPPORT RESOURCES

- **Hummingbot Discord**: https://discord.hummingbot.io
- **Docs**: https://docs.hummingbot.org
- **Your test script**: `test_weex_orders_direct.py`

---

## PRIORITY ACTIONS FOR TODAY:

1. **Update strategy for multiple order levels** ← CRITICAL
2. **Verify API permissions**
3. **Check account balances**
4. **Configure kill switch**
5. **Do a 10-minute dry run test**
