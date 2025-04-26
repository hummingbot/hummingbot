import asyncio
import functools
import logging
import time
from decimal import Decimal
from enum import StrEnum
from typing import Any, Awaitable, Callable, Concatenate, ParamSpec, TypeVar

from pydantic.dataclasses import dataclass

from hummingbot.client.settings import GatewayConnectionSetting
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.logger import HummingbotLogger


@dataclass
class GatewayStatus:
    gateway_ready: bool = False
    wallet_address: str = ""


@dataclass
class GatewayConnectionInfo:
    connector: str
    chain: str
    network: str


@dataclass
class PoolInfo:
    base_token: str | None
    quote_token: str | None
    last_price: Decimal


async def check_gateway_status(
    gw_info: GatewayConnectionInfo, logger: HummingbotLogger
) -> GatewayStatus:
    """Check if Gateway server is online and verify wallet connection"""
    logger.debug("Checking Gateway server status...")
    gw_status = GatewayStatus()
    try:
        gateway_http_client = GatewayHttpClient.get_instance()
        if await gateway_http_client.ping_gateway():
            gw_status.gateway_ready = True
            logger.debug("Gateway server is online!")

            # Verify wallet connections
            connector = gw_info.connector
            chain = gw_info.chain
            network = gw_info.network
            gateway_connections_conf = GatewayConnectionSetting.load()

            if len(gateway_connections_conf) < 1:
                logger.error(
                    "No wallet connections found. "
                    "Please connect a wallet using 'gateway connect'."
                )
            else:
                wallet = [
                    w
                    for w in gateway_connections_conf
                    if w["chain"] == chain
                    and w["connector"] == connector
                    and w["network"] == network
                ]

                if not wallet:
                    logger.error(
                        "No wallet found for %s/%s/%s. Please connect using 'gateway connect'.",
                        chain,
                        connector,
                        network,
                    )
                else:
                    gw_status.wallet_address = wallet[0]["wallet_address"]
                    logger.debug(
                        "Found wallet connection: %s", gw_status.wallet_address
                    )
        else:
            gw_status.gateway_ready = False
            logger.error(
                "Gateway server is offline! Make sure Gateway is "
                "running before using this strategy."
            )
    except (ConnectionError, TimeoutError) as e:
        # Network-related errors when connecting to Gateway
        gw_status.gateway_ready = False
        logger.error("Network error connecting to Gateway server: %s", str(e))
    except (FileNotFoundError, PermissionError) as e:
        # Configuration file access errors
        gw_status.gateway_ready = False
        logger.error("Error accessing Gateway configuration: %s", str(e))
    except (KeyError, AttributeError) as e:
        # Data structure access errors
        gw_status.gateway_ready = False
        logger.error("Error processing Gateway data: %s", str(e))

    return gw_status


class PoolError(Exception):
    """Base class for AMM/CLMM pool errors."""


class NoPoolAddress(PoolError):
    """Exception raised when no pool address is provided."""


class PoolConnectionError(PoolError):
    """Exception raised when there is a connection error with the Gateway server."""


class PoolNoWalletAddress(PoolError):
    """Exception raised when no wallet address is provided."""


class NoPositionAddress(PoolError):
    """Exception raised when no position address is provided."""


C = TypeVar("C")
P = ParamSpec("P")
R = TypeVar("R")


def handle_pool_errors(
    operation_flag: str,
    done_flag: str,
    progress_attr: str = "progress",
) -> Callable[
    [Callable[Concatenate[C, P], Awaitable[R]]],
    Callable[Concatenate[C, P], Awaitable[R]],
]:
    """
    Decorator factory for CLMM operations on methods:
      - Skips if self.progress.<operation_flag> or .<done_flag> is True
      - Sets self.progress.<operation_flag> = True before calling
      - Clears it if .<done_flag> remains False
      - Catches ConnectionError/TimeoutError → logs & raises PoolConnectionError
      - Catches ValueError/KeyError/AttributeError → logs & raises PoolError
      - On success, stamps self._last_update = now
    """

    def decorator(
        fn: Callable[Concatenate[C, P], Awaitable[R]],
    ) -> Callable[Concatenate[C, P], Awaitable[R]]:
        @functools.wraps(fn)
        async def wrapper(self: C, *args: P.args, **kwargs: P.kwargs) -> R:
            # pull out the progress dataclass
            progress = getattr(self, progress_attr)

            # guard: already in-progress or done?
            if getattr(progress, operation_flag) or getattr(progress, done_flag):
                return  # type: ignore[return-value]

            # mark in-progress
            # setattr(progress, operation_flag, True)
            try:
                # now Pylance is happy: fn expects (self, *P.args)
                result = await fn(self, *args, **kwargs)
            except (ConnectionError, TimeoutError) as e:
                self.logger().error("Network error during %s: %s", fn.__name__, e)  # type: ignore
                raise PoolConnectionError(
                    f"Could not {fn.__name__.replace('_', ' ')} due to network error."
                ) from e
            except (ValueError, KeyError, AttributeError) as e:
                self.logger().error("Error processing pool data: %s", e)  # type: ignore
                raise PoolError(
                    "Error processing pool data. Please check parameters and try again."
                ) from e
            finally:
                # clear in-progress if done_flag never flipped
                if not getattr(progress, done_flag):
                    setattr(progress, operation_flag, False)

            # success → update timestamp
            setattr(self, "_last_update", time.time())

            return result

        return wrapper

    return decorator


@dataclass
class PositionProgress:
    position_opening: bool = False
    position_opened: bool = False
    position_closing: bool = False
    position_closed: bool = False
    pool_info_fetching: bool = False
    pool_info_fetched: bool = False


class PoolType(StrEnum):
    """Enum for pool types"""

    CLMM = "CLMM"
    AMM = "AMM"


class Pool:
    _logger: HummingbotLogger | None = None

    def __init__(
        self,
        gw_info: GatewayConnectionInfo,
        pool_address: str | None = None,
        wallet_address: str | None = None,
        pool_type: PoolType = PoolType.CLMM,
    ) -> None:
        self.gw_info = gw_info
        self.pool_address = pool_address
        self.wallet_address = wallet_address
        self.pool_info: PoolInfo = PoolInfo(
            base_token=None,
            quote_token=None,
            last_price=Decimal("0"),
        )
        self.positions_owned: list[dict[str, Any]] = []
        self._last_update: float = 0
        self.progress = PositionProgress()
        self.position_address: str | None = None
        self.pool_type = pool_type

    @property
    def last_update(self) -> float:
        return self._last_update

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)  # type: ignore
        return cls._logger  # type: ignore

    @handle_pool_errors("pool_info_fetching", "pool_info_fetched")
    async def fetch_pool_info(self) -> None:
        """Fetch pool information to get tokens and current price"""
        self._last_update = time.time()
        if self.pool_address is None:
            raise NoPoolAddress(
                "No pool address provided. Please set a valid pool address or open a new position."
            )

        if self.wallet_address is None:
            raise PoolNoWalletAddress(
                "No wallet address provided. Please set a valid wallet address."
            )

        self.logger().debug("Fetching information for pool %s...", self.pool_address)
        pool_info = await GatewayHttpClient.get_instance().pool_info(
            self.gw_info.connector,
            self.gw_info.network,
            self.pool_address,
        )

        if not pool_info:
            self.logger().error(
                "Failed to get pool information for %s", self.pool_address
            )
            raise NoPoolAddress(
                f"Failed to get pool information for {self.pool_address}"
            )

        # Extract token information
        self.pool_info.base_token = pool_info.get("baseTokenAddress")
        self.pool_info.quote_token = pool_info.get("quoteTokenAddress")

        # Extract current price
        if "price" in pool_info:
            try:
                self.pool_info.last_price = Decimal(str(pool_info["price"]))
            except (ValueError, TypeError) as e:
                self.logger().error("Error converting price value: %s", e)

        self.logger().debug(
            "Fetching information for position of wallet %s of pool %s...",
            self.wallet_address,
            self.pool_address,
        )
        self.positions_owned = (
            (
                await GatewayHttpClient.get_instance().clmm_positions_owned(
                    self.gw_info.connector,
                    self.gw_info.network,
                    self.pool_address,
                    self.wallet_address,
                )
            )
            if self.pool_type == PoolType.CLMM
            else (
                [
                    await GatewayHttpClient.get_instance().amm_position_info(
                        connector=self.gw_info.connector,
                        network=self.gw_info.network,
                        wallet_address=self.wallet_address,
                        pool_address=self.pool_address,
                    )
                ]
            )
        )
        if self.positions_owned:
            self.position_address = (
                self.positions_owned[0].get("address")
                if self.pool_type == PoolType.CLMM
                else self.positions_owned[0].get("poolAddress")
            )
            self.progress.position_opened = True
            self.progress.position_opening = False
            self.logger().debug("Position address: %s", self.position_address)
        else:
            raise NoPositionAddress(
                f"No positions found for wallet {self.wallet_address} in pool {self.pool_address}"
            )
        self.logger().debug("Positions owned: %s", self.positions_owned)

    @handle_pool_errors("position_opening", "position_opened")
    async def open_position(
        self,
        base_amount: float,
        quote_amount: float,
        lower_bound: float,
        upper_bound: float,
    ) -> None:
        """Open a position in the CLMM pool"""
        if self.progress.position_opening or self.progress.position_opened:
            return

        if self.wallet_address is None:
            raise PoolNoWalletAddress(
                "No wallet address provided. Please set a valid wallet address."
            )

        self.progress.position_opening = True

        self.logger().debug(
            "Opening position in pool %s with base amount %s and quote amount %s...",
            self.pool_address,
            base_amount,
            quote_amount,
        )
        if self.pool_type == PoolType.CLMM:
            response = await GatewayHttpClient.get_instance().clmm_open_position(
                connector=self.gw_info.connector,
                network=self.gw_info.network,
                pool_address=self.pool_address,
                wallet_address=self.wallet_address,
                lower_price=lower_bound,
                upper_price=upper_bound,
                base_token_amount=base_amount,
                quote_token_amount=quote_amount,
            )
        else:
            response = await GatewayHttpClient.get_instance().amm_add_liquidity(
                connector=self.gw_info.connector,
                network=self.gw_info.network,
                pool_address=self.pool_address,
                wallet_address=self.wallet_address,
                base_token_amount=base_amount,
                quote_token_amount=quote_amount,
            )

        self.logger().info("Open position/liquidity response: %s", response)

        # Check for txHash
        if "signature" in response:
            tx_hash = response["signature"]
            self.logger().info(f"Position opening transaction submitted: {tx_hash}")

            # Store position address from response
            if "positionAddress" in response:
                potential_position_address: str = response["positionAddress"]
                self.logger().info(
                    f"Position address from transaction "
                    f"(pending confirmation): {potential_position_address}"
                )
                # Store it temporarily in case we need it
                self.position_address = potential_position_address

            # Poll for transaction result - this is async and will wait
            tx_success = await poll_transaction(
                tx_hash=tx_hash,
                chain=self.gw_info.chain,
                network=self.gw_info.network,
                logger=self.logger(),
            )

            if tx_success:
                # Transaction confirmed successfully
                self.progress.position_opened = True
                self.logger().info(
                    f"Position opened successfully! Position address: {self.position_address}"
                )
            else:
                # Transaction failed or still pending after max attempts
                self.logger().warning(
                    "Transaction did not confirm successfully within polling period."
                )
                self.logger().warning(
                    "Position may still confirm later. Check your wallet for status."
                )
                # Clear the position address since we're not sure of its status
                self.position_address = None
        else:
            # No transaction hash in response
            self.logger().error(
                f"Failed to open position. No signature in response: {response}"
            )

    @handle_pool_errors("position_closing", "position_closed")
    async def close_position(self) -> None:
        """Close the concentrated liquidity position"""
        if not self.position_address:
            raise NoPositionAddress(
                "No position address provided. Please open a position first."
            )

        if self.wallet_address is None:
            raise PoolNoWalletAddress(
                "No wallet address provided. Please set a valid wallet address."
            )

        max_retries = 10
        retry_count = 0
        position_closed = False

        # Close position with retry logic
        while retry_count < max_retries and not position_closed:
            if retry_count > 0:
                self.logger().info(
                    f"Retrying position closing (attempt {retry_count + 1}/{max_retries})..."
                )

            # Close position
            self.logger().info(f"Closing position {self.position_address}...")
            if self.pool_type == PoolType.CLMM:
                response = await GatewayHttpClient.get_instance().clmm_close_position(
                    connector=self.gw_info.connector,
                    network=self.gw_info.network,
                    wallet_address=self.wallet_address,
                    position_address=self.position_address,
                )
            else:
                response = await GatewayHttpClient.get_instance().amm_remove_liquidity(
                    connector=self.gw_info.connector,
                    network=self.gw_info.network,
                    wallet_address=self.wallet_address,
                    pool_address=self.pool_address,
                    percentage=100,
                )

            # Check response
            if "signature" in response:
                tx_hash = response["signature"]
                self.logger().info(f"Position closing transaction submitted: {tx_hash}")

                # Poll for transaction result
                tx_success = await poll_transaction(
                    tx_hash=tx_hash,
                    chain=self.gw_info.chain,
                    network=self.gw_info.network,
                    logger=self.logger(),
                )

                if tx_success:
                    self.logger().info("Position closed successfully!")
                    position_closed = True

                    # Reset position state
                    self.progress.position_opened = False
                    self.progress.position_closed = True
                    self.position_address = None

                    break  # Exit retry loop on success
                else:
                    # Transaction failed, increment retry counter
                    retry_count += 1
                    self.logger().info(
                        f"Transaction failed, will retry. {max_retries - retry_count} "
                        "attempts remaining."
                    )
                    await asyncio.sleep(2)  # Short delay before retry
            else:
                self.logger().error(
                    f"Failed to close position. No signature in response: {response}"
                )
                retry_count += 1

        if not position_closed and retry_count >= max_retries:
            self.logger().error(
                f"Failed to close position after {max_retries} attempts. Giving up."
            )


async def poll_transaction(
    *,
    tx_hash: str,
    chain: str,
    network: str,
    logger: HummingbotLogger,
    max_poll_attempts: int = 90,
) -> bool:
    """Continuously polls for transaction status until completion or max attempts reached"""
    if not tx_hash:
        return False

    logger.info(f"Polling for transaction status: {tx_hash}")

    # Transaction status codes
    # -1 = FAILED
    # 0 = UNCONFIRMED
    # 1 = CONFIRMED

    poll_attempts = 0

    while poll_attempts < max_poll_attempts:
        poll_attempts += 1
        try:
            # Use the get_transaction_status method to check transaction status
            poll_data = await GatewayHttpClient.get_instance().get_transaction_status(
                chain=chain,
                network=network,
                transaction_hash=tx_hash,
            )

            transaction_status = poll_data.get("txStatus")

            if transaction_status == 1:  # CONFIRMED
                logger.info(f"Transaction {tx_hash} confirmed successfully!")
                return True
            elif transaction_status == -1:  # FAILED
                logger.error(f"Transaction {tx_hash} failed!")
                logger.error(f"Details: {poll_data}")
                return False
            elif transaction_status == 0:  # UNCONFIRMED
                logger.info(
                    f"Transaction {tx_hash} still pending... "
                    "(attempt {poll_attempts}/{max_poll_attempts})"
                )
                # Continue polling for unconfirmed transactions
                await asyncio.sleep(5)  # Wait before polling again
            else:
                logger.warning(f"Unknown txStatus: {transaction_status}")
                logger.info(f"{poll_data}")
                # Continue polling for unknown status
                await asyncio.sleep(10)

        except (ConnectionError, TimeoutError) as e:
            logger.error(f"Network error polling transaction: {str(e)}")
            await asyncio.sleep(5)  # Add delay to avoid rapid retries on error
        except (KeyError, ValueError, AttributeError) as e:
            logger.error(f"Error processing transaction data: {str(e)}")
            await asyncio.sleep(5)  # Add delay to avoid rapid retries on error

    # If we reach here, we've exceeded maximum polling attempts
    logger.warning(
        f"Transaction {tx_hash} still unconfirmed after {max_poll_attempts} polling attempts"
    )
    # Return false but don't mark as definitely failed
    return False
