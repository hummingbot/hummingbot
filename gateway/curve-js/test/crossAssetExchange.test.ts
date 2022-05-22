import { assert } from "chai";
import { crossAssetExchangeAvailable, crossAssetExchangeExpected, crossAssetExchange } from "../src/pools";
import { BN, getBalances } from "../src/utils";
import { curve, COINS } from "../src/curve";

const exchangeTest = async (coin1: string, coin2: string) => {
    const amount = '1';
    const initialBalances = await getBalances([coin1, coin2]) as string[];

    const output = await crossAssetExchangeExpected(coin1, coin2, amount);
    await crossAssetExchange(coin1, coin2, amount);

    const balances = await getBalances([coin1, coin2]) as string[];

    if (coin1 === 'steth' || coin2 === 'steth') {
        assert.approximately(Number(Object.values(balances)[0]), Number(BN(Object.values(initialBalances)[0]).minus(BN(amount)).toString()), 1e-18);
    } else if (['adai', 'ausdc', 'ausdt', 'asusd'].includes(coin1) || ['adai', 'ausdc', 'ausdt', 'asusd'].includes(coin2)) {
        assert.approximately(Number(Object.values(balances)[0]), Number(BN(Object.values(initialBalances)[0]).minus(BN(amount)).toString()), 1e-4);
    } else {
        assert.deepStrictEqual(BN(balances[0]), BN(initialBalances[0]).minus(BN(amount)));
    }
    assert.isAtLeast(Number(balances[1]), Number(BN(initialBalances[1]).plus(BN(output).times(0.99)).toString()));
}

describe('Exchange using all pools', async function () {
    this.timeout(240000);

    before(async function () {
        await curve.init('JsonRpc', {}, { gasPrice: 0 });
    });

    const coins = Object.keys(COINS).filter((c) => c !== 'snx' && c !== 'eurs'); // TODO remove eurs
    for (const coin1 of coins) {
        for (const coin2 of coins) {
            if (coin1 !== coin2) {
                it(`${coin1} --> ${coin2}`, async function () {
                    if (await crossAssetExchangeAvailable(coin1, coin2)) {
                        await exchangeTest(coin1, coin2);
                    } else {
                        console.log("Not available");
                    }
                });
            }
        }
    }
})
