# Running Market Maker + Volume Generator on Same Pair

## Overview

This guide explains how to run both strategies simultaneously on the same trading pair (e.g., VCC-USDT):
- **Market Maker (PMM)**: Earns spread from passive liquidity provision
- **Volume Generator**: Guarantees minimum daily volume through active trading

## Architecture: Two Instances, Two Sub-Accounts

```
┌─────────────────────────────────────────────────────────────┐
│  WEEX Account                                                │
│                                                              │
│  ┌─────────────────────────┐  ┌──────────────────────────┐ │
│  │ Sub-Account #1          │  │ Sub-Account #2           │ │
│  │ "Market Making"         │  │ "Volume Generation"      │ │
│  │                         │  │                          │ │
│  │ API Key: weex-mm-001    │  │ API Key: weex-vol-001    │ │
│  │                         │  │                          │ │
│  │ Funds:                  │  │ Funds:                   │ │
│  │ - 2M VCC (~$300)        │  │ - 1M VCC (~$150)         │ │
│  │ - $500 USDT             │  │ - $300 USDT              │ │
│  │                         │  │                          │ │
│  │ Strategy:               │  │ Strategy:                │ │
│  │ weex_vcc_pmm            │  │ weex_volume_generator    │ │
│  │ (passive orders)        │  │ (active trading)         │ │
│  └─────────────────────────┘  └──────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘

┌──────────────────┐          ┌──────────────────┐
│ Hummingbot       │          │ Hummingbot       │
│ Instance #1      │          │ Instance #2      │
│                  │          │                  │
│ Port: 8888       │          │ Port: 8889       │
│ (Market Maker)   │          │ (Volume Gen)     │
└──────────────────┘          └──────────────────┘
```

## Step-by-Step Setup

### Step 1: Create Weex Accounts

1. **Register two separate WEEX accounts**:
   - Account 1 Email: `market-making@yourcompany.com` (or any unique email)
   - Account 2 Email: `volume-generation@yourcompany.com`

2. **Complete verification** for both accounts

3. **Deposit funds** to each account:
   - **Market Making**: 2M VCC + $500 USDT (for passive orders)
   - **Volume Generation**: 1M VCC + $300 USDT (for active trading)

4. **Generate API keys** for each account:
   - Enable: Trading permissions
   - IP Whitelist: Add your server IP
   - Save keys securely
   - *(Optional: Create second key pair per account for monitoring - read-only)*

### Step 2: Set Up First Hummingbot Instance (Market Maker)

#### Terminal 1:
```bash
cd /home/jkovacs/git/hummingbot
./start
```

#### In Hummingbot:
```
# Connect with market making API key
connect weex
# Enter API key from "market-making" sub-account
# Enter API secret
# Enter API passphrase

# Import and start market maker
import weex_vcc_pmm
start
```

### Step 3: Set Up Second Hummingbot Instance (Volume Generator)

#### Terminal 2:
```bash
cd /home/jkovacs/git/hummingbot

# Create a separate instance directory
mkdir -p ~/hummingbot-volume
cd ~/hummingbot-volume

# Copy Hummingbot files (or use Docker - see below)
# Easiest: Use Docker method below
```

#### Docker Method (Recommended):
```bash
# Create volume generator instance
docker run -it \
  --name hummingbot-volume \
  -p 8889:8888 \
  -v $(pwd)/conf:/conf \
  -v $(pwd)/logs:/logs \
  -v $(pwd)/data:/data \
  hummingbot/hummingbot:latest

# Inside the container:
connect weex
# Enter API key from "volume-generation" sub-account
# Enter API secret
# Enter API passphrase

# Copy the volume generator files
exit

# Copy strategy files to the new instance
docker cp /home/jkovacs/git/hummingbot/scripts/weex_volume_generator.py hummingbot-volume:/home/hummingbot/scripts/
docker cp /home/jkovacs/git/hummingbot/conf/scripts/weex_volume_generator.yml hummingbot-volume:/conf/scripts/

# Restart and run
docker start -i hummingbot-volume
import weex_volume_generator
start
```

#### Local Method (Alternative):
```bash
# Clone to separate directory
cd ~
git clone https://github.com/hummingbot/hummingbot.git hummingbot-volume
cd hummingbot-volume

# Install
./install

# Copy strategy files
cp /home/jkovacs/git/hummingbot/scripts/weex_volume_generator.py scripts/
cp /home/jkovacs/git/hummingbot/conf/scripts/weex_volume_generator.yml conf/scripts/

# Start
./start

# Connect with volume generation API key
connect weex
import weex_volume_generator
start
```

### Step 4: Monitor Both Instances

Keep both terminals open. In each instance you can use:
```
status     # View current state
history    # View completed trades
balance    # Check available funds
pnl        # Check profit/loss
```

## Configuration Recommendations

### Market Maker Configuration
**File**: `conf/scripts/weex_vcc_pmm.yml`

```yml
# Optimized for passive liquidity provision
order_amount: 12500              # Smaller orders for market making
number_of_orders: 4              # Multiple levels
order_refresh_time: 30           # Moderate refresh
bid_spread: 0.0066              # Tighter spreads for fills
ask_spread: 0.0066
```

### Volume Generator Configuration
**File**: `conf/scripts/weex_volume_generator.yml`

```yml
# Optimized for volume targets
daily_volume_target_usdt: 10000  # $10k daily minimum
trade_interval_seconds: 300      # Every 5 minutes
order_size_usdt: 35             # Larger per trade
order_type: limit_cross_spread   # Ensures fills
```

## How They Work Together

| Aspect | Market Maker | Volume Generator |
|--------|-------------|-----------------|
| **Goal** | Earn spread profit | Meet volume targets |
| **Orders** | Passive (both sides) | Active (crosses spread) |
| **Fills** | Wait for takers | Forces fills |
| **Frequency** | 30s refresh | 5min intervals |
| **Inventory** | Neutral bias | Auto-rebalancing |
| **Cost** | Earns fees (maker rebates) | Pays fees |

**Synergy**:
- Market maker provides liquidity and earns when organic traders appear
- Volume generator ensures minimum activity even when market is quiet
- Combined: You meet volume requirements AND profit from spreads

## Fund Allocation Example

For VCC-USDT at $0.00015:

### Market Maker Account:
- **VCC**: 2,000,000 (~$300)
- **USDT**: $500
- **Purpose**: 4 levels @ 12,500 VCC each = buffer for multiple orders

### Volume Generator Account:
- **VCC**: 1,000,000 (~$150)
- **USDT**: $300
- **Purpose**: ~6 trades worth of buffer on each side

### Total Capital Required:
- **VCC**: 3,000,000 (~$450)
- **USDT**: $800
- **Total**: ~$1,250

## Monitoring & Management

### Check Volume Progress
**Volume Generator Instance**:
```
status
```
Shows:
- Volume: $X,XXX / $10,000 (XX%)
- Trades today: XX
- Next trade in: XXs

### Check Market Making Performance
**Market Maker Instance**:
```
status
history
pnl
```

### Daily Routine
1. **Morning**: Check both instances are running
2. **Midday**: Verify volume generator is on track
3. **Evening**: Review P&L from market maker
4. **Midnight**: Both reset for new day

## Troubleshooting

### Issue: Volume generator consuming market maker's inventory
**Solution**: Verify using separate sub-accounts with separate API keys

### Issue: Both instances showing same balance
**Solution**: Ensure different API keys are configured in each instance

### Issue: Orders conflicting
**Solution**: Check that instances are truly using different sub-accounts

### Issue: Insufficient balance errors
**Solution**: Transfer more funds to the specific sub-account

## Process Management

### Using tmux (Recommended for servers):
```bash
# Start first instance
tmux new -s hummingbot-mm
cd /home/jkovacs/git/hummingbot
./start
# Ctrl+B, D to detach

# Start second instance
tmux new -s hummingbot-vol
cd ~/hummingbot-volume
./start
# Ctrl+B, D to detach

# Reattach later:
tmux attach -t hummingbot-mm
tmux attach -t hummingbot-vol

# List sessions:
tmux ls
```

### Using systemd (For production):
Create service files for automatic restart and monitoring.

## Cost-Benefit Analysis

### Costs:
- **Volume Generator**: ~$40-60 per $10k volume (fees + spread crossing)
- **Market Maker**: Minimal (may earn from spreads)
- **Total Daily Cost**: ~$40-60

### Benefits:
- **Guaranteed Volume**: Meet 10k minimum daily
- **Spread Earnings**: Profit from market making
- **Liquidity Provision**: Support market depth
- **Net Cost**: ~0.4-0.6% of volume target

## Security Best Practices

1. **IP Whitelist**: Restrict API keys to your server IP
2. **Trading Only**: No withdrawal permissions on API keys
3. **Separate Keys**: Never share API keys between accounts
4. **Monitor Logs**: Check both instances daily
5. **Balance Alerts**: Set up notifications for low balances

## FAQ

**Q: Can I use the same API key for both instances?**
A: Technically yes, but strongly discouraged. Inventory conflicts will occur.

**Q: What if one instance crashes?**
A: The other continues independently. Restart the crashed instance.

**Q: Can I run both on one computer?**
A: Yes, either with Docker or separate directories.

**Q: How do I know which strategy made which trades?**
A: Check the `history` command in each instance separately.

**Q: What if I exceed volume target early in the day?**
A: Volume generator will stop placing trades once target is met.

**Q: Can the market maker help meet volume requirements?**
A: Only if orders fill organically. Volume generator guarantees the target.

## Summary Checklist

- [ ] Create 2 Weex sub-accounts
- [ ] Generate separate API keys for each
- [ ] Transfer appropriate funds to each sub-account
- [ ] Set up first Hummingbot instance (market maker)
- [ ] Set up second Hummingbot instance (volume generator)
- [ ] Configure each strategy appropriately
- [ ] Test both instances with small amounts first
- [ ] Set up process management (tmux/systemd)
- [ ] Monitor daily for first week
- [ ] Adjust configurations based on performance

## Support & Monitoring

Monitor both strategies and adjust as needed. The combination ensures you meet volume requirements while also profiting from market making opportunities.
