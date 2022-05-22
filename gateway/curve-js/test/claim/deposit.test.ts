import curve from "../../src";
import {DictInterface} from "../../lib/interfaces";

const PLAIN_POOLS =  ['susd', 'ren', 'sbtc', 'hbtc', '3pool', 'seth', 'steth', 'ankreth', 'link', 'reth', 'eurt']; // Without eurs
const LENDING_POOLS = ['compound', 'usdt', 'y', 'busd', 'pax', 'aave', 'saave', 'ib'];
const META_POOLS = ['gusd', 'husd', 'usdk', 'usdn', 'musd', 'rsv', 'tbtc', 'dusd', 'pbtc', 'bbtc', 'obtc', 'ust', 'usdp', 'tusd', 'frax', 'lusd', 'busdv2', 'alusd', 'mim'];
const CRYPTO_POOLS = ['tricrypto2', 'eurtusd', 'crveth', 'cvxeth'];
const ETHEREUM_POOLS = [...PLAIN_POOLS, ...LENDING_POOLS, ...META_POOLS, ...CRYPTO_POOLS];

const POLYGON_POOLS = ['aave', 'ren', 'atricrypto3', 'eurtusd'];

(async function () {
    await curve.init('JsonRpc', {},{ gasPrice: 0 });

    for (const poolName of ['susd']) {
        const pool = new curve.Pool(poolName);
        const amounts = pool.underlyingCoinAddresses.map(() => '10');

        await pool.addLiquidity(amounts);

        const depositAmount: string = (await pool.lpTokenBalances() as DictInterface<string>).lpToken;
        await pool.gaugeDeposit(depositAmount);
        console.log(`Deposited ${depositAmount} LP tokens to ${poolName.toUpperCase()} gauge`);
    }
})()
