import {MARKETS} from '@project-serum/serum';
import express from 'express';
import {Express} from 'express-serve-static-core';
import {StatusCodes} from 'http-status-codes';
import 'jest-extended';
import request from 'supertest';
import {Solana} from '../../../../src/chains/solana/solana';
import {ClobRoutes} from '../../../../src/clob/clob.routes';
import {Serum} from '../../../../src/connectors/serum/serum';
import {convertToGetOrderResponse} from "../../../../src/connectors/serum/serum.convertors";
import {SerumRoutes} from '../../../../src/connectors/serum/serum.routes';
import {
  CreateOrdersRequest,
  GetMarketResponse,
  GetOrderBookResponse,
  GetOrderResponse,
  GetTickerResponse,
  OrderSide,
  OrderStatus,
  Ticker
} from '../../../../src/connectors/serum/serum.types';
import {unpatch} from '../../../services/patch';
import {getNewOrderTemplate} from "./fixtures/dummy";
import {default as config} from './fixtures/serumConfig';

let app: Express;
let serum: Serum;

jest.setTimeout(1000000);

beforeAll(async () => {
  app = express();
  app.use(express.json());

  await Solana.getInstance(config.solana.network);

  serum = await Serum.getInstance(config.serum.chain, config.serum.network);

  app.use(`/clob`, ClobRoutes.router);
  app.use('/serum', SerumRoutes.router);
});

afterEach(() => {
  unpatch();
});

const routePrefix = '/clob';

describe(`${routePrefix}`, () => {
  describe(`GET ${routePrefix}`, () => {
    it('Get the API status', async () => {
      await request(app)
        .get(`${routePrefix}`)
        .send({
          chain: config.serum.chain,
          network: config.serum.network,
          connector: config.serum.connector,
        })
        .set('Accept', 'application/json')
        .expect(StatusCodes.OK)
        .then((response) => {
          expect(response.body.chain).toBe(config.serum.chain);
          expect(response.body.network).toBe(config.serum.network);
          expect(response.body.connector).toBe(config.serum.connector);
          expect(response.body.connection).toBe(true);
          expect(response.body.timestamp).toBeLessThanOrEqual(Date.now());
        });
    });
  });
});

describe(`${routePrefix}/markets`, () => {
  describe(`GET ${routePrefix}/markets`, () => {
    it('Get a specific market by its name', async () => {
      const marketName = 'BTC/USDT';

      await request(app)
        .get(`${routePrefix}/markets`)
        .send({
          chain: config.serum.chain,
          network: config.serum.network,
          connector: config.serum.connector,
          name: marketName,
        })
        .set('Accept', 'application/json')
        .expect(StatusCodes.OK)
        .then((response) => {
          const targetMarket = MARKETS.find(
            (market) => market.name === marketName
          )!;

          const market: GetMarketResponse = response.body;

          expect(market.name).toBe(targetMarket.name);
          expect(market.address).toBe(targetMarket.address.toString());
          expect(market.programId).toBe(targetMarket.programId.toString());
          expect(market.deprecated).toBe(targetMarket.deprecated);
          expect(market.minimumOrderSize).toBe(-1);
          expect(market.tickSize).toBe(-1);
          expect(market.minimumBaseIncrement).toBe(-1);
          expect(market.fees).toBe(-1);
        });
    });

    it('Get a map of markets by their names', async () => {
      const marketNames = ['BTC/USDT', 'ETH/USDT'];

      await request(app)
        .get(`${routePrefix}/markets`)
        .send({
          chain: config.serum.chain,
          network: config.serum.network,
          connector: config.serum.connector,
          names: marketNames,
        })
        .set('Accept', 'application/json')
        .expect(StatusCodes.OK)
        .expect('Content-Type', 'application/json; charset=utf-8')
        .then((response) => {
          const marketsMap = new Map<string, GetMarketResponse>(Object.entries(response.body));

          expect(marketsMap.size).toBe(marketNames.length);
          for (const [marketName, market] of marketsMap) {
            expect(marketNames.includes(marketName)).toBe(true);
            expect(market.name).toBe(marketName);
          }
        });
    });

    it('Get a map with all markets', async () => {
      await request(app)
        .get(`${routePrefix}/markets`)
        .send({
          chain: config.serum.chain,
          network: config.serum.network,
          connector: config.serum.connector,
        })
        .set('Accept', 'application/json')
        .expect(StatusCodes.OK)
        .expect('Content-Type', 'application/json; charset=utf-8')
        .then((response) => {
          const marketsMap = new Map<string, GetMarketResponse>(Object.entries(response.body));

          expect(marketsMap.size).toBe(MARKETS.length);
          for (const [marketName, market] of marketsMap) {
            expect(market.name).toBe(marketName);
          }
        });
    });

    it('Fail when trying to get a market without informing its name', async () => {
      const marketName = '';

      await request(app)
        .get(`${routePrefix}/markets`)
        .send({
          chain: config.serum.chain,
          network: config.serum.network,
          connector: config.serum.connector,
          name: marketName,
        })
        .set('Accept', 'application/json')
        .expect(StatusCodes.BAD_REQUEST)
        .expect('Content-Type', 'text/html; charset=utf-8')
        .then((response) => {
          expect(response.error).not.toBeFalsy();
          if (response.error) {
            expect(response.error.text.replace(/&quot;/gi, '"')).toContain(
              `No market was informed. If you want to get a market, please inform the parameter "name".`
            );
          }
        });
    });

    it('Fail when trying to get a non existing market', async () => {
      const marketName = 'ABC/XYZ';

      await request(app)
        .get(`${routePrefix}/markets`)
        .send({
          chain: config.serum.chain,
          network: config.serum.network,
          connector: config.serum.connector,
          name: marketName,
        })
        .set('Accept', 'application/json')
        .expect(StatusCodes.NOT_FOUND)
        .then((response) => {
          expect(response.error).not.toBeFalsy()
          if (response.error) {
            expect(response.error.text.replace(/&quot;/gi, '"')).toContain(
              `Market "${marketName}" not found.`
            );
          }
        });
    });

    it('Fail when trying to get a map of markets but without informing any of their names', async () => {
      const marketNames: string[] = [];

      await request(app)
        .get(`${routePrefix}/markets`)
        .send({
          chain: config.serum.chain,
          network: config.serum.network,
          connector: config.serum.connector,
          names: marketNames,
        })
        .set('Accept', 'application/json')
        .expect(StatusCodes.BAD_REQUEST)
        .then((response) => {
          expect(response.error).not.toBeFalsy()
          if (response.error) {
            expect(response.error.text.replace(/&quot;/gi, '"')).toContain(
              `No markets were informed. If you want to get all markets, please do not inform the parameter "names".`
            );
          }
        });
    });

    it('Fail when trying to get a map of markets but including a non existing market name', async () => {
      const marketNames = ['BTC/USDT', 'ABC/XYZ', 'ETH/USDT'];

      await request(app)
        .get(`${routePrefix}/markets`)
        .send({
          chain: config.serum.chain,
          network: config.serum.network,
          connector: config.serum.connector,
          names: marketNames,
        })
        .set('Accept', 'application/json')
        .expect(StatusCodes.NOT_FOUND)
        .then((response) => {
          expect(response.error).not.toBeFalsy()
          if (response.error) {
            expect(response.error.text.replace(/&quot;/gi, '"')).toContain(
              `Market "${marketNames[1]}" not found.`
            );
          }
        });
    });
  });
});

describe(`${routePrefix}/orderBooks`, () => {
  describe(`GET ${routePrefix}/orderBooks`, () => {
    it('Get a specific order book by its market name', async () => {
      const marketName = 'BTC/USDT';

      await request(app)
        .get(`${routePrefix}/orderBooks`)
        .send({
          chain: config.serum.chain,
          network: config.serum.network,
          connector: config.serum.connector,
          marketName: marketName,
        })
        .set('Accept', 'application/json')
        .expect(StatusCodes.OK)
        .then((response) => {
          const targetMarket = MARKETS.find(
            (market) => market.name === marketName
          )!;

          const orderBook: GetOrderBookResponse = response.body;

          expect(orderBook.market.name).toBe(targetMarket.name);
          expect(orderBook.market.address).toBe(targetMarket.address.toString());
          expect(orderBook.market.programId).toBe(targetMarket.programId.toString());
          expect(orderBook.market.deprecated).toBe(targetMarket.deprecated);
          expect(orderBook.market.minimumOrderSize).toBe(-1);
          expect(orderBook.market.tickSize).toBe(-1);
          expect(orderBook.market.minimumBaseIncrement).toBe(-1);
          expect(orderBook.market.fees).toBe(-1);
          expect(orderBook.bids).toBe(-1);
          expect(orderBook.asks).toBe(-1);
        });
    });

    it('Get a map of order books by their market names', async () => {
      const marketNames = ['BTC/USDT', 'ETH/USDT'];

      await request(app)
        .get(`${routePrefix}/orderBooks`)
        .send({
          chain: config.serum.chain,
          network: config.serum.network,
          connector: config.serum.connector,
          marketNames: marketNames,
        })
        .set('Accept', 'application/json')
        .expect(StatusCodes.OK)
        .expect('Content-Type', 'application/json; charset=utf-8')
        .then((response) => {
          const orderBooksMap = new Map<string, GetOrderBookResponse>(Object.entries(response.body));

          expect(orderBooksMap.size).toBe(marketNames.length);
          for (const [marketName, orderBook] of orderBooksMap) {
            expect(marketNames.includes(marketName)).toBe(true);
            expect(orderBook.market.name).toBe(marketName);
          }
        });
    });

    it('Get a map with all order books', async () => {
      await request(app)
        .get(`${routePrefix}/orderBooks`)
        .send({
          chain: config.serum.chain,
          network: config.serum.network,
          connector: config.serum.connector,
        })
        .set('Accept', 'application/json')
        .expect(StatusCodes.OK)
        .expect('Content-Type', 'application/json; charset=utf-8')
        .then((response) => {
          const marketsMap = new Map<string, GetOrderBookResponse>(Object.entries(response.body));

          expect(marketsMap.size).toBe(MARKETS.length);
          for (const [marketName, orderBook] of marketsMap) {
            expect(orderBook.market.name).toBe(marketName);
          }
        });
    });

    it('Fail when trying to get an order book without informing its market name', async () => {
      const marketName = '';

      await request(app)
        .get(`${routePrefix}/orderBooks`)
        .send({
          chain: config.serum.chain,
          network: config.serum.network,
          connector: config.serum.connector,
          marketName: marketName,
        })
        .set('Accept', 'application/json')
        .expect(StatusCodes.BAD_REQUEST)
        .expect('Content-Type', 'text/html; charset=utf-8')
        .then((response) => {
          expect(response.error).not.toBeFalsy();
          if (response.error) {
            expect(response.error.text.replace(/&quot;/gi, '"')).toContain(
              `No market name was informed. If you want to get an order book, please inform the parameter "marketName".`
            );
          }
        });
    });

    it('Fail when trying to get a non existing order book', async () => {
      const marketName = 'ABC/XYZ';

      await request(app)
        .get(`${routePrefix}/orderBooks`)
        .send({
          chain: config.serum.chain,
          network: config.serum.network,
          connector: config.serum.connector,
          marketName: marketName,
        })
        .set('Accept', 'application/json')
        .expect(StatusCodes.NOT_FOUND)
        .then((response) => {
          expect(response.error).not.toBeFalsy()
          if (response.error) {
            expect(response.error.text.replace(/&quot;/gi, '"')).toContain(
              `Market "${marketName}" not found.`
            );
          }
        });
    });

    it('Fail when trying to get a map of order books but without informing any of their market names', async () => {
      const marketNames: string[] = [];

      await request(app)
        .get(`${routePrefix}/orderBooks`)
        .send({
          chain: config.serum.chain,
          network: config.serum.network,
          connector: config.serum.connector,
          marketNames: marketNames,
        })
        .set('Accept', 'application/json')
        .expect(StatusCodes.BAD_REQUEST)
        .then((response) => {
          expect(response.error).not.toBeFalsy()
          if (response.error) {
            expect(response.error.text.replace(/&quot;/gi, '"')).toContain(
              `No market names were informed. If you want to get all order books, please do not inform the parameter "marketNames".`
            );
          }
        });
    });

    it('Fail when trying to get a map of order books but including a non existing market name', async () => {
      const marketNames = ['BTC/USDT', 'ABC/XYZ', 'ETH/USDT'];

      await request(app)
        .get(`${routePrefix}/orderBooks`)
        .send({
          chain: config.serum.chain,
          network: config.serum.network,
          connector: config.serum.connector,
          marketNames: marketNames,
        })
        .set('Accept', 'application/json')
        .expect(StatusCodes.NOT_FOUND)
        .then((response) => {
          expect(response.error).not.toBeFalsy()
          if (response.error) {
            expect(response.error.text.replace(/&quot;/gi, '"')).toContain(
              `Market "${marketNames[1]}" not found.`
            );
          }
        });
    });
  });
});

describe(`${routePrefix}/tickers`, () => {
  describe(`GET ${routePrefix}/tickers`, () => {
    it('Get a specific ticker by its market name', async () => {
      const marketName = 'BTC/USDT';

      await request(app)
        .get(`${routePrefix}/tickers`)
        .send({
          chain: config.serum.chain,
          network: config.serum.network,
          connector: config.serum.connector,
          marketName: marketName,
        })
        .set('Accept', 'application/json')
        .expect(StatusCodes.OK)
        .then((response) => {
          const ticker = response.body as Ticker;

          expect(ticker.price).toBeGreaterThan(0);
          expect(ticker.amount).toBeGreaterThan(0);
          expect(ticker.side).toBe(OrderSide.BUY || OrderSide.SELL);
          expect((new Date(ticker.timestamp))).toBeValidDate()
        });
    });

    it('Get a map of tickers by their market names', async () => {
      const marketNames = ['BTC/USDT', 'ETH/USDT'];

      await request(app)
        .get(`${routePrefix}/tickers`)
        .send({
          chain: config.serum.chain,
          network: config.serum.network,
          connector: config.serum.connector,
          marketNames: marketNames,
        })
        .set('Accept', 'application/json')
        .expect(StatusCodes.OK)
        .expect('Content-Type', 'application/json; charset=utf-8')
        .then((response) => {
          const tickersMap = new Map<string, GetTickerResponse>(Object.entries(response.body));

          expect(tickersMap.size).toBe(marketNames.length);
          for (const [marketName, ticker] of tickersMap) {
            expect(marketNames.includes(marketName)).toBe(true);
            expect(ticker.price).toBeGreaterThan(0);
            expect(ticker.amount).toBeGreaterThan(0);
            expect(ticker.side).toBe(OrderSide.BUY || OrderSide.SELL);
            expect((new Date(ticker.timestamp))).toBeValidDate()
          }
        });
    });

    it('Get a map with all tickers', async () => {
      await request(app)
        .get(`${routePrefix}/tickers`)
        .send({
          chain: config.serum.chain,
          network: config.serum.network,
          connector: config.serum.connector,
        })
        .set('Accept', 'application/json')
        .expect(StatusCodes.OK)
        .expect('Content-Type', 'application/json; charset=utf-8')
        .then((response) => {
          const tickersMap = new Map<string, GetTickerResponse>(Object.entries(response.body));

          expect(tickersMap.size).toBe(MARKETS.length);
          for (const [_marketName, ticker] of tickersMap) {
            expect(ticker.price).toBeGreaterThan(0);
          }
        });
    });

    it('Fail when trying to get a ticker without informing its market name', async () => {
      const marketName = '';

      await request(app)
        .get(`${routePrefix}/tickers`)
        .send({
          chain: config.serum.chain,
          network: config.serum.network,
          connector: config.serum.connector,
          marketName: marketName,
        })
        .set('Accept', 'application/json')
        .expect(StatusCodes.BAD_REQUEST)
        .expect('Content-Type', 'text/html; charset=utf-8')
        .then((response) => {
          expect(response.error).not.toBeFalsy();
          if (response.error) {
            expect(response.error.text.replace(/&quot;/gi, '"')).toContain(
              `No market name was informed. If you want to get a ticker, please inform the parameter "marketName".`
            );
          }
        });
    });

    it('Fail when trying to get a non existing ticker', async () => {
      const marketName = 'ABC/XYZ';

      await request(app)
        .get(`${routePrefix}/tickers`)
        .send({
          chain: config.serum.chain,
          network: config.serum.network,
          connector: config.serum.connector,
          marketName: marketName,
        })
        .set('Accept', 'application/json')
        .expect(StatusCodes.NOT_FOUND)
        .then((response) => {
          expect(response.error).not.toBeFalsy()
          if (response.error) {
            expect(response.error.text.replace(/&quot;/gi, '"')).toContain(
              `Market "${marketName}" not found.`
            );
          }
        });
    });

    it('Fail when trying to get a map of tickers but without informing any of their market names', async () => {
      const marketNames: string[] = [];

      await request(app)
        .get(`${routePrefix}/tickers`)
        .send({
          chain: config.serum.chain,
          network: config.serum.network,
          connector: config.serum.connector,
          marketNames: marketNames,
        })
        .set('Accept', 'application/json')
        .expect(StatusCodes.BAD_REQUEST)
        .then((response) => {
          expect(response.error).not.toBeFalsy()
          if (response.error) {
            expect(response.error.text.replace(/&quot;/gi, '"')).toContain(
              `No market names were informed. If you want to get all tickers, please do not inform the parameter "marketNames".`
            );
          }
        });
    });

    it('Fail when trying to get a map of tickers but including a non existing market name', async () => {
      const marketNames = ['BTC/USDT', 'ABC/XYZ', 'ETH/USDT'];

      await request(app)
        .get(`${routePrefix}/tickers`)
        .send({
          chain: config.serum.chain,
          network: config.serum.network,
          connector: config.serum.connector,
          marketNames: marketNames,
        })
        .set('Accept', 'application/json')
        .expect(StatusCodes.NOT_FOUND)
        .then((response) => {
          expect(response.error).not.toBeFalsy()
          if (response.error) {
            expect(response.error.text.replace(/&quot;/gi, '"')).toContain(
              `Market "${marketNames[1]}" not found.`
            );
          }
        });
    });
  });
});

describe(`${routePrefix}/orders`, () => {
  describe(`GET ${routePrefix}/orders`, () => {
    it('Fail when trying to get one or more orders without informing any parameters', async () => {
      await request(app)
        .get(`${routePrefix}/orders`)
        .send({
          chain: config.serum.chain,
          network: config.serum.network,
          connector: config.serum.connector,
        })
        .set('Accept', 'application/json')
        .expect(StatusCodes.BAD_REQUEST)
        .then((response) => {
          expect(response.error).not.toBeFalsy()
          if (response.error) {
            expect(response.error.text.replace(/&quot;/gi, '"')).toContain(
              `No order(s) was/were informed.`
            );
          }
        });
    });

    describe('Single order', () => {
      let target: OrderPair;

      beforeAll(async () =>{
        target = await createNewOrder();
      });

      it('Get a specific order by its id and owner address', async () => {
        const orderId = target.order.id;
        const ownerAddress = target.order.ownerAddress;

        await request(app)
        .get(`${routePrefix}/orders`)
        .send({
          chain: config.serum.chain,
          network: config.serum.network,
          connector: config.serum.connector,
          order: {
            id: orderId,
            ownerAddress: ownerAddress,
          }
        })
        .set('Accept', 'application/json')
        .expect(StatusCodes.OK)
        .then((response) => {
          const order = response.body as GetOrderResponse;

          expect(order).toBeDefined();
        });
      });

      it('Get a specific order by its id, owner address and market name', async () => {
        const orderId = target.order.id;
        const marketName = target.order.marketName;
        const ownerAddress = target.order.ownerAddress;

        await request(app)
        .get(`${routePrefix}/orders`)
        .send({
          chain: config.serum.chain,
          network: config.serum.network,
          connector: config.serum.connector,
          order: {
            id: orderId,
            marketName: marketName,
            ownerAddress: ownerAddress,
          }
        })
        .set('Accept', 'application/json')
        .expect(StatusCodes.OK)
        .then((response) => {
          const order = response.body as GetOrderResponse;

          expect(order).toBeDefined();
        });
      });

      it('Get a specific order by its exchange id and owner address', async () => {
        const exchangeId = target.order.exchangeId;
        const ownerAddress = target.order.ownerAddress;

        await request(app)
        .get(`${routePrefix}/orders`)
        .send({
          chain: config.serum.chain,
          network: config.serum.network,
          connector: config.serum.connector,
          order: {
            id: exchangeId,
            ownerAddress: ownerAddress,
          }
        })
        .set('Accept', 'application/json')
        .expect(StatusCodes.OK)
        .then((response) => {
          const order = response.body as GetOrderResponse;

          expect(order).toBeDefined();
        });
      });

      it('Get a specific order by its exchange id, owner address and market name', async () => {
        const exchangeId = target.order.exchangeId;
        const marketName = target.order.marketName;
        const ownerAddress = target.order.ownerAddress;

        await request(app)
        .get(`${routePrefix}/orders`)
        .send({
          chain: config.serum.chain,
          network: config.serum.network,
          connector: config.serum.connector,
          order: {
            id: exchangeId,
            marketName: marketName,
            ownerAddress: ownerAddress,
          }
        })
        .set('Accept', 'application/json')
        .expect(StatusCodes.OK)
        .then((response) => {
          const order = response.body as GetOrderResponse;

          expect(order).toBeDefined();
        });
      });

      it('Fail when trying to get an order without informing its owner address', async () => {
        const exchangeId = target.order.exchangeId;
        const marketName = target.order.marketName;

        await request(app)
        .get(`${routePrefix}/orders`)
        .send({
          chain: config.serum.chain,
          network: config.serum.network,
          connector: config.serum.connector,
          order: {
            exchangeId: exchangeId,
            marketName: marketName,
          }
        })
        .set('Accept', 'application/json')
        .expect(StatusCodes.BAD_REQUEST)
        .then((response) => {
          expect(response.error).not.toBeFalsy()
          if (response.error) {
            expect(response.error.text.replace(/&quot;/gi, '"')).toContain(
              `No owner address provided for order "${target.order.id} / ${target.order.exchangeId}".`
            );
          }
        });
      });

      it('Fail when trying to get an order without informing its id and exchange id', async () => {
        const marketName = target.order.marketName;
        const ownerAddress = target.order.ownerAddress;

        await request(app)
        .get(`${routePrefix}/orders`)
        .send({
          chain: config.serum.chain,
          network: config.serum.network,
          connector: config.serum.connector,
          order: {
            marketName: marketName,
            ownerAddress: ownerAddress,
          }
        })
        .set('Accept', 'application/json')
        .expect(StatusCodes.BAD_REQUEST)
        .then((response) => {
          expect(response.error).not.toBeFalsy()
          if (response.error) {
            expect(response.error.text.replace(/&quot;/gi, '"')).toContain(
              `No clientId or exchangeId provided.`
            );
          }
        });
      });

      it('Fail when trying to get a non existing order', async () => {
        const orderId = target.order.id;
        const ownerAddress = target.order.ownerAddress;

        await request(app)
        .get(`${routePrefix}/orders`)
        .send({
          chain: config.serum.chain,
          network: config.serum.network,
          connector: config.serum.connector,
          order: {
            id: orderId,
            ownerAddress: ownerAddress,
          }
        })
        .set('Accept', 'application/json')
        .expect(StatusCodes.BAD_REQUEST)
        .then((response) => {
          expect(response.error).not.toBeFalsy()
          if (response.error) {
            expect(response.error.text.replace(/&quot;/gi, '"')).toContain(
              `Order "${orderId}" not found.`
            );
          }
        });
      });
    });

    describe('Multiple orders', () => {
      let targets: OrderPair[];

      beforeAll(async () => {
        targets = await createNewOrders(3);
      });

      it('Get a map of orders by their ids and owner addresses', async () => {
        await request(app)
        .get(`${routePrefix}/orders`)
        .send({
          chain: config.serum.chain,
          network: config.serum.network,
          connector: config.serum.connector,
          orders: targets.map(item => ({
            id: item.order.id,
            ownerAddress: item.order.ownerAddress,
          }))
        })
        .set('Accept', 'application/json')
        .expect(StatusCodes.OK)
        .then((response) => {
          const orders = new Map<string, GetOrderResponse>(Object.entries(response.body));

          for (const [orderId, order] of orders) {
            const found = targets.find(item => item.order.id === orderId);

            expect(found).not.toBeUndefined();
            expect(order.id).toEqual(orderId);
            expect(order.exchangeId).toBeGreaterThan(0);
            expect(order.marketName).toEqual(found?.order.marketName);
            expect(order.ownerAddress).toEqual(found?.order.ownerAddress);
            expect(order.price).toEqual(found?.order.price);
            expect(order.amount).toEqual(found?.order.amount);
            expect(order.side).toEqual(found?.order.side);
            expect(order.status).toEqual(OrderStatus.OPEN);
            expect(order.type).toEqual(found?.order.type);
            expect(order.fee).toBeGreaterThanOrEqual(0);
          }
        });
      });

      it('Get a map of orders by their ids, owner addresses and market names', async () => {
        await request(app)
        .get(`${routePrefix}/orders`)
        .send({
          chain: config.serum.chain,
          network: config.serum.network,
          connector: config.serum.connector,
          orders: targets.map(item => ({
            id: item.order.id,
            ownerAddress: item.order.ownerAddress,
            marketName: item.order.marketName,
          }))
        })
        .set('Accept', 'application/json')
        .expect(StatusCodes.OK)
        .then((response) => {
          const orders = new Map<string, GetOrderResponse>(Object.entries(response.body));

          for (const [orderId, order] of orders) {
            const found = targets.find(item => item.order.id === orderId);

            expect(found).not.toBeUndefined();
            expect(order.id).toEqual(orderId);
            expect(order.exchangeId).toBeGreaterThan(0);
            expect(order.marketName).toEqual(found?.order.marketName);
            expect(order.ownerAddress).toEqual(found?.order.ownerAddress);
            expect(order.price).toEqual(found?.order.price);
            expect(order.amount).toEqual(found?.order.amount);
            expect(order.side).toEqual(found?.order.side);
            expect(order.status).toEqual(OrderStatus.OPEN);
            expect(order.type).toEqual(found?.order.type);
            expect(order.fee).toBeGreaterThanOrEqual(0);
          }
        });
      });

      it('Get a map of orders by their exchange ids and owner addresses', async () => {
        await request(app)
        .get(`${routePrefix}/orders`)
        .send({
          chain: config.serum.chain,
          network: config.serum.network,
          connector: config.serum.connector,
          orders: targets.map(item => ({
            exchangeId: item.order.exchangeId,
            ownerAddress: item.order.ownerAddress,
          }))
        })
        .set('Accept', 'application/json')
        .expect(StatusCodes.OK)
        .then((response) => {
          const orders = new Map<string, GetOrderResponse>(Object.entries(response.body));

          for (const [orderId, order] of orders) {
            const found = targets.find(item => item.order.id === orderId);

            expect(found).not.toBeUndefined();
            expect(order.id).toEqual(orderId);
            expect(order.exchangeId).toBeGreaterThan(0);
            expect(order.marketName).toEqual(found?.order.marketName);
            expect(order.ownerAddress).toEqual(found?.order.ownerAddress);
            expect(order.price).toEqual(found?.order.price);
            expect(order.amount).toEqual(found?.order.amount);
            expect(order.side).toEqual(found?.order.side);
            expect(order.status).toEqual(OrderStatus.OPEN);
            expect(order.type).toEqual(found?.order.type);
            expect(order.fee).toBeGreaterThanOrEqual(0);
          }
        });
      });

      it('Get a map of orders by their exchange ids, owner addresses and market names', async () => {
        await request(app)
        .get(`${routePrefix}/orders`)
        .send({
          chain: config.serum.chain,
          network: config.serum.network,
          connector: config.serum.connector,
          orders: targets.map(item => ({
            exchangeId: item.order.exchangeId,
            ownerAddress: item.order.ownerAddress,
            marketName: item.order.marketName,
          }))
        })
        .set('Accept', 'application/json')
        .expect(StatusCodes.OK)
        .then((response) => {
          const orders = new Map<string, GetOrderResponse>(Object.entries(response.body));

          for (const [orderId, order] of orders) {
            const found = targets.find(item => item.order.id === orderId);

            expect(found).not.toBeUndefined();
            expect(order.id).toEqual(orderId);
            expect(order.exchangeId).toBeGreaterThan(0);
            expect(order.marketName).toEqual(found?.order.marketName);
            expect(order.ownerAddress).toEqual(found?.order.ownerAddress);
            expect(order.price).toEqual(found?.order.price);
            expect(order.amount).toEqual(found?.order.amount);
            expect(order.side).toEqual(found?.order.side);
            expect(order.status).toEqual(OrderStatus.OPEN);
            expect(order.type).toEqual(found?.order.type);
            expect(order.fee).toBeGreaterThanOrEqual(0);
          }
        });
      });

      it('Fail when trying to get a map of orders without informing their owner addresses', async () => {
        await request(app)
        .get(`${routePrefix}/orders`)
        .send({
          chain: config.serum.chain,
          network: config.serum.network,
          connector: config.serum.connector,
          orders: targets.map(item => ({
            exchangeId: item.order.exchangeId,
            marketName: item.order.marketName,
          }))
        })
        .set('Accept', 'application/json')
        .expect(StatusCodes.BAD_REQUEST)
        .then((response) => {
          expect(response.error).not.toBeFalsy()
          if (response.error) {
            expect(response.error.text.replace(/&quot;/gi, '"')).toContain(
              `No owner address provided for order "${targets[0].order.id} / ${targets[0].order.exchangeId}".`
            );
          }
        });
      });

      it('Fail when trying to get a map of orders without informing any orders within the orders parameter', async () => {
        console.log('');
      });

      it('Fail when trying to get a map of orders without informing the id or exchange id of one of them', async () => {
        console.log('');
      });

      it('Fail when trying to get a map of orders informing an id of a non existing one', async () => {
        console.log('');
      });
    });
  });

  describe(`POST ${routePrefix}/orders`, () => {
    describe('Single order', () => {
      it('Create an order and receive a response with the new information', async () => {
        const candidateOrder = {
          id: '',
          marketName: 'BTC/USDT',
          ownerAddress: '0x0000000000000000000000000000000000000000',
          price: 0.00000000000000001,
          amount: 0.0000000000000001,
          side: 'BUY',
          type: 'LIMIT'
        } as CreateOrdersRequest;

        await request(app)
          .post(`${routePrefix}/orders`)
          .send({
            chain: config.serum.chain,
            network: config.serum.network,
            connector: config.serum.connector,
            order: candidateOrder
          })
          .set('Accept', 'application/json')
          .expect(StatusCodes.OK)
          .then((response) => {
            const order = response.body as GetOrderResponse;

            expect(order.id).toBeGreaterThan(0);
            expect(order.exchangeId).toBeGreaterThan(0);
            expect(order.marketName).toBe(candidateOrder.marketName);
            expect(order.ownerAddress).toBe(candidateOrder.ownerAddress)
            expect(order.price).toBe(candidateOrder.price);
            expect(order.amount).toBe(candidateOrder.amount);
            expect(order.side).toBe(candidateOrder.side);
            expect(order.status).toBe(OrderStatus.OPEN);
            expect(order.type).toBe(candidateOrder.type);
          });
      });

      it('Fail when trying to create an order without informing the order parameter', async () => {
        console.log('');
      });

      it('Fail when trying to create an order without informing some of its required parameters', async () => {
        console.log('');
      });
    });

    describe('Multiple orders', () => {
      it('Create multiple orders and receive a response as a map with the new information', async () => {
        console.log('');
      });

      it('Fail when trying to create multiple orders without informing the orders parameter', async () => {
        console.log('');
      });

      it('Fail when trying to create multiple orders without informing some of their required parameters', async () => {
        console.log('');
      });
    });
  });

  describe(`DELETE ${routePrefix}/orders`, () => {
    describe('Single order', () => {
      it('Cancel a specific order by its id and owner address', async () => {
        console.log('');
      });

      it('Cancel a specific order by its id, owner address and market name', async () => {
        console.log('');
      });

      it('Cancel a specific order by its exchange id and owner address', async () => {
        console.log('');
      });

      it('Cancel a specific order by its exchange id, owner address and market name', async () => {
        console.log('');
      });

      it('Fail when trying to cancel an order without informing the order parameter', async () => {
        console.log('');
      });

      it('Fail when trying to cancel an order without informing its owner address', async () => {
        console.log('');
      });

      it('Fail when trying to cancel an order without informing its id and exchange id', async () => {
        console.log('');
      });

      it('Fail when trying to cancel a non existing order', async () => {
        console.log('');
      });
    });

    describe('Multiple orders', () => {
      it('Cancel multiple orders by their ids and owner addresses', async () => {
        console.log('');
      });

      it('Cancel multiple orders by their ids, owner addresses, and market names', async () => {
        console.log('');
      });

      it('Cancel multiple orders by their exchange ids and owner addresses', async () => {
        console.log('');
      });

      it('Cancel multiple orders by their exchange ids, owner addresses, and market names', async () => {
        console.log('');
      });

      it('Fail when trying to cancel multiple orders without informing the orders parameter', async () => {
        console.log('');
      });

      it('Fail when trying to cancel multiple orders without informing any orders within the orders parameter', async () => {
        console.log('');
      });

      it('Fail when trying to cancel multiple orders without informing some of their owner addresses', async () => {
        console.log('');
      });

      it('Fail when trying to cancel multiple orders without informing some of their ids and exchange ids', async () => {
        console.log('');
      });

      it('Fail when trying to cancel multiple orders informing an id of a non existing one', async () => {
        console.log('');
      });
    });
  });
});

describe(`${routePrefix}/openOrders`, () => {
  describe(`GET ${routePrefix}/openOrders`, () => {
    describe('Single order', () => {
      it('Get a specific open order by its id and owner address', async () => {
        console.log('');
      });

      it('Get a specific open order by its id, owner address and market name', async () => {
        console.log('');
      });

      it('Get a specific open order by its exchange id and owner address', async () => {
        console.log('');
      });

      it('Get a specific open order by its exchange id, owner address and market name', async () => {
        console.log('');
      });

      it('Fail when trying to get an open order without informing the order parameter', async () => {
        console.log('');
      });

      it('Fail when trying to get an open order without informing its owner address', async () => {
        console.log('');
      });

      it('Fail when trying to get an open order without informing its id and exchange id', async () => {
        console.log('');
      });

      it('Fail when trying to get a non existing open order', async () => {
        console.log('');
      });
    });

    describe('Multiple orders', () => {
      it('Get a map of open orders by their ids and owner addresses', async () => {
        console.log('');
      });

      it('Get a map of open orders by their ids, owner addresses and market names', async () => {
        console.log('');
      });

      it('Get a map of open orders by their exchange ids and owner addresses', async () => {
        console.log('');
      });

      it('Get a map of open orders by their exchange ids, owner addresses and market names', async () => {
        console.log('');
      });

      it('Get a map of with all open orders by for a specific owner address', async () => {
        console.log('');
      });

      it('Get a map of with all open orders by for a specific owner address and market name', async () => {
        console.log('');
      });

      it('Fail when trying to get a map of open orders without informing the orders parameter', async () => {
        console.log('');
      });

      it('Fail when trying to get a map of open orders without informing any orders filter within the orders parameter', async () => {
        console.log('');
      });

      it('Fail when trying to get a map of open orders without informing some of their owner addresses', async () => {
        console.log('');
      });

      it('Fail when trying to get a map of multiple open orders informing an id of a non existing one', async () => {
        console.log('');
      });
    });
  });

  describe(`DELETE ${routePrefix}/openOrders`, () => {
    describe('Single open order', () => {
      it('Cancel a specific open order by its id and owner address', async () => {
        console.log('');
      });

      it('Cancel a specific open order by its id, owner address and market name', async () => {
        console.log('');
      });

      it('Cancel a specific open order by its exchange id and owner address', async () => {
        console.log('');
      });

      it('Cancel a specific open order by its exchange id, owner address and market name', async () => {
        console.log('');
      });

      it('Fail when trying to cancel an open order without informing the order parameter', async () => {
        console.log('');
      });

      it('Fail when trying to cancel an open order without informing its owner address', async () => {
        console.log('');
      });

      it('Fail when trying to cancel an open order without informing its id and exchange id', async () => {
        console.log('');
      });

      it('Fail when trying to cancel a non existing open order', async () => {
        console.log('');
      });
    });

    describe('Multiple orders', () => {
      it('Cancel multiple open orders by their ids and owner addresses', async () => {
        console.log('');
      });

      it('Cancel multiple open orders by their ids, owner addresses, and market names', async () => {
        console.log('');
      });

      it('Cancel multiple open orders by their exchange ids and owner addresses', async () => {
        console.log('');
      });

      it('Cancel multiple open orders by their exchange ids, owner addresses, and market names', async () => {
        console.log('');
      });

      it('Cancel all open orders for an owner address', async () => {
        console.log('');
      });

      it('Cancel all open orders for an owner address and a market name', async () => {
        console.log('');
      });

      it('Fail when trying to cancel multiple open orders without informing the orders parameter', async () => {
        console.log('');
      });

      it('Fail when trying to cancel multiple open orders without informing any orders within the orders parameter', async () => {
        console.log('');
      });

      it('Fail when trying to cancel multiple open orders without informing some of their owner addresses', async () => {
        console.log('');
      });

      it('Fail when trying to cancel multiple open orders informing an id of a non existing one', async () => {
        console.log('');
      });
    });
  });
});

describe(`${routePrefix}/filledOrders`, () => {
  describe(`GET ${routePrefix}/filledOrders`, () => {
    describe('Single order', () => {
      it('Get a specific filled order by its id and owner address', async () => {
        console.log('');
      });

      it('Get a specific filled order by its id, owner address and market name', async () => {
        console.log('');
      });

      it('Get a specific filled order by its exchange id and owner address', async () => {
        console.log('');
      });

      it('Get a specific filled order by its exchange id, owner address and market name', async () => {
        console.log('');
      });

      it('Fail when trying to get a filled order without informing the order parameter', async () => {
        console.log('');
      });

      it('Fail when trying to get a filled order without informing its owner address', async () => {
        console.log('');
      });

      it('Fail when trying to get a filled order without informing its id and exchange id', async () => {
        console.log('');
      });
    });

    describe('Multiple orders', () => {
      it('Get a map of filled orders by their ids and owner addresses', async () => {
        console.log('');
      });

      it('Get a map of filled orders by their ids, owner addresses and market names', async () => {
        console.log('');
      });

      it('Get a map of filled orders by their exchange ids and owner addresses', async () => {
        console.log('');
      });

      it('Get a map of filled orders by their exchange ids, owner addresses and market names', async () => {
        console.log('');
      });

      it('Get a map of with all filled orders by for a specific owner address', async () => {
        console.log('');
      });

      it('Get a map of with all filled orders by for a specific owner address and market name', async () => {
        console.log('');
      });

      it('Fail when trying to get a map of filled orders without informing the orders parameter', async () => {
        console.log('');
      });

      it('Fail when trying to get a map of filled orders without informing any orders filter within the orders parameter', async () => {
        console.log('');
      });

      it('Fail when trying to get a map of filled orders without informing some of their owner addresses', async () => {
        console.log('');
      });
    });
  });
});

interface OrderPair { candidate: CreateOrdersRequest; order: GetOrderResponse };

const createNewOrder = async (): Promise<OrderPair> => {
  const candidate = getNewOrderTemplate();

  return {
    candidate: candidate,
    order: convertToGetOrderResponse(await serum.createOrder(candidate)),
  };
};

const createNewOrders = async(quantity: number) => {
  const orders = [];

  for (let i = 0; i < quantity; i++) {
    orders.push(await createNewOrder());
  }

  return orders;
};
