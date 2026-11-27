"""Hermetic strategy contracts. All numbers here are explicitly test fixtures."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

CORE = Path(__file__).resolve().parents[4] / "scripts/hk_strategy_core.py"
spec = importlib.util.spec_from_file_location("_hk6220_core", CORE)
core = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = core
spec.loader.exec_module(core)

T = 1794000000.0


def fixture():
    return {"ok": True, "symbol": "BTCUSDT", "tier": "delayed", "delay_sec": 7200,
            "as_of": T - 7200, "as_of_iso": "fixture", "age_sec": 7200,
            "mark": {"price": 100, "basis": "delayed_snapshot"},
            "nearest": {"below": {"price": 98, "usd": 500, "side": "long"},
                        "above": {"price": 103, "usd": 600, "side": "short"}},
            "walls": [{"evidence": "unmeasured"}], "truth": {"fixture": True}, "record": {"fixture": True}}


class TestPointInTimeInputs(unittest.TestCase):
    def test_preserves_snapshot_time_delay_and_unmeasured_source(self):
        payload = fixture()
        snapshot = core.parse_snapshot(payload, T, "BTCUSDT")
        self.assertEqual(snapshot.as_of, T - 7200)
        self.assertEqual(snapshot.available_at, T)
        self.assertEqual(snapshot.payload, payload)
        payload["walls"][0]["evidence"] = "changed"
        self.assertEqual(snapshot.payload["walls"][0]["evidence"], "unmeasured")

    def test_missing_time_or_false_delay_cannot_become_a_trade(self):
        for field, value in [("as_of", None), ("as_of", T), ("delay_sec", 0),
                             ("delay_sec", True), ("tier", "unknown"), ("symbol", "ETHUSDT")]:
            with self.subTest(field=field, value=value):
                payload = fixture()
                payload[field] = value
                with self.assertRaises(ValueError):
                    core.parse_snapshot(payload, T, "BTCUSDT")

    def test_live_and_delayed_have_distinct_times(self):
        payload = fixture()
        payload.update(tier="live", as_of=T - 2, delay_sec=0)
        snapshot = core.parse_snapshot(payload, T, "BTCUSDT")
        self.assertTrue(snapshot.usable_at(T + 1))
        self.assertEqual(snapshot.tier, "live")

    def test_empty_nearest_pair_remains_empty(self):
        payload = fixture()
        payload["nearest"] = {"below": None, "above": None}
        snapshot = core.parse_snapshot(payload, T, "BTCUSDT")
        self.assertIsNone(snapshot.long_plan(100, T))

    def test_wrong_side_and_nonfinite_values_rejected(self):
        for key, value in [("price", 104), ("price", float("nan")), ("usd", 0), ("side", "short")]:
            with self.subTest(key=key, value=value):
                payload = fixture()
                payload["nearest"]["below"][key] = value
                with self.assertRaises(ValueError):
                    core.parse_snapshot(payload, T, "BTCUSDT")

    def test_never_reads_a_future_receipt_or_forward_fills_expired_data(self):
        timeline = core.Timeline()
        timeline.append(T, core.parse_snapshot(fixture(), T, "BTCUSDT"))
        self.assertIsNone(timeline.at(T - 0.01))
        self.assertEqual(timeline.at(T).below, 98)
        self.assertIsNone(timeline.at(T + 901))

    def test_old_snapshot_does_not_get_freshened_by_a_new_receipt(self):
        payload = fixture()
        payload["as_of"] = T - 10000
        snapshot = core.parse_snapshot(payload, T, "BTCUSDT")
        self.assertFalse(snapshot.usable_at(T))

    def test_error_receipt_cuts_off_the_last_success(self):
        timeline = core.Timeline()
        timeline.append(T, core.parse_snapshot(fixture(), T, "BTCUSDT"))
        timeline.append(T + 60, None)
        self.assertIsNotNone(timeline.at(T + 59))
        self.assertIsNone(timeline.at(T + 60))

    def test_duplicate_or_unsorted_receipts_fail_instead_of_sorting_history(self):
        timeline = core.Timeline()
        timeline.append(T, None)
        for stamp in (T, T - 1):
            with self.assertRaises(ValueError):
                timeline.append(stamp, None)

    def test_replay_loads_exact_source_and_error_gaps(self):
        rows = [{"received_at": T, "payload": fixture()}, {"received_at": T + 60, "error": "HTTP 429"}]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "fixture.jsonl"
            path.write_text("\n".join(json.dumps(row) for row in rows))
            timeline = core.Timeline.read(path)
            self.assertIsNotNone(timeline.at(T))
            self.assertIsNone(timeline.at(T + 61))

    def test_long_plan_uses_the_pair_and_keeps_it_in_a_frozen_tag(self):
        snapshot = core.parse_snapshot(fixture(), T, "BTCUSDT")
        plan = snapshot.long_plan(100, T)
        self.assertEqual((plan.stop, plan.target), (98, 103))
        self.assertEqual(core.LongPlan.from_tag(plan.tag()), plan)
        self.assertIsNone(snapshot.long_plan(102, T))  # Fixed reward/risk rule.
        self.assertIsNone(snapshot.long_plan(97, T))
        self.assertIsNone(snapshot.long_plan(104, T))
        self.assertIsNone(snapshot.long_plan(100, T - 1))

    def test_bad_tags_are_not_new_exit_estimates(self):
        for tag in (None, "", "hk:nan:103:4", "hk:104:98:4", "foreign:98:103:4"):
            self.assertIsNone(core.LongPlan.from_tag(tag))

    def test_grid_inventory_and_quote_budget_are_bounded(self):
        plan = core.LongPlan(98, 103, T)
        quotes = core.grid_quotes(plan, 100, 0.25)
        bids = [(price, amount) for side, price, amount in quotes if side == "buy"]
        asks = [(price, amount) for side, price, amount in quotes if side == "sell"]
        self.assertAlmostEqual(sum(price * amount for price, amount in bids), 75)
        self.assertAlmostEqual(sum(amount for price, amount in asks), 0.25)
        self.assertTrue(all(98 < price < 100 for price, amount in bids))
        self.assertTrue(all(100 < price < 103 for price, amount in asks))
        self.assertEqual(core.grid_quotes(plan, 97, 0.25), [])
        self.assertEqual(core.grid_quotes(plan, 104, 0.25), [])
        full = core.grid_quotes(plan, 100, 1.0)
        self.assertFalse(any(side == "buy" for side, price, amount in full))

    def test_http_completion_time_is_first_availability_and_key_is_explicit(self):
        seen = []
        def fetch(symbol, **kwargs):
            seen.append((symbol, kwargs))
            return fixture()
        feed = core.LevelsFeed(fetch=fetch, clock=lambda: T + 10, probe=True)
        feed.poll(T)
        feed.poll(T + 30)
        self.assertIsNone(feed.timeline.at(T + 9))
        self.assertIsNotNone(feed.timeline.at(T + 10))
        self.assertEqual(seen, [("BTCUSDT", {"key": None, "probe": True})])

    def test_auth_rate_and_availability_errors_never_turn_into_empty_success(self):
        class Failure(RuntimeError):
            status = 429
        now = [T]
        def fail(*args, **kwargs):
            raise Failure("fixture text is not logged")
        feed = core.LevelsFeed(fetch=lambda *a, **k: fixture(), clock=lambda: now[0])
        feed.poll(T)
        now[0] += 60
        feed.fetch = fail
        feed.poll(T + 60)
        self.assertEqual(feed.last_error, "HTTP 429")
        self.assertIsNone(feed.timeline.at(T + 60))
        self.assertIsNotNone(feed.timeline.at(T + 59))

    def test_shared_keyed_transport_rejects_redirect_before_a_second_request(self):
        import hunterkiller_langchain as client
        request = urllib.request.Request("https://hunterkiller.io/api/v1/levels/BTCUSDT",
                                         headers={"Authorization": "Bearer fixture-only"})
        handler = client._NoRedirect()
        self.assertIsNone(handler.redirect_request(request, None, 302, "fixture", {}, "https://other.invalid"))
        with patch.object(client.urllib.request, "build_opener") as builder:
            builder.return_value.open.side_effect = urllib.error.HTTPError(
                request.full_url, 302, "fixture redirect", {}, None)
            with self.assertRaises(client.HunterKillerError) as error:
                client.get_levels("BTCUSDT", key="fixture-only")
            self.assertEqual(error.exception.status, 302)
            builder.return_value.open.assert_called_once()
            self.assertIsInstance(builder.call_args.args[0], client._NoRedirect)

    def test_proxy_requires_explicit_opt_in_and_never_invents_api_snapshot_time(self):
        row = {"kind": core.PUBLICATION_PROXY, "symbol": "BTCUSDT", "received_at": T,
               "snapshot_as_of": None, "delay_sec": None, "mark": 100,
               "source": {"viewer": "free"}, "nearest": fixture()["nearest"]}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "fixture.jsonl"
            path.write_text(json.dumps(row) + "\n")
            with self.assertRaisesRegex(ValueError, "explicit opt in"):
                core.Timeline.read(path)
            timeline = core.Timeline.read(path, allow_publication_proxy=True)
            sample = timeline.at(T)
            self.assertIsNone(sample.as_of)
            self.assertIsNone(sample.delay_sec)
            self.assertEqual(sample.tier, core.PUBLICATION_PROXY)
            self.assertIsNotNone(sample.long_plan(100, T))
            self.assertIsNone(timeline.at(T + 901))

    def test_clock_regression_invalidates_the_live_cache(self):
        now = [T]
        feed = core.LevelsFeed(fetch=lambda *a, **k: fixture(), clock=lambda: now[0])
        feed.poll(T)
        now[0] = T - 1
        feed.poll(T + 60)
        self.assertIsNone(feed.timeline.at(T))
        self.assertIsNotNone(feed.last_error)


if __name__ == "__main__":
    unittest.main()
