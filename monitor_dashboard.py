import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import List

import streamlit as st

DEFAULT_HEALTH_FILE = os.getenv("HEALTH_FILE_MM", "/tmp/weex_mm_health.json")
DEFAULT_LOG_FILE = os.getenv("LOG_FILE_MM", "/home/jkovacs/git/hummingbot/logs/logs_weex_vcc_pmm.log")


def _tail_lines(path: str, max_lines: int) -> List[str]:
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            end = f.tell()
            block = 1024
            data = bytearray()
            while end > 0 and data.count(b"\n") <= max_lines:
                step = min(block, end)
                end -= step
                f.seek(end)
                data[:0] = f.read(step)
            return data.decode("utf-8", errors="replace").splitlines()[-max_lines:]
    except FileNotFoundError:
        return [f"File not found: {path}"]
    except Exception as e:
        return [f"Error reading {path}: {e}"]


def _load_health(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"healthy": False, "issues": [f"Health file not found: {path}"]}
    except Exception as e:
        return {"healthy": False, "issues": [f"Health file error: {e}"]}


st.set_page_config(page_title="WEEX Monitor", layout="wide")

st.title("WEEX Monitor Dashboard")

with st.sidebar:
    st.header("Settings")
    health_path = st.text_input("Health file", DEFAULT_HEALTH_FILE)
    log_path = st.text_input("Log file", DEFAULT_LOG_FILE)
    refresh_seconds = st.number_input("Auto-refresh interval (seconds, 0=manual)", min_value=0, max_value=60, value=0)
    log_lines = st.number_input("Log lines", min_value=50, max_value=2000, value=300)

    if st.button("🔄 Refresh Now"):
        st.rerun()

    if refresh_seconds > 0:
        time.sleep(refresh_seconds)
        st.rerun()

health = _load_health(health_path)

col1, col2, col3, col4 = st.columns(4)

healthy = bool(health.get("healthy", False))
last_update = health.get("last_update", 0)
last_update_dt = datetime.fromtimestamp(last_update) if last_update else None
issues = health.get("issues", [])

col1.metric("Healthy", "YES" if healthy else "NO")
col2.metric("Issues", str(len(issues)))
col3.metric("Last Update", last_update_dt.strftime("%Y-%m-%d %H:%M:%S") if last_update_dt else "N/A")
col4.metric("Health File", "OK" if Path(health_path).exists() else "Missing")

if issues:
    st.warning("\n".join(issues))

st.subheader("Health Snapshot")
st.json(health)

st.subheader("Order Book")
open_orders = health.get("open_orders", [])
if open_orders:
    buy_orders = [o for o in open_orders if o["side"] == "BUY"]
    sell_orders = [o for o in open_orders if o["side"] == "SELL"]

    col_buy, col_sell = st.columns(2)

    with col_buy:
        st.markdown("**BUY ORDERS**")
        for order in sorted(buy_orders, key=lambda x: x["price"], reverse=True):
            st.text(f"{order['price']:.6f} × {order['amount']:.0f} = {order['price'] * order['amount']:.2f}")

    with col_sell:
        st.markdown("**SELL ORDERS**")
        for order in sorted(sell_orders, key=lambda x: x["price"]):
            st.text(f"{order['price']:.6f} × {order['amount']:.0f} = {order['price'] * order['amount']:.2f}")
else:
    st.info("No open orders")

st.subheader("Balances")
balances = health.get("balances", {})
if balances:
    for asset, amount in balances.items():
        st.text(f"{asset}: {amount:.8f}")
else:
    st.info("No balance data")

st.subheader("Logs (tail)")
log_tail = _tail_lines(log_path, int(log_lines))
st.text("\n".join(log_tail))
