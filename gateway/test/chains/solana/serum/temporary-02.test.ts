import 'jest-extended';
import {Serum} from '../../../../src/connectors/serum/serum';
import {unpatch} from '../../../services/patch';
import {Solana} from '../../../../src/chains/solana/solana';
import {default as config} from './fixtures/serumConfig';
// @ts-ignore
import {
  cancelOpenOrders,
  cancelOrders,
  createOrders, getFilledOrders,
  getOpenOrders,
  getOrders
} from '../../../../src/clob/clob.controllers';
// @ts-ignore
import {getNewOrderTemplate} from "./fixtures/dummy";
import BN from "bn.js";
import {Account} from "@solana/web3.js";

jest.setTimeout(1000000);

// @ts-ignore
let serum: Serum;
// @ts-ignore
let solana: Solana;

beforeAll(async () => {
  solana = await Solana.getInstance(config.solana.network);

  serum = await Serum.getInstance(config.serum.chain, config.serum.network);

  await reset();
});

afterEach(() => {
  unpatch();
});

  // @ts-ignore
const commonParameters = {
  chain: config.serum.chain,
  network: config.serum.network,
  connector: config.serum.connector,
}

const reset = async () => {
  const connection = serum.getConnection();
  const markets = await (await Serum.getInstance(commonParameters.chain, commonParameters.network)).getAllMarkets();
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
  const marketNames = ['SOL/USDT', 'SOL/USDC'];
  // @ts-ignore
  const marketName = marketNames[0];

  const orderIds = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9'];
  // @ts-ignore
  const orderId = orderIds[0];

  // @ts-ignore
  let result: any;

  // // result = (await getMarkets({
  // //   ...commonParameters,
  // //   name: marketName,
  // // })).body;
  // // console.log('markets:', JSON.stringify(result, null, 2));
  // //
  // // result = (await getMarkets({
  // //   ...commonParameters,
  // //   names: marketNames,
  // // })).body;
  // // console.log('markets:', JSON.stringify(result, null, 2));
  // //
  // // result = (await getMarkets({
  // //   ...commonParameters
  // // })).body;
  // // console.log('markets:', JSON.stringify(result, null, 2));
  //
  // // result = (await getOrderBooks({
  // //   ...commonParameters,
  // //   marketName: marketName,
  // // })).body;
  // // console.log('order books:', JSON.stringify(result, null, 2));
  // //
  // // result = (await getOrderBooks({
  // //   ...commonParameters,
  // //   marketNames: marketNames,
  // // })).body;
  // // console.log('order books::', JSON.stringify(result, null, 2));
  // //
  // // result = (await getOrderBooks({
  // //   ...commonParameters
  // // })).body;
  // // console.log('order books::', JSON.stringify(result, null, 2));
  //
  // // result = (await getTickers({
  // //   ...commonParameters,
  // //   marketName: marketName,
  // // })).body;
  // // console.log('tickers:', JSON.stringify(result, null, 2));
  // //
  // // result = (await getTickers({
  // //   ...commonParameters,
  // //   marketNames: marketNames,
  // // })).body;
  // // console.log('tickers:', JSON.stringify(result, null, 2));
  // //
  // // result = (await getTickers({
  // //   ...commonParameters
  // // })).body;
  // // console.log('tickers:', JSON.stringify(result, null, 2));

  // result = await createOrders({
  //   ...commonParameters,
  //   order: (() => { const order = getNewOrderTemplate(); order.id = orderId; return order; })()
  // });
  // console.log('create order:', JSON.stringify(result, null, 2));
  //
  // result = await createOrders({
  //   ...commonParameters,
  //   orders: [
  //     (() => { const order = getNewOrderTemplate(); order.id = orderIds[1]; return order; })(),
  //     (() => { const order = getNewOrderTemplate(); order.id = orderIds[2]; return order; })(),
  //     (() => { const order = getNewOrderTemplate(); order.id = orderIds[3]; return order; })(),
  //     (() => { const order = getNewOrderTemplate(); order.id = orderIds[4]; return order; })(),
  //     (() => { const order = getNewOrderTemplate(); order.id = orderIds[5]; return order; })(),
  //     (() => { const order = getNewOrderTemplate(); order.id = orderIds[6]; return order; })(),
  //     (() => { const order = getNewOrderTemplate(); order.id = orderIds[7]; return order; })(),
  //     (() => { const order = getNewOrderTemplate(); order.id = orderIds[8]; return order; })(),
  //   ]
  // });
  // console.log('create orders:', JSON.stringify(result, null, 2));
  //
  // result = await getOpenOrders({
  //   ...commonParameters,
  //   order: {
  //     id: orderIds[0],
  //     ownerAddress: config.solana.wallet.owner.address
  //   },
  // });
  // console.log('get open order:', JSON.stringify(result, null, 2));
  //
  // result = await getOrders({
  //   ...commonParameters,
  //   order: {
  //     id: orderIds[1],
  //     ownerAddress: config.solana.wallet.owner.address
  //   },
  // });
  // console.log('get order:', JSON.stringify(result, null, 2));
  //
  // result = await getOpenOrders({
  //   ...commonParameters,
  //   orders: [{
  //     ids: orderIds.slice(2, 4),
  //     ownerAddress: config.solana.wallet.owner.address
  //   }],
  // });
  // console.log('get open orders:', JSON.stringify(result, null, 2));
  //
  // result = await getOrders({
  //   ...commonParameters,
  //   orders: [{
  //     ids: orderIds.slice(4, 6),
  //     ownerAddress: config.solana.wallet.owner.address
  //   }],
  // });
  // console.log('get orders:', JSON.stringify(result, null, 2));
  //
  // result = await getOpenOrders({
  //   ...commonParameters,
  //   ownerAddress: config.solana.wallet.owner.address,
  // });
  // console.log('get all open orders:', JSON.stringify(result, null, 2));
  //
  // result = await getOrders({
  //   ...commonParameters,
  //   ownerAddress: config.solana.wallet.owner.address,
  // });
  // console.log('get all orders:', JSON.stringify(result, null, 2));
  //
  // result = await cancelOpenOrders({
  //   ...commonParameters,
  //   order: {
  //     id: orderIds[0],
  //     ownerAddress: config.solana.wallet.owner.address
  //   },
  // });
  // console.log('cancel open order:', JSON.stringify(result, null, 2));
  //
  // result = await cancelOpenOrders({
  //   ...commonParameters,
  //   order: {
  //     id: orderIds[0],
  //     ownerAddress: config.solana.wallet.owner.address
  //   },
  // });
  // console.log('cancel open order:', JSON.stringify(result, null, 2));
  //
  // result = await cancelOrders({
  //   ...commonParameters,
  //   order: {
  //     id: orderIds[1],
  //     ownerAddress: config.solana.wallet.owner.address
  //   },
  // });
  // console.log('cancel order:', JSON.stringify(result, null, 2));
  //
  // result = await getOpenOrders({
  //   ...commonParameters,
  //   order: {
  //     id: orderIds[0],
  //     ownerAddress: config.solana.wallet.owner.address
  //   },
  // });
  // console.log('get open order:', JSON.stringify(result, null, 2));
  //
  // result = await getOrders({
  //   ...commonParameters,
  //   order: {
  //     id: orderIds[1],
  //     ownerAddress: config.solana.wallet.owner.address
  //   },
  // });
  // console.log('get order:', JSON.stringify(result, null, 2));
  //
  // result = await getFilledOrders({
  //   ...commonParameters,
  //   order: {
  //     id: orderIds[2],
  //     ownerAddress: config.solana.wallet.owner.address
  //   },
  // });
  // console.log('get filled order:', JSON.stringify(result, null, 2));
  //
  // result = await getFilledOrders({
  //   ...commonParameters,
  //   orders: [{
  //     ids: orderIds.slice(3, 5),
  //     ownerAddress: config.solana.wallet.owner.address
  //   }],
  // });
  // console.log('get filled orders:', JSON.stringify(result, null, 2));
  //
  // result = await getFilledOrders({
  //   ...commonParameters,
  //   ownerAddress: config.solana.wallet.owner.address,
  // });
  // console.log('get all filled orders:', JSON.stringify(result, null, 2));
  //
  // result = await cancelOpenOrders({
  //   ...commonParameters,
  //   orders: [{
  //     ids: orderIds.slice(2, 4),
  //     ownerAddress: config.solana.wallet.owner.address
  //   }],
  // });
  // console.log('cancel open orders:', JSON.stringify(result, null, 2));
  //
  // result = await cancelOrders({
  //   ...commonParameters,
  //   orders: [{
  //     ids: orderIds.slice(4, 6),
  //     ownerAddress: config.solana.wallet.owner.address
  //   }],
  // });
  // console.log('cancel orders:', JSON.stringify(result, null, 2));
  //
  // result = await getOpenOrders({
  //   ...commonParameters,
  //   orders: [{
  //     ids: orderIds.slice(2, 4),
  //     ownerAddress: config.solana.wallet.owner.address
  //   }],
  // });
  // console.log('get open orders:', JSON.stringify(result, null, 2));
  //
  // result = await getOrders({
  //   ...commonParameters,
  //   orders: [{
  //     ids: orderIds.slice(4, 6),
  //     ownerAddress: config.solana.wallet.owner.address
  //   }],
  // });
  // console.log('get orders:', JSON.stringify(result, null, 2));
  //
  // result = await cancelOpenOrders({
  //   ...commonParameters,
  //   ownerAddress: config.solana.wallet.owner.address,
  // });
  // console.log('cancel all open orders:', JSON.stringify(result, null, 2));
  //
  // result = await getOpenOrders({
  //   ...commonParameters,
  //   ownerAddress: config.solana.wallet.owner.address,
  // });
  // console.log('get all open orders:', JSON.stringify(result, null, 2));
  //
  // result = await getOrders({
  //   ...commonParameters,
  //   ownerAddress: config.solana.wallet.owner.address,
  // });
  // console.log('get all orders:', JSON.stringify(result, null, 2));
  //
  // result = await createOrders({
  //   ...commonParameters,
  //   orders: [
  //     (() => { const order = getNewOrderTemplate(); order.id = orderIds[8]; return order; })(),
  //     (() => { const order = getNewOrderTemplate(); order.id = orderIds[9]; return order; })(),
  //   ]
  // });
  // console.log('create orders:', JSON.stringify(result, null, 2));
  //
  // result = await getOpenOrders({
  //   ...commonParameters,
  //   ownerAddress: config.solana.wallet.owner.address,
  // });
  // console.log('get all open orders:', JSON.stringify(result, null, 2));
  //
  // result = await getOrders({
  //   ...commonParameters,
  //   ownerAddress: config.solana.wallet.owner.address,
  // });
  // console.log('get all orders:', JSON.stringify(result, null, 2));
  //
  // result = await cancelOrders({
  //   ...commonParameters,
  //   ownerAddress: config.solana.wallet.owner.address,
  // });
  // console.log('cancel all orders:', JSON.stringify(result, null, 2));
  //
  // result = await getOpenOrders({
  //   ...commonParameters,
  //   ownerAddress: config.solana.wallet.owner.address,
  // });
  // console.log('get all open orders:', JSON.stringify(result, null, 2));
  //
  // result = await getOrders({
  //   ...commonParameters,
  //   ownerAddress: config.solana.wallet.owner.address,
  // });
  // console.log('get all orders:', JSON.stringify(result, null, 2));

  /*
  create order [0]
  create orders [1, 2, 3, 4, 5, 6, 7]
  get open order [0]
  get order [1]
  get open orders [2, 3]
  get orders [4, 5]
  get all open orders [0, 1, 2, 3, 4, 5, 6, 7]
  get all orders [0, 1, 2, 3, 4, 5, 6, 7]
  cancel open order [0]
  cancel order [1]
  get canceled open order [0]
  get canceled order [1]
  get filled order [2]
  get filled orders [3, 4]
  get all filled orders [],
  cancel open orders [2, 3]
  cancel orders [4, 5]
  get canceled open orders [2, 3]
  get canceled orders [4, 5]
  cancel all open orders [6, 7]
  get all open orders
  get all orders
  create orders [8, 9]
  get all open orders
  get all orders
  cancel all orders [8, 9]
  get all open orders
  get all orders
   */
});
