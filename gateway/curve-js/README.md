# Curve JS

## Setup

Install from npm:

`npm install @curvefi/api`

## Init
```ts
import curve from "@curvefi/api";

(async () => {
    // 1. Dev
    await curve.init('JsonRpc', {url: 'http://localhost:8545/', privateKey: ''}, { gasPrice: 0, maxFeePerGas: 0, maxPriorityFeePerGas: 0, chainId: 1 });
    // OR
    await curve.init('JsonRpc', {}, { chainId: 1 }); // In this case fee data will be specified automatically

    // 2. Infura
    curve.init("Infura", { network: "homestead", apiKey: <INFURA_KEY> }, { chainId: 1 });
    
    // 3. Web3 provider
    curve.init('Web3', { externalProvider: <WEB3_PROVIDER> }, { chainId: 1 });
})()
```
**Note 1.** ```chainId``` parameter is optional, but you must specify it in the case you use Metamask on localhost network, because Metamask has that [bug](https://hardhat.org/metamask-issue.html)

**Note 2.** Web3 init requires the address. Therefore, it can be initialized only after receiving the address.

**Wrong ❌️**
```tsx
import type { FunctionComponent } from 'react'
import { useState, useMemo } from 'react'
import { providers } from 'ethers'
import Onboard from 'bnc-onboard'
import type { Wallet } from 'bnc-onboard/dist/src/interfaces'
import curve from '@curvefi/api'

    ...

const WalletProvider: FunctionComponent = ({ children }) => {
    const [wallet, setWallet] = useState<Wallet>()
    const [provider, setProvider] = useState<providers.Web3Provider>()
    const [address, setAddress] = useState<string>()

    const networkId = 1

    const onboard = useMemo(
        () =>
            Onboard({
                dappId: DAPP_ID,
                networkId,

                subscriptions: {
                    address: (address) => {
                        setAddress(address)
                    },

                    wallet: (wallet) => {
                        setWallet(wallet)
                        if (wallet.provider) {
                            curve.init("Web3", { externalProvider: wallet.provider }, { chainId: networkId })
                        }
                    },
                },
                walletSelect: {
                    wallets: wallets,
                },
            }),
        []
    )

    ...
```

**Right ✔️**
```tsx
import type { FunctionComponent } from 'react'
import { useState, useMemo, useEffect } from 'react'
import { providers } from 'ethers'
import Onboard from 'bnc-onboard'
import type { Wallet } from 'bnc-onboard/dist/src/interfaces'
import curve from '@curvefi/api'

    ...

const WalletProvider: FunctionComponent = ({ children }) => {
    const [wallet, setWallet] = useState<Wallet>()
    const [provider, setProvider] = useState<providers.Web3Provider>()
    const [address, setAddress] = useState<string>()

    const networkId = 1

    const onboard = useMemo(
        () =>
            Onboard({
                dappId: DAPP_ID,
                networkId,

                subscriptions: {
                    address: (address) => {
                        setAddress(address)
                    },

                    wallet: (wallet) => {
                        setWallet(wallet)
                    },
                },
                walletSelect: {
                    wallets: wallets,
                },
            }),
        []
    )

    useEffect(() => {
        if (address && wallet?.provider) {
            curve.init("Web3", { externalProvider: wallet.provider }, { chainId: networkId })
        }
    }, [address, wallet?.provider]);

    ...
```

## Available pools
```ts
import curve from "@curvefi/api";

(async () => {
    await curve.init('JsonRpc', {}, {gasPrice: 0, maxFeePerGas: 0, maxPriorityFeePerGas: 0});

    console.log(curve.getPoolList());
    // [
    //     'compound', 'usdt',   'y',          'busd',
    //     'susd',     'pax',    'ren',        'sbtc',
    //     'hbtc',     '3pool',  'gusd',       'husd',
    //     'usdk',     'usdn',   'musd',       'rsv',
    //     'tbtc',     'dusd',   'pbtc',       'bbtc',
    //     'obtc',     'seth',   'eurs',       'ust',
    //     'aave',     'steth',  'saave',      'ankreth',
    //     'usdp',     'ib',     'link',       'tusd',
    //     'frax',     'lusd',   'busdv2',     'reth',
    //     'alusd',    'mim',    'tricrypto2', 'eurt',
    //     'eurtusd',  'crveth', 'cvxeth'
    // ]
})()
````

## Balances
```ts
import curve from "@curvefi/api";

(async () => {
    await curve.init('JsonRpc', {}, { gasPrice: 0, maxFeePerGas: 0, maxPriorityFeePerGas: 0 });

    console.log(await curve.getBalances(['DAI', 'sUSD']));
    // OR console.log(await curve.getBalances(['0x6B175474E89094C44Da98b954EedeAC495271d0F', '0x57Ab1ec28D129707052df4dF418D58a2D46d5f51']));
    
    // [ '10000.0', '10000.0' ]

    console.log(await curve.getBalances(['aDAI', 'aSUSD']));
    // OR console.log(await curve.getBalances(['0x028171bCA77440897B824Ca71D1c56caC55b68A3', '0x6c5024cd4f8a59110119c56f8933403a539555eb']));

    // [ '10000.00017727177059715', '10000.000080108429034461' ]


    // --- Pool ---

    const saave = new curve.Pool('saave');
    
    // 1. Current address balances (signer balances)
    
    console.log(await saave.balances());
    // {
    //     lpToken: '0.0',
    //     gauge: '0.0',
    //     '0x6B175474E89094C44Da98b954EedeAC495271d0F': '10000.0',
    //     '0x57Ab1ec28D129707052df4dF418D58a2D46d5f51': '10000.0',
    //     '0x028171bCA77440897B824Ca71D1c56caC55b68A3': '10000.00017727177059715',
    //     '0x6c5024cd4f8a59110119c56f8933403a539555eb': '10000.000080108429034461'
    // }

    console.log(await saave.lpTokenBalances());
    // { lpToken: '0.0', gauge: '0.0' }
    
    console.log(await saave.underlyingCoinBalances());
    // {
    //     '0x6B175474E89094C44Da98b954EedeAC495271d0F': '10000.0',
    //     '0x57Ab1ec28D129707052df4dF418D58a2D46d5f51': '10000.0'
    // }
    
    console.log(await saave.coinBalances());
    // {
    //     '0x028171bCA77440897B824Ca71D1c56caC55b68A3': '10000.00017727177059715',
    //     '0x6c5024cd4f8a59110119c56f8933403a539555eb': '10000.000080108429034461'
    // }
    
    console.log(await saave.allCoinBalances());
    // {
    //     '0x6B175474E89094C44Da98b954EedeAC495271d0F': '10000.0',
    //     '0x57Ab1ec28D129707052df4dF418D58a2D46d5f51': '10000.0',
    //     '0x028171bCA77440897B824Ca71D1c56caC55b68A3': '10000.00017727177059715',
    //     '0x6c5024cd4f8a59110119c56f8933403a539555eb': '10000.000080108429034461'
    // }


    // 2. For every method above you can specify the address
    
    console.log(await saave.balances("0x0063046686E46Dc6F15918b61AE2B121458534a5"));
    // {
    //     lpToken: '0.0',
    //     gauge: '0.0',
    //     '0x6B175474E89094C44Da98b954EedeAC495271d0F': '0.0',
    //     '0x57Ab1ec28D129707052df4dF418D58a2D46d5f51': '0.0',
    //     '0x028171bCA77440897B824Ca71D1c56caC55b68A3': '0.0',
    //     '0x6c5024cd4f8a59110119c56f8933403a539555eb': '0.0'
    // }

    // Or several addresses
    console.log(await saave.balances("0x0063046686E46Dc6F15918b61AE2B121458534a5", "0x66aB6D9362d4F35596279692F0251Db635165871"));
    // {
    //     '0x0063046686E46Dc6F15918b61AE2B121458534a5': {
    //         lpToken: '0.0',
    //         gauge: '0.0',
    //         '0x6B175474E89094C44Da98b954EedeAC495271d0F': '0.0',
    //         '0x57Ab1ec28D129707052df4dF418D58a2D46d5f51': '0.0',
    //         '0x028171bCA77440897B824Ca71D1c56caC55b68A3': '0.0',
    //         '0x6c5024cd4f8a59110119c56f8933403a539555eb': '0.0'
    //     },
    //     '0x66aB6D9362d4F35596279692F0251Db635165871': {
    //         lpToken: '0.0',
    //         gauge: '0.0',
    //         '0x6B175474E89094C44Da98b954EedeAC495271d0F': '10000.0',
    //         '0x57Ab1ec28D129707052df4dF418D58a2D46d5f51': '10000.0',
    //         '0x028171bCA77440897B824Ca71D1c56caC55b68A3': '10000.00017727177059715',
    //         '0x6c5024cd4f8a59110119c56f8933403a539555eb': '10000.000080108429034461'
    //     }
    // }


})()
```

## Stats
```ts
import curve from "@curvefi/api";

(async () => {
    await curve.init('JsonRpc', {}, {gasPrice: 0, maxFeePerGas: 0, maxPriorityFeePerGas: 0});
    
    console.log(await curve.getTVL());
    // 19281307454.671753

    const aave = new curve.Pool('aave');

    console.log(await aave.stats.getParameters());
    // {
    //     virtualPrice: '1.082056814810440924',
    //     fee: '0.04',
    //     adminFee: '0.02',
    //     A: '2000',
    //     future_A: '2000',
    //     initial_A: '200',
    //     future_A_time: 1628525830000,
    //     initial_A_time: 1627923611000,
    //     gamma: undefined
    // }


    console.log(await aave.stats.getPoolBalances());
    // [ '19619514.600802512613372364', '18740372.790339', '16065974.167437' ]
    
    console.log(await aave.stats.getPoolWrappedBalances());
    // [ '19619514.600802512613372364', '18740372.790339', '16065974.167437' ]
    
    console.log(await aave.stats.getTotalLiquidity());
    // 54425861.55857851
    
    console.log(await aave.stats.getVolume());
    // 175647.68180084194
    
    console.log(await aave.stats.getBaseApy());
    // { day: '3.2015', week: '3.1185', month: '3.1318', total: '7.7286' }
    
    console.log(await aave.stats.getTokenApy());
    // [ '0.4093', '1.0233' ]

    console.log(await aave.stats.getRewardsApy());
    // [
    //     {
    //         token: '0x4da27a545c0c5B758a6BA100e3a049001de870f5',
    //         symbol: 'stkAAVE',
    //         apy: '0.4978306501849664'
    //     }
    // ]
})()
````

## Add/remove liquidity

```ts
import curve from "@curvefi/api";

(async () => {
    await curve.init('JsonRpc', {}, { gasPrice: 0, maxFeePerGas: 0, maxPriorityFeePerGas: 0, chainId: 1 });

    const pool = new curve.Pool('aave');
    console.log(pool.underlyingCoins); // [ 'DAI', 'USDC', 'USDT' ]
    console.log(pool.coins); // [ 'aDAI', 'aUSDC', 'aUSDT' ]

    console.log(await pool.balances());
    //{
    //  lpToken: '0.0',
    //  gauge: '0.0',
    //  DAI: '1000.0',
    //  USDC: '1000.0',
    //  USDT: '1000.0',
    //  aDAI: '1000.000012756069187853',
    //  aUSDC: '1000.000005',
    //  aUSDT: '1000.0'
    //}


    // --- ADD LIQUIDITY ---
    
    const expectedLpTokenAmount1 = await pool.addLiquidityExpected(['100', '100', '100']);
    // 283.535915313504880343
    const tx = await pool.addLiquidity(['100', '100', '100']);
    console.log(tx); // 0x7aef5b13385207f1d311b7e5d485d4994a6520482e8dc682b5ef26e9addc53be

    //{
    //  lpToken: '283.531953275007017412',
    //  gauge: '0.0',
    //  DAI: '900.0',
    //  USDC: '900.0',
    //  USDT: '900.0',
    //  aDAI: '1000.000091543555348124',
    //  aUSDC: '1000.00007',
    //  aUSDT: '1000.000095'
    //}


    // --- ADD LIQUIDITY WRAPPED ---
    
    await pool.addLiquidityWrappedExpected(['100', '100', '100']);
    // 283.53589268907800207
    await pool.addLiquidityWrapped(['100', '100', '100']);
    
    //{
    //  lpToken: '567.06390438645751582',
    //  gauge: '0.0',
    //  DAI: '900.0',
    //  USDC: '900.0',
    //  USDT: '900.0',
    //  aDAI: '900.00009904712567354',
    //  aUSDC: '900.000077',
    //  aUSDT: '900.000104'
    //}

    
    // --- GAUGE DEPOSIT ---
    
    const lpTokenBalance = (await pool.balances())['lpToken'];
    await pool.gaugeDeposit(lpTokenBalance);
    
    //{
    //  lpToken: '0.0',
    //  gauge: '567.06390438645751582',
    //  DAI: '900.0',
    //  USDC: '900.0',
    //  USDT: '900.0',
    //  aDAI: '900.00009972244701026',
    //  aUSDC: '900.000077',
    //  aUSDT: '900.000105'
    //}


    // --- GAUGE WITHDRAW ---
    
    await pool.gaugeWithdraw(lpTokenBalance);

    //{
    //  lpToken: '567.06390438645751582',
    //  gauge: '0.0',
    //  DAI: '900.0',
    //  USDC: '900.0',
    //  USDT: '900.0',
    //  aDAI: '900.000116605480428249',
    //  aUSDC: '900.000091',
    //  aUSDT: '900.000125'
    //}


    // --- REMOVE LIQUIDITY ---
    
    await pool.removeLiquidityExpected('10');
    // [ '3.200409227699300211', '3.697305', '3.683197' ]
    await pool.removeLiquidity('10');

    //{
    //  lpToken: '557.06390438645751582',
    //  gauge: '0.0',
    //  DAI: '903.200409232502213136',
    //  USDC: '903.697304',
    //  USDT: '903.683196',
    //  aDAI: '900.000117956123101688',
    //  aUSDC: '900.000092',
    //  aUSDT: '900.000127'
    //}


    // --- REMOVE LIQUIDITY WRAPPED ---
    
    await pool.removeLiquidityWrappedExpected('10');
    // [ '3.200409232502213137', '3.697305', '3.683197' ]
    await pool.removeLiquidityWrapped('10');
    
    //{
    //  lpToken: '547.06390438645751582',
    //  gauge: '0.0',
    //  DAI: '903.200409232502213136',
    //  USDC: '903.697304',
    //  USDT: '903.683196',
    //  aDAI: '903.200529221793815936',
    //  aUSDC: '903.697398',
    //  aUSDT: '903.683325'
    //}


    // --- REMOVE LIQUIDITY IMBALANCE ---
    
    await pool.removeLiquidityImbalanceExpected(['10', '10', '10']);
    // 28.353588385263656951
    await pool.removeLiquidityImbalance(['10', '10', '10']);

    //{
    //  lpToken: '518.709923802845859288',
    //  gauge: '0.0',
    //  DAI: '913.200409232502213136',
    //  USDC: '913.697304',
    //  USDT: '913.683196',
    //  aDAI: '903.200530577239468989',
    //  aUSDC: '903.697399',
    //  aUSDT: '903.683327'
    //}


    // --- REMOVE LIQUIDITY IMBALANCE WRAPPED ---
    
    await pool.removeLiquidityImbalanceWrappedExpected(['10', '10', '10']);
    // 28.353588342257067439
    await pool.removeLiquidityImbalanceWrapped(['10', '10', '10']);
    
    //{
    //  lpToken: '490.355943262223785163',
    //  gauge: '0.0',
    //  DAI: '913.200409232502213136',
    //  USDC: '913.697304',
    //  USDT: '913.683196',
    //  aDAI: '913.200531932685151936',
    //  aUSDC: '913.6974',
    //  aUSDT: '913.683329'
    //}


    // --- REMOVE LIQUIDITY ONE COIN ---
    
    await pool.removeLiquidityOneCoinExpected('10','DAI');  // OR await pool.removeLiquidityOneCoinExpected('10', 0);
    // 10.573292542135201585 (DAI amount)
    await pool.removeLiquidityOneCoin('10', 'DAI');  // OR await pool.removeLiquidityOneCoin('10', 0);
    
    //{
    //  lpToken: '480.355943262223785163',
    //  gauge: '0.0',
    //  DAI: '923.773701782667764366',
    //  USDC: '913.697304',
    //  USDT: '913.683196',
    //  aDAI: '913.200532617911563408',
    //  aUSDC: '913.697401',
    //  aUSDT: '913.68333'
    //}


    // --- REMOVE LIQUIDITY ONE COIN WRAPPED ---
    
    await pool.removeLiquidityOneCoinWrappedExpected('10', 'aUSDC');  // OR await pool.removeLiquidityOneCoinWrappedExpected('10', 1);
    // 10.581285 (aUSDC amount)
    await pool.removeLiquidityOneCoinWrapped('10', 'aUSDC');  // OR await pool.removeLiquidityOneCoinWrapped('10', 1);
    
    //{
    //  lpToken: '470.355943262223785163',
    //  gauge: '0.0',
    //  DAI: '923.773701782667764366',
    //  USDC: '913.697304',
    //  USDT: '913.683196',
    //  aDAI: '913.200533988364413768',
    //  aUSDC: '924.278687',
    //  aUSDT: '913.683331'
    //}
})()
```

## Exchange

### Router exchange

```ts
import curve from "@curvefi/api";

(async () => {
    await curve.init('JsonRpc', {}, { gasPrice: 0, chainId: 1 });

    console.log(await curve.getBalances(['DAI', 'CRV']));
    // [ '9900.0', '100049.744832225238317557' ]

    const { route, output } = await curve.getBestRouteAndOutput('DAI', 'CRV', '1000');
    // OR await curve.getBestPoolAndOutput('0x6B175474E89094C44Da98b954EedeAC495271d0F', '0xD533a949740bb3306d119CC777fa900bA034cd52', '10000');
    const expected = await curve.routerExchangeExpected('DAI', 'CRV', '1000');
    // OR await curve.exchangeExpected('0x6B175474E89094C44Da98b954EedeAC495271d0F', '0xD533a949740bb3306d119CC777fa900bA034cd52', '10000');

    console.log(route, output, expected);
    // route = [
    //     {
    //         poolId: '3pool',
    //         poolAddress: '0xbEbc44782C7dB0a1A60Cb6fe97d0b483032FF1C7',
    //         outputCoinAddress: '0xdac17f958d2ee523a2206206994597c13d831ec7',
    //         i: 0,
    //         j: 2,
    //         swapType: 1,
    //         swapAddress: '0x0000000000000000000000000000000000000000'
    //     },
    //     {
    //         poolId: 'tricrypto2',
    //         poolAddress: '0xD51a44d3FaE010294C616388b506AcdA1bfAAE46',
    //         outputCoinAddress: '0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2',
    //         i: 0,
    //         j: 2,
    //         swapType: 3,
    //         swapAddress: '0x0000000000000000000000000000000000000000'
    //     },
    //     {
    //         poolId: 'crveth',
    //         poolAddress: '0x8301AE4fc9c624d1D396cbDAa1ed877821D7C511',
    //         outputCoinAddress: '0xd533a949740bb3306d119cc777fa900ba034cd52',
    //         i: 0,
    //         j: 1,
    //         swapType: 3,
    //         swapAddress: '0x0000000000000000000000000000000000000000'
    //     }
    // ]
    // 
    // output = expected = 378.881631202862354937

    await curve.routerExchange('DAI', 'CRV', '1000')
    // OR await curve.exchange('0x6B175474E89094C44Da98b954EedeAC495271d0F', '0xD533a949740bb3306d119CC777fa900bA034cd52', '10000');

    console.log(await curve.getBalances(['DAI', 'CRV']));
    // [ '8900.0', '100428.626463428100672494' ]
})()
```

### Single-pool exchange

```ts
import curve from "@curvefi/api";

(async () => {
    await curve.init('JsonRpc', {}, { gasPrice: 0, maxFeePerGas: 0, maxPriorityFeePerGas: 0, chainId: 1 });

    console.log(await curve.getBalances(['DAI', 'USDC']));
    // [ '1000.0', '0.0' ]

    const { poolAddress, output } = await curve.getBestPoolAndOutput('DAI', 'USDC', '100');
    // OR await curve.getBestPoolAndOutput('0x6B175474E89094C44Da98b954EedeAC495271d0F', '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', '100');
    const expected = await curve.exchangeExpected('DAI', 'USDC', '100');
    // OR await curve.exchangeExpected('0x6B175474E89094C44Da98b954EedeAC495271d0F', '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', '100');

    console.log(poolAddress, output, expected);
    // poolAddress = 0x79a8C46DeA5aDa233ABaFFD40F3A0A2B1e5A4F27, output = expected = 100.071099

    await curve.exchange('DAI', 'USDC', '10')
    // OR await curve.exchange('0x6B175474E89094C44Da98b954EedeAC495271d0F', '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', '100');

    console.log(await curve.getBalances(['DAI', 'USDC']));
    // [ '900.0', '100.071098' ]
})()
```

### Cross-Asset Exchange

```ts
import curve from "@curvefi/api";

(async () => {
    await curve.init('JsonRpc', {}, { gasPrice: 0, maxFeePerGas: 0, maxPriorityFeePerGas: 0, chainId: 1 });

    console.log(await curve.getBalances(['DAI', 'WBTC']));
    // [ '1000.0', '0.0' ]

    console.log(await curve.crossAssetExchangeAvailable('DAI', 'WBTC'));
    // true
    console.log(await curve.crossAssetExchangeOutputAndSlippage('DAI', 'WBTC', '500'));
    // { output: '0.01207752', slippage: 0.0000016559718476472085 }
    console.log(await curve.crossAssetExchangeExpected('DAI', 'WBTC', '500'));
    // 0.01207752

    const tx = await curve.crossAssetExchange('DAI', 'WBTC', '500');
    console.log(tx);
    // 0xf452fbb49d9e4ba8976dc6762bcfcc87d5e164577c21f3fa087ae4fe275d1710

    console.log(await curve.getBalances(['DAI', 'WBTC']));
    // [ '500.0', '0.01207752' ]
})()
```

## Boosting
```ts
import curve from "@curvefi/api";

(async () => {
    await curve.init('JsonRpc', {}, { gasPrice: 0, maxFeePerGas: 0, maxPriorityFeePerGas: 0, chainId: 1 });

    console.log(await curve.boosting.getCrv());
    // 100000.0

    await curve.boosting.createLock('1000', 365);
    // 99000.0 CRV
    
    console.log(await curve.boosting.getLockedAmountAndUnlockTime());
    // { lockedAmount: '1000.0', unlockTime: 1657152000000 }
    console.log(await curve.boosting.getVeCrv());
    // 248.193183980208499221
    console.log(await curve.boosting.getVeCrvPct());
    // 0.000006190640156035

    await curve.boosting.increaseAmount('500');

    // 98500.0 CRV
    // { lockedAmount: '1500.0', unlockTime: 1657152000000 }
    // 372.289692732093137414 veCRV
    // 0.000009285953543912 veCRV %


    await curve.boosting.increaseUnlockTime(365);

    // { lockedAmount: '1500.0', unlockTime: 1688601600000 }
    // 746.262271689452535192 veCRV
    // 0.000018613852077810 veCRV %
})()
```

## Allowance and approve
### General methods
```ts
const spender = "0xbEbc44782C7dB0a1A60Cb6fe97d0b483032FF1C7" // 3pool swap address

await curve.getAllowance(["DAI", "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"], curve.signerAddress, spender)
// [ '0.0', '0.0' ]
await curve.hasAllowance(["DAI", "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"], ['1000', '1000'], curve.signerAddress, spender)
// false
await curve.ensureAllowance(["DAI", "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"], ['1000', '1000'], spender)
// [
//     '0xb0cada2a2983dc0ed85a26916d32b9caefe45fecde47640bd7d0e214ff22aed3',
//     '0x00ea7d827b3ad50ce933e96c579810cd7e70d66a034a86ec4e1e10005634d041'
// ]

```

### Pools
```ts
const pool = new curve.Pool('usdn');

// --- Add Liquidity ---

await pool.addLiquidityIsApproved(["1000", "1000", "1000", "1000"])
// false
await pool.addLiquidityApprove(["1000", "1000", "1000", "1000"])
// [
//     '0xbac4b0271ad340488a8135dda2f9adf3e3c402361b514f483ba2b7e9cafbdc21',
//     '0x39fe196a52d9fb649f9c099fbd40ae773d28c457195c878ecdb7cd05be0f6512',
//     '0xf39ebfb4b11434b879f951a08a1c633a038425c35eae09b2b7015816d068de3c',
//     '0xa8b1631384da247efe1987b56fe010b852fc1d38e4d71d204c7dc5448a3a6c96'
// ]


// --- Add Liquidity Wrapped ---

await pool.addLiquidityWrappedIsApproved(["1000", "1000"])
// false
await pool.addLiquidityWrappedApprove(["1000", "1000"])
// [
//     '0xe486bfba5e9e8190be580ad528707876136e6b0c201e228db0f3bd82e51619fa',
//     '0xd56f7d583b20f4f7760510cc4310e3651f7dab8c276fe3bcde7e7200d65ed0dd'
// ]


// --- Remove Liquidity ---

await pool.removeLiquidityIsApproved("1000")
await pool.removeLiquidityApprove("1000")


// --- Remove Liquidity Imbalance ---

await pool.removeLiquidityImbalanceIsApproved(["1000", "1000", "1000", "1000"])
await pool.removeLiquidityImbalanceApprove(["1000", "1000", "1000", "1000"])


// --- Remove Liquidity One Coin ---

await pool.removeLiquidityOneCoinIsApproved("1000")
await pool.removeLiquidityOneCoinApprove("1000")


// --- Gauge Deposit ---

await pool.gaugeDepositIsApproved("1000")
await pool.gaugeDepositApprove("1000")


// --- Exchange ---

await pool.exchangeIsApproved("DAI", "1000")
await pool.exchangeApprove("DAI", "1000")


// --- Exchange Wrapped ---

await pool.exchangeWrappedIsApproved("0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490", "1000")
await pool.exchangeWrappedApprove("0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490", "1000")
```
**Note.** Removing wrapped does not require approve.

### Exchange
```ts
// Router
await curve.routerExchangeisApproved("DAI", "0x99d8a9c45b2eca8864373a26d1459e3dff1e17f3", "1000"); // DAI -> MIM
await curve.routerExchangeApprove("DAI", "0x99d8a9c45b2eca8864373a26d1459e3dff1e17f3", "1000"); // DAI -> MIM

// Straight
await curve.exchangeisApproved("DAI", "0x99d8a9c45b2eca8864373a26d1459e3dff1e17f3", "1000"); // DAI -> MIM
await curve.exchangeApprove("DAI", "0x99d8a9c45b2eca8864373a26d1459e3dff1e17f3", "1000"); // DAI -> MIM

// Cross-Asset
await curve.crossAssetExchangeIsApproved("DAI", "1000");
await curve.crossAssetExchangeApprove("DAI", "1000");
```

### Boosting
```ts
await curve.boosting.isApproved('1000')
await curve.boosting.approve('1000')
```

## Gas estimation
Every non-constant method has corresponding gas estimation method. Rule: ```obj.method -> obj.estimateGas.method```

**Examples**
```ts
const spender = "0xbEbc44782C7dB0a1A60Cb6fe97d0b483032FF1C7" // 3pool swap address
await curve.estimateGas.ensureAllowance(["DAI", "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"], curve.signerAddress, spender);

const pool = new curve.Pool('usdn');
await pool.estimateGas.addLiquidityApprove(["1000", "1000", "1000", "1000"])
await pool.estimateGas.addLiquidity(["1000", "1000", "1000", "1000"])

await curve.estimateGas.crossAssetExchange('DAI', "WBTC", "1000", 0.01)

await curve.boosting.estimateGas.createLock('1000', 365)
```

## Rewards
```ts
const pool = new curve.Pool('susd');

// CRV
console.log(await pool.gaugeClaimableTokens());
// 0.006296257916265276
await pool.gaugeClaimTokens();

// Additional rewards
console.log(await pool.gaugeClaimableRewards());
// [
//     {
//         token: '0xC011a73ee8576Fb46F5E1c5751cA3B9Fe0af2a6F',
//         symbol: 'SNX',
//         amount: '0.000596325465987726'
//     }
// ]
await pool.gaugeClaimRewards();
```

## Deposit&Stake
Add liquidity and deposit into gauge in one transaction.

### Underlying
```ts
(async () => {
    const pool = new curve.Pool('compound');
    const amounts = ['1000', '1000'];

    console.log(await pool.underlyingCoinBalances());
    // { DAI: '10000.0', USDC: '10000.0' }
    console.log(await pool.lpTokenBalances());
    // { lpToken: '0.0', gauge: '0.0' }
    
    console.log(await pool.depositAndStakeExpected(amounts));
    // 1820.604572902286288394
    console.log(await pool.depositAndStakeSlippage(amounts));
    // -0.0000036435051742755193

    console.log(await pool.depositAndStakeIsApproved(amounts));
    // false
    
    await pool.depositAndStakeApprove(amounts);
    await pool.depositAndStake(amounts);

    console.log(await pool.underlyingCoinBalances());
    // { DAI: '9000.0', USDC: '9000.0' }
    console.log(await pool.lpTokenBalances());
    // { lpToken: '0.0', gauge: '1820.556829935710883568' }
})();
```

### Wrapped
```ts
(async () => {
    const pool = new curve.Pool('compound');
    const amounts = ['1000', '1000'];

    console.log(await pool.coinBalances());
    // { cDAI: '10000.0', cUSDC: '10000.0' }
    console.log(await pool.lpTokenBalances());
    // { lpToken: '0.0', gauge: '1820.556829935710883568' }
    
    console.log(await pool.depositAndStakeWrappedExpected(amounts));
    // 40.328408669183101673
    console.log(await pool.depositAndStakeWrappedSlippage(amounts));
    // -0.0020519915272297325

    console.log(await pool.depositAndStakeWrappedIsApproved(amounts));
    // false
    
    await pool.depositAndStakeWrappedApprove(amounts);
    await pool.depositAndStakeWrapped(amounts);

    console.log(await pool.coinBalances());
    // { cDAI: '9000.0', cUSDC: '9000.0' }
    console.log(await pool.lpTokenBalances());
    // { lpToken: '0.0', gauge: '1860.884096082215274556' }
})();
```

## Factory
All the methods above can be used for factory pools. It's only needed to fetch them.
```ts
import curve from "@curvefi/api";

(async () => {
    await curve.init('JsonRpc', {}, { chainId: 1 });
    await curve.fetchFactoryPools();
    await curve.fetchCryptoFactoryPools();

    const factoryPools = curve.getFactoryPoolList();
    // [
    //     'factory-v2-0',  'factory-v2-1',  'factory-v2-2',  'factory-v2-3',
    //     'factory-v2-4',  'factory-v2-5',  'factory-v2-6',  'factory-v2-7',
    //     'factory-v2-8',  'factory-v2-9',  'factory-v2-10', 'factory-v2-11',
    //     'factory-v2-12', 'factory-v2-13', 'factory-v2-14', 'factory-v2-15',
    //     'factory-v2-16', 'factory-v2-17', 'factory-v2-18', 'factory-v2-19',
    //     'factory-v2-20', 'factory-v2-21', 'factory-v2-22', 'factory-v2-23',
    //     'factory-v2-24', 'factory-v2-25', 'factory-v2-26', 'factory-v2-27',
    //     'factory-v2-28', 'factory-v2-29', 'factory-v2-30', 'factory-v2-31',
    //     'factory-v2-32', 'factory-v2-33', 'factory-v2-34', 'factory-v2-35',
    //     'factory-v2-36', 'factory-v2-37', 'factory-v2-38', 'factory-v2-39',
    //     'factory-v2-40', 'factory-v2-41', 'factory-v2-42', 'factory-v2-43',
    //     'factory-v2-44', 'factory-v2-45', 'factory-v2-46', 'factory-v2-47',
    //     'factory-v2-48', 'factory-v2-49', 'factory-v2-50', 'factory-v2-51',
    //     'factory-v2-52', 'factory-v2-53', 'factory-v2-54', 'factory-v2-55',
    //     'factory-v2-56', 'factory-v2-57', 'factory-v2-58', 'factory-v2-59',
    //     'factory-v2-60', 'factory-v2-61', 'factory-v2-62', 'factory-v2-63',
    //     'factory-v2-64', 'factory-v2-65', 'factory-v2-66', 'factory-v2-67',
    //     'factory-v2-68', 'factory-v2-69', 'factory-v2-70', 'factory-v2-71',
    //     'factory-v2-72', 'factory-v2-73', 'factory-v2-74', 'factory-v2-75',
    //     'factory-v2-76', 'factory-v2-77', 'factory-v2-78', 'factory-v2-79',
    //     'factory-v2-80', 'factory-v2-81', 'factory-v2-82', 'factory-v2-83',
    //     'factory-v2-84', 'factory-v2-85', 'factory-v2-86', 'factory-v2-87',
    //     'factory-v2-88', 'factory-v2-89', 'factory-v2-90', 'factory-v2-91',
    //     'factory-v2-92', 'factory-v2-93', 'factory-v2-94', 'factory-v2-95',
    //     'factory-v2-96', 'factory-v2-97', 'factory-v2-98', 'factory-v2-99',
    // ]

    const cryptoFactoryPools = curve.getCryptoFactoryPoolList()
    // [
    //     'factory-crypto-0',  'factory-crypto-1',
    //     'factory-crypto-2',  'factory-crypto-3',
    //     'factory-crypto-4',  'factory-crypto-5',
    //     'factory-crypto-6',  'factory-crypto-7',
    //     'factory-crypto-8',  'factory-crypto-9',
    //     'factory-crypto-10', 'factory-crypto-11',
    //     'factory-crypto-12', 'factory-crypto-13',
    //     'factory-crypto-14', 'factory-crypto-15',
    //     'factory-crypto-16', 'factory-crypto-17',
    //     'factory-crypto-18', 'factory-crypto-19',
    //     'factory-crypto-20', 'factory-crypto-21',
    //     'factory-crypto-22', 'factory-crypto-23',
    //     'factory-crypto-24', 'factory-crypto-25',
    //     'factory-crypto-26', 'factory-crypto-27',
    //     'factory-crypto-28', 'factory-crypto-29',
    //     'factory-crypto-30', 'factory-crypto-31',
    //     'factory-crypto-32', 'factory-crypto-33',
    //     'factory-crypto-34', 'factory-crypto-35',
    //     'factory-crypto-36', 'factory-crypto-37'
    // ]
})()
```