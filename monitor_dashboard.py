import json
import os
import time
from datetime import datetime
from typing import List

import streamlit as st

DEFAULT_HEALTH_FILE_MM = os.getenv("HEALTH_FILE_MM", "/app/health/weex_mm_health.json")
DEFAULT_HEALTH_FILE_VOL = os.getenv("HEALTH_FILE_VOL", "/app/health/weex_vol_health.json")
DEFAULT_LOG_FILE_MM = os.getenv("LOG_FILE_MM", "/app/logs/mm/logs_weex_vcc_pmm.log")


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
    selected_bot = st.radio("Select Bot", ["Market Making", "Volume Generator", "Both"])
    health_file_mm = st.text_input("MM Health File", DEFAULT_HEALTH_FILE_MM)
    health_file_vol = st.text_input("VOL Health File", DEFAULT_HEALTH_FILE_VOL)
    log_path = st.text_input("Log File", DEFAULT_LOG_FILE_MM)
    refresh_seconds = st.number_input("Auto-refresh interval (seconds, 0=manual)", min_value=0, max_value=60, value=0)
    log_lines = st.number_input("Log lines", min_value=50, max_value=2000, value=300)

    if st.button("🔄 Refresh Now"):
        st.rerun()

    if refresh_seconds > 0:
        time.sleep(refresh_seconds)
        st.rerun()

health_mm = _load_health(health_file_mm) if selected_bot in ["Market Making", "Both"] else {}
health_vol = _load_health(health_file_vol) if selected_bot in ["Volume Generator", "Both"] else {}

col1, col2, col3, col4 = st.columns(4)

if selected_bot in ["Market Making", "Both"]:
    healthy_mm = bool(health_mm.get("healthy", False))
    last_update_mm = health_mm.get("last_update", 0)
    last_update_dt_mm = datetime.fromtimestamp(last_update_mm) if last_update_mm else None
    issues_mm = health_mm.get("issues", [])

    col1.metric("MM Healthy", "YES" if healthy_mm else "NO")
    col2.metric("MM Issues", str(len(issues_mm)))
    col3.metric("MM Last Update", last_update_dt_mm.strftime("%H:%M:%S") if last_update_dt_mm else "N/A")

if selected_bot in ["Volume Generator", "Both"]:
    healthy_vol = bool(health_vol.get("healthy", False))
    last_update_vol = health_vol.get("last_update", 0)
    last_update_dt_vol = datetime.fromtimestamp(last_update_vol) if last_update_vol else None
    issues_vol = health_vol.get("issues", [])

    if selected_bot == "Both":
        col1, col2, col3, col4 = st.columns(4)
    col1.metric("VOL Healthy", "YES" if healthy_vol else "NO")
    col2.metric("VOL Issues", str(len(issues_vol)))
    col3.metric("VOL Last Update", last_update_dt_vol.strftime("%H:%M:%S") if last_update_dt_vol else "N/A")

if selected_bot == "Both":
    st.divider()

if selected_bot in ["Market Making", "Both"]:
    if issues_mm:
        st.warning(f"**MM Issues**: {', '.join(issues_mm)}")

if selected_bot in ["Volume Generator", "Both"]:
    if issues_vol:
        st.warning(f"**VOL Issues**: {', '.join(issues_vol)}")

if selected_bot in ["Market Making", "Both"]:
    st.subheader("MM Health Snapshot")
    st.json(health_mm)

if selected_bot in ["Volume Generator", "Both"]:
    st.subheader("VOL Health Snapshot")
    st.json(health_vol)

st.subheader("Account Balances")

balances_data = {}
if selected_bot in ["Market Making", "Both"]:
    balances_data["Market Making"] = health_mm.get("balances", {})
if selected_bot in ["Volume Generator", "Both"]:
    balances_data["Volume Generator"] = health_vol.get("balances", {})

if balances_data:
    for bot_name, balances in balances_data.items():
        st.text(f"**{bot_name}:**")
        for coin, amount in sorted(balances.items()):
            st.text(f"  {coin}: {amount:.8f}")
else:
    st.info("No balance data available")

st.subheader("Order Book")

orders_data = {}
if selected_bot in ["Market Making", "Both"]:
    orders_data["Market Making"] = health_mm.get("open_orders", [])
if selected_bot in ["Volume Generator", "Both"]:
    orders_data["Volume Generator"] = health_vol.get("open_orders", [])

for bot_name, open_orders in orders_data.items():
    st.text(f"**{bot_name}:** {len(open_orders)} orders")
    if open_orders:
        buy_orders = [o for o in open_orders if o["side"] == "BUY"]
        sell_orders = [o for o in open_orders if o["side"] == "SELL"]

        col_buy, col_sell = st.columns(2)

        with col_buy:
            st.markdown(f"**BUY ({len(buy_orders)})**")
            for order in sorted(buy_orders, key=lambda x: x["price"], reverse=True)[:10]:
                st.text(f"{order['price']:.8f} × {order['amount']:.0f}")

        with col_sell:
            st.markdown(f"**SELL ({len(sell_orders)})**")
            for order in sorted(sell_orders, key=lambda x: x["price"])[:10]:
                st.text(f"{order['price']:.8f} × {order['amount']:.0f}")
    else:
        st.info(f"No open orders for {bot_name}")

    st.divider()

st.subheader("Logs (tail)")
log_tail = _tail_lines(log_path, int(log_lines))
st.text("\n".join(log_tail))
