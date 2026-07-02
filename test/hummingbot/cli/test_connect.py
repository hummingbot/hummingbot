import asyncio
import io
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import typer

from hummingbot.cli.commands.connect import (
    _collect_key_values,
    _connect_key_fields,
    _connectable_exchanges,
    _prompt_text,
    connect,
)
from hummingbot.cli.output import ExitCode
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.client.settings import AllConnectorSettings


def _field(attr, secure=False, prompt="enter"):
    """A fake connect-key field (attr + client_field_data), enough for the connect helpers."""
    return SimpleNamespace(
        attr=attr,
        client_field_data=SimpleNamespace(is_connect_key=True, is_secure=secure, prompt=prompt))


class _RejectingCfg:
    """A fake connector config adapter whose setattr always rejects the value."""

    def __init__(self, fields):
        object.__setattr__(self, "_fields", fields)

    def traverse(self, secure=True):
        return list(self._fields)

    def __setattr__(self, name, value):
        raise ValueError("rejected")


class ConnectFieldsTest(unittest.TestCase):
    def test_connectable_exchanges_includes_cex_excludes_gateway(self):
        exchanges = _connectable_exchanges()
        self.assertIn("binance", exchanges)
        # gateway/ethereum-wallet connectors are excluded
        self.assertTrue(all("uniswap" not in e for e in exchanges))

    def test_binance_connect_key_fields(self):
        cfg = ClientConfigAdapter(AllConnectorSettings.get_connector_config_keys("binance"))
        fields = _connect_key_fields(cfg)
        attrs = [f.attr for f in fields]
        self.assertIn("binance_api_key", attrs)
        self.assertIn("binance_api_secret", attrs)
        # the connector-name field is not a connect key
        self.assertNotIn("connector", attrs)
        # api credentials are marked secret (hidden prompts / encrypted)
        self.assertTrue(all(f.client_field_data.is_secure for f in fields))

    def test_prompt_text_resolves_callable(self):
        cfg = ClientConfigAdapter(AllConnectorSettings.get_connector_config_keys("binance"))
        field = next(f for f in _connect_key_fields(cfg) if f.attr == "binance_api_key")
        self.assertIn("API key", _prompt_text(field, cfg))

    def test_prompt_text_callable_raising_falls_back_to_attr(self):
        field = _field("api_key", prompt=lambda hb_config: 1 / 0)
        self.assertEqual(_prompt_text(field, SimpleNamespace(hb_config=None)), "api_key")

    def test_prompt_text_none_falls_back_to_attr(self):
        field = _field("api_key", prompt=None)
        self.assertEqual(_prompt_text(field, SimpleNamespace(hb_config=None)), "api_key")

    def test_collect_key_values_prompts_secure_and_plain(self):
        fields = [_field("api_key", secure=True), _field("subaccount", secure=False)]
        with patch("sys.stdin.isatty", return_value=True), \
                patch("getpass.getpass", return_value="sec"), \
                patch("builtins.input", return_value="plain"):
            values = _collect_key_values(fields, SimpleNamespace(hb_config=None), keys_stdin=False)
        self.assertEqual(values, {"api_key": "sec", "subaccount": "plain"})


class ConnectCommandTest(unittest.TestCase):
    """End-to-end runs of the `connect` command with Security / settings / network faked."""

    def setUp(self) -> None:
        patch("hummingbot.cli.commands.connect._connectable_exchanges",
              return_value=["binance", "kraken"]).start()
        self.security = patch("hummingbot.client.config.security.Security").start()
        self.security.connector_config_file_exists.return_value = False
        self.login = patch("hummingbot.cli.commands.connect.login").start()
        self.ccm = SimpleNamespace(commands_timeout=SimpleNamespace(other_commands_timeout=1))
        patch("hummingbot.client.config.config_helpers.load_client_config_map_from_file",
              return_value=self.ccm).start()
        self.addCleanup(patch.stopall)

    def _run(self, connector=None, **kw) -> str:
        args = dict(keys_stdin=False, replace=False, show_fields=False, show_all=False,
                    password_stdin=False)
        args.update(kw)
        buf = io.StringIO()
        with redirect_stdout(buf):
            connect(connector, **args)
        return buf.getvalue()

    def _fail(self, connector=None, **kw) -> int:
        with redirect_stdout(io.StringIO()):
            with self.assertRaises(typer.Exit) as ctx:
                self._run(connector, **kw)
        return ctx.exception.exit_code

    # -- listing --

    def test_all_lists_static_checklist(self):
        self.security.connector_config_file_exists.side_effect = lambda n: n == "binance"
        out = self._run(show_all=True)
        self.assertIn("connectable connectors", out)
        self.assertIn("| binance | yes |", out)
        self.assertIn("| kraken | no |", out)

    def test_no_arg_none_connected(self):
        out = self._run()
        self.assertIn("No connectors connected", out)

    def test_no_arg_tests_connected_keys(self):
        self.security.connector_config_file_exists.side_effect = lambda n: True
        self.security.login.return_value = True
        ub = SimpleNamespace(update_exchanges=AsyncMock(return_value={"kraken": "bad api key"}))
        with patch("hummingbot.cli.commands.connect.resolve_password", return_value="pw"), \
                patch("hummingbot.client.config.config_crypt.ETHKeyFileSecretManger"), \
                patch("hummingbot.user.user_balances.UserBalances") as ub_cls:
            ub_cls.instance.return_value = ub
            out = self._run()
        self.assertIn("connections", out)
        self.assertIn("| binance | yes | yes |", out)         # confirmed, no error
        self.assertIn("| kraken | yes | no | bad api key |", out)

    def test_no_arg_invalid_password(self):
        self.security.connector_config_file_exists.side_effect = lambda n: True
        self.security.login.return_value = False
        with patch("hummingbot.cli.commands.connect.resolve_password", return_value="pw"), \
                patch("hummingbot.client.config.config_crypt.ETHKeyFileSecretManger"):
            code = self._fail()
        self.assertEqual(code, int(ExitCode.CONFIG_ERROR))

    def test_no_arg_network_timeout(self):
        self.security.connector_config_file_exists.side_effect = lambda n: True
        self.security.login.return_value = True
        ub = SimpleNamespace(update_exchanges=AsyncMock(side_effect=asyncio.TimeoutError))
        with patch("hummingbot.cli.commands.connect.resolve_password", return_value="pw"), \
                patch("hummingbot.client.config.config_crypt.ETHKeyFileSecretManger"), \
                patch("hummingbot.user.user_balances.UserBalances") as ub_cls:
            ub_cls.instance.return_value = ub
            code = self._fail()
        self.assertEqual(code, int(ExitCode.TIMEOUT))

    # -- adding keys --

    def test_unknown_connector_fails(self):
        code = self._fail("nope")
        self.assertEqual(code, int(ExitCode.CONFIG_ERROR))

    def test_connector_without_api_keys_fails(self):
        with patch("hummingbot.client.settings.AllConnectorSettings") as acs:
            acs.get_connector_config_keys.return_value = None
            code = self._fail("binance")
        self.assertEqual(code, int(ExitCode.CONFIG_ERROR))

    def test_fields_lists_key_fields(self):
        out = self._run("binance", show_fields=True)
        self.assertIn("key fields for binance", out)
        self.assertIn("binance_api_key", out)
        self.assertIn("binance_api_secret", out)
        self.security.update_secure_config.assert_not_called()

    def test_existing_keys_require_replace(self):
        self.security.connector_config_file_exists.return_value = True
        code = self._fail("binance")
        self.assertEqual(code, int(ExitCode.CONFIG_ERROR))

    def test_add_keys_from_stdin(self):
        with patch("hummingbot.cli.commands._common.read_json_object_from_stdin",
                   return_value={"binance_api_key": "k", "binance_api_secret": "s"}):
            out = self._run("binance", keys_stdin=True)
        self.assertIn("binance_api_key, binance_api_secret", out)
        self.login.assert_called_once_with(password_stdin=False)
        self.security.update_secure_config.assert_called_once()

    def test_add_keys_replace_existing(self):
        self.security.connector_config_file_exists.return_value = True
        with patch("hummingbot.cli.commands._common.read_json_object_from_stdin",
                   return_value={"binance_api_key": "k", "binance_api_secret": "s"}):
            self._run("binance", keys_stdin=True, replace=True)
        self.security.update_secure_config.assert_called_once()

    def test_add_keys_stdin_missing_fields_fails(self):
        with patch("hummingbot.cli.commands._common.read_json_object_from_stdin",
                   return_value={"binance_api_key": "k"}):
            code = self._fail("binance", keys_stdin=True)
        self.assertEqual(code, int(ExitCode.CONFIG_ERROR))
        self.security.update_secure_config.assert_not_called()

    def test_add_keys_via_tty_prompts(self):
        with patch("sys.stdin.isatty", return_value=True), \
                patch("getpass.getpass", side_effect=["k", "s"]):
            out = self._run("binance")
        self.assertIn("connect", out)
        self.security.update_secure_config.assert_called_once()

    def test_rejected_key_value_fails(self):
        cfg = _RejectingCfg([_field("api_key", secure=True)])
        with patch("hummingbot.client.settings.AllConnectorSettings") as acs, \
                patch("hummingbot.client.config.config_helpers.ClientConfigAdapter", return_value=cfg), \
                patch("hummingbot.cli.commands._common.read_json_object_from_stdin",
                      return_value={"api_key": "k"}):
            acs.get_connector_config_keys.return_value = object()
            code = self._fail("binance", keys_stdin=True)
        self.assertEqual(code, int(ExitCode.CONFIG_ERROR))
        self.security.update_secure_config.assert_not_called()


if __name__ == "__main__":
    unittest.main()
