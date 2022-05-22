import { assert } from "chai";
import { BN } from "../src/utils";
import curve from "../src";
import { COINS_POLYGON } from "../src/constants/coins-polygon";
import { COINS_ETHEREUM } from "../src/constants/coins-ethereum";

const routerExchangeTest = async (coin1: string, coin2: string) => {
    const amount = '1';
    const initialBalances = await curve.getBalances([coin1, coin2]) as string[];

    const output = await curve.routerExchangeExpected(coin1, coin2, amount);
    await curve.routerExchange(coin1, coin2, amount);

    const balances = await curve.getBalances([coin1, coin2]) as string[];

    if (coin1 === 'steth' || coin2 === 'steth') {
        assert.approximately(Number(Object.values(balances)[0]), Number(BN(Object.values(initialBalances)[0]).minus(BN(amount)).toString()), 1e-18);
    } else if (['adai', 'ausdc', 'ausdt', 'asusd', 'awbtc', 'amdai', 'amusdt', 'amusdc', 'amwbtc'].includes(coin1) ||
        ['adai', 'ausdc', 'ausdt', 'asusd', 'awbtc', 'amdai', 'amusdt', 'amusdc', 'amwbtc'].includes(coin2)) {
        assert.approximately(Number(Object.values(balances)[0]), Number(BN(Object.values(initialBalances)[0]).minus(BN(amount)).toString()), 1e-2);
    } else {
        assert.deepStrictEqual(BN(balances[0]), BN(initialBalances[0]).minus(BN(amount)));
    }
    assert.isAtLeast(Number(balances[1]), Number(BN(initialBalances[1]).plus(BN(output).times(0.99)).toString()));
}

describe('Router exchange', async function () {
    this.timeout(240000);

    before(async function () {
        await curve.init('JsonRpc', {}, { gasPrice: 0 });
        await curve.fetchFactoryPools();
        await curve.fetchCryptoFactoryPools();
    });

    // const coins = Object.keys(COINS_POLYGON).filter((c) => c !== 'snx' && c !== 'eurs'); // TODO remove eurs
    // ETHEREUM
    const coins = ['susd', 'dai', 'mim', 'usdn', 'crv', 'cvx', 'eth', 'xaut', 'eurt', '3crv', '0x62b9c7356a2dc64a1969e19c23e4f579f9810aa7']; // cvxCRV
    // POLYGON
    // const coins = ['crv', 'dai', 'usdc', 'usdt', 'eurt', 'weth', 'wbtc', 'renbtc', 'amdai', 'amusdc', 'amusdt', 'am3crv', 'matic', '0x45c32fa6df82ead1e2ef74d17b76547eddfaff89']; // frax
    for (const coin1 of coins) {
        for (const coin2 of coins) {
            if (coin1 !== coin2) {
                it(`${coin1} --> ${coin2}`, async function () {
                    try {
                        await routerExchangeTest(coin1, coin2);
                    } catch (err: any) {
                        console.log(err.message);
                        assert.equal(err.message, "This pair can't be exchanged");
                    }
                });
            }
        }
    }
})
