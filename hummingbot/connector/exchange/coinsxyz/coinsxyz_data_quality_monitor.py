"""
Data Quality Monitor and Anomaly Detection for Coins.xyz Exchange.

This module provides comprehensive data quality monitoring with:
- Real-time anomaly detection
- Data consistency checks
- Price movement validation
- Volume anomaly detection
- Market data integrity monitoring
"""

import asyncio
import logging
import time
from decimal import Decimal
from typing import Dict, Any, List, Optional, Tuple
from collections import deque, defaultdict
from dataclasses import dataclass
from enum import Enum
import statistics

from hummingbot.logger import HummingbotLogger


class AnomalyType(Enum):
    """Types of anomalies that can be detected."""
    PRICE_SPIKE = "price_spike"
    PRICE_DROP = "price_drop"
    VOLUME_SPIKE = "volume_spike"
    STALE_DATA = "stale_data"
    INVALID_DATA = "invalid_data"
    SEQUENCE_GAP = "sequence_gap"
    DUPLICATE_DATA = "duplicate_data"
    SPREAD_ANOMALY = "spread_anomaly"


@dataclass
class AnomalyAlert:
    """Anomaly alert data structure."""
    timestamp: float
    trading_pair: str
    anomaly_type: AnomalyType
    severity: str  # LOW, MEDIUM, HIGH, CRITICAL
    description: str
    current_value: Any
    expected_range: Tuple[Any, Any]
    confidence: float  # 0.0 to 1.0


@dataclass
class MarketDataPoint:
    """Market data point for analysis."""
    timestamp: float
    trading_pair: str
    price: float
    volume: float
    bid: Optional[float] = None
    ask: Optional[float] = None
    spread: Optional[float] = None


class CoinsxyzDataQualityMonitor:
    """
    Comprehensive data quality monitor and anomaly detection system.

    Features:
    - Real-time price movement analysis
    - Volume anomaly detection
    - Data freshness monitoring
    - Sequence integrity checks
    - Spread analysis
    - Statistical anomaly detection
    - Configurable alert thresholds
    """

    def __init__(self,
                 window_size: int = 100,
                 price_spike_threshold: float = 0.1,  # 10%
                 volume_spike_threshold: float = 3.0,  # 3x normal
                 stale_data_threshold: float = 30.0):  # 30 seconds
        """
        Initialize data quality monitor.

        Args:
            window_size: Size of rolling window for analysis
            price_spike_threshold: Price spike detection threshold (percentage)
            volume_spike_threshold: Volume spike detection multiplier
            stale_data_threshold: Stale data threshold in seconds
        """
        self._logger = None

        # Configuration
        self._window_size = window_size
        self._price_spike_threshold = price_spike_threshold
        self._volume_spike_threshold = volume_spike_threshold
        self._stale_data_threshold = stale_data_threshold

        # Data storage
        self._price_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=window_size))
        self._volume_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=window_size))
        self._last_update_times: Dict[str, float] = {}
        self._last_sequence_ids: Dict[str, int] = {}

        # Anomaly tracking
        self._anomaly_alerts: List[AnomalyAlert] = []
        self._anomaly_counts: Dict[AnomalyType, int] = defaultdict(int)

        # Statistics
        self._stats = {
            "data_points_processed": 0,
            "anomalies_detected": 0,
            "critical_anomalies": 0,
            "data_quality_score": 1.0,
            "uptime_start": time.time()
        }

        # Background tasks
        self._monitoring_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()

    def logger(self) -> HummingbotLogger:
        """Get logger instance."""
        if self._logger is None:
            self._logger = logging.getLogger(__name__)
        return self._logger

    async def start(self) -> None:
        """Start data quality monitoring."""
        if self._monitoring_task and not self._monitoring_task.done():
            self.logger().warning("Data quality monitor already started")
            return

        self.logger().info("Starting data quality monitor")

        # Start background tasks
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

        # Reset statistics
        self._stats["uptime_start"] = time.time()

        self.logger().info("Data quality monitor started successfully")

    async def stop(self) -> None:
        """Stop data quality monitoring."""
        self.logger().info("Stopping data quality monitor")

        # Signal shutdown
        self._shutdown_event.set()

        # Cancel background tasks
        tasks_to_cancel = [self._monitoring_task, self._cleanup_task]

        for task in tasks_to_cancel:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        self.logger().info("Data quality monitor stopped")

    async def process_trade_data(self, trade_data: Dict[str, Any]) -> List[AnomalyAlert]:
        """
        Process trade data and detect anomalies.

        Args:
            trade_data: Trade data to analyze

        Returns:
            List of detected anomalies
        """
        try:
            # Handle different data formats
            symbol = trade_data.get("symbol", trade_data.get("s", ""))
            trading_pair = symbol.replace("USDT", "-USDT") if symbol else ""

            # Handle different price field names
            price_str = trade_data.get("price", trade_data.get("p", "0"))
            quantity_str = trade_data.get("quantity", trade_data.get("q", "0"))

            try:
                price = float(price_str) if price_str and price_str != "invalid_price" else 0
                quantity = float(quantity_str) if quantity_str and quantity_str != "-1.0" else 0
            except (ValueError, TypeError):
                price = 0
                quantity = 0

            timestamp = float(trade_data.get("timestamp", trade_data.get("T", time.time() * 1000)))
            if timestamp > 1e12:  # Convert from milliseconds if needed
                timestamp = timestamp / 1000

            if not trading_pair or price <= 0 or quantity <= 0:
                return [self._create_anomaly_alert(
                    trading_pair or "UNKNOWN",
                    AnomalyType.INVALID_DATA,
                    "HIGH",
                    f"Invalid trade data: price={price}, quantity={quantity}",
                    trade_data,
                    ("valid_price > 0", "valid_quantity > 0"),
                    0.9
                )]

            # Create data point
            data_point = MarketDataPoint(
                timestamp=timestamp,
                trading_pair=trading_pair,
                price=price,
                volume=quantity
            )

            # Detect anomalies
            anomalies = await self._analyze_trade_data(data_point)

            # Update statistics
            self._stats["data_points_processed"] += 1
            self._stats["anomalies_detected"] += len(anomalies)

            for anomaly in anomalies:
                if anomaly.severity == "CRITICAL":
                    self._stats["critical_anomalies"] += 1
                self._anomaly_counts[anomaly.anomaly_type] += 1

            return anomalies

        except Exception as e:
            self.logger().error(f"Error processing trade data: {e}")
            return []

    async def process_ticker_data(self, ticker_data: Dict[str, Any]) -> List[AnomalyAlert]:
        """
        Process ticker data and detect anomalies.

        Args:
            ticker_data: Ticker data to analyze

        Returns:
            List of detected anomalies
        """
        try:
            # Handle different data formats
            symbol = ticker_data.get("symbol", ticker_data.get("s", ""))
            trading_pair = symbol.replace("USDT", "-USDT") if symbol else ""

            # Handle different price field names
            price_str = ticker_data.get("last_price", ticker_data.get("c", "0"))
            volume_str = ticker_data.get("volume", ticker_data.get("v", "0"))

            try:
                last_price = float(price_str) if price_str and price_str != "invalid_price" else 0
                volume = float(volume_str) if volume_str else 0
            except (ValueError, TypeError):
                last_price = 0
                volume = 0

            timestamp = float(ticker_data.get("timestamp", ticker_data.get("E", time.time() * 1000)))
            if timestamp > 1e12:  # Convert from milliseconds if needed
                timestamp = timestamp / 1000

            # Extract bid/ask if available
            bid = None
            ask = None
            spread = None

            if "best_bid" in ticker_data and "best_ask" in ticker_data:
                bid = float(ticker_data["best_bid"])
                ask = float(ticker_data["best_ask"])
                spread = (ask - bid) / bid if bid > 0 else 0

            if not trading_pair or last_price <= 0:
                return [self._create_anomaly_alert(
                    trading_pair or "UNKNOWN",
                    AnomalyType.INVALID_DATA,
                    "HIGH",
                    f"Invalid ticker data: price={last_price}",
                    ticker_data,
                    ("valid_price > 0",),
                    0.9
                )]

            # Create data point
            data_point = MarketDataPoint(
                timestamp=timestamp,
                trading_pair=trading_pair,
                price=last_price,
                volume=volume,
                bid=bid,
                ask=ask,
                spread=spread
            )

            # Detect anomalies
            anomalies = await self._analyze_ticker_data(data_point)

            # Update statistics
            self._stats["data_points_processed"] += 1
            self._stats["anomalies_detected"] += len(anomalies)

            for anomaly in anomalies:
                if anomaly.severity == "CRITICAL":
                    self._stats["critical_anomalies"] += 1
                self._anomaly_counts[anomaly.anomaly_type] += 1

            return anomalies

        except Exception as e:
            self.logger().error(f"Error processing ticker data: {e}")
            return []

    async def process_order_book_data(self,
                                      order_book_data: Dict[str, Any],
                                      sequence_id: Optional[int] = None) -> List[AnomalyAlert]:
        """
        Process order book data and detect anomalies.

        Args:
            order_book_data: Order book data to analyze
            sequence_id: Optional sequence ID for gap detection

        Returns:
            List of detected anomalies
        """
        try:
            trading_pair = order_book_data.get("symbol", "").replace("USDT", "-USDT")
            timestamp = float(order_book_data.get("timestamp", time.time()))

            anomalies = []

            # Check for sequence gaps
            if sequence_id and trading_pair in self._last_sequence_ids:
                expected_id = self._last_sequence_ids[trading_pair] + 1
                if sequence_id > expected_id:
                    anomalies.append(self._create_anomaly_alert(
                        trading_pair,
                        AnomalyType.SEQUENCE_GAP,
                        "MEDIUM",
                        f"Sequence gap detected: expected {expected_id}, got {sequence_id}",
                        sequence_id,
                        (expected_id, expected_id),
                        0.8
                    ))

            if sequence_id:
                self._last_sequence_ids[trading_pair] = sequence_id

            # Check data freshness
            current_time = time.time()
            if current_time - timestamp > self._stale_data_threshold:
                anomalies.append(self._create_anomaly_alert(
                    trading_pair,
                    AnomalyType.STALE_DATA,
                    "MEDIUM",
                    f"Stale order book data: {current_time - timestamp:.1f}s old",
                    timestamp,
                    (current_time - self._stale_data_threshold, current_time),
                    0.7
                ))

            # Update statistics
            self._stats["data_points_processed"] += 1
            self._stats["anomalies_detected"] += len(anomalies)

            for anomaly in anomalies:
                if anomaly.severity == "CRITICAL":
                    self._stats["critical_anomalies"] += 1
                self._anomaly_counts[anomaly.anomaly_type] += 1

            return anomalies

        except Exception as e:
            self.logger().error(f"Error processing order book data: {e}")
            return []

    async def _analyze_trade_data(self, data_point: MarketDataPoint) -> List[AnomalyAlert]:
        """Analyze trade data for anomalies."""
        anomalies = []
        trading_pair = data_point.trading_pair

        # Update price history
        self._price_history[trading_pair].append(data_point.price)
        self._volume_history[trading_pair].append(data_point.volume)
        self._last_update_times[trading_pair] = data_point.timestamp

        # Check for price spikes/drops
        if len(self._price_history[trading_pair]) >= 2:
            price_history = list(self._price_history[trading_pair])
            previous_price = price_history[-2]
            current_price = price_history[-1]

            price_change = abs(current_price - previous_price) / previous_price

            if price_change > self._price_spike_threshold:
                severity = "CRITICAL" if price_change > 0.2 else "HIGH"
                anomaly_type = AnomalyType.PRICE_SPIKE if current_price > previous_price else AnomalyType.PRICE_DROP

                anomalies.append(self._create_anomaly_alert(
                    trading_pair,
                    anomaly_type,
                    severity,
                    f"Price {'spike' if current_price > previous_price else 'drop'}: {price_change:.2%}",
                    current_price,
                    (previous_price * (1 - self._price_spike_threshold),
                     previous_price * (1 + self._price_spike_threshold)),
                    0.8
                ))

        # Check for volume spikes
        if len(self._volume_history[trading_pair]) >= 10:
            volume_history = list(self._volume_history[trading_pair])
            recent_volumes = volume_history[-10:-1]  # Exclude current volume
            avg_volume = statistics.mean(recent_volumes) if recent_volumes else 0

            if avg_volume > 0 and data_point.volume > avg_volume * self._volume_spike_threshold:
                anomalies.append(self._create_anomaly_alert(
                    trading_pair,
                    AnomalyType.VOLUME_SPIKE,
                    "MEDIUM",
                    f"Volume spike: {data_point.volume / avg_volume:.1f}x normal",
                    data_point.volume,
                    (0, avg_volume * self._volume_spike_threshold),
                    0.7
                ))

        return anomalies

    async def _analyze_ticker_data(self, data_point: MarketDataPoint) -> List[AnomalyAlert]:
        """Analyze ticker data for anomalies."""
        anomalies = []

        # Check spread anomalies
        if data_point.spread is not None and data_point.spread > 0.05:  # 5% spread
            severity = "CRITICAL" if data_point.spread > 0.1 else "HIGH"
            anomalies.append(self._create_anomaly_alert(
                data_point.trading_pair,
                AnomalyType.SPREAD_ANOMALY,
                severity,
                f"Wide spread detected: {data_point.spread:.2%}",
                data_point.spread,
                (0, 0.05),
                0.8
            ))

        # Analyze price data (similar to trade analysis)
        price_anomalies = await self._analyze_trade_data(data_point)
        anomalies.extend(price_anomalies)

        return anomalies

    async def _monitoring_loop(self) -> None:
        """Background monitoring loop."""
        self.logger().info("Starting data quality monitoring loop")

        while not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(60)  # Monitor every minute

                if self._shutdown_event.is_set():
                    break

                await self._check_data_freshness()
                await self._update_quality_score()

            except Exception as e:
                self.logger().error(f"Error in monitoring loop: {e}")

        self.logger().info("Data quality monitoring loop stopped")

    async def _cleanup_loop(self) -> None:
        """Background cleanup loop."""
        while not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(300)  # Cleanup every 5 minutes

                if self._shutdown_event.is_set():
                    break

                # Clean up old anomaly alerts (keep last 1000)
                if len(self._anomaly_alerts) > 1000:
                    self._anomaly_alerts = self._anomaly_alerts[-1000:]

            except Exception as e:
                self.logger().error(f"Error in cleanup loop: {e}")

    async def _check_data_freshness(self) -> None:
        """Check for stale data across all trading pairs."""
        current_time = time.time()

        for trading_pair, last_update in self._last_update_times.items():
            if current_time - last_update > self._stale_data_threshold:
                anomaly = self._create_anomaly_alert(
                    trading_pair,
                    AnomalyType.STALE_DATA,
                    "HIGH",
                    f"No data received for {current_time - last_update:.1f}s",
                    last_update,
                    (current_time - self._stale_data_threshold, current_time),
                    0.9
                )

                self._anomaly_alerts.append(anomaly)
                self._anomaly_counts[AnomalyType.STALE_DATA] += 1
                self._stats["anomalies_detected"] += 1

    async def _update_quality_score(self) -> None:
        """Update overall data quality score."""
        total_data_points = self._stats["data_points_processed"]
        total_anomalies = self._stats["anomalies_detected"]

        if total_data_points > 0:
            anomaly_rate = total_anomalies / total_data_points
            # Quality score decreases with anomaly rate
            self._stats["data_quality_score"] = max(0.0, 1.0 - (anomaly_rate * 2))
        else:
            self._stats["data_quality_score"] = 1.0

    def _create_anomaly_alert(self,
                              trading_pair: str,
                              anomaly_type: AnomalyType,
                              severity: str,
                              description: str,
                              current_value: Any,
                              expected_range: Tuple[Any, Any],
                              confidence: float) -> AnomalyAlert:
        """Create anomaly alert."""
        alert = AnomalyAlert(
            timestamp=time.time(),
            trading_pair=trading_pair,
            anomaly_type=anomaly_type,
            severity=severity,
            description=description,
            current_value=current_value,
            expected_range=expected_range,
            confidence=confidence
        )

        self._anomaly_alerts.append(alert)

        # Log based on severity
        if severity == "CRITICAL":
            self.logger().error(f"CRITICAL ANOMALY: {trading_pair} - {description}")
        elif severity == "HIGH":
            self.logger().warning(f"HIGH ANOMALY: {trading_pair} - {description}")
        else:
            self.logger().info(f"{severity} ANOMALY: {trading_pair} - {description}")

        return alert

    def get_recent_anomalies(self, limit: int = 50) -> List[AnomalyAlert]:
        """Get recent anomaly alerts."""
        return self._anomaly_alerts[-limit:] if self._anomaly_alerts else []

    def get_anomaly_summary(self) -> Dict[str, Any]:
        """Get anomaly summary statistics."""
        return {
            "total_anomalies": len(self._anomaly_alerts),
            "anomaly_counts": dict(self._anomaly_counts),
            "recent_anomalies": len([a for a in self._anomaly_alerts if time.time() - a.timestamp < 3600]),
            "critical_anomalies": self._stats["critical_anomalies"],
            "data_quality_score": self._stats["data_quality_score"]
        }

    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive statistics."""
        uptime = time.time() - self._stats["uptime_start"]

        return {
            **self._stats,
            "uptime_seconds": uptime,
            "trading_pairs_monitored": len(self._last_update_times),
            "anomaly_rate": (self._stats["anomalies_detected"] / max(1, self._stats["data_points_processed"])),
            "anomaly_summary": self.get_anomaly_summary()
        }

    # Day 17: Additional Data Validation Methods

    def validate_user_data(self, data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate user stream data - Day 17 Implementation.

        Args:
            data: User stream data to validate

        Returns:
            Tuple of (is_valid, list of issues)
        """
        try:
            pass

            if not isinstance(data, dict):
                return False, ["Data must be a dictionary"]

            # Determine data type and validate accordingly
            data_type = data.get('type')
            if not data_type:
                return False, ["Missing data type"]

            if data_type == 'balance_update':
                return self._validate_balance_update_data(data)
            elif data_type == 'order_update':
                return self._validate_order_update_data(data)
            elif data_type == 'trade_update':
                return self._validate_trade_update_data(data)
            else:
                return True, [f"Unknown data type: {data_type}"]

        except Exception as e:
            self.logger().error(f"Error validating user data: {e}")
            return False, [f"Validation error: {str(e)}"]

    def _validate_balance_update_data(self, data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate balance update data."""
        issues = []

        # Check required fields
        if 'balances' not in data:
            issues.append("Missing balances field")

        if 'timestamp' not in data:
            issues.append("Missing timestamp field")

        # Validate balances
        balances = data.get('balances', [])
        if not isinstance(balances, list):
            issues.append("Balances must be a list")
        else:
            for i, balance in enumerate(balances):
                if not isinstance(balance, dict):
                    issues.append(f"Balance {i} must be a dictionary")
                    continue

                # Check required balance fields
                for field in ['asset', 'free', 'locked']:
                    if field not in balance:
                        issues.append(f"Balance {i} missing {field}")

                # Validate numeric fields
                for field in ['free', 'locked']:
                    if field in balance:
                        try:
                            value = Decimal(str(balance[field]))
                            if value < 0:
                                issues.append(f"Balance {i} {field} cannot be negative")
                        except (ValueError, TypeError):
                            issues.append(f"Balance {i} {field} must be numeric")

        return len(issues) == 0, issues

    def _validate_order_update_data(self, data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate order update data."""
        issues = []

        # Check required fields
        required_fields = ['order_id', 'status', 'timestamp']
        for field in required_fields:
            if field not in data:
                issues.append(f"Missing required field: {field}")

        # Validate status
        valid_statuses = ['NEW', 'PARTIALLY_FILLED', 'FILLED', 'CANCELED', 'REJECTED', 'EXPIRED']
        status = data.get('status')
        if status and status not in valid_statuses:
            issues.append(f"Invalid order status: {status}")

        # Validate numeric fields
        numeric_fields = ['quantity', 'price', 'executed_quantity']
        for field in numeric_fields:
            if field in data:
                try:
                    value = Decimal(str(data[field]))
                    if value < 0:
                        issues.append(f"Order {field} cannot be negative")
                except (ValueError, TypeError):
                    issues.append(f"Order {field} must be numeric")

        return len(issues) == 0, issues

    def _validate_trade_update_data(self, data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate trade update data."""
        issues = []

        # Check required fields
        required_fields = ['trade_id', 'order_id', 'quantity', 'price', 'timestamp']
        for field in required_fields:
            if field not in data:
                issues.append(f"Missing required field: {field}")

        # Validate numeric fields
        numeric_fields = ['quantity', 'price', 'commission']
        for field in numeric_fields:
            if field in data:
                try:
                    value = Decimal(str(data[field]))
                    if value <= 0 and field in ['quantity', 'price']:
                        issues.append(f"Trade {field} must be positive")
                    elif value < 0 and field == 'commission':
                        issues.append(f"Trade {field} cannot be negative")
                except (ValueError, TypeError):
                    issues.append(f"Trade {field} must be numeric")

        return len(issues) == 0, issues

    def check_data_consistency(self, data_batch: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Check data consistency across multiple records - Day 17 Implementation.

        Args:
            data_batch: Batch of data records to check

        Returns:
            Consistency check results
        """
        try:
            results = {
                'total_records': len(data_batch),
                'consistent_records': 0,
                'inconsistent_records': 0,
                'issues': [],
                'duplicate_count': 0,
                'timestamp_gaps': 0,
                'data_quality_score': 0.0
            }

            if not data_batch:
                return results

            # Check for duplicates
            seen_records = set()
            duplicates = 0

            for i, record in enumerate(data_batch):
                # Generate record signature
                record_sig = self._generate_record_signature(record)
                if record_sig in seen_records:
                    duplicates += 1
                    results['issues'].append(f"Duplicate record at index {i}")
                else:
                    seen_records.add(record_sig)

            results['duplicate_count'] = duplicates

            # Check timestamp consistency
            timestamps = []
            for record in data_batch:
                if 'timestamp' in record:
                    try:
                        timestamps.append(int(record['timestamp']))
                    except (ValueError, TypeError):
                        results['issues'].append("Invalid timestamp format")

            # Check for timestamp gaps
            if len(timestamps) > 1:
                timestamps.sort()
                gaps = 0
                for i in range(1, len(timestamps)):
                    gap = timestamps[i] - timestamps[i - 1]
                    if gap > 60000:  # More than 1 minute
                        gaps += 1
                        results['issues'].append(f"Large timestamp gap: {gap}ms")

                results['timestamp_gaps'] = gaps

            # Calculate consistency score
            total_issues = duplicates + results['timestamp_gaps']
            results['inconsistent_records'] = total_issues
            results['consistent_records'] = len(data_batch) - total_issues

            if len(data_batch) > 0:
                results['data_quality_score'] = results['consistent_records'] / len(data_batch)

            return results

        except Exception as e:
            self.logger().error(f"Error checking data consistency: {e}")
            return {'error': str(e)}

    def _generate_record_signature(self, record: Dict[str, Any]) -> str:
        """Generate unique signature for record deduplication."""
        key_parts = []

        # Use different keys based on record type
        record_type = record.get('type', 'unknown')

        if record_type == 'order_update':
            key_parts = [
                record.get('order_id', ''),
                record.get('timestamp', ''),
                record.get('status', '')
            ]
        elif record_type == 'trade_update':
            key_parts = [
                record.get('trade_id', ''),
                record.get('timestamp', '')
            ]
        elif record_type == 'balance_update':
            key_parts = [
                record.get('timestamp', ''),
                str(len(record.get('balances', [])))
            ]
        else:
            key_parts = [str(record)]

        return '|'.join(str(part) for part in key_parts)

    def monitor_data_quality(self) -> Dict[str, Any]:
        """
        Monitor overall data quality - Day 17 Implementation.

        Returns:
            Data quality monitoring results
        """
        try:
            current_time = time.time()

            # Get current statistics
            total_processed = self._stats.get("data_points_processed", 0)
            anomalies_detected = self._stats.get("anomalies_detected", 0)

            # Calculate quality metrics
            if total_processed > 0:
                anomaly_rate = anomalies_detected / total_processed
                quality_score = max(0.0, 1.0 - anomaly_rate)
            else:
                anomaly_rate = 0.0
                quality_score = 1.0

            # Determine quality level
            if quality_score >= 0.95:
                quality_level = "EXCELLENT"
            elif quality_score >= 0.90:
                quality_level = "GOOD"
            elif quality_score >= 0.80:
                quality_level = "ACCEPTABLE"
            elif quality_score >= 0.60:
                quality_level = "POOR"
            else:
                quality_level = "CRITICAL"

            monitoring_results = {
                'timestamp': current_time,
                'quality_score': quality_score,
                'quality_level': quality_level,
                'anomaly_rate': anomaly_rate,
                'total_data_points': total_processed,
                'anomalies_detected': anomalies_detected,
                'trading_pairs_monitored': len(self._last_update_times),
                'uptime_seconds': current_time - self._start_time,
                'recent_anomalies': list(self._recent_anomalies)[-10:],  # Last 10 anomalies
                'recommendations': self._generate_quality_recommendations(quality_level)
            }

            return monitoring_results

        except Exception as e:
            self.logger().error(f"Error monitoring data quality: {e}")
            return {'error': str(e)}

    def _generate_quality_recommendations(self, quality_level: str) -> List[str]:
        """Generate recommendations based on quality level."""
        recommendations = []

        if quality_level == "CRITICAL":
            recommendations.extend([
                "URGENT: Data quality is critical - immediate attention required",
                "Check data source connectivity and API status",
                "Verify data parsing and validation logic",
                "Consider implementing emergency data recovery procedures"
            ])
        elif quality_level == "POOR":
            recommendations.extend([
                "Data quality needs significant improvement",
                "Review and tighten validation rules",
                "Investigate data source reliability issues",
                "Consider increasing monitoring frequency"
            ])
        elif quality_level == "ACCEPTABLE":
            recommendations.extend([
                "Data quality is acceptable but has room for improvement",
                "Monitor trending issues and patterns",
                "Consider optimizing data processing pipeline"
            ])
        elif quality_level in ["GOOD", "EXCELLENT"]:
            recommendations.extend([
                "Data quality is good - maintain current monitoring",
                "Continue regular quality assessments"
            ])

        return recommendations
