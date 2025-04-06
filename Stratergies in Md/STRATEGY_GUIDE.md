# Hummingbot Strategy Development Guide
## Understanding and Creating Trading Strategies

## 1. Strategy Fundamentals

### 1.1 Strategy Types

1. **Pure Market Making**
   - Creates and maintains orders on a single exchange
   - Profits from bid-ask spread
   - Manages inventory risk

2. **Cross-Exchange Market Making**
   - Arbitrages between different exchanges
   - Profits from price discrepancies
   - Requires careful latency management

3. **Arbitrage**
   - Exploits price differences
   - Can be triangular or direct
   - Requires precise timing

4. **Grid Trading**
   - Places multiple orders at different price levels
   - Profits from price oscillations
   - Requires range-bound markets

## 2. Strategy Development

### 2.1 Basic Strategy Template

```python
from hummingbot.strategy.strategy_base import StrategyBase
from decimal import Decimal
import logging

class CustomStrategy(StrategyBase):
    def __init__(self,
                 exchange: str,
                 trading_pair: str,
                 order_amount: Decimal,
                 min_profitability: Decimal):
        super().__init__()
        self._exchange = exchange
        self._trading_pair = trading_pair
        self._order_amount = order_amount
        self._min_profitability = min_profitability
        self._logger = logging.getLogger(__name__)
        
    def start(self, clock: Clock, timestamp: float):
        super().start(clock, timestamp)
        self._logger.info("Strategy started.")
        
    def stop(self, clock: Clock):
        super().stop(clock)
        self._logger.info("Strategy stopped.")
        
    def tick(self, timestamp: float):
        """Called on every clock tick"""
        if not self._allow_trading:
            return
            
        self.process_market_data()
        self.execute_strategy_logic()
        
    async def process_market_data(self):
        """Process market data and update internal state"""
        pass
        
    async def execute_strategy_logic(self):
        """Execute core strategy logic"""
        pass
```

### 2.2 Market Making Strategy Example

```python
from hummingbot.strategy.strategy_base import StrategyBase
from hummingbot.core.data_type.limit_order import LimitOrder
from decimal import Decimal
import logging

class SimpleMarketMaker(StrategyBase):
    def __init__(self,
                 exchange: str,
                 trading_pair: str,
                 bid_spread: Decimal,
                 ask_spread: Decimal,
                 order_amount: Decimal):
        super().__init__()
        self._exchange = exchange
        self._trading_pair = trading_pair
        self._bid_spread = bid_spread
        self._ask_spread = ask_spread
        self._order_amount = order_amount
        self._logger = logging.getLogger(__name__)
        
        # Internal state
        self._current_orders = []
        self._last_timestamp = 0
        
    async def create_orders(self):
        """Create bid and ask orders"""
        # Get current mid price
        mid_price = await self.get_mid_price()
        if not mid_price:
            return
            
        # Calculate order prices
        bid_price = mid_price * (Decimal("1") - self._bid_spread)
        ask_price = mid_price * (Decimal("1") + self._ask_spread)
        
        # Create orders
        self.buy_with_specific_market(
            self._exchange,
            self._trading_pair,
            self._order_amount,
            order_type="limit",
            price=bid_price
        )
        
        self.sell_with_specific_market(
            self._exchange,
            self._trading_pair,
            self._order_amount,
            order_type="limit",
            price=ask_price
        )
        
    async def cancel_all_orders(self):
        """Cancel all active orders"""
        for order in self._current_orders:
            await self.cancel_order(order.client_order_id)
        self._current_orders = []
        
    def tick(self, timestamp: float):
        """Strategy tick handler"""
        if timestamp - self._last_timestamp < 60:  # 1-minute interval
            return
            
        self._last_timestamp = timestamp
        
        # Main strategy loop
        asyncio.ensure_future(self.main_strategy_loop())
        
    async def main_strategy_loop(self):
        """Main strategy execution loop"""
        try:
            # Cancel existing orders
            await self.cancel_all_orders()
            
            # Create new orders
            await self.create_orders()
            
        except Exception as e:
            self._logger.error(f"Error in strategy loop: {str(e)}")
```

## 3. Advanced Strategy Components

### 3.1 Order Management

```python
class OrderManager:
    def __init__(self, strategy: StrategyBase):
        self.strategy = strategy
        self.active_orders = {}
        self.filled_orders = []
        
    async def place_order(self, side: str, amount: Decimal,
                         price: Decimal) -> str:
        """Place a new order and track it"""
        order_id = await self.strategy.place_order(
            side, amount, price
        )
        self.active_orders[order_id] = {
            "side": side,
            "amount": amount,
            "price": price,
            "status": "open"
        }
        return order_id
        
    async def cancel_order(self, order_id: str):
        """Cancel an active order"""
        if order_id in self.active_orders:
            await self.strategy.cancel_order(order_id)
            self.active_orders.pop(order_id)
            
    def on_order_filled(self, order_id: str, fill_price: Decimal,
                       fill_amount: Decimal):
        """Handle order fill event"""
        if order_id in self.active_orders:
            order = self.active_orders.pop(order_id)
            self.filled_orders.append({
                "order_id": order_id,
                "side": order["side"],
                "fill_price": fill_price,
                "fill_amount": fill_amount,
                "timestamp": time.time()
            })
```

### 3.2 Position Management

```python
class PositionManager:
    def __init__(self, max_position: Decimal,
                 target_position: Decimal):
        self.max_position = max_position
        self.target_position = target_position
        self.current_position = Decimal("0")
        
    def can_open_position(self, side: str,
                         amount: Decimal) -> bool:
        """Check if new position can be opened"""
        potential_position = (
            self.current_position + amount
            if side == "buy"
            else self.current_position - amount
        )
        return abs(potential_position) <= self.max_position
        
    def update_position(self, side: str, amount: Decimal):
        """Update current position"""
        self.current_position += (
            amount if side == "buy" else -amount
        )
        
    def get_rebalance_order(self) -> Optional[Dict]:
        """Get order details for position rebalancing"""
        if self.current_position == self.target_position:
            return None
            
        deviation = self.current_position - self.target_position
        if abs(deviation) < Decimal("0.01"):
            return None
            
        return {
            "side": "sell" if deviation > 0 else "buy",
            "amount": abs(deviation)
        }
```

### 3.3 Risk Management

```python
class RiskManager:
    def __init__(self,
                 max_position_size: Decimal,
                 max_loss_pct: Decimal,
                 max_drawdown_pct: Decimal):
        self.max_position_size = max_position_size
        self.max_loss_pct = max_loss_pct
        self.max_drawdown_pct = max_drawdown_pct
        self.initial_portfolio_value = None
        self.peak_portfolio_value = None
        
    def initialize(self, portfolio_value: Decimal):
        """Initialize risk tracking"""
        self.initial_portfolio_value = portfolio_value
        self.peak_portfolio_value = portfolio_value
        
    def update_portfolio_value(self,
                             current_value: Decimal) -> bool:
        """Update portfolio value and check risk limits"""
        if current_value > self.peak_portfolio_value:
            self.peak_portfolio_value = current_value
            
        # Check maximum loss
        loss_pct = (
            (self.initial_portfolio_value - current_value)
            / self.initial_portfolio_value
        )
        if loss_pct > self.max_loss_pct:
            return False
            
        # Check maximum drawdown
        drawdown_pct = (
            (self.peak_portfolio_value - current_value)
            / self.peak_portfolio_value
        )
        if drawdown_pct > self.max_drawdown_pct:
            return False
            
        return True
```

## 4. Strategy Optimization

### 4.1 Parameter Optimization

```python
class StrategyOptimizer:
    def __init__(self, strategy_class, param_ranges: Dict):
        self.strategy_class = strategy_class
        self.param_ranges = param_ranges
        self.results = []
        
    async def optimize(self, market_data: pd.DataFrame,
                      iterations: int = 100):
        """Run parameter optimization"""
        for i in range(iterations):
            # Generate random parameters
            params = self.generate_params()
            
            # Create strategy instance
            strategy = self.strategy_class(**params)
            
            # Run backtest
            result = await self.run_backtest(
                strategy, market_data
            )
            
            self.results.append({
                "params": params,
                "metrics": result
            })
            
    def generate_params(self) -> Dict:
        """Generate random parameters within ranges"""
        params = {}
        for param, range_values in self.param_ranges.items():
            if isinstance(range_values, list):
                params[param] = random.choice(range_values)
            else:
                min_val, max_val = range_values
                params[param] = random.uniform(min_val, max_val)
        return params
        
    def get_best_params(self, metric: str = "sharpe_ratio"):
        """Get best performing parameters"""
        sorted_results = sorted(
            self.results,
            key=lambda x: x["metrics"][metric],
            reverse=True
        )
        return sorted_results[0]["params"]
```

### 4.2 Performance Analysis

```python
class PerformanceAnalyzer:
    def __init__(self, trades: List[Dict],
                 market_data: pd.DataFrame):
        self.trades = trades
        self.market_data = market_data
        
    def calculate_metrics(self) -> Dict:
        """Calculate performance metrics"""
        returns = self.calculate_returns()
        
        return {
            "total_return": self.calculate_total_return(),
            "sharpe_ratio": self.calculate_sharpe_ratio(returns),
            "max_drawdown": self.calculate_max_drawdown(returns),
            "win_rate": self.calculate_win_rate(),
            "profit_factor": self.calculate_profit_factor()
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
                             returns: pd.Series) -> float:
        """Calculate Sharpe ratio"""
        if len(returns) < 2:
            return 0.0
        return (
            returns.mean() / returns.std()
            * np.sqrt(252)  # Annualize
        )
        
    def calculate_max_drawdown(self,
                             returns: pd.Series) -> float:
        """Calculate maximum drawdown"""
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        return abs(drawdown.min())
```

## 5. Advanced Topics

### 5.1 Machine Learning Integration

```python
class MLStrategy(StrategyBase):
    def __init__(self, model_path: str, **kwargs):
        super().__init__(**kwargs)
        self.model = self.load_model(model_path)
        self.feature_calculator = FeatureCalculator()
        
    def load_model(self, model_path: str):
        """Load trained machine learning model"""
        return joblib.load(model_path)
        
    async def predict_price_movement(self,
                                   market_data: pd.DataFrame):
        """Predict price movement using ML model"""
        features = self.feature_calculator.calculate(
            market_data
        )
        prediction = self.model.predict(features)
        return prediction
        
    async def execute_strategy_logic(self):
        """Execute ML-based trading logic"""
        market_data = await self.get_market_data()
        prediction = await self.predict_price_movement(
            market_data
        )
        
        if prediction > 0.5:  # Bullish signal
            await self.place_buy_order()
        elif prediction < -0.5:  # Bearish signal
            await self.place_sell_order()
```

### 5.2 Event-Driven Components

```python
class EventDrivenStrategy(StrategyBase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.event_queue = asyncio.Queue()
        self.handlers = {
            "ORDER_FILLED": self.handle_order_filled,
            "PRICE_ALERT": self.handle_price_alert,
            "POSITION_UPDATE": self.handle_position_update
        }
        
    async def start(self):
        """Start event processing"""
        while True:
            event = await self.event_queue.get()
            await self.process_event(event)
            
    async def process_event(self, event: Dict):
        """Process incoming events"""
        event_type = event["type"]
        if event_type in self.handlers:
            await self.handlers[event_type](event)
            
    async def handle_order_filled(self, event: Dict):
        """Handle order filled event"""
        order_id = event["order_id"]
        fill_price = event["fill_price"]
        fill_amount = event["fill_amount"]
        
        # Update position
        await self.position_manager.update_position(
            event["side"],
            fill_amount
        )
        
        # Check for rebalancing
        await self.check_rebalancing()
        
    async def handle_price_alert(self, event: Dict):
        """Handle price alert event"""
        price = event["price"]
        alert_type = event["alert_type"]
        
        if alert_type == "BREAKOUT":
            await self.handle_breakout(price)
        elif alert_type == "SUPPORT_RESISTANCE":
            await self.handle_support_resistance(price)
```

## 6. Testing and Deployment

### 6.1 Unit Testing

```python
import unittest
from unittest.mock import Mock, patch

class TestCustomStrategy(unittest.TestCase):
    def setUp(self):
        self.exchange = Mock()
        self.strategy = CustomStrategy(
            exchange="binance",
            trading_pair="BTC-USDT",
            order_amount=Decimal("0.1"),
            min_profitability=Decimal("0.01")
        )
        
    def test_initialization(self):
        """Test strategy initialization"""
        self.assertEqual(
            self.strategy._exchange,
            "binance"
        )
        self.assertEqual(
            self.strategy._trading_pair,
            "BTC-USDT"
        )
        
    @patch("asyncio.create_task")
    async def test_create_orders(self, mock_create_task):
        """Test order creation"""
        # Mock market data
        self.strategy.get_mid_price = Mock(
            return_value=Decimal("50000")
        )
        
        # Execute order creation
        await self.strategy.create_orders()
        
        # Verify orders were created
        self.assertEqual(
            mock_create_task.call_count,
            2  # One call for buy and one for sell
        )
```

### 6.2 Integration Testing

```python
class IntegrationTest:
    def __init__(self, strategy: StrategyBase,
                 test_config: Dict):
        self.strategy = strategy
        self.config = test_config
        self.results = []
        
    async def run_test(self):
        """Run integration test"""
        # Initialize strategy
        await self.strategy.start()
        
        # Run test scenarios
        for scenario in self.config["scenarios"]:
            result = await self.run_scenario(scenario)
            self.results.append(result)
            
        # Stop strategy
        await self.strategy.stop()
        
    async def run_scenario(self, scenario: Dict) -> Dict:
        """Run single test scenario"""
        # Setup scenario conditions
        await self.setup_market_conditions(
            scenario["market_conditions"]
        )
        
        # Execute scenario actions
        for action in scenario["actions"]:
            await self.execute_action(action)
            
        # Verify scenario expectations
        results = await self.verify_expectations(
            scenario["expectations"]
        )
        
        return {
            "scenario": scenario["name"],
            "results": results
        }
```

## Best Practices

1. **Strategy Design**
   - Keep strategies modular and focused
   - Implement proper error handling
   - Use async/await for I/O operations
   - Maintain clean separation of concerns

2. **Risk Management**
   - Always implement position limits
   - Use stop-loss mechanisms
   - Monitor drawdown
   - Implement circuit breakers

3. **Testing**
   - Write comprehensive unit tests
   - Perform paper trading
   - Test edge cases
   - Monitor performance metrics

4. **Optimization**
   - Regular parameter tuning
   - Performance profiling
   - Memory usage optimization
   - Network latency management

## Common Pitfalls

1. **Implementation Issues**
   - Incorrect order sizing
   - Missing error handling
   - Race conditions
   - Memory leaks

2. **Market Risks**
   - Insufficient liquidity
   - High slippage
   - Market manipulation
   - Technical failures

## Resources

1. **Documentation**
   - Hummingbot API Reference
   - Strategy Development Guide
   - Best Practices Guide

2. **Tools**
   - Strategy Template
   - Testing Framework
   - Performance Analyzer
   - Risk Management Tools

[Source: Hummingbot Documentation](https://hummingbot.org/developers/strategies/) 