import pytest

from services.event_bus import InMemoryEventBus
from services.market_data_service import MarketDataService


class FakeHyperliquidClient:
    def __init__(self, messages):
        self._messages = messages
        self.connected = False

    async def connect(self, symbols, timeframes):
        self.connected = True

    async def messages(self):
        for message in self._messages:
            yield message


@pytest.mark.asyncio
async def test_market_data_service_publishes_indicator_payloads():
    bus = InMemoryEventBus()
    candle = {
        "symbol": "BTC-PERP",
        "timeframe": "1m",
        "high": "101",
        "low": "99",
        "close": "100",
        "timestamp": 1,
    }
    client = FakeHyperliquidClient(messages=[candle, candle])
    service = MarketDataService(client, bus, symbols=["BTC-PERP"], timeframes=["1m"])

    subscriber = await bus.subscribe("md.BTC-PERP.1m")

    await service.run()

    payload = await subscriber.__anext__()
    assert payload["symbol"] == "BTC-PERP"
    assert "ema_fast" in payload
    await subscriber.aclose()
