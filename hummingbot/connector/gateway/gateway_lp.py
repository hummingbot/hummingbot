import asyncio
from decimal import Decimal
from typing import Any, Dict, Optional, Union

from pydantic import BaseModel, Field

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
    base_token_address: str = Field(alias="baseTokenAddress")
    quote_token_address: str = Field(alias="quoteTokenAddress")
    price: float
    fee_pct: float = Field(alias="feePct")
    base_token_amount: float = Field(alias="baseTokenAmount")
    quote_token_amount: float = Field(alias="quoteTokenAmount")


class CLMMPoolInfo(BaseModel):
    address: str
    base_token_address: str = Field(alias="baseTokenAddress")
    quote_token_address: str = Field(alias="quoteTokenAddress")
    bin_step: int = Field(alias="binStep")
    fee_pct: float = Field(alias="feePct")
    price: float
    base_token_amount: float = Field(alias="baseTokenAmount")
    quote_token_amount: float = Field(alias="quoteTokenAmount")
    active_bin_id: int = Field(alias="activeBinId")


class AMMPositionInfo(BaseModel):
    pool_address: str = Field(alias="poolAddress")
    wallet_address: str = Field(alias="walletAddress")
    base_token_address: str = Field(alias="baseTokenAddress")
    quote_token_address: str = Field(alias="quoteTokenAddress")
    lp_token_amount: float = Field(alias="lpTokenAmount")
    base_token_amount: float = Field(alias="baseTokenAmount")
    quote_token_amount: float = Field(alias="quoteTokenAmount")
    price: float


class CLMMPositionInfo(BaseModel):
    address: str
    pool_address: str = Field(alias="poolAddress")
    base_token_address: str = Field(alias="baseTokenAddress")
    quote_token_address: str = Field(alias="quoteTokenAddress")
    base_token_amount: float = Field(alias="baseTokenAmount")
    quote_token_amount: float = Field(alias="quoteTokenAmount")
    base_fee_amount: float = Field(alias="baseFeeAmount")
    quote_fee_amount: float = Field(alias="quoteFeeAmount")
    lower_bin_id: int = Field(alias="lowerBinId")
    upper_bin_id: int = Field(alias="upperBinId")
    lower_price: float = Field(alias="lowerPrice")
    upper_price: float = Field(alias="upperPrice")
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
        trading_pair: str,
    ) -> Optional[Union[AMMPoolInfo, CLMMPoolInfo]]:
        """
        Retrieves pool information for a given trading pair.
        Uses the appropriate model (AMMPoolInfo or CLMMPoolInfo) based on connector type.
        """
        try:
            # Split trading_pair to get base and quote tokens
            tokens = trading_pair.split("-")
            if len(tokens) != 2:
                raise ValueError(f"Invalid trading pair format: {trading_pair}")

            base_token, quote_token = tokens

            resp: Dict[str, Any] = await self._get_gateway_instance().pool_info(
                network=self.network,
                connector=self.connector_name,
                base_token=base_token,
                quote_token=quote_token,
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
        :param request_args: Additional arguments for position opening
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
    ):
        """
        Opens a concentrated liquidity position around the specified price with a percentage width.

        :param trade_type: The trade type (should be RANGE)
        :param order_id: Internal order id (also called client_order_id)
        :param trading_pair: The trading pair for the position
        :param price: The center price for the position
        :param spread_pct: The width percentage to create range (e.g. 5.0 for 5%)
        :param base_token_amount: Amount of base token to add (optional)
        :param quote_token_amount: Amount of quote token to add (optional)
        :param slippage_pct: Maximum allowed slippage percentage
        :return: Response from the gateway API
        """
        # Check connector type is CLMM
        if get_connector_type(self.connector_name) != ConnectorType.CLMM:
            raise ValueError(f"Connector {self.connector_name} is not of type CLMM.")

        # Split trading_pair to get base and quote tokens
        tokens = trading_pair.split("-")
        if len(tokens) != 2:
            raise ValueError(f"Invalid trading pair format: {trading_pair}")

        base_token, quote_token = tokens

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
                base_token=base_token,
                quote_token=quote_token,
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
    ):
        """
        Opens a regular AMM liquidity position.

        :param trade_type: The trade type (should be RANGE)
        :param order_id: Internal order id (also called client_order_id)
        :param trading_pair: The trading pair for the position
        :param price: The price for the position
        :param base_token_amount: Amount of base token to add (required)
        :param quote_token_amount: Amount of quote token to add (required)
        :param slippage_pct: Maximum allowed slippage percentage
        """
        # Check connector type is AMM
        if get_connector_type(self.connector_name) != ConnectorType.AMM:
            raise ValueError(f"Connector {self.connector_name} is not of type AMM.")

        # Split trading_pair to get base and quote tokens
        tokens = trading_pair.split("-")
        if len(tokens) != 2:
            raise ValueError(f"Invalid trading pair format: {trading_pair}")

        base_token, quote_token = tokens

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
                base_token=base_token,
                quote_token=quote_token,
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
        position_address: Optional[str] = None,
        percentage: float = 100.0,
        **request_args
    ) -> str:
        """
        Closes a liquidity position - either concentrated (CLMM) or regular (AMM) based on the connector type.
        :param trading_pair: The market trading pair
        :param position_address: The address of the position to close (required for CLMM, optional for AMM)
        :param percentage: Percentage of liquidity to remove (for AMM, defaults to 100%)
        :return: A newly created order id (internal).
        """
        connector_type = get_connector_type(self.connector_name)

        # Verify we have a position address for CLMM positions
        if connector_type == ConnectorType.CLMM and position_address is None:
            raise ValueError("position_address is required to close a CLMM position")

        trade_type: TradeType = TradeType.RANGE
        order_id: str = self.create_market_order_id(trade_type, trading_pair)

        # Call appropriate function based on connector type
        if connector_type == ConnectorType.CLMM:
            safe_ensure_future(self._clmm_close_position(trade_type, order_id, trading_pair, position_address, **request_args))
        elif connector_type == ConnectorType.AMM:
            safe_ensure_future(self._amm_close_position(trade_type, order_id, trading_pair, percentage, **request_args))
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
        percentage: float = 100.0,
        fail_silently: bool = False,
    ):
        """
        Closes an AMM liquidity position by removing specified percentage of liquidity.

        :param trade_type: The trade type (should be RANGE)
        :param order_id: Internal order id (also called client_order_id)
        :param trading_pair: The trading pair for the position
        :param percentage: Percentage of liquidity to remove (0-100)
        :param fail_silently: Whether to fail silently on error
        """
        # Check connector type is AMM
        if get_connector_type(self.connector_name) != ConnectorType.AMM:
            raise ValueError(f"Connector {self.connector_name} is not of type AMM.")

        # Split trading_pair to get base and quote tokens
        tokens = trading_pair.split("-")
        if len(tokens) != 2:
            raise ValueError(f"Invalid trading pair format: {trading_pair}")

        base_token, quote_token = tokens

        # Start tracking order
        self.start_tracking_order(order_id=order_id,
                                  trading_pair=trading_pair,
                                  trade_type=trade_type)

        try:
            transaction_result = await self._get_gateway_instance().amm_remove_liquidity(
                connector=self.connector_name,
                network=self.network,
                wallet_address=self.address,
                base_token=base_token,
                quote_token=quote_token,
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
        base_token_amount: float,
        quote_token_amount: float,
        slippage_pct: Optional[float] = None,
        fail_silently: bool = False
    ) -> Dict[str, Any]:
        """
        Adds liquidity to an AMM pool.
        :param trading_pair: The trading pair for the position
        :param base_token_amount: Amount of base token to add
        :param quote_token_amount: Amount of quote token to add
        :param slippage_pct: Maximum allowed slippage percentage
        :param fail_silently: Whether to fail silently on error
        :return: Response from the gateway API
        """
        # Check connector type is AMM
        if get_connector_type(self.connector_name) != ConnectorType.AMM:
            raise ValueError(f"Connector {self.connector_name} is not of type AMM.")

        # Split trading_pair to get base and quote tokens
        tokens = trading_pair.split("-")
        if len(tokens) != 2:
            raise ValueError(f"Invalid trading pair format: {trading_pair}")

        base_token, quote_token = tokens

        order_id: str = self.create_market_order_id(TradeType.RANGE, trading_pair)
        self.start_tracking_order(order_id=order_id,
                                  trading_pair=trading_pair,
                                  trade_type=TradeType.RANGE)
        try:
            transaction_result = await self._get_gateway_instance().amm_add_liquidity(
                connector=self.connector_name,
                network=self.network,
                wallet_address=self.address,
                base_token=base_token,
                quote_token=quote_token,
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
        percentage: float,
        fail_silently: bool = False
    ) -> Dict[str, Any]:
        """
        Removes liquidity from an AMM pool.
        :param trading_pair: The trading pair for the position
        :param percentage: Percentage of liquidity to remove (0-100)
        :param fail_silently: Whether to fail silently on error
        :return: Response from the gateway API
        """
        # Check connector type is AMM
        if get_connector_type(self.connector_name) != ConnectorType.AMM:
            raise ValueError(f"Connector {self.connector_name} is not of type AMM.")

        # Split trading_pair to get base and quote tokens
        tokens = trading_pair.split("-")
        if len(tokens) != 2:
            raise ValueError(f"Invalid trading pair format: {trading_pair}")

        base_token, quote_token = tokens

        order_id: str = self.create_market_order_id(TradeType.RANGE, trading_pair)
        self.start_tracking_order(order_id=order_id,
                                  trading_pair=trading_pair,
                                  trade_type=TradeType.RANGE)
        try:
            transaction_result = await self._get_gateway_instance().amm_remove_liquidity(
                connector=self.connector_name,
                network=self.network,
                wallet_address=self.address,
                base_token=base_token,
                quote_token=quote_token,
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
            # Split trading_pair to get base and quote tokens
            tokens = trading_pair.split("-")
            if len(tokens) != 2:
                raise ValueError(f"Invalid trading pair format: {trading_pair}")

            base_token, quote_token = tokens

            connector_type = get_connector_type(self.connector_name)
            if connector_type == ConnectorType.CLMM:
                if position_address is None:
                    raise ValueError("position_address is required for CLMM positions")

                resp: Dict[str, Any] = await self._get_gateway_instance().clmm_position_info(
                    connector=self.connector_name,
                    network=self.network,
                    position_address=position_address,
                    wallet_address=self.address,
                )
                # Validate response against CLMM schema
                return CLMMPositionInfo(**resp) if resp else None

            elif connector_type == ConnectorType.AMM:
                resp: Dict[str, Any] = await self._get_gateway_instance().amm_position_info(
                    connector=self.connector_name,
                    network=self.network,
                    pool_address=position_address,
                    base_token=base_token,
                    quote_token=quote_token,
                    wallet_address=self.address,
                )
                # Validate response against AMM schema
                return AMMPositionInfo(**resp) if resp else None

            else:
                raise ValueError(f"Connector type {connector_type} does not support liquidity positions")

        except asyncio.CancelledError:
            raise
        except Exception as e:
            addr_info = f"position {position_address}" if position_address else trading_pair
            self.logger().network(
                f"Error fetching position info for {addr_info} on {self.connector_name}.",
                exc_info=True,
                app_warning_msg=str(e)
            )
            return None
