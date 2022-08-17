import { MARKETS } from '@project-serum/serum';
import BN from 'bn.js';
import { StatusCodes } from 'http-status-codes';
import 'jest-extended';
import { Solana } from '../../../../src/chains/solana/solana';
import { Serum } from '../../../../src/connectors/serum/serum';
import {
  cancelOrders,
  createOrders,
  getFilledOrders,
  getMarkets,
  getOpenOrders,
  getOrderBooks,
  getOrders,
  getTickers,
  settleFunds,
} from '../../../../src/connectors/serum/serum.controllers';
import { getNotNullOrThrowError } from '../../../../src/connectors/serum/serum.helpers';
import {
  CancelOrderResponse,
  CreateOrderResponse,
  CreateOrdersRequest,
  GetMarketResponse,
  GetOpenOrderResponse,
  GetOrderBookResponse,
  GetOrderResponse,
  GetTickerResponse,
  OrderSide,
  OrderStatus,
} from '../../../../src/connectors/serum/serum.types';
import { ConfigManagerV2 } from '../../../../src/services/config-manager-v2';
import { HttpException } from '../../../../src/services/error-handler';
import { unpatch } from '../../../services/patch';
import { default as config } from './fixtures/config';
import { getNewCandidateOrdersTemplates } from './fixtures/helpers';
import {
  default as patchesCreator,
  enablePatches,
} from './fixtures/patches/patches';

enablePatches();

jest.setTimeout(5 * 60 * 1000);

let solana: Solana;
let serum: Serum;

let patches: Map<string, any>;

beforeAll(async () => {
  const configManager = ConfigManagerV2.getInstance();
  configManager.set('solana.timeout.all', 1);
  configManager.set('solana.retry.all.maxNumberOfRetries', 1);
  configManager.set('solana.retry.all.delayBetweenRetries', 1);
  configManager.set('solana.parallel.all.batchSize', 100);
  configManager.set('solana.parallel.all.delayBetweenBatches', 1);

  solana = await Solana.getInstance(config.serum.network);

  serum = await Serum.getInstance(config.serum.chain, config.serum.network);

  patches = await patchesCreator(solana, serum);

  patches.get('solana/loadTokens')();

  patches.get('serum/serumGetMarketsInformation')();
  patches.get('serum/market/load')();

  await solana.init();
  await serum.init();
});

afterEach(() => {
  unpatch();
});

/*
create order [0]
create orders [1, 2, 3, 4, 5, 6, 7]
get open order [0]
get order [1]
get open orders [2, 3]
get orders [4, 5]
get all open orders (0, 1, 2, 3, 4, 5, 6, 7)
get all orders (0, 1, 2, 3, 4, 5, 6, 7)
cancel order [0]
get canceled open order [0]
get filled order [1]
get filled orders [2, 3]
get all filled orders (),
cancel orders [4, 5]
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
settle all funds (SOL/USDT, SOL/USDC, SRM/SOL)
*/

const commonParameters = {
  chain: config.serum.chain,
  network: config.serum.network,
  connector: config.serum.connector,
};

// All markets intersection with the whitelisted ones excepted the blacklisted ones.
// This is defined in the 'gateway/conf/serum.yml' file.
const allowedMarkets = Object.values(config.solana.markets).map(
  (market) => market.name
);

const targetMarkets = allowedMarkets.slice(0, 2);

const numberOfAllowedMarkets = allowedMarkets.length;

const marketName = targetMarkets[0];

const orderIds = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9'];

const candidateOrders = getNewCandidateOrdersTemplates(10, 0);

let request: any;

let response: any;

it('getMarket ["SOL/USDT"]', async () => {
  request = {
    ...commonParameters,
    name: marketName,
  };
  response = await getMarkets(solana, serum, request);

  expect(response.status).toBe(StatusCodes.OK);

  const market: GetMarketResponse = response.body as GetMarketResponse;
  expect(market).toBeDefined();

  const targetMarket = MARKETS.find(
    (market) => market.name === marketName && !market.deprecated
  );
  expect(targetMarket).toBeDefined();

  expect(market.name).toBe(targetMarket?.name);
  expect(market.address.toString()).toBe(targetMarket?.address.toString());
  expect(market.programId.toString()).toBe(targetMarket?.programId.toString());
  expect(market.deprecated).toBe(targetMarket?.deprecated);
  expect(market.minimumOrderSize).toBeGreaterThan(0);
  expect(market.tickSize).toBeGreaterThan(0);
  expect(market.minimumBaseIncrement).toBeDefined();
  expect(
    new BN(getNotNullOrThrowError(market.minimumBaseIncrement)).gt(new BN(0))
  );
});

it('getMarkets ["SOL/USDT", "SOL/USDC"]', async () => {
  request = {
    ...commonParameters,
    names: targetMarkets,
  };
  response = await getMarkets(solana, serum, request);

  expect(response.status).toBe(StatusCodes.OK);

  const marketsMap: Map<string, GetMarketResponse> = new Map<
    string,
    GetMarketResponse
  >(Object.entries(response.body));
  expect(marketsMap).toBeDefined();
  expect(marketsMap.size).toBe(targetMarkets.length);

  for (const [marketName, market] of marketsMap) {
    const targetMarket = MARKETS.find(
      (market) => market.name === marketName && !market.deprecated
    );
    expect(targetMarket).toBeDefined();

    expect(market.name).toBe(targetMarket?.name);
    expect(market.address.toString()).toBe(targetMarket?.address.toString());
    expect(market.programId.toString()).toBe(
      targetMarket?.programId.toString()
    );
    expect(market.deprecated).toBe(targetMarket?.deprecated);
    expect(market.minimumOrderSize).toBeGreaterThan(0);
    expect(market.tickSize).toBeGreaterThan(0);
    expect(market.minimumBaseIncrement).toBeDefined();
    expect(
      new BN(getNotNullOrThrowError(market.minimumBaseIncrement)).gt(new BN(0))
    );
  }
});

it('getMarkets (all)', async () => {
  request = {
    ...commonParameters,
  };
  response = await getMarkets(solana, serum, request);

  expect(response.status).toBe(StatusCodes.OK);

  const marketsMap: Map<string, GetMarketResponse> = new Map<
    string,
    GetMarketResponse
  >(Object.entries(response.body));
  expect(marketsMap).toBeDefined();
  expect(marketsMap.size).toBe(numberOfAllowedMarkets);

  for (const [marketName, market] of marketsMap) {
    const targetMarket = MARKETS.find(
      (market) => market.name === marketName && !market.deprecated
    );
    expect(targetMarket).toBeDefined();

    expect(market.name).toBe(targetMarket?.name);
    expect(market.address.toString()).toBe(targetMarket?.address.toString());
    expect(market.programId.toString()).toBe(
      targetMarket?.programId.toString()
    );
    expect(market.deprecated).toBe(targetMarket?.deprecated);
    expect(market.minimumOrderSize).toBeGreaterThan(0);
    expect(market.tickSize).toBeGreaterThan(0);
    expect(market.minimumBaseIncrement).toBeDefined();
    expect(
      new BN(getNotNullOrThrowError(market.minimumBaseIncrement)).gt(new BN(0))
    );
  }
});

it('getOrderBook ["SOL/USDT"]', async () => {
  await patches.get('serum/market/loadAsks')('SOL/USDT');
  await patches.get('serum/market/loadBids')('SOL/USDT');

  request = {
    ...commonParameters,
    marketName: marketName,
  };
  response = await getOrderBooks(solana, serum, request);

  expect(response.status).toBe(StatusCodes.OK);

  const orderBook: GetOrderBookResponse = response.body as GetOrderBookResponse;
  expect(orderBook).toBeDefined();
  expect(orderBook.market).toBeDefined();

  const market = orderBook.market;

  const targetMarket = MARKETS.find(
    (market) => market.name === marketName && !market.deprecated
  );
  expect(targetMarket).toBeDefined();

  expect(market.name).toBe(targetMarket?.name);
  expect(market.address.toString()).toBe(targetMarket?.address.toString());
  expect(market.programId.toString()).toBe(targetMarket?.programId.toString());
  expect(market.deprecated).toBe(targetMarket?.deprecated);
  expect(market.minimumOrderSize).toBeGreaterThan(0);
  expect(market.tickSize).toBeGreaterThan(0);
  expect(market.minimumBaseIncrement).toBeDefined();
  expect(
    new BN(getNotNullOrThrowError(market.minimumBaseIncrement)).gt(new BN(0))
  );

  expect(Object.entries(orderBook.bids).length).toBeGreaterThan(0);
  expect(Object.entries(orderBook.bids).length).toBeGreaterThan(0);
});

it('getOrderBooks ["SOL/USDT", "SOL/USDC"]', async () => {
  await Promise.all(
    targetMarkets.flatMap(async (marketName) => {
      await patches.get('serum/market/loadAsks')(marketName);
      await patches.get('serum/market/loadBids')(marketName);
    })
  );

  request = {
    ...commonParameters,
    marketNames: targetMarkets,
  };
  response = await getOrderBooks(solana, serum, request);

  expect(response.status).toBe(StatusCodes.OK);

  const orderBooksMap: Map<string, GetOrderBookResponse> = new Map<
    string,
    GetOrderBookResponse
  >(Object.entries(response.body));
  expect(orderBooksMap).toBeDefined();
  expect(orderBooksMap.size).toBe(targetMarkets.length);

  for (const [marketName, orderBook] of orderBooksMap) {
    expect(orderBook).toBeDefined();
    expect(orderBook.market).toBeDefined();

    const market = orderBook.market;

    const targetMarket = MARKETS.find(
      (market) => market.name === marketName && !market.deprecated
    );
    expect(targetMarket).toBeDefined();

    expect(market.name).toBe(targetMarket?.name);
    expect(market.address.toString()).toBe(targetMarket?.address.toString());
    expect(market.programId.toString()).toBe(
      targetMarket?.programId.toString()
    );
    expect(market.deprecated).toBe(targetMarket?.deprecated);
    expect(market.minimumOrderSize).toBeGreaterThan(0);
    expect(market.tickSize).toBeGreaterThan(0);
    expect(market.minimumBaseIncrement).toBeDefined();
    expect(
      new BN(getNotNullOrThrowError(market.minimumBaseIncrement)).gt(new BN(0))
    );
  }
});

it('getOrderBooks (all)', async () => {
  await Promise.all(
    allowedMarkets.flatMap(async (marketName) => {
      await patches.get('serum/market/loadAsks')(marketName);
      await patches.get('serum/market/loadBids')(marketName);
    })
  );

  request = {
    ...commonParameters,
  };
  response = await getOrderBooks(solana, serum, request);

  expect(response.status).toBe(StatusCodes.OK);

  const orderBooksMap: Map<string, GetOrderBookResponse> = new Map<
    string,
    GetOrderBookResponse
  >(Object.entries(response.body));
  expect(orderBooksMap).toBeDefined();
  expect(orderBooksMap.size).toBe(numberOfAllowedMarkets);

  for (const [marketName, orderBook] of orderBooksMap) {
    expect(orderBook).toBeDefined();
    expect(orderBook.market).toBeDefined();

    const market = orderBook.market;

    const targetMarket = MARKETS.find(
      (market) => market.name === marketName && !market.deprecated
    );
    expect(targetMarket).toBeDefined();

    expect(market.name).toBe(targetMarket?.name);
    expect(market.address.toString()).toBe(targetMarket?.address.toString());
    expect(market.programId.toString()).toBe(
      targetMarket?.programId.toString()
    );
    expect(market.deprecated).toBe(targetMarket?.deprecated);
    expect(market.minimumOrderSize).toBeGreaterThan(0);
    expect(market.tickSize).toBeGreaterThan(0);
    expect(market.minimumBaseIncrement).toBeDefined();
    expect(
      new BN(getNotNullOrThrowError(market.minimumBaseIncrement)).gt(new BN(0))
    );
  }
});

it('getTicker ["SOL/USDT"]', async () => {
  patches.get('serum/getTicker')();

  request = {
    ...commonParameters,
    marketName: marketName,
  };
  response = await getTickers(solana, serum, request);

  expect(response.status).toBe(StatusCodes.OK);

  const ticker: GetTickerResponse = response.body as GetTickerResponse;
  expect(ticker).toBeDefined();

  const targetMarket = MARKETS.find(
    (market) => market.name === marketName && !market.deprecated
  );
  expect(targetMarket).toBeDefined();

  expect(ticker.price).toBeGreaterThan(0);
  expect(ticker.timestamp).toBeGreaterThan(0);
  expect(new Date(ticker.timestamp).getTime()).toBeLessThanOrEqual(Date.now());
});

it('getTickers ["SOL/USDT", "SOL/USDC"]', async () => {
  patches.get('serum/getTicker')();

  request = {
    ...commonParameters,
    marketNames: targetMarkets,
  };
  response = await getTickers(solana, serum, request);

  expect(response.status).toBe(StatusCodes.OK);

  const tickersMap: Map<string, GetTickerResponse> = new Map<
    string,
    GetTickerResponse
  >(Object.entries(response.body));
  expect(tickersMap).toBeDefined();
  expect(tickersMap.size).toBe(targetMarkets.length);

  for (const [marketName, ticker] of tickersMap) {
    expect(ticker).toBeDefined();

    const targetMarket = MARKETS.find(
      (market) => market.name === marketName && !market.deprecated
    );
    expect(targetMarket).toBeDefined();

    expect(ticker.price).toBeGreaterThan(0);
    expect(ticker.timestamp).toBeGreaterThan(0);
    expect(new Date(ticker.timestamp).getTime()).toBeLessThanOrEqual(
      Date.now()
    );
  }
});

it('getTickers (all)', async () => {
  patches.get('serum/getTicker')();

  request = {
    ...commonParameters,
  };
  response = await getTickers(solana, serum, request);

  expect(response.status).toBe(StatusCodes.OK);

  const tickersMap: Map<string, GetTickerResponse> = new Map<
    string,
    GetTickerResponse
  >(Object.entries(response.body));
  expect(tickersMap).toBeDefined();
  expect(tickersMap.size).toBe(numberOfAllowedMarkets);

  for (const [marketName, ticker] of tickersMap) {
    expect(ticker).toBeDefined();

    const targetMarket = MARKETS.find(
      (market) => market.name === marketName && !market.deprecated
    );
    expect(targetMarket).toBeDefined();

    expect(ticker.price).toBeGreaterThan(0);
    expect(ticker.timestamp).toBeGreaterThan(0);
    expect(new Date(ticker.timestamp).getTime()).toBeLessThanOrEqual(
      Date.now()
    );
  }
});

it('cancelOrders (all)', async () => {
  await patches.get('serum/market/asksBidsForAllMarkets')();
  patches.get('solana/getKeyPair')();
  patches.get('serum/serumMarketCancelOrdersAndSettleFunds')();
  await patches.get('serum/market/loadOrdersForOwner')([]);

  request = {
    ...commonParameters,
    ownerAddress: config.solana.wallet.owner.publicKey,
  };
  response = await cancelOrders(solana, serum, request);

  expect(response.status).toBe(StatusCodes.OK);

  const canceledOrdersMap: Map<string, CancelOrderResponse> = new Map<
    string,
    CancelOrderResponse
  >(Object.entries(response.body));

  expect(canceledOrdersMap).toBeDefined();
  expect(canceledOrdersMap.size).toBe(0);
});

it('getOpenOrders (all)', async () => {
  await patches.get('serum/market/asksBidsForAllMarkets')();
  patches.get('solana/getKeyPair')();
  await patches.get('serum/market/loadOrdersForOwner')([]);

  request = {
    ...commonParameters,
    ownerAddress: config.solana.wallet.owner.publicKey,
  };
  response = await getOpenOrders(solana, serum, request);

  expect(response.status).toBe(StatusCodes.OK);

  const openOrdersMapMap: Map<
    string,
    Map<string, GetOpenOrderResponse>
  > = new Map<string, Map<string, GetOpenOrderResponse>>(
    Object.entries(response.body)
  );

  expect(openOrdersMapMap).toBeDefined();
  expect(openOrdersMapMap.size).toBe(numberOfAllowedMarkets);

  for (const [marketName, openOrdersMapObject] of openOrdersMapMap) {
    const openOrdersMap = new Map<string, GetOpenOrderResponse>(
      Object.entries(openOrdersMapObject)
    );
    expect(allowedMarkets).toContain(marketName);
    expect(openOrdersMap).toBeDefined();
    expect(openOrdersMap.size).toBe(0);
  }
});

it('createOrder [0]', async () => {
  patches.get('solana/getKeyPair')();
  patches.get('serum/serumMarketPlaceOrders')();

  request = {
    ...commonParameters,
    order: candidateOrders[0],
  };
  response = await createOrders(solana, serum, request);

  expect(response.status).toBe(StatusCodes.OK);

  const createdOrder: CreateOrderResponse =
    response.body as CreateOrderResponse;
  const candidateOrder = request.order;

  expect(createdOrder).toBeDefined();
  expect(createdOrder.id).toBe(candidateOrder.id);
  // expect(createdOrder.exchangeId).toBeDefined();
  expect(createdOrder.marketName).toBe(candidateOrder.marketName);
  expect(createdOrder.ownerAddress).toBe(candidateOrder.ownerAddress);
  expect(createdOrder.price).toBe(candidateOrder.price);
  expect(createdOrder.amount).toBe(candidateOrder.amount);
  expect(createdOrder.side).toBe(candidateOrder.side);
  expect(createdOrder.status).toBe(OrderStatus.OPEN);
  expect(createdOrder.type).toBe(candidateOrder.type);
});

it('createOrders [1, 2, 3, 4, 5, 6, 7]', async () => {
  patches.get('solana/getKeyPair')();
  patches.get('serum/serumMarketPlaceOrders')();

  request = {
    ...commonParameters,
    orders: candidateOrders.slice(1, 8),
  };
  response = await createOrders(solana, serum, request);

  expect(response.status).toBe(StatusCodes.OK);

  const createdOrders: Map<string, CreateOrderResponse> = new Map<
    string,
    CreateOrderResponse
  >(Object.entries(response.body));

  expect(createdOrders).toBeDefined();
  expect(createdOrders.size).toBe(request.orders.length);

  for (const [orderId, createdOrder] of createdOrders) {
    const candidateOrder = request.orders.find(
      (order: CreateOrdersRequest) => order.id === orderId
    );

    expect(createdOrder).toBeDefined();
    expect(createdOrder.id).toBe(orderId);
    // expect(createdOrder.exchangeId).toBeDefined();
    expect(createdOrder.marketName).toBe(candidateOrder.marketName);
    expect(createdOrder.ownerAddress).toBe(candidateOrder.ownerAddress);
    expect(createdOrder.price).toBe(candidateOrder.price);
    expect(createdOrder.amount).toBe(candidateOrder.amount);
    expect(createdOrder.side).toBe(candidateOrder.side);
    expect(createdOrder.status).toBe(OrderStatus.OPEN);
    expect(createdOrder.type).toBe(candidateOrder.type);
  }
});

it('getOpenOrder [0]', async () => {
  await patches.get('serum/market/asksBidsForAllMarkets')();
  patches.get('solana/getKeyPair')();
  await patches.get('serum/market/loadOrdersForOwner')([candidateOrders[0]]);

  request = {
    ...commonParameters,
    order: {
      id: orderIds[0],
      ownerAddress: config.solana.wallet.owner.publicKey,
    },
  };
  response = await getOpenOrders(solana, serum, request);

  expect(response.status).toBe(StatusCodes.OK);

  const openOrder: GetOpenOrderResponse = response.body as GetOpenOrderResponse;

  expect(openOrder).toBeDefined();
  expect(openOrder.id).toBe(orderIds[0]);
  // expect(openOrder.exchangeId).toBeDefined();
  expect(targetMarkets).toContain(openOrder.marketName);
  expect(openOrder.ownerAddress).toBe(config.solana.wallet.owner.publicKey);
  expect(openOrder.price).toBeGreaterThan(0);
  expect(openOrder.amount).toBeGreaterThan(0);
  expect(Object.keys(OrderSide)).toContain(openOrder.side);
  expect(openOrder.status).toBe(OrderStatus.OPEN);
  // expect(Object.keys(OrderType)).toContain(openOrder.type);
});

it('getOrder [1]', async () => {
  await patches.get('serum/market/asksBidsForAllMarkets')();
  patches.get('solana/getKeyPair')();
  await patches.get('serum/market/loadOrdersForOwner')([candidateOrders[1]]);
  patches.get('serum/serumMarketLoadFills')();

  request = {
    ...commonParameters,
    order: {
      id: orderIds[1],
      ownerAddress: config.solana.wallet.owner.publicKey,
    },
  };
  response = await getOrders(solana, serum, request);

  expect(response.status).toBe(StatusCodes.OK);

  const openOrder: GetOrderResponse = response.body as GetOrderResponse;

  expect(openOrder).toBeDefined();
  expect(openOrder.id).toBe(orderIds[1]);
  // expect(openOrder.exchangeId).toBeDefined();
  expect(targetMarkets).toContain(openOrder.marketName);
  expect(openOrder.ownerAddress).toBe(config.solana.wallet.owner.publicKey);
  expect(openOrder.price).toBeGreaterThan(0);
  expect(openOrder.amount).toBeGreaterThan(0);
  expect(Object.keys(OrderSide)).toContain(openOrder.side);
  expect(openOrder.status).toBe(OrderStatus.OPEN);
  // expect(Object.keys(OrderType)).toContain(openOrder.type);
});

it('getOpenOrders [2, 3]', async () => {
  await patches.get('serum/market/asksBidsForAllMarkets')();
  patches.get('solana/getKeyPair')();
  await patches.get('serum/market/loadOrdersForOwner')(
    candidateOrders.slice(2, 4)
  );

  request = {
    ...commonParameters,
    orders: [
      {
        ids: orderIds.slice(2, 4),
        ownerAddress: config.solana.wallet.owner.publicKey,
      },
    ],
  };
  response = await getOpenOrders(solana, serum, request);

  expect(response.status).toBe(StatusCodes.OK);

  const openOrders: Map<string, GetOpenOrderResponse> = new Map<
    string,
    GetOpenOrderResponse
  >(Object.entries(response.body));
  expect(openOrders).toBeDefined();
  expect(openOrders.size).toBe(request.orders[0].ids.length);

  for (const [id, openOrder] of openOrders) {
    expect(openOrder).toBeDefined();
    expect(request.orders[0].ids).toContain(openOrder.id);
    expect(openOrder.id).toBe(id);
    expect(targetMarkets).toContain(openOrder.marketName);
    expect(openOrder.ownerAddress).toBe(config.solana.wallet.owner.publicKey);
    expect(openOrder.price).toBeGreaterThan(0);
    expect(openOrder.amount).toBeGreaterThan(0);
    expect(Object.keys(OrderSide)).toContain(openOrder.side);
    expect(openOrder.status).toBe(OrderStatus.OPEN);
    // expect(Object.keys(OrderType)).toContain(openOrder.type);
  }
});

it('getOrders [4, 5]', async () => {
  await patches.get('serum/market/asksBidsForAllMarkets')();
  patches.get('solana/getKeyPair')();
  await patches.get('serum/market/loadOrdersForOwner')(
    candidateOrders.slice(4, 6)
  );
  patches.get('serum/serumMarketLoadFills')();

  request = {
    ...commonParameters,
    orders: [
      {
        ids: orderIds.slice(4, 6),
        ownerAddress: config.solana.wallet.owner.publicKey,
      },
    ],
  };
  response = await getOrders(solana, serum, request);

  expect(response.status).toBe(StatusCodes.OK);

  const ordersMap: Map<string, GetOrderResponse> = new Map<
    string,
    GetOrderResponse
  >(Object.entries(response.body));
  expect(ordersMap).toBeDefined();
  expect(ordersMap.size).toBe(request.orders[0].ids.length);

  for (const [id, order] of ordersMap) {
    expect(order).toBeDefined();
    expect(request.orders[0].ids).toContain(order.id);
    expect(order.id).toBe(id);
    expect(targetMarkets).toContain(order.marketName);
    expect(order.ownerAddress).toBe(config.solana.wallet.owner.publicKey);
    expect(order.price).toBeGreaterThan(0);
    expect(order.amount).toBeGreaterThan(0);
    expect(order.side).toBeOneOf(Object.keys(OrderSide));
    expect(order.status).toBe(OrderStatus.OPEN);
    // expect(order.type).toBeOneOf(Object.keys(OrderType));
  }
});

it('getOpenOrders (all)', async () => {
  await patches.get('serum/market/asksBidsForAllMarkets')();
  patches.get('solana/getKeyPair')();
  await patches.get('serum/market/loadOrdersForOwner')(
    candidateOrders.slice(0, 8)
  );

  request = {
    ...commonParameters,
    ownerAddress: config.solana.wallet.owner.publicKey,
  };
  response = await getOpenOrders(solana, serum, request);

  expect(response.status).toBe(StatusCodes.OK);

  const openOrdersMapMap: Map<
    string,
    Map<string, GetOpenOrderResponse>
  > = new Map<string, Map<string, GetOpenOrderResponse>>(
    Object.entries(response.body)
  );

  expect(openOrdersMapMap).toBeDefined();
  expect(openOrdersMapMap.size).toBe(numberOfAllowedMarkets);

  for (const [marketName, openOrdersMapObject] of openOrdersMapMap) {
    const openOrdersMap = new Map<string, GetOpenOrderResponse>(
      Object.entries(openOrdersMapObject)
    );
    expect(openOrdersMap).toBeDefined();

    for (const [id, openOrder] of openOrdersMap) {
      expect(openOrder).toBeDefined();
      expect(openOrder.id).toBe(id);
      expect(openOrder.exchangeId).toBeDefined();
      expect(openOrder.marketName).toBe(marketName);
      expect(targetMarkets).toContain(openOrder.marketName);
      expect(openOrder.ownerAddress).toBe(config.solana.wallet.owner.publicKey);
      expect(openOrder.price).toBeGreaterThan(0);
      expect(openOrder.amount).toBeGreaterThan(0);
      expect(Object.keys(OrderSide)).toContain(openOrder.side);
      expect(openOrder.status).toBe(OrderStatus.OPEN);
      // expect(openOrder.type).toBeOneOf(Object.keys(OrderType));
    }
  }
});

it('getOrders (all)', async () => {
  await patches.get('serum/market/asksBidsForAllMarkets')();
  patches.get('solana/getKeyPair')();
  await patches.get('serum/market/loadOrdersForOwner')(
    candidateOrders.slice(0, 8)
  );
  patches.get('serum/serumMarketLoadFills')();

  request = {
    ...commonParameters,
    ownerAddress: config.solana.wallet.owner.publicKey,
  };
  response = await getOrders(solana, serum, request);

  expect(response.status).toBe(StatusCodes.OK);

  const ordersMapMap: Map<string, Map<string, GetOrderResponse>> = new Map<
    string,
    Map<string, GetOrderResponse>
  >(Object.entries(response.body));

  expect(ordersMapMap).toBeDefined();
  expect(ordersMapMap.size).toBe(numberOfAllowedMarkets);

  for (const [marketName, ordersMapObject] of ordersMapMap) {
    const ordersMap = new Map<string, GetOrderResponse>(
      Object.entries(ordersMapObject)
    );
    expect(ordersMap).toBeDefined();

    for (const [id, order] of ordersMap) {
      expect(order).toBeDefined();
      expect(order.id).toBe(id);
      expect(order.exchangeId).toBeDefined();
      expect(order.marketName).toBe(marketName);
      expect(targetMarkets).toContain(order.marketName);
      expect(order.ownerAddress).toBe(config.solana.wallet.owner.publicKey);
      expect(order.price).toBeGreaterThan(0);
      expect(order.amount).toBeGreaterThan(0);
      expect(order.side).toBeOneOf(Object.keys(OrderSide));
      expect(order.status).toBe(OrderStatus.OPEN);
      // expect(order.type).toBeOneOf(Object.keys(OrderType));
    }
  }
});

it('cancelOrders [0]', async () => {
  await patches.get('serum/market/asksBidsForAllMarkets')();
  patches.get('solana/getKeyPair')();
  patches.get('serum/serumMarketCancelOrdersAndSettleFunds')();
  await patches.get('serum/market/loadOrdersForOwner')([candidateOrders[0]]);

  request = {
    ...commonParameters,
    order: {
      id: orderIds[0],
      ownerAddress: config.solana.wallet.owner.publicKey,
      marketName: marketName,
    },
  };
  response = await cancelOrders(solana, serum, request);

  expect(response.status).toBe(StatusCodes.OK);

  const canceledOrder: CancelOrderResponse =
    response.body as CancelOrderResponse;
  const candidateOrder: CreateOrdersRequest = getNotNullOrThrowError(
    candidateOrders.find((item) => item.id === request.order.id)
  );

  expect(canceledOrder).toBeDefined();
  expect(canceledOrder.id).toBe(candidateOrder.id);
  expect(canceledOrder.exchangeId).toBeDefined();
  expect(canceledOrder.marketName).toBe(candidateOrder.marketName);
  expect(canceledOrder.ownerAddress).toBe(candidateOrder.ownerAddress);
  expect(canceledOrder.price).toBe(candidateOrder.price);
  expect(canceledOrder.amount).toBe(candidateOrder.amount);
  expect(canceledOrder.side).toBe(candidateOrder.side);
  expect([OrderStatus.CANCELED, OrderStatus.CANCELATION_PENDING]).toContain(
    canceledOrder.status
  );
  // expect(canceledOrder.type).toBe(candidateOrder.type);
});

it('getOpenOrders [0]', async () => {
  await patches.get('serum/market/asksBidsForAllMarkets')();
  patches.get('solana/getKeyPair')();
  await patches.get('serum/market/loadOrdersForOwner')([]);

  request = {
    ...commonParameters,
    order: {
      id: orderIds[0],
      ownerAddress: config.solana.wallet.owner.publicKey,
    },
  };

  await expect(async () => {
    await getOpenOrders(solana, serum, request);
  }).rejects.toThrowError(
    new HttpException(
      StatusCodes.NOT_FOUND,
      'No open order found with id / exchange id "0 / undefined".'
    )
  );
});

it('getFilledOrders [1]', async () => {
  await patches.get('serum/market/asksBidsForAllMarkets')();
  patches.get('solana/getKeyPair')();
  patches.get('serum/serumMarketLoadFills')();

  request = {
    ...commonParameters,
    order: {
      id: orderIds[1],
      ownerAddress: config.solana.wallet.owner.publicKey,
    },
  };

  await expect(async () => {
    await getFilledOrders(solana, serum, request);
  }).rejects.toThrowError(
    new HttpException(
      StatusCodes.NOT_FOUND,
      'No filled order found with id / exchange id "1 / undefined".'
    )
  );
});

it('getFilledOrders [2, 3]', async () => {
  await patches.get('serum/market/asksBidsForAllMarkets')();
  patches.get('solana/getKeyPair')();
  patches.get('serum/serumMarketLoadFills')();

  request = {
    ...commonParameters,
    orders: [
      {
        ids: orderIds.slice(2, 4),
        ownerAddress: config.solana.wallet.owner.publicKey,
      },
    ],
  };

  await expect(async () => {
    await getFilledOrders(solana, serum, request);
  }).rejects.toThrowError(
    new HttpException(StatusCodes.NOT_FOUND, 'No filled orders found.')
  );
});

it('getFilledOrders (all)', async () => {
  await patches.get('serum/market/asksBidsForAllMarkets')();
  patches.get('solana/getKeyPair')();
  patches.get('serum/serumMarketLoadFills')();

  request = {
    ...commonParameters,
    ownerAddress: config.solana.wallet.owner.publicKey,
  };
  response = await getFilledOrders(solana, serum, request);

  expect(response.status).toBe(StatusCodes.OK);

  const filledOrdersMapMap: Map<
    string,
    Map<string, GetOpenOrderResponse>
  > = new Map<string, Map<string, GetOpenOrderResponse>>(
    Object.entries(response.body)
  );

  expect(filledOrdersMapMap).toBeDefined();
  expect(filledOrdersMapMap.size).toBe(numberOfAllowedMarkets);

  for (const [marketName, ordersMap] of filledOrdersMapMap) {
    expect(ordersMap).toBeDefined();
    expect(ordersMap.size).toBeUndefined();
    expect(allowedMarkets).toContain(marketName);
  }
});

it('cancelOrders [4, 5]', async () => {
  await patches.get('serum/market/asksBidsForAllMarkets')();
  patches.get('solana/getKeyPair')();
  patches.get('serum/serumMarketCancelOrdersAndSettleFunds')();
  await patches.get('serum/market/loadOrdersForOwner')(
    candidateOrders.slice(4, 6)
  );

  request = {
    ...commonParameters,
    orders: [
      {
        ids: orderIds.slice(4, 6),
        ownerAddress: config.solana.wallet.owner.publicKey,
        marketName: marketName,
      },
    ],
  };
  response = await cancelOrders(solana, serum, request);

  expect(response.status).toBe(StatusCodes.OK);

  const canceledOrdersMap: Map<string, CancelOrderResponse> = new Map<
    string,
    CancelOrderResponse
  >(Object.entries(response.body));
  expect(canceledOrdersMap).toBeDefined();
  expect(canceledOrdersMap.size).toBe(request.orders[0].ids.length);

  for (const [id, canceledOrder] of canceledOrdersMap) {
    expect(canceledOrder).toBeDefined();
    expect(canceledOrder.id).toBe(id);
    expect(canceledOrder.exchangeId).toBeDefined();
    expect(targetMarkets).toContain(canceledOrder.marketName);
    expect(canceledOrder.ownerAddress).toBe(
      config.solana.wallet.owner.publicKey
    );
    expect(canceledOrder.price).toBeGreaterThan(0);
    expect(canceledOrder.amount).toBeGreaterThan(0);
    expect(Object.keys(OrderSide)).toContain(canceledOrder.side);
    expect([OrderStatus.CANCELED, OrderStatus.CANCELATION_PENDING]).toContain(
      canceledOrder.status
    );
    // expect(canceledOrder.type).toBeOneOf(Object.keys(OrderType));
  }
});

it('getOrders [4, 5]', async () => {
  await patches.get('serum/market/asksBidsForAllMarkets')();
  patches.get('solana/getKeyPair')();
  await patches.get('serum/market/loadOrdersForOwner')([]);
  patches.get('serum/serumMarketLoadFills')();

  request = {
    ...commonParameters,
    orders: [
      {
        ids: orderIds.slice(4, 6),
        ownerAddress: config.solana.wallet.owner.publicKey,
      },
    ],
  };

  await expect(async () => {
    await getOrders(solana, serum, request);
  }).rejects.toThrowError(
    new HttpException(StatusCodes.NOT_FOUND, 'No orders found.')
  );
});

it('cancelOrders (all)', async () => {
  await patches.get('serum/market/asksBidsForAllMarkets')();
  patches.get('solana/getKeyPair')();
  patches.get('serum/serumMarketCancelOrdersAndSettleFunds')();
  await patches.get('serum/market/loadOrdersForOwner')(
    candidateOrders.slice(1, 2).concat(candidateOrders.slice(6, 8))
  );

  request = {
    ...commonParameters,
    ownerAddress: config.solana.wallet.owner.publicKey,
  };
  response = await cancelOrders(solana, serum, request);

  expect(response.status).toBe(StatusCodes.OK);

  const canceledOrdersMap: Map<string, CancelOrderResponse> = new Map<
    string,
    CancelOrderResponse
  >(Object.entries(response.body));

  expect(canceledOrdersMap).toBeDefined();
  expect(canceledOrdersMap.size).toBe(numberOfAllowedMarkets);

  for (const [id, canceledOrder] of canceledOrdersMap) {
    expect(canceledOrder).toBeDefined();
    expect(canceledOrder.id).toBe(id);
    expect(canceledOrder.exchangeId).toBeDefined();
    expect(targetMarkets).toContain(canceledOrder.marketName);
    expect(canceledOrder.ownerAddress).toBe(
      config.solana.wallet.owner.publicKey
    );
    expect(canceledOrder.price).toBeGreaterThan(0);
    expect(canceledOrder.amount).toBeGreaterThan(0);
    expect(Object.keys(OrderSide)).toContain(canceledOrder.side);
    expect([OrderStatus.CANCELED, OrderStatus.CANCELATION_PENDING]).toContain(
      canceledOrder.status
    );
    // expect(canceledOrder.type).toBeOneOf(Object.keys(OrderType));
  }
});

it('getOpenOrders (all)', async () => {
  await patches.get('serum/market/asksBidsForAllMarkets')();
  patches.get('solana/getKeyPair')();
  await patches.get('serum/market/loadOrdersForOwner')([]);

  request = {
    ...commonParameters,
    ownerAddress: config.solana.wallet.owner.publicKey,
  };
  response = await getOpenOrders(solana, serum, request);

  expect(response.status).toBe(StatusCodes.OK);

  const openOrdersMapMap: Map<
    string,
    Map<string, GetOpenOrderResponse>
  > = new Map<string, Map<string, GetOpenOrderResponse>>(
    Object.entries(response.body)
  );

  expect(openOrdersMapMap).toBeDefined();
  expect(openOrdersMapMap.size).toBe(numberOfAllowedMarkets);

  for (const [marketName, openOrdersMapObject] of openOrdersMapMap) {
    const openOrdersMap = new Map<string, GetOpenOrderResponse>(
      Object.entries(openOrdersMapObject)
    );
    expect(allowedMarkets).toContain(marketName);
    expect(openOrdersMap).toBeDefined();
    expect(openOrdersMap.size).toBe(0);
  }
});

it('getOrders (all)', async () => {
  await patches.get('serum/market/asksBidsForAllMarkets')();
  patches.get('solana/getKeyPair')();
  await patches.get('serum/market/loadOrdersForOwner')([]);
  patches.get('serum/serumMarketLoadFills')();

  request = {
    ...commonParameters,
    ownerAddress: config.solana.wallet.owner.publicKey,
  };
  response = await getOrders(solana, serum, request);

  expect(response.status).toBe(StatusCodes.OK);

  const ordersMapMap: Map<string, Map<string, GetOrderResponse>> = new Map<
    string,
    Map<string, GetOrderResponse>
  >(Object.entries(response.body));

  expect(ordersMapMap).toBeDefined();
  expect(ordersMapMap.size).toBe(numberOfAllowedMarkets);

  for (const [marketName, ordersMapObject] of ordersMapMap) {
    const ordersMap = new Map<string, GetOrderResponse>(
      Object.entries(ordersMapObject)
    );
    expect(allowedMarkets).toContain(marketName);
    expect(ordersMap).toBeDefined();
    expect(ordersMap.size).toBe(0);
  }
});

it('createOrders [8, 9]', async () => {
  patches.get('solana/getKeyPair')();
  patches.get('serum/serumMarketPlaceOrders')();

  request = {
    ...commonParameters,
    orders: candidateOrders.slice(8, 10),
  };
  response = await createOrders(solana, serum, request);

  expect(response.status).toBe(StatusCodes.OK);

  const createdOrders: Map<string, CreateOrderResponse> = new Map<
    string,
    CreateOrderResponse
  >(Object.entries(response.body));

  expect(createdOrders).toBeDefined();
  expect(createdOrders.size).toBe(request.orders.length);

  for (const [orderId, createdOrder] of createdOrders) {
    const candidateOrder = request.orders.find(
      (order: CreateOrdersRequest) => order.id === orderId
    );

    expect(createdOrder).toBeDefined();
    expect(createdOrder.id).toBe(orderId);
    // expect(createdOrder.exchangeId).toBeDefined();
    expect(createdOrder.marketName).toBe(candidateOrder.marketName);
    expect(createdOrder.ownerAddress).toBe(candidateOrder.ownerAddress);
    expect(createdOrder.price).toBe(candidateOrder.price);
    expect(createdOrder.amount).toBe(candidateOrder.amount);
    expect(createdOrder.side).toBe(candidateOrder.side);
    expect(createdOrder.status).toBeOneOf([
      OrderStatus.OPEN,
      OrderStatus.CREATION_PENDING,
    ]);
    expect(createdOrder.type).toBe(candidateOrder.type);
  }
});

it('getOpenOrders (all)', async () => {
  await patches.get('serum/market/asksBidsForAllMarkets')();
  patches.get('solana/getKeyPair')();
  await patches.get('serum/market/loadOrdersForOwner')(
    candidateOrders.slice(8, 10)
  );

  request = {
    ...commonParameters,
    ownerAddress: config.solana.wallet.owner.publicKey,
  };
  response = await getOpenOrders(solana, serum, request);

  expect(response.status).toBe(StatusCodes.OK);

  const openOrdersMapMap: Map<
    string,
    Map<string, GetOpenOrderResponse>
  > = new Map<string, Map<string, GetOpenOrderResponse>>(
    Object.entries(response.body)
  );

  expect(openOrdersMapMap).toBeDefined();
  expect(openOrdersMapMap.size).toBe(numberOfAllowedMarkets);

  for (const [marketName, openOrdersMapObject] of openOrdersMapMap) {
    const openOrdersMap = new Map<string, GetOpenOrderResponse>(
      Object.entries(openOrdersMapObject)
    );
    expect(openOrdersMap).toBeDefined();

    for (const [id, openOrder] of openOrdersMap) {
      expect(openOrder).toBeDefined();
      expect(openOrder.id).toBe(id);
      expect(openOrder.exchangeId).toBeDefined();
      expect(openOrder.marketName).toBe(marketName);
      expect(targetMarkets).toContain(openOrder.marketName);
      expect(openOrder.ownerAddress).toBe(config.solana.wallet.owner.publicKey);
      expect(openOrder.price).toBeGreaterThan(0);
      expect(openOrder.amount).toBeGreaterThan(0);
      expect(Object.keys(OrderSide)).toContain(openOrder.side);
      expect(openOrder.status).toBe(OrderStatus.OPEN);
      // expect(openOrder.type).toBeOneOf(Object.keys(OrderType));
    }
  }
});

it('getOrders (all)', async () => {
  await patches.get('serum/market/asksBidsForAllMarkets')();
  patches.get('solana/getKeyPair')();
  await patches.get('serum/market/loadOrdersForOwner')(
    candidateOrders.slice(8, 10)
  );
  patches.get('serum/serumMarketLoadFills')();

  request = {
    ...commonParameters,
    ownerAddress: config.solana.wallet.owner.publicKey,
  };
  response = await getOrders(solana, serum, request);

  expect(response.status).toBe(StatusCodes.OK);

  const ordersMapMap: Map<string, Map<string, GetOpenOrderResponse>> = new Map<
    string,
    Map<string, GetOpenOrderResponse>
  >(Object.entries(response.body));

  expect(ordersMapMap).toBeDefined();
  expect(ordersMapMap.size).toBe(numberOfAllowedMarkets);

  for (const [marketName, ordersMapObject] of ordersMapMap) {
    const openOrdersMap = new Map<string, GetOpenOrderResponse>(
      Object.entries(ordersMapObject)
    );
    expect(openOrdersMap).toBeDefined();

    for (const [id, order] of openOrdersMap) {
      expect(order).toBeDefined();
      expect(order.id).toBe(id);
      expect(order.exchangeId).toBeDefined();
      expect(order.marketName).toBe(marketName);
      expect(targetMarkets).toContain(order.marketName);
      expect(order.ownerAddress).toBe(config.solana.wallet.owner.publicKey);
      expect(order.price).toBeGreaterThan(0);
      expect(order.amount).toBeGreaterThan(0);
      expect(Object.keys(OrderSide)).toContain(order.side);
      expect(order.status).toBe(OrderStatus.OPEN);
      // expect(order.type).toBeOneOf(Object.keys(OrderType));
    }
  }
});

it('cancelOrders (all)', async () => {
  await patches.get('serum/market/asksBidsForAllMarkets')();
  patches.get('solana/getKeyPair')();
  patches.get('serum/serumMarketCancelOrdersAndSettleFunds')();
  await patches.get('serum/market/loadOrdersForOwner')(
    candidateOrders.slice(8, 10)
  );

  request = {
    ...commonParameters,
    ownerAddress: config.solana.wallet.owner.publicKey,
  };
  response = await cancelOrders(solana, serum, request);

  expect(response.status).toBe(StatusCodes.OK);

  const canceledOrdersMap: Map<string, CancelOrderResponse> = new Map<
    string,
    CancelOrderResponse
  >(Object.entries(response.body));

  expect(canceledOrdersMap).toBeDefined();
  expect(canceledOrdersMap.size).toBe(2);

  for (const [id, canceledOrder] of canceledOrdersMap) {
    expect(canceledOrder).toBeDefined();
    expect(canceledOrder.id).toBe(id);
    expect(canceledOrder.exchangeId).toBeDefined();
    expect(targetMarkets).toContain(canceledOrder.marketName);
    expect(canceledOrder.ownerAddress).toBe(
      config.solana.wallet.owner.publicKey
    );
    expect(canceledOrder.price).toBeGreaterThan(0);
    expect(canceledOrder.amount).toBeGreaterThan(0);
    expect(Object.keys(OrderSide)).toContain(canceledOrder.side);
    expect([OrderStatus.CANCELED, OrderStatus.CANCELATION_PENDING]).toContain(
      canceledOrder.status
    );
    // expect(canceledOrder.type).toBeOneOf(Object.keys(OrderType));
  }
});

it('getOpenOrders (all)', async () => {
  await patches.get('serum/market/asksBidsForAllMarkets')();
  patches.get('solana/getKeyPair')();
  await patches.get('serum/market/loadOrdersForOwner')([]);

  request = {
    ...commonParameters,
    ownerAddress: config.solana.wallet.owner.publicKey,
  };
  response = await getOpenOrders(solana, serum, request);

  expect(response.status).toBe(StatusCodes.OK);

  const openOrdersMapMap: Map<
    string,
    Map<string, GetOpenOrderResponse>
  > = new Map<string, Map<string, GetOpenOrderResponse>>(
    Object.entries(response.body)
  );

  expect(openOrdersMapMap).toBeDefined();
  expect(openOrdersMapMap.size).toBe(numberOfAllowedMarkets);

  for (const [marketName, openOrdersMapObject] of openOrdersMapMap) {
    const openOrdersMap = new Map<string, GetOpenOrderResponse>(
      Object.entries(openOrdersMapObject)
    );
    expect(allowedMarkets).toContain(marketName);
    expect(openOrdersMap).toBeDefined();
    expect(openOrdersMap.size).toBe(0);
  }
});

it('getOrders (all)', async () => {
  await patches.get('serum/market/asksBidsForAllMarkets')();
  patches.get('solana/getKeyPair')();
  await patches.get('serum/market/loadOrdersForOwner')([]);
  patches.get('serum/serumMarketLoadFills')();

  request = {
    ...commonParameters,
    ownerAddress: config.solana.wallet.owner.publicKey,
  };
  response = await getOrders(solana, serum, request);

  expect(response.status).toBe(StatusCodes.OK);

  const ordersMapMap: Map<string, Map<string, GetOrderResponse>> = new Map<
    string,
    Map<string, GetOrderResponse>
  >(Object.entries(response.body));

  expect(ordersMapMap).toBeDefined();
  expect(ordersMapMap.size).toBe(numberOfAllowedMarkets);

  for (const [marketName, ordersMapObject] of ordersMapMap) {
    const ordersMap = new Map<string, GetOrderResponse>(
      Object.entries(ordersMapObject)
    );
    expect(allowedMarkets).toContain(marketName);
    expect(ordersMap).toBeDefined();
    expect(ordersMap.size).toBe(0);
  }
});

it('settleFunds ["SOL/USDT"]', async () => {
  await patches.get('serum/market/asksBidsForAllMarkets')();
  patches.get('solana/getKeyPair')();
  patches.get('serum/settleFundsForMarket')();
  patches.get('serum/serumMarketLoadFills')();
  await patches.get('serum/market/loadOrdersForOwner')([]);

  request = {
    ...commonParameters,
    marketName: marketName,
    ownerAddress: config.solana.wallet.owner.publicKey,
  };
  response = await settleFunds(solana, serum, request);

  expect(response.status).toBe(StatusCodes.OK);

  expect(response.body).toBeDefined();
});

it('settleFunds ["SOL/USDT", "SOL/USDC"]', async () => {
  await patches.get('serum/market/asksBidsForAllMarkets')();
  patches.get('solana/getKeyPair')();
  patches.get('serum/settleFundsForMarket')();
  patches.get('serum/serumMarketLoadFills')();
  await patches.get('serum/market/loadOrdersForOwner')([]);

  request = {
    ...commonParameters,
    marketNames: targetMarkets,
    ownerAddress: config.solana.wallet.owner.publicKey,
  };
  response = await settleFunds(solana, serum, request);

  expect(response.status).toBe(StatusCodes.OK);

  expect(response.body).toBeDefined();
});

it('settleFunds (all)', async () => {
  await patches.get('serum/market/asksBidsForAllMarkets')();
  patches.get('solana/getKeyPair')();
  patches.get('serum/settleFundsForMarket')();
  patches.get('serum/serumMarketLoadFills')();
  await patches.get('serum/market/loadOrdersForOwner')([]);

  request = {
    ...commonParameters,
    ownerAddress: config.solana.wallet.owner.publicKey,
  };
  response = await settleFunds(solana, serum, request);

  expect(response.status).toBe(StatusCodes.OK);

  expect(response.body).toBeDefined();
});
