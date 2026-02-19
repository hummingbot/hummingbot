# MISSION: HUMMINGBOT DECIBEL CONNECTOR
# Context: 10_MALKUTH/Agentic_DAO/Active_Missions/Hummingbot
# Reward: $3000 USDC | Class: ⚔️ PROTOCOL

# 1. INHERITANCE
reference ../../../GEMINI.md
reference ../../../BOUNTY_HUNTER_PROTOCOL.md

# 2. OBJECTIVE
Build a production-grade Perp Connector for Decibel exchange within the Hummingbot framework.
*   **Standards:** Hummingbot v2.1+ Connector Standard.
*   **Fidelity:** Real REST + WebSocket integration. Zero-Mock.
*   **Tests:** Unit + Integration (Live).

# 3. STRATEGY (THE HUNT)
1.  **Recon:** Analyze Decibel API docs (https://docs.decibel.trade/) and Hummingbot CLOB specs.
2.  **Scaffold:** Clone Hummingbot (shallow) to understand structure, then build connector in isolation or as a fork.
3.  **Forge:** Implement `Exchange` class, `OrderBook`, `UserStream`.
4.  **Verify:** Run Hummingbot's built-in connector tests against Decibel Testnet/Mainnet.

# 4. CRITICAL RESOURCES
*   **Decibel API:** https://docs.decibel.trade/
*   **Hummingbot Dev Guide:** https://hummingbot.org/developers/connectors/
*   **Template:** Look at `binance_perpetual` or `hyperliquid` implementation in Hummingbot.
