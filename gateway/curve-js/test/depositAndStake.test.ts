import { assert } from "chai";
import curve from "../src";
import { Pool } from "../src/pools";
import { BN } from "../src/utils";
import { DictInterface } from "../lib/interfaces";

// const PLAIN_POOLS = ['susd', 'ren', 'sbtc', 'hbtc', '3pool', 'seth', 'eurs', 'steth', 'ankreth', 'link', 'reth', 'eurt'];
const PLAIN_POOLS =  ['susd', 'ren', 'sbtc', 'hbtc', '3pool', 'seth', 'steth', 'ankreth', 'link', 'reth', 'eurt']; // Without eurs
const LENDING_POOLS = ['compound', 'usdt', 'y', 'busd', 'pax', 'aave', 'saave', 'ib'];
const META_POOLS = ['gusd', 'husd', 'usdk', 'usdn', 'musd', 'rsv', 'tbtc', 'dusd', 'pbtc', 'bbtc', 'obtc', 'ust', 'usdp', 'tusd', 'frax', 'lusd', 'busdv2', 'alusd', 'mim'];
const CRYPTO_POOLS = ['tricrypto2', 'eurtusd', 'crveth', 'cvxeth', 'xautusd', 'spelleth', 'teth'];

const ETHEREUM_POOLS = [...PLAIN_POOLS, ...LENDING_POOLS, ...META_POOLS, ...CRYPTO_POOLS];
const POLYGON_POOLS = ['aave', 'ren', 'atricrypto3', 'eurtusd'];

const underlyingDepositAndStakeTest = (name: string) => {
    describe(`${name} Deposit&Stake underlying`, function () {
        let pool: Pool;
        let coinAddresses: string[];

        before(async function () {
            pool = new curve.Pool(name);
            coinAddresses = pool.underlyingCoinAddresses;
        });

        it('Deposits and stakes', async function () {
            const amount = '10';
            const amounts = coinAddresses.map(() => amount);

            const initialBalances = await pool.balances() as DictInterface<string>;
            const lpTokenExpected = await pool.depositAndStakeExpected(amounts);

            await pool.depositAndStake(amounts);

            const balances = await pool.balances() as DictInterface<string>;

            pool.underlyingCoins.forEach((c: string) => {
                if (name === 'steth') {
                    assert.approximately(Number(BN(balances[c])), Number(BN(initialBalances[c]).minus(BN(amount).toString())), 1e-18);
                } else {
                    assert.deepStrictEqual(BN(balances[c]), BN(initialBalances[c]).minus(BN(amount)));
                }
            })

            assert.approximately(Number(balances.gauge) - Number(initialBalances.gauge), Number(lpTokenExpected), 0.01);
            assert.strictEqual(Number(balances.lpToken) - Number(initialBalances.lpToken), 0);
        });

    });
}

const wrappedDepositAndStakeTest = (name: string) => {
    describe(`${name} Deposit&Stake wrapped`, function () {
        let pool: Pool;
        let coinAddresses: string[];

        before(async function () {
            pool = new curve.Pool(name);
            coinAddresses = pool.coinAddresses;
        });

        it('Deposits and stakes', async function () {
            const amount = '10';
            const amounts = coinAddresses.map(() => amount);

            const initialBalances = await pool.balances() as DictInterface<string>;
            const lpTokenExpected = await pool.depositAndStakeWrappedExpected(amounts);

            await pool.depositAndStakeWrapped(amounts);

            const balances = await pool.balances() as DictInterface<string>;

            pool.coins.forEach((c: string) => {
                if (['aave', 'saave'].includes(name) || (curve.chainId === 137 && pool.name === 'ren')) {
                    assert.approximately(Number(BN(balances[c])), Number(BN(initialBalances[c]).minus(BN(amount).toString())), 1e-2);
                } else {
                    assert.deepStrictEqual(BN(balances[c]), BN(initialBalances[c]).minus(BN(amount)));
                }
            })

            assert.approximately(Number(balances.gauge) - Number(initialBalances.gauge), Number(lpTokenExpected), 0.01);
            assert.strictEqual(Number(balances.lpToken) - Number(initialBalances.lpToken), 0);
        });
    });
}

describe('Deposit&Stake test', async function () {
    this.timeout(120000);

    before(async function () {
        await curve.init('JsonRpc', {},{ gasPrice: 0 });
    });

    for (const poolName of ETHEREUM_POOLS) {
        underlyingDepositAndStakeTest(poolName);
        if (!PLAIN_POOLS.includes(poolName)) {
            wrappedDepositAndStakeTest(poolName);
        }
    }

    // for (const poolName of POLYGON_POOLS) {
    //     underlyingDepositAndStakeTest(poolName);
    //     if (poolName !== 'atricrypto3') {
    //         wrappedDepositAndStakeTest(poolName);
    //     }
    // }
})
