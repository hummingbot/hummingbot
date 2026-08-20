# Generated from gateway-openapi.json by 'make gateway-models'. Do not edit.
# flake8: noqa: E501

from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, condecimal, confloat, conint


class AmmPoolInfo(BaseModel):
    address: str
    base_token_address: str = Field(..., alias='baseTokenAddress')
    quote_token_address: str = Field(..., alias='quoteTokenAddress')
    fee_pct: Decimal = Field(..., alias='feePct')
    price: Decimal
    base_token_amount: Decimal = Field(..., alias='baseTokenAmount')
    quote_token_amount: Decimal = Field(..., alias='quoteTokenAmount')


class AmmAddLiquidityResponseData(BaseModel):
    fee: Decimal
    pool_address: str | None = Field(None, alias='poolAddress', description='Pool this operation acted on')
    position_address: str | None = Field(None, alias='positionAddress', description='Position the liquidity went into. Absent on fungible-LP AMMs, which hold liquidity as LP tokens rather than a position account.')
    position_rent: Decimal | None = Field(None, alias='positionRent', description='Native token locked as rent when this call opened the position. Absent when adding to a position that already existed, and on fungible-LP AMMs.')
    base_token_amount_added: Decimal = Field(..., alias='baseTokenAmountAdded')
    quote_token_amount_added: Decimal = Field(..., alias='quoteTokenAmountAdded')


class AmmQuoteLiquidityResponse(BaseModel):
    pool_address: str | None = Field(None, alias='poolAddress', description='Pool the quote was computed against')
    base_limited: bool = Field(..., alias='baseLimited')
    base_token_amount: Decimal = Field(..., alias='baseTokenAmount')
    quote_token_amount: Decimal = Field(..., alias='quoteTokenAmount')
    base_token_amount_max: Decimal = Field(..., alias='baseTokenAmountMax')
    quote_token_amount_max: Decimal = Field(..., alias='quoteTokenAmountMax')


class AmmRemoveLiquidityResponseData(BaseModel):
    fee: Decimal
    pool_address: str | None = Field(None, alias='poolAddress', description='Pool this operation acted on')
    position_address: str | None = Field(None, alias='positionAddress', description='Position this operation acted on')
    position_rent_refunded: Decimal | None = Field(None, alias='positionRentRefunded', description='Native token rent returned when the position account closed. Present only on a 100% removal from an AMM whose positions are accounts.')
    base_token_amount_removed: Decimal = Field(..., alias='baseTokenAmountRemoved')
    quote_token_amount_removed: Decimal = Field(..., alias='quoteTokenAmountRemoved')


class AmmCreatePoolResponseData(BaseModel):
    fee: Decimal
    base_token_amount_added: Decimal = Field(..., alias='baseTokenAmountAdded')
    quote_token_amount_added: Decimal = Field(..., alias='quoteTokenAmountAdded')


class PositionDetail(BaseModel):
    position_address: str = Field(..., alias='positionAddress', description='Address of the individual position (NFT position account)')
    lp_token_amount: Decimal = Field(..., alias='lpTokenAmount', description='Liquidity held by this position (LP units)')
    base_token_amount: Decimal = Field(..., alias='baseTokenAmount')
    quote_token_amount: Decimal = Field(..., alias='quoteTokenAmount')


class AmmPositionInfo(BaseModel):
    pool_address: str = Field(..., alias='poolAddress')
    wallet_address: str = Field(..., alias='walletAddress')
    base_token_address: str = Field(..., alias='baseTokenAddress')
    quote_token_address: str = Field(..., alias='quoteTokenAddress')
    lp_token_amount: Decimal = Field(..., alias='lpTokenAmount')
    base_token_amount: Decimal = Field(..., alias='baseTokenAmount')
    quote_token_amount: Decimal = Field(..., alias='quoteTokenAmount')
    price: Decimal
    positions: list[PositionDetail] | None = None


class EstimateGasRequest(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    network: str | None = Field(None, description="Network to use. Defaults to the chain's configured default network.", examples=['mainnet-beta'])


class EstimateGasResponse(BaseModel):
    fee_per_compute_unit: Decimal = Field(..., alias='feePerComputeUnit')
    denomination: str
    compute_units: float = Field(..., alias='computeUnits')
    fee_asset: str = Field(..., alias='feeAsset')
    fee: Decimal
    timestamp: float
    gas_type: str | None = Field(None, alias='gasType')
    max_fee_per_gas: Decimal | None = Field(None, alias='maxFeePerGas')
    max_priority_fee_per_gas: Decimal | None = Field(None, alias='maxPriorityFeePerGas')
    priority_fee_level: str | None = Field(None, alias='priorityFeeLevel')
    priority_fee_per_cu_estimate: Decimal | None = Field(None, alias='priorityFeePerCUEstimate')


class BalanceRequest(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    network: str | None = Field(None, description="Network to use. Defaults to the chain's configured default network.", examples=['mainnet-beta'])
    address: str | None = None
    tokens: list[str] | None = Field(None, description='a list of token symbols or addresses')
    fetch_all: bool | None = Field(None, alias='fetchAll', description='fetch all tokens in wallet, not just those in token list (default: false)')


class BalanceResponse(BaseModel):
    balances: dict[str, float]


class PollRequest(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    network: str | None = Field(None, description="Network to use. Defaults to the chain's configured default network.", examples=['mainnet-beta'])
    signature: str = Field(..., description='Transaction signature/hash')


class PollResponse(BaseModel):
    current_block: float = Field(..., alias='currentBlock')
    signature: str
    tx_block: float | None = Field(..., alias='txBlock')
    tx_status: float = Field(..., alias='txStatus', description='Transaction status: 1 = confirmed, 0 = pending, -1 = failed, -2 = not found (unknown to the chain: never received or dropped; on Solana this is terminal once the transaction blockhash expires)')
    fee: float | None
    error: str | None
    tx_data: dict[str, Any] | None = Field(..., alias='txData')


class StatusRequest(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    network: str | None = Field(None, description="Network to use. Defaults to the chain's configured default network.", examples=['mainnet-beta'])


class StatusResponse(BaseModel):
    chain: str
    network: str
    rpc_url: str = Field(..., alias='rpcUrl')
    rpc_provider: str = Field(..., alias='rpcProvider')
    current_block_number: float = Field(..., alias='currentBlockNumber')
    native_currency: str = Field(..., alias='nativeCurrency')
    swap_provider: str = Field(..., alias='swapProvider')


class ChainQuoteSwapResponse(BaseModel):
    token_in: str = Field(..., alias='tokenIn', description='Address of the token being swapped from')
    token_out: str = Field(..., alias='tokenOut', description='Address of the token being swapped to')
    amount_in: Decimal = Field(..., alias='amountIn', description='Amount of tokenIn to be swapped')
    amount_out: Decimal = Field(..., alias='amountOut', description='Expected amount of tokenOut to receive')
    price: Decimal = Field(..., description='Exchange rate between tokenIn and tokenOut')
    price_impact_pct: Decimal = Field(..., alias='priceImpactPct', description='Estimated price impact percentage (0-100)')
    min_amount_out: Decimal = Field(..., alias='minAmountOut', description='Minimum amount of tokenOut that will be accepted')
    max_amount_in: Decimal = Field(..., alias='maxAmountIn', description='Maximum amount of tokenIn that will be spent')
    pool_address: str | None = Field(None, alias='poolAddress', description='Pool address for AMM/CLMM swaps')
    route_path: str | None = Field(None, alias='routePath', description='Route path for router-based swaps')
    slippage_pct: Decimal | None = Field(None, alias='slippagePct', description='Slippage tolerance percentage')


class ChainExecuteSwapResponseData(BaseModel):
    token_in: str = Field(..., alias='tokenIn', description='Address of the token swapped from')
    token_out: str = Field(..., alias='tokenOut', description='Address of the token swapped to')
    amount_in: Decimal = Field(..., alias='amountIn', description='Actual amount of tokenIn swapped')
    amount_out: Decimal = Field(..., alias='amountOut', description='Actual amount of tokenOut received')
    fee: Decimal = Field(..., description='Transaction fee paid')
    base_token_balance_change: Decimal = Field(..., alias='baseTokenBalanceChange', description='Change in base token balance (negative for decrease)')
    quote_token_balance_change: Decimal = Field(..., alias='quoteTokenBalanceChange', description='Change in quote token balance (negative for decrease)')
    slippage_pct: Decimal | None = Field(None, alias='slippagePct', description='Slippage tolerance percentage actually applied to the swap')
    pool_address: str | None = Field(None, alias='poolAddress', description='Pool the swap executed against. Set by the pool-scoped routes (/trading/clmm, /trading/amm), which resolve exactly one pool; a router picks its own path across pools and leaves this unset. Without it a settled fill cannot be reconciled to a venue without refetching the transaction.')


class WrapRequest(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    network: str | None = Field(None, description="Network to use. Defaults to the chain's configured default network.", examples=['mainnet-beta'])
    address: str = Field(..., description='Wallet address holding the native token')
    amount: str = Field(..., description='Amount of the native token to wrap, in whole units (not lamports/wei)', examples=['1.0'])


class UnwrapRequest(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    network: str | None = Field(None, description="Network to use. Defaults to the chain's configured default network.", examples=['mainnet-beta'])
    address: str = Field(..., description='Wallet address holding the wrapped token')
    amount: str | None = Field(None, description='Amount of the wrapped token to unwrap, in whole units. Solana unwraps the full balance when omitted; EVM chains require it.', examples=['1.0'])


class ChainWrapResponseData(BaseModel):
    nonce: float | None = Field(None, description='EVM transaction nonce; absent on non-EVM chains')
    fee: str
    amount: str
    wrapped_address: str = Field(..., alias='wrappedAddress')
    native_token: str = Field(..., alias='nativeToken')
    wrapped_token: str = Field(..., alias='wrappedToken')


class RouterQuoteSwapResponse(BaseModel):
    token_in: str = Field(..., alias='tokenIn', description='Address of the token being swapped from')
    token_out: str = Field(..., alias='tokenOut', description='Address of the token being swapped to')
    amount_in: Decimal = Field(..., alias='amountIn', description='Amount of tokenIn to be swapped')
    amount_out: Decimal = Field(..., alias='amountOut', description='Expected amount of tokenOut to receive')
    price: Decimal = Field(..., description='Exchange rate between tokenIn and tokenOut')
    price_impact_pct: Decimal = Field(..., alias='priceImpactPct', description='Estimated price impact percentage (0-100)')
    min_amount_out: Decimal = Field(..., alias='minAmountOut', description='Minimum amount of tokenOut that will be accepted')
    max_amount_in: Decimal = Field(..., alias='maxAmountIn', description='Maximum amount of tokenIn that will be spent')
    pool_address: str | None = Field(None, alias='poolAddress', description='Pool address for AMM/CLMM swaps')
    route_path: str | None = Field(None, alias='routePath', description='Route path for router-based swaps')
    slippage_pct: Decimal | None = Field(None, alias='slippagePct', description='Slippage tolerance percentage')
    quote_id: str = Field(..., alias='quoteId', description='Identifier to pass to /trading/router/execute-quote')
    approximation: bool | None = Field(None, description='True when a BUY was approximated via a sell-leg ExactIn quote because the router has no ExactOut route; amountOut is an estimate rather than exact')


class PoolListItem(BaseModel):
    address: str = Field(..., description='Pool address')
    name: str = Field(..., description='Pool name (e.g., SOL-USDC)')
    base_token_address: str = Field(..., alias='baseTokenAddress', description='Base token address')
    base_token_symbol: str = Field(..., alias='baseTokenSymbol', description='Base token symbol')
    quote_token_address: str = Field(..., alias='quoteTokenAddress', description='Quote token address')
    quote_token_symbol: str = Field(..., alias='quoteTokenSymbol', description='Quote token symbol')
    bin_step: float = Field(..., alias='binStep', description='Bin step / tick spacing')
    base_fee: Decimal = Field(..., alias='baseFee', description='Base fee percentage')
    price: Decimal = Field(..., description='Current price')
    tvl: Decimal = Field(..., description='Total value locked in USD')
    apr: Decimal | None = Field(None, description='Annual percentage rate')
    apy: Decimal | None = Field(None, description='Annual percentage yield')
    volume24h: Decimal | None = Field(None, description='24-hour trading volume')
    fees24h: Decimal | None = Field(None, description='24-hour fees collected')


class ClmmFetchPoolsResponse(BaseModel):
    pools: list[PoolListItem]
    total: float = Field(..., description='Total number of matching pools')
    page: float = Field(..., description='Current page number')
    page_size: float = Field(..., alias='pageSize', description='Number of pools per page')


class BinLiquidity(BaseModel):
    bin_id: float = Field(..., alias='binId')
    price: Decimal
    base_token_amount: Decimal = Field(..., alias='baseTokenAmount')
    quote_token_amount: Decimal = Field(..., alias='quoteTokenAmount')


class ClmmPoolInfo(BaseModel):
    address: str
    base_token_address: str = Field(..., alias='baseTokenAddress')
    quote_token_address: str = Field(..., alias='quoteTokenAddress')
    bin_step: float | None = Field(None, alias='binStep')
    fee_pct: Decimal = Field(..., alias='feePct')
    price: Decimal
    base_token_amount: Decimal = Field(..., alias='baseTokenAmount')
    quote_token_amount: Decimal = Field(..., alias='quoteTokenAmount')
    active_bin_id: float = Field(..., alias='activeBinId')
    bins: list[BinLiquidity] | None = None


class ClmmPositionInfo(BaseModel):
    address: str
    pool_address: str = Field(..., alias='poolAddress')
    base_token_address: str = Field(..., alias='baseTokenAddress')
    quote_token_address: str = Field(..., alias='quoteTokenAddress')
    base_token_amount: Decimal = Field(..., alias='baseTokenAmount')
    quote_token_amount: Decimal = Field(..., alias='quoteTokenAmount')
    base_fee_amount: Decimal = Field(..., alias='baseFeeAmount')
    quote_fee_amount: Decimal = Field(..., alias='quoteFeeAmount')
    lower_bin_id: float = Field(..., alias='lowerBinId')
    upper_bin_id: float = Field(..., alias='upperBinId')
    lower_price: Decimal = Field(..., alias='lowerPrice')
    upper_price: Decimal = Field(..., alias='upperPrice')
    price: Decimal


class ClmmOpenPositionResponseData(BaseModel):
    fee: Decimal
    pool_address: str | None = Field(None, alias='poolAddress', description='Pool this operation acted on')
    position_address: str = Field(..., alias='positionAddress')
    position_rent: Decimal = Field(..., alias='positionRent')
    base_token_amount_added: Decimal = Field(..., alias='baseTokenAmountAdded')
    quote_token_amount_added: Decimal = Field(..., alias='quoteTokenAmountAdded')


class ClmmAddLiquidityResponseData(BaseModel):
    fee: Decimal
    pool_address: str | None = Field(None, alias='poolAddress', description='Pool this operation acted on')
    position_address: str | None = Field(None, alias='positionAddress', description='Position this operation acted on')
    base_token_amount_added: Decimal = Field(..., alias='baseTokenAmountAdded')
    quote_token_amount_added: Decimal = Field(..., alias='quoteTokenAmountAdded')


class ClmmRemoveLiquidityResponseData(BaseModel):
    fee: Decimal
    pool_address: str | None = Field(None, alias='poolAddress', description='Pool this operation acted on')
    position_address: str | None = Field(None, alias='positionAddress', description='Position this operation acted on')
    base_token_amount_removed: Decimal = Field(..., alias='baseTokenAmountRemoved')
    quote_token_amount_removed: Decimal = Field(..., alias='quoteTokenAmountRemoved')


class ClmmCollectFeesResponseData(BaseModel):
    fee: Decimal
    pool_address: str | None = Field(None, alias='poolAddress', description='Pool this operation acted on')
    position_address: str | None = Field(None, alias='positionAddress', description='Position this operation acted on')
    base_fee_amount_collected: Decimal = Field(..., alias='baseFeeAmountCollected')
    quote_fee_amount_collected: Decimal = Field(..., alias='quoteFeeAmountCollected')


class ClmmClosePositionResponseData(BaseModel):
    fee: Decimal
    pool_address: str | None = Field(None, alias='poolAddress', description='Pool this operation acted on')
    position_address: str | None = Field(None, alias='positionAddress', description='Position this operation acted on')
    position_rent_refunded: Decimal = Field(..., alias='positionRentRefunded')
    base_token_amount_removed: Decimal = Field(..., alias='baseTokenAmountRemoved')
    quote_token_amount_removed: Decimal = Field(..., alias='quoteTokenAmountRemoved')
    base_fee_amount_collected: Decimal = Field(..., alias='baseFeeAmountCollected')
    quote_fee_amount_collected: Decimal = Field(..., alias='quoteFeeAmountCollected')


class ClmmCreatePoolResponseData(BaseModel):
    fee: Decimal


class ClmmQuoteLiquidityResponse(BaseModel):
    pool_address: str | None = Field(None, alias='poolAddress', description='Pool the quote was computed against')
    base_limited: bool = Field(..., alias='baseLimited')
    base_token_amount: Decimal = Field(..., alias='baseTokenAmount')
    quote_token_amount: Decimal = Field(..., alias='quoteTokenAmount')
    base_token_amount_max: Decimal = Field(..., alias='baseTokenAmountMax')
    quote_token_amount_max: Decimal = Field(..., alias='quoteTokenAmountMax')
    liquidity: Any | None = None


class AmmCreatePoolRequest(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    connector: str = Field(..., description='AMM connector', examples=['meteora'])
    chain_network: str = Field(..., alias='chainNetwork', description='Chain and network in format: chain-network (e.g., solana-mainnet-beta, ethereum-mainnet)', examples=['solana-mainnet-beta'])
    wallet_address: str = Field(..., alias='walletAddress', description='Wallet address (pool creator + payer)')
    base_token: str = Field(..., alias='baseToken', description='Base token symbol or address (becomes the pool base)')
    quote_token: str = Field(..., alias='quoteToken', description='Quote token symbol or address (becomes the pool quote)')
    base_token_amount: Decimal = Field(..., alias='baseTokenAmount', description='Amount of base token to seed the pool with')
    quote_token_amount: Decimal | None = Field(None, alias='quoteTokenAmount', description='Amount of quote token to seed with. If provided, the base:quote ratio sets the initial price. If omitted (and no initialPrice), the price is fetched from the market.')
    initial_price: Decimal | None = Field(None, alias='initialPrice', description='Initial price as quote per base. Overrides quoteTokenAmount. If both are omitted, the current market price is fetched from the unified swap router so the pool opens on-market.')
    config_address: str | None = Field(None, alias='configAddress', description='Meteora DAMM v2 config account address (required for the meteora connector — configs are permissionless accounts with no index derivation, so the address must be explicit).')
    amm_config_index: float | None = Field(None, alias='ammConfigIndex', description='Raydium CPMM fee-config index (optional; defaults to the first available config).')
    slippage_pct: condecimal(ge=Decimal('0'), le=Decimal('100')) | None = Field(None, alias='slippagePct', description="Uniswap/PancakeSwap seeding slippage percentage. Defaults to the connector's configured slippagePct.", examples=[1])


class AmmAddRequest(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    connector: str = Field(..., description='AMM connector', examples=['meteora'])
    chain_network: str = Field(..., alias='chainNetwork', description='Chain and network in format: chain-network (e.g., solana-mainnet-beta, ethereum-mainnet)', examples=['solana-mainnet-beta'])
    wallet_address: str = Field(..., alias='walletAddress', description='Wallet address')
    pool_address: str = Field(..., alias='poolAddress', description='Pool contract address')
    base_token_amount: Decimal = Field(..., alias='baseTokenAmount', description='Amount of base token to add')
    quote_token_amount: Decimal = Field(..., alias='quoteTokenAmount', description='Amount of quote token to add')
    position_address: str | None = Field(None, alias='positionAddress', description='meteora only (DAMM v2 positions are NFTs): add to this specific position. Omit to open a new position. Ignored by fungible-LP AMMs.')
    slippage_pct: condecimal(ge=Decimal('0'), le=Decimal('100')) | None = Field(None, alias='slippagePct', description="Maximum acceptable slippage percentage. Defaults to the connector's configured slippagePct.", examples=[1])


class AmmRemoveRequest(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    connector: str = Field(..., description='AMM connector', examples=['meteora'])
    chain_network: str = Field(..., alias='chainNetwork', description='Chain and network in format: chain-network (e.g., solana-mainnet-beta, ethereum-mainnet)', examples=['solana-mainnet-beta'])
    wallet_address: str = Field(..., alias='walletAddress', description='Wallet address')
    pool_address: str = Field(..., alias='poolAddress', description='Pool contract address')
    position_address: str | None = Field(None, alias='positionAddress', description='Required for meteora (DAMM v2 positions are NFTs): the specific position to remove from. List positions with position-info or positions-owned. Ignored by fungible-LP AMMs.')
    percentage_to_remove: condecimal(ge=Decimal('0'), le=Decimal('100')) = Field(..., alias='percentageToRemove', description='Percentage of liquidity to remove', examples=[100])
    slippage_pct: condecimal(ge=Decimal('0'), le=Decimal('100')) | None = Field(None, alias='slippagePct', description="Maximum acceptable slippage percentage. Defaults to the connector's configured slippagePct.", examples=[1])


class AmmPoolInfoRequest(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    connector: str = Field(..., description='AMM connector', examples=['meteora'])
    chain_network: str = Field(..., alias='chainNetwork', description='Chain and network in format: chain-network (e.g., solana-mainnet-beta, ethereum-mainnet)', examples=['solana-mainnet-beta'])
    pool_address: str = Field(..., alias='poolAddress', description='Pool contract address')


class AmmPositionInfoRequest(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    connector: str = Field(..., description='AMM connector', examples=['meteora'])
    chain_network: str = Field(..., alias='chainNetwork', description='Chain and network in format: chain-network (e.g., solana-mainnet-beta, ethereum-mainnet)', examples=['solana-mainnet-beta'])
    pool_address: str = Field(..., alias='poolAddress', description='Pool contract address')
    wallet_address: str = Field(..., alias='walletAddress', description='Wallet address')


class AmmPositionsOwnedRequest(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    connector: str = Field(..., description='AMM connector (only non-fungible-LP AMMs supported: meteora)', examples=['meteora'])
    chain_network: str = Field(..., alias='chainNetwork', description='Chain and network in format: chain-network (e.g., solana-mainnet-beta, ethereum-mainnet)', examples=['solana-mainnet-beta'])
    wallet_address: str = Field(..., alias='walletAddress', description='Wallet address to list positions for')


class AmmQuoteLiquidityRequest(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    connector: str = Field(..., description='AMM connector', examples=['meteora'])
    chain_network: str = Field(..., alias='chainNetwork', description='Chain and network in format: chain-network (e.g., solana-mainnet-beta, ethereum-mainnet)', examples=['solana-mainnet-beta'])
    pool_address: str = Field(..., alias='poolAddress', description='Pool contract address')
    base_token_amount: Decimal = Field(..., alias='baseTokenAmount', description='Amount of base token to deposit')
    quote_token_amount: Decimal = Field(..., alias='quoteTokenAmount', description='Amount of quote token to deposit')
    slippage_pct: condecimal(ge=Decimal('0'), le=Decimal('100')) | None = Field(None, alias='slippagePct', description="Maximum acceptable slippage percentage. Defaults to the connector's configured slippagePct.", examples=[1])


class ClmmOpenRequest(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    connector: str = Field(..., description='CLMM connector', examples=['meteora'])
    chain_network: str = Field(..., alias='chainNetwork', description='Chain and network in format: chain-network (e.g., solana-mainnet-beta, ethereum-mainnet)', examples=['solana-mainnet-beta'])
    wallet_address: str = Field(..., alias='walletAddress', description='Wallet address')
    lower_price: Decimal = Field(..., alias='lowerPrice', description='Lower price bound for the position', examples=[150])
    upper_price: Decimal = Field(..., alias='upperPrice', description='Upper price bound for the position', examples=[250])
    pool_address: str = Field(..., alias='poolAddress', description='Pool address', examples=['2sf5NYcY4zUPXUSmG6f66mskb24t5F8S11pC1Nz5nQT3'])
    base_token_amount: Decimal | None = Field(None, alias='baseTokenAmount', description='Amount of base token to deposit', examples=[0.01])
    quote_token_amount: Decimal | None = Field(None, alias='quoteTokenAmount', description='Amount of quote token to deposit', examples=[2])
    slippage_pct: condecimal(ge=Decimal('0'), le=Decimal('100')) | None = Field(None, alias='slippagePct', description="Maximum acceptable slippage percentage. Defaults to the connector's configured slippagePct.", examples=[1])
    strategy_type: float | None = Field(None, alias='strategyType', description='Strategy type for Meteora positions (0=Spot, 1=Curve). Only applies to Meteora connector.', examples=[0])


class ClmmAddRequest(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    connector: str = Field(..., description='CLMM connector', examples=['meteora'])
    chain_network: str = Field(..., alias='chainNetwork', description='Chain and network in format: chain-network (e.g., solana-mainnet-beta, ethereum-mainnet)', examples=['solana-mainnet-beta'])
    wallet_address: str = Field(..., alias='walletAddress', description='Wallet address')
    position_address: str = Field(..., alias='positionAddress', description='Position address', examples=['<sample-position-address>'])
    base_token_amount: Decimal | None = Field(None, alias='baseTokenAmount', description='Amount of base token to deposit (omit for single-sided quote deposit)', examples=[0.01])
    quote_token_amount: Decimal | None = Field(None, alias='quoteTokenAmount', description='Amount of quote token to deposit (omit for single-sided base deposit)', examples=[2])
    slippage_pct: condecimal(ge=Decimal('0'), le=Decimal('100')) | None = Field(None, alias='slippagePct', description="Maximum acceptable slippage percentage. Defaults to the connector's configured slippagePct.", examples=[1])
    strategy_type: float | None = Field(None, alias='strategyType', description='Strategy type for Meteora positions (0=Spot, 1=Curve). Only applies to Meteora connector.', examples=[0])


class ClmmRemoveRequest(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    connector: str = Field(..., description='CLMM connector', examples=['meteora'])
    chain_network: str = Field(..., alias='chainNetwork', description='Chain and network in format: chain-network (e.g., solana-mainnet-beta, ethereum-mainnet)', examples=['solana-mainnet-beta'])
    wallet_address: str = Field(..., alias='walletAddress', description='Wallet address')
    position_address: str = Field(..., alias='positionAddress', description='Position address', examples=['<sample-position-address>'])
    percentage_to_remove: condecimal(ge=Decimal('0'), le=Decimal('100')) = Field(..., alias='percentageToRemove', description='Percentage of liquidity to remove', examples=[100])
    slippage_pct: condecimal(ge=Decimal('0'), le=Decimal('100')) | None = Field(None, alias='slippagePct', description="Maximum acceptable slippage percentage. Honored by orca, uniswap and pancakeswap; the other connectors remove at their configured slippagePct. Defaults to the connector's configured slippagePct.", examples=[1])


class ClmmCollectFeesRequest(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    connector: str = Field(..., description='CLMM connector', examples=['meteora'])
    chain_network: str = Field(..., alias='chainNetwork', description='Chain and network in format: chain-network (e.g., solana-mainnet-beta, ethereum-mainnet)', examples=['solana-mainnet-beta'])
    wallet_address: str = Field(..., alias='walletAddress', description='Wallet address')
    position_address: str = Field(..., alias='positionAddress', description='Position address', examples=['<sample-position-address>'])


class ClmmCloseRequest(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    connector: str = Field(..., description='CLMM connector', examples=['meteora'])
    chain_network: str = Field(..., alias='chainNetwork', description='Chain and network in format: chain-network (e.g., solana-mainnet-beta, ethereum-mainnet)', examples=['solana-mainnet-beta'])
    wallet_address: str = Field(..., alias='walletAddress', description='Wallet address')
    position_address: str = Field(..., alias='positionAddress', description='Position address', examples=['<sample-position-address>'])
    slippage_pct: condecimal(ge=Decimal('0'), le=Decimal('100')) | None = Field(None, alias='slippagePct', description="Maximum acceptable slippage percentage for the withdrawal. Enforced by orca, uniswap and pancakeswap; meteora, raydium and pancakeswap-sol close with no minimum-amount check at all, so it changes nothing there. Defaults to the connector's configured slippagePct.", examples=[1])


class ClmmCreatePoolRequest(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    connector: str = Field(..., description='CLMM connector', examples=['meteora'])
    chain_network: str = Field(..., alias='chainNetwork', description='Chain and network in format: chain-network (e.g., solana-mainnet-beta, ethereum-mainnet)', examples=['solana-mainnet-beta'])
    wallet_address: str = Field(..., alias='walletAddress', description='Wallet address (pool creator + payer)')
    base_token: str = Field(..., alias='baseToken')
    quote_token: str = Field(..., alias='quoteToken')
    initial_price: Decimal | None = Field(None, alias='initialPrice', description='Initial pool price as quote per base. If omitted, the current market price is fetched from the unified swap router so the pool opens on-market.')
    bin_step: float | None = Field(None, alias='binStep', description='Bin/tick granularity: Meteora DLMM bin step (bps); Orca Whirlpool tick spacing.')
    fee_bps: float | None = Field(None, alias='feeBps', description='Base fee in basis points: Meteora DLMM base fee; Uniswap/PancakeSwap V3 fee tier (1, 5, 30 or 100 bps; PancakeSwap also 25).')
    amm_config_index: float | None = Field(None, alias='ammConfigIndex', description='Fee-config index for the Raydium CLMM family: Raydium API config list index; pancakeswap-sol amm_config PDA index. Default 0.')


class ClmmFetchPoolsRequest(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    chain_network: str = Field(..., alias='chainNetwork', description='Chain and network in format: chain-network (e.g., solana-mainnet-beta, ethereum-mainnet)', examples=['solana-mainnet-beta'])
    connector: str = Field(..., description='CLMM connector whose pool-discovery API to query', examples=['meteora'])
    limit: confloat(ge=1.0, le=1000.0) | None = Field(50, description='Maximum number of pools to return')
    query: str | None = Field(None, description='Search pools by name, token, or address', examples=['SOL'])
    sort_by: str | None = Field(None, alias='sortBy', description='Sort field. Meteora takes a "field:direction" pair; Orca takes the field alone with sortDirection.', examples=['tvl'])
    page: confloat(ge=0.0) | None = Field(None, description='0-based page index. Only connectors whose API paginates honor this.')
    include_unverified: bool | None = Field(None, alias='includeUnverified', description='Include unverified pools')
    sort_direction: str | None = Field(None, alias='sortDirection', description='Sort direction')
    verified_only: bool | None = Field(None, alias='verifiedOnly', description='Return only verified pools')


class ClmmPoolInfoRequest(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    connector: str = Field(..., description='CLMM connector', examples=['meteora'])
    chain_network: str = Field(..., alias='chainNetwork', description='Chain and network in format: chain-network (e.g., solana-mainnet-beta, ethereum-mainnet)', examples=['solana-mainnet-beta'])
    pool_address: str = Field(..., alias='poolAddress', description='Pool contract address', examples=['2sf5NYcY4zUPXUSmG6f66mskb24t5F8S11pC1Nz5nQT3'])
    bin_count: conint(ge=0, le=401) | None = Field(0, alias='binCount', description='If > 0, include a `bins` array of per-tick liquidity around the active tick. Supported by every connector except Meteora, which always returns its bins and ignores this. Default 0 = skip the bin fetch.')


class ClmmPositionInfoRequest(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    connector: str = Field(..., description='CLMM connector', examples=['meteora'])
    chain_network: str = Field(..., alias='chainNetwork', description='Chain and network in format: chain-network (e.g., solana-mainnet-beta, ethereum-mainnet)', examples=['solana-mainnet-beta'])
    position_address: str = Field(..., alias='positionAddress', description='Position address or NFT token ID', examples=['<sample-position-address>'])


class ClmmPositionsOwnedRequest(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    connector: str = Field(..., description='CLMM connector', examples=['meteora'])
    chain_network: str = Field(..., alias='chainNetwork', description='Chain and network in format: chain-network (e.g., solana-mainnet-beta, ethereum-mainnet)', examples=['solana-mainnet-beta'])
    wallet_address: str = Field(..., alias='walletAddress', description='Wallet address')


class ClmmQuoteLiquidityRequest(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    connector: str = Field(..., description='CLMM connector', examples=['meteora'])
    chain_network: str = Field(..., alias='chainNetwork', description='Chain and network in format: chain-network (e.g., solana-mainnet-beta, ethereum-mainnet)', examples=['solana-mainnet-beta'])
    lower_price: Decimal = Field(..., alias='lowerPrice', description='Lower price bound for the position', examples=[150])
    upper_price: Decimal = Field(..., alias='upperPrice', description='Upper price bound for the position', examples=[250])
    pool_address: str = Field(..., alias='poolAddress', description='Pool contract address', examples=['2sf5NYcY4zUPXUSmG6f66mskb24t5F8S11pC1Nz5nQT3'])
    base_token_amount: Decimal | None = Field(None, alias='baseTokenAmount', description='Amount of base token to deposit', examples=[0.01])
    quote_token_amount: Decimal | None = Field(None, alias='quoteTokenAmount', description='Amount of quote token to deposit', examples=[2])
    slippage_pct: condecimal(ge=Decimal('0'), le=Decimal('100')) | None = Field(None, alias='slippagePct', description="Maximum acceptable slippage percentage. Defaults to the connector's configured slippagePct.", examples=[1])


class RouterExecuteQuoteRequest(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    chain_network: str = Field(..., alias='chainNetwork', description='Chain and network in format: chain-network (e.g., solana-mainnet-beta, ethereum-mainnet)', examples=['solana-mainnet-beta'])
    connector: str | None = Field(None, description="Router connector. Defaults to the network's swapProvider", examples=['jupiter'])
    wallet_address: str = Field(..., alias='walletAddress', description='Wallet address that will execute the quote')
    quote_id: str = Field(..., alias='quoteId', description='ID of a quote returned by /trading/router/quote-swap')


class RouterExecuteSwapRequest(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    chain_network: str = Field(..., alias='chainNetwork', description='Chain and network in format: chain-network (e.g., solana-mainnet-beta, ethereum-mainnet)', examples=['solana-mainnet-beta'])
    connector: str | None = Field(None, description="Router connector. Defaults to the network's swapProvider", examples=['jupiter'])
    wallet_address: str = Field(..., alias='walletAddress', description='Wallet address that will execute the swap')
    base_token: str = Field(..., alias='baseToken', description='Symbol or address of the base token')
    quote_token: str = Field(..., alias='quoteToken', description='Symbol or address of the quote token')
    amount: Decimal = Field(..., description='Amount of base token to trade')
    side: str = Field(..., description='BUY means buying base token with quote token, SELL means selling base token for quote token')
    slippage_pct: condecimal(ge=Decimal('0'), le=Decimal('100')) | None = Field(None, alias='slippagePct', description="Maximum acceptable slippage percentage. Defaults to the connector's configured slippagePct.", examples=[1])
    approximate_if_no_exact_out: bool | None = Field(True, alias='approximateIfNoExactOut', description='For BUY orders when the router has no ExactOut route: approximate via a sell-leg ExactIn swap instead of failing.')


class RouterQuoteSwapRequest(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    chain_network: str = Field(..., alias='chainNetwork', description='Chain and network in format: chain-network (e.g., solana-mainnet-beta, ethereum-mainnet)', examples=['solana-mainnet-beta'])
    connector: str | None = Field(None, description="Router connector. Defaults to the network's swapProvider", examples=['jupiter'])
    base_token: str = Field(..., alias='baseToken', description='Symbol or address of the base token')
    quote_token: str = Field(..., alias='quoteToken', description='Symbol or address of the quote token')
    amount: Decimal = Field(..., description='Amount of base token to trade')
    side: str = Field(..., description='BUY means buying base token with quote token, SELL means selling base token for quote token')
    slippage_pct: condecimal(ge=Decimal('0'), le=Decimal('100')) | None = Field(None, alias='slippagePct', description="Maximum acceptable slippage percentage. Defaults to the connector's configured slippagePct.", examples=[1])
    wallet_address: str | None = Field(None, alias='walletAddress', description='Taker the quote is priced for. Required by routers that quote per-wallet or return wallet-specific calldata.')
    approximate_if_no_exact_out: bool | None = Field(True, alias='approximateIfNoExactOut', description='For BUY orders when the router has no ExactOut route: approximate via a sell-leg ExactIn quote instead of failing.')
    indicative_price: bool | None = Field(None, alias='indicativePrice', description='Return an indicative price instead of a firm, executable quote. An indicative quote cannot be executed with /trading/router/execute-quote.')


class AmmQuoteSwapRequest(BaseModel):
    chain_network: str = Field(..., alias='chainNetwork', description='Chain and network in format: chain-network (e.g., solana-mainnet-beta, ethereum-mainnet)', examples=['solana-mainnet-beta'])
    connector: str | None = Field('meteora', description='AMM connector to price the swap against', examples=['meteora'])
    base_token: str = Field(..., alias='baseToken', description='Symbol or address of the base token')
    quote_token: str = Field(..., alias='quoteToken', description='Symbol or address of the quote token')
    amount: Decimal = Field(..., description='Amount of base token to trade')
    side: str = Field(..., description='BUY means buying base token with quote token, SELL means selling base token for quote token')
    pool_address: str | None = Field(None, alias='poolAddress', description="Pool to trade against. Omit to resolve it from Gateway's configured pool list by token pair; pass an address to pin a pool that is not in that list.")
    slippage_pct: condecimal(ge=Decimal('0'), le=Decimal('100')) | None = Field(None, alias='slippagePct', description="Maximum acceptable slippage percentage. Defaults to the connector's configured slippagePct.", examples=[1])


class ClmmQuoteSwapRequest(BaseModel):
    chain_network: str = Field(..., alias='chainNetwork', description='Chain and network in format: chain-network (e.g., solana-mainnet-beta, ethereum-mainnet)', examples=['solana-mainnet-beta'])
    connector: str | None = Field('meteora', description='CLMM connector to price the swap against', examples=['meteora'])
    base_token: str = Field(..., alias='baseToken', description='Symbol or address of the base token')
    quote_token: str = Field(..., alias='quoteToken', description='Symbol or address of the quote token')
    amount: Decimal = Field(..., description='Amount of base token to trade')
    side: str = Field(..., description='BUY means buying base token with quote token, SELL means selling base token for quote token')
    pool_address: str | None = Field(None, alias='poolAddress', description="Pool to trade against. Omit to resolve it from Gateway's configured pool list by token pair; pass an address to pin a pool that is not in that list.")
    slippage_pct: condecimal(ge=Decimal('0'), le=Decimal('100')) | None = Field(None, alias='slippagePct', description="Maximum acceptable slippage percentage. Defaults to the connector's configured slippagePct.", examples=[1])


class AmmExecuteSwapRequest(BaseModel):
    chain_network: str = Field(..., alias='chainNetwork', description='Chain and network in format: chain-network (e.g., solana-mainnet-beta, ethereum-mainnet)', examples=['solana-mainnet-beta'])
    connector: str | None = Field('meteora', description='AMM connector to execute the swap against', examples=['meteora'])
    wallet_address: str = Field(..., alias='walletAddress', description='Wallet address that will execute the swap')
    base_token: str = Field(..., alias='baseToken', description='Symbol or address of the base token')
    quote_token: str = Field(..., alias='quoteToken', description='Symbol or address of the quote token')
    amount: Decimal = Field(..., description='Amount of base token to trade')
    side: str = Field(..., description='BUY means buying base token with quote token, SELL means selling base token for quote token')
    pool_address: str | None = Field(None, alias='poolAddress', description="Pool to trade against. Omit to resolve it from Gateway's configured pool list by token pair; pass an address to pin a pool that is not in that list.")
    slippage_pct: condecimal(ge=Decimal('0'), le=Decimal('100')) | None = Field(None, alias='slippagePct', description="Maximum acceptable slippage percentage. Defaults to the connector's configured slippagePct.", examples=[1])


class ClmmExecuteSwapRequest(BaseModel):
    chain_network: str = Field(..., alias='chainNetwork', description='Chain and network in format: chain-network (e.g., solana-mainnet-beta, ethereum-mainnet)', examples=['solana-mainnet-beta'])
    connector: str | None = Field('meteora', description='CLMM connector to execute the swap against', examples=['meteora'])
    wallet_address: str = Field(..., alias='walletAddress', description='Wallet address that will execute the swap')
    base_token: str = Field(..., alias='baseToken', description='Symbol or address of the base token')
    quote_token: str = Field(..., alias='quoteToken', description='Symbol or address of the quote token')
    amount: Decimal = Field(..., description='Amount of base token to trade')
    side: str = Field(..., description='BUY means buying base token with quote token, SELL means selling base token for quote token')
    pool_address: str | None = Field(None, alias='poolAddress', description="Pool to trade against. Omit to resolve it from Gateway's configured pool list by token pair; pass an address to pin a pool that is not in that list.")
    slippage_pct: condecimal(ge=Decimal('0'), le=Decimal('100')) | None = Field(None, alias='slippagePct', description="Maximum acceptable slippage percentage. Defaults to the connector's configured slippagePct.", examples=[1])


class AllowancesRequest(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    network: str | None = Field('mainnet', description='The Ethereum network to use')
    address: str | None = Field('<ethereum-wallet-address>', description='Ethereum wallet address')
    spender: str = Field(..., description='Connector name (e.g., uniswap/clmm, uniswap/amm, 0x/router) or contract address', examples=['uniswap/router'])
    tokens: list[str] = Field(..., description='Array of token symbols or addresses', examples=[['USDC', 'WETH']])


class AllowancesResponse(BaseModel):
    spender: str
    approvals: dict[str, str]


class ApproveRequest(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    network: str | None = Field('mainnet', description='The Ethereum network to use')
    address: str | None = Field('<ethereum-wallet-address>', description='Ethereum wallet address')
    spender: str = Field(..., description='Connector name (e.g., uniswap/clmm, uniswap/amm, 0x/router) contract address', examples=['uniswap/router'])
    token: str = Field(..., description='Token symbol or address', examples=['USDC'])
    amount: str | None = Field('', description='The amount to approve. If not provided, defaults to maximum amount (unlimited approval).')


class ApproveResponseData(BaseModel):
    token_address: str = Field(..., alias='tokenAddress')
    spender: str
    amount: str
    nonce: float
    fee: str


class RemoveWalletRequest(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    chain: str = Field(..., description='Blockchain to remove wallet from', examples=['solana'])
    address: str = Field(..., description='Wallet address to remove')


class AddHardwareWalletRequest(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    chain: str = Field(..., description='Blockchain for hardware wallet', examples=['solana'])
    address: str = Field(..., description='Hardware wallet address to add (must exist on connected Ledger device)')
    set_default: bool | None = Field(False, alias='setDefault', description='Set this wallet as the default for the chain')


class Token(BaseModel):
    chain_id: float | None = Field(None, alias='chainId', description='The chain ID', examples=[1])
    name: str = Field(..., description='The full name of the token', examples=['USD Coin'])
    symbol: str = Field(..., description='The token symbol', examples=['USDC'])
    address: str = Field(..., description='The token contract address', examples=['0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48'])
    decimals: confloat(ge=0.0, le=255.0) = Field(..., description='The number of decimals the token uses', examples=[6])


class ErrorResponse(BaseModel):
    status_code: int = Field(..., alias='statusCode', description='HTTP status code', examples=[400])
    error: str = Field(..., description='HTTP status name', examples=['Bad Request'])
    message: str = Field(..., description='What went wrong, in terms of the request that caused it', examples=["Connector 'meteora' runs on solana, not ethereum"])
    code: str | None = Field(None, description='Machine-readable cause, present when Gateway can name one. This is what a caller branches on: TRANSACTION_TIMEOUT and RATE_LIMITED are retryable, the rest are not.')


class AmmAddLiquidityResponse(BaseModel):
    signature: str
    status: float = Field(..., description='TransactionStatus enum value')
    data: AmmAddLiquidityResponseData | None = None


class AmmRemoveLiquidityResponse(BaseModel):
    signature: str
    status: float = Field(..., description='TransactionStatus enum value')
    data: AmmRemoveLiquidityResponseData | None = None


class AmmCreatePoolResponse(BaseModel):
    signature: str
    status: float = Field(..., description='TransactionStatus enum value')
    pool_address: str = Field(..., alias='poolAddress', description='Address of the newly created pool')
    price: Decimal | None = Field(None, description='Initial price the pool was seeded at (quote per base)')
    data: AmmCreatePoolResponseData | None = None


class ChainExecuteSwapResponse(BaseModel):
    signature: str = Field(..., description='Transaction signature/hash')
    status: float = Field(..., description='Transaction status: 0 = PENDING, 1 = CONFIRMED, -1 = FAILED')
    data: ChainExecuteSwapResponseData | None = None


class ChainWrapResponse(BaseModel):
    signature: str
    status: float = Field(..., description='TransactionStatus enum value')
    data: ChainWrapResponseData | None = None


class ClmmOpenPositionResponse(BaseModel):
    signature: str
    status: float = Field(..., description='TransactionStatus enum value')
    data: ClmmOpenPositionResponseData | None = None


class ClmmAddLiquidityResponse(BaseModel):
    signature: str
    status: float = Field(..., description='TransactionStatus enum value')
    data: ClmmAddLiquidityResponseData | None = None


class ClmmRemoveLiquidityResponse(BaseModel):
    signature: str
    status: float = Field(..., description='TransactionStatus enum value')
    data: ClmmRemoveLiquidityResponseData | None = None


class ClmmCollectFeesResponse(BaseModel):
    signature: str
    status: float = Field(..., description='TransactionStatus enum value')
    data: ClmmCollectFeesResponseData | None = None


class ClmmClosePositionResponse(BaseModel):
    signature: str
    status: float = Field(..., description='TransactionStatus enum value')
    data: ClmmClosePositionResponseData | None = None


class ClmmCreatePoolResponse(BaseModel):
    signature: str
    status: float = Field(..., description='TransactionStatus enum value')
    pool_address: str = Field(..., alias='poolAddress', description='Address of the newly created pool')
    price: Decimal | None = Field(None, description='Initial price the pool was initialized at (quote per base)')
    data: ClmmCreatePoolResponseData | None = None


class ApproveResponse(BaseModel):
    signature: str
    status: float = Field(..., description='TransactionStatus enum value')
    data: ApproveResponseData | None = None
