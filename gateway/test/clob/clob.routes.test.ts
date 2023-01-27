import request from 'supertest';
import { patch, unpatch } from '../services/patch';
import { gatewayApp } from '../../src/app';
import { Injective } from '../../src/chains/injective/injective';
import { InjectiveCLOB } from '../../src/connectors/injective/injective';

let inj: Injective;
let injCLOB: InjectiveCLOB;

const TX_HASH =
  'CC6BF44223B4BD05396F83D55A0ABC0F16CE80836C0E34B08F4558CF72944299'; // noqa: mock
const MARKET = 'INJ-USDT';

const MARKETS = [
  {
    marketId:
      '0xa508cb32923323679f29a032c70342c147c17d0145625922b0ef22e955c844c0', // noqa: mock
    marketStatus: 'active',
    ticker: 'INJ/USDT',
    baseDenom: 'inj',
    quoteDenom: 'peggy0xdAC17F958D2ee523a2206206994597C13D831ec7',
    quoteToken: {
      name: 'Tether',
      address: '0xdAC17F958D2ee523a2206206994597C13D831ec7',
      symbol: 'USDT',
      logo: 'https://static.alchemyapi.io/images/assets/825.png',
      decimals: 6,
      updatedAt: 1669849325905,
      coinGeckoId: '',
    },
    baseToken: {
      name: 'Injective Protocol',
      address: '0xe28b3B32B6c345A34Ff64674606124Dd5Aceca30',
      symbol: 'INJ',
      logo: 'https://static.alchemyapi.io/images/assets/7226.png',
      decimals: 18,
      updatedAt: 1659191789475,
      coinGeckoId: '',
    },
    makerFeeRate: '-0.0001',
    takerFeeRate: '0.001',
    serviceProviderFee: '0.4',
    minPriceTickSize: 1e-15,
    minQuantityTickSize: 1000000000000000,
  },
];

const ORDER_BOOK = {
  sells: [
    ['12', '1'],
    ['11', '0.3'],
  ],
  buys: [
    ['10', '1'],
    ['9', '0.3'],
  ],
};

const ORDERS = {
  orderHistory: [
    {
      orderHash:
        '0xf6f81a37796bd06a797484467302e4d6f72832409545e2e01feb86dd8b22e4b2', // noqa: mock
      marketId:
        '0xa508cb32923323679f29a032c70342c147c17d0145625922b0ef22e955c844c0', // noqa: mock
      active: false,
      subaccountId:
        '0x261362dbc1d83705ab03e99792355689a4589b8e000000000000000000000000', // noqa: mock
      executionType: 'limit',
      orderType: 'sell',
      price: '0.000000000002',
      triggerPrice: '0',
      quantity: '2000000000000000000',
      filledQuantity: '0',
      state: 'canceled',
      createdAt: 1669850499821,
      updatedAt: 1669853807685,
      direction: 'sell',
    },
    {
      orderHash:
        '0x751a0fcfa52562d0cfe842d21673ebcb654a3774739654800388b1037bc267bc', // noqa: mock
      marketId:
        '0xa508cb32923323679f29a032c70342c147c17d0145625922b0ef22e955c844c0', // noqa: mock
      active: true,
      subaccountId:
        '0x261362dbc1d83705ab03e99792355689a4589b8e000000000000000000000000', // noqa: mock
      executionType: 'limit',
      orderType: 'sell',
      price: '0.000000000002',
      triggerPrice: '0',
      quantity: '2000000000000000000',
      filledQuantity: '0',
      state: 'booked',
      createdAt: 1669850223538,
      updatedAt: 1669850223538,
      direction: 'sell',
    },
  ],
};

const GAS_PRICES = {
  gasPrice: '500000000',
  gasPriceToken: 'Token',
  gasLimit: '1000',
  gasCost: '100',
};

const INVALID_REQUEST = {
  chain: 'unknown',
  network: 'mainnet',
};

beforeAll(async () => {
  inj = Injective.getInstance('mainnet');
  patchCurrentBlockNumber();
  inj.init();
  injCLOB = InjectiveCLOB.getInstance('injective', 'mainnet');
  patchMarkets();
  await injCLOB.init();
});

// eslint-disable-next-line @typescript-eslint/no-empty-function
beforeEach(() => {
  patchCurrentBlockNumber();
});

afterEach(() => {
  unpatch();
});

afterAll(async () => {
  await inj.close();
});

const patchCurrentBlockNumber = (withError: boolean = false) => {
  patch(inj.chainRestTendermintApi, 'fetchLatestBlock', () => {
    return withError ? {} : { header: { height: 100 } };
  });
};

const patchMarkets = () => {
  patch(injCLOB.spotApi, 'fetchMarkets', () => {
    return MARKETS;
  });
};

const patchOrderBook = () => {
  patch(injCLOB.spotApi, 'fetchOrderbook', () => {
    return ORDER_BOOK;
  });
};
const patchGetWallet = () => {
  patch(inj, 'getWallet', () => {
    return {
      privateKey:
        'b5959390c834283a11ad71f3668fee9784853f1422e921a7015c275c98c95c08', // noqa: mock
      injectiveAddress: 'inj1ycfk9k7pmqmst2craxteyd2k3xj93xuw2x0vgp',
    };
  });
};

const patchMsgBroadcaster = () => {
  patch(inj, 'broadcaster', () => {
    return {
      broadcast() {
        return {
          txHash: TX_HASH,
        };
      },
    };
  });
};

const patchOrders = () => {
  patch(injCLOB.spotApi, 'fetchOrderHistory', () => {
    return ORDERS;
  });
};

const patchGasPrices = () => {
  patch(injCLOB, 'estimateGas', () => {
    return GAS_PRICES;
  });
};

describe('GET /clob/markets', () => {
  it('should return 200 with proper request', async () => {
    patchMarkets();
    await request(gatewayApp)
      .get(`/clob/markets`)
      .query({
        chain: 'injective',
        network: 'mainnet',
        connector: 'injective',
      })
      .set('Accept', 'application/json')
      .expect('Content-Type', /json/)
      .expect(200)
      .expect((res) => expect(res.body.markets).toEqual(injCLOB.parsedMarkets));
  });

  it('should return 404 when parameters are invalid', async () => {
    await request(gatewayApp)
      .get(`/clob/markets`)
      .query(INVALID_REQUEST)
      .expect(404);
  });
});

describe('GET /clob/orderBook', () => {
  it('should return 200 with proper request', async () => {
    patchOrderBook();
    await request(gatewayApp)
      .get(`/clob/orderBook`)
      .query({
        chain: 'injective',
        network: 'mainnet',
        connector: 'injective',
        market: MARKET,
      })
      .set('Accept', 'application/json')
      .expect('Content-Type', /json/)
      .expect(200)
      .expect((res) => expect(res.body.buys).toEqual(ORDER_BOOK.buys))
      .expect((res) => expect(res.body.sells).toEqual(ORDER_BOOK.sells));
  });

  it('should return 404 when parameters are invalid', async () => {
    await request(gatewayApp)
      .get(`/clob/orderBook`)
      .query(INVALID_REQUEST)
      .expect(404);
  });
});

describe('GET /clob/ticker', () => {
  it('should return 200 with proper request', async () => {
    patchMarkets();
    await request(gatewayApp)
      .get(`/clob/ticker`)
      .query({
        chain: 'injective',
        network: 'mainnet',
        connector: 'injective',
        market: MARKET,
      })
      .set('Accept', 'application/json')
      .expect('Content-Type', /json/)
      .expect(200)
      .expect((res) => expect(res.body.markets).toEqual(injCLOB.parsedMarkets));
  });

  it('should return 404 when parameters are invalid', async () => {
    await request(gatewayApp)
      .get(`/clob/ticker`)
      .query(INVALID_REQUEST)
      .expect(404);
  });
});

describe('GET /clob/orders', () => {
  it('should return 200 with proper request', async () => {
    patchOrders();
    await request(gatewayApp)
      .get(`/clob/orders`)
      .query({
        chain: 'injective',
        network: 'mainnet',
        connector: 'injective',
        address:
          '0x261362dBC1D83705AB03e99792355689A4589b8E000000000000000000000000', // noqa: mock
        market: MARKET,
        orderId: '0x...',
      })
      .set('Accept', 'application/json')
      .expect('Content-Type', /json/)
      .expect(200)
      .expect((res) => expect(res.body.orders).toEqual(ORDERS.orderHistory));
  });

  it('should return 404 when parameters are invalid', async () => {
    await request(gatewayApp)
      .get(`/clob/orders`)
      .query(INVALID_REQUEST)
      .expect(404);
  });
});

describe('POST /clob/orders', () => {
  it('should return 200 with proper request', async () => {
    patchGetWallet();
    patchMsgBroadcaster();
    await request(gatewayApp)
      .post(`/clob/orders`)
      .send({
        chain: 'injective',
        network: 'mainnet',
        connector: 'injective',
        address:
          '0x261362dBC1D83705AB03e99792355689A4589b8E000000000000000000000000', // noqa: mock
        market: MARKET,
        price: '10000.12',
        amount: '0.12',
        side: 'BUY',
        orderType: 'LIMIT',
      })
      .set('Accept', 'application/json')
      .expect('Content-Type', /json/)
      .expect(200)
      .expect((res) => expect(res.body.txHash).toEqual(TX_HASH));
  });

  it('should return 404 when parameters are invalid', async () => {
    await request(gatewayApp)
      .post(`/clob/orders`)
      .send(INVALID_REQUEST)
      .expect(404);
  });
});

describe('DELETE /clob/orders', () => {
  it('should return 200 with proper request', async () => {
    patchGetWallet();
    patchMsgBroadcaster();
    await request(gatewayApp)
      .delete(`/clob/orders`)
      .send({
        chain: 'injective',
        network: 'mainnet',
        connector: 'injective',
        address:
          '0x261362dBC1D83705AB03e99792355689A4589b8E000000000000000000000000', // noqa: mock
        market: MARKET,
        orderId: '0x...',
      })
      .set('Accept', 'application/json')
      .expect('Content-Type', /json/)
      .expect(200)
      .expect((res) => expect(res.body.txHash).toEqual(TX_HASH));
  });

  it('should return 404 when parameters are invalid', async () => {
    await request(gatewayApp)
      .delete(`/clob/orders`)
      .send(INVALID_REQUEST)
      .expect(404);
  });
});

describe('POST /clob/batchOrders', () => {
  it('should return 200 with proper request to create batch orders', async () => {
    patchGetWallet();
    patchMsgBroadcaster();
    await request(gatewayApp)
      .post(`/clob/batchOrders`)
      .send({
        chain: 'injective',
        network: 'mainnet',
        connector: 'injective',
        address:
          '0x261362dBC1D83705AB03e99792355689A4589b8E000000000000000000000000', // noqa: mock
        market: MARKET,
        createOrderParams: [
          {
            price: '2',
            amount: '0.10',
            side: 'SELL',
            orderType: 'LIMIT',
          },
          {
            price: '3',
            amount: '0.10',
            side: 'SELL',
          },
        ],
      })
      .set('Accept', 'application/json')
      .expect('Content-Type', /json/)
      .expect(200)
      .expect((res) => expect(res.body.txHash).toEqual(TX_HASH));
  });

  it('should return 200 with proper request to delete batch orders', async () => {
    patchGetWallet();
    patchMsgBroadcaster();
    await request(gatewayApp)
      .post(`/clob/batchOrders`)
      .send({
        chain: 'injective',
        network: 'mainnet',
        connector: 'injective',
        address:
          '0x261362dBC1D83705AB03e99792355689A4589b8E000000000000000000000000', // noqa: mock
        market: MARKET,
        cancelOrderIds: [
          '0x73af517124c3f564d1d70e38ad5200dfc7101d04986c14df410042e00932d4bf', // noqa: mock
          '0x8ce222ca5da95aaffd87b3d38a307f25d6e2c09e70a0cb8599bc6c8a0851fda3', // noqa: mock
        ],
      })
      .set('Accept', 'application/json')
      .expect('Content-Type', /json/)
      .expect(200)
      .expect((res) => expect(res.body.txHash).toEqual(TX_HASH));
  });

  it('should return 404 when parameters are invalid', async () => {
    await request(gatewayApp)
      .post(`/clob/batchOrders`)
      .send(INVALID_REQUEST)
      .expect(404);
  });
});

describe('GET /clob/estimateGas', () => {
  it('should return 200 with proper request', async () => {
    patchGasPrices();
    await request(gatewayApp)
      .get(`/clob/estimateGas`)
      .query({
        chain: 'injective',
        network: 'mainnet',
        connector: 'injective',
      })
      .set('Accept', 'application/json')
      .expect('Content-Type', /json/)
      .expect(200)
      .expect((res) => expect(res.body.gasPrice).toEqual(GAS_PRICES.gasPrice));
  });

  it('should return 404 when parameters are invalid', async () => {
    await request(gatewayApp)
      .get(`/clob/estimateGas`)
      .query(INVALID_REQUEST)
      .expect(404);
  });
});
