import asyncio
import io
import logging
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.client import runner
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.logger.cli_handler import CLIHandler


class AutofixPermissionsTest(unittest.TestCase):
    """pwd/grp/subprocess/os are fully mocked — no chown runs and no uid/gid is changed."""

    def _run(self, spec):
        with patch.object(runner, "pwd") as pwd_mock, \
                patch.object(runner, "grp") as grp_mock, \
                patch.object(runner, "subprocess") as subprocess_mock, \
                patch.object(runner, "os") as os_mock:
            pwd_mock.getpwnam.return_value.pw_uid = 1234
            grp_mock.getgrnam.return_value.gr_gid = 5678
            pwd_mock.getpwuid.return_value.pw_dir = "/home/hbot"
            os_mock.path.realpath.return_value = "/opt/hummingbot"
            runner.autofix_permissions(spec)
        return pwd_mock, grp_mock, subprocess_mock, os_mock

    def test_numeric_spec_skips_name_lookups(self):
        pwd_mock, grp_mock, subprocess_mock, os_mock = self._run("501:20")
        pwd_mock.getpwnam.assert_not_called()
        grp_mock.getgrnam.assert_not_called()
        pwd_mock.getpwuid.assert_called_once_with(501)
        os_mock.environ.__setitem__.assert_called_once_with("HOME", "/home/hbot")
        os_mock.setgid.assert_called_once_with(20)
        os_mock.setuid.assert_called_once_with(501)
        cmd = subprocess_mock.run.call_args[0][0]
        self.assertIn("chown -R 501:20", cmd)
        self.assertTrue(subprocess_mock.run.call_args.kwargs["shell"])

    def test_named_spec_resolves_uid_and_gid(self):
        pwd_mock, grp_mock, _, os_mock = self._run("hbot:staff")
        pwd_mock.getpwnam.assert_called_once_with("hbot")
        grp_mock.getgrnam.assert_called_once_with("staff")
        pwd_mock.getpwuid.assert_called_once_with(1234)
        os_mock.setgid.assert_called_once_with(5678)
        os_mock.setuid.assert_called_once_with(1234)


class WaitForGatewayReadyTest(unittest.IsolatedAsyncioTestCase):
    def _make_hb(self, uses_gateway):
        hb = MagicMock()
        hb.trading_core.connector_manager.connectors = {"conn": object()}
        hb.trading_core.gateway_monitor.ready_event.wait = AsyncMock()
        setting = MagicMock()
        setting.uses_gateway_generic_connector.return_value = uses_gateway
        return hb, {"conn": setting}

    async def test_no_gateway_connectors_returns_immediately(self):
        hb, settings = self._make_hb(uses_gateway=False)
        with patch.object(runner.AllConnectorSettings, "get_connector_settings", return_value=settings):
            await runner.wait_for_gateway_ready(hb)
        hb.trading_core.gateway_monitor.ready_event.wait.assert_not_awaited()

    async def test_waits_for_gateway_ready_event(self):
        hb, settings = self._make_hb(uses_gateway=True)
        with patch.object(runner.AllConnectorSettings, "get_connector_settings", return_value=settings):
            await runner.wait_for_gateway_ready(hb)
        hb.trading_core.gateway_monitor.ready_event.wait.assert_awaited_once()

    async def test_timeout_is_logged_and_reraised(self):
        hb, settings = self._make_hb(uses_gateway=True)
        hb.trading_core.gateway_monitor.ready_event.wait = AsyncMock(side_effect=asyncio.TimeoutError)
        with patch.object(runner.AllConnectorSettings, "get_connector_settings", return_value=settings):
            with self.assertRaises(asyncio.TimeoutError):
                await runner.wait_for_gateway_ready(hb)


class LoadAndStartStrategyV2Test(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.conf_dir = Path(self._tmp.name)
        patcher = patch.object(runner, "SCRIPT_STRATEGY_CONF_DIR_PATH", self.conf_dir)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.hb = MagicMock()
        self.hb.trading_core.start_strategy = AsyncMock(return_value=True)

    def _write_conf(self, name, text):
        (self.conf_dir / name).write_text(text)

    async def test_missing_config_file_fails(self):
        self.assertFalse(await runner.load_and_start_strategy(self.hb, v2_conf="nope.yml", headless=True))

    async def test_config_without_script_file_name_fails(self):
        self._write_conf("conf.yml", "other_field: 1\n")
        self.assertFalse(await runner.load_and_start_strategy(self.hb, v2_conf="conf.yml", headless=True))

    async def test_empty_config_file_fails(self):
        self._write_conf("conf.yml", "")
        self.assertFalse(await runner.load_and_start_strategy(self.hb, v2_conf="conf.yml", headless=True))

    async def test_headless_start_success(self):
        self._write_conf("conf.yml", "script_file_name: pmm_simple.py\n")
        self.assertTrue(await runner.load_and_start_strategy(self.hb, v2_conf="conf.yml", headless=True))
        self.assertEqual(self.hb.strategy_file_name, "conf.yml")
        self.assertEqual(self.hb.trading_core.strategy_name, "pmm_simple")
        self.hb.trading_core.start_strategy.assert_awaited_once_with("pmm_simple", "conf.yml", "conf.yml")

    async def test_headless_start_failure(self):
        self._write_conf("conf.yml", "script_file_name: pmm_simple.py\n")
        self.hb.trading_core.start_strategy = AsyncMock(return_value=False)
        self.assertFalse(await runner.load_and_start_strategy(self.hb, v2_conf="conf.yml", headless=True))

    async def test_ui_mode_defers_start_to_listener(self):
        self._write_conf("conf.yml", "script_file_name: pmm_simple.py\n")
        self.assertTrue(await runner.load_and_start_strategy(self.hb, v2_conf="conf.yml", headless=False))
        self.assertEqual(self.hb.script_config, "conf.yml")
        self.hb.trading_core.start_strategy.assert_not_awaited()


class LoadAndStartStrategyV1Test(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.hb = MagicMock()
        self.hb.trading_core.start_strategy = AsyncMock(return_value=True)

    def _patch_loader(self, **kwargs):
        return patch.object(runner, "load_strategy_config_map_from_file", new=AsyncMock(**kwargs))

    async def test_config_file_not_found_fails(self):
        with self._patch_loader(side_effect=FileNotFoundError):
            self.assertFalse(await runner.load_and_start_strategy(
                self.hb, config_file_name="conf_x.yml", headless=True))

    async def test_config_load_error_fails(self):
        with self._patch_loader(side_effect=ValueError("bad yaml")):
            self.assertFalse(await runner.load_and_start_strategy(
                self.hb, config_file_name="conf_x.yml", headless=True))

    async def test_headless_adapter_config_starts_strategy(self):
        config = ClientConfigAdapter(SimpleNamespace(strategy="pure_market_making"))
        with self._patch_loader(return_value=config):
            self.assertTrue(await runner.load_and_start_strategy(
                self.hb, config_file_name="conf_pmm.yml", headless=True))
        self.assertEqual(self.hb.strategy_file_name, "conf_pmm")
        self.assertEqual(self.hb.trading_core.strategy_name, "pure_market_making")
        self.assertIs(self.hb.strategy_config_map, config)
        self.hb.trading_core.start_strategy.assert_awaited_once_with(
            "pure_market_making", config, "conf_pmm.yml")

    async def test_headless_legacy_map_config_starts_strategy(self):
        config = {"strategy": SimpleNamespace(value="cross_exchange_market_making")}
        with self._patch_loader(return_value=config):
            self.assertTrue(await runner.load_and_start_strategy(
                self.hb, config_file_name="conf_xemm.yml", headless=True))
        self.assertEqual(self.hb.trading_core.strategy_name, "cross_exchange_market_making")

    async def test_headless_start_failure(self):
        config = {"strategy": SimpleNamespace(value="pmm")}
        self.hb.trading_core.start_strategy = AsyncMock(return_value=False)
        with self._patch_loader(return_value=config):
            self.assertFalse(await runner.load_and_start_strategy(
                self.hb, config_file_name="conf_pmm.yml", headless=True))

    async def test_ui_mode_incomplete_config_shows_status(self):
        config = {"strategy": SimpleNamespace(value="pmm")}
        with self._patch_loader(return_value=config), \
                patch.object(runner, "all_configs_complete", return_value=False):
            self.assertTrue(await runner.load_and_start_strategy(
                self.hb, config_file_name="conf_pmm.yml", headless=False))
        self.hb.status.assert_called_once()
        self.hb.trading_core.start_strategy.assert_not_awaited()

    async def test_ui_mode_complete_config_skips_status(self):
        config = {"strategy": SimpleNamespace(value="pmm")}
        with self._patch_loader(return_value=config), \
                patch.object(runner, "all_configs_complete", return_value=True):
            self.assertTrue(await runner.load_and_start_strategy(
                self.hb, config_file_name="conf_pmm.yml", headless=False))
        self.hb.status.assert_not_called()

    async def test_no_config_and_no_v2_conf_is_a_noop_success(self):
        self.assertTrue(await runner.load_and_start_strategy(self.hb, headless=True))
        self.hb.trading_core.start_strategy.assert_not_awaited()


class BootstrapApplicationTest(unittest.IsolatedAsyncioTestCase):
    """All deferred imports (init_logging, yml helpers, Security) are patched at their source
    modules; no real login, decryption, file writes, or logging re-init happens."""

    def _patches(self, login_ok=True):
        security = MagicMock()
        security.login.return_value = login_ok
        security.wait_til_decryption_done = AsyncMock()
        return (
            patch("hummingbot.init_logging"),
            patch("hummingbot.client.config.config_helpers.create_yml_files_legacy", new=AsyncMock()),
            patch("hummingbot.client.config.config_helpers.read_system_configs_from_yml", new=AsyncMock()),
            patch("hummingbot.client.config.security.Security", security),
            patch.object(runner, "silence_console_handlers"),
            patch.object(runner.AllConnectorSettings, "initialize_paper_trade_settings"),
            patch.object(runner.HummingbotApplication, "main_application"),
        )

    def _make_config_map(self):
        config_map = MagicMock()
        config_map.mqtt_bridge.mqtt_autostart = False
        return config_map

    async def test_bad_password_returns_none(self):
        patches = self._patches(login_ok=False)
        config_map = self._make_config_map()
        with patches[0] as init_logging, patches[1], patches[2], patches[3], \
                patches[4], patches[5], patches[6]:
            app = await runner.bootstrap_application(config_map, MagicMock())
        self.assertIsNone(app)
        init_logging.assert_not_called()

    async def test_default_boot_sequence(self):
        patches = self._patches()
        config_map = self._make_config_map()
        with patches[0] as init_logging, patches[1] as create_yml, patches[2] as read_configs, \
                patches[3], patches[4] as silence, patches[5] as init_paper, patches[6] as main_app:
            app = await runner.bootstrap_application(
                config_map, MagicMock(), strategy_file_name="mybot", override_log_level="DEBUG")
        self.assertIs(app, main_app.return_value)
        init_logging.assert_called_once_with(
            "hummingbot_logs.yml", config_map, override_log_level="DEBUG", strategy_file_path="mybot")
        create_yml.assert_awaited_once()
        read_configs.assert_awaited_once()
        silence.assert_not_called()
        self.assertFalse(config_map.mqtt_bridge.mqtt_autostart)
        init_paper.assert_called_once_with(config_map.paper_trade.paper_trade_exchanges)
        main_app.assert_called_once_with(client_config_map=config_map, headless_mode=False)

    async def test_headless_silenced_mqtt_boot(self):
        patches = self._patches()
        config_map = self._make_config_map()
        with patches[0], patches[1], patches[2], patches[3], \
                patches[4] as silence, patches[5], patches[6] as main_app:
            app = await runner.bootstrap_application(
                config_map, MagicMock(), headless=True, mqtt_autostart=True, silence_console=True)
        self.assertIs(app, main_app.return_value)
        silence.assert_called_once()
        self.assertTrue(config_map.mqtt_bridge.mqtt_autostart)
        main_app.assert_called_once_with(client_config_map=config_map, headless_mode=True)


class SilenceConsoleHandlersTest(unittest.TestCase):
    def test_removes_console_handlers_but_keeps_file_like_handlers(self):
        logger = logging.getLogger("test_runner.silence.dummy")
        stdout_handler = logging.StreamHandler(sys.stdout)
        stderr_handler = logging.StreamHandler(sys.stderr)
        cli_handler = CLIHandler(io.StringIO())  # CLIHandler is dropped regardless of stream
        kept_handler = logging.StreamHandler(io.StringIO())
        # snapshot every logger's handlers: the function walks the whole logger tree
        all_loggers = [logging.getLogger()] + [
            logging.getLogger(n) for n in list(logging.root.manager.loggerDict)]
        saved = [(lg, list(getattr(lg, "handlers", []))) for lg in all_loggers]
        for h in (stdout_handler, stderr_handler, cli_handler, kept_handler):
            logger.addHandler(h)
        try:
            runner.silence_console_handlers()
            self.assertNotIn(stdout_handler, logger.handlers)
            self.assertNotIn(stderr_handler, logger.handlers)
            self.assertNotIn(cli_handler, logger.handlers)
            self.assertIn(kept_handler, logger.handlers)
        finally:
            for lg, handlers in saved:
                lg.handlers = handlers
            logger.handlers = []


if __name__ == "__main__":
    unittest.main()
