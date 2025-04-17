import asyncio
from decimal import Decimal
from typing import Any, Dict, Optional, Union

from pydantic import BaseModel

from hummingbot.connector.gateway.common_types import ConnectorType, get_connector_type
from hummingbot.connector.gateway.gateway_swap import GatewaySwap
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.utils import async_ttl_cache
from hummingbot.core.utils.async_utils import safe_ensure_future


class TokenInfo(BaseModel):
    address: str
    symbol: str
    decimals: int


class AMMPoolInfo(BaseModel):
    address: str
    baseTokenAddress: str
    quoteTokenAddress: str
    price: float
    feePct: float
    baseTokenAmount: float
    quoteTokenAmount: float


class CLMMPoolInfo(BaseModel):
    address: str
    baseTokenAddress: str
    quoteTokenAddress: str
    binStep: int
    feePct: float
    price: float
    baseTokenAmount: float
    quoteTokenAmount: float
    activeBinId: int


class AMMPositionInfo(BaseModel):
    poolAddress: str
    walletAddress: str
    baseTokenAddress: str
    quoteTokenAddress: str
    lpTokenAmount: float
    baseTokenAmount: float
    quoteTokenAmount: float
    price: float


class CLMMPositionInfo(BaseModel):
    address: str
    poolAddress: str
    baseTokenAddress: str
    quoteTokenAddress: str
    baseTokenAmount: float
    quoteTokenAmount: float
    baseFeeAmount: float
    quoteFeeAmount: float
    lowerBinId: int
    upperBinId: int
    lowerPrice: float
    upperPrice: float
    price: float


class GatewayLp(GatewaySwap):
    """
    Handles AMM and CLMM liquidity provision functionality including fetching pool info and adding/removing liquidity.
    Maintains order tracking and wallet interactions in the base class.
    """

    async def get_pool_address(self, trading_pair: str):
        self.logger().info(f"Fetching pool address for {trading_pair} on {self.connector_name}")
        pools = await self._get_gateway_instance().get_pools(self.connector_name)
        pool_address = pools[trading_pair]
        self.logger().info(f"Pool address: {pool_address}")

        return pool_address

    @async_ttl_cache(ttl=5, maxsize=10)
    async def get_pool_info(
        self,
        trading_pair: str
    ) -> Optional[Union[AMMPoolInfo, CLMMPoolInfo]]:
        """
        Retrieves pool information for a given trading pair.
        Uses the appropriate model (AMMPoolInfo or CLMMPoolInfo) based on connector type.
        """
        pool_address = None
        try:
            pool_address = await self.get_pool_address(trading_pair)
            resp: Dict[str, Any] = await self._get_gateway_instance().pool_info(
                network=self.network,
                connector=self.connector_name,
                pool_address=pool_address,
            )

            # Determine which model to use based on connector type
            connector_type = get_connector_type(self.connector_name)
            if connector_type == ConnectorType.CLMM:
                return CLMMPoolInfo(**resp) if resp else None
            elif connector_type == ConnectorType.AMM:
                return AMMPoolInfo(**resp) if resp else None
            else:
                self.logger().warning(f"Unknown connector type: {connector_type} for {self.connector_name}")
                return None

        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().network(
                f"Error fetching pool info for {trading_pair} on {self.connector_name}.",
                exc_info=True,
                app_warning_msg=str(e)
            )
            return None

    def open_position(self, trading_pair: str, price: float, **request_args) -> str:
        """
        Opens a liquidity position - either concentrated (CLMM) or regular (AMM) based on the connector type.
        :param trading_pair: The market trading pair
        :param price: The center price for the position.
        :return: A newly created order id (internal).
        """
        trade_type: TradeType = TradeType.RANGE
        order_id: str = self.create_market_order_id(trade_type, trading_pair)

        # Check connector type and call appropriate function
        connector_type = get_connector_type(self.connector_name)
        if connector_type == ConnectorType.CLMM:
            safe_ensure_future(self._clmm_open_position(trade_type, order_id, trading_pair, price, **request_args))
        elif connector_type == ConnectorType.AMM:
            safe_ensure_future(self._amm_open_position(trade_type, order_id, trading_pair, price, **request_args))
        else:
            raise ValueError(f"Connector type {connector_type} does not support liquidity provision")

        return order_id

    async def _clmm_open_position(
        self,
        trade_type: TradeType,
        order_id: str,
        trading_pair: str,
        price: float,
        spread_pct: float,
        base_token_amount: Optional[float] = None,
        quote_token_amount: Optional[float] = None,
        slippage_pct: Optional[float] = None,
        pool_address: Optional[str] = None,
    ):
        """
        Opens a concentrated liquidity position around the specified price with a percentage width.

        :param trade_type: The trade type (should be RANGE)
        :param order_id: Internal order id (also called client_order_id)
        :param trading_pair: The trading pair for the position
        :param price: The center price for the position
        :param pool_address: The address of the liquidity pool
        :param spread_pct: The width percentage to create range (e.g. 5.0 for 5%)
        :param base_token_amount: Amount of base token to add (optional)
        :param quote_token_amount: Amount of quote token to add (optional)
        :param slippage_pct: Maximum allowed slippage percentage
        :return: Response from the gateway API
        """
        # Check connector type is CLMM
        if get_connector_type(self.connector_name) != ConnectorType.CLMM:
            raise ValueError(f"Connector {self.connector_name} is not of type CLMM.")

        # Calculate the total amount in base token units
        base_amount = base_token_amount or 0.0
        quote_amount_in_base = (quote_token_amount or 0.0) / price if price > 0 else 0.0
        total_amount_in_base = base_amount + quote_amount_in_base

        # Start tracking order with calculated amount
        self.start_tracking_order(order_id=order_id,
                                  trading_pair=trading_pair,
                                  trade_type=trade_type,
                                  price=Decimal(str(price)),
                                  amount=Decimal(str(total_amount_in_base)))

        # Calculate position price range based on center price and width percentage
        spread_pct_decimal = spread_pct / 100.0
        lower_price = price * (1 - spread_pct_decimal)
        upper_price = price * (1 + spread_pct_decimal)

        # Open position
        try:
            transaction_result = await self._get_gateway_instance().clmm_open_position(
                connector=self.connector_name,
                network=self.network,
                wallet_address=self.address,
                pool_address=pool_address,
                lower_price=lower_price,
                upper_price=upper_price,
                base_token_amount=base_token_amount,
                quote_token_amount=quote_token_amount,
                slippage_pct=slippage_pct
            )
            transaction_hash: Optional[str] = transaction_result.get("signature")
            if transaction_hash is not None and transaction_hash != "":
                self.update_order_from_hash(order_id, trading_pair, transaction_hash, transaction_result)
                return transaction_hash
            else:
                raise ValueError("No transaction hash returned from gateway")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self._handle_operation_failure(order_id, trading_pair, "opening CLMM position", e)

    async def _amm_open_position(
        self,
        trade_type: TradeType,
        order_id: str,
        trading_pair: str,
        price: float,
        base_token_amount: float,
        quote_token_amount: float,
        slippage_pct: Optional[float] = None,
        pool_address: Optional[str] = None,
    ):
        """
        Opens a regular AMM liquidity position.

        :param trade_type: The trade type (should be RANGE)
        :param order_id: Internal order id (also called client_order_id)
        :param trading_pair: The trading pair for the position
        :param price: The price for the position
        :param pool_address: The address of the liquidity pool
        :param base_token_amount: Amount of base token to add (required)
        :param quote_token_amount: Amount of quote token to add (required)
        :param slippage_pct: Maximum allowed slippage percentage
        """
        # Check connector type is AMM
        if get_connector_type(self.connector_name) != ConnectorType.AMM:
            raise ValueError(f"Connector {self.connector_name} is not of type AMM.")

        # Calculate the total amount in base token units
        quote_amount_in_base = quote_token_amount / price if price > 0 else 0.0
        total_amount_in_base = base_token_amount + quote_amount_in_base

        # Start tracking order with calculated amount
        self.start_tracking_order(order_id=order_id,
                                  trading_pair=trading_pair,
                                  trade_type=trade_type,
                                  price=Decimal(str(price)),
                                  amount=Decimal(str(total_amount_in_base)))

        # Add liquidity to AMM pool
        try:
            transaction_result = await self._get_gateway_instance().amm_add_liquidity(
                connector=self.connector_name,
                network=self.network,
                wallet_address=self.address,
                pool_address=pool_address,
                base_token_amount=base_token_amount,
                quote_token_amount=quote_token_amount,
                slippage_pct=slippage_pct
            )
            transaction_hash: Optional[str] = transaction_result.get("signature")
            if transaction_hash is not None and transaction_hash != "":
                self.update_order_from_hash(order_id, trading_pair, transaction_hash, transaction_result)
                return transaction_hash
            else:
                raise ValueError("No transaction hash returned from gateway")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self._handle_operation_failure(order_id, trading_pair, "opening AMM position", e)

    def close_position(
        self,
        trading_pair: str,
        position_address: str,
        percentage: float = 100.0,
        **request_args
    ) -> str:
        """
        Closes a liquidity position - either concentrated (CLMM) or regular (AMM) based on the connector type.
        :param trading_pair: The market trading pair
        :param position_address: The address of the position to close (for CLMM)
        :param percentage: Percentage of liquidity to remove (for AMM, defaults to 100%)
        :return: A newly created order id (internal).
        """
        trade_type: TradeType = TradeType.RANGE
        order_id: str = self.create_market_order_id(trade_type, trading_pair)

        # Check connector type and call appropriate function
        connector_type = get_connector_type(self.connector_name)
        if connector_type == ConnectorType.CLMM:
            safe_ensure_future(self._clmm_close_position(trade_type, order_id, trading_pair, position_address, **request_args))
        elif connector_type == ConnectorType.AMM:
            safe_ensure_future(self._amm_close_position(trade_type, order_id, trading_pair, position_address, percentage, **request_args))
        else:
            raise ValueError(f"Connector type {connector_type} does not support liquidity provision")

        return order_id

    async def _clmm_close_position(
        self,
        trade_type: TradeType,
        order_id: str,
        trading_pair: str,
        position_address: str,
        fail_silently: bool = False,
    ):
        """
        Closes a concentrated liquidity position for the given position address.

        :param trade_type: The trade type (should be RANGE)
        :param order_id: Internal order id (also called client_order_id)
        :param trading_pair: The trading pair for the position
        :param position_address: The address of the position to close
        :param fail_silently: Whether to fail silently on error
        """
        # Check connector type is CLMM
        if get_connector_type(self.connector_name) != ConnectorType.CLMM:
            raise ValueError(f"Connector {self.connector_name} is not of type CLMM.")

        # Start tracking order
        self.start_tracking_order(order_id=order_id,
                                  trading_pair=trading_pair,
                                  trade_type=trade_type)
        try:
            transaction_result = await self._get_gateway_instance().clmm_close_position(
                connector=self.connector_name,
                network=self.network,
                wallet_address=self.address,
                position_address=position_address,
                fail_silently=fail_silently
            )
            transaction_hash: Optional[str] = transaction_result.get("signature")
            if transaction_hash is not None and transaction_hash != "":
                self.update_order_from_hash(order_id, trading_pair, transaction_hash, transaction_result)
                return transaction_hash
            else:
                raise ValueError("No transaction hash returned from gateway")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self._handle_operation_failure(order_id, trading_pair, "closing CLMM position", e)

    async def _amm_close_position(
        self,
        trade_type: TradeType,
        order_id: str,
        trading_pair: str,
        pool_address: str,
        percentage: float = 100.0,
        fail_silently: bool = False,
    ):
        """
        Closes an AMM liquidity position by removing specified percentage of liquidity.

        :param trade_type: The trade type (should be RANGE)
        :param order_id: Internal order id (also called client_order_id)
        :param trading_pair: The trading pair for the position
        :param pool_address: The address of the pool (used as position identifier for AMM)
        :param percentage: Percentage of liquidity to remove (0-100)
        :param fail_silently: Whether to fail silently on error
        """
        # Check connector type is AMM
        if get_connector_type(self.connector_name) != ConnectorType.AMM:
            raise ValueError(f"Connector {self.connector_name} is not of type AMM.")

        # Start tracking order
        self.start_tracking_order(order_id=order_id,
                                  trading_pair=trading_pair,
                                  trade_type=trade_type)

        try:
            transaction_result = await self._get_gateway_instance().amm_remove_liquidity(
                connector=self.connector_name,
                network=self.network,
                wallet_address=self.address,
                pool_address=pool_address,
                percentage=percentage,
                fail_silently=fail_silently
            )
            transaction_hash: Optional[str] = transaction_result.get("signature")
            if transaction_hash is not None and transaction_hash != "":
                self.update_order_from_hash(order_id, trading_pair, transaction_hash, transaction_result)
                return transaction_hash
            else:
                raise ValueError("No transaction hash returned from gateway")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self._handle_operation_failure(order_id, trading_pair, "closing AMM position", e)

    async def amm_add_liquidity(
        self,
        trading_pair: str,
        pool_address: str,
        base_token_amount: float,
        quote_token_amount: float,
        slippage_pct: Optional[float] = None,
        fail_silently: bool = False
    ) -> Dict[str, Any]:
        """
        Adds liquidity to an AMM pool.
        :param trading_pair: The trading pair for the position
        :param pool_address: The address of the AMM pool
        :param base_token_amount: Amount of base token to add
        :param quote_token_amount: Amount of quote token to add
        :param slippage_pct: Maximum allowed slippage percentage
        :param fail_silently: Whether to fail silently on error
        :return: Response from the gateway API
        """
        # Check connector type is AMM
        if get_connector_type(self.connector_name) != ConnectorType.AMM:
            raise ValueError(f"Connector {self.connector_name} is not of type AMM.")

        order_id: str = self.create_market_order_id(TradeType.RANGE, trading_pair)
        self.start_tracking_order(order_id=order_id,
                                  trading_pair=trading_pair,
                                  trade_type=TradeType.RANGE)
        try:
            transaction_result = await self._get_gateway_instance().amm_add_liquidity(
                connector=self.connector_name,
                network=self.network,
                wallet_address=self.address,
                pool_address=pool_address,
                base_token_amount=base_token_amount,
                quote_token_amount=quote_token_amount,
                slippage_pct=slippage_pct,
                fail_silently=fail_silently
            )
            transaction_hash: Optional[str] = transaction_result.get("signature")
            if transaction_hash is not None and transaction_hash != "":
                self.update_order_from_hash(order_id, trading_pair, transaction_hash, transaction_result)
            else:
                raise ValueError
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self._handle_operation_failure(order_id, trading_pair, "adding AMM liquidity", e)

    async def amm_remove_liquidity(
        self,
        trading_pair: str,
        pool_address: str,
        percentage: float,
        fail_silently: bool = False
    ) -> Dict[str, Any]:
        """
        Removes liquidity from an AMM pool.
        :param trading_pair: The trading pair for the position
        :param pool_address: The address of the AMM pool
        :param percentage: Percentage of liquidity to remove (0-100)
        :param fail_silently: Whether to fail silently on error
        :return: Response from the gateway API
        """
        # Check connector type is AMM
        if get_connector_type(self.connector_name) != ConnectorType.AMM:
            raise ValueError(f"Connector {self.connector_name} is not of type AMM.")

        order_id: str = self.create_market_order_id(TradeType.RANGE, trading_pair)
        self.start_tracking_order(order_id=order_id,
                                  trading_pair=trading_pair,
                                  trade_type=TradeType.RANGE)
        try:
            transaction_result = await self._get_gateway_instance().amm_remove_liquidity(
                connector=self.connector_name,
                network=self.network,
                wallet_address=self.address,
                pool_address=pool_address,
                percentage=percentage,
                fail_silently=fail_silently
            )
            transaction_hash: Optional[str] = transaction_result.get("signature")
            if transaction_hash is not None and transaction_hash != "":
                self.update_order_from_hash(order_id, trading_pair, transaction_hash, transaction_result)
            else:
                raise ValueError
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self._handle_operation_failure(order_id, trading_pair, "removing AMM liquidity", e)

    @async_ttl_cache(ttl=5, maxsize=10)
    async def get_position_info(
        self,
        trading_pair: str,
        position_address: Optional[str] = None
    ) -> Union[AMMPositionInfo, CLMMPositionInfo, None]:
        """
        Retrieves position information for a given liquidity position.

        :param trading_pair: The trading pair for the position
        :param position_address: The address of the position (required for CLMM, optional for AMM)
        :return: Position information from gateway, validated against appropriate schema
        """
        try:
            connector_type = get_connector_type(self.connector_name)
            if connector_type == ConnectorType.CLMM:
                # For CLMM, we require position_address
                if position_address is None:
                    raise ValueError("position_address is required for CLMM connectors")

                resp: Dict[str, Any] = await self._get_gateway_instance().clmm_position_info(
                    connector=self.connector_name,
                    network=self.network,
                    position_address=position_address,
                    wallet_address=self.address,
                )
                # Validate response against CLMM schema
                return CLMMPositionInfo(**resp) if resp else None

            elif connector_type == ConnectorType.AMM:
                # For AMM, we can use the pool address if position_address is not provided
                pool_address = position_address
                if pool_address is None:
                    self.logger().info(f"No position address provided, fetching pool address for {trading_pair}")
                    pool_address = await self.get_pool_address(trading_pair)

                resp: Dict[str, Any] = await self._get_gateway_instance().amm_position_info(
                    connector=self.connector_name,
                    network=self.network,
                    pool_address=pool_address,
                    wallet_address=self.address,
                )
                # Validate response against AMM schema
                return AMMPositionInfo(**resp) if resp else None

            else:
                raise ValueError(f"Connector type {connector_type} does not support liquidity positions")

        except asyncio.CancelledError:
            raise
        except Exception as e:
            addr_str = position_address if position_address else f"trading pair {trading_pair}"
            self.logger().network(
                f"Error fetching position info for {addr_str} on {self.connector_name}.",
                exc_info=True,
                app_warning_msg=str(e)
            )
            return None
