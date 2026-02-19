## Description
This PR initiates the Decibel Perpetual connector implementation.

**Key Features:**
*   **Zero-Mock Data Sources:** Utilizes real endpoints (`api.mainnet.aptoslabs.com`) derived from `@decibeltrade/sdk`.
*   **SDK Alignment:** Mapped all binary types (UserPosition, MarketDepth) to Hummingbot structures.
*   **Unit Tested:** Core deserialization logic verified against golden fixtures from SDK schemas.

**Status:**
*   [x] Architecture (Exchange, Auth, OrderBook)
*   [x] Data Source (REST Snapshot Parsing)
*   [ ] Live Integration (Blocked by API Key, see issue #8028)

We are ready to proceed with integration testing as soon as access credentials are provided.
/cc @nikspz
