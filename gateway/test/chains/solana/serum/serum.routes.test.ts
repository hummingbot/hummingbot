import express from 'express';
import {Express} from 'express-serve-static-core';
import request from 'supertest';
import {MARKETS} from '@project-serum/serum';
import {Serum} from '../../../../src/connectors/serum/serum';
import {ClobRoutes} from '../../../../src/clob/clob.routes';
import {unpatch} from '../../../services/patch';
import {Solana} from '../../../../src/chains/solana/solana';
import {default as config} from './fixtures/getSerumConfig';
import {StatusCodes} from 'http-status-codes';
import {Market, OrderBook, Ticker,} from '../../../../src/connectors/serum/serum.types';
import {SerumRoutes} from '../../../../src/connectors/serum/serum.routes';

let app: Express;

jest.setTimeout(1000000);

beforeAll(async () => {
  app = express();
  app.use(express.json());

  await Solana.getInstance(config.solana.network).init();

  await Serum.getInstance(config.serum.chain, config.serum.network);

  app.use('/clob', ClobRoutes.router);
  app.use('/serum', SerumRoutes.router);
});

afterEach(() => {
  unpatch();
});

describe('/clob', () => {
  describe('GET /clob', () => {
    it('Get the API status', async () => {
      await request(app)
        .get('/clob')
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

describe('/clob/markets', () => {
  describe('GET /clob/markets', () => {
    it('Get an specific market by its name', async () => {
      const marketName = 'BTC/USDT';

      await request(app)
        .get('/clob/markets')
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

          const market: Market = response.body;

          expect(market.name).toBe(targetMarket.name);
          expect(market.address).toBe(targetMarket.address.toString());
          expect(market.programId).toBe(targetMarket.programId.toString());
          expect(market.deprecated).toBe(targetMarket.deprecated);
          // TODO fill the rest of the fields!!!
        });
    });

    it('Get a map of markets by their names', async () => {
      const marketNames = ['BTC/USDT', 'ETH/USDT'];

      await request(app)
        .get('/clob/markets')
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
          const marketsMap: Map<string, Market> = response.body;

          expect(marketsMap.size).toBe(marketNames.length);
          for (const [marketName, market] of marketsMap) {
            expect(marketNames.includes(marketName)).toBe(true);
            expect(market.name).toBe(marketName);
          }
        });
    });

    it('Get a map with all markets', async () => {
      await request(app)
        .get('/clob/markets')
        .send({
          chain: config.serum.chain,
          network: config.serum.network,
          connector: config.serum.connector,
        })
        .set('Accept', 'application/json')
        .expect(StatusCodes.OK)
        .expect('Content-Type', 'application/json; charset=utf-8')
        .then((response) => {
          const marketsMap: Map<string, Market> = response.body;

          expect(marketsMap.size).toBe(MARKETS.length);
          for (const [marketName, market] of marketsMap) {
            expect(market.name).toBe(marketName);
          }
        });
    });

    it('Fail when trying to get a market without informing its name', async () => {
      const marketName = '';

      await request(app)
        .get('/clob/markets')
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
            expect(response.error.text).toContain(
              `No market was informed. If you want to get a market, please inform the parameter "name".`
            );
          }
        });
    });

    it('Fail when trying to get an non existing market', async () => {
      const marketName = 'ABC/XYZ';

      await request(app)
        .get('/clob/markets')
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
            expect(response.error.text).toContain(
              `Market ${marketName} not found.`
            );
          }
        });
    });

    it('Fail when trying to get a map of markets but without informing any of their names', async () => {
      const marketNames: string[] = [];

      await request(app)
        .get('/clob/markets')
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
              expect(response.error.text).toContain(
                `No markets were informed. If you want to get all markets, please do not inform the parameter "names".`
              );
            }
          });
    });

    it('Fail when trying to get a map of markets but with a non existing one', async () => {
      const marketNames = ['BTC/USDT', 'ABC/XYZ', 'ETH/USDT'];

      await request(app)
        .get('/clob/markets')
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
              expect(response.error.text).toContain(
                `Market ${marketNames[1]} not found`
              );
            }
          });
    });
  });
});

describe('/clob/orderBooks', () => {
  describe('GET /clob/orderBooks', () => {
    it('Get an specific order book by its market name', async () => {
      await request(app)
        .get('/clob/orderBooks')
        .send({
          chain: config.serum.chain,
          network: config.serum.network,
          connector: config.serum.connector,
          marketName: 'BTC/USDT',
        })
        .set('Accept', 'application/json')
        .expect(StatusCodes.OK)
        .then((response) => {
          const orderBook: OrderBook = response.body;

          console.log(orderBook);

          fail('Not implemented');
        });
    });

    it('Get a map of order books by their market names', async () => {
      await request(app)
        .get('/clob/orderBooks')
        .send({
          chain: config.serum.chain,
          network: config.serum.network,
          connector: config.serum.connector,
          names: ['BTC/USDT', 'ETH/USDT'],
        })
        .set('Accept', 'application/json')
        .expect(StatusCodes.OK)
        .then((response) => {
          const map: Map<string, OrderBook> = response.body;

          console.log(map);

          fail('Not implemented');
        });
    });

    it('Get a map with all order books', async () => {
      await request(app)
        .get('/clob/orderBooks')
        .send({
          chain: config.serum.chain,
          network: config.serum.network,
          connector: config.serum.connector,
        })
        .set('Accept', 'application/json')
        .expect(StatusCodes.OK)
        .then((response) => {
          const map: Map<string, OrderBook> = response.body;

          console.log(map);

          fail('Not implemented');
        });
    });
  });
});

describe('/clob/tickers', () => {
  describe('GET /clob/tickers', () => {
    it('Get an specific ticker by its market name', async () => {
      await request(app)
        .get('/clob/tickers')
        .send({
          chain: config.serum.chain,
          network: config.serum.network,
          connector: config.serum.connector,
          marketName: 'BTC/USDT',
        })
        .set('Accept', 'application/json')
        .expect(StatusCodes.OK)
        .then((response) => {
          const ticker: Ticker = response.body;

          console.log(ticker);

          fail('Not implemented');
        });
    });

    it('Get a map of tickers by their market names', async () => {
      await request(app)
        .get('/clob/tickers')
        .send({
          chain: config.serum.chain,
          network: config.serum.network,
          connector: config.serum.connector,
          names: ['BTC/USDT', 'ETH/USDT'],
        })
        .set('Accept', 'application/json')
        .expect(StatusCodes.OK)
        .then((response) => {
          const map: Map<string, Ticker> = response.body;

          console.log(map);

          fail('Not implemented');
        });
    });

    it('Get a map with all tickers', async () => {
      await request(app)
        .get('/clob/tickers')
        .send({
          chain: config.serum.chain,
          network: config.serum.network,
          connector: config.serum.connector,
        })
        .set('Accept', 'application/json')
        .expect(StatusCodes.OK)
        .then((response) => {
          const map: Map<string, Ticker> = response.body;

          console.log(map);

          fail('Not implemented');
        });
    });
  });
});

describe('/clob/orders', () => {
  describe('GET /clob/orders', () => {
    it('Get an specific order by its id', async () => {
      console.log('');
    });
    it('Get an specific order by its exchange id', async () => {
      console.log('');
    });
  });

  describe('POST /clob/orders', () => {
    it('', async () => {
      console.log('');
    });
  });

  describe('DELETE /clob/orders', () => {
    it('', async () => {
      console.log('');
    });
  });
});

describe('/clob/openOrders', () => {
  describe('GET /clob/openOrders', () => {
    it('', async () => {
      console.log('');
    });
  });

  describe('DELETE /clob/openOrders', () => {
    it('', async () => {
      console.log('');
    });
  });
});

describe('/clob/filledOrders', () => {
  describe('GET /clob/filledOrders', () => {
    it('', async () => {
      console.log('');
    });
  });

  describe('DELETE /clob/filledOrders', () => {
    it('', async () => {
      console.log('');
    });
  });
});
