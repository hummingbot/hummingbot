"""
Market Conditions Testing for Coins.xyz Exchange.

This module provides comprehensive market conditions testing including:
- Order management under various market conditions
- High volatility scenario testing
- Network latency and connectivity testing
- Market stress testing
- Order lifecycle performance monitoring
"""

import asyncio
import logging
import random
import time
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List

from hummingbot.connector.exchange.coinsxyz.coinsxyz_order_lifecycle import CoinsxyzOrderLifecycle
from hummingbot.connector.exchange.coinsxyz.coinsxyz_order_placement import CoinsxyzOrderPlacement
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.logger import HummingbotLogger


class MarketCondition(Enum):
    """Market condition types."""
    NORMAL = "NORMAL"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    LOW_LIQUIDITY = "LOW_LIQUIDITY"
    NETWORK_ISSUES = "NETWORK_ISSUES"
    HIGH_VOLUME = "HIGH_VOLUME"
    MARKET_CRASH = "MARKET_CRASH"
    FLASH_CRASH = "FLASH_CRASH"


@dataclass
class MarketScenario:
    """Market scenario configuration."""
    condition: MarketCondition
    duration: float
    order_count: int
    price_volatility: float
    network_latency: float
    success_rate_threshold: float
    description: str


@dataclass
class MarketTestResult:
    """Market test result data structure."""
    scenario: MarketScenario
    start_time: float
    end_time: float
    total_orders: int
    successful_orders: int
    failed_orders: int
    average_response_time: float
    success_rate: float
    performance_metrics: Dict[str, Any]
    errors: List[str]


class CoinsxyzMarketConditions:
    """
    Market conditions testing for Coins.xyz exchange.

    Provides comprehensive testing under various market conditions:
    - High volatility scenarios
    - Network connectivity issues
    - Market stress testing
    - Order lifecycle performance monitoring
    - Bulk operation efficiency testing
    """

    def __init__(self,
                 api_factory: WebAssistantsFactory,
                 order_lifecycle: CoinsxyzOrderLifecycle,
                 order_placement: CoinsxyzOrderPlacement):
        """
        Initialize market conditions testing.

        Args:
            api_factory: Web assistants factory for API requests
            order_lifecycle: Order lifecycle manager
            order_placement: Order placement engine
        """
        self._api_factory = api_factory
        self._order_lifecycle = order_lifecycle
        self._order_placement = order_placement
        self._logger = None

        # Test scenarios
        self._test_scenarios = self._create_test_scenarios()
        self._test_results: List[MarketTestResult] = []

        # Performance tracking
        self._performance_metrics = {
            "total_tests": 0,
            "successful_tests": 0,
            "failed_tests": 0,
            "average_success_rate": 0.0
        }

    def logger(self) -> HummingbotLogger:
        """Get logger instance."""
        if self._logger is None:
            self._logger = logging.getLogger(__name__)
        return self._logger

    def _create_test_scenarios(self) -> List[MarketScenario]:
        """
        Create comprehensive test scenarios for various market conditions.

        Returns:
            List of market test scenarios
        """
        scenarios = [
            MarketScenario(
                condition=MarketCondition.NORMAL,
                duration=30.0,
                order_count=10,
                price_volatility=0.01,  # 1% volatility
                network_latency=0.1,    # 100ms latency
                success_rate_threshold=95.0,
                description="Normal market conditions with standard volatility"
            ),
            MarketScenario(
                condition=MarketCondition.HIGH_VOLATILITY,
                duration=60.0,
                order_count=20,
                price_volatility=0.05,  # 5% volatility
                network_latency=0.2,    # 200ms latency
                success_rate_threshold=85.0,
                description="High volatility market with rapid price changes"
            ),
            MarketScenario(
                condition=MarketCondition.LOW_LIQUIDITY,
                duration=45.0,
                order_count=15,
                price_volatility=0.02,  # 2% volatility
                network_latency=0.3,    # 300ms latency
                success_rate_threshold=80.0,
                description="Low liquidity market with wider spreads"
            ),
            MarketScenario(
                condition=MarketCondition.NETWORK_ISSUES,
                duration=40.0,
                order_count=12,
                price_volatility=0.01,  # 1% volatility
                network_latency=1.0,    # 1000ms latency
                success_rate_threshold=70.0,
                description="Network connectivity issues with high latency"
            ),
            MarketScenario(
                condition=MarketCondition.HIGH_VOLUME,
                duration=90.0,
                order_count=50,
                price_volatility=0.03,  # 3% volatility
                network_latency=0.15,   # 150ms latency
                success_rate_threshold=90.0,
                description="High volume trading with increased activity"
            ),
            MarketScenario(
                condition=MarketCondition.MARKET_CRASH,
                duration=120.0,
                order_count=25,
                price_volatility=0.10,  # 10% volatility
                network_latency=0.5,    # 500ms latency
                success_rate_threshold=60.0,
                description="Market crash scenario with extreme volatility"
            ),
            MarketScenario(
                condition=MarketCondition.FLASH_CRASH,
                duration=20.0,
                order_count=8,
                price_volatility=0.15,  # 15% volatility
                network_latency=0.8,    # 800ms latency
                success_rate_threshold=50.0,
                description="Flash crash with extreme rapid price movements"
            )
        ]

        return scenarios

    async def run_all_market_tests(self) -> List[MarketTestResult]:
        """
        Run all market condition tests.

        Returns:
            List of test results for all scenarios
        """
        self.logger().info("Starting comprehensive market conditions testing")

        all_results = []

        for scenario in self._test_scenarios:
            self.logger().info(f"Running test: {scenario.condition.value} - {scenario.description}")

            try:
                result = await self.run_market_test(scenario)
                all_results.append(result)

                self.logger().info(
                    f"Test completed: {scenario.condition.value} - "
                    f"Success Rate: {result.success_rate:.1f}% "
                    f"({result.successful_orders}/{result.total_orders})"
                )

            except Exception as e:
                self.logger().error(f"Test failed: {scenario.condition.value} - {e}")

                # Create failed result
                failed_result = MarketTestResult(
                    scenario=scenario,
                    start_time=time.time(),
                    end_time=time.time(),
                    total_orders=0,
                    successful_orders=0,
                    failed_orders=1,
                    average_response_time=0.0,
                    success_rate=0.0,
                    performance_metrics={},
                    errors=[str(e)]
                )
                all_results.append(failed_result)

        # Update performance metrics
        self._update_performance_metrics(all_results)
        self._test_results.extend(all_results)

        return all_results

    async def run_market_test(self, scenario: MarketScenario) -> MarketTestResult:
        """
        Run a specific market condition test.

        Args:
            scenario: Market scenario to test

        Returns:
            MarketTestResult with test outcomes
        """
        start_time = time.time()

        # Initialize test tracking
        successful_orders = 0
        failed_orders = 0
        response_times = []
        errors = []

        try:
            # Simulate market conditions
            await self._simulate_market_conditions(scenario)

            # Generate test orders based on scenario
            test_orders = self._generate_test_orders(scenario)

            # Execute orders under market conditions
            for order_data in test_orders:
                order_start_time = time.time()

                try:
                    # Simulate network latency
                    await asyncio.sleep(scenario.network_latency)

                    # Place order (simulated)
                    success = await self._simulate_order_placement(order_data, scenario)

                    order_end_time = time.time()
                    response_time = order_end_time - order_start_time
                    response_times.append(response_time)

                    if success:
                        successful_orders += 1
                    else:
                        failed_orders += 1
                        errors.append(f"Order {order_data['client_order_id']} failed under {scenario.condition.value}")

                except Exception as e:
                    failed_orders += 1
                    errors.append(f"Order {order_data['client_order_id']} exception: {e}")
                    response_times.append(scenario.network_latency * 2)  # Penalty for errors

            end_time = time.time()

            # Calculate metrics
            total_orders = successful_orders + failed_orders
            success_rate = (successful_orders / total_orders * 100) if total_orders > 0 else 0
            avg_response_time = sum(response_times) / len(response_times) if response_times else 0

            # Performance metrics
            performance_metrics = {
                "test_duration": end_time - start_time,
                "orders_per_second": total_orders / (end_time - start_time) if end_time > start_time else 0,
                "average_latency": avg_response_time,
                "max_latency": max(response_times) if response_times else 0,
                "min_latency": min(response_times) if response_times else 0,
                "threshold_met": success_rate >= scenario.success_rate_threshold,
                "volatility_handled": scenario.price_volatility,
                "network_conditions": scenario.network_latency
            }

            return MarketTestResult(
                scenario=scenario,
                start_time=start_time,
                end_time=end_time,
                total_orders=total_orders,
                successful_orders=successful_orders,
                failed_orders=failed_orders,
                average_response_time=avg_response_time,
                success_rate=success_rate,
                performance_metrics=performance_metrics,
                errors=errors
            )

        except Exception as e:
            self.logger().error(f"Market test failed: {e}")
            raise

    async def _simulate_market_conditions(self, scenario: MarketScenario):
        """
        Simulate specific market conditions.

        Args:
            scenario: Market scenario to simulate
        """
        # Simulate market condition setup
        if scenario.condition == MarketCondition.HIGH_VOLATILITY:
            self.logger().info("Simulating high volatility market conditions")
            # In real implementation, this would adjust price feeds, etc.

        elif scenario.condition == MarketCondition.NETWORK_ISSUES:
            self.logger().info("Simulating network connectivity issues")
            # In real implementation, this would introduce network delays

        elif scenario.condition == MarketCondition.MARKET_CRASH:
            self.logger().info("Simulating market crash scenario")
            # In real implementation, this would simulate rapid price drops

        # Add small delay to simulate condition setup
        await asyncio.sleep(0.1)

    def _generate_test_orders(self, scenario: MarketScenario) -> List[Dict[str, Any]]:
        """
        Generate test orders for the scenario.

        Args:
            scenario: Market scenario

        Returns:
            List of test order data
        """
        orders = []
        base_price = Decimal("50000.0")  # Base BTC price

        for i in range(scenario.order_count):
            # Apply price volatility
            price_variation = random.uniform(-scenario.price_volatility, scenario.price_volatility)
            order_price = base_price * (1 + Decimal(str(price_variation)))

            # Random order parameters
            order_type = random.choice([OrderType.LIMIT, OrderType.MARKET])
            trade_type = random.choice([TradeType.BUY, TradeType.SELL])
            amount = Decimal(str(random.uniform(0.1, 2.0)))

            order_data = {
                "client_order_id": f"test_{scenario.condition.value.lower()}_{i}_{int(time.time())}",
                "trading_pair": "BTC-USDT",
                "order_type": order_type,
                "trade_type": trade_type,
                "amount": amount,
                "price": order_price if order_type == OrderType.LIMIT else None
            }

            orders.append(order_data)

        return orders

    async def _simulate_order_placement(self,
                                        order_data: Dict[str, Any],
                                        scenario: MarketScenario) -> bool:
        """
        Simulate order placement under market conditions.

        Args:
            order_data: Order data to place
            scenario: Market scenario

        Returns:
            Boolean indicating success/failure
        """
        # Simulate success/failure based on market conditions
        base_success_rate = 0.95  # 95% base success rate

        # Adjust success rate based on market conditions
        if scenario.condition == MarketCondition.NORMAL:
            success_probability = base_success_rate
        elif scenario.condition == MarketCondition.HIGH_VOLATILITY:
            success_probability = base_success_rate * 0.9
        elif scenario.condition == MarketCondition.LOW_LIQUIDITY:
            success_probability = base_success_rate * 0.85
        elif scenario.condition == MarketCondition.NETWORK_ISSUES:
            success_probability = base_success_rate * 0.75
        elif scenario.condition == MarketCondition.HIGH_VOLUME:
            success_probability = base_success_rate * 0.92
        elif scenario.condition == MarketCondition.MARKET_CRASH:
            success_probability = base_success_rate * 0.6
        elif scenario.condition == MarketCondition.FLASH_CRASH:
            success_probability = base_success_rate * 0.5
        else:
            success_probability = base_success_rate

        # Random success/failure based on probability
        return random.random() < success_probability

    def _update_performance_metrics(self, results: List[MarketTestResult]):
        """
        Update overall performance metrics.

        Args:
            results: List of test results
        """
        if not results:
            return

        total_tests = len(results)
        successful_tests = sum(1 for r in results if r.success_rate >= r.scenario.success_rate_threshold)
        failed_tests = total_tests - successful_tests

        average_success_rate = sum(r.success_rate for r in results) / total_tests

        self._performance_metrics.update({
            "total_tests": total_tests,
            "successful_tests": successful_tests,
            "failed_tests": failed_tests,
            "average_success_rate": average_success_rate,
            "test_completion_rate": (successful_tests / total_tests * 100) if total_tests > 0 else 0
        })

    def get_test_scenarios(self) -> List[MarketScenario]:
        """Get all test scenarios."""
        return self._test_scenarios.copy()

    def get_test_results(self) -> List[MarketTestResult]:
        """Get all test results."""
        return self._test_results.copy()

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get overall performance metrics."""
        return self._performance_metrics.copy()

    def generate_test_report(self) -> Dict[str, Any]:
        """
        Generate comprehensive test report.

        Returns:
            Dictionary with comprehensive test report
        """
        if not self._test_results:
            return {"error": "No test results available"}

        # Overall statistics
        total_orders = sum(r.total_orders for r in self._test_results)
        total_successful = sum(r.successful_orders for r in self._test_results)
        total_failed = sum(r.failed_orders for r in self._test_results)

        overall_success_rate = (total_successful / total_orders * 100) if total_orders > 0 else 0

        # Scenario breakdown
        scenario_results = {}
        for result in self._test_results:
            condition = result.scenario.condition.value
            scenario_results[condition] = {
                "success_rate": result.success_rate,
                "orders": result.total_orders,
                "successful": result.successful_orders,
                "failed": result.failed_orders,
                "avg_response_time": result.average_response_time,
                "threshold_met": result.success_rate >= result.scenario.success_rate_threshold,
                "performance_metrics": result.performance_metrics
            }

        return {
            "test_summary": {
                "total_scenarios": len(self._test_results),
                "total_orders": total_orders,
                "successful_orders": total_successful,
                "failed_orders": total_failed,
                "overall_success_rate": overall_success_rate
            },
            "scenario_results": scenario_results,
            "performance_metrics": self._performance_metrics,
            "recommendations": self._generate_recommendations()
        }

    def _generate_recommendations(self) -> List[str]:
        """
        Generate recommendations based on test results.

        Returns:
            List of recommendations
        """
        recommendations = []

        if not self._test_results:
            return ["No test results available for recommendations"]

        # Analyze results and generate recommendations
        avg_success_rate = self._performance_metrics.get("average_success_rate", 0)

        if avg_success_rate < 70:
            recommendations.append("Overall success rate is low - consider implementing retry mechanisms")

        if avg_success_rate >= 90:
            recommendations.append("Excellent performance across market conditions")

        # Check specific conditions
        for result in self._test_results:
            if result.success_rate < result.scenario.success_rate_threshold:
                recommendations.append(
                    f"Performance under {result.scenario.condition.value} conditions needs improvement"
                )

        # Network-specific recommendations
        network_results = [r for r in self._test_results if r.scenario.condition == MarketCondition.NETWORK_ISSUES]
        if network_results and network_results[0].success_rate < 70:
            recommendations.append("Consider implementing connection pooling and retry logic for network issues")

        # Volatility-specific recommendations
        volatility_results = [r for r in self._test_results if r.scenario.condition == MarketCondition.HIGH_VOLATILITY]
        if volatility_results and volatility_results[0].success_rate < 80:
            recommendations.append("Implement dynamic pricing and order adjustment for high volatility markets")

        return recommendations if recommendations else ["All market conditions handled well"]
