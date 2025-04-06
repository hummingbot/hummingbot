# Hummingbot Backtesting Guide
## Comprehensive Guide to Strategy Backtesting

## 1. Introduction to Backtesting

Backtesting is a crucial step in strategy development that allows you to:
- Validate trading strategies using historical data
- Optimize strategy parameters
- Assess risk and performance metrics
- Identify potential issues before live trading

## 2. Backtesting Framework

### 2.1 Basic Backtester Implementation

```python
from typing import Dict, List
import pandas as pd
from decimal import Decimal
import numpy as np
from datetime import datetime

class Backtester:
    def __init__(self,
                 strategy,
                 market_data: pd.DataFrame,
                 initial_balance: Dict[str, Decimal]):
        self.strategy = strategy
        self.market_data = market_data
        self.initial_balance = initial_balance
        self.current_balance = initial_balance.copy()
        self.trades = []
        self.portfolio_value_history = []
        
    def run(self, start_time: datetime, end_time: datetime):
        """Run backtest over specified period"""
        # Filter market data for time period
        mask = (self.market_data.index >= start_time) & \
               (self.market_data.index <= end_time)
        data = self.market_data[mask]
        
        # Iterate through each timestamp
        for timestamp, row in data.iterrows():
            # Update market state
            self.update_market_state(row)
            
            # Execute strategy
            self.strategy.tick(timestamp.timestamp())
            
            # Process any trades
            self.process_trades(timestamp)
            
            # Record portfolio value
            self.record_portfolio_value(timestamp)
            
    def process_trades(self, timestamp: datetime):
        """Process trades from strategy"""
        for trade in self.strategy.get_trades():
            self.execute_trade(trade, timestamp)
            
    def execute_trade(self, trade: Dict, timestamp: datetime):
        """Execute a single trade"""
        # Calculate trade details
        base_amount = Decimal(str(trade["amount"]))
        price = Decimal(str(trade["price"]))
        quote_amount = base_amount * price
        
        # Update balances
        if trade["side"] == "buy":
            self.current_balance["quote"] -= quote_amount
            self.current_balance["base"] += base_amount
        else:
            self.current_balance["quote"] += quote_amount
            self.current_balance["base"] -= base_amount
            
        # Record trade
        self.trades.append({
            "timestamp": timestamp,
            "side": trade["side"],
            "price": price,
            "amount": base_amount,
            "quote_amount": quote_amount
        })
```

### 2.2 Market Data Management

```python
class MarketDataManager:
    def __init__(self):
        self.data = {}
        
    def load_data(self, exchange: str, trading_pair: str,
                 start_time: datetime, end_time: datetime,
                 interval: str = "1m") -> pd.DataFrame:
        """Load market data for backtesting"""
        # Load from database or CSV
        data = self.load_from_source(
            exchange, trading_pair, start_time, end_time
        )
        
        # Resample to desired interval
        data = self.resample_data(data, interval)
        
        # Calculate additional fields
        data = self.calculate_indicators(data)
        
        return data
        
    def calculate_indicators(self,
                           data: pd.DataFrame) -> pd.DataFrame:
        """Calculate technical indicators"""
        # VWAP
        data["vwap"] = (data["price"] * data["volume"]).cumsum() / \
                       data["volume"].cumsum()
        
        # Moving averages
        data["sma_20"] = data["price"].rolling(20).mean()
        data["ema_20"] = data["price"].ewm(span=20).mean()
        
        # Volatility
        data["volatility"] = data["price"].rolling(20).std()
        
        return data
```

## 3. Performance Analysis

### 3.1 Performance Metrics Calculator

```python
class PerformanceAnalyzer:
    def __init__(self, trades: List[Dict],
                 market_data: pd.DataFrame,
                 initial_balance: Dict[str, Decimal]):
        self.trades = trades
        self.market_data = market_data
        self.initial_balance = initial_balance
        
    def calculate_metrics(self) -> Dict:
        """Calculate comprehensive performance metrics"""
        returns = self.calculate_returns()
        
        return {
            "total_return": self.calculate_total_return(),
            "sharpe_ratio": self.calculate_sharpe_ratio(returns),
            "sortino_ratio": self.calculate_sortino_ratio(returns),
            "max_drawdown": self.calculate_max_drawdown(returns),
            "win_rate": self.calculate_win_rate(),
            "profit_factor": self.calculate_profit_factor(),
            "avg_trade_return": self.calculate_avg_trade_return(),
            "volatility": self.calculate_volatility(returns)
        }
        
    def calculate_returns(self) -> pd.Series:
        """Calculate trade returns"""
        returns = []
        for trade in self.trades:
            pnl = (
                trade["exit_price"] - trade["entry_price"]
                if trade["side"] == "buy"
                else trade["entry_price"] - trade["exit_price"]
            )
            returns.append(pnl / trade["entry_price"])
        return pd.Series(returns)
        
    def calculate_sharpe_ratio(self,
                             returns: pd.Series,
                             risk_free_rate: float = 0.02) -> float:
        """Calculate annualized Sharpe ratio"""
        if len(returns) < 2:
            return 0.0
            
        excess_returns = returns - risk_free_rate/252
        return np.sqrt(252) * (
            excess_returns.mean() / excess_returns.std()
        )
        
    def calculate_sortino_ratio(self,
                              returns: pd.Series,
                              risk_free_rate: float = 0.02) -> float:
        """Calculate Sortino ratio"""
        if len(returns) < 2:
            return 0.0
            
        excess_returns = returns - risk_free_rate/252
        downside_returns = excess_returns[excess_returns < 0]
        downside_std = np.sqrt(
            np.mean(downside_returns**2)
        )
        
        return np.sqrt(252) * (
            excess_returns.mean() / downside_std
        )
        
    def calculate_max_drawdown(self,
                             returns: pd.Series) -> float:
        """Calculate maximum drawdown"""
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdowns = (cumulative - running_max) / running_max
        return abs(drawdowns.min())
```

### 3.2 Risk Analysis

```python
class RiskAnalyzer:
    def __init__(self, trades: List[Dict],
                 portfolio_history: List[Dict]):
        self.trades = trades
        self.portfolio_history = portfolio_history
        
    def analyze_risk(self) -> Dict:
        """Perform comprehensive risk analysis"""
        return {
            "value_at_risk": self.calculate_var(),
            "expected_shortfall": self.calculate_es(),
            "beta": self.calculate_beta(),
            "correlation": self.calculate_correlation(),
            "tail_risk": self.analyze_tail_risk()
        }
        
    def calculate_var(self, confidence: float = 0.95) -> float:
        """Calculate Value at Risk"""
        returns = self.calculate_returns()
        return np.percentile(returns, (1 - confidence) * 100)
        
    def calculate_es(self, confidence: float = 0.95) -> float:
        """Calculate Expected Shortfall (CVaR)"""
        returns = self.calculate_returns()
        var = self.calculate_var(confidence)
        return -returns[returns <= -var].mean()
        
    def analyze_tail_risk(self) -> Dict:
        """Analyze tail risk events"""
        returns = self.calculate_returns()
        
        return {
            "left_tail_events": len(returns[returns < -3 * returns.std()]),
            "right_tail_events": len(returns[returns > 3 * returns.std()]),
            "kurtosis": returns.kurtosis(),
            "skewness": returns.skew()
        }
```

## 4. Strategy Optimization

### 4.1 Parameter Optimizer

```python
class StrategyOptimizer:
    def __init__(self, strategy_class, param_ranges: Dict,
                 market_data: pd.DataFrame):
        self.strategy_class = strategy_class
        self.param_ranges = param_ranges
        self.market_data = market_data
        self.results = []
        
    async def optimize(self, metric: str = "sharpe_ratio",
                      iterations: int = 100):
        """Run parameter optimization"""
        for i in range(iterations):
            # Generate parameters
            params = self.generate_params()
            
            # Create and run strategy
            strategy = self.strategy_class(**params)
            backtester = Backtester(
                strategy,
                self.market_data,
                {"USDT": Decimal("10000")}
            )
            
            # Run backtest
            await backtester.run()
            
            # Calculate metrics
            metrics = PerformanceAnalyzer(
                backtester.trades,
                self.market_data,
                backtester.initial_balance
            ).calculate_metrics()
            
            self.results.append({
                "params": params,
                "metrics": metrics
            })
            
    def get_best_params(self, metric: str = "sharpe_ratio"):
        """Get best performing parameters"""
        sorted_results = sorted(
            self.results,
            key=lambda x: x["metrics"][metric],
            reverse=True
        )
        return sorted_results[0]["params"]
```

### 4.2 Walk-Forward Analysis

```python
class WalkForwardAnalyzer:
    def __init__(self, strategy_class, market_data: pd.DataFrame,
                 train_size: int, test_size: int):
        self.strategy_class = strategy_class
        self.market_data = market_data
        self.train_size = train_size
        self.test_size = test_size
        self.results = []
        
    def run_analysis(self):
        """Perform walk-forward analysis"""
        data_length = len(self.market_data)
        
        for i in range(0, data_length - self.train_size - self.test_size,
                      self.test_size):
            # Split data
            train_data = self.market_data[i:i+self.train_size]
            test_data = self.market_data[
                i+self.train_size:i+self.train_size+self.test_size
            ]
            
            # Optimize on training data
            optimizer = StrategyOptimizer(
                self.strategy_class,
                self.param_ranges,
                train_data
            )
            optimizer.optimize()
            best_params = optimizer.get_best_params()
            
            # Test on out-of-sample data
            strategy = self.strategy_class(**best_params)
            backtester = Backtester(
                strategy,
                test_data,
                {"USDT": Decimal("10000")}
            )
            backtester.run()
            
            # Record results
            self.results.append({
                "train_period": (train_data.index[0],
                               train_data.index[-1]),
                "test_period": (test_data.index[0],
                              test_data.index[-1]),
                "parameters": best_params,
                "performance": backtester.get_metrics()
            })
```

## 5. Advanced Topics

### 5.1 Monte Carlo Simulation

```python
class MonteCarloSimulator:
    def __init__(self, strategy, market_data: pd.DataFrame,
                 num_simulations: int = 1000):
        self.strategy = strategy
        self.market_data = market_data
        self.num_simulations = num_simulations
        
    def run_simulations(self):
        """Run Monte Carlo simulations"""
        results = []
        
        for i in range(self.num_simulations):
            # Generate synthetic market data
            synthetic_data = self.generate_synthetic_data()
            
            # Run backtest
            backtester = Backtester(
                self.strategy,
                synthetic_data,
                {"USDT": Decimal("10000")}
            )
            backtester.run()
            
            # Record results
            results.append(backtester.get_metrics())
            
        return self.analyze_simulation_results(results)
        
    def generate_synthetic_data(self) -> pd.DataFrame:
        """Generate synthetic market data"""
        # Calculate returns
        returns = np.log(
            self.market_data["close"] / self.market_data["close"].shift(1)
        )
        
        # Generate random returns
        random_returns = np.random.normal(
            returns.mean(),
            returns.std(),
            len(returns)
        )
        
        # Generate synthetic prices
        synthetic_prices = self.market_data["close"].iloc[0] * \
                         np.exp(random_returns.cumsum())
        
        return pd.DataFrame({
            "timestamp": self.market_data.index,
            "close": synthetic_prices
        })
```

### 5.2 Market Impact Simulation

```python
class MarketImpactSimulator:
    def __init__(self, market_data: pd.DataFrame,
                 impact_model: str = "linear"):
        self.market_data = market_data
        self.impact_model = impact_model
        
    def simulate_market_impact(self, order_size: Decimal,
                             side: str) -> pd.DataFrame:
        """Simulate market impact of trades"""
        impact_data = self.market_data.copy()
        
        if self.impact_model == "linear":
            impact = self.calculate_linear_impact(
                order_size, side
            )
        elif self.impact_model == "square_root":
            impact = self.calculate_square_root_impact(
                order_size, side
            )
        
        # Apply impact to prices
        impact_data["close"] = impact_data["close"] * \
                              (1 + impact if side == "buy" else 1 - impact)
        
        return impact_data
        
    def calculate_linear_impact(self, order_size: Decimal,
                              side: str) -> float:
        """Calculate linear price impact"""
        avg_volume = self.market_data["volume"].mean()
        return float(order_size / avg_volume) * 0.1
        
    def calculate_square_root_impact(self, order_size: Decimal,
                                   side: str) -> float:
        """Calculate square root price impact"""
        avg_volume = self.market_data["volume"].mean()
        return float(np.sqrt(order_size / avg_volume)) * 0.1
```

## 6. Reporting and Visualization

### 6.1 Performance Report Generator

```python
class ReportGenerator:
    def __init__(self, backtest_results: Dict):
        self.results = backtest_results
        
    def generate_report(self) -> str:
        """Generate comprehensive performance report"""
        report = []
        
        # Overall performance
        report.append(self.generate_performance_summary())
        
        # Risk metrics
        report.append(self.generate_risk_metrics())
        
        # Trade analysis
        report.append(self.generate_trade_analysis())
        
        # Charts
        self.generate_charts()
        
        return "\n\n".join(report)
        
    def generate_performance_summary(self) -> str:
        """Generate performance summary"""
        metrics = self.results["metrics"]
        
        return f"""
        Performance Summary
        ------------------
        Total Return: {metrics["total_return"]:.2%}
        Sharpe Ratio: {metrics["sharpe_ratio"]:.2f}
        Max Drawdown: {metrics["max_drawdown"]:.2%}
        Win Rate: {metrics["win_rate"]:.2%}
        Profit Factor: {metrics["profit_factor"]:.2f}
        """
        
    def generate_charts(self):
        """Generate performance charts"""
        import matplotlib.pyplot as plt
        
        # Equity curve
        plt.figure(figsize=(12, 6))
        plt.plot(self.results["equity_curve"])
        plt.title("Equity Curve")
        plt.savefig("equity_curve.png")
        
        # Drawdown chart
        plt.figure(figsize=(12, 6))
        plt.plot(self.results["drawdown"])
        plt.title("Drawdown")
        plt.savefig("drawdown.png")
```

## Best Practices

1. **Data Quality**
   - Use high-quality market data
   - Handle missing data appropriately
   - Account for trading fees and slippage

2. **Validation**
   - Use walk-forward analysis
   - Test on multiple market conditions
   - Consider transaction costs

3. **Risk Management**
   - Implement position sizing
   - Set stop-loss levels
   - Monitor drawdown

4. **Optimization**
   - Avoid overfitting
   - Use cross-validation
   - Consider multiple metrics

## Common Pitfalls

1. **Data Issues**
   - Look-ahead bias
   - Survivorship bias
   - Data quality problems

2. **Implementation**
   - Incorrect fee calculation
   - Unrealistic fill assumptions
   - Missing risk management

3. **Analysis**
   - Overfitting parameters
   - Ignoring transaction costs
   - Insufficient testing periods

## Resources

1. **Documentation**
   - Backtesting Framework Guide
   - Performance Analysis Guide
   - Risk Management Guide

2. **Tools**
   - Data Management Tools
   - Analysis Libraries
   - Visualization Tools

[Source: Hummingbot Documentation](https://hummingbot.org/developers/) 