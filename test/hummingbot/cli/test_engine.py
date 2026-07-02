import asyncio
import signal
import unittest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.cli import bot, engine


def tearDownModule():
    # IsolatedAsyncioTestCase leaves the main thread with no current event loop; legacy tests later
    # in the suite still reach it via asyncio.get_event_loop(), so restore one.
    asyncio.set_event_loop(asyncio.new_event_loop())


def _make_hb(connectors=None):
    hb = MagicMock()
    hb.trading_core.connector_manager.connectors = connectors if connectors is not None else {}
    return hb


class CollectBalancesTest(unittest.IsolatedAsyncioTestCase):
    async def test_filters_zero_amounts_and_floats_values(self):
        hb = _make_hb({"binance": object()})
        hb.trading_core.get_current_balances = AsyncMock(
            return_value={"BTC": Decimal("1.5"), "DUST": Decimal("0")})
        balances = await engine._collect_balances(hb)
        self.assertEqual(balances, {"binance": {"BTC": 1.5}})
        hb.trading_core.get_current_balances.assert_awaited_once_with("binance")

    async def test_failing_connector_is_skipped(self):
        hb = _make_hb({"good": object(), "bad": object()})

        async def balances_for(name):
            if name == "bad":
                raise RuntimeError("boom")
            return {"ETH": Decimal("2")}

        hb.trading_core.get_current_balances = AsyncMock(side_effect=balances_for)
        balances = await engine._collect_balances(hb)
        self.assertEqual(balances, {"good": {"ETH": 2.0}})


class FormatStatusTextTest(unittest.IsolatedAsyncioTestCase):
    async def test_no_strategy_returns_none(self):
        hb = _make_hb()
        hb.trading_core.strategy = None
        self.assertIsNone(await engine._format_status_text(hb))

    async def test_sync_format_status(self):
        hb = _make_hb()
        hb.trading_core.strategy.format_status = MagicMock(return_value="all good")
        self.assertEqual(await engine._format_status_text(hb), "all good")

    async def test_coroutine_format_status_is_awaited(self):
        async def status_coro():
            return "async status"

        hb = _make_hb()
        hb.trading_core.strategy.format_status = MagicMock(return_value=status_coro())
        self.assertEqual(await engine._format_status_text(hb), "async status")

    async def test_format_status_exception_returns_none(self):
        hb = _make_hb()
        hb.trading_core.strategy.format_status = MagicMock(side_effect=RuntimeError("nope"))
        self.assertIsNone(await engine._format_status_text(hb))


class WriteSnapshotTest(unittest.IsolatedAsyncioTestCase):
    async def test_running_snapshot_includes_engine_and_balances(self):
        hb = _make_hb()
        hb.trading_core.get_status = MagicMock(return_value={"strategy": "pmm"})
        with patch.object(engine, "_collect_balances", new=AsyncMock(return_value={"b": {"BTC": 1.0}})), \
                patch.object(engine, "_format_status_text", new=AsyncMock(return_value="txt")), \
                patch.object(bot, "write_status") as write_status:
            await engine._write_snapshot(hb, "mybot", running=True)
        snapshot = write_status.call_args[0][0]
        self.assertEqual(snapshot["name"], "mybot")
        self.assertTrue(snapshot["running"])
        self.assertEqual(snapshot["engine"], {"strategy": "pmm"})
        self.assertEqual(snapshot["format_status"], "txt")
        self.assertEqual(snapshot["balances"], {"b": {"BTC": 1.0}})
        self.assertIsInstance(snapshot["pid"], int)
        self.assertIn("updated_at", snapshot)

    async def test_get_status_failure_yields_none_engine(self):
        hb = _make_hb()
        hb.trading_core.get_status = MagicMock(side_effect=RuntimeError("dead"))
        with patch.object(engine, "_collect_balances", new=AsyncMock(return_value={})), \
                patch.object(engine, "_format_status_text", new=AsyncMock(return_value=None)), \
                patch.object(bot, "write_status") as write_status:
            await engine._write_snapshot(hb, "mybot", running=True)
        self.assertIsNone(write_status.call_args[0][0]["engine"])

    async def test_stopped_snapshot_omits_balances(self):
        hb = _make_hb()
        hb.trading_core.get_status = MagicMock(return_value={})
        with patch.object(engine, "_collect_balances", new=AsyncMock()) as collect, \
                patch.object(engine, "_format_status_text", new=AsyncMock(return_value=None)), \
                patch.object(bot, "write_status") as write_status:
            await engine._write_snapshot(hb, "mybot", running=False)
        snapshot = write_status.call_args[0][0]
        self.assertNotIn("balances", snapshot)
        self.assertFalse(snapshot["running"])
        collect.assert_not_awaited()


class ServeTest(unittest.IsolatedAsyncioTestCase):
    """Signal handlers are captured on a fake loop — no real handlers are installed and no
    real signals are sent; handler callbacks are invoked directly to simulate delivery."""

    def _fake_loop(self, real_loop):
        handlers = {}
        fake_loop = MagicMock()
        fake_loop.add_signal_handler.side_effect = lambda sig, cb: handlers.__setitem__(sig, cb)
        fake_loop.create_task.side_effect = real_loop.create_task
        return fake_loop, handlers

    async def _drain(self, condition, tries=50):
        for _ in range(tries):
            if condition():
                return
            await asyncio.sleep(0)

    async def test_serves_until_sigterm_and_shuts_down(self):
        real_loop = asyncio.get_running_loop()
        fake_loop, handlers = self._fake_loop(real_loop)
        hb = _make_hb()
        hb.stop_loop = AsyncMock()
        hb.trading_core.shutdown = AsyncMock()
        snap = AsyncMock()
        with patch.object(engine, "_write_snapshot", new=snap), \
                patch.object(bot, "clear_pid") as clear_pid, \
                patch.object(engine.asyncio, "get_event_loop", return_value=fake_loop):
            task = real_loop.create_task(engine._serve(hb, "mybot"))
            await self._drain(lambda: snap.await_count >= 1)
            self.assertEqual(set(handlers), {signal.SIGTERM, signal.SIGINT, signal.SIGUSR1})
            # initial snapshot (readiness marker)
            self.assertEqual(snap.await_args_list[0].kwargs, {"running": True})

            handlers[signal.SIGUSR1]()  # on-demand status snapshot
            await self._drain(lambda: snap.await_count >= 2)
            self.assertEqual(snap.await_count, 2)

            handlers[signal.SIGTERM]()  # graceful stop
            await task
        hb.stop_loop.assert_awaited_once()
        hb.trading_core.shutdown.assert_awaited_once()
        self.assertEqual(snap.await_count, 3)
        self.assertEqual(snap.await_args_list[-1].kwargs, {"running": False})
        clear_pid.assert_called_once()

    async def test_shutdown_errors_still_write_final_snapshot_and_clear_pid(self):
        real_loop = asyncio.get_running_loop()
        fake_loop, handlers = self._fake_loop(real_loop)
        hb = _make_hb()
        hb.stop_loop = AsyncMock(side_effect=RuntimeError("stop failed"))
        hb.trading_core.shutdown = AsyncMock(side_effect=RuntimeError("shutdown failed"))
        snap = AsyncMock()
        with patch.object(engine, "_write_snapshot", new=snap), \
                patch.object(bot, "clear_pid") as clear_pid, \
                patch.object(engine.asyncio, "get_event_loop", return_value=fake_loop):
            task = real_loop.create_task(engine._serve(hb, "mybot"))
            await self._drain(lambda: signal.SIGTERM in handlers and snap.await_count >= 1)
            handlers[signal.SIGTERM]()
            await task
        self.assertEqual(snap.await_args_list[-1].kwargs, {"running": False})
        clear_pid.assert_called_once()


class RunEngineTest(unittest.IsolatedAsyncioTestCase):
    def _patches(self, hb, started=True):
        return (
            patch.object(engine, "load_client_config_map_from_file", return_value=MagicMock(log_level="INFO")),
            patch.object(engine, "ETHKeyFileSecretManger", return_value=MagicMock()),
            patch.object(engine, "autofix_permissions"),
            patch.object(engine, "bootstrap_application", new=AsyncMock(return_value=hb)),
            patch.object(engine, "load_and_start_strategy", new=AsyncMock(return_value=started)),
            patch.object(engine, "wait_for_gateway_ready", new=AsyncMock()),
            patch.object(engine, "_serve", new=AsyncMock()),
            patch.object(bot, "update_meta"),
        )

    async def test_bad_password_returns_4(self):
        patches = self._patches(hb=None)
        with patches[0], patches[1], patches[2] as autofix, patches[3], patches[4] as load_start, \
                patches[5], patches[6], patches[7]:
            rc = await engine.run_engine("mybot", None, None, "pw", None)
        self.assertEqual(rc, 4)
        autofix.assert_not_called()
        load_start.assert_not_awaited()

    async def test_failed_strategy_load_returns_1(self):
        hb = _make_hb()
        patches = self._patches(hb, started=False)
        with patches[0], patches[1], patches[2], patches[3], patches[4], \
                patches[5] as gateway, patches[6], patches[7]:
            rc = await engine.run_engine("mybot", "conf.yml", None, "pw", None)
        self.assertEqual(rc, 1)
        gateway.assert_not_awaited()

    async def test_happy_path_records_meta_and_serves(self):
        hb = _make_hb()
        hb.trading_core.trade_fill_db.db_path = "/data/mybot.sqlite"
        hb.trading_core._strategy_file_name = "conf_v2.yml"
        hb.trading_core.strategy_name = "pmm"
        patches = self._patches(hb)
        with patches[0], patches[1], patches[2] as autofix, patches[3], patches[4] as load_start, \
                patches[5] as gateway, patches[6] as serve, patches[7] as update_meta:
            rc = await engine.run_engine("mybot", None, "conf_v2.yml", "pw", "501:20")
        self.assertEqual(rc, 0)
        autofix.assert_called_once_with("501:20")
        load_start.assert_awaited_once_with(hb, config_file_name=None, v2_conf="conf_v2.yml", headless=True)
        gateway.assert_awaited_once_with(hb)
        update_meta.assert_called_once_with(
            db_path="/data/mybot.sqlite", config_file_path="conf_v2.yml", strategy_name="pmm")
        serve.assert_awaited_once_with(hb, "mybot")

    async def test_missing_trade_db_records_none_db_path(self):
        hb = _make_hb()
        hb.trading_core.trade_fill_db = None
        hb.trading_core._strategy_file_name = None
        hb.strategy_file_name = "conf_v1"
        hb.trading_core.strategy_name = "xemm"
        patches = self._patches(hb)
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], \
                patches[6], patches[7] as update_meta:
            rc = await engine.run_engine("mybot", "conf_v1.yml", None, "pw", None)
        self.assertEqual(rc, 0)
        update_meta.assert_called_once_with(db_path=None, config_file_path="conf_v1", strategy_name="xemm")


class MainTest(unittest.TestCase):
    """main() is exercised with a fully mocked asyncio module and a mocked run_engine — no real
    event loop is created and no engine machinery runs."""

    def _run_main(self, argv, env, rc=0, run_error=None):
        fake_asyncio = MagicMock()
        loop = fake_asyncio.new_event_loop.return_value
        if run_error is not None:
            loop.run_until_complete.side_effect = run_error
        else:
            loop.run_until_complete.return_value = rc
        run_engine = MagicMock(return_value=MagicMock())  # plain sentinel, not a coroutine
        with patch.object(engine, "asyncio", fake_asyncio), \
                patch.object(engine, "run_engine", run_engine), \
                patch.object(engine.sys, "argv", ["engine"] + argv), \
                patch.dict(engine.os.environ, env, clear=True):
            with self.assertRaises(SystemExit) as ctx:
                engine.main()
            env_after = dict(engine.os.environ)
        return ctx.exception.code, run_engine, env_after

    def test_missing_password_exits_4_without_running(self):
        code, run_engine, _ = self._run_main(["--name", "mybot"], env={})
        self.assertEqual(code, 4)
        run_engine.assert_not_called()

    def test_password_is_scrubbed_from_env_and_passed_to_engine(self):
        code, run_engine, env_after = self._run_main(
            ["--name", "mybot", "--config", "c.yml", "--script-config", "v2.yml",
             "--auto-set-permissions", "501:20"],
            env={"HBOT_PASSWORD": "s3cret", "CONFIG_PASSWORD": "legacy"})
        self.assertEqual(code, 0)
        run_engine.assert_called_once_with("mybot", "c.yml", "v2.yml", "s3cret", "501:20")
        self.assertNotIn("HBOT_PASSWORD", env_after)
        self.assertNotIn("CONFIG_PASSWORD", env_after)

    def test_config_password_fallback(self):
        code, run_engine, env_after = self._run_main(
            ["--name", "mybot"], env={"CONFIG_PASSWORD": "legacy"})
        self.assertEqual(code, 0)
        self.assertEqual(run_engine.call_args[0][3], "legacy")
        self.assertNotIn("CONFIG_PASSWORD", env_after)

    def test_engine_crash_exits_1(self):
        code, _, _ = self._run_main(
            ["--name", "mybot"], env={"HBOT_PASSWORD": "pw"}, run_error=RuntimeError("boom"))
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
