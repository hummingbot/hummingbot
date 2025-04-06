# Running the Precision Trading Strategy with Binance (April 2025)

This guide provides step-by-step instructions for running the Precision Trading Strategy on Binance using the latest version of Hummingbot (as of April 2025).

## Prerequisites

1. **Install Hummingbot**
   - Follow the official installation guide at [Hummingbot Installation](https://hummingbot.org/installation/)
   - Make sure to install all dependencies:
     ```
     pip install -r requirements.txt
     ```

2. **Set up Binance API Keys**
   - Create a Binance account if you don't have one
   - Generate API keys with trading permissions
   - Keep your API keys secure and never share them

## Environment Setup

1. **Activate the Hummingbot environment**
   ```
   conda activate hummingbot
   ```

2. **Install required dependencies**
   ```
   pip install 'pydantic<2.0.0'
   ```
   
   Note: The current implementation requires pydantic v1.x due to compatibility issues with Hummingbot's core modules.

3. **Verify configuration**
   - Check `config/strategy_config.yaml` and ensure:
     - `exchange` is set to `"binance_paper_trade"` (or `"binance"` for live trading)
     - `trading_pair` is set to your desired pair (default is `"BTC-USDT"`)
     - Risk parameters are adjusted to your preferences

## Running in Hummingbot

1. **Start Hummingbot**
   ```
   cd /path/to/hummingbot
   ./start
   ```

2. **Configure exchange credentials**
   ```
   connect binance
   ```
   
   Then enter your API key and secret when prompted.
   
   For paper trading:
   ```
   connect binance_paper_trade
   ```

3. **Import the strategy**
   ```
   import_strategy strategies/precision_trading.py
   ```

4. **Start the strategy**
   ```
   start
   ```

5. **Monitor performance**
   - Watch the Hummingbot terminal for real-time logs
   - You can also check logs in the `logs/` directory:
     ```
     tail -f logs/logs_precision_trading.log
     ```

## Troubleshooting

### Common Issues

1. **Import errors**
   - If you encounter import errors related to Python type annotations, ensure you have the correct pydantic version installed:
     ```
     pip install 'pydantic<2.0.0'
     ```

2. **Version conflicts**
   - The strategy is designed for Hummingbot's April 2025 release
   - If using an older version, you might need to adapt the code accordingly

3. **Exchange connectivity**
   - Verify your API keys have the correct permissions
   - Check your internet connection
   - Ensure Binance services are operational

### Testing

Run the test suite to verify everything is working correctly:
```
python tests/run_tests.py
```

All tests should pass before attempting to run the strategy in a live environment.

## Performance Monitoring

Monitor the following key metrics to evaluate strategy performance:

1. **Order fill rates**
2. **Inventory balance**
3. **Spread adjustments during different market regimes**
4. **Profit and loss (PnL)**

Use the logs to analyze how the strategy responds to different market conditions and adjust parameters as needed.

## Safety Precautions

1. **Always start with paper trading** to test your strategy without real funds
2. **Use small position sizes** when starting with real funds
3. **Set stop-losses** to limit potential losses
4. **Monitor regularly** and be prepared to intervene if needed

## Further Customization

The strategy parameters can be fine-tuned in `config/strategy_config.yaml`. Consider adjusting:

- Risk profile (conservative, moderate, aggressive)
- Order sizes and spreads
- Technical indicator parameters
- Target inventory ratio

Remember to run tests after making significant changes to ensure everything works as expected. 