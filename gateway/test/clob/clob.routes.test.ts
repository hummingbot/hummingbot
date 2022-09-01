import { MARKETS } from '@project-serum/serum';
import BN from 'bn.js';
import express from 'express';
import { Express } from 'express-serve-static-core';
import { StatusCodes } from 'http-status-codes';
import 'jest-extended';
import request from 'supertest';
import { Solana } from '../../src/chains/solana/solana';
import { ClobRoutes } from '../../src/clob/clob.routes';
import { Serum } from '../../src/connectors/serum/serum';
import { getNotNullOrThrowError } from '../../src/connectors/serum/serum.helpers';
import {
  CancelOrderResponse,
  GetMarketResponse,
  GetOpenOrderResponse,
  GetOrderBookResponse,
  GetOrderResponse,
  GetTickerResponse,
  OrderStatus,
  SettleFundsResponse,
} from '../../src/connectors/serum/serum.types';
import { ConfigManagerV2 } from '../../src/services/config-manager-v2';
import { default as config } from '../../test/chains/solana/serum/fixtures/config';
import {
  CreateOrderData,
  getNewCandidateOrdersTemplates,
  getOrderPairsFromCandidateOrders,
} from '../chains/solana/serum/fixtures/helpers';
import { unpatch } from '../services/patch';
import {
  default as patchesCreator,
  enablePatches,
} from '../../test/chains/solana/serum/fixtures/patches/patches';

enablePatches();

jest.setTimeout(5 * 60 * 1000);

let app: Express;
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

  app = express();
  app.use(express.json());

  app.use('/clob', ClobRoutes.router);

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

// All markets intersection with the whitelisted ones excepted the blacklisted ones.
// This is defined in the 'gateway/conf/serum.yml' file.
const allowedMarkets = Object.values(config.solana.markets).map(
  (market) => market.name
);
const numberOfAllowedMarkets = allowedMarkets.length;

const targetMarkets = allowedMarkets.slice(0, 2);

const targetMarket = targetMarkets[0];

// const orderIds = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9'];

const candidateOrders = getNewCandidateOrdersTemplates(10, 0);
const orderPairs: CreateOrderData[] =
  getOrderPairsFromCandidateOrders(candidateOrders);

describe(`/clob`, () => {
  describe(`GET /clob`, () => {
    it('Get the API status', async () => {
      await request(app)
        .get(`/clob`)
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
          expect(response.body.timestamp).toBeGreaterThanOrEqual(
            Date.now() - 60 * 60 * 1000
          );
        });
    });
  });
});

describe(`/clob/markets`, () => {
  describe(`GET /clob/markets`, () => {
    it('Get a specific market by its name', async () => {
      await request(app)
        .get(`/clob/markets`)
        .send({
          chain: config.serum.chain,
          network: config.serum.network,
          connector: config.serum.connector,
          name: targetMarket,
        })
        .set('Accept', 'application/json')
        .expect(StatusCodes.OK)
        .then((response) => {
          const market: GetMarketResponse = response.body as GetMarketResponse;
          expect(market).toBeDefined();

          const found: any = MARKETS.find(
            (market) => market.name === targetMarket && !market.deprecated
          );
          expect(found).toBeDefined();

          expect(market.name).toBe(found?.name);
          expect(market.address.toString()).toBe(found?.address.toString());
          expect(market.programId.toString()).toBe(found?.programId.toString());
          expect(market.deprecated).toBe(found?.deprecated);
          expect(market.minimumOrderSize).toBeGreaterThan(0);
          expect(market.tickSize).toBeGreaterThan(0);
          expect(market.minimumBaseIncrement).toBeDefined();
          expect(
            new BN(getNotNullOrThrowError(market.minimumBaseIncrement)).gt(
              new BN(0)
            )
          );
        });
    });

    it('Get a map of markets by their names', async () => {
      await request(app)
        .get(`/clob/markets`)
        .send({
          chain: config.serum.chain,
          network: config.serum.network,
          connector: config.serum.connector,
          names: targetMarkets,
        })
        .set('Accept', 'application/json')
        .expect(StatusCodes.OK)
        .expect('Content-Type', 'application/json; charset=utf-8')
        .then((response) => {
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
            expect(market.address.toString()).toBe(
              targetMarket?.address.toString()
            );
            expect(market.programId.toString()).toBe(
              targetMarket?.programId.toString()
            );
            expect(market.deprecated).toBe(targetMarket?.deprecated);
            expect(market.minimumOrderSize).toBeGreaterThan(0);
            expect(market.tickSize).toBeGreaterThan(0);
            expect(market.minimumBaseIncrement).toBeDefined();
            expect(
              new BN(getNotNullOrThrowError(market.minimumBaseIncrement)).gt(
                new BN(0)
              )
            );
          }
        });
    });

    it('Get a map with all markets', async () => {
      await request(app)
        .get(`/clob/markets`)
        .send({
          chain: config.serum.chain,
          network: config.serum.network,
          connector: config.serum.connector,
        })
        .set('Accept', 'application/json')
        .expect(StatusCodes.OK)
        .expect('Content-Type', 'application/json; charset=utf-8')
        .then((response) => {
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
            expect(market.address.toString()).toBe(
              targetMarket?.address.toString()
            );
            expect(market.programId.toString()).toBe(
              targetMarket?.programId.toString()
            );
            expect(market.deprecated).toBe(targetMarket?.deprecated);
            expect(market.minimumOrderSize).toBeGreaterThan(0);
            expect(market.tickSize).toBeGreaterThan(0);
            expect(market.minimumBaseIncrement).toBeDefined();
            expect(
              new BN(getNotNullOrThrowError(market.minimumBaseIncrement)).gt(
                new BN(0)
              )
            );
          }
        });
    });

    it('Fail when trying to get a market without informing its name', async () => {
      const marketName = '';

      await request(app)
        .get(`/clob/markets`)
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
        .get(`/clob/markets`)
        .send({
          chain: config.serum.chain,
          network: config.serum.network,
          connector: config.serum.connector,
          name: marketName,
        })
        .set('Accept', 'application/json')
        .expect(StatusCodes.NOT_FOUND)
        .then((response) => {
          expect(response.error).not.toBeFalsy();
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
        .get(`/clob/markets`)
        .send({
          chain: config.serum.chain,
          network: config.serum.network,
          connector: config.serum.connector,
          names: marketNames,
        })
        .set('Accept', 'application/json')
        .expect(StatusCodes.BAD_REQUEST)
        .then((response) => {
          expect(response.error).not.toBeFalsy();
          if (response.error) {
            expect(response.error.text.replace(/&quot;/gi, '"')).toContain(
              `No markets were informed. If you want to get all markets, please do not inform the parameter "names".`
            );
          }
        });
    });

    it('Fail when trying to get a map of markets but including a non existing market name', async () => {
      const marketNames = ['SOL/USDT', 'ABC/XYZ', 'SRM/SOL'];

      await request(app)
        .get(`/clob/markets`)
        .send({
          chain: config.serum.chain,
          network: config.serum.network,
          connector: config.serum.connector,
          names: marketNames,
        })
        .set('Accept', 'application/json')
        .expect(StatusCodes.NOT_FOUND)
        .then((response) => {
          expect(response.error).not.toBeFalsy();
          if (response.error) {
            expect(response.error.text.replace(/&quot;/gi, '"')).toContain(
              `Market "${marketNames[1]}" not found.`
            );
          }
        });
    });
  });
});

describe(`/clob/orderBooks`, () => {
  beforeEach(async () => {
    await Promise.all(
      allowedMarkets.flatMap(async (marketName) => {
        await patches.get('serum/market/loadAsks')(marketName);
        await patches.get('serum/market/loadBids')(marketName);
      })
    );
  });

  describe(`GET /clob/orderBooks`, () => {
    it('Get a specific order book by its market name', async () => {
      await request(app)
        .get(`/clob/orderBooks`)
        .send({
          chain: config.serum.chain,
          network: config.serum.network,
          connector: config.serum.connector,
          marketName: targetMarket,
        })
        .set('Accept', 'application/json')
        .expect(StatusCodes.OK)
        .then((response) => {
          const orderBook: GetOrderBookResponse =
            response.body as GetOrderBookResponse;
          expect(orderBook).toBeDefined();
          expect(orderBook.market).toBeDefined();

          const market = orderBook.market;

          const found: any = MARKETS.find(
            (market) => market.name === targetMarket && !market.deprecated
          );
          expect(found).toBeDefined();

          expect(market.name).toBe(found?.name);
          expect(market.address.toString()).toBe(found?.address.toString());
          expect(market.programId.toString()).toBe(found?.programId.toString());
          expect(market.deprecated).toBe(found?.deprecated);
          expect(market.minimumOrderSize).toBeGreaterThan(0);
          expect(market.tickSize).toBeGreaterThan(0);
          expect(market.minimumBaseIncrement).toBeDefined();
          expect(
            new BN(getNotNullOrThrowError(market.minimumBaseIncrement)).gt(
              new BN(0)
            )
          );

          expect(Object.entries(orderBook.bids).length).toBeGreaterThan(0);
          expect(Object.entries(orderBook.bids).length).toBeGreaterThan(0);
        });
    });

    it('Get a map of order books by their market names', async () => {
      await request(app)
        .get(`/clob/orderBooks`)
        .send({
          chain: config.serum.chain,
          network: config.serum.network,
          connector: config.serum.connector,
          marketNames: targetMarkets,
        })
        .set('Accept', 'application/json')
        .expect(StatusCodes.OK)
        .expect('Content-Type', 'application/json; charset=utf-8')
        .then((response) => {
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
            expect(market.address.toString()).toBe(
              targetMarket?.address.toString()
            );
            expect(market.programId.toString()).toBe(
              targetMarket?.programId.toString()
            );
            expect(market.deprecated).toBe(targetMarket?.deprecated);
            expect(market.minimumOrderSize).toBeGreaterThan(0);
            expect(market.tickSize).toBeGreaterThan(0);
            expect(market.minimumBaseIncrement).toBeDefined();
            expect(
              new BN(getNotNullOrThrowError(market.minimumBaseIncrement)).gt(
                new BN(0)
              )
            );
          }
        });
    });

    it('Get a map with all order books', async () => {
      await request(app)
        .get(`/clob/orderBooks`)
        .send({
          chain: config.serum.chain,
          network: config.serum.network,
          connector: config.serum.connector,
        })
        .set('Accept', 'application/json')
        .expect(StatusCodes.OK)
        .expect('Content-Type', 'application/json; charset=utf-8')
        .then((response) => {
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
            expect(market.address.toString()).toBe(
              targetMarket?.address.toString()
            );
            expect(market.programId.toString()).toBe(
              targetMarket?.programId.toString()
            );
            expect(market.deprecated).toBe(targetMarket?.deprecated);
            expect(market.minimumOrderSize).toBeGreaterThan(0);
            expect(market.tickSize).toBeGreaterThan(0);
            expect(market.minimumBaseIncrement).toBeDefined();
            expect(
              new BN(getNotNullOrThrowError(market.minimumBaseIncrement)).gt(
                new BN(0)
              )
            );
          }
        });
    });

    it('Fail when trying to get an order book without informing its market name', async () => {
      const marketName = '';

      await request(app)
        .get(`/clob/orderBooks`)
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
        .get(`/clob/orderBooks`)
        .send({
          chain: config.serum.chain,
          network: config.serum.network,
          connector: config.serum.connector,
          marketName: marketName,
        })
        .set('Accept', 'application/json')
        .expect(StatusCodes.NOT_FOUND)
        .then((response) => {
          expect(response.error).not.toBeFalsy();
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
        .get(`/clob/orderBooks`)
        .send({
          chain: config.serum.chain,
          network: config.serum.network,
          connector: config.serum.connector,
          marketNames: marketNames,
        })
        .set('Accept', 'application/json')
        .expect(StatusCodes.BAD_REQUEST)
        .then((response) => {
          expect(response.error).not.toBeFalsy();
          if (response.error) {
            expect(response.error.text.replace(/&quot;/gi, '"')).toContain(
              `No market names were informed. If you want to get all order books, please do not inform the parameter "marketNames".`
            );
          }
        });
    });

    it('Fail when trying to get a map of order books but including a non existing market name', async () => {
      const marketNames = ['SOL/USDT', 'ABC/XYZ', 'SRM/SOL'];

      await request(app)
        .get(`/clob/orderBooks`)
        .send({
          chain: config.serum.chain,
          network: config.serum.network,
          connector: config.serum.connector,
          marketNames: marketNames,
        })
        .set('Accept', 'application/json')
        .expect(StatusCodes.NOT_FOUND)
        .then((response) => {
          expect(response.error).not.toBeFalsy();
          if (response.error) {
            expect(response.error.text.replace(/&quot;/gi, '"')).toContain(
              `Market "${marketNames[1]}" not found.`
            );
          }
        });
    });
  });
});

describe(`/clob/tickers`, () => {
  beforeEach(async () => {
    patches.get('serum/getTicker')();
  });

  describe(`GET /clob/tickers`, () => {
    it('Get a specific ticker by its market name', async () => {
      await request(app)
        .get(`/clob/tickers`)
        .send({
          chain: config.serum.chain,
          network: config.serum.network,
          connector: config.serum.connector,
          marketName: targetMarket,
        })
        .set('Accept', 'application/json')
        .expect(StatusCodes.OK)
        .then((response) => {
          const ticker: GetTickerResponse = response.body as GetTickerResponse;
          expect(ticker).toBeDefined();

          const found: any = MARKETS.find(
            (market) => market.name === targetMarket && !market.deprecated
          );
          expect(found).toBeDefined();

          expect(ticker.price).toBeGreaterThan(0);
          expect(ticker.timestamp).toBeGreaterThan(0);
          expect(new Date(ticker.timestamp).getTime()).toBeLessThanOrEqual(
            Date.now()
          );
        });
    });

    it('Get a map of tickers by their market names', async () => {
      await request(app)
        .get(`/clob/tickers`)
        .send({
          chain: config.serum.chain,
          network: config.serum.network,
          connector: config.serum.connector,
          marketNames: targetMarkets,
        })
        .set('Accept', 'application/json')
        .expect(StatusCodes.OK)
        .expect('Content-Type', 'application/json; charset=utf-8')
        .then((response) => {
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
    });

    it('Get a map with all tickers', async () => {
      await request(app)
        .get(`/clob/tickers`)
        .send({
          chain: config.serum.chain,
          network: config.serum.network,
          connector: config.serum.connector,
        })
        .set('Accept', 'application/json')
        .expect(StatusCodes.OK)
        .expect('Content-Type', 'application/json; charset=utf-8')
        .then((response) => {
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
    });

    it('Fail when trying to get a ticker without informing its market name', async () => {
      const marketName = '';

      await request(app)
        .get(`/clob/tickers`)
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
        .get(`/clob/tickers`)
        .send({
          chain: config.serum.chain,
          network: config.serum.network,
          connector: config.serum.connector,
          marketName: 'ABC/XYZ',
        })
        .set('Accept', 'application/json')
        .expect(StatusCodes.NOT_FOUND)
        .then((response) => {
          expect(response.error).not.toBeFalsy();
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
        .get(`/clob/tickers`)
        .send({
          chain: config.serum.chain,
          network: config.serum.network,
          connector: config.serum.connector,
          marketNames: marketNames,
        })
        .set('Accept', 'application/json')
        .expect(StatusCodes.BAD_REQUEST)
        .then((response) => {
          expect(response.error).not.toBeFalsy();
          if (response.error) {
            expect(response.error.text.replace(/&quot;/gi, '"')).toContain(
              `No market names were informed. If you want to get all tickers, please do not inform the parameter "marketNames".`
            );
          }
        });
    });

    it('Fail when trying to get a map of tickers but including a non existing market name', async () => {
      const marketNames = ['SOL/USDT', 'ABC/XYZ', 'SRM/SOL'];

      await request(app)
        .get(`/clob/tickers`)
        .send({
          chain: config.serum.chain,
          network: config.serum.network,
          connector: config.serum.connector,
          marketNames: marketNames,
        })
        .set('Accept', 'application/json')
        .expect(StatusCodes.NOT_FOUND)
        .then((response) => {
          expect(response.error).not.toBeFalsy();
          if (response.error) {
            expect(response.error.text.replace(/&quot;/gi, '"')).toContain(
              `Market "${marketNames[1]}" not found.`
            );
          }
        });
    });
  });
});

describe(`/clob/orders`, () => {
  describe(`GET /clob/orders`, () => {
    it('Fail when trying to get one or more orders without informing any parameters', async () => {
      await request(app)
        .get(`/clob/orders`)
        .send({
          chain: config.serum.chain,
          network: config.serum.network,
          connector: config.serum.connector,
        })
        .set('Accept', 'application/json')
        .expect(StatusCodes.BAD_REQUEST)
        .then((response) => {
          expect(response.error).not.toBeFalsy();
          if (response.error) {
            expect(response.error.text.replace(/&quot;/gi, '"')).toContain(
              `The request is missing the key/property "ownerAddress"`
            );
          }
        });
    });

    describe('Single order', () => {
      let target: CreateOrderData;

      beforeAll(async () => {
        target = orderPairs[0];
      });

      it('Get a specific order by its id and owner address', async () => {
        await patches.get('serum/market/asksBidsForAllMarkets')();
        patches.get('solana/getKeyPair')();
        await patches.get('serum/market/loadOrdersForOwner')([target.request]);
        patches.get('serum/serumMarketLoadFills')();

        const orderId = target.response.id;
        const ownerAddress = target.response.ownerAddress;

        await request(app)
          .get(`/clob/orders`)
          .send({
            chain: config.serum.chain,
            network: config.serum.network,
            connector: config.serum.connector,
            order: {
              id: orderId,
              ownerAddress: ownerAddress,
            },
          })
          .set('Accept', 'application/json')
          .expect(StatusCodes.OK)
          .then((response) => {
            const order = response.body as GetOrderResponse;

            expect(order).toBeDefined();
          });
      });

      it('Get a specific order by its id, owner address and market name', async () => {
        await patches.get('serum/market/asksBidsForAllMarkets')();
        patches.get('solana/getKeyPair')();
        await patches.get('serum/market/loadOrdersForOwner')([target.request]);
        patches.get('serum/serumMarketLoadFills')();

        const orderId = target.response.id;
        const marketName = target.response.marketName;
        const ownerAddress = target.response.ownerAddress;

        await request(app)
          .get(`/clob/orders`)
          .send({
            chain: config.serum.chain,
            network: config.serum.network,
            connector: config.serum.connector,
            order: {
              id: orderId,
              marketName: marketName,
              ownerAddress: ownerAddress,
            },
          })
          .set('Accept', 'application/json')
          .expect(StatusCodes.OK)
          .then((response) => {
            const order = response.body as GetOrderResponse;

            expect(order).toBeDefined();
          });
      });

      it('Get a specific order by its exchange id and owner address', async () => {
        await patches.get('serum/market/asksBidsForAllMarkets')();
        patches.get('solana/getKeyPair')();
        await patches.get('serum/market/loadOrdersForOwner')([target.response]);
        patches.get('serum/serumMarketLoadFills')();

        const exchangeId = target.response.exchangeId;
        const ownerAddress = target.response.ownerAddress;

        await request(app)
          .get(`/clob/orders`)
          .send({
            chain: config.serum.chain,
            network: config.serum.network,
            connector: config.serum.connector,
            order: {
              exchangeId: exchangeId,
              ownerAddress: ownerAddress,
            },
          })
          .set('Accept', 'application/json')
          .expect(StatusCodes.OK)
          .then((response) => {
            const order = response.body as GetOrderResponse;

            expect(order).toBeDefined();
          });
      });

      it('Get a specific order by its exchange id, owner address and market name', async () => {
        await patches.get('serum/market/asksBidsForAllMarkets')();
        patches.get('solana/getKeyPair')();
        await patches.get('serum/market/loadOrdersForOwner')([target.response]);
        patches.get('serum/serumMarketLoadFills')();

        const exchangeId = target.response.exchangeId;
        const marketName = target.response.marketName;
        const ownerAddress = target.response.ownerAddress;

        await request(app)
          .get(`/clob/orders`)
          .send({
            chain: config.serum.chain,
            network: config.serum.network,
            connector: config.serum.connector,
            order: {
              exchangeId: exchangeId,
              marketName: marketName,
              ownerAddress: ownerAddress,
            },
          })
          .set('Accept', 'application/json')
          .expect(StatusCodes.OK)
          .then((response) => {
            const order = response.body as GetOrderResponse;

            expect(order).toBeDefined();
          });
      });

      it('Fail when trying to get an order without informing its owner address', async () => {
        const exchangeId = target.response.exchangeId;
        const marketName = target.response.marketName;

        await request(app)
          .get(`/clob/orders`)
          .send({
            chain: config.serum.chain,
            network: config.serum.network,
            connector: config.serum.connector,
            order: {
              exchangeId: exchangeId,
              marketName: marketName,
            },
          })
          .set('Accept', 'application/json')
          .expect(StatusCodes.BAD_REQUEST)
          .then((response) => {
            expect(response.error).not.toBeFalsy();
            if (response.error) {
              expect(response.error.text.replace(/&quot;/gi, '"')).toContain(
                `The request is missing the key/property "ownerAddress"`
              );
            }
          });
      });

      it('Fail when trying to get an order without informing its id and exchange id', async () => {
        const marketName = target.response.marketName;
        const ownerAddress = target.response.ownerAddress;

        await request(app)
          .get(`/clob/orders`)
          .send({
            chain: config.serum.chain,
            network: config.serum.network,
            connector: config.serum.connector,
            order: {
              marketName: marketName,
              ownerAddress: ownerAddress,
            },
          })
          .set('Accept', 'application/json')
          .expect(StatusCodes.BAD_REQUEST)
          .then((response) => {
            expect(response.error).not.toBeFalsy();
            if (response.error) {
              expect(response.error.text.replace(/&quot;/gi, '"')).toContain(
                `No client id or exchange id were informed`
              );
            }
          });
      });

      it('Fail when trying to get a non existing order', async () => {
        await patches.get('serum/market/asksBidsForAllMarkets')();
        patches.get('solana/getKeyPair')();
        await patches.get('serum/market/loadOrdersForOwner')([]);
        patches.get('serum/serumMarketLoadFills')();

        const orderId = target.response.id;
        const ownerAddress = target.response.ownerAddress;

        await request(app)
          .get(`/clob/orders`)
          .send({
            chain: config.serum.chain,
            network: config.serum.network,
            connector: config.serum.connector,
            order: {
              id: orderId,
              ownerAddress: ownerAddress,
            },
          })
          .set('Accept', 'application/json')
          .expect(StatusCodes.NOT_FOUND)
          .then((response) => {
            expect(response.error).not.toBeFalsy();
            if (response.error) {
              expect(response.error.text.replace(/&quot;/gi, '"')).toContain(
                `No order found with id / exchange id "${orderId}`
              );
            }
          });
      });
    });

    describe('Multiple orders', () => {
      let targets: CreateOrderData[];

      beforeAll(async () => {
        targets = orderPairs.slice(0, 3);
      });

      beforeEach(async () => {
        await patches.get('serum/market/asksBidsForAllMarkets')();
        patches.get('solana/getKeyPair')();
        await patches.get('serum/market/loadOrdersForOwner')(
          targets.map((order) => order.response)
        );
        patches.get('serum/serumMarketLoadFills')();
      });

      it('Get a map of orders by their ids and owner addresses', async () => {
        await request(app)
          .get(`/clob/orders`)
          .send({
            chain: config.serum.chain,
            network: config.serum.network,
            connector: config.serum.connector,
            orders: [
              {
                ids: targets.map((item) => item.request.id),
                ownerAddress: targets[0].request.ownerAddress,
              },
            ],
          })
          .set('Accept', 'application/json')
          .expect(StatusCodes.OK)
          .then((response) => {
            const orders = new Map<string, GetOrderResponse>(
              Object.entries(response.body)
            );

            for (const [orderId, order] of orders) {
              const found = targets.find(
                (item) => item.response.id === orderId
              );

              expect(found).not.toBeUndefined();
              expect(order.id).toEqual(orderId);
              expect(order.exchangeId).toBeDefined();
              expect(order.marketName).toEqual(found?.response.marketName);
              expect(order.ownerAddress).toEqual(found?.response.ownerAddress);
              expect(order.price).toEqual(found?.response.price);
              expect(order.amount).toEqual(found?.response.amount);
              expect(order.side).toEqual(found?.response.side);
              expect(order.status).toEqual(OrderStatus.OPEN);
              // expect(order.type).toEqual(found?.response.type);
              // expect(order.fee).toBeGreaterThanOrEqual(0);
            }
          });
      });

      it('Get a map of orders by their ids, owner addresses and market names', async () => {
        await request(app)
          .get(`/clob/orders`)
          .send({
            chain: config.serum.chain,
            network: config.serum.network,
            connector: config.serum.connector,
            orders: targets.map((item) => ({
              ids: [item.request.id],
              ownerAddress: item.request.ownerAddress,
              marketName: item.request.marketName,
            })),
          })
          .set('Accept', 'application/json')
          .expect(StatusCodes.OK)
          .then((response) => {
            const orders = new Map<string, GetOrderResponse>(
              Object.entries(response.body)
            );

            for (const [orderId, order] of orders) {
              const found = targets.find(
                (item) => item.response.id === orderId
              );

              expect(found).not.toBeUndefined();
              expect(order.id).toEqual(orderId);
              expect(order.exchangeId).toBeDefined();
              expect(order.marketName).toEqual(found?.response.marketName);
              expect(order.ownerAddress).toEqual(found?.response.ownerAddress);
              expect(order.price).toEqual(found?.response.price);
              expect(order.amount).toEqual(found?.response.amount);
              expect(order.side).toEqual(found?.response.side);
              expect(order.status).toEqual(OrderStatus.OPEN);
              // expect(order.type).toEqual(found?.response.type);
              // expect(order.fee).toBeGreaterThanOrEqual(0);
            }
          });
      });

      it('Get a map of orders by their exchange ids and owner addresses', async () => {
        await request(app)
          .get(`/clob/orders`)
          .send({
            chain: config.serum.chain,
            network: config.serum.network,
            connector: config.serum.connector,
            orders: [
              {
                exchangeIds: targets.map((item) => item.response.exchangeId),
                ownerAddress: targets[0].request.ownerAddress,
              },
            ],
          })
          .set('Accept', 'application/json')
          .expect(StatusCodes.OK)
          .then((response) => {
            const orders = new Map<string, GetOrderResponse>(
              Object.entries(response.body)
            );

            for (const [orderId, order] of orders) {
              const found = targets.find(
                (item) => item.response.id === orderId
              );

              expect(found).not.toBeUndefined();
              expect(order.id).toEqual(orderId);
              expect(order.exchangeId).toBeDefined();
              expect(order.marketName).toEqual(found?.response.marketName);
              expect(order.ownerAddress).toEqual(found?.response.ownerAddress);
              expect(order.price).toEqual(found?.response.price);
              expect(order.amount).toEqual(found?.response.amount);
              expect(order.side).toEqual(found?.response.side);
              expect(order.status).toEqual(OrderStatus.OPEN);
              // expect(order.type).toEqual(found?.response.type);
              // expect(order.fee).toBeGreaterThanOrEqual(0);
            }
          });
      });

      it('Get a map of orders by their exchange ids, owner addresses and market names', async () => {
        await request(app)
          .get(`/clob/orders`)
          .send({
            chain: config.serum.chain,
            network: config.serum.network,
            connector: config.serum.connector,
            orders: targets.map((item) => ({
              exchangeIds: [item.response.exchangeId],
              ownerAddress: item.request.ownerAddress,
              marketName: item.request.marketName,
            })),
          })
          .set('Accept', 'application/json')
          .expect(StatusCodes.OK)
          .then((response) => {
            const orders = new Map<string, GetOrderResponse>(
              Object.entries(response.body)
            );

            for (const [orderId, order] of orders) {
              const found = targets.find(
                (item) => item.response.id === orderId
              );

              expect(found).not.toBeUndefined();
              expect(order.id).toEqual(orderId);
              expect(order.exchangeId).toBeDefined();
              expect(order.marketName).toEqual(found?.response.marketName);
              expect(order.ownerAddress).toEqual(found?.response.ownerAddress);
              expect(order.price).toEqual(found?.response.price);
              expect(order.amount).toEqual(found?.response.amount);
              expect(order.side).toEqual(found?.response.side);
              expect(order.status).toEqual(OrderStatus.OPEN);
              // expect(order.type).toEqual(found?.response.type);
              // expect(order.fee).toBeGreaterThanOrEqual(0);
            }
          });
      });

      it('Fail when trying to get a map of orders without informing their owner addresses', async () => {
        await request(app)
          .get(`/clob/orders`)
          .send({
            chain: config.serum.chain,
            network: config.serum.network,
            connector: config.serum.connector,
            orders: targets.map((item) => ({
              exchangeIds: [item.response.exchangeId],
              marketName: item.request.marketName,
            })),
          })
          .set('Accept', 'application/json')
          .expect(StatusCodes.BAD_REQUEST)
          .then((response) => {
            expect(response.error).not.toBeFalsy();
            if (response.error) {
              expect(response.error.text.replace(/&quot;/gi, '"')).toContain(
                `The request is missing the key/property "ownerAddress"`
              );
            }
          });
      });

      // it('Fail when trying to get a map of orders without informing any orders within the orders parameter', async () => {
      //   console.log('');
      // });
      //
      // it('Fail when trying to get a map of orders without informing the id or exchange id of one of them', async () => {
      //   console.log('');
      // });
      //
      // it('Fail when trying to get a map of orders informing an id of a non existing one', async () => {
      //   console.log('');
      // });
    });
  });

  describe(`POST /serum/orders`, () => {
    describe('Single order', () => {
      it('Create an order and receive a response with the new information', async () => {
        patches.get('solana/getKeyPair')();

        patches.get('serum/serumMarketPlaceOrders')();
        await patches.get('serum/market/loadOrdersForOwner')([
          orderPairs[0].response,
        ]);

        const candidateOrder = orderPairs[0].request;

        await request(app)
          .post(`/clob/orders`)
          .send({
            chain: config.serum.chain,
            network: config.serum.network,
            connector: config.serum.connector,
            order: candidateOrder,
          })
          .set('Accept', 'application/json')
          .expect(StatusCodes.OK)
          .then((response) => {
            const order = response.body as GetOrderResponse;

            expect(order.id).toBe(orderPairs[0].response.id);
            // expect(order.exchangeId).toBeDefined();
            expect(order.marketName).toBe(candidateOrder.marketName);
            expect(order.ownerAddress).toBe(candidateOrder.ownerAddress);
            expect(order.price).toBe(candidateOrder.price);
            expect(order.amount).toBe(candidateOrder.amount);
            expect(order.side).toBe(candidateOrder.side);
            expect(order.status).toBe(OrderStatus.OPEN);
            // expect(order.type).toBe(candidateOrder.type);
          });
      });

      // it('Fail when trying to create an order without informing the order parameter', async () => {
      //   console.log('');
      // });
      //
      // it('Fail when trying to create an order without informing some of its required parameters', async () => {
      //   console.log('');
      // });
    });

    // describe('Multiple orders', () => {
    //   it('Create multiple orders and receive a response as a map with the new information', async () => {
    //     console.log('');
    //   });
    //
    //   it('Fail when trying to create multiple orders without informing the orders parameter', async () => {
    //     console.log('');
    //   });
    //
    //   it('Fail when trying to create multiple orders without informing some of their required parameters', async () => {
    //     console.log('');
    //   });
    // });
  });

  describe(`DELETE /clob/orders`, () => {
    describe('Single order', () => {
      let target: CreateOrderData;

      beforeAll(async () => {
        target = orderPairs[0];
      });

      // it('Cancel a specific order by its id and owner address', async () => {
      //   console.log('');
      // });

      it('Cancel a specific order by its id, owner address and market name', async () => {
        await patches.get('serum/market/asksBidsForAllMarkets')();
        patches.get('solana/getKeyPair')();
        patches.get('serum/serumMarketCancelOrdersAndSettleFunds')();
        await patches.get('serum/market/loadOrdersForOwner')([target.request]);

        const orderId = target.response.id;
        const ownerAddress = target.response.ownerAddress;
        const marketName = target.response.marketName;

        await request(app)
          .delete(`/clob/orders`)
          .send({
            chain: config.serum.chain,
            network: config.serum.network,
            connector: config.serum.connector,
            order: {
              id: orderId,
              ownerAddress: ownerAddress,
              marketName: marketName,
            },
          })
          .set('Accept', 'application/json')
          .expect(StatusCodes.OK)
          .then((response) => {
            const order = response.body as CancelOrderResponse;

            expect(order).toBeDefined();
          });
      });
      //
      // it('Cancel a specific order by its exchange id and owner address', async () => {
      //   console.log('');
      // });
      //
      // it('Cancel a specific order by its exchange id, owner address and market name', async () => {
      //   console.log('');
      // });
      //
      // it('Fail when trying to cancel an order without informing the order parameter', async () => {
      //   console.log('');
      // });
      //
      // it('Fail when trying to cancel an order without informing its owner address', async () => {
      //   console.log('');
      // });
      //
      // it('Fail when trying to cancel an order without informing its id and exchange id', async () => {
      //   console.log('');
      // });
      //
      // it('Fail when trying to cancel a non existing order', async () => {
      //   console.log('');
      // });
    });

    // describe('Multiple orders', () => {
    //   it('Cancel multiple orders by their ids and owner addresses', async () => {
    //     console.log('');
    //   });
    //
    //   it('Cancel multiple orders by their ids, owner addresses, and market names', async () => {
    //     console.log('');
    //   });
    //
    //   it('Cancel multiple orders by their exchange ids and owner addresses', async () => {
    //     console.log('');
    //   });
    //
    //   it('Cancel multiple orders by their exchange ids, owner addresses, and market names', async () => {
    //     console.log('');
    //   });
    //
    //   it('Fail when trying to cancel multiple orders without informing the orders parameter', async () => {
    //     console.log('');
    //   });
    //
    //   it('Fail when trying to cancel multiple orders without informing any orders within the orders parameter', async () => {
    //     console.log('');
    //   });
    //
    //   it('Fail when trying to cancel multiple orders without informing some of their owner addresses', async () => {
    //     console.log('');
    //   });
    //
    //   it('Fail when trying to cancel multiple orders without informing some of their ids and exchange ids', async () => {
    //     console.log('');
    //   });
    //
    //   it('Fail when trying to cancel multiple orders informing an id of a non existing one', async () => {
    //     console.log('');
    //   });
    // });
  });
});

describe(`/clob/orders/open`, () => {
  describe(`GET /clob/orders/open`, () => {
    describe('Single order', () => {
      let target: CreateOrderData;

      beforeAll(async () => {
        target = orderPairs[0];
      });

      // it('Get a specific open order by its id and owner address', async () => {
      //   console.log('');
      // });

      it('Get a specific open order by its id, owner address and market name', async () => {
        await patches.get('serum/market/asksBidsForAllMarkets')();
        patches.get('solana/getKeyPair')();
        patches.get('serum/serumMarketCancelOrdersAndSettleFunds')();
        await patches.get('serum/market/loadOrdersForOwner')([target.request]);

        const orderId = target.response.id;
        const ownerAddress = target.response.ownerAddress;
        const marketName = target.response.marketName;

        await request(app)
          .get(`/clob/orders/open`)
          .send({
            chain: config.serum.chain,
            network: config.serum.network,
            connector: config.serum.connector,
            order: {
              id: orderId,
              ownerAddress: ownerAddress,
              marketName: marketName,
            },
          })
          .set('Accept', 'application/json')
          .expect(StatusCodes.OK)
          .then((response) => {
            const order = response.body as GetOpenOrderResponse;

            expect(order).toBeDefined();
          });
      });

      // it('Get a specific open order by its exchange id and owner address', async () => {
      //   console.log('');
      // });
      //
      // it('Get a specific open order by its exchange id, owner address and market name', async () => {
      //   console.log('');
      // });
      //
      // it('Fail when trying to get an open order without informing the order parameter', async () => {
      //   console.log('');
      // });
      //
      // it('Fail when trying to get an open order without informing its owner address', async () => {
      //   console.log('');
      // });
      //
      // it('Fail when trying to get an open order without informing its id and exchange id', async () => {
      //   console.log('');
      // });
      //
      // it('Fail when trying to get a non existing open order', async () => {
      //   console.log('');
      // });
    });

    // describe('Multiple orders', () => {
    //   it('Get a map of open orders by their ids and owner addresses', async () => {
    //     console.log('');
    //   });
    //
    //   it('Get a map of open orders by their ids, owner addresses and market names', async () => {
    //     console.log('');
    //   });
    //
    //   it('Get a map of open orders by their exchange ids and owner addresses', async () => {
    //     console.log('');
    //   });
    //
    //   it('Get a map of open orders by their exchange ids, owner addresses and market names', async () => {
    //     console.log('');
    //   });
    //
    //   it('Get a map of with all open orders by for a specific owner address', async () => {
    //     console.log('');
    //   });
    //
    //   it('Get a map of with all open orders by for a specific owner address and market name', async () => {
    //     console.log('');
    //   });
    //
    //   it('Fail when trying to get a map of open orders without informing the orders parameter', async () => {
    //     console.log('');
    //   });
    //
    //   it('Fail when trying to get a map of open orders without informing any orders filter within the orders parameter', async () => {
    //     console.log('');
    //   });
    //
    //   it('Fail when trying to get a map of open orders without informing some of their owner addresses', async () => {
    //     console.log('');
    //   });
    //
    //   it('Fail when trying to get a map of multiple open orders informing an id of a non existing one', async () => {
    //     console.log('');
    //   });
    // });
  });
});

describe(`/clob/orders/filled`, () => {
  describe(`GET /clob/orders/filled`, () => {
    describe('Single order', () => {
      let target: CreateOrderData;

      beforeAll(async () => {
        target = orderPairs[0];
      });

      //       it('Get a specific filled order by its id and owner address', async () => {
      //         console.log('');
      //       });

      it('Get a specific filled order by its id, owner address and market name', async () => {
        await patches.get('serum/market/asksBidsForAllMarkets')();
        patches.get('solana/getKeyPair')();
        patches.get('serum/serumMarketCancelOrdersAndSettleFunds')();
        await patches.get('serum/market/loadOrdersForOwner')([target.request]);
        patches.get('serum/serumMarketLoadFills')([target.request]);

        const orderId = target.response.id;
        const ownerAddress = target.response.ownerAddress;
        const marketName = target.response.marketName;

        await request(app)
          .get(`/clob/orders/filled`)
          .send({
            chain: config.serum.chain,
            network: config.serum.network,
            connector: config.serum.connector,
            order: {
              id: orderId,
              ownerAddress: ownerAddress,
              marketName: marketName,
            },
          })
          .set('Accept', 'application/json')
          .expect(StatusCodes.NOT_FOUND)
          .then((response) => {
            expect(response.error).not.toBeFalsy();
            if (response.error) {
              expect(response.error.text.replace(/&quot;/gi, '"')).toContain(
                `found with id / exchange id "${target.request.id}`
              );
            }
          });
      });

      //       it('Get a specific filled order by its exchange id and owner address', async () => {
      //         console.log('');
      //       });
      //
      //       it('Get a specific filled order by its exchange id, owner address and market name', async () => {
      //         console.log('');
      //       });
      //
      //       it('Fail when trying to get a filled order without informing the order parameter', async () => {
      //         console.log('');
      //       });
      //
      //       it('Fail when trying to get a filled order without informing its owner address', async () => {
      //         console.log('');
      //       });
      //
      //       it('Fail when trying to get a filled order without informing its id and exchange id', async () => {
      //         console.log('');
      //       });
    });
    //
    //     describe('Multiple orders', () => {
    //       it('Get a map of filled orders by their ids and owner addresses', async () => {
    //         console.log('');
    //       });
    //
    //       it('Get a map of filled orders by their ids, owner addresses and market names', async () => {
    //         console.log('');
    //       });
    //
    //       it('Get a map of filled orders by their exchange ids and owner addresses', async () => {
    //         console.log('');
    //       });
    //
    //       it('Get a map of filled orders by their exchange ids, owner addresses and market names', async () => {
    //         console.log('');
    //       });
    //
    //       it('Get a map of with all filled orders by for a specific owner address', async () => {
    //         console.log('');
    //       });
    //
    //       it('Get a map of with all filled orders by for a specific owner address and market name', async () => {
    //         console.log('');
    //       });
    //
    //       it('Fail when trying to get a map of filled orders without informing the orders parameter', async () => {
    //         console.log('');
    //       });
    //
    //       it('Fail when trying to get a map of filled orders without informing any orders filter within the orders parameter', async () => {
    //         console.log('');
    //       });
    //
    //       it('Fail when trying to get a map of filled orders without informing some of their owner addresses', async () => {
    //         console.log('');
    //       });
    //     });
  });
});

describe(`/clob/settleFunds`, () => {
  describe(`GET /clob/settleFunds`, () => {
    let target: CreateOrderData;

    beforeAll(async () => {
      target = orderPairs[0];
    });

    it('Settle funds for as specific market by its market name and owner address', async () => {
      await patches.get('serum/market/asksBidsForAllMarkets')();
      patches.get('solana/getKeyPair')();
      patches.get('serum/settleFundsForMarket')();
      patches.get('serum/serumMarketLoadFills')();
      await patches.get('serum/market/loadOrdersForOwner')([]);

      const ownerAddress = target.response.ownerAddress;
      const marketName = target.response.marketName;

      await request(app)
        .post(`/clob/settleFunds`)
        .send({
          chain: config.serum.chain,
          network: config.serum.network,
          connector: config.serum.connector,
          ownerAddress: ownerAddress,
          marketName: marketName,
        })
        .set('Accept', 'application/json')
        .expect(StatusCodes.OK)
        .then((response) => {
          const order = response.body as SettleFundsResponse;

          expect(order).toBeDefined();
        });
    });
  });
});
