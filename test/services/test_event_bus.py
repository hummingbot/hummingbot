import pytest

from services.event_bus import InMemoryEventBus


@pytest.mark.asyncio
async def test_in_memory_event_bus_fan_out():
    bus = InMemoryEventBus()
    subscriber_one = await bus.subscribe("md.BTC.1m")
    subscriber_two = await bus.subscribe("md.BTC.1m")

    payload = {"value": 42}
    await bus.publish("md.BTC.1m", payload)

    first = await subscriber_one.__anext__()
    second = await subscriber_two.__anext__()

    assert first == payload
    assert second == payload

    await subscriber_one.aclose()
    await subscriber_two.aclose()
