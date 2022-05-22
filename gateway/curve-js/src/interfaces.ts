import { Contract, ethers } from "ethers";
import { Contract as MulticallContract, Provider as MulticallProvider } from "ethcall";

export interface DictInterface<T> {
    [index: string]: T,
}

export interface ICurve {
    provider: ethers.providers.Web3Provider | ethers.providers.JsonRpcProvider,
    multicallProvider: MulticallProvider,
    signer: ethers.Signer | null,
    signerAddress: string,
    chainId: number,
    contracts: { [index: string]: { contract: Contract, multicallContract: MulticallContract } },
    feeData: { gasPrice?: number, maxFeePerGas?: number, maxPriorityFeePerGas?: number },
    constantOptions: { gasLimit: number },
    options: { gasPrice?: number | ethers.BigNumber, maxFeePerGas?: number | ethers.BigNumber, maxPriorityFeePerGas?: number | ethers.BigNumber },
    constants: DictInterface<any>;
}

export type REFERENCE_ASSET = 'USD' | 'EUR' | 'BTC' | 'ETH' | 'LINK' | 'CRYPTO' | 'OTHER';

export interface PoolDataInterface {
    name: string,
    full_name: string,
    symbol: string,
    reference_asset: REFERENCE_ASSET,
    N_COINS: number,
    underlying_decimals: number[],
    decimals: number[],
    tethered?: boolean[],
    use_lending: boolean[],
    is_plain: boolean[],
    has_eth?: boolean,
    is_aave?: boolean,
    is_new_underlying?: boolean,
    old_swap_address?: string,
    swap_address: string,
    token_address: string,
    gauge_address: string,
    old_token_address?: string,
    migration_address?: string,
    deposit_address?: string,
    underlying_coins: string[],
    coins: string[],
    underlying_coin_addresses: string[],
    coin_addresses: string[],
    swap_abi: any,
    gauge_abi: any,
    deposit_abi?: any,
    old_swap_abi?: any,
    is_meta?: boolean,
    is_fake?: boolean,
    is_crypto?: boolean,
    meta_N?: number,
    meta_decimals?: number[],
    meta_coin_decimals?: number[],
    meta_wrapped_decimals?: number[],
    base_pool?: string,
    meta_coin_addresses?: string[],
    all_coin_addresses?: string[],
    is_factory?: boolean,
    is_plain_factory?: boolean,
    is_meta_factory?: boolean,
    is_crypto_factory?: boolean,
    adapter_abi?: any,
    old_adapter_address?: string,
    adapter_biconomy_address?: string,
    adapter_address?: string,
    migration_abi?: any,
    sCurveRewards_abi?: any,
    sCurveRewards_address?: string,
    aRewards_abi?: any,
    aRewards_address?: string,
    reward_token?: string,
    reward_tokens?: string[],
    pool_type?: string,
    reward_contract?: string,
}

export interface ICoinFromPoolDataApi {
    address: string,
    symbol: string,
    decimals: string,
    usdPrice: number | string,
}

export interface IPoolDataFromApi {
    id: string,
    name: string,
    symbol: string,
    assetTypeName: string,
    address: string,
    lpTokenAddress?: string,
    gaugeAddress?: string,
    implementation: string,
    implementationAddress: string,
    coins: ICoinFromPoolDataApi[],
    usdTotal: number,
}

export interface IExtendedPoolDataFromApi {
    poolData: IPoolDataFromApi[],
    tvl?: number,
    tvlAll: number,
}

export interface RewardsApyInterface {
    token: string,
    symbol: string,
    apy: string,
}

export interface IPoolStats {
    volume: number,
    apy: {
        day: number,
        week: number,
        month: number,
        total: number,
    }
}

export interface IStats {
    [index: string]: IPoolStats
}

export interface ISinglePoolSwapData {
    poolName: string,
    poolAddress: string,
    i: number,
    j: number,
    swapType: 1 | 2 | 3 | 4 | 5,
    swapAddress: string,  // for swapType == 4
}

export interface ISinglePoolSwapDataAndOutput extends ISinglePoolSwapData {
    _output: ethers.BigNumber,
}

export interface IRouteStep {
    poolId: string,
    poolAddress: string,
    outputCoinAddress: string,
    i: number,
    j: number,
    swapType: 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10,
    swapAddress: string,  // for swapType == 4
}

export interface IRoute {
    steps: IRouteStep[],
    _output: ethers.BigNumber,
    outputUsd: number,
    txCostUsd: number,
}
