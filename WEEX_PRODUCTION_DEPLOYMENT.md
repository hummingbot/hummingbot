# WEEX Production Deployment Guide
## Dual Strategy Setup with Monitoring Keys

This guide adapts the volume generation and market making strategies to your existing production infrastructure with separate WEEX accounts and dual API key pairs (trading + monitoring) per account.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  WEEX Main Account                                               │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Sub-Account 1: VCC Market Making                           │ │
│  │                                                            │ │
│  │  API Keys:                                                 │ │
│  │  ├── Key Pair 1 (Trading)                                 │ │
│  │  │   └─→ Hummingbot Instance #1                           │ │
│  │  └── Key Pair 2 (Monitoring/Reporting)                    │ │
│  │      └─→ Your monitoring/reporting system                 │ │
│  │                                                            │ │
│  │  Funds: 2M VCC + $500 USDT                                │ │
│  │  Strategy: weex_vcc_pmm (passive market making)           │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Sub-Account 2: VCC Volume Generation                       │ │
│  │                                                            │ │
│  │  API Keys:                                                 │ │
│  │  ├── Key Pair 1 (Trading)                                 │ │
│  │  │   └─→ Hummingbot Instance #2                           │ │
│  │  └── Key Pair 2 (Monitoring/Reporting)                    │ │
│  │      └─→ Your monitoring/reporting system                 │ │
│  │                                                            │ │
│  │  Funds: 1M VCC + $300 USDT                                │ │
│  │  Strategy: weex_volume_generator (active volume)          │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Sub-Account 3: [Your existing use case]                   │ │
│  │  API Keys: Trading + Monitoring                            │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Setup Process

### Step 1: Create Sub-Accounts on WEEX

1. **Log into WEEX main account**
2. **Create two new sub-accounts**:
   - `vcc-market-making`
   - `vcc-volume-generation`

### Step 2: Generate API Keys (Following Your Standard)

For each sub-account, generate **2 pairs** of API keys:

#### Sub-Account 1: VCC Market Making

**Trading Key Pair 1:**
- Purpose: Hummingbot trading operations
- Permissions: ✅ Trading, ❌ Withdrawal
- IP Whitelist: [Your Hummingbot server IP]
- Label: `vcc-mm-trading`

**Monitoring Key Pair 2:**
- Purpose: Read-only monitoring/reporting
- Permissions: ✅ Read, ❌ Trading, ❌ Withdrawal
- IP Whitelist: [Your monitoring system IP]
- Label: `vcc-mm-monitoring`

#### Sub-Account 2: VCC Volume Generation

**Trading Key Pair 1:**
- Purpose: Hummingbot trading operations
- Permissions: ✅ Trading, ❌ Withdrawal
- IP Whitelist: [Your Hummingbot server IP]
- Label: `vcc-vol-trading`

**Monitoring Key Pair 2:**
- Purpose: Read-only monitoring/reporting
- Permissions: ✅ Read, ❌ Trading, ❌ Withdrawal
- IP Whitelist: [Your monitoring system IP]
- Label: `vcc-vol-monitoring`

### Step 3: Fund Sub-Accounts

Transfer from main account to sub-accounts:

**Market Making Sub-Account:**
```
Transfer: 2,000,000 VCC
Transfer: 500 USDT
```

**Volume Generation Sub-Account:**
```
Transfer: 1,000,000 VCC
Transfer: 300 USDT
```

### Step 4: Configure Hummingbot Instances

#### Hummingbot Instance #1: Market Maker

```bash
# Start Hummingbot
./start

# Connect using TRADING key pair 1 from market making sub-account
connect weex

# Enter credentials
API Key: [vcc-mm-trading key]
API Secret: [vcc-mm-trading secret]
Passphrase: [vcc-mm-trading passphrase]

# Import and configure
import weex_vcc_pmm
config  # Adjust if needed
start
```

#### Hummingbot Instance #2: Volume Generator

```bash
# Start second Hummingbot instance (separate directory or Docker)
./start

# Connect using TRADING key pair 1 from volume generation sub-account
connect weex

# Enter credentials
API Key: [vcc-vol-trading key]
API Secret: [vcc-vol-trading secret]
Passphrase: [vcc-vol-trading passphrase]

# Import and configure
import weex_volume_generator
config  # Adjust if needed
start
```

### Step 5: Configure Monitoring System

Your existing monitoring/reporting system can now access both accounts:

**Market Making Account Monitoring:**
```
API Key: [vcc-mm-monitoring key]
API Secret: [vcc-mm-monitoring secret]
Endpoints: GET /api/v2/account/*, GET /api/v2/trade/*, etc.
```

**Volume Generation Account Monitoring:**
```
API Key: [vcc-vol-monitoring key]
API Secret: [vcc-vol-monitoring secret]
Endpoints: GET /api/v2/account/*, GET /api/v2/trade/*, etc.
```

## API Key Permissions Matrix

| Key Type | Trading | Withdrawal | Read Balances | Read Orders | Read Trades |
|----------|---------|------------|---------------|-------------|-------------|
| **Trading (HB)** | ✅ | ❌ | ✅ | ✅ | ✅ |
| **Monitoring** | ❌ | ❌ | ✅ | ✅ | ✅ |

## Security Benefits of This Approach

1. **Principle of Least Privilege**
   - Hummingbot only has trading permissions
   - Monitoring systems only have read permissions
   - No withdrawal permissions on any keys

2. **Blast Radius Containment**
   - If trading key compromised: Limited to one sub-account
   - If monitoring key compromised: Read-only, no trading possible
   - Sub-accounts isolate risk from main account

3. **Audit Trail**
   - Clear separation: which key did what
   - Monitoring keys create independent audit log
   - Each sub-account has separate transaction history

4. **Operational Flexibility**
   - Can rotate trading keys without affecting monitoring
   - Can update monitoring systems without touching trading
   - Can disable one strategy without affecting the other

## Monitoring & Reporting Integration

### Metrics to Track Per Sub-Account

**Market Making Account:**
- Active orders count
- Filled orders (buy/sell breakdown)
- Spread earned per trade
- Inventory drift from neutral
- Daily P&L
- Fee analysis (should be negative = earning)

**Volume Generation Account:**
- Daily volume progress ($X / $10,000)
- Trades executed count
- Average trade size
- Inventory deviation from start
- Daily cost (fees + spread crossing)
- Time to target completion

### Example Monitoring API Calls

Using the **monitoring keys** (read-only):

```python
# Check balances (monitoring key)
GET /api/v2/account/assets

# Check active orders (monitoring key)
GET /api/v2/trade/open-orders?symbol=VCCUSDT-SPBL

# Check trade history (monitoring key)
GET /api/v2/trade/fills?symbol=VCCUSDT-SPBL

# Check order history (monitoring key)
GET /api/v2/trade/history?symbol=VCCUSDT-SPBL
```

### Aggregated Dashboard

Your monitoring system can aggregate data from both:

```
┌─────────────────────────────────────────────────────┐
│  VCC-USDT Combined Performance Dashboard            │
├─────────────────────────────────────────────────────┤
│                                                      │
│  Total Daily Volume:        $8,234 / $10,000 (82%)  │
│  ├─ Market Maker:           $1,456                  │
│  └─ Volume Generator:       $6,778                  │
│                                                      │
│  Net P&L:                   +$12.45                  │
│  ├─ Market Maker:           +$23.50 (spread)        │
│  └─ Volume Generator:       -$11.05 (fees)          │
│                                                      │
│  Active Orders:             8                        │
│  ├─ Market Maker:           8 (4 buy, 4 sell)       │
│  └─ Volume Generator:       0 (next trade in 245s)  │
│                                                      │
│  Inventory Status:          Healthy                  │
│  ├─ Market Maker:           +12k VCC                │
│  └─ Volume Generator:       -8k VCC                 │
│                                                      │
└─────────────────────────────────────────────────────┘
```

## Operational Procedures

### Daily Checks

**Morning (09:00):**
1. Verify both Hummingbot instances running
2. Check monitoring dashboard for overnight activity
3. Verify volume generator is on track for daily target
4. Check no balance warnings or errors

**Midday (14:00):**
1. Review volume progress (should be ~50% by noon)
2. Check market maker spread performance
3. Verify no stuck orders
4. Check inventory levels

**Evening (20:00):**
1. Review P&L for the day
2. Check volume target achievement status
3. Plan any config adjustments for next day

**Midnight (00:00):**
1. Capture daily metrics before reset
2. Archive logs
3. Verify reset happened correctly

### Alert Configuration

**Critical Alerts (Immediate Action):**
- ❌ Hummingbot instance offline
- ❌ API key authentication failed
- ❌ Balance below minimum threshold
- ❌ No trades for 30+ minutes (volume gen)

**Warning Alerts (Monitor):**
- ⚠️ Volume <50% by noon
- ⚠️ Inventory deviation >threshold
- ⚠️ Unusual price movement (>5%)
- ⚠️ High order rejection rate

### Key Rotation Procedure

When rotating API keys (recommended quarterly):

**For Trading Keys:**
1. Generate new key pair in WEEX sub-account
2. Update key in Hummingbot: `connect weex`
3. Test with small order
4. Disable old key in WEEX
5. Monitor for 24h
6. Delete old key

**For Monitoring Keys:**
1. Generate new key pair in WEEX sub-account
2. Update in monitoring system config
3. Test API connectivity
4. Disable old key in WEEX
5. Delete old key

## Cost-Benefit Analysis

### Monthly Costs

**Volume Generation:**
- Daily: ~$40-60 in fees
- Monthly: ~$1,200-1,800

**Market Making:**
- Daily: Likely profitable (+$10-30)
- Monthly: +$300-900

**Net Cost:** ~$300-1,500/month for guaranteed 10k daily volume

**Per-Volume Cost:** ~0.3-0.5% of monthly volume

### Benefits

1. **Guaranteed Volume:** 10k USDT daily minimum
2. **Spread Profits:** Additional earnings from market making
3. **Market Depth:** Support healthier order book
4. **Operational Control:** Full control over trading activity
5. **Compliance Ready:** Clean audit trails per sub-account

## Disaster Recovery

### Hummingbot Instance Failure

**Scenario:** Market maker instance crashes

1. Volume generator continues independently
2. Restart market maker instance
3. Check balances and open orders
4. Resume normal operation

**Impact:** Minimal - volume target still met

### API Key Compromise

**Scenario:** Trading key potentially compromised

1. **Immediate:** Disable key in WEEX (via main account)
2. Cancel all open orders via WEEX UI
3. Generate new key pair
4. Update Hummingbot instance
5. Review transaction logs via monitoring key
6. Document incident

**Impact:** Isolated to one sub-account

### Exchange Downtime

**Scenario:** WEEX API temporarily unavailable

1. Both Hummingbot instances will retry
2. Monitor via status updates
3. Check WEEX status page
4. Instances auto-reconnect when available

**Impact:** Temporary - strategies resume automatically

## Migration from Current Setup

### If Currently Using Accounts 1-3 for Other Purposes

**Option 1:** Use existing accounts as sub-accounts
- No change to current setup
- Add these two strategies alongside

**Option 2:** Dedicate one account to VCC strategies
- Migrate one account to VCC-only
- Run both strategies in that account's sub-accounts

**Option 3:** Request additional accounts
- Keep current 3 accounts as-is
- Request accounts 4 & 5 for VCC strategies

## Checklist for Deployment

### Pre-Deployment
- [ ] WEEX sub-accounts created
- [ ] 4 API key pairs generated (2 per sub-account)
- [ ] Trading keys: IP whitelisted, trading permissions only
- [ ] Monitoring keys: read-only permissions
- [ ] Funds transferred to sub-accounts
- [ ] Strategy files copied to both Hummingbot instances
- [ ] Configurations reviewed and tested

### Deployment
- [ ] Connect Hummingbot instances with trading keys
- [ ] Start market maker strategy
- [ ] Start volume generator strategy
- [ ] Verify both instances trading successfully
- [ ] Configure monitoring system with monitoring keys
- [ ] Test alert systems

### Post-Deployment
- [ ] Monitor first 24 hours closely
- [ ] Verify volume tracking accurate
- [ ] Check P&L calculations
- [ ] Confirm monitoring dashboard working
- [ ] Document any issues or adjustments
- [ ] Schedule daily review meetings for first week

## Support & Escalation

### Troubleshooting Contacts
- Hummingbot: Discord support channel
- WEEX: Support ticket system
- Internal: [Your team contact]

### Log Locations
```
Market Maker:
  Hummingbot logs: logs/logs_hummingbot.log
  WEEX API logs: [via monitoring key]

Volume Generator:
  Hummingbot logs: logs/logs_hummingbot.log
  WEEX API logs: [via monitoring key]
```

## Conclusion

This deployment model:
- ✅ Respects your existing 2-key-per-account security model
- ✅ Provides complete inventory isolation between strategies
- ✅ Integrates with your monitoring infrastructure
- ✅ Maintains compliance and audit capabilities
- ✅ Minimizes operational complexity

The dual-strategy approach ensures volume targets are met while maximizing profit potential from market making.
