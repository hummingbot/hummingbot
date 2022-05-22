import curve from "../src";
import { DictInterface } from "../src/interfaces";


const balancesTest = async () => {
    await curve.init('JsonRpc', {}, { gasPrice: 0, chainId: 1 });

    console.log(await curve.getBalances(['DAI', 'sUSD']));
    // OR console.log(await curve.getBalances(['0x6B175474E89094C44Da98b954EedeAC495271d0F', '0x57Ab1ec28D129707052df4dF418D58a2D46d5f51']));

    console.log(await curve.getBalances(['aDAI', 'aSUSD']));
    // OR console.log(await curve.getBalances(['0x028171bCA77440897B824Ca71D1c56caC55b68A3', '0x6c5024cd4f8a59110119c56f8933403a539555eb']));


    // --- Pool ---

    const saave = new curve.Pool('saave');

    // Current address balances (signer balances)
    console.log(await saave.balances());
    console.log(await saave.lpTokenBalances());
    console.log(await saave.underlyingCoinBalances());
    console.log(await saave.coinBalances());
    console.log(await saave.allCoinBalances());


    // For every method above you can specify address
    console.log(await saave.balances("0x0063046686E46Dc6F15918b61AE2B121458534a5"));
    // Or several addresses
    console.log(await saave.balances("0x0063046686E46Dc6F15918b61AE2B121458534a5", "0x66aB6D9362d4F35596279692F0251Db635165871"));
}

const statsTest = async () => {
    await curve.init('JsonRpc', {}, { gasPrice: 0 });

    const aave = new curve.Pool('aave');

    console.log(await aave.stats.getParameters());
    console.log(await aave.stats.getPoolBalances());
    console.log(await aave.stats.getPoolWrappedBalances());
    console.log(await aave.stats.getTotalLiquidity());
    console.log(await aave.stats.getVolume());
    console.log(await aave.stats.getBaseApy());
    console.log(await aave.stats.getTokenApy());
    console.log(await aave.stats.getRewardsApy());
}

const poolTest = async () => {
    await curve.init('JsonRpc', {url: 'http://localhost:8545/', privateKey: ''}, { gasPrice: 0, chainId: 1 });

    const pool = new curve.Pool('aave');
    console.log(pool.underlyingCoins);
    console.log(pool.coins);

    console.log(await pool.balances());

    console.log('// ADD LIQUIDITY');
    const expectedLpTokenAmount1 = await pool.addLiquidityExpected(['100', '100', '100']);
    console.log(expectedLpTokenAmount1);
    const addLiquidityTx1 = await pool.addLiquidity(['100', '100', '100']);
    console.log(addLiquidityTx1);

    console.log(await pool.balances());

    console.log('// ADD LIQUIDITY WRAPPED');
    const expectedLpTokenAmount2 = await pool.addLiquidityWrappedExpected(['100', '100', '100']);
    console.log(expectedLpTokenAmount2);
    const addLiquidityTx2 = await pool.addLiquidityWrapped(['100', '100', '100']);
    console.log(addLiquidityTx2);

    const balances = await pool.balances() as DictInterface<string>;
    console.log(balances);

    console.log('// GAUGE DEPOSIT');
    const gaugeDepositTx = await pool.gaugeDeposit(balances['lpToken']);
    console.log(gaugeDepositTx);

    console.log(await pool.balances());

    console.log('// GAUGE WITHDRAW');
    const gaugeWithdrawTx = await pool.gaugeWithdraw(balances['lpToken']);
    console.log(gaugeWithdrawTx);

    console.log(await pool.balances());

    console.log('// REMOVE LIQUIDITY');
    const expectedUnderlyingCoinAmounts = await pool.removeLiquidityExpected('10');
    console.log(expectedUnderlyingCoinAmounts);
    const removeLiquidityTx = await pool.removeLiquidity('10');
    console.log(removeLiquidityTx);

    console.log(await pool.balances());

    console.log('// REMOVE LIQUIDITY WRAPPED');
    const expectedCoinAmounts = await pool.removeLiquidityWrappedExpected('10');
    console.log(expectedCoinAmounts);
    const removeLiquidityWrappedTx = await pool.removeLiquidityWrapped('10');
    console.log(removeLiquidityWrappedTx);

    console.log(await pool.balances());

    console.log('// REMOVE LIQUIDITY IMBALANCE');
    const expectedLpTokenAmount3 = await pool.removeLiquidityImbalanceExpected(['10', '10', '10']);
    console.log(expectedLpTokenAmount3);
    const removeLiquidityImbalanceTx = await pool.removeLiquidityImbalance(['10', '10', '10']);
    console.log(removeLiquidityImbalanceTx);

    console.log(await pool.balances());

    console.log('// REMOVE LIQUIDITY IMBALANCE WRAPPED');
    const expectedLpTokenAmount4 = await pool.removeLiquidityImbalanceWrappedExpected(['10', '10', '10']);
    console.log(expectedLpTokenAmount4);
    const removeLiquidityImbalanceWrappedTx = await pool.removeLiquidityImbalanceWrapped(['10', '10', '10']);
    console.log(removeLiquidityImbalanceWrappedTx);

    console.log(await pool.balances());

    console.log('// REMOVE LIQUIDITY ONE COIN');
    const expectedDAIAmount = await pool.removeLiquidityOneCoinExpected('10','DAI');
    // OR const expectedDAIAmount = await pool.removeLiquidityOneCoinExpected('10', 0);
    console.log(expectedDAIAmount);
    const removeLiquidityOneCoinTx = await pool.removeLiquidityOneCoin('10', 'DAI');
    // OR const removeLiquidityImbalanceTx = await pool.removeLiquidityOneCoin('10', 0);
    console.log(removeLiquidityOneCoinTx);

    console.log(await pool.balances());

    console.log('// REMOVE LIQUIDITY ONE COIN WRAPPED');
    const expectedADAIAmount = await pool.removeLiquidityOneCoinWrappedExpected('10', 'aUSDC');
    // OR const expectedADAIAmount = await pool.removeLiquidityOneCoinWrappedExpected('10', 1);
    console.log(expectedADAIAmount);
    const removeLiquidityOneCoinWrappedTx = await pool.removeLiquidityOneCoinWrapped('10', 'aUSDC');
    // OR const removeLiquidityImbalanceWrappedTx = await pool.removeLiquidityOneCoinWrapped('10', 1);
    console.log(removeLiquidityOneCoinWrappedTx);

    console.log(await pool.balances());
}

const routerExchangeTest = async () => {
    await curve.init('JsonRpc', {}, { gasPrice: 0, chainId: 1 });

    console.log(await curve.getBalances(['DAI', 'CRV']));

    const { route, output } = await curve.getBestRouteAndOutput('DAI', 'CRV', '1000');
    // OR await curve.getBestPoolAndOutput('0x6B175474E89094C44Da98b954EedeAC495271d0F', '0xD533a949740bb3306d119CC777fa900bA034cd52', '10000');
    const expected = await curve.routerExchangeExpected('DAI', 'CRV', '1000');
    // OR await curve.exchangeExpected('0x6B175474E89094C44Da98b954EedeAC495271d0F', '0xD533a949740bb3306d119CC777fa900bA034cd52', '10000');

    console.log(route, output, expected);

    await curve.routerExchange('DAI', 'CRV', '1000')
    // OR await curve.exchange('0x6B175474E89094C44Da98b954EedeAC495271d0F', '0xD533a949740bb3306d119CC777fa900bA034cd52', '10000');

    console.log(await curve.getBalances(['DAI', 'CRV']));
}

const exchangeTest = async () => {
    await curve.init('JsonRpc', {}, { gasPrice: 0, chainId: 1 });

    console.log(await curve.getBalances(['DAI', 'USDC']));

    const { poolAddress, output } = await curve.getBestPoolAndOutput('DAI', 'USDC', '100');
    // OR await curve.getBestPoolAndOutput('0x6B175474E89094C44Da98b954EedeAC495271d0F', '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', '100');
    const expected = await curve.exchangeExpected('DAI', 'USDC', '100');
    // OR await curve.exchangeExpected('0x6B175474E89094C44Da98b954EedeAC495271d0F', '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', '100');

    console.log(poolAddress, output, expected);

    await curve.exchange('DAI', 'USDC', '100')
    // OR await curve.exchange('0x6B175474E89094C44Da98b954EedeAC495271d0F', '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', '100');

    console.log(await curve.getBalances(['DAI', 'USDC']));
}

const crossAssetExchangeTest = async () => {
    await curve.init('JsonRpc', {}, { gasPrice: 0, chainId: 1 });

    console.log(await curve.getBalances(['DAI', 'WBTC']));

    console.log(await curve.crossAssetExchangeAvailable('DAI', 'WBTC'));
    console.log(await curve.crossAssetExchangeOutputAndSlippage('DAI', 'WBTC', '500'));
    console.log(await curve.crossAssetExchangeExpected('DAI', 'WBTC', '500'));

    const tx = await curve.crossAssetExchange('DAI', 'WBTC', '500');
    console.log(tx);

    console.log(await curve.getBalances(['DAI', 'WBTC']));
}

const boostingTest = async () => {
    await curve.init('JsonRpc', {}, { gasPrice: 0, chainId: 1 });

    console.log(await curve.boosting.getCrv());

    await curve.boosting.createLock('1000', 365);

    console.log(await curve.boosting.getCrv());
    console.log(await curve.boosting.getLockedAmountAndUnlockTime());
    console.log(await curve.boosting.getVeCrv());
    console.log(await curve.boosting.getVeCrvPct());

    await curve.boosting.increaseAmount('500');

    console.log(await curve.boosting.getCrv());
    console.log(await curve.boosting.getLockedAmountAndUnlockTime());
    console.log(await curve.boosting.getVeCrv());
    console.log(await curve.boosting.getVeCrvPct());

    await curve.boosting.increaseUnlockTime(365);

    console.log(await curve.boosting.getLockedAmountAndUnlockTime());
    console.log(await curve.boosting.getVeCrv());
    console.log(await curve.boosting.getVeCrvPct());
}

const rewardsTest = async () => {
    await curve.init('JsonRpc', {}, { gasPrice: 0 });

    const pool = new curve.Pool('susd');

    console.log(await pool.gaugeClaimableTokens());
    console.log(await pool.gaugeClaimTokens());

    console.log(await pool.gaugeClaimableRewards());
    console.log(await pool.gaugeClaimRewards());
}

const depositAndStakeUnderlyingTest = async () => {
    await curve.init('JsonRpc', {}, { gasPrice: 0 });

    const pool = new curve.Pool('compound');
    const amounts = ['1000', '1000'];

    console.log(await pool.underlyingCoinBalances());
    console.log(await pool.lpTokenBalances());

    console.log(await pool.depositAndStakeExpected(amounts));
    console.log(await pool.depositAndStakeSlippage(amounts));

    console.log(await pool.depositAndStakeIsApproved(amounts));

    await pool.depositAndStakeApprove(amounts);
    await pool.depositAndStake(amounts);

    console.log(await pool.underlyingCoinBalances());
    console.log(await pool.lpTokenBalances());
}

const depositAndStakeWrappedTest = async () => {
    await curve.init('JsonRpc', {}, { gasPrice: 0 });

    const pool = new curve.Pool('compound');
    const amounts = ['1000', '1000'];

    console.log(await pool.coinBalances());
    console.log(await pool.lpTokenBalances());

    console.log(await pool.depositAndStakeWrappedExpected(amounts));
    console.log(await pool.depositAndStakeWrappedSlippage(amounts));

    console.log(await pool.depositAndStakeWrappedIsApproved(amounts));

    await pool.depositAndStakeWrappedApprove(amounts);
    await pool.depositAndStakeWrapped(amounts);

    console.log(await pool.coinBalances());
    console.log(await pool.lpTokenBalances());
}
