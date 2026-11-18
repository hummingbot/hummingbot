"""
NEOMA P-CAM Shock-Damped Pure Market Making (PMM) Strategy for Hummingbot
Protects passive liquidity orders from toxic sweeps using 15µs physical relaxation.

Usage in Hummingbot CLI:
  1. Copy this file into hummingbot/scripts/
  2. Start Hummingbot: bin/hummingbot.py
  3. Run command: start --v2 hummingbot_pcam_pmm.py
"""

import asyncio
import time
from decimal import Decimal
from pydantic import Field

try:
    import aiohttp
except ImportError:
    pass

try:
    from hummingbot.strategy.strategy_v2_base import StrategyV2Base
    from hummingbot.strategy.strategy_v2_config_base import StrategyV2ConfigBase
    from hummingbot.core.data_type.common import OrderType, TradeType
    from hummingbot.core.data_type.order_candidate import OrderCandidate
    HUMMINGBOT_AVAILABLE = True
except ImportError:
    # 로컬 독립 테스트용 모의 클래스
    HUMMINGBOT_AVAILABLE = False
    class StrategyV2Base:
        pass
    class StrategyV2ConfigBase:
        pass

class PCAMHummingbotConfig(StrategyV2ConfigBase):
    script_file_name: str = Field(default_factory=lambda: __name__)

    # 거래소 및 마켓 설정
    exchange: str = Field(default="binance_paper_trade", client_data=None)
    trading_pair: str = Field(default="BTC-USDT", client_data=None)

    # 기본 마켓메이킹 파라미터
    bid_spread: Decimal = Field(default=Decimal("0.001"), client_data=None)
    ask_spread: Decimal = Field(default=Decimal("0.001"), client_data=None)
    order_amount: Decimal = Field(default=Decimal("0.005"), client_data=None)
    order_refresh_time: int = Field(default=15, client_data=None)

    # P-CAM 설정
    pcam_host: str = Field(default="https://neoma-p-cam-quant-reflex-hft.p.rapidapi.com", client_data=None)
    rapidapi_key: str = Field(default="", client_data=None)

class PCAMHummingbotStrategy(StrategyV2Base):
    @classmethod
    def init_markets(cls, config: PCAMHummingbotConfig):
        cls.markets = {config.exchange: {config.trading_pair}}

    def __init__(self, connectors, config: PCAMHummingbotConfig):
        super().__init__(connectors)
        self.config = config

        self.create_timestamp = 0
        self.last_mid_price = 0.0
        self.last_velocity = 0.0
        self.last_timestamp = time.perf_counter()

        # P-CAM 상태 변수 (초기 상태는 안전하지 않음으로 간주하여 첫 응답 전 주문 생성 방지)
        self.current_zeta = 1.0
        self.should_cancel = True
        self.api_failed = True
        self.is_safe_to_trade = False
        self.query_task = None

    def on_tick(self):
        """매 초마다 실행되는 허밍봇 메인 루프"""
        if not HUMMINGBOT_AVAILABLE:
            return

        now = time.perf_counter()
        dt = max(1e-4, now - self.last_timestamp)

        connector = self.connectors[self.config.exchange]
        order_book = connector.get_order_book(self.config.trading_pair)

        # 1. 실시간 오더북 최우선 호가 및 볼륨 조회
        best_bid = float(connector.get_price(self.config.trading_pair, True))
        best_ask = float(connector.get_price(self.config.trading_pair, False))

        bid_entries = list(order_book.bid_entries())
        ask_entries = list(order_book.ask_entries())
        bid_vol = float(bid_entries[0].amount) if bid_entries else 0.0
        ask_vol = float(ask_entries[0].amount) if ask_entries else 0.0

        mid_price = (best_bid + best_ask) / 2.0

        # 2. 4차원 물리 텐서 파라미터 연산 (가속도 도출)
        imbalance = (bid_vol - ask_vol) / max(1e-6, bid_vol + ask_vol)
        flux_v = round(0.080 + (abs(imbalance) * 0.020), 4)

        velocity = (mid_price - self.last_mid_price) / dt if self.last_mid_price > 0 else 0.0
        acceleration = (velocity - self.last_velocity) / dt

        self.last_mid_price = mid_price
        self.last_velocity = velocity
        self.last_timestamp = now

        # 3. P-CAM 인클레이브 15µs 충격 완화 평가 (비동기 호출로 봇 멈춤 방지)
        if self.query_task is None or self.query_task.done():
            self.query_task = asyncio.create_task(
                self.query_pcam_reflex(flux_v, abs(velocity), abs(acceleration))
            )

        # 4. 방어 로직: 첫 응답 대기 중, API 실패, 또는 감쇠비 Zeta > 1.2 초과 시 주문 전량 즉시 취소
        if not self.is_safe_to_trade:
            if self.api_failed:
                self.logger().warning(
                    "🚨 [P-CAM] API connection pending/failed. PULL_QUOTES active for safety."
                )
            elif self.should_cancel:
                self.logger().warning(
                    f"🚨 [P-CAM SHOCK DAMPING] Non-equilibrium stress detected! Zeta={self.current_zeta:.4f} > 1.2. "
                    f"PULL_QUOTES active - canceling all open limit orders to eliminate slippage."
                )
            self.cancel_all_orders()
            return

        # 5. 임계 감쇠 안정 구간(0.8 <= Zeta <= 1.2): 정상 마켓메이킹 호가 배치
        if self.create_timestamp <= now:
            self.cancel_all_orders()
            self.create_proactive_orders(mid_price)
            self.create_timestamp = self.config.order_refresh_time + now

    async def query_pcam_reflex(self, flux_v: float, velocity: float, acceleration: float):
        payload = {
            "flux_potential_v": min(0.120, max(0.080, flux_v)),
            "gradient_velocity": round(velocity, 2),
            "gradient_acceleration": round(acceleration, 2),
            "active_strain": 1.05
        }
        headers = {"Content-Type": "application/json"}
        if self.config.rapidapi_key:
            headers["X-RapidAPI-Key"] = self.config.rapidapi_key
            headers["X-RapidAPI-Host"] = "neoma-p-cam-quant-reflex-hft.p.rapidapi.com"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self.config.pcam_host}/v1/quant/predict", json=payload, headers=headers, timeout=1.0) as res:
                    if res.status == 200:
                        data = await res.json()
                        zeta = data.get("zeta")
                        if zeta is not None:
                            self.current_zeta = zeta
                            self.should_cancel = (zeta > 1.2)
                            self.api_failed = False
                            self.is_safe_to_trade = not self.should_cancel
                            return
        except Exception:
            pass

        # API 호출 실패, 타임아웃, 또는 유효하지 않은 응답 시 방어 모드 활성화
        self.api_failed = True
        self.should_cancel = True
        self.is_safe_to_trade = False

    def cancel_all_orders(self):
        for order in self.get_active_orders(connector_name=self.config.exchange):
            self.cancel(self.config.exchange, order.trading_pair, order.client_order_id)

    def create_proactive_orders(self, mid_price):
        buy_price = Decimal(str(mid_price)) * (Decimal("1") - self.config.bid_spread)
        sell_price = Decimal(str(mid_price)) * (Decimal("1") + self.config.ask_spread)

        buy_order = OrderCandidate(
            trading_pair=self.config.trading_pair,
            is_maker=True,
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            amount=self.config.order_amount,
            price=buy_price
        )
        sell_order = OrderCandidate(
            trading_pair=self.config.trading_pair,
            is_maker=True,
            order_type=OrderType.LIMIT,
            order_side=TradeType.SELL,
            amount=self.config.order_amount,
            price=sell_price
        )

        adjusted_buy = self.connectors[self.config.exchange].budget_checker.adjust_candidate(buy_order)
        adjusted_sell = self.connectors[self.config.exchange].budget_checker.adjust_candidate(sell_order)

        if adjusted_buy.amount > Decimal("0"):
            self.buy(self.config.exchange, self.config.trading_pair, adjusted_buy.amount, OrderType.LIMIT, adjusted_buy.price)
        if adjusted_sell.amount > Decimal("0"):
            self.sell(self.config.exchange, self.config.trading_pair, adjusted_sell.amount, OrderType.LIMIT, adjusted_sell.price)

# 로컬에서 단독 실행 시 구조 안내 출력
if __name__ == "__main__":
    print("=" * 78)
    print(" [NEOMA P-CAM] Hummingbot Pure Market Making (PMM) Shock Damping Strategy")
    print("=" * 78)
    print(" ✔ Standalone script ready for deployment.")
    print(" ✔ Deployment Steps:")
    print("    1. Copy this script to your Hummingbot root: 'hummingbot/scripts/'")
    print("    2. Launch Hummingbot on your server/Docker: 'bin/hummingbot.py'")
    print("    3. Inside Hummingbot CLI, type: start --v2 hummingbot_pcam_pmm.py")
    print(" ✔ The bot will ping P-CAM asynchronously. Continuous live execution")
    print("   automatically converts via RapidAPI PRO tier ($499/mo).")
    print("=" * 78)
