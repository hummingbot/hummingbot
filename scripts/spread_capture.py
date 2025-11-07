
from __future__ import annotations

import glob
import json
import os
import time
import urllib.parse
import urllib.request
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, ClassVar, Dict, List, Optional, Tuple

try:
    import yaml
except Exception:
    yaml = None

from pydantic import Field
from sqlalchemy.orm import Session, sessionmaker

from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.model import HummingbotBase
from hummingbot.model.spread_samples import SpreadSample
from hummingbot.strategy.strategy_v2_base import StrategyV2Base, StrategyV2ConfigBase


class SpreadSamplerConfig(StrategyV2ConfigBase):
    """
    Generic config for the spread sampler. Accepts connector/exchange aliases.
    quote is a list of quotes to include (e.g. ["USDT", "BUSD"]). Backwards-compatible with a single string.
    """
    script_file_name: str = __file__

    connector_name: Optional[str] = Field(None, description="Primary connector/exchange name (e.g., binance).")
    exchange: Optional[str] = Field(None, description="Alias for connector_name.")
    connector: Optional[str] = Field(None, description="Alias for connector_name.")
    quote: List[str] = Field(default_factory=lambda: ["USDT"], description="List of quote assets to filter trading pairs (e.g., ['USDT']).")
    snapshot_interval_min: int = Field(default=15, description="Snapshot interval in minutes.")
    averaging_window_hours: int = Field(default=24, description="Averaging window in hours.")
    averaging_window_min: Optional[int] = Field(default=None, description="Optional averaging window in minutes.")
    markets: Dict[str, set] = Field(default_factory=dict)
    candles_config: List[CandlesConfig] = Field(default_factory=list)


def _find_saved_script_yaml(base_name: str) -> Optional[str]:
    candidates = []
    cwd = os.getcwd()
    candidates += glob.glob(os.path.join(cwd, "conf", "scripts", f"conf_{base_name}*.yml"))
    candidates += glob.glob(os.path.join(cwd, "conf", "strategies", f"{base_name}.yml"))
    project_root = os.path.dirname(os.path.dirname(cwd))
    candidates += glob.glob(os.path.join(project_root, "conf", "scripts", f"conf_{base_name}*.yml"))
    candidates += glob.glob(os.path.join(project_root, "conf", "strategies", f"{base_name}.yml"))
    home = os.path.expanduser("~")
    candidates += glob.glob(os.path.join(home, ".hummingbot", "conf", "scripts", f"conf_{base_name}*.yml"))
    candidates += glob.glob(os.path.join(home, ".hummingbot", "conf", "strategies", f"{base_name}.yml"))
    for p in candidates:
        if os.path.isfile(p):
            return p
    return None


def _load_yaml_as_dict(path: str) -> Optional[dict]:
    if not path or not os.path.isfile(path):
        return None
    if yaml is None:
        data: Dict[str, Any] = {}
        with open(path, "r") as f:
            key = None
            for raw in f:
                line = raw.rstrip("\n")
                if not line.strip() or line.strip().startswith("#"):
                    continue
                if line.lstrip().startswith("-"):
                    if key is None:
                        continue
                    item = line.lstrip().lstrip("-").strip()
                    if isinstance(data.get(key), list):
                        data[key].append(item.strip('"').strip("'"))
                    else:
                        data[key] = [item.strip('"').strip("'")]
                    continue
                if ":" not in line:
                    continue
                k, v = line.split(":", 1)
                key = k.strip()
                val = v.strip()
                if val == "":
                    data[key] = []
                else:
                    if val.lower() in ("null", "none"):
                        data[key] = None
                    elif val.lower() in ("true", "false"):
                        data[key] = val.lower() == "true"
                    else:
                        if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                            data[key] = val[1:-1]
                        else:
                            try:
                                data[key] = int(val)
                            except Exception:
                                data[key] = val
        return data
    try:
        with open(path, "r") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return None


class SpreadSampler(StrategyV2Base):
    markets: ClassVar[Dict[str, set]] = {}

    def __init__(self, *args, **kwargs):
        connectors = kwargs.get("connectors", None)
        config_in = kwargs.get("config", None)

        if config_in is None and len(args) >= 1:
            if len(args) >= 2:
                connectors = connectors or args[0]
                config_in = config_in or args[1]
            else:
                single = args[0]
                if isinstance(single, (dict, SpreadSamplerConfig)):
                    config_in = single
                else:
                    connectors = single

        if connectors is None:
            connectors = {}
        if not isinstance(connectors, dict):
            try:
                connectors = dict(connectors)
            except Exception:
                connectors = {}

        # produce normalized configuration object
        config_obj = None

        def _normalize_data(d: dict) -> dict:
            out = dict(d)
            # connector_name from aliases
            if "connector_name" not in out or not out.get("connector_name"):
                for alias in ("exchange", "connector"):
                    if alias in out and out.get(alias):
                        out["connector_name"] = out.get(alias)
                        break
            # normalize quote to list uppercase
            q = out.get("quote", None)
            if isinstance(q, str):
                out["quote"] = [q.strip().upper()]
            elif isinstance(q, (list, tuple, set)):
                out["quote"] = [str(x).strip().upper() for x in q if x is not None]
            else:
                out["quote"] = ["USDT"]
            # normalize markets values to lists of normalized pairs (BASE-QUOTE)
            mk = out.get("markets", {}) or {}
            norm_markets: Dict[str, List[str]] = {}
            for k, v in mk.items():
                items: List[str] = []
                if isinstance(v, (list, tuple, set)):
                    seq = v
                elif v is None:
                    seq = []
                else:
                    seq = [v]
                for it in seq:
                    if not isinstance(it, str):
                        continue
                    p = it.replace("/", "-").replace("_", "-").upper()
                    items.append(p)
                norm_markets[k] = items
            out["markets"] = norm_markets
            return out

        try:
            if isinstance(config_in, SpreadSamplerConfig):
                config_obj = config_in
            elif isinstance(config_in, dict):
                data = _normalize_data(config_in)
                try:
                    config_obj = SpreadSamplerConfig(**data)
                except Exception:
                    cfg = type("Cfg", (), {})()
                    for k, v in data.items():
                        setattr(cfg, k, v)
                    config_obj = cfg
            elif config_in is None:
                base_name = os.path.splitext(os.path.basename(__file__))[0]
                yaml_path = _find_saved_script_yaml(base_name)
                if not yaml_path:
                    try_path = os.path.join(os.getcwd(), "conf", "scripts", f"conf_{base_name}.yml")
                    if os.path.isfile(try_path):
                        yaml_path = try_path
                if yaml_path:
                    data = _load_yaml_as_dict(yaml_path)
                    if data:
                        data = _normalize_data(data)
                        try:
                            config_obj = SpreadSamplerConfig(**data)
                        except Exception:
                            cfg = type("Cfg", (), {})()
                            for k, v in data.items():
                                setattr(cfg, k, v)
                            config_obj = cfg
        except Exception:
            config_obj = None

        if config_obj is None:
            raise ValueError("SpreadSampler requires a valid config object or conf YAML.")

        # call parent
        super().__init__(connectors, config_obj)

        self.config = config_obj  # type: ignore
        self._started_at: Optional[float] = None
        self._last_snapshot_at: float = 0.0
        self._last_window_report: float = 0.0
        self._samples: Dict[str, List[dict]] = {}
        self._pairs: List[str] = []
        self._discovered = False
        self._symbol_cache_ts: float = 0.0
        self._symbol_cache: List[str] = []

        # If connector_name or markets missing, try explicit conf/scripts/conf_spread_capture.yml fallback
        try:
            has_conn = bool(getattr(self.config, "connector_name", None))
            has_markets = bool(getattr(self.config, "markets", None))
            if not has_conn or not has_markets:
                explicit_path = os.path.join(os.getcwd(), "conf", "scripts", "conf_spread_capture.yml")
                if os.path.isfile(explicit_path):
                    data = _load_yaml_as_dict(explicit_path) or {}
                    # apply connector_name if missing
                    if not has_conn and data.get("connector_name"):
                        try:
                            setattr(self.config, "connector_name", data.get("connector_name"))
                        except Exception:
                            pass
                    # apply quote if present
                    if data.get("quote") is not None:
                        q = data.get("quote")
                        if isinstance(q, str):
                            q = [q]
                        q_list = [str(x).strip().upper() for x in (q or []) if x is not None]
                        try:
                            setattr(self.config, "quote", q_list)
                        except Exception:
                            pass
                    # apply and normalize markets
                    if data.get("markets") is not None:
                        mk = data.get("markets") or {}
                        norm: Dict[str, List[str]] = {}
                        for k, v in mk.items():
                            seq = v if isinstance(v, (list, tuple, set)) else ([v] if v is not None else [])
                            items = [it.replace("/", "-").replace("_", "-").upper() for it in seq if isinstance(it, str)]
                            norm[str(k)] = items
                        try:
                            setattr(self.config, "markets", norm)
                        except Exception:
                            pass
                    self._log_msg(f"[spread_sampler] loaded explicit config from {explicit_path}")
        except Exception:
            pass

        # debug: show what config/connectors look like at init
        try:
            ck = list(getattr(self, "connectors", {}).keys())
            cname = getattr(self.config, "connector_name", None)
            q = getattr(self.config, "quote", None)
            mk_keys = list(getattr(self.config, "markets", {}).keys()) if getattr(self.config, "markets", None) else []
            self._log_msg(f"[spread_sampler] debug init connector_keys={ck} connector_name={cname} quote={q} markets_keys={mk_keys}")
        except Exception:
            pass

    def _now(self) -> float:
        return time.time()

    def _fetch_exchange_symbols(self) -> List[str]:
        now = self._now()
        if self._symbol_cache and (now - self._symbol_cache_ts) < 300:
            return self._symbol_cache
        try:
            connector = (getattr(self.config, "connector_name", "") or "").lower()
            if "binance" not in connector:
                return []
            url = "https://api.binance.com/api/v3/exchangeInfo"
            with urllib.request.urlopen(url, timeout=8) as resp:
                data = json.loads(resp.read().decode())
            syms = data.get("symbols") or []
            q_list = [q.upper() for q in (getattr(self.config, "quote", []) or [])]
            out = []
            for s in syms:
                try:
                    if s.get("status", "").upper() != "TRADING":
                        continue
                    quote = (s.get("quoteAsset") or "").upper()
                    base = (s.get("baseAsset") or "").upper()
                    if quote in q_list:
                        out.append(f"{base}-{quote}")
                except Exception:
                    continue
            self._symbol_cache = sorted(set(out))
            self._symbol_cache_ts = now
            return self._symbol_cache
        except Exception:
            return []

    def _fetch_exchange_top(self, pair: str) -> Tuple[Optional[Decimal], Optional[Decimal]]:
        try:
            connector = (getattr(self.config, "connector_name", "") or "").lower()
            if "binance" not in connector:
                return None, None
            sym = pair.replace("-", "").replace("/", "").upper()
            url = f"https://api.binance.com/api/v3/depth?symbol={urllib.parse.quote(sym)}&limit=5"
            with urllib.request.urlopen(url, timeout=6) as resp:
                data = json.loads(resp.read().decode())
            bids = data.get("bids") or []
            asks = data.get("asks") or []
            bid = Decimal(str(bids[0][0])) if bids and len(bids[0]) >= 1 else None
            ask = Decimal(str(asks[0][0])) if asks and len(asks[0]) >= 1 else None
            return bid, ask
        except Exception:
            return None, None

    def _get_db_session(self) -> Optional[Session]:
        try:
            app = HummingbotApplication.main_application()
            sess = getattr(app, "db_session", None)
            if isinstance(sess, Session):
                return sess
            get_sess = getattr(app, "get_db_session", None)
            if callable(get_sess):
                s = get_sess()
                if isinstance(s, Session):
                    return s
        except Exception:
            pass
        try:
            engine = HummingbotBase.metadata.bind
            if engine is not None:
                return sessionmaker(bind=engine)()
        except Exception:
            pass
        return None

    def _store_sample_to_db(self,
                            pair: str,
                            ts: float,
                            bid: Optional[Decimal],
                            ask: Optional[Decimal],
                            mid: Optional[Decimal],
                            spread: Optional[Decimal],
                            source: Optional[str]):
        session = self._get_db_session()
        if session is None:
            self._log_msg(f"[spread_sampler] no DB session available, skipping persist for {pair}")
            return

        created_local = False
        try:
            try:
                engine = HummingbotBase.metadata.bind
            except Exception:
                engine = None
            created_local = engine is not None and getattr(session, "bind", None) is not None

            bid_d = Decimal(str(bid)) if bid is not None else None
            ask_d = Decimal(str(ask)) if ask is not None else None
            mid_d = Decimal(str(mid)) if mid is not None else None
            spread_d = Decimal(str(spread)) if spread is not None else None

            SpreadSample.add(
                session=session,
                pair=pair,
                timestamp=int(ts),
                bid=bid_d,
                ask=ask_d,
                mid=mid_d,
                spread=spread_d,
                connector=getattr(self.config, "connector_name", None),
                source=source,
            )

            try:
                session.commit()
                self._log_msg(f"[spread_sampler] persisted sample {pair} ts={int(ts)}")
            except Exception as e:
                try:
                    session.rollback()
                except Exception:
                    pass
                self._log_msg(f"[spread_sampler] DB commit failed: {e}")
        finally:
            if created_local:
                try:
                    session.close()
                except Exception:
                    pass

    def _discover_pairs(self) -> List[str]:
        pairs = set()
        conn = getattr(self, "connectors", None)
        conn = conn.get(getattr(self.config, "connector_name", None)) if conn else None
        if conn is not None:
            ob = getattr(conn, "order_books", None)
            if isinstance(ob, dict):
                pairs.update(ob.keys())
            tp = getattr(conn, "trading_pairs", None)
            if isinstance(tp, (list, set, tuple)):
                pairs.update(tp)

        # include configured seed markets (all keys)
        try:
            cfg_markets = getattr(self.config, "markets", {}) or {}
            for v in cfg_markets.values():
                if isinstance(v, (list, set, tuple)):
                    pairs.update(v)
                elif isinstance(v, str):
                    pairs.add(v)
        except Exception:
            pass

        # REST fallback symbol list for known connectors
        rest_pairs = []
        try:
            rest_pairs = self._fetch_exchange_symbols()
            pairs.update(rest_pairs)
        except Exception:
            pass

        # normalize to BASE-QUOTE form 'BASE-QUOTE' and filter by configured quotes
        normalized = set()
        q_list = [q.upper() for q in (self.config.quote or [])]
        for p in pairs:
            if not isinstance(p, str):
                continue
            p_norm = p.replace("/", "-").replace("_", "-").upper()
            matched = False
            for q in q_list:
                if p_norm.endswith(f"-{q}"):
                    normalized.add(p_norm)
                    matched = True
                    break
            if matched:
                continue
            for q in q_list:
                if p_norm.endswith(q) and "-" not in p_norm:
                    base = p_norm[:-len(q)]
                    if base:
                        normalized.add(f"{base}-{q}")
                        break

        # debug: report discovery metrics
        try:
            self._log_msg(f"[spread_sampler] debug discover connector_present={conn is not None} connector_name={self.config.connector_name} seed_count={sum(len(v) for v in (self.config.markets or {}).values())} rest_count={len(rest_pairs)} normalized_count={len(normalized)}")
        except Exception:
            pass

        return sorted(normalized)

    def _sample_top(self, pair: str) -> None:
        conn = getattr(self, "connectors", None)
        conn = conn.get(self.config.connector_name) if conn else None
        bid = None
        ask = None
        source = "connector"
        try:
            if conn is not None:
                ob = getattr(conn, "order_books", {})
                ob_pair = ob.get(pair)
                if ob_pair is None:
                    alt_keys = [pair.replace("-", "/"), pair.replace("-", "")]
                    for k in alt_keys:
                        ob_pair = ob.get(k)
                        if ob_pair is not None:
                            break
                if ob_pair:
                    if isinstance(ob_pair, dict):
                        bids = ob_pair.get("bids") or []
                        asks = ob_pair.get("asks") or []
                        if bids:
                            bid = Decimal(str(bids[0][0])) if bids and len(bids[0]) >= 1 else None
                        if asks:
                            ask = Decimal(str(asks[0][0])) if asks and len(asks[0]) >= 1 else None
                    else:
                        try:
                            snap = getattr(ob_pair, "get_snapshot", lambda: None)()
                            if snap:
                                bids = snap.get("bids") or []
                                asks = snap.get("asks") or []
                                if bids:
                                    bid = Decimal(str(bids[0][0]))
                                if asks:
                                    ask = Decimal(str(asks[0][0]))
                        except Exception:
                            pass

            if (bid is None or ask is None):
                fb, fa = self._fetch_exchange_top(pair)
                if fb is not None or fa is not None:
                    self._log_msg(f"[spread_sampler] REST fallback {pair} -> bid={fb} ask={fa}")
                    bid = bid or fb
                    ask = ask or fa
                    source = "rest"

            spread = None
            try:
                if bid is not None and ask is not None:
                    bid_d = Decimal(str(bid))
                    ask_d = Decimal(str(ask))
                    mid_d = (bid_d + ask_d) / Decimal("2")
                    if mid_d != Decimal("0"):
                        raw_spread = ((ask_d - bid_d) / mid_d) * Decimal("100")
                        spread = raw_spread.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                else:
                    mid_d = None
            except Exception:
                mid_d = None
                spread = None

            ts_now = self._now()
            self._samples.setdefault(pair, []).append({"ts": ts_now, "bid": bid, "ask": ask, "spread": spread, "source": source})
            try:
                self._store_sample_to_db(pair=pair, ts=ts_now, bid=bid, ask=ask, mid=mid_d, spread=spread, source=source)
            except Exception:
                pass
        except Exception:
            return

    def _take_snapshot(self) -> None:
        for p in self._pairs:
            self._sample_top(p)
        self._last_snapshot_at = self._now()
        for p in self._pairs:
            entries = self._samples.get(p) or []
            if not entries:
                continue
            last = entries[-1]
            bid = last.get("bid")
            ask = last.get("ask")
            ts = last.get("ts")
            spread = last.get("spread")
            spread_text = f"{spread:.2f}%" if isinstance(spread, Decimal) else "None"
            self._log_msg(f"[spread_sampler] snapshot {p} ts={ts} bid={bid} ask={ask} spread={spread_text}")

    def _trim(self) -> None:
        window_min = self.config.averaging_window_min if (self.config.averaging_window_min is not None) else (self.config.averaging_window_hours * 60)
        cutoff = self._now() - (window_min * 60)
        for pair in list(self._samples.keys()):
            entries = self._samples.get(pair, [])
            self._samples[pair] = [e for e in entries if e.get("ts", 0) >= cutoff]
            if not self._samples[pair]:
                del self._samples[pair]

    def get_24h_report(self) -> List[Tuple[str, int, Decimal, Decimal, Decimal, Optional[Decimal], Optional[Decimal]]]:
        results = []
        for pair, entries in self._samples.items():
            if not entries:
                continue
            bids = [Decimal(str(e["bid"])) for e in entries if e.get("bid") is not None]
            asks = [Decimal(str(e["ask"])) for e in entries if e.get("ask") is not None]
            spreads = [e["spread"] for e in entries if isinstance(e.get("spread"), Decimal)]
            avg_bid = (sum(bids) / Decimal(len(bids))) if bids else Decimal("0")
            avg_ask = (sum(asks) / Decimal(len(asks))) if asks else Decimal("0")
            avg_mid = (avg_bid + avg_ask) / Decimal("2") if (avg_bid != Decimal("0") or avg_ask != Decimal("0")) else Decimal("0")
            avg_spread = None
            if spreads:
                try:
                    avg_spread = (sum(spreads) / Decimal(len(spreads))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                except Exception:
                    avg_spread = None
            current_mid = None
            results.append((pair, len(entries), avg_bid, avg_ask, avg_mid, current_mid, avg_spread))
        results.sort(key=lambda r: r[4], reverse=True)
        return results

    def _log_msg(self, msg: str) -> None:
        try:
            app = HummingbotApplication.main_application()
            app_logger = getattr(app, "logger", None)
            if app_logger and hasattr(app_logger, "info"):
                app_logger.info(msg)
                return
        except Exception:
            pass
        try:
            logger_attr = getattr(self, "logger", None)
            logger_instance = logger_attr() if callable(logger_attr) else logger_attr
            if logger_instance and hasattr(logger_instance, "info"):
                logger_instance.info(msg)
                return
        except Exception:
            pass
        print(msg)

    def on_tick(self):
        now = self._now()
        if self._started_at is None:
            self._started_at = now
            self._last_window_report = now

        if not self._discovered:
            self._pairs = self._discover_pairs()
            if self._pairs:
                self._discovered = True
                self._log_msg(f"[spread_sampler] discovered pairs: {self._pairs}")
                self._take_snapshot()
                self._trim()

        interval_s = max(1, int(self.config.snapshot_interval_min)) * 60
        if now - self._last_snapshot_at >= interval_s:
            self._take_snapshot()
            self._trim()

        window_min = self.config.averaging_window_min if (self.config.averaging_window_min is not None) else (self.config.averaging_window_hours * 60)
        window_s = window_min * 60
        if now - self._last_window_report >= window_s:
            cutoff = now - window_s
            pairs_contributed = 0
            for p in self._pairs:
                entries = self._samples.get(p) or []
                spreads = [e["spread"] for e in entries if isinstance(e.get("spread"), Decimal) and e.get("ts", 0) >= cutoff]
                if not spreads:
                    continue
                try:
                    avg_sp = (sum(spreads) / Decimal(len(spreads))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                except Exception:
                    continue
                pairs_contributed += 1
                self._log_msg(f"[spread_sampler] window_avg_spread {p} = {avg_sp:.2f}% samples={len(spreads)} window_min={window_min}")
            self._log_msg(f"[spread_sampler] window_spread_report pairs_contributing={pairs_contributed} window_min={window_min}")
            self._last_window_report = now


def print_24h_report(limit: int = 50) -> None:
    app = HummingbotApplication.main_application()
    strategy = getattr(app, "strategy", None)
    if strategy is None or not hasattr(strategy, "get_24h_report"):
        print("No running strategy with get_24h_report() found.")
        return
    report = strategy.get_24h_report()
    if not report:
        print("No samples available.")
        return
    for pair, count, avg_bid, avg_ask, avg_mid, current_mid, avg_spread in report[:limit]:
        sp_text = f"{avg_spread:.2f}%" if isinstance(avg_spread, Decimal) else "None"
        print(f"{pair} | samples={count} | avg_bid={avg_bid} | avg_ask={avg_ask} | avg_mid={avg_mid} | current_mid={current_mid} | spread={sp_text}")
