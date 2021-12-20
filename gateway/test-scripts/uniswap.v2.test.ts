import { request, ethTests } from './ethereum.test.base';
import 'jest-extended';

// constants
const TOKENS = ['WETH', 'DAI', 'ETH'];
const AMOUNT_PRICE = 1;
const AMOUNT_TRADE = 0.01;
const SCALE_FACTOR = 1000;

jest.setTimeout(300000); // run for 5 mins

export const unitTests = async () => {
  test('ethereum routes', async () => {
    await ethTests('uniswap', TOKENS);
    console.log('\nStarting Uniswap tests');
    console.log('***************************************************');
    // call /start
    const pair = `${TOKENS[0]}-${TOKENS[1]}`;
    console.log(`Starting Uniswap v2 on pair ${pair}...`);
    const start = await request('GET', '/eth/uniswap/start', {
      pairs: JSON.stringify([pair]),
    });
    console.log(start);

    // call /gas-limit
    console.log('Calling uniswap v2 gas-limit endpoint...');
    const gasLimit = await request('POST', '/eth/uniswap/gas-limit', {});
    console.log(gasLimit);

    // price buy
    console.log(`Checking buy price for ${pair}...`);
    const buyPrice = await request('POST', '/eth/uniswap/price', {
      base: TOKENS[0],
      quote: TOKENS[1],
      amount: AMOUNT_PRICE.toString(),
      side: 'buy',
    });
    console.log(`Buy price: ${buyPrice.price}`);

    // price sell
    console.log(`Checking sell price for ${pair}...`);
    const sellPrice = await request('POST', '/eth/uniswap/price', {
      base: TOKENS[0],
      quote: TOKENS[1],
      amount: AMOUNT_PRICE.toString(),
      side: 'sell',
    });
    console.log(`Sell price: ${sellPrice.price}`);

    // trade buy
    console.log(
      `Executing buy trade on ${pair} with ${AMOUNT_TRADE} amount...`
    );
    const buy = await request('POST', '/eth/uniswap/trade', {
      base: TOKENS[0],
      quote: TOKENS[1],
      amount: AMOUNT_TRADE.toString(),
      side: 'buy',
      limitPrice: buyPrice.price,
    });
    expect(buy.txHash).toBeDefined();
    console.log(`Buy hash - ${buy.txHash}`);
    let done = false;
    let tx1, tx2;
    console.log(`Polling...`);
    while (!done) {
      tx1 = await request('POST', '/eth/poll', { txHash: buy.txHash });
      console.log(tx1);
      done = tx1.confirmed;
    }
    expect(tx1.receipt.status).toEqual(1);

    done = false;

    // trade sell
    console.log(
      `Executing sell trade on ${pair} with ${AMOUNT_TRADE} amount...`
    );
    const sell = await request('POST', '/eth/uniswap/trade', {
      base: TOKENS[0],
      quote: TOKENS[1],
      amount: AMOUNT_TRADE.toString(),
      side: 'sell',
      limitPrice: sellPrice.price,
    });
    expect(sell.txHash).toBeDefined();
    console.log(`Buy hash - ${sell.txHash}`);
    console.log(`Polling...`);
    while (!done) {
      tx2 = await request('POST', '/eth/poll', { txHash: sell.txHash });
      console.log(tx2);
      done = tx2.confirmed;
    }
    expect(tx2.receipt.status).toEqual(1);

    // add tests for extreme values of limitPrice - buy and sell
    console.log(
      `Testing for failure with ${
        buyPrice.price / SCALE_FACTOR
      } buy limitPrice...`
    );
    expect(
      await request('POST', '/eth/uniswap/trade', {
        base: TOKENS[0],
        quote: TOKENS[1],
        amount: '1',
        side: 'buy',
        limitPrice: buyPrice.price / SCALE_FACTOR,
      })
    ).toBeUndefined();

    // add tests for extreme values of minimumSlippage
    console.log(
      `Testing for failure with ${
        sellPrice.price * SCALE_FACTOR
      } sell limitPrice...`
    );
    expect(
      await request('POST', '/eth/uniswap/trade', {
        base: TOKENS[0],
        quote: TOKENS[1],
        amount: '1',
        side: 'sell',
        limitPrice: sellPrice.price * SCALE_FACTOR,
      })
    ).toBeUndefined();
  });
};

(async () => {
  await unitTests();
})();
