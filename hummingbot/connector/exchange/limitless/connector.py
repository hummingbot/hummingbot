"""Limitless Exchange Connector.

Async connector class wrapping limitless-sdk for market making.
Designed with Hummingbot ExchangePyBase compatibility in mind.
"""

import asyncio
import logging
import os
import time
from typing import Optional

from eth_account import Account
from limitless_sdk.api import APIError, HttpClient
from limitless_sdk.markets import MarketFetcher
from limitless_sdk.orders import OrderClient
from limitless_sdk.portfolio import PortfolioFetcher
from limitless_sdk.types import OrderType, Side
from limitless_sdk.websocket import WebSocketClient, WebSocketConfig
from web3 import Web3

logger = logging.getLogger(__name__)


class ConnectorError(Exception):
    """Connector-level error wrapping SDK exceptions."""

    def __init__(self, message: str, cause: Optional[Exception] = None):
        super().__init__(message)
        self.cause = cause


class LimitlessConnector:
    """Async connector for Limitless Exchange.

    Provides market data, trading, portfolio, and WebSocket orderbook streaming.
    Supports paper_mode to log orders without submitting.

    Args:
        api_key: Limitless API key (falls back to LIMITLESS_API_KEY env).
        private_key: Ethereum wallet private key for EIP-712 signing.
        markets: List of market slugs to track.
        paper_mode: If True, log orders instead of submitting.
        max_order_size_usd: Maximum order size in USD (safety cap).
        ws_enabled: Whether to connect WebSocket for live orderbooks.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        private_key: Optional[str] = None,
        markets: Optional[list[str]] = None,
        paper_mode: bool = False,
        max_order_size_usd: float = 20.0,
        ws_enabled: bool = True,
    ):
        self._api_key = api_key or os.getenv("LIMITLESS_API_KEY", "")
        self._private_key = private_key or os.getenv("WALLET_PRIVATE_KEY", "") or os.getenv("LIMITLESS_PRIVATE_KEY", "")
        self._market_slugs = markets or []
        self._paper_mode = paper_mode
        self._max_order_size_usd = max_order_size_usd
        self._ws_enabled = ws_enabled

        # SDK clients (initialised in start())
        self._http_client: Optional[HttpClient] = None
        self._market_fetcher: Optional[MarketFetcher] = None
        self._order_client: Optional[OrderClient] = None
        self._portfolio_fetcher: Optional[PortfolioFetcher] = None
        self._ws_client: Optional[WebSocketClient] = None
        self._account: Optional[Account] = None

        # Internal state
        self._orders: dict[str, dict] = {}
        self._orderbooks: dict[str, dict] = {}
        self._markets: dict[str, object] = {}
        self._venues: dict[str, object] = {}
        self._ob_timestamps: dict[str, float] = {}
        self._started = False
        self._ws_task: Optional[asyncio.Task] = None

    # ── Lifecycle ──────────────────────────────────────────────

    async def start(self):
        """Initialise SDK clients, fetch market data, start WS."""
        if self._started:
            logger.warning("Connector already started")
            return

        logger.info("Starting LimitlessConnector (paper=%s)", self._paper_mode)

        # Wallet
        if self._private_key:
            self._account = Account.from_key(self._private_key)
            logger.info("Wallet loaded: %s", self._account.address)
        else:
            logger.warning("No private key — trading disabled")

        # HTTP + SDK modules
        self._http_client = HttpClient(api_key=self._api_key)
        self._market_fetcher = MarketFetcher(self._http_client)
        self._portfolio_fetcher = PortfolioFetcher(self._http_client)

        if self._account:
            self._order_client = OrderClient(
                http_client=self._http_client,
                wallet=self._account,
                market_fetcher=self._market_fetcher,
            )

        # Pre-fetch configured markets (caches venues)
        for slug in self._market_slugs:
            try:
                market = await self._market_fetcher.get_market(slug)
                self._markets[slug] = market
                if market.venue:
                    self._venues[slug] = market.venue
                logger.info("Cached market: %s", slug)
            except Exception as exc:
                logger.error("Failed to fetch market %s: %s", slug, exc)

        # WebSocket
        if self._ws_enabled:
            await self._start_ws()

        self._started = True
        logger.info("LimitlessConnector started")

    async def stop(self):
        """Cancel all open orders, close WS, close HTTP."""
        if not self._started:
            return

        logger.info("Stopping LimitlessConnector")

        # Cancel all orders on tracked markets
        if self._order_client and not self._paper_mode:
            for slug in self._market_slugs:
                try:
                    await self.cancel_all(slug)
                except Exception as exc:
                    logger.error("Failed to cancel orders on %s: %s", slug, exc)

        # Close WS
        if self._ws_client:
            try:
                await self._ws_client.disconnect()
            except Exception as exc:
                logger.error("WS disconnect error: %s", exc)
            self._ws_client = None

        # Close HTTP
        if self._http_client:
            await self._http_client.close()
            self._http_client = None

        self._started = False
        logger.info("LimitlessConnector stopped")

    # ── Market Data ────────────────────────────────────────────

    async def get_order_book(self, market_slug: str) -> dict:
        """Return orderbook: {bids: [{price, size}], asks: [{price, size}]}.

        Uses WS cache if fresh (<30s), falls back to REST.
        """
        self._ensure_started()

        # Check WS cache freshness
        ts = self._ob_timestamps.get(market_slug, 0)
        if market_slug in self._orderbooks and (time.time() - ts) < 30:
            return self._orderbooks[market_slug]

        # REST fallback
        try:
            logger.debug("REST fallback for orderbook %s", market_slug)
            ob = await self._market_fetcher.get_orderbook(market_slug)
            result = {
                "bids": [{"price": e.price, "size": e.size} for e in ob.bids],
                "asks": [{"price": e.price, "size": e.size} for e in ob.asks],
                "token_id": ob.token_id,
            }
            self._orderbooks[market_slug] = result
            self._ob_timestamps[market_slug] = time.time()
            logger.debug("REST orderbook: %d bids, %d asks", len(result["bids"]), len(result["asks"]))
            return result
        except Exception as exc:
            logger.error("REST orderbook fetch failed for %s: %s", market_slug, exc)
            raise ConnectorError(f"Failed to get orderbook for {market_slug}", exc) from exc

    async def get_mid_price(self, market_slug: str) -> float:
        """Return midpoint price from best bid/ask."""
        bid, ask = await self.get_best_bid_ask(market_slug)
        if bid is None or ask is None:
            raise ConnectorError(f"No bid/ask available for {market_slug}")
        return (bid + ask) / 2.0

    async def get_best_bid_ask(self, market_slug: str) -> tuple[Optional[float], Optional[float]]:
        """Return (best_bid, best_ask) prices."""
        ob = await self.get_order_book(market_slug)
        best_bid = ob["bids"][0]["price"] if ob["bids"] else None
        best_ask = ob["asks"][0]["price"] if ob["asks"] else None
        return best_bid, best_ask

    # ── Trading ────────────────────────────────────────────────

    async def buy(
        self,
        market_slug: str,
        price: float,
        size: float,
        order_type: str = "GTC",
        token: str = "YES",
    ) -> dict:
        """Place a buy order. Returns order result dict.

        In paper_mode, logs the order and returns a synthetic result.
        """
        return await self._place_order(
            market_slug=market_slug,
            side=Side.BUY,
            price=price,
            size=size,
            order_type=order_type,
            token=token,
        )

    async def sell(
        self,
        market_slug: str,
        price: float,
        size: float,
        order_type: str = "GTC",
        token: str = "YES",
    ) -> dict:
        """Place a sell order. Returns order result dict."""
        return await self._place_order(
            market_slug=market_slug,
            side=Side.SELL,
            price=price,
            size=size,
            order_type=order_type,
            token=token,
        )

    async def cancel(self, order_id: str) -> dict:
        """Cancel a single order by ID."""
        self._ensure_started()
        if self._paper_mode:
            logger.info("[PAPER] Cancel order %s", order_id)
            self._orders.pop(order_id, None)
            return {"message": "Order canceled (paper)", "order_id": order_id}

        self._ensure_order_client()
        try:
            result = await self._order_client.cancel(order_id)
            self._orders.pop(order_id, None)
            logger.info("Cancelled order %s", order_id)
            return result
        except APIError as exc:
            raise ConnectorError(f"Cancel failed for {order_id}: {exc}", exc) from exc

    async def cancel_all(self, market_slug: str) -> dict:
        """Cancel all open orders on a market."""
        self._ensure_started()
        if self._paper_mode:
            count = sum(1 for o in self._orders.values() if o.get("market_slug") == market_slug)
            self._orders = {
                k: v for k, v in self._orders.items() if v.get("market_slug") != market_slug
            }
            logger.info("[PAPER] Cancelled %d orders on %s", count, market_slug)
            return {"message": f"Cancelled {count} orders (paper)", "market_slug": market_slug}

        self._ensure_order_client()
        try:
            result = await self._order_client.cancel_all(market_slug)
            # Remove from tracked
            self._orders = {
                k: v for k, v in self._orders.items() if v.get("market_slug") != market_slug
            }
            logger.info("Cancelled all orders on %s", market_slug)
            return result
        except APIError as exc:
            raise ConnectorError(f"Cancel all failed for {market_slug}: {exc}", exc) from exc

    # ── Account / Portfolio ────────────────────────────────────

    async def get_balance(self) -> dict:
        """Return portfolio balance info."""
        self._ensure_started()
        try:
            positions = await self._portfolio_fetcher.get_positions()
            return positions
        except APIError as exc:
            raise ConnectorError(f"Failed to get balance: {exc}", exc) from exc

    async def get_positions(self) -> list[dict]:
        """Return all open CLOB positions."""
        self._ensure_started()
        try:
            positions = await self._portfolio_fetcher.get_clob_positions()
            return positions
        except APIError as exc:
            raise ConnectorError(f"Failed to get positions: {exc}", exc) from exc

    async def get_open_orders(self, market_slug: str) -> list:
        """Return all open orders for a market via Market fluent API."""
        self._ensure_started()
        try:
            market = self._markets.get(market_slug)
            if market is None:
                market = await self._market_fetcher.get_market(market_slug)
                self._markets[market_slug] = market
            orders = await market.get_user_orders()
            return orders
        except APIError as exc:
            raise ConnectorError(f"Failed to get open orders for {market_slug}: {exc}", exc) from exc

    async def get_order_status(self, order_id: str) -> dict:
        """Return status of a tracked order.

        Checks local cache first, then queries the API for live status.
        """
        if order_id in self._orders:
            cached = self._orders[order_id]
            if cached.get("status") not in (None, "unknown"):
                return cached
        # Query via open orders on all cached markets
        try:
            for slug in list(self._markets.keys()):
                orders = await self.get_open_orders(slug)
                for o in orders:
                    oid = o.get("id", "")
                    order_data = {
                        "order_id": oid,
                        "status": o.get("status", "unknown"),
                        "price": o.get("price"),
                        "size": o.get("originalSize"),
                        "remaining": o.get("remainingSize"),
                        "side": o.get("side"),
                        "created_at": o.get("createdAt"),
                        "market_slug": slug,
                    }
                    self._orders[oid] = order_data
                    if oid == order_id:
                        return order_data
        except Exception as e:
            logger.debug("API order status scan failed for %s: %s", order_id, e)
        return {"order_id": order_id, "status": "unknown"}

    # ── Settlement / Redemption ──────────────────────────────────

    async def redeem_positions(self, market_slug: str) -> dict:
        """Redeem winning conditional tokens for USDC after market settlement.

        Calls the Gnosis CTF redeemPositions on-chain.
        Returns dict with tx_hash, gas_used, usdc_redeemed.
        """
        self._ensure_started()
        if not self._account:
            raise ConnectorError("No wallet — cannot redeem")

        # Always re-fetch to get latest resolution status
        market = await self._market_fetcher.get_market(market_slug)
        self._markets[market_slug] = market

        condition_id = getattr(market, "condition_id", None)
        if not condition_id:
            raise ConnectorError(f"No condition_id for {market_slug}")

        status = getattr(market, "status", "")
        if status != "RESOLVED":
            raise ConnectorError(f"Market not resolved yet (status={status})")

        collateral = getattr(market.collateral_token, "address", None)
        if not collateral:
            raise ConnectorError("No collateral token address")

        w3 = Web3(Web3.HTTPProvider("https://mainnet.base.org"))
        CT_ADDRESS = Web3.to_checksum_address(
            "0xC9c98965297Bc527861c898329Ee280632B76e18"
        )

        CTF_ABI = [
            {
                "inputs": [
                    {"name": "collateralToken", "type": "address"},
                    {"name": "parentCollectionId", "type": "bytes32"},
                    {"name": "conditionId", "type": "bytes32"},
                    {"name": "indexSets", "type": "uint256[]"},
                ],
                "name": "redeemPositions",
                "outputs": [],
                "type": "function",
                "stateMutability": "nonpayable",
            },
        ]

        ct = w3.eth.contract(address=CT_ADDRESS, abi=CTF_ABI)

        # Check USDC balance before
        usdc_abi = [
            {
                "constant": True,
                "inputs": [{"name": "", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function",
            }
        ]
        usdc = w3.eth.contract(
            address=Web3.to_checksum_address(collateral), abi=usdc_abi
        )
        bal_before = usdc.functions.balanceOf(self._account.address).call()

        # Build and send redeem tx
        parent = b"\x00" * 32
        cond_bytes = bytes.fromhex(condition_id.replace("0x", ""))
        index_sets = [1, 2]  # YES=1, NO=2

        nonce = w3.eth.get_transaction_count(self._account.address)
        tx = ct.functions.redeemPositions(
            Web3.to_checksum_address(collateral),
            parent,
            cond_bytes,
            index_sets,
        ).build_transaction(
            {
                "from": self._account.address,
                "nonce": nonce,
                "gas": 150000,
                "maxFeePerGas": w3.eth.gas_price * 2,
                "maxPriorityFeePerGas": w3.to_wei(0.001, "gwei"),
                "chainId": 8453,
            }
        )

        signed = self._account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)

        bal_after = usdc.functions.balanceOf(self._account.address).call()
        redeemed = (bal_after - bal_before) / 1e6

        result = {
            "tx_hash": tx_hash.hex(),
            "status": receipt["status"],
            "gas_used": receipt["gasUsed"],
            "usdc_redeemed": redeemed,
            "usdc_balance": bal_after / 1e6,
        }

        if receipt["status"] == 1:
            logger.info(
                "Redeemed %s: +$%.4f USDC (tx=%s, gas=%d)",
                market_slug[:40],
                redeemed,
                tx_hash.hex()[:16],
                receipt["gasUsed"],
            )
        else:
            logger.error("Redeem tx failed for %s: %s", market_slug, tx_hash.hex())

        return result

    # ── Minting / Token Balances ─────────────────────────────────

    async def mint_tokens(self, market_slug: str, amount_usdc: float) -> dict:
        """Mint YES + NO conditional tokens by splitting USDC.

        Calls splitPosition on the Gnosis CTF contract.
        $N USDC → N YES + N NO tokens for the given market.

        Returns dict with tx_hash, status, gas_used, amount_minted.
        """
        self._ensure_started()
        if not self._account:
            raise ConnectorError("No wallet — cannot mint")

        # Always re-fetch for latest status
        market = await self._market_fetcher.get_market(market_slug)
        self._markets[market_slug] = market

        condition_id = getattr(market, "condition_id", None)
        if not condition_id:
            raise ConnectorError(f"No condition_id for {market_slug}")

        status = getattr(market, "status", "")
        if status == "RESOLVED":
            raise ConnectorError(f"Cannot mint on resolved market (status={status})")

        collateral = getattr(market.collateral_token, "address", None)
        if not collateral:
            raise ConnectorError("No collateral token address")

        w3 = Web3(Web3.HTTPProvider("https://mainnet.base.org"))
        CT_ADDRESS = Web3.to_checksum_address(
            "0xC9c98965297Bc527861c898329Ee280632B76e18"
        )

        # USDC approval check + approve if needed
        usdc_abi = [
            {
                "constant": True,
                "inputs": [
                    {"name": "owner", "type": "address"},
                    {"name": "spender", "type": "address"},
                ],
                "name": "allowance",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function",
            },
            {
                "inputs": [
                    {"name": "spender", "type": "address"},
                    {"name": "amount", "type": "uint256"},
                ],
                "name": "approve",
                "outputs": [{"name": "", "type": "bool"}],
                "type": "function",
            },
        ]
        usdc = w3.eth.contract(
            address=Web3.to_checksum_address(collateral), abi=usdc_abi
        )

        amount_raw = int(amount_usdc * 1e6)
        allowance = usdc.functions.allowance(
            self._account.address, CT_ADDRESS
        ).call()

        if allowance < amount_raw:
            max_approval = 2**256 - 1
            nonce = w3.eth.get_transaction_count(self._account.address)
            approve_tx = usdc.functions.approve(
                CT_ADDRESS, max_approval
            ).build_transaction({
                "from": self._account.address,
                "nonce": nonce,
                "gas": 60000,
                "maxFeePerGas": w3.eth.gas_price * 2,
                "maxPriorityFeePerGas": w3.to_wei(0.001, "gwei"),
                "chainId": 8453,
            })
            signed_approve = self._account.sign_transaction(approve_tx)
            approve_hash = w3.eth.send_raw_transaction(
                signed_approve.raw_transaction
            )
            w3.eth.wait_for_transaction_receipt(approve_hash, timeout=30)
            logger.info("USDC approved for CTF contract: tx=%s", approve_hash.hex()[:16])

        # splitPosition call
        CTF_ABI = [
            {
                "inputs": [
                    {"name": "collateralToken", "type": "address"},
                    {"name": "parentCollectionId", "type": "bytes32"},
                    {"name": "conditionId", "type": "bytes32"},
                    {"name": "partition", "type": "uint256[]"},
                    {"name": "amount", "type": "uint256"},
                ],
                "name": "splitPosition",
                "outputs": [],
                "type": "function",
                "stateMutability": "nonpayable",
            },
        ]

        ct = w3.eth.contract(address=CT_ADDRESS, abi=CTF_ABI)

        parent = b"\x00" * 32
        cond_bytes = bytes.fromhex(condition_id.replace("0x", ""))
        partition = [1, 2]  # YES=1, NO=2

        nonce = w3.eth.get_transaction_count(self._account.address)
        tx = ct.functions.splitPosition(
            Web3.to_checksum_address(collateral),
            parent,
            cond_bytes,
            partition,
            amount_raw,
        ).build_transaction({
            "from": self._account.address,
            "nonce": nonce,
            "gas": 150000,
            "maxFeePerGas": w3.eth.gas_price * 2,
            "maxPriorityFeePerGas": w3.to_wei(0.001, "gwei"),
            "chainId": 8453,
        })

        signed = self._account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)

        tokens = getattr(market, "tokens", None)
        result = {
            "tx_hash": tx_hash.hex(),
            "status": receipt["status"],
            "gas_used": receipt["gasUsed"],
            "amount_minted": amount_usdc,
            "yes_token_id": tokens.yes if tokens else None,
            "no_token_id": tokens.no if tokens else None,
        }

        if receipt["status"] == 1:
            logger.info(
                "Minted %s: %.4f USDC → YES+NO (tx=%s, gas=%d)",
                market_slug[:40], amount_usdc,
                tx_hash.hex()[:16], receipt["gasUsed"],
            )
        else:
            logger.error("Mint tx failed for %s: %s", market_slug, tx_hash.hex())

        return result

    async def get_token_balance(self, market_slug: str, token: str) -> float:
        """Return balance of YES or NO tokens for a specific market.

        Args:
            market_slug: Market identifier.
            token: "YES" or "NO".

        Returns:
            Balance as float (USDC-denominated, divided by 1e6).
        """
        self._ensure_started()
        if not self._account:
            raise ConnectorError("No wallet — cannot check balance")

        token_id = await self._resolve_token_id(market_slug, token)

        w3 = Web3(Web3.HTTPProvider("https://mainnet.base.org"))
        CT_ADDRESS = Web3.to_checksum_address(
            "0xC9c98965297Bc527861c898329Ee280632B76e18"
        )

        CTF_ABI = [
            {
                "inputs": [
                    {"name": "account", "type": "address"},
                    {"name": "id", "type": "uint256"},
                ],
                "name": "balanceOf",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function",
                "stateMutability": "view",
            },
        ]

        ct = w3.eth.contract(address=CT_ADDRESS, abi=CTF_ABI)
        raw_balance = ct.functions.balanceOf(
            self._account.address, int(token_id)
        ).call()

        return raw_balance / 1e6

    # ── Market Discovery ───────────────────────────────────────

    async def get_active_markets(self, ticker: Optional[str] = None) -> list:
        """Return active markets, optionally filtered by ticker."""
        self._ensure_started()
        try:
            resp = await self._market_fetcher.get_active_markets()
            markets = resp.data
            if ticker:
                ticker_lower = ticker.lower()
                markets = [
                    m for m in markets
                    if (m.price_oracle_metadata and m.price_oracle_metadata.ticker.lower() == ticker_lower)
                ]
            return [self._market_to_dict(m) for m in markets]
        except APIError as exc:
            raise ConnectorError(f"Failed to get active markets: {exc}", exc) from exc

    async def get_market(self, market_slug: str) -> dict:
        """Return full market data dict."""
        self._ensure_started()
        try:
            market = await self._market_fetcher.get_market(market_slug)
            self._markets[market_slug] = market
            if market.venue:
                self._venues[market_slug] = market.venue
            return self._market_to_dict(market)
        except APIError as exc:
            raise ConnectorError(f"Failed to get market {market_slug}: {exc}", exc) from exc

    # ── Properties ─────────────────────────────────────────────

    @property
    def paper_mode(self) -> bool:
        return self._paper_mode

    @property
    def tracked_orders(self) -> dict[str, dict]:
        return dict(self._orders)

    @property
    def cached_orderbooks(self) -> dict[str, dict]:
        return dict(self._orderbooks)

    @property
    def wallet_address(self) -> Optional[str]:
        return self._account.address if self._account else None

    # ── Internal ───────────────────────────────────────────────

    async def _place_order(
        self,
        market_slug: str,
        side: Side,
        price: float,
        size: float,
        order_type: str,
        token: str,
    ) -> dict:
        """Core order placement logic."""
        self._ensure_started()

        # Safety check
        if size > self._max_order_size_usd:
            raise ConnectorError(
                f"Order size ${size} exceeds max ${self._max_order_size_usd}"
            )

        # Resolve token_id
        token_id = await self._resolve_token_id(market_slug, token)
        sdk_order_type = OrderType.GTC if order_type == "GTC" else OrderType.FOK

        log_data = {
            "market": market_slug,
            "side": side.name,
            "price": price,
            "size": size,
            "type": order_type,
            "token": token,
        }

        if self._paper_mode:
            paper_id = f"paper-{int(time.time() * 1000)}"
            paper_order = {
                "order_id": paper_id,
                "market_slug": market_slug,
                "side": side.name,
                "price": price,
                "size": size,
                "order_type": order_type,
                "token": token,
                "status": "open",
                "paper": True,
                "created_at": time.time(),
            }
            self._orders[paper_id] = paper_order
            logger.info("[PAPER] %s order: %s", side.name, log_data)
            return paper_order

        self._ensure_order_client()

        # Ensure market is cached (for venue)
        if market_slug not in self._markets:
            await self.get_market(market_slug)

        try:
            logger.info("Placing %s order: %s", side.name, log_data)
            resp = await self._order_client.create_order(
                token_id=token_id,
                side=side,
                order_type=sdk_order_type,
                market_slug=market_slug,
                price=price,
                size=size,
            )

            order_data = {
                "order_id": resp.order.id if hasattr(resp.order, "id") else "unknown",
                "market_slug": market_slug,
                "side": side.name,
                "price": price,
                "size": size,
                "order_type": order_type,
                "token": token,
                "status": resp.order.status if hasattr(resp.order, "status") else "submitted",
                "response": resp.model_dump() if hasattr(resp, "model_dump") else str(resp),
                "created_at": time.time(),
            }
            order_id = order_data["order_id"]
            self._orders[str(order_id)] = order_data
            logger.info("Order placed: %s (id=%s)", side.name, order_id)
            return order_data
        except APIError as exc:
            logger.error("Order failed: %s — %s", log_data, exc)
            raise ConnectorError(f"Order failed: {exc}", exc) from exc

    async def _resolve_token_id(self, market_slug: str, token: str) -> str:
        """Resolve YES/NO token string to actual token ID. Auto-fetches if not cached."""
        market = self._markets.get(market_slug)
        if market is None:
            try:
                market = await self._market_fetcher.get_market(market_slug)
                self._markets[market_slug] = market
                if market.venue:
                    self._venues[market_slug] = market.venue
            except Exception as exc:
                raise ConnectorError(
                    f"Market {market_slug} not found: {exc}"
                ) from exc
        tokens = getattr(market, "tokens", None)
        if tokens is None:
            raise ConnectorError(f"Market {market_slug} has no token IDs (not a CLOB market?)")

        if token.upper() == "YES":
            return tokens.yes
        elif token.upper() == "NO":
            return tokens.no
        else:
            raise ConnectorError(f"Invalid token '{token}'. Must be 'YES' or 'NO'.")

    def _ensure_started(self):
        if not self._started:
            raise ConnectorError("Connector not started. Call start() first.")

    def _ensure_order_client(self):
        if self._order_client is None:
            raise ConnectorError("OrderClient not available. Provide a private_key.")

    @staticmethod
    def _market_to_dict(market) -> dict:
        """Convert SDK Market model to a simple dict."""
        d = {
            "slug": market.slug,
            "title": market.title,
            "status": market.status,
            "trade_type": market.trade_type,
            "market_type": market.market_type,
            "expiration_date": market.expiration_date,
            "expiration_timestamp": getattr(market, "expiration_timestamp", None),
            "deadline": market.expiration_date,
            "categories": getattr(market, "categories", []),
            "prices": market.prices,
            "volume": market.volume,
            "volume_formatted": getattr(market, "volume_formatted", None),
        }
        if market.tokens:
            d["tokens"] = {"yes": market.tokens.yes, "no": market.tokens.no}
        if market.venue:
            d["venue"] = {"exchange": market.venue.exchange, "adapter": market.venue.adapter}
        if market.price_oracle_metadata:
            d["ticker"] = market.price_oracle_metadata.ticker
            d["asset_type"] = market.price_oracle_metadata.asset_type
        if market.metadata:
            d["open_price"] = getattr(market.metadata, "open_price", None)
        if getattr(market, "settings", None):
            d["min_size"] = getattr(market.settings, "min_size", None)
            d["max_spread"] = getattr(market.settings, "max_spread", None)
        return d

    # ── WebSocket ──────────────────────────────────────────────

    async def _start_ws(self):
        """Connect WS and subscribe to configured markets."""
        try:
            config = WebSocketConfig(
                api_key=self._api_key if self._api_key else None,
                auto_reconnect=True,
            )
            self._ws_client = WebSocketClient(config=config)

            # Register orderbook handler before connecting
            @self._ws_client.on("orderbookUpdate")
            async def _on_orderbook(data):
                self._handle_orderbook_update(data)

            await self._ws_client.connect()
            logger.info("WebSocket connected")

            # Subscribe to each market
            for slug in self._market_slugs:
                await self._ws_client.subscribe(
                    "subscribe_market_prices",
                    {"marketSlugs": [slug]},
                )
                logger.info("WS subscribed to %s", slug)

        except Exception as exc:
            logger.error("WebSocket start failed: %s", exc)
            self._ws_client = None

    async def subscribe_market(self, market_slug: str):
        """Subscribe WS to a new market's orderbook updates."""
        if self._ws_client:
            try:
                await self._ws_client.subscribe(
                    "subscribe_market_prices",
                    {"marketSlugs": [market_slug]},
                )
                logger.info("WS subscribed to %s", market_slug)
            except Exception as exc:
                logger.warning("WS subscribe failed for %s: %s", market_slug, exc)
        if market_slug not in self._market_slugs:
            self._market_slugs.append(market_slug)

    def _handle_orderbook_update(self, data):
        """Process incoming WS orderbook update."""
        try:
            slug = data.get("marketSlug") or data.get("market_slug", "")
            if not slug:
                return

            # Data is nested: data["orderbook"]["bids"]/["asks"]
            ob = data.get("orderbook", data)
            bids_raw = ob.get("bids", [])
            asks_raw = ob.get("asks", [])

            if not bids_raw and not asks_raw:
                return  # Don't overwrite cache with empty data

            self._orderbooks[slug] = {
                "bids": [{"price": b.get("price"), "size": b.get("size")} for b in bids_raw],
                "asks": [{"price": a.get("price"), "size": a.get("size")} for a in asks_raw],
            }
            self._ob_timestamps[slug] = time.time()
        except Exception as exc:
            logger.error("Failed to process orderbook update: %s", exc)
