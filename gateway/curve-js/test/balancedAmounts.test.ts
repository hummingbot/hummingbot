import { assert } from "chai";
import { Pool } from "../src/pools";
import { curve } from "../src/curve";


// const PLAIN_POOLS = ['susd', 'ren', 'sbtc', 'hbtc', '3pool', 'seth', 'eurs', 'steth', 'ankreth', 'link', 'reth'];
const PLAIN_POOLS = ['susd', 'ren', 'sbtc', 'hbtc', '3pool', 'seth', 'steth', 'ankreth', 'link', 'reth']; // Without eurs
const LENDING_POOLS = ['compound', 'usdt', 'y', 'busd', 'pax', 'aave', 'saave', 'ib'];
const META_POOLS = ['gusd', 'husd', 'usdk', 'usdn', 'musd', 'rsv', 'tbtc', 'dusd', 'pbtc', 'bbtc', 'obtc', 'ust', 'usdp', 'tusd', 'frax', 'lusd', 'busdv2', 'alusd', 'mim'];

const POLYGON_POOLS = ['aave', 'ren', 'atricrypto3', 'eurtusd'];

const balancedAmountsTest = (name: string) => {
    describe(`${name} balanced amounts`, function () {
        let pool: Pool;

        before(async function () {
            pool = new Pool(name);
        });

        it('underlying', async function () {
            const balancedAmounts = (await pool.balancedAmounts()).map(Number);

            assert.equal(balancedAmounts.length, pool.underlyingCoins.length);
            for (const amount of balancedAmounts) {
                assert.isAbove(amount, 0);
            }
        });

        it('wrapped', async function () {
            const balancedWrappedAmounts = (await pool.balancedWrappedAmounts()).map(Number);

            assert.equal(balancedWrappedAmounts.length, pool.coins.length);
            for (const amount of balancedWrappedAmounts) {
                assert.isAbove(amount, 0);
            }
        });

    });
}

describe('Underlying test', async function () {
    this.timeout(120000);

    before(async function () {
        await curve.init('JsonRpc', {},{ gasPrice: 0 });
    });

    for (const poolName of PLAIN_POOLS) {
        balancedAmountsTest(poolName);
    }

    for (const poolName of LENDING_POOLS) {
        balancedAmountsTest(poolName);
    }

    for (const poolName of META_POOLS) {
        balancedAmountsTest(poolName);
    }

    for (const poolName of POLYGON_POOLS) {
        balancedAmountsTest(poolName);
    }
})
