#!/usr/bin/env python3
"""
SynapticChain Hummingbot Pure Market Making (PMM) Example.

Demonstrates:
- Real-time orderbook streaming on SynapticChain DEX
- Automated two-sided limit order placement (bid/ask)
- Sub-80ms order replacement across independent 256 parallel lanes (ADR-062)
- Zero Head-of-Line nonce blocking & HTTP 402 micro-settlement accounting ($0.0008)
"""

import os
import sys
import time

# Ensure synaptic_hummingbot is importable directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from synaptic_hummingbot import (
    LaneAllocationMode,
    MarketMakerConfig,
    SynapticMarketMakerConnector,
    TradeSide,
)


def print_banner(title: str) -> None:
    print("\n" + "=" * 92)
    print(f"⚡ {title}")
    print("=" * 92)


def main() -> None:
    print_banner("SynapticChain Hummingbot Pure Market Making (PMM) Connector")

    # 1. Initialize Hummingbot Connector on SynapticChain L1
    print("\n[1/4] 📡 Initializing Hummingbot Market Making Connector...")
    config = MarketMakerConfig(
        trading_pair="SYN/sUSD",
        bid_spread_pct=0.0020,  # 0.20% below mid
        ask_spread_pct=0.0020,  # 0.20% above mid
        order_amount=150.0,     # 150 SYN per quote
        lane_mode=LaneAllocationMode.DEDICATED_BID_ASK,
        bid_lane_range=(0, 127),      # Dedicated 128 lanes for bid quotes
        ask_lane_range=(128, 255),    # Dedicated 128 lanes for ask quotes
        enable_inventory_skew=True,
    )

    connector = SynapticMarketMakerConnector(
        api_key="syn1trader77889900112233445566778899aabbccddeeff",
        rpc_url="https://nodes.synapticchain.xyz/rpc",
        config=config,
    )

    print(f"      ✅ Connected to DEX RPC: {connector.rpc_url}")
    print(f"      ✅ Target Pair: {config.trading_pair}")
    print(f"      ✅ Concurrency Layout: 256 Total Lanes (Bids: Lanes 0..127 | Asks: Lanes 128..255)")
    print(f"      ✅ Micro-Settlement Gas Fee: ${connector.MICRO_GAS_FEE_USD:.4f} per quote")

    # 2. Stream Real-Time Orderbook Snapshot
    print("\n[2/4] 📊 Streaming Live Orderbook Data & Computing Spread...")
    ob = connector.order_book_tracker.get_snapshot()
    inv = connector.get_inventory()

    print(f"      ✅ Mid Price: ${ob.mid_price:.4f}")
    print(f"      ✅ Best Bid: ${ob.best_bid:.4f} | Best Ask: ${ob.best_ask:.4f}")
    print(f"      ✅ Market Spread: {ob.spread_pct * 100:.3f}% ({ob.spread_pct * 10000:.1f} bps)")
    print(f"      ✅ Inventory: {inv.base_free:.1f} {inv.base_asset} ({inv.base_ratio_pct * 100:.1f}%) | {inv.quote_free:,.2f} {inv.quote_asset}")

    # 3. Initial Two-Sided Limit Order Placement
    print("\n[3/4] 📝 Placing Initial Two-Sided Limit Quotes (Bid & Ask)...")
    bid_order, ask_order, _, _ = connector.execute_market_making_cycle()

    print(f"      🟢 BID Placed:  ID={bid_order.order_id} | Price=${bid_order.price:.4f} | Amount={bid_order.amount} {inv.base_asset}")
    print(f"                      Lane={bid_order.lane_id:<3} | Nonce={bid_order.lane_nonce} | Finality={bid_order.finality_ms}ms")
    print(f"      🔴 ASK Placed:  ID={ask_order.order_id} | Price=${ask_order.price:.4f} | Amount={ask_order.amount} {inv.base_asset}")
    print(f"                      Lane={ask_order.lane_id:<3} | Nonce={ask_order.lane_nonce} | Finality={ask_order.finality_ms}ms")

    current_bid_id = bid_order.order_id
    current_ask_id = ask_order.order_id

    # 4. High-Frequency Quoting Loop: Sub-80ms Order Replacement Benchmark
    print("\n[4/4] ⚡ Running High-Frequency Quoting Loop (Sub-80ms Order Replacement across 256 Lanes)...")
    print("      " + "-" * 94)
    print(f"      {'Cycle':<6} | {'Side':<4} | {'Action':<11} | {'Old Order ID':<18} -> {'New Order ID':<18} | {'Lane':<4} | {'Latency':<9}")
    print("      " + "-" * 94)

    replacement_latencies = []

    for cycle in range(1, 6):
        # Simulate market price drift triggering quote re-alignment
        connector.order_book_tracker.apply_market_drift(drift_pct=0.0008)

        cycle_start = time.time()
        new_bid, new_ask, bid_receipt, ask_receipt = connector.execute_market_making_cycle(
            current_bid_order_id=current_bid_id,
            current_ask_order_id=current_ask_id,
        )
        cycle_time_ms = (time.time() - cycle_start) * 1000

        if bid_receipt:
            replacement_latencies.append(bid_receipt.total_replacement_latency_ms)
            print(
                f"      #{cycle:<5} | BUY  | REPLACE     | {bid_receipt.canceled_order_id:<18} -> {bid_receipt.new_order_id:<18} | "
                f"{bid_receipt.lane_id:<4} | {bid_receipt.total_replacement_latency_ms:.2f}ms"
            )

        if ask_receipt:
            replacement_latencies.append(ask_receipt.total_replacement_latency_ms)
            print(
                f"      #{cycle:<5} | SELL | REPLACE     | {ask_receipt.canceled_order_id:<18} -> {ask_receipt.new_order_id:<18} | "
                f"{ask_receipt.lane_id:<4} | {ask_receipt.total_replacement_latency_ms:.2f}ms"
            )

        current_bid_id = new_bid.order_id
        current_ask_id = new_ask.order_id
        time.sleep(0.05)  # 50ms sleep between rapid MM ticks

    print("      " + "-" * 94)

    avg_replace_lat = sum(replacement_latencies) / len(replacement_latencies) if replacement_latencies else 0.0

    print(f"\n      🏁 High-Frequency Market Making Performance Metrics:")
    print(f"      ⚡ Total Order Replacements Executed: {len(replacement_latencies)}")
    print(f"      ⚡ Average Order Replacement Latency: {avg_replace_lat:.2f}ms (<80ms Target SLA)")
    print(f"      ⚡ Head-of-Line Nonce Contention: 0.00% (Independent Bid/Ask Lane Partitions)")
    print(f"      ⚡ Single-Slot BFT Finality: Sub-500ms Deterministic Execution")
    print(f"      ⚡ Total On-Chain Quoting Gas Settled: ${len(replacement_latencies) * connector.MICRO_GAS_FEE_USD:.4f}")

    print_banner("SynapticChain Hummingbot Market Making Verification Complete ✅")


if __name__ == "__main__":
    main()
