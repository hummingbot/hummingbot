import axios from 'axios';
import memoize from 'memoizee';
import { ethers } from 'ethers';
import BigNumber from 'bignumber.js';
import {DictInterface, IStats } from './interfaces';
import { curve, POOLS_DATA, LP_TOKENS, GAUGES } from "./curve";
import { COINS, DECIMALS_LOWER_CASE } from "./curve";
import { _getPoolsFromApi } from "./external-api";


const ETH_ADDRESS = '0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE';
export const MAX_ALLOWANCE = ethers.BigNumber.from(2).pow(ethers.BigNumber.from(256)).sub(ethers.BigNumber.from(1));

// bignumber.js

export const BN = (val: number | string): BigNumber => new BigNumber(val);

export const toBN = (n: ethers.BigNumber, decimals = 18): BigNumber => {
    return BN(ethers.utils.formatUnits(n, decimals));
}

export const toStringFromBN = (bn: BigNumber, decimals = 18): string => {
    return bn.toFixed(decimals);
}

export const fromBN = (bn: BigNumber, decimals = 18): ethers.BigNumber => {
    return ethers.utils.parseUnits(toStringFromBN(bn, decimals), decimals)
}

// -------------------

export const isEth = (address: string): boolean => address.toLowerCase() === ETH_ADDRESS.toLowerCase();
export const getEthIndex = (addresses: string[]): number => addresses.map((address: string) => address.toLowerCase()).indexOf(ETH_ADDRESS.toLowerCase());

// coins can be either addresses or symbols
export const _getCoinAddresses = (...coins: string[] | string[][]): string[] => {
    if (coins.length == 1 && Array.isArray(coins[0])) coins = coins[0];
    coins = coins as string[];

    const coinAddresses = coins.map((c) => COINS[c.toLowerCase()] || c);
    const availableAddresses = [
        ...Object.keys(DECIMALS_LOWER_CASE).filter((c) => c !== COINS['snx']?.toLowerCase()),
        ...LP_TOKENS,
        ...GAUGES,
    ];
    for (const coinAddr of coinAddresses) {
        if (!availableAddresses.includes(coinAddr.toLowerCase())) throw Error(`Coin with address '${coinAddr}' is not available`);
    }
    return coinAddresses
}

export const _getCoinDecimals = (...coinAddresses: string[] | string[][]): number[] => {
    if (coinAddresses.length == 1 && Array.isArray(coinAddresses[0])) coinAddresses = coinAddresses[0];
    coinAddresses = coinAddresses as string[];

    return coinAddresses.map((coinAddr) => DECIMALS_LOWER_CASE[coinAddr.toLowerCase()] ?? 18);
}

export const _getBalances = async (coins: string[], addresses: string[]): Promise<DictInterface<string[]>> => {
    const coinAddresses = _getCoinAddresses(coins);
    const decimals = _getCoinDecimals(coinAddresses);

    const ethIndex = getEthIndex(coinAddresses);
    if (ethIndex !== -1) {
        coinAddresses.splice(ethIndex, 1);
    }

    const contractCalls = [];
    for (const coinAddr of coinAddresses) {
        contractCalls.push(...addresses.map((address: string) => curve.contracts[coinAddr].multicallContract.balanceOf(address)));
    }
    const _response: ethers.BigNumber[] = await curve.multicallProvider.all(contractCalls);

    if (ethIndex !== -1) {
        const ethBalances: ethers.BigNumber[] = [];
        for (const address of addresses) {
            ethBalances.push(await curve.provider.getBalance(address));
        }
        _response.splice(ethIndex * addresses.length, 0, ...ethBalances);
    }

    const _balances: DictInterface<ethers.BigNumber[]>  = {};
    addresses.forEach((address: string, i: number) => {
        _balances[address] = coins.map((_, j: number ) => _response[i + (j * addresses.length)]);
    });

    const balances: DictInterface<string[]>  = {};
    for (const address of addresses) {
        balances[address] = _balances[address].map((b, i: number ) => ethers.utils.formatUnits(b, decimals[i]));
    }

    return balances;
}

export const _prepareAddresses = (addresses: string[] | string[][]): string[] => {
    if (addresses.length == 1 && Array.isArray(addresses[0])) addresses = addresses[0];
    if (addresses.length === 0 && curve.signerAddress !== '') addresses = [curve.signerAddress];
    addresses = addresses as string[];

    return addresses.filter((val, idx, arr) => arr.indexOf(val) === idx)
}

export const getBalances = async (coins: string[], ...addresses: string[] | string[][]): Promise<DictInterface<string[]> | string[]> => {
    addresses = _prepareAddresses(addresses);
    const balances: DictInterface<string[]> = await _getBalances(coins, addresses);

    return addresses.length === 1 ? balances[addresses[0]] : balances
}


export const _getAllowance = async (coins: string[], address: string, spender: string): Promise<ethers.BigNumber[]> => {
    const _coins = [...coins]
    const ethIndex = getEthIndex(_coins);
    if (ethIndex !== -1) {
        _coins.splice(ethIndex, 1);

    }

    let allowance: ethers.BigNumber[];
    if (_coins.length === 1) {
        allowance = [await curve.contracts[_coins[0]].contract.allowance(address, spender)];
    } else {
        const contractCalls = _coins.map((coinAddr) => curve.contracts[coinAddr].multicallContract.allowance(address, spender));
        allowance = await curve.multicallProvider.all(contractCalls);
    }


    if (ethIndex !== -1) {
        allowance.splice(ethIndex, 0, MAX_ALLOWANCE);
    }

    return allowance;
}

// coins can be either addresses or symbols
export const getAllowance = async (coins: string[], address: string, spender: string): Promise<string[]> => {
    const coinAddresses = _getCoinAddresses(coins);
    const decimals = _getCoinDecimals(coinAddresses);
    const _allowance = await _getAllowance(coinAddresses, address, spender);

    return _allowance.map((a, i) => ethers.utils.formatUnits(a, decimals[i]))
}

// coins can be either addresses or symbols
export const hasAllowance = async (coins: string[], amounts: string[], address: string, spender: string): Promise<boolean> => {
    const coinAddresses = _getCoinAddresses(coins);
    const decimals = _getCoinDecimals(coinAddresses);
    const _allowance = await _getAllowance(coinAddresses, address, spender);
    const _amounts = amounts.map((a, i) => ethers.utils.parseUnits(a, decimals[i]));

    return _allowance.map((a, i) => a.gte(_amounts[i])).reduce((a, b) => a && b);
}

export const _ensureAllowance = async (coins: string[], amounts: ethers.BigNumber[], spender: string): Promise<string[]> => {
    const address = curve.signerAddress;
    const allowance: ethers.BigNumber[] = await _getAllowance(coins, address, spender);

    const txHashes: string[] = []
    for (let i = 0; i < allowance.length; i++) {
        if (allowance[i].lt(amounts[i])) {
            const contract = curve.contracts[coins[i]].contract;
            await curve.updateFeeData();
            if (allowance[i].gt(ethers.BigNumber.from(0))) {
                const gasLimit = (await contract.estimateGas.approve(spender, ethers.BigNumber.from(0), curve.constantOptions)).mul(130).div(100);
                txHashes.push((await contract.approve(spender, ethers.BigNumber.from(0), { ...curve.options, gasLimit })).hash);
            }
            const gasLimit = (await contract.estimateGas.approve(spender, MAX_ALLOWANCE, curve.constantOptions)).mul(130).div(100);
            txHashes.push((await contract.approve(spender, MAX_ALLOWANCE, { ...curve.options, gasLimit })).hash);
        }
    }

    return txHashes;
}

// coins can be either addresses or symbols
export const ensureAllowanceEstimateGas = async (coins: string[], amounts: string[], spender: string): Promise<number> => {
    const coinAddresses = _getCoinAddresses(coins);
    const decimals = _getCoinDecimals(coinAddresses);
    const _amounts = amounts.map((a, i) => ethers.utils.parseUnits(a, decimals[i]));
    const address = curve.signerAddress;
    const allowance: ethers.BigNumber[] = await _getAllowance(coinAddresses, address, spender);

    let gas = 0;
    for (let i = 0; i < allowance.length; i++) {
        if (allowance[i].lt(_amounts[i])) {
            const contract = curve.contracts[coinAddresses[i]].contract;
            if (allowance[i].gt(ethers.BigNumber.from(0))) {
                gas += (await contract.estimateGas.approve(spender, ethers.BigNumber.from(0), curve.constantOptions)).toNumber();
            }
            gas += (await contract.estimateGas.approve(spender, MAX_ALLOWANCE, curve.constantOptions)).toNumber();
        }
    }

    return gas
}

// coins can be either addresses or symbols
export const ensureAllowance = async (coins: string[], amounts: string[], spender: string): Promise<string[]> => {
    const coinAddresses = _getCoinAddresses(coins);
    const decimals = _getCoinDecimals(coinAddresses);
    const _amounts = amounts.map((a, i) => ethers.utils.parseUnits(a, decimals[i]));

    return await _ensureAllowance(coinAddresses, _amounts, spender)
}

export const getPoolNameBySwapAddress = (swapAddress: string): string => {
    return Object.entries(POOLS_DATA).filter(([_, poolData]) => poolData.swap_address.toLowerCase() === swapAddress.toLowerCase())[0][0];
}

export const _getUsdPricesFromApi = async (): Promise<DictInterface<number>> => {
    const network = curve.chainId === 137 ? "polygon" : "ethereum";
    const promises = [
        _getPoolsFromApi(network, "main"),
        _getPoolsFromApi(network, "crypto"),
        _getPoolsFromApi(network, "factory"),
        _getPoolsFromApi(network, "factory-crypto"),
    ];
    const allTypesExtendedPoolData = await Promise.all(promises);
    const priceDict: DictInterface<number> = {};

    for (const extendedPoolData of allTypesExtendedPoolData) {
        for (const pool of extendedPoolData.poolData) {
            for (const coin of pool.coins) {
                if (typeof coin.usdPrice === "number") priceDict[coin.address.toLowerCase()] = coin.usdPrice;
            }
        }
    }

    return priceDict
}

const _usdRatesCache: DictInterface<{ rate: number, time: number }> = {}
export const _getUsdRate = async (assetId: string): Promise<number> => {
    const pricesFromApi = await _getUsdPricesFromApi();
    if (assetId.toLowerCase() in pricesFromApi) return pricesFromApi[assetId.toLowerCase()];

    if (assetId === 'USD' || (curve.chainId === 137 && (assetId.toLowerCase() === COINS.am3crv.toLowerCase()))) return 1

    let chainName = {
        1: 'ethereum',
        137: 'polygon-pos',
        1337: 'ethereum',
    }[curve.chainId]

    if (chainName === undefined) {
        throw Error('curve object is not initialized')
    }

    assetId = {
        'EUR': COINS.eurt,
        'BTC': 'bitcoin',
        'ETH': 'ethereum',
        'LINK': 'link',
    }[assetId] || assetId
    assetId = isEth(assetId) ? "ethereum" : assetId.toLowerCase();

    // No EURT on Coingecko Polygon
    if (assetId.toLowerCase() === COINS.eurt.toLowerCase()) {
        chainName = 'ethereum';
        assetId = '0xC581b735A1688071A1746c968e0798D642EDE491'.toLowerCase(); // EURT Ethereum
    }

    if ((_usdRatesCache[assetId]?.time || 0) + 600000 < Date.now()) {
        const url = ['bitcoin', 'ethereum', 'link'].includes(assetId.toLowerCase()) ?
            `https://api.coingecko.com/api/v3/simple/price?ids=${assetId}&vs_currencies=usd` :
            `https://api.coingecko.com/api/v3/simple/token_price/${chainName}?contract_addresses=${assetId}&vs_currencies=usd`
        const response = await axios.get(url);
        try {
            _usdRatesCache[assetId] = {'rate': response.data[assetId]['usd'] ?? 1, 'time': Date.now()};
        } catch (err) { // TODO pay attention!
            _usdRatesCache[assetId] = {'rate': 1, 'time': Date.now()};
        }
    }

    return _usdRatesCache[assetId]['rate']
}

export const _getFactoryStatsUrl = (): string => {
    if (curve.chainId === 1 || curve.chainId === 1337) {
        return "https://curve-api-hplkiejxx-curvefi.vercel.app/api/getSubgraphData";
    } else if (curve.chainId === 137) {
        return "https://api.curve.fi/api/getFactoryAPYs-polygon"
    } else {
        throw Error(`Unsupported network id${curve.chainId}`)
    }
}

export const _getStatsUrl = (isCrypto = false): string => {
    if (curve.chainId === 1 || curve.chainId === 1337) {
        return isCrypto ? "https://stats.curve.fi/raw-stats-crypto/apys.json" : "https://stats.curve.fi/raw-stats/apys.json";
    } else if (curve.chainId === 137) {
        return "https://stats.curve.fi/raw-stats-polygon/apys.json"
    } else {
        throw Error(`Unsupported network id${curve.chainId}`)
    }
}

export const _getStats = memoize(
    async (statsUrl: string): Promise<IStats> => {
        const rawData = (await axios.get(statsUrl)).data;

        const data: IStats = {};
        Object.keys(rawData.apy.day).forEach((poolName) => {
            data[poolName] = {
                volume: rawData.volume[poolName] ?? 0,
                apy: {
                    day: rawData.apy.day[poolName],
                    week: rawData.apy.week[poolName],
                    month: rawData.apy.month[poolName],
                    total: rawData.apy.total[poolName],
                },
            }
        })

        return data
    },
    {
        promise: true,
        maxAge: 10 * 60 * 1000, // 10m
    }
)

export const _getFactoryStatsEthereum = memoize(
    async (statsUrl: string): Promise<IStats> => {
        const rawData = (await axios.get(statsUrl)).data.data.poolList;
        const data: IStats = {};
        rawData.forEach((item: { address: string, volumeUSD: number, latestDailyApy: number | null, latestWeeklyApy: number | null }) => {
            data[item.address.toLowerCase()] = {
                volume: item.volumeUSD ?? 0,
                apy: {
                    day: item.latestDailyApy ?? 0,
                    week: item.latestWeeklyApy ?? 0,
                    month: item.latestWeeklyApy ?? 0,
                    total: item.latestWeeklyApy ?? 0,
                },
            }
        })

        return data;
    },
    {
        promise: true,
        maxAge: 10 * 60 * 1000, // 10m
    }
)

export const _getFactoryStatsPolygon = memoize(
    async (statsUrl: string): Promise<IStats> => {
        const rawData = (await axios.get(statsUrl)).data.data.poolDetails;
        const data: IStats = {};
        rawData.forEach((item: { poolAddress: string, volume: number, apy: number }) => {
            data[item.poolAddress.toLowerCase()] = {
                volume: item.volume ?? 0,
                apy: {
                    day: item.apy ?? 0,
                    week: item.apy ?? 0,
                    month: item.apy ?? 0,
                    total: item.apy ?? 0,
                },
            }
        })

        return data;
    },
    {
        promise: true,
        maxAge: 10 * 60 * 1000, // 10m
    }
)

export const getPoolList = (): string[] => Object.keys(POOLS_DATA);

export const getFactoryPoolList = (): string[] => Object.keys(curve.constants.FACTORY_POOLS_DATA);

export const getCryptoFactoryPoolList = (): string[] => Object.keys(curve.constants.CRYPTO_FACTORY_POOLS_DATA);

export const getUsdRate = async (coin: string): Promise<number> => {
    const [coinAddress] = _getCoinAddresses(coin);
    return await _getUsdRate(coinAddress);
}

export const getTVL = async (chainId = curve.chainId): Promise<number> => {
    const network = chainId === 137 ? "polygon" : "ethereum";

    const promises = [
        _getPoolsFromApi(network, "main"),
        _getPoolsFromApi(network, "crypto"),
        _getPoolsFromApi(network, "factory"),
        _getPoolsFromApi(network, "factory-crypto"),
    ];
    const allTypesExtendedPoolData = await Promise.all(promises);

    return allTypesExtendedPoolData.reduce((sum, data) => sum + (data.tvl ?? data.tvlAll), 0)
}