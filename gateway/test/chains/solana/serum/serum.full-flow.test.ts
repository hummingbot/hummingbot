import 'jest-extended';
import {Serum} from '../../../../src/connectors/serum/serum';
import {unpatch} from '../../../services/patch';
import {Solana} from '../../../../src/chains/solana/solana';
import {default as config} from './fixtures/serumConfig';
// @ts-ignore
import { cancelOpenOrders, cancelOrders, createOrders, getFilledOrders, getMarkets, getOpenOrders, getOrderBooks, getOrders, getTickers, settleFunds } from '../../../../src/clob/clob.controllers';
// @ts-ignore
import {getNewOrderTemplate} from './fixtures/dummy';
import BN from 'bn.js';
import {Account} from '@solana/web3.js';

jest.setTimeout(1000000);

// @ts-ignore
let serum: Serum;
// @ts-ignore
let solana: Solana;

beforeAll(async () => {
  solana = await Solana.getInstance(config.solana.network);

  serum = await Serum.getInstance(config.serum.chain, config.serum.network);

  // await reset();
});

afterEach(() => {
  unpatch();
});

const commonParameters = {
  chain: config.serum.chain,
  network: config.serum.network,
  connector: config.serum.connector,
}

const marketNames = ['SOL/USDT', 'SOL/USDC'];

// @ts-ignore
const reset = async () => {
  const connection = serum.getConnection();
  const markets = await (await Serum.getInstance(commonParameters.chain, commonParameters.network)).getMarkets(marketNames);
  const ownerKeyPair = await solana.getKeypair(config.solana.wallet.owner.address);
  const owner = new Account(ownerKeyPair.secretKey);

  for (const market of markets.values()) {
    console.log(`Resetting market ${market.name}:`);

    const serumMarket = market.market;
    const openOrders = await serumMarket.loadOrdersForOwner(connection, owner.publicKey);

    console.log('Open orders found:', JSON.stringify(openOrders, null, 2));

    for (let openOrder of openOrders) {
      const result = await serumMarket.cancelOrder(connection, owner, openOrder)
      console.log(`Cancelling order ${openOrder.orderId}:`, JSON.stringify(result, null, 2));
    }

    for (const openOrders of await serumMarket.findOpenOrdersAccountsForOwner(
      connection,
      owner.publicKey,
    )) {
      console.log(`Settling funds for orders:`, JSON.stringify(openOrders, null, 2));

      if (openOrders.baseTokenFree.gt(new BN(0)) || openOrders.quoteTokenFree.gt(new BN(0))) {
        const base = await serumMarket.findBaseTokenAccountsForOwner(connection, owner.publicKey, true);
        const baseTokenAccount = base[0].pubkey;
        const quote = await serumMarket.findQuoteTokenAccountsForOwner(connection, owner.publicKey, true);
        const quoteTokenAccount = quote[0].pubkey;

        const result = await serumMarket.settleFunds(
          connection,
          owner,
          openOrders,
          baseTokenAccount,
          quoteTokenAccount,
        );

        console.log(`Result of settling funds:`, JSON.stringify(result, null, 2));
      }
    }
  }
}

it('Temporary 01', async () => {
  /*
  create order [0]
  create orders [1, 2, 3, 4, 5, 6, 7]
  get open order [0]
  get order [1]
  get open orders [2, 3]
  get orders [4, 5]
  get all open orders (0, 1, 2, 3, 4, 5, 6, 7)
  get all orders (0, 1, 2, 3, 4, 5, 6, 7)
  cancel open order [0]
  cancel order [1]
  get canceled open order [0]
  get canceled order [1]
  get filled order [2]
  get filled orders [3, 4]
  get all filled orders (),
  cancel open orders [2, 3]
  cancel orders [4, 5]
  get canceled open orders [2, 3]
  get canceled orders [4, 5]
  cancel all open orders (6, 7)
  get all open orders ()
  get all orders ()
  create orders [8, 9]
  get all open orders ()
  get all orders ()
  cancel all orders (8, 9)
  get all open orders ()
  get all orders ()
  settle funds for market [SOL/USDT]
  settle funds for markets [SOL/USDT, SOL/USDC]
  settle all funds (SOL/USDT, SOL/USDC)
  */

  // @ts-ignore
  const marketName = marketNames[0];

  // @ts-ignore
  const orderIds = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9'];

  // @ts-ignore
  let request: any;

  // @ts-ignore
  let response: any;

  request = {
    ...commonParameters,
    name: marketName,
  };
  response = (await getMarkets(request)).body;
  console.log('markets:', 'request:', JSON.stringify(request, null, 2), 'response', JSON.stringify(response, null, 2));

  request = {
    ...commonParameters,
    names: marketNames,
  };
  response = (await getMarkets(request)).body;
  console.log('markets', 'request:', JSON.stringify(request, null, 2), 'response', JSON.stringify(response, null, 2));

  request = {
    ...commonParameters
  };
  response = (await getMarkets(request)).body;
  console.log('markets', 'request:', JSON.stringify(request, null, 2), 'response', JSON.stringify(response, null, 2));

  request = {
    ...commonParameters,
    marketName: marketName,
  };
  response = (await getOrderBooks(request)).body;
  console.log('order books', 'request:', JSON.stringify(request, null, 2), 'response', JSON.stringify(response, null, 2));

  request = {
    ...commonParameters,
    marketNames: marketNames,
  };
  response = (await getOrderBooks(request)).body;
  console.log('order books:', 'request:', JSON.stringify(request, null, 2), 'response', JSON.stringify(response, null, 2));

  request = {
    ...commonParameters
  };
  response = (await getOrderBooks(request)).body;
  console.log('order books:', 'request:', JSON.stringify(request, null, 2), 'response', JSON.stringify(response, null, 2));

  request = {
    ...commonParameters,
    marketName: marketName,
  };
  response = (await getTickers(request)).body;
  console.log('tickers', 'request:', JSON.stringify(request, null, 2), 'response', JSON.stringify(response, null, 2));

  request = {
    ...commonParameters,
    marketNames: marketNames,
  };
  response = (await getTickers(request)).body;
  console.log('tickers', 'request:', JSON.stringify(request, null, 2), 'response', JSON.stringify(response, null, 2));

  request = {
    ...commonParameters
  };
  response = (await getTickers(request)).body;
  console.log('tickers', 'request:', JSON.stringify(request, null, 2), 'response', JSON.stringify(response, null, 2));

  request = {
    ...commonParameters,
    ownerAddress: config.solana.wallet.owner.address,
  };
  response = await getOpenOrders(request);
  console.log('get all open orders', 'request:', JSON.stringify(request, null, 2), 'response', JSON.stringify(response, null, 2));

  request = {
    ...commonParameters,
    order: (() => { const order = getNewOrderTemplate(); order.id = orderIds[0]; return order; })()
  };
  response = await createOrders(request);
  console.log('create order', 'request:', JSON.stringify(request, null, 2), 'response', JSON.stringify(response, null, 2));

  request = {
    ...commonParameters,
    orders: [
      (() => { const order = getNewOrderTemplate(); order.id = orderIds[1]; return order; })(),
      (() => { const order = getNewOrderTemplate(); order.id = orderIds[2]; return order; })(),
      (() => { const order = getNewOrderTemplate(); order.id = orderIds[3]; return order; })(),
      (() => { const order = getNewOrderTemplate(); order.id = orderIds[4]; return order; })(),
      (() => { const order = getNewOrderTemplate(); order.id = orderIds[5]; return order; })(),
      (() => { const order = getNewOrderTemplate(); order.id = orderIds[6]; return order; })(),
      (() => { const order = getNewOrderTemplate(); order.id = orderIds[7]; return order; })(),
      (() => { const order = getNewOrderTemplate(); order.id = orderIds[8]; return order; })(),
    ]
  };
  response = await createOrders(request);
  console.log('create orders', 'request:', JSON.stringify(request, null, 2), 'response', JSON.stringify(response, null, 2));

  request = {
    ...commonParameters,
    order: {
      id: orderIds[0],
      ownerAddress: config.solana.wallet.owner.address
    },
  };
  response = await getOpenOrders(request);
  console.log('get open order', 'request:', JSON.stringify(request, null, 2), 'response', JSON.stringify(response, null, 2));

  request = {
    ...commonParameters,
    order: {
      id: orderIds[1],
      ownerAddress: config.solana.wallet.owner.address
    },
  };
  response = await getOrders(request);
  console.log('get order', 'request:', JSON.stringify(request, null, 2), 'response', JSON.stringify(response, null, 2));

  request = {
    ...commonParameters,
    orders: [{
      ids: orderIds.slice(2, 4),
      ownerAddress: config.solana.wallet.owner.address
    }],
  };
  response = await getOpenOrders(request);
  console.log('get open orders', 'request:', JSON.stringify(request, null, 2), 'response', JSON.stringify(response, null, 2));

  request = {
    ...commonParameters,
    orders: [{
      ids: orderIds.slice(4, 6),
      ownerAddress: config.solana.wallet.owner.address
    }],
  };
  response = await getOrders(request);
  console.log('get orders', 'request:', JSON.stringify(request, null, 2), 'response', JSON.stringify(response, null, 2));

  request = {
    ...commonParameters,
    ownerAddress: config.solana.wallet.owner.address,
  };
  response = await getOpenOrders(request);
  console.log('get all open orders', 'request:', JSON.stringify(request, null, 2), 'response', JSON.stringify(response, null, 2));

  request = {
    ...commonParameters,
    ownerAddress: config.solana.wallet.owner.address,
  };
  response = await getOrders(request);
  console.log('get all orders', 'request:', JSON.stringify(request, null, 2), 'response', JSON.stringify(response, null, 2));

  request = {
    ...commonParameters,
    order: {
      id: orderIds[0],
      ownerAddress: config.solana.wallet.owner.address,
      marketName: marketName
    },
  };
  response = await cancelOpenOrders(request);
  console.log('cancel open order', 'request:', JSON.stringify(request, null, 2), 'response', JSON.stringify(response, null, 2));

  request = {
    ...commonParameters,
    order: {
      id: orderIds[1],
      ownerAddress: config.solana.wallet.owner.address,
      marketName: marketName
    },
  };
  response = await cancelOrders(request);
  console.log('cancel order', 'request:', JSON.stringify(request, null, 2), 'response', JSON.stringify(response, null, 2));

  request = {
    ...commonParameters,
    order: {
      id: orderIds[0],
      ownerAddress: config.solana.wallet.owner.address
    },
  };
  response = await getOpenOrders(request);
  console.log('get open order', 'request:', JSON.stringify(request, null, 2), 'response', JSON.stringify(response, null, 2));

  request = {
    ...commonParameters,
    order: {
      id: orderIds[1],
      ownerAddress: config.solana.wallet.owner.address
    },
  };
  response = await getOrders(request);
  console.log('get order', 'request:', JSON.stringify(request, null, 2), 'response', JSON.stringify(response, null, 2));

  // request = {
  //   ...commonParameters,
  //   order: {
  //     id: orderIds[2],
  //     ownerAddress: config.solana.wallet.owner.address
  //   },
  // };
  // response = await getFilledOrders(request);
  // console.log('get filled order', 'request:', JSON.stringify(request, null, 2), 'response', JSON.stringify(response, null, 2));

  // request = {
  //   ...commonParameters,
  //   orders: [{
  //     ids: orderIds.slice(3, 5),
  //     ownerAddress: config.solana.wallet.owner.address
  //   }],
  // };
  // response = await getFilledOrders(request);
  // console.log('get filled orders', 'request:', JSON.stringify(request, null, 2), 'response', JSON.stringify(response, null, 2));

  request = {
    ...commonParameters,
    ownerAddress: config.solana.wallet.owner.address,
  };
  response = await getFilledOrders(request);
  console.log('get all filled orders', 'request:', JSON.stringify(request, null, 2), 'response', JSON.stringify(response, null, 2));

  request = {
    ...commonParameters,
    orders: [{
      ids: orderIds.slice(2, 4),
      ownerAddress: config.solana.wallet.owner.address,
      marketName: marketName
    }],
  };
  response = await cancelOpenOrders(request);
  console.log('cancel open orders', 'request:', JSON.stringify(request, null, 2), 'response', JSON.stringify(response, null, 2));

  request = {
    ...commonParameters,
    orders: [{
      ids: orderIds.slice(4, 6),
      ownerAddress: config.solana.wallet.owner.address,
      marketName: marketName
    }],
  };
  response = await cancelOrders(request);
  console.log('cancel orders', 'request:', JSON.stringify(request, null, 2), 'response', JSON.stringify(response, null, 2));

  request = {
    ...commonParameters,
    orders: [{
      ids: orderIds.slice(2, 4),
      ownerAddress: config.solana.wallet.owner.address
    }],
  };
  response = await getOpenOrders(request);
  console.log('get open orders', 'request:', JSON.stringify(request, null, 2), 'response', JSON.stringify(response, null, 2));

  request = {
    ...commonParameters,
    orders: [{
      ids: orderIds.slice(4, 6),
      ownerAddress: config.solana.wallet.owner.address
    }],
  };
  response = await getOrders(request);
  console.log('get orders', 'request:', JSON.stringify(request, null, 2), 'response', JSON.stringify(response, null, 2));

  request = {
    ...commonParameters,
    ownerAddress: config.solana.wallet.owner.address,
  };
  response = await cancelOpenOrders(request);
  console.log('cancel all open orders', 'request:', JSON.stringify(request, null, 2), 'response', JSON.stringify(response, null, 2));

  request = {
    ...commonParameters,
    ownerAddress: config.solana.wallet.owner.address,
  };
  response = await getOpenOrders(request);
  console.log('get all open orders', 'request:', JSON.stringify(request, null, 2), 'response', JSON.stringify(response, null, 2));

  request = {
    ...commonParameters,
    ownerAddress: config.solana.wallet.owner.address,
  };
  response = await getOrders(request);
  console.log('get all orders', 'request:', JSON.stringify(request, null, 2), 'response', JSON.stringify(response, null, 2));

  request = {
    ...commonParameters,
    orders: [
      (() => { const order = getNewOrderTemplate(); order.id = orderIds[8]; return order; })(),
      (() => { const order = getNewOrderTemplate(); order.id = orderIds[9]; return order; })(),
    ]
  };
  response = await createOrders(request);
  console.log('create orders', 'request:', JSON.stringify(request, null, 2), 'response', JSON.stringify(response, null, 2));

  request = {
    ...commonParameters,
    ownerAddress: config.solana.wallet.owner.address,
  };
  response = await getOpenOrders(request);
  console.log('get all open orders', 'request:', JSON.stringify(request, null, 2), 'response', JSON.stringify(response, null, 2));

  request = {
    ...commonParameters,
    ownerAddress: config.solana.wallet.owner.address,
  };
  response = await getOrders(request);
  console.log('get all orders', 'request:', JSON.stringify(request, null, 2), 'response', JSON.stringify(response, null, 2));

  request = {
    ...commonParameters,
    ownerAddress: config.solana.wallet.owner.address,
  };
  response = await cancelOrders(request);
  console.log('cancel all orders', 'request:', JSON.stringify(request, null, 2), 'response', JSON.stringify(response, null, 2));

  request = {
    ...commonParameters,
    ownerAddress: config.solana.wallet.owner.address,
  };
  response = await getOpenOrders(request);
  console.log('get all open orders', 'request:', JSON.stringify(request, null, 2), 'response', JSON.stringify(response, null, 2));

  request = {
    ...commonParameters,
    ownerAddress: config.solana.wallet.owner.address,
  };
  response = await getOrders(request);
  console.log('get all orders', 'request:', JSON.stringify(request, null, 2), 'response', JSON.stringify(response, null, 2));

  request = {
    ...commonParameters,
    marketName: marketName,
  };
  response = await settleFunds(request);
  console.log('settle funds for market', 'request:', JSON.stringify(request, null, 2), 'response', JSON.stringify(response, null, 2));

  request = {
    ...commonParameters,
    marketNames: marketNames,
  };
  response = await settleFunds(request);
  console.log('settle funds for markets', 'request:', JSON.stringify(request, null, 2), 'response', JSON.stringify(response, null, 2));

  request = {
    ...commonParameters,
  };
  response = await settleFunds(request);
  console.log('settle all funds', 'request:', JSON.stringify(request, null, 2), 'response', JSON.stringify(response, null, 2));
});
