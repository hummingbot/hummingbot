import asyncio

import pytest

from hummingbot.core.utils.async_call_scheduler import AsyncCallScheduler


@pytest.fixture(autouse=True)
def reset_shared_instance():
    """Ensure each test gets a clean shared instance."""
    AsyncCallScheduler._acs_shared_instance = None
    yield
    AsyncCallScheduler._acs_shared_instance = None


# ---------------------------------------------------------------------------
# Line 61: start() — creates _coro_scheduler_task via safe_ensure_future
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_creates_scheduler_task():
    """Line 61: start() must set _coro_scheduler_task to a non-None task."""
    scheduler = AsyncCallScheduler()
    assert not scheduler.started

    scheduler.start()
    try:
        assert scheduler.started
        assert scheduler.coro_scheduler_task is not None
    finally:
        scheduler.stop()


@pytest.mark.asyncio
async def test_start_stops_previous_task_before_restarting():
    """start() when already started: stops the old task and creates a new one."""
    scheduler = AsyncCallScheduler()
    scheduler.start()
    first_task = scheduler.coro_scheduler_task

    scheduler.start()
    second_task = scheduler.coro_scheduler_task
    try:
        assert first_task is not second_task
        # Allow event loop to process the cancellation
        await asyncio.sleep(0.05)
        assert first_task.cancelled() or first_task.done()
    finally:
        scheduler.stop()


# ---------------------------------------------------------------------------
# Line 104: schedule_async_call — enqueues and auto-starts if needed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_schedule_async_call_returns_result():
    """Line 104: schedule_async_call executes the coroutine and returns its result."""
    scheduler = AsyncCallScheduler(call_interval=0.001)

    async def simple_coro():
        return 42

    result = await asyncio.wait_for(
        scheduler.schedule_async_call(simple_coro(), timeout_seconds=5.0),
        timeout=5.0,
    )
    scheduler.stop()
    assert result == 42


@pytest.mark.asyncio
async def test_schedule_async_call_auto_starts_scheduler():
    """schedule_async_call auto-starts the scheduler when it hasn't been started."""
    scheduler = AsyncCallScheduler(call_interval=0.001)
    assert not scheduler.started

    async def simple_coro():
        return "auto_start"

    result = await asyncio.wait_for(
        scheduler.schedule_async_call(simple_coro(), timeout_seconds=5.0),
        timeout=5.0,
    )
    scheduler.stop()
    assert result == "auto_start"


# ---------------------------------------------------------------------------
# Line 87: exception path — exception propagates back to the caller
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_schedule_async_call_propagates_exception():
    """Line 87: when the coroutine raises, the exception is set on the future
    and re-raised at the await site."""
    scheduler = AsyncCallScheduler(call_interval=0.001)

    async def failing_coro():
        raise ValueError("deliberate failure")

    with pytest.raises(ValueError, match="deliberate failure"):
        await asyncio.wait_for(
            scheduler.schedule_async_call(failing_coro(), timeout_seconds=5.0),
            timeout=5.0,
        )
    scheduler.stop()


# ---------------------------------------------------------------------------
# stop() — cancels task and sets it to None
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stop_cancels_task():
    scheduler = AsyncCallScheduler()
    scheduler.start()
    task = scheduler.coro_scheduler_task

    scheduler.stop()
    assert scheduler.coro_scheduler_task is None
    # give the event loop a tick so the cancellation is processed
    await asyncio.sleep(0)
    assert task.cancelled() or task.done()


@pytest.mark.asyncio
async def test_stop_when_not_started_is_noop():
    scheduler = AsyncCallScheduler()
    scheduler.stop()  # must not raise
    assert not scheduler.started


# ---------------------------------------------------------------------------
# shared_instance — singleton behaviour
# ---------------------------------------------------------------------------


def test_shared_instance_is_singleton():
    a = AsyncCallScheduler.shared_instance()
    b = AsyncCallScheduler.shared_instance()
    assert a is b
    a.stop()
