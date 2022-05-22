import { assert } from "chai";
import curve from "../../src/";

// ----------------
// TO MAKE THIS TEST WORKING YOU NEED TO DO THESE STEPS FIRST
//
// 1. Run
//     node deposit.test.js
//
// 2. Go to brownie console and run:
//     chain.sleep(1000000)
//     chain.mine(1)
//
// ----------------


const PLAIN_POOLS =  ['susd', 'ren', 'sbtc', 'hbtc', '3pool', 'seth', 'steth', 'ankreth', 'link', 'reth', 'eurt']; // Without eurs
const LENDING_POOLS = ['compound', 'usdt', 'y', 'busd', 'pax', 'aave', 'saave', 'ib'];
const META_POOLS = ['gusd', 'husd', 'usdk', 'usdn', 'musd', 'rsv', 'tbtc', 'dusd', 'pbtc', 'bbtc', 'obtc', 'ust', 'usdp', 'tusd', 'frax', 'lusd', 'busdv2', 'alusd', 'mim'];
const CRYPTO_POOLS = ['tricrypto2', 'eurtusd', 'crveth', 'cvxeth'];
const ETHEREUM_POOLS = [...PLAIN_POOLS, ...LENDING_POOLS, ...META_POOLS, ...CRYPTO_POOLS];

const POLYGON_POOLS = ['aave', 'ren', 'atricrypto3', 'eurtusd'];


describe('Claiming CRV', function() {
    this.timeout(120000);

    before(async function() {
        await curve.init('JsonRpc', {}, { gasPrice: 0 });
    });

    for (const poolName of CRYPTO_POOLS) {
        it(`Claims CRV from ${poolName.toUpperCase()}`, async function () {
            const pool = new curve.Pool(poolName);

            const [crvBalanceBefore] = await curve.getBalances(['crv']) as string[];
            const expected = await pool.gaugeClaimableTokens();

            console.log(crvBalanceBefore, "+", expected, "=", Number(crvBalanceBefore) + Number(expected));
            await pool.gaugeClaimTokens();

            const [crvBalanceAfter] = await curve.getBalances(['crv']) as string[];
            console.log(crvBalanceAfter);

            assert.approximately(Number(crvBalanceAfter), Number(crvBalanceBefore) + Number(expected), 1e-3);
        });
    }
});
