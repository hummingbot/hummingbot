#!/usr/bin/env python3
"""
Backtesting Script for Adaptive Market Making Strategy

This script provides backtesting functionality for the Adaptive Market Making Strategy.
"""

import os
import sys
import argparse
import logging
import yaml
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
from typing import Dict, Any, List, Tuple

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import strategy components
try:
    from scripts.strategies.config import AdaptiveMMConfig
    from scripts.strategies.indicators import calculate_rsi, calculate_macd, calculate_bollinger_bands
    from scripts.strategies.utils import calculate_inventory_ratio
except ImportError:
    print("Error importing strategy modules. Make sure you're running from the hummingbot directory.")
    sys.exit(1)


def load_config(config_path: str) -> Dict[str, Any]:
    """
    Load configuration from YAML file
    
    Args:
        config_path: Path to YAML configuration file
        
    Returns:
        Configuration dictionary
    """
    try:
        with open(config_path, 'r') as file:
            config = yaml.safe_load(file)
        return config
    except Exception as e:
        print(f"Error loading configuration: {str(e)}")
        return {}


def load_historical_data(config: Dict[str, Any]) -> pd.DataFrame:
    """
    Load historical data for backtesting
    
    Args:
        config: Backtesting configuration
        
    Returns:
        DataFrame with historical data
    """
    data_config = config['backtest']
    data_path = data_config.get('data_path')
    
    if not os.path.exists(data_path):
        raise FileNotFoundError(f"Data file not found: {data_path}")
    
    # Load data based on source type
    if data_config.get('data_source') == 'csv':
        df = pd.read_csv(data_path)
        
        # Convert timestamp to datetime if needed
        if 'timestamp' in df.columns:
            if df['timestamp'].dtype == np.int64 or df['timestamp'].dtype == np.float64:
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            else:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            df.set_index('timestamp', inplace=True)
    else:
        raise ValueError(f"Unsupported data source: {data_config.get('data_source')}")
    
    # Filter data based on start and end times
    start_time = pd.to_datetime(data_config.get('start_time'))
    end_time = pd.to_datetime(data_config.get('end_time'))
    
    df = df[(df.index >= start_time) & (df.index <= end_time)]
    
    return df


class BacktestEngine:
    """Engine for backtesting the Adaptive Market Making Strategy"""
    
    def __init__(self, config: Dict[str, Any], data: pd.DataFrame):
        """
        Initialize the backtest engine
        
        Args:
            config: Backtesting configuration
            data: Historical data for backtesting
        """
        self.config = config
        self.data = data
        self.strategy_config = AdaptiveMMConfig(**config['strategy_config'])
        
        # Initialize account balances
        self.base_balance = config['backtest'].get('initial_base_balance', 1.0)
        self.quote_balance = config['backtest'].get('initial_quote_balance', 1000.0)
        
        # Initialize fee structure
        self.maker_fee = config['backtest'].get('maker_fee', 0.001)
        self.taker_fee = config['backtest'].get('taker_fee', 0.001)
        
        # Initialize market simulation parameters
        self.slippage = config['backtest'].get('slippage', 0.0005)
        self.latency = config['backtest'].get('latency', 0.5)
        self.fill_probability = config['backtest'].get('fill_probability', 0.95)
        
        # Initialize tracking variables
        self.trades = []
        self.portfolio_value_history = []
        self.positions = []
        
        # Get trading pair components
        self.base_asset, self.quote_asset = self.strategy_config.trading_pair.split("-")
    
    def run(self) -> Dict[str, Any]:
        """
        Run the backtest
        
        Returns:
            Dictionary with backtest results
        """
        # Initialize portfolio value history
        self.portfolio_value_history = []
        
        # Initialize order tracking
        active_orders = {}
        
        # Calculate initial portfolio value
        initial_price = self.data.iloc[0]['close']
        initial_portfolio_value = self.base_balance * initial_price + self.quote_balance
        
        # Track portfolio value
        self.portfolio_value_history.append({
            'timestamp': self.data.index[0],
            'portfolio_value': initial_portfolio_value,
            'base_balance': self.base_balance,
            'quote_balance': self.quote_balance,
            'price': initial_price
        })
        
        # Iterate through each data point
        for i in range(1, len(self.data)):
            # Get current candle data
            current_data = self.data.iloc[i]
            timestamp = self.data.index[i]
            
            # Calculate mid price
            mid_price = (current_data['high'] + current_data['low']) / 2
            
            # Process any active orders
            filled_orders = self.process_orders(active_orders, current_data)
            active_orders = {k: v for k, v in active_orders.items() if k not in filled_orders}
            
            # Generate signals and create new orders
            if i % int(self.strategy_config.order_refresh_time / 60) == 0:  # Assuming data is minute-based
                # Cancel existing orders (simulation)
                active_orders = {}
                
                # Generate signals
                signals = self.generate_signals(i)
                
                # Create new orders if signal strength is sufficient
                if signals['total_score'] > self.strategy_config.signal_threshold:
                    new_orders = self.create_orders(signals, mid_price)
                    active_orders.update(new_orders)
            
            # Calculate current portfolio value
            current_portfolio_value = self.base_balance * mid_price + self.quote_balance
            
            # Track portfolio value
            self.portfolio_value_history.append({
                'timestamp': timestamp,
                'portfolio_value': current_portfolio_value,
                'base_balance': self.base_balance,
                'quote_balance': self.quote_balance,
                'price': mid_price
            })
        
        # Calculate final metrics
        results = self.calculate_metrics()
        
        return results
    
    def process_orders(
        self, 
        active_orders: Dict[str, Dict[str, Any]], 
        candle_data: pd.Series
    ) -> List[str]:
        """
        Process active orders against current candle data
        
        Args:
            active_orders: Dictionary of active orders
            candle_data: Current candle data
            
        Returns:
            List of filled order IDs
        """
        filled_orders = []
        
        for order_id, order in active_orders.items():
            # Check if order would be filled based on candle data
            if order['side'] == 'buy':
                # Buy order fills if low price <= order price
                if candle_data['low'] <= order['price']:
                    # Execute the trade
                    self.execute_trade(
                        side='buy',
                        price=order['price'],
                        amount=order['amount'],
                        timestamp=candle_data.name
                    )
                    filled_orders.append(order_id)
            else:  # sell order
                # Sell order fills if high price >= order price
                if candle_data['high'] >= order['price']:
                    # Execute the trade
                    self.execute_trade(
                        side='sell',
                        price=order['price'],
                        amount=order['amount'],
                        timestamp=candle_data.name
                    )
                    filled_orders.append(order_id)
        
        return filled_orders
    
    def execute_trade(
        self, 
        side: str, 
        price: float, 
        amount: float, 
        timestamp
    ) -> None:
        """
        Execute a trade and update balances
        
        Args:
            side: Trade side ('buy' or 'sell')
            price: Trade price
            amount: Trade amount
            timestamp: Trade timestamp
        """
        # Apply fees
        fee_pct = self.maker_fee  # Using maker fee for limit orders
        
        if side == 'buy':
            # Calculate quote amount with fee
            quote_amount = price * amount * (1 + fee_pct)
            
            # Update balances
            self.base_balance += amount
            self.quote_balance -= quote_amount
        else:  # sell
            # Calculate quote amount with fee
            quote_amount = price * amount * (1 - fee_pct)
            
            # Update balances
            self.base_balance -= amount
            self.quote_balance += quote_amount
        
        # Record the trade
        self.trades.append({
            'timestamp': timestamp,
            'side': side,
            'price': price,
            'amount': amount,
            'quote_amount': quote_amount,
            'fee': price * amount * fee_pct,
            'fee_pct': fee_pct
        })
    
    def generate_signals(self, index: int) -> Dict[str, Any]:
        """
        Generate trading signals based on historical data
        
        Args:
            index: Current data index
            
        Returns:
            Dictionary with signal information
        """
        # Get historical data up to current index
        hist_data = self.data.iloc[:index+1]
        
        # Calculate indicators
        close_prices = hist_data['close'].values
        
        # RSI
        rsi = calculate_rsi(close_prices)
        
        # MACD
        macd_line, signal_line, histogram = calculate_macd(
            close_prices, 
            self.strategy_config.ema_short, 
            self.strategy_config.ema_long
        )
        
        # Bollinger Bands
        upper_band, middle_band, lower_band = calculate_bollinger_bands(
            close_prices, 
            self.strategy_config.bb_length, 
            self.strategy_config.bb_std
        )
        
        # Calculate indicator scores (simplified)
        rsi_score = 50 + (50 - rsi) * 2  # Higher score when RSI is lower (oversold)
        
        if macd_line > signal_line:
            macd_score = 50 + min(50, abs(macd_line - signal_line) * 100)
        else:
            macd_score = 50 - min(50, abs(macd_line - signal_line) * 100)
        
        # BB score based on current price relative to bands
        current_price = close_prices[-1]
        bb_width = (upper_band - lower_band) / middle_band
        
        if current_price < lower_band:
            bb_score = 80  # Potential buy signal
        elif current_price > upper_band:
            bb_score = 20  # Potential sell signal
        else:
            # Proportional to position within bands
            bb_position = (current_price - lower_band) / (upper_band - lower_band)
            bb_score = 100 - bb_position * 100  # Higher score closer to lower band
        
        # Volume analysis (simplified)
        volume = hist_data['volume'].values
        avg_volume = np.mean(volume[-20:])
        current_volume = volume[-1]
        
        volume_score = 50
        if current_volume > avg_volume * 1.5:
            # High volume might confirm signals
            if current_price > close_prices[-2]:
                volume_score = 70  # Bullish volume
            else:
                volume_score = 30  # Bearish volume
        
        # Simple support/resistance score (placeholder)
        sr_score = 50
        
        # Calculate total score with fixed weights
        weights = {
            "rsi": 0.2,
            "macd": 0.2, 
            "ema": 0.15,
            "bbands": 0.15,
            "volume": 0.2,
            "support_resistance": 0.1
        }
        
        total_score = (
            rsi_score * weights["rsi"] +
            macd_score * weights["macd"] +
            50 * weights["ema"] +  # Placeholder for EMA score
            bb_score * weights["bbands"] +
            volume_score * weights["volume"] +
            sr_score * weights["support_resistance"]
        )
        
        return {
            "rsi": rsi,
            "macd_line": macd_line,
            "signal_line": signal_line,
            "upper_band": upper_band,
            "middle_band": middle_band,
            "lower_band": lower_band,
            "rsi_score": rsi_score,
            "macd_score": macd_score,
            "bb_score": bb_score,
            "volume_score": volume_score,
            "sr_score": sr_score,
            "total_score": total_score,
            "bb_width": bb_width
        }
    
    def create_orders(
        self, 
        signals: Dict[str, Any], 
        mid_price: float
    ) -> Dict[str, Dict[str, Any]]:
        """
        Create orders based on signals
        
        Args:
            signals: Signal information
            mid_price: Current mid price
            
        Returns:
            Dictionary of orders
        """
        # Calculate adaptive spread
        base_spread = float(self.strategy_config.min_spread)
        
        # Adjust based on total score
        if signals["total_score"] > 75:  # Strong bullish
            score_adjustment = -0.2  # Tighten spreads
        elif signals["total_score"] < 25:  # Strong bearish
            score_adjustment = 0.3  # Widen spreads
        else:
            # Linear adjustment between 25-75 score
            score_adjustment = (50 - signals["total_score"]) / 100
        
        # Adjust based on bollinger band width
        bb_adjustment = signals["bb_width"] * 0.5
        
        # Combine adjustments
        adjusted_spread = base_spread * (1 + score_adjustment + bb_adjustment)
        adjusted_spread = max(float(self.strategy_config.min_spread), 
                             min(adjusted_spread, float(self.strategy_config.max_spread)))
        
        # Calculate bid and ask prices
        bid_price = mid_price * (1 - adjusted_spread / 2)
        ask_price = mid_price * (1 + adjusted_spread / 2)
        
        # Calculate inventory ratio
        inventory_ratio = calculate_inventory_ratio(
            self.base_balance, 
            self.quote_balance, 
            mid_price
        )
        
        # Adjust order amounts based on inventory
        inventory_deviation = self.strategy_config.inventory_target_base_pct - inventory_ratio
        
        base_amount = float(self.strategy_config.order_amount)
        buy_amount = base_amount * (1.0 + min(1.0, inventory_deviation * 2))
        sell_amount = base_amount * (1.0 - min(1.0, inventory_deviation * 2))
        
        # Ensure minimum sizes
        min_order_amount = float(self.strategy_config.min_order_amount)
        buy_amount = max(min_order_amount, buy_amount)
        sell_amount = max(min_order_amount, sell_amount)
        
        # Check if we have enough balance
        max_buy_amount = self.quote_balance / bid_price
        max_sell_amount = self.base_balance
        
        buy_amount = min(buy_amount, max_buy_amount)
        sell_amount = min(sell_amount, max_sell_amount)
        
        # Create orders
        orders = {}
        
        if buy_amount > min_order_amount:
            orders["buy_1"] = {
                "side": "buy",
                "price": bid_price,
                "amount": buy_amount,
                "created_at": datetime.now()
            }
        
        if sell_amount > min_order_amount:
            orders["sell_1"] = {
                "side": "sell",
                "price": ask_price,
                "amount": sell_amount,
                "created_at": datetime.now()
            }
        
        return orders
    
    def calculate_metrics(self) -> Dict[str, Any]:
        """
        Calculate performance metrics
        
        Returns:
            Dictionary with performance metrics
        """
        # Convert portfolio history to DataFrame
        portfolio_df = pd.DataFrame(self.portfolio_value_history)
        
        # Calculate returns
        portfolio_df['returns'] = portfolio_df['portfolio_value'].pct_change()
        
        # Calculate benchmark returns (hold strategy)
        initial_price = portfolio_df.iloc[0]['price']
        final_price = portfolio_df.iloc[-1]['price']
        benchmark_return = final_price / initial_price - 1
        
        # Calculate strategy return
        initial_value = portfolio_df.iloc[0]['portfolio_value']
        final_value = portfolio_df.iloc[-1]['portfolio_value']
        strategy_return = final_value / initial_value - 1
        
        # Convert trades to DataFrame
        trades_df = pd.DataFrame(self.trades) if self.trades else pd.DataFrame()
        
        # Calculate basic metrics
        num_trades = len(trades_df)
        win_trades = len(trades_df[trades_df['side'] == 'sell']) if not trades_df.empty else 0
        lose_trades = len(trades_df[trades_df['side'] == 'buy']) if not trades_df.empty else 0
        
        # Calculate Sharpe ratio (annualized, assuming 365 trading days)
        daily_returns = portfolio_df.groupby(portfolio_df['timestamp'].dt.date)['returns'].sum()
        sharpe_ratio = np.sqrt(365) * daily_returns.mean() / daily_returns.std() if len(daily_returns) > 1 else 0
        
        # Calculate max drawdown
        portfolio_df['cummax'] = portfolio_df['portfolio_value'].cummax()
        portfolio_df['drawdown'] = (portfolio_df['portfolio_value'] / portfolio_df['cummax']) - 1
        max_drawdown = portfolio_df['drawdown'].min()
        
        return {
            'initial_value': initial_value,
            'final_value': final_value,
            'strategy_return': strategy_return,
            'benchmark_return': benchmark_return,
            'alpha': strategy_return - benchmark_return,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'num_trades': num_trades,
            'win_trades': win_trades,
            'lose_trades': lose_trades,
            'win_rate': win_trades / num_trades if num_trades > 0 else 0,
            'portfolio_history': portfolio_df,
            'trades': trades_df
        }
    
    def plot_results(self, results: Dict[str, Any]) -> None:
        """
        Plot backtest results
        
        Args:
            results: Dictionary with backtest results
        """
        portfolio_df = results['portfolio_history']
        
        # Create figure and axes
        fig, axes = plt.subplots(3, 1, figsize=(12, 18), gridspec_kw={'height_ratios': [3, 1, 1]})
        
        # Plot portfolio value
        axes[0].plot(portfolio_df['timestamp'], portfolio_df['portfolio_value'], label='Portfolio Value')
        axes[0].set_title('Portfolio Value Over Time')
        axes[0].set_xlabel('Date')
        axes[0].set_ylabel('Value')
        axes[0].legend()
        axes[0].grid(True)
        
        # Plot drawdown
        axes[1].fill_between(portfolio_df['timestamp'], portfolio_df['drawdown'] * 100, 0, color='red', alpha=0.3)
        axes[1].set_title('Drawdown Over Time')
        axes[1].set_xlabel('Date')
        axes[1].set_ylabel('Drawdown (%)')
        axes[1].grid(True)
        
        # Plot price and trades
        axes[2].plot(portfolio_df['timestamp'], portfolio_df['price'], label='Price')
        
        # Plot trades if available
        if not results['trades'].empty:
            # Buy trades
            buy_trades = results['trades'][results['trades']['side'] == 'buy']
            if not buy_trades.empty:
                axes[2].scatter(buy_trades['timestamp'], buy_trades['price'], 
                               color='green', marker='^', s=100, label='Buy')
            
            # Sell trades
            sell_trades = results['trades'][results['trades']['side'] == 'sell']
            if not sell_trades.empty:
                axes[2].scatter(sell_trades['timestamp'], sell_trades['price'], 
                               color='red', marker='v', s=100, label='Sell')
        
        axes[2].set_title('Price and Trades')
        axes[2].set_xlabel('Date')
        axes[2].set_ylabel('Price')
        axes[2].legend()
        axes[2].grid(True)
        
        # Add strategy performance text
        strategy_text = (
            f"Strategy Return: {results['strategy_return']:.2%}\n"
            f"Benchmark Return: {results['benchmark_return']:.2%}\n"
            f"Alpha: {results['alpha']:.2%}\n"
            f"Sharpe Ratio: {results['sharpe_ratio']:.2f}\n"
            f"Max Drawdown: {results['max_drawdown']:.2%}\n"
            f"Number of Trades: {results['num_trades']}\n"
            f"Win Rate: {results['win_rate']:.2%}"
        )
        
        fig.text(0.12, 0.01, strategy_text, fontsize=12)
        
        plt.tight_layout()
        plt.subplots_adjust(bottom=0.15)
        
        # Save plot to file
        plt.savefig('backtest_results.png')
        plt.close()


def main() -> None:
    """Main function"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Backtest Adaptive Market Making Strategy')
    parser.add_argument('--config', type=str, default='conf/backtest_config.yml',
                        help='Path to configuration file')
    args = parser.parse_args()
    
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(os.path.join('logs', 'backtest.log'))
        ]
    )
    
    logging.info("Starting backtesting...")
    
    # Load configuration
    config = load_config(args.config)
    if not config:
        logging.error("Failed to load configuration")
        return
    
    # Load historical data
    try:
        data = load_historical_data(config)
        logging.info(f"Loaded {len(data)} data points for backtesting")
    except Exception as e:
        logging.error(f"Error loading historical data: {str(e)}")
        return
    
    # Create and run backtest engine
    engine = BacktestEngine(config, data)
    results = engine.run()
    
    # Log results
    logging.info(f"Backtest completed. Strategy return: {results['strategy_return']:.2%}")
    logging.info(f"Benchmark return: {results['benchmark_return']:.2%}")
    logging.info(f"Alpha: {results['alpha']:.2%}")
    logging.info(f"Sharpe ratio: {results['sharpe_ratio']:.2f}")
    logging.info(f"Max drawdown: {results['max_drawdown']:.2%}")
    logging.info(f"Number of trades: {results['num_trades']}")
    logging.info(f"Win rate: {results['win_rate']:.2%}")
    
    # Plot results
    engine.plot_results(results)
    logging.info("Results plot saved to 'backtest_results.png'")


if __name__ == '__main__':
    main() 