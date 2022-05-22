import { ethers } from "ethers";
import { Networkish } from "@ethersproject/networks";
import {
    Pool,
    getBestPoolAndOutput,
    exchangeExpected,
    exchangeIsApproved,
    exchangeApproveEstimateGas,
    exchangeApprove,
    exchangeEstimateGas,
    exchange,
    crossAssetExchangeAvailable,
    crossAssetExchangeOutputAndSlippage,
    crossAssetExchangeExpected,
    crossAssetExchangeIsApproved,
    crossAssetExchangeApproveEstimateGas,
    crossAssetExchangeApprove,
    crossAssetExchangeEstimateGas,
    crossAssetExchange,
    getUserPoolList,
    getBestRouteAndOutput,
    routerExchangeExpected,
    routerExchangeIsApproved,
    routerExchangeApproveEstimateGas,
    routerExchangeApprove,
    routerExchangeEstimateGas,
    routerExchange,
} from "./pools";
import { curve as _curve } from "./curve";
import {
    getCrv,
    getLockedAmountAndUnlockTime,
    getVeCrv,
    getVeCrvPct,
    createLockEstimateGas,
    createLock,
    isApproved,
    approveEstimateGas,
    approve,
    increaseAmountEstimateGas,
    increaseAmount,
    increaseUnlockTimeEstimateGas,
    increaseUnlockTime,
    withdrawLockedCrvEstimateGas,
    withdrawLockedCrv,
} from "./boosting";
import {
    getBalances,
    getAllowance,
    hasAllowance,
    ensureAllowanceEstimateGas,
    ensureAllowance,
    getPoolList,
    getFactoryPoolList,
    getCryptoFactoryPoolList,
    getUsdRate,
    getTVL,
} from "./utils";

async function init (
    providerType: 'JsonRpc' | 'Web3' | 'Infura' | 'Alchemy',
    providerSettings: { url?: string, privateKey?: string } | { externalProvider: ethers.providers.ExternalProvider } | { network?: Networkish, apiKey?: string },
    options: { gasPrice?: number, maxFeePerGas?: number, maxPriorityFeePerGas?: number, chainId?: number } = {}
): Promise<void> {
    await _curve.init(providerType, providerSettings, options);
    // @ts-ignore
    this.signerAddress = _curve.signerAddress;
    // @ts-ignore
    this.chainId = _curve.chainId;
}

async function fetchFactoryPools(useApi = true): Promise<void> {
    await _curve.fetchFactoryPools(useApi);
}

async function fetchCryptoFactoryPools(useApi = true): Promise<void> {
    await _curve.fetchCryptoFactoryPools(useApi);
}

function setCustomFeeData (customFeeData: { gasPrice?: number, maxFeePerGas?: number, maxPriorityFeePerGas?: number }): void {
    _curve.setCustomFeeData(customFeeData);
}

const curve = {
    init,
    fetchFactoryPools,
    fetchCryptoFactoryPools,
    getPoolList,
    getFactoryPoolList,
    getCryptoFactoryPoolList,
    getUsdRate,
    getTVL,
    setCustomFeeData,
    signerAddress: '',
    chainId: 0,
    Pool,
    getBalances,
    getAllowance,
    hasAllowance,
    ensureAllowance,
    getBestPoolAndOutput,
    exchangeExpected,
    exchangeIsApproved,
    exchangeApprove,
    exchange,
    crossAssetExchangeAvailable,
    crossAssetExchangeOutputAndSlippage,
    crossAssetExchangeExpected,
    crossAssetExchangeIsApproved,
    crossAssetExchangeApprove,
    crossAssetExchange,
    getUserPoolList,
    getBestRouteAndOutput,
    routerExchangeExpected,
    routerExchangeIsApproved,
    routerExchangeApprove,
    routerExchange,
    estimateGas: {
        ensureAllowance: ensureAllowanceEstimateGas,
        exchangeApprove: exchangeApproveEstimateGas,
        exchange: exchangeEstimateGas,
        crossAssetExchangeApprove: crossAssetExchangeApproveEstimateGas,
        crossAssetExchange: crossAssetExchangeEstimateGas,
        routerExchangeApprove: routerExchangeApproveEstimateGas,
        routerExchange: routerExchangeEstimateGas,
    },
    boosting: {
        getCrv,
        getLockedAmountAndUnlockTime,
        getVeCrv,
        getVeCrvPct,
        isApproved,
        approve,
        createLock,
        increaseAmount,
        increaseUnlockTime,
        withdrawLockedCrv,
        estimateGas: {
            approve: approveEstimateGas,
            createLock: createLockEstimateGas,
            increaseAmount: increaseAmountEstimateGas,
            increaseUnlockTime: increaseUnlockTimeEstimateGas,
            withdrawLockedCrv: withdrawLockedCrvEstimateGas,
        },
    },
}

export default curve;
