"""Unit tests for the repo-root MCP server (mcp_server.py) — a thin wrapper over `hbot`.

The `mcp` package is not part of the hummingbot conda env (the server runs under
`uv run --with mcp`), so the whole module is skipped when it isn't importable.
Every test drives the real subprocess boundary against a stub `hbot` executable
that records its argv/stdin and plays back a scripted exit code and output.
"""
import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path

import pytest

pytest.importorskip("mcp")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import mcp_server  # noqa: E402

STUB = """#!/bin/sh
# Stub hbot: record how we were called, then play back the scripted reply.
printf '%s\\n' "$@" > "$STUB_DIR/argv"
cat > "$STUB_DIR/stdin"
cat "$STUB_DIR/reply_stdout" 2>/dev/null
cat "$STUB_DIR/reply_stderr" 1>&2 2>/dev/null
exit $(cat "$STUB_DIR/reply_exit" 2>/dev/null || echo 0)
"""


class MCPServerStubTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        stub_dir = Path(self.dir.name)
        stub = stub_dir / "hbot"
        stub.write_text(STUB)
        stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
        os.environ["HBOT_BIN"] = str(stub)
        os.environ["STUB_DIR"] = str(stub_dir)
        self.stub_dir = stub_dir

    def tearDown(self):
        os.environ.pop("HBOT_BIN", None)
        os.environ.pop("STUB_DIR", None)
        self.dir.cleanup()

    def script(self, stdout="", stderr="", exit_code=0):
        (self.stub_dir / "reply_stdout").write_text(stdout)
        (self.stub_dir / "reply_stderr").write_text(stderr)
        (self.stub_dir / "reply_exit").write_text(str(exit_code))

    def argv(self):
        return (self.stub_dir / "argv").read_text().splitlines()

    def stdin(self):
        return (self.stub_dir / "stdin").read_text()

    # ── result mapping ──────────────────────────────────────────────────

    def test_json_command_parses_data(self):
        self.script(stdout='{"running": true, "pid": 42}')
        result = mcp_server.status()
        self.assertEqual(self.argv(), ["status", "--json"])
        self.assertTrue(result["ok"])
        self.assertEqual(result["exit_status"], "SUCCESS")
        self.assertEqual(result["data"], {"running": True, "pid": 42})
        self.assertIsNone(result["output"])
        self.assertIsNone(result["error"])

    def test_markdown_command_returns_output_verbatim(self):
        self.script(stdout="## connections\n\n| connector |\n")
        result = mcp_server.connections()
        self.assertEqual(self.argv(), ["connect"])
        self.assertTrue(result["ok"])
        self.assertIsNone(result["data"])
        self.assertIn("## connections", result["output"])

    def test_exit_codes_map_to_cli_contract(self):
        for code, name in [(1, "ERROR"), (2, "NOT_FOUND"), (3, "NOT_RUNNING"),
                           (4, "CONFIG_ERROR"), (5, "TIMEOUT"), (86, "UNKNOWN")]:
            self.script(stderr=f"Error: boom (code {code})", exit_code=code)
            result = mcp_server.status()
            self.assertFalse(result["ok"])
            self.assertEqual(result["exit_code"], code)
            self.assertEqual(result["exit_status"], name)
            self.assertIn("boom", result["error"])

    def test_unparseable_json_falls_back_to_output(self):
        self.script(stdout="not json")
        result = mcp_server.status()
        self.assertTrue(result["ok"])
        self.assertIsNone(result["data"])
        self.assertEqual(result["output"], "not json")

    def test_hung_cli_reports_client_timeout(self):
        stub = self.stub_dir / "hbot"
        stub.write_text("#!/bin/sh\nsleep 30\n")
        old = (mcp_server.SUBPROCESS_TIMEOUT, mcp_server.TIMEOUT_SLACK)
        mcp_server.SUBPROCESS_TIMEOUT, mcp_server.TIMEOUT_SLACK = 1, 0
        try:
            result = mcp_server.status()
        finally:
            mcp_server.SUBPROCESS_TIMEOUT, mcp_server.TIMEOUT_SLACK = old
        self.assertFalse(result["ok"])
        self.assertEqual(result["exit_status"], "CLIENT_TIMEOUT")
        self.assertIn("did not return within 1s", result["error"])

    def test_missing_binary_reports_no_cli(self):
        os.environ["HBOT_BIN"] = str(self.stub_dir / "does-not-exist")
        result = mcp_server.status()
        self.assertFalse(result["ok"])
        self.assertEqual(result["exit_status"], "NO_CLI")
        self.assertIn("HBOT_BIN", result["error"])

    # ── argv construction per tool ──────────────────────────────────────

    def test_deploy_sends_values_via_stdin(self):
        self.script(stdout="{}")
        mcp_server.deploy("pmm_simple", values={"trading_pair": "ETH-USD"},
                          name="conf_eth.yml", replace=True, timeout=60)
        self.assertEqual(self.argv(), [
            "deploy", "pmm_simple", "--values-stdin", "--timeout", "60",
            "--name", "conf_eth.yml", "--replace", "--json",
        ])
        self.assertEqual(json.loads(self.stdin()), {"trading_pair": "ETH-USD"})

    def test_create_with_defaults(self):
        self.script(stdout="- created: x")
        mcp_server.create("pmm_simple", name="conf_x.yml", with_defaults=True)
        self.assertEqual(self.argv(), ["create", "pmm_simple", "--name", "conf_x.yml", "--with-defaults"])
        self.assertEqual(self.stdin(), "")

    def test_start_stop_logs_history_config(self):
        self.script(stdout="{}")
        mcp_server.start("conf_x.yml", replace=True)
        self.assertEqual(self.argv(), ["start", "conf_x.yml", "--timeout", "120.0", "--replace", "--json"])
        mcp_server.stop(force=True, timeout=10)
        self.assertEqual(self.argv(), ["stop", "--timeout", "10", "--force", "--json"])
        mcp_server.logs(name="conf_old", lines=25)
        self.assertEqual(self.argv(), ["logs", "conf_old", "--lines", "25", "--json"])
        mcp_server.history(name="conf_old", days=7)
        self.assertEqual(self.argv(), ["history", "conf_old", "--days", "7"])
        mcp_server.config("total_amount_quote", "250")
        self.assertEqual(self.argv(), ["config", "total_amount_quote", "250", "--json"])
        mcp_server.balance(units_only=True)
        self.assertEqual(self.argv(), ["balance", "--units-only", "--json"])

    def test_connections_variants(self):
        self.script(stdout="x")
        mcp_server.connections(show_all=True)
        self.assertEqual(self.argv(), ["connect", "--all"])
        mcp_server.connections(connector="binance", show_fields=True)
        self.assertEqual(self.argv(), ["connect", "binance", "--fields"])
        # A connector alone implies the fields listing — never the interactive key-entry path.
        mcp_server.connections(connector="binance")
        self.assertEqual(self.argv(), ["connect", "binance", "--fields"])
        mcp_server.import_config("conf_x.yml")
        self.assertEqual(self.argv(), ["import", "conf_x.yml"])

    def test_config_type_maps_to_the_cli_disambiguation_flag(self):
        self.script(stdout="x")
        mcp_server.import_config("conf_x.yml", config_type="controller")
        self.assertEqual(self.argv(), ["import", "conf_x.yml", "--controller"])
        mcp_server.start("conf_x.yml", config_type="v2-script")
        self.assertEqual(self.argv(), ["start", "conf_x.yml", "--v2-script", "--timeout", "120.0", "--json"])
        mcp_server.deploy("conf_x.yml", config_type="v1-strategy")
        self.assertEqual(self.argv(),
                         ["deploy", "conf_x.yml", "--v1-strategy", "--timeout", "120.0", "--json"])
        mcp_server.create("pmm_simple", config_type="controller")
        self.assertEqual(self.argv(), ["create", "pmm_simple", "--controller"])

    def test_invalid_config_type_fails_client_side(self):
        result = mcp_server.import_config("conf_x.yml", config_type="script")
        self.assertFalse(result["ok"])
        self.assertEqual(result["exit_status"], "BAD_ARGUMENT")
        self.assertIn("v2-script", result["error"])
        self.assertFalse((self.stub_dir / "argv").exists(), "hbot must not be invoked")

    # ── surface & secrets policy ────────────────────────────────────────

    def test_no_tool_accepts_secrets(self):
        """No tool parameter may carry a password or API key — that is the contract."""
        import asyncio
        tools = asyncio.run(mcp_server.mcp.list_tools())
        names = {t.name for t in tools}
        self.assertEqual(names, {
            "connections", "balance", "create", "import_config", "config",
            "deploy", "start", "stop", "status", "logs", "history",
        })
        for tool in tools:
            for param in tool.inputSchema.get("properties", {}):
                for banned in ("password", "secret", "api_key", "private_key"):
                    self.assertNotIn(banned, param.lower(), f"{tool.name}.{param}")


if __name__ == "__main__":
    unittest.main()
