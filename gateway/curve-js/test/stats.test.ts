import { assert } from "chai";
import curve from "../src/";
import { Pool } from "../src/pools";
import {ethers} from "ethers";

const MAIN_POOLS_ETHEREUM = [
    'compound', 'usdt',   'y',          'busd',
    'susd',     'pax',    'ren',        'sbtc',
    'hbtc',     '3pool',  'gusd',       'husd',
    'usdk',     'usdn',   'musd',       'rsv',
    'tbtc',     'dusd',   'pbtc',       'bbtc',
    'obtc',     'seth',   'eurs',       'ust',
    'aave',     'steth',  'saave',      'ankreth',
    'usdp',     'ib',     'link',       'tusd',
    'frax',     'lusd',   'busdv2',     'reth',
    'alusd',    'mim',    'tricrypto2', 'eurt',
    'eurtusd',  'crveth', 'cvxeth',     'xautusd',
    'spelleth', 'teth',
];
const FACTORY_POOLS_COUNT_ETHEREUM = 104;
const CRYPTO_FACTORY_POOLS_COUNT_ETHEREUM = 38;

const MAIN_POOLS_POLYGON = [ 'aave', 'ren', 'atricrypto3', 'eurtusd' ];
const FACTORY_POOLS_COUNT_POLYGON = 213;


const checkNumber = (str: string) => {
    const re = /-?\d+(\.\d+)?(e-\d+)?/g
    const match = str.match(re);
    return match && str === match[0]
}

const poolStatsTest = (name: string) => {
    describe(`${name} stats test`, function () {
        let pool: Pool;

        before(async function () {
            pool = new Pool(name);
        });


        it('Total liquidity', async function () {
            const totalLiquidity = await pool.stats.getTotalLiquidity();

            assert.isTrue(checkNumber(totalLiquidity));
        });

        it('Volume', async function () {
            const volume = await pool.stats.getVolume();

            assert.isTrue(checkNumber(volume));
        });

        it('Base APY', async function () {
            const apy = await pool.stats.getBaseApy();

            assert.isTrue(checkNumber(apy.day));
            assert.isTrue(checkNumber(apy.week));
            assert.isTrue(checkNumber(apy.month));
            assert.isTrue(checkNumber(apy.total));
        });

        it('Token APY', async function () {
            if (pool.gauge === ethers.constants.AddressZero) {
                console.log("Skip");
                return
            }

            const [apy, boostedApy] = await pool.stats.getTokenApy();

            assert.isTrue(checkNumber(apy));
            assert.isTrue(checkNumber(boostedApy));
        });

        it('Rewards APY', async function () {
            const rewardsApy = await pool.stats.getRewardsApy();

            rewardsApy.forEach((item: { apy: string }) => {
                assert.isTrue(checkNumber(item.apy));
            })
        });
    })
}

describe('Stats test', async function () {
    this.timeout(120000);


    before(async function () {
        await curve.init('JsonRpc', {},{ gasPrice: 0 });
        await curve.fetchFactoryPools();
        await curve.fetchCryptoFactoryPools();
    });

    for (const poolName of MAIN_POOLS_ETHEREUM) {
        poolStatsTest(poolName);
    }

    for (let i = 0; i < FACTORY_POOLS_COUNT_ETHEREUM; i++) {
        poolStatsTest("factory-v2-" + i);
    }

    for (let i = 0; i < CRYPTO_FACTORY_POOLS_COUNT_ETHEREUM; i++) {
        poolStatsTest("factory-crypto-" + i);
    }

    // for (const poolName of MAIN_POOLS_POLYGON) {
    //     poolStatsTest(poolName);
    // }
    //
    // for (let i = 0; i < FACTORY_POOLS_COUNT_POLYGON + 9; i++) {
    //     const blacklist = [126, 136, 155, 156, 157, 163, 187, 189, 195];
    //     if (blacklist.includes(i)) continue;
    //
    //     poolStatsTest("factory-v2-" + i);
    // }
})
