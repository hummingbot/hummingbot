"""
NEOMA P-CAM Shock-Damped Pure Market Making (PMM) Strategy for Hummingbot
Protects passive liquidity orders from toxic sweeps using 15µs physical relaxation.

Usage in Hummingbot CLI:
  1. Copy this file into hummingbot/scripts/
  2. Start Hummingbot: bin/hummingbot.py
  3. Run command: start --script hummingbot_pcam_pmm.py
"""

from decimal import Decimal
import time
import requests

try:
    from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
    from hummingbot.core.data_type.common import OrderType, PriceType
    from hummingbot.core.data_type.order_candidate import OrderCandidate
    HUMMINGBOT_AVAILABLE = True
except ImportError:
    HUMMINGBOT_AVAILABLE = False
    class ScriptStrategyBase:
        pass

class PCAMHummingbotStrategy(ScriptStrategyBase):
    exchange = "binance_paper_trade"
    trading_pair = "BTC-USDT"
    markets = {exchange: {trading_pair}}

    bid_spread = Decimal("0.001")   # 0.1%
    ask_spread = Decimal("0.001")   # 0.1%
    order_amount = Decimal("0.005") # 0.005 BTC
    order_refresh_time = 15         # 15s

    pcam_host = "https://neoma-p-cam-quant-reflex-hft.p.rapidapi.com"
    rapidapi_key = ""

    create_timestamp = 0
    last_mid_price = 0.0
    last_timestamp = time.perf_counter()

    def on_tick(self):
        if not HUMMINGBOT_AVAILABLE:
            return

        now = time.perf_counter()
        dt = max(1e-4, now - self.last_timestamp)

        order_book = self.connectors[self.exchange].get_order_book(self.trading_pair)
        best_bid = float(order_book.bid_price)
        best_ask = float(order_book.ask_price)
        bid_vol = float(order_book.bid_volume)
        ask_vol = float(order_book.ask_volume)
        mid_price = (best_bid + best_ask) / 2.0

        imbalance = (bid_vol - ask_vol) / max(1e-6, bid_vol + ask_vol)
        flux_v = round(0.080 + (abs(imbalance) * 0.020), 4)
        velocity = (mid_price - self.last_mid_price) / dt if self.last_mid_price > 0 else 0.0

        self.last_mid_price = mid_price
        self.last_timestamp = now

        zeta, should_cancel = self.query_pcam_reflex(flux_v, abs(velocity))

        # Damping ratio Zeta > 1.2: Pull quotes to avoid toxic fills
        if should_cancel:
            self.logger().warning(
                f"🚨 [P-CAM SHOCK DAMPING] Stress detected! Zeta={zeta:.4f} > 1.2. "
                f"PULL_QUOTES active - canceling resting orders."
            )
            self.cancel_all_orders()
            return

        if self.create_timestamp <= self.current_timestamp:
            self.cancel_all_orders()
            self.create_proactive_orders(mid_price)
            self.create_timestamp = self.order_refresh_time + self.current_timestamp

    def query_pcam_reflex(self, flux_v: float, velocity: float):
        payload = {
            "flux_potential_v": min(0.120, max(0.080, flux_v)),
            "gradient_velocity": round(velocity, 2),
            "gradient_acceleration": 12000.0,
            "active_strain": 1.05
        }
        headers = {"Content-Type": "application/json"}
        if self.rapidapi_key:
            headers["X-RapidAPI-Key"] = self.rapidapi_key
            headers["X-RapidAPI-Host"] = "neoma-p-cam-quant-reflex-hft.p.rapidapi.com"

        try:
            res = requests.post(f"{self.pcam_host}/v1/quant/predict", json=payload, headers=headers, timeout=1.0)
            if res.status_code == 200:
                data = res.json()
                zeta = data.get("zeta", 1.0)
                return zeta, (zeta > 1.2)
        except Exception:
            pass
        return 1.0, False

    def cancel_all_orders(self):
        for order in self.get_active_orders(connector_name=self.exchange):
            self.cancel(self.exchange, order.trading_pair, order.client_order_id)

    def create_proactive_orders(self, mid_price):
        buy_price = Decimal(str(mid_price)) * (Decimal("1") - self.bid_spread)
        sell_price = Decimal(str(mid_price)) * (Decimal("1") + self.ask_spread)

        buy_order = OrderCandidate(
            trading_pair=self.trading_pair,
            is_maker=True,
            order_type=OrderType.LIMIT,
            order_side=PriceType.Buy,
            amount=self.order_amount,
            price=buy_price
        )
        sell_order = OrderCandidate(
            trading_pair=self.trading_pair,
            is_maker=True,
            order_type=OrderType.LIMIT,
            order_side=PriceType.Sell,
            amount=self.order_amount,
            price=sell_price
        )

        adj_buy = self.connectors[self.exchange].budget_checker.adjust_candidate(buy_order)
        adj_sell = self.connectors[self.exchange].budget_checker.adjust_candidate(sell_order)

        if adj_buy.amount > Decimal("0"):
            self.buy(self.exchange, self.trading_pair, adj_buy.amount, OrderType.LIMIT, adj_buy.price)
        if adj_sell.amount > Decimal("0"):
            self.sell(self.exchange, self.trading_pair, adj_sell.amount, OrderType.LIMIT, adj_sell.price)
