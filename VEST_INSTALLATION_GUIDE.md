# Vest Markets Connector Installation Guide

## 📋 Overview

This guide will help you set up the Vest Markets connector with proper dependency management for the `./start` script.

## 🔧 Dependencies Configuration

### ✅ Already Configured in `setup.py`

The following dependencies have been verified and are already properly configured:

```python
install_requires = [
    # ... other dependencies ...
    "bidict>=0.22.1",           # ✅ Required by Vest connector
    "eth-account>=0.13.0",      # ✅ Required for Ethereum signing
    "pandas>=2.0.3",            # ✅ Required by Hummingbot core
    "pydantic>=2",              # ✅ Required for configuration
    # ... other dependencies ...
]
```

## 🚀 Installation Steps

### 1. Install Dependencies
Run this command in the Hummingbot root directory to install all dependencies:

```bash
pip install -e .
```

This will:
- Install Hummingbot in development mode
- Install all required dependencies from `setup.py`
- Make the Vest connector available to the system

### 2. Verify Installation
Test that all Vest connector dependencies are available:

```bash
python3 -c "
import pandas, bidict, pydantic
from eth_account import Account
print('✅ All Vest connector dependencies installed successfully!')
"
```

### 3. Test Connector Registration
Verify the Vest connector is properly registered:

```bash
python3 -c "
from hummingbot.client.settings import AllConnectorSettings
settings = AllConnectorSettings.get_connector_settings()
if 'vest' in settings:
    print('✅ Vest connector is registered!')
else:
    print('❌ Vest connector not found')
"
```

### 4. Start Hummingbot
Use the start script to launch Hummingbot:

```bash
./start
```

## 📁 File Structure Verification

Ensure these Vest connector files exist:

```
hummingbot/connector/exchange/vest/
├── __init__.py                           ✅
├── vest_exchange.py                      ✅
├── vest_auth.py                          ✅
├── vest_constants.py                     ✅
├── vest_utils.py                         ✅
├── vest_web_utils.py                     ✅
├── vest_api_order_book_data_source.py   ✅
└── vest_api_user_stream_data_source.py  ✅
```

## ⚙️ Configuration Setup

### 1. Configure Vest API Credentials

After starting Hummingbot, configure the Vest connector:

```
config vest
```

You'll need to provide:
- **API Key**: Your Vest Markets API key
- **Primary Address**: Wallet address holding your funds
- **Signing Address**: Delegate signing key address
- **Private Key**: Private key for transaction signing
- **Environment**: Choose between 'prod' (production) or 'dev' (development)

### 2. Trading Pairs

Vest supports perpetual contracts for various assets:
- `BTC-PERP` - Bitcoin Perpetual
- `ETH-PERP` - Ethereum Perpetual
- `SOL-PERP` - Solana Perpetual
- And many more...

## 🔍 Troubleshooting

### Issue: "No module named 'pandas'" when using ./start

**Solution**: Reinstall dependencies
```bash
pip install -e .
```

### Issue: "No module named 'eth_account'"

**Solution**: The eth-account dependency should be installed automatically. If not:
```bash
pip install eth-account>=0.13.0
```

### Issue: Vest connector not appearing in Hummingbot

**Solution**: Verify the connector is properly implemented
```bash
python3 -c "
from hummingbot.connector.exchange.vest.vest_exchange import VestExchange
print('✅ Vest connector imports successfully')
"
```

### Issue: Import errors for bidict

**Solution**: Reinstall bidict
```bash
pip install bidict>=0.22.1
```

## 📝 Development Mode Benefits

Installing with `pip install -e .` provides:
- **Live Updates**: Changes to connector code are immediately available
- **Dependency Management**: All dependencies managed through setup.py
- **Proper Registration**: Connector automatically discovered by Hummingbot
- **Start Script Compatibility**: Works perfectly with ./start script

## 🎯 Verification Checklist

Before using the Vest connector:

- [ ] All dependencies installed via `pip install -e .`
- [ ] Vest connector files present in correct directory
- [ ] Connector imports without errors
- [ ] Connector appears in Hummingbot settings
- [ ] API credentials configured
- [ ] Start script launches successfully

## 🚀 Ready for Trading

Once all steps are complete, the Vest Markets connector will be fully integrated with Hummingbot and ready for:

- ✅ Spot and perpetual futures trading
- ✅ Real-time market data
- ✅ Order management
- ✅ Portfolio tracking
- ✅ Strategy execution

## 📞 Support

For issues specific to the Vest connector implementation, refer to:
- `VEST_CONNECTOR_IMPLEMENTATION.md` - Technical implementation details
- `VEST_TEST_REPORT.md` - Comprehensive test results

The connector has been thoroughly tested and is production-ready! 🎉
