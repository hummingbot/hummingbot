import express from 'express';
import { Express } from 'express-serve-static-core';
import request from 'supertest';
import { Big } from 'big.js';
import { Ethereum } from '../../../../src/chains/ethereum/ethereum';
import { Perp } from '../../../../src/connectors/perp/perp';
import { PerpAmmRoutes } from '../../../../src/amm/amm.routes';
import { patch, unpatch } from '../../../services/patch';
import { gasCostInEthString } from '../../../../src/services/base';
import { patchEVMNonceManager } from '../../../evm.nonce.mock';

let app: Express;
let ethereum: Ethereum;
let perp: Perp;

beforeAll(async () => {
  app = express();
  app.use(express.json());

  ethereum = Ethereum.getInstance('optimism');
  patchEVMNonceManager(ethereum.nonceManager);
  await ethereum.init();

  perp = Perp.getInstance('ethereum', 'optimism');
  await perp.init();

  app.use('/amm/perp', PerpAmmRoutes.router);
});

beforeEach(() => {
  patchEVMNonceManager(ethereum.nonceManager);
});

afterEach(() => {
  unpatch();
});

afterAll(async () => {
  await ethereum.close();
});

const address: string = '0xFaA12FD102FE8623C9299c72B03E45107F2772B5';

const patchGetWallet = () => {
  patch(ethereum, 'getWallet', () => {
    return {
      address: '0xFaA12FD102FE8623C9299c72B03E45107F2772B5',
    };
  });
};

const patchInit = () => {
  patch(perp, 'init', async () => {
    return;
  });
};

const patchGasPrice = () => {
  patch(ethereum, 'gasPrice', () => 100);
};

const patchMarket = () => {
  patch(perp.perp, 'marketMap', () => {
    return {
      getPrices() {
        return {
          markPrice: new Big('1'),
          indexPrice: new Big('2'),
          indexTwapPrice: new Big('3'),
        };
      },
      getStatus() {
        return true;
      },
      get marketMap() {
        return {
          AAVEUSD: 1,
          WETHUSD: 2,
          WBTCUSD: 3,
        };
      },
    };
  });
};

const patchPosition = () => {
  patch(perp.perp, 'positions', () => {
    return {
      getTakerPositionByTickerSymbol() {
        return;
      },
    };
  });
};

const patchCH = () => {
  patch(perp.perp, 'clearingHouse', () => {
    return {
      createPositionDraft() {
        return;
      },
      openPosition() {
        return {
          type: 2,
          chainId: 42,
          nonce: 115,
          maxPriorityFeePerGas: { toString: () => '106000000000' },
          maxFeePerGas: { toString: () => '106000000000' },
          gasPrice: { toString: () => null },
          gasLimit: { toString: () => '100000' },
          to: '0x4F96Fe3b7A6Cf9725f59d353F723c1bDb64CA6Aa',
          value: { toString: () => '0' },
          data: '0x095ea7b30000000000000000000000007a250d5630b4cf539739df2c5dacb4c659f2488dffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff', // noqa: mock
          accessList: [],
          hash: '0x75f98675a8f64dcf14927ccde9a1d59b67fa09b72cc2642ad055dae4074853d9', // noqa: mock
          v: 0,
          r: '0xbeb9aa40028d79b9fdab108fcef5de635457a05f3a254410414c095b02c64643', // noqa: mock
          s: '0x5a1506fa4b7f8b4f3826d8648f27ebaa9c0ee4bd67f569414b8cd8884c073100', // noqa: mock
          from: '0xFaA12FD102FE8623C9299c72B03E45107F2772B5',
          confirmations: 0,
        };
      },
    };
  });
};

const patchGetNonce = () => {
  patch(ethereum.nonceManager, 'getNonce', () => 21);
};

describe('POST /amm/perp/market-prices', () => {
  it('should return 200 with right parameter', async () => {
    patchInit();
    patchGasPrice();
    patchMarket();

    await request(app)
      .post(`/amm/perp/market-prices`)
      .send({
        chain: 'ethereum',
        network: 'optimism',
        connector: 'perp',
        quote: 'DAI',
        base: 'WETH',
      })
      .set('Accept', 'application/json')
      .expect(200)
      .then((res: any) => {
        expect(res.body.markPrice).toEqual('1');
        expect(res.body.indexPrice).toEqual('2');
        expect(res.body.indexTwapPrice).toEqual('3');
      });
  });

  it('should return 500 with wrong paramters', async () => {
    patchInit();
    patchGasPrice();
    patchMarket();

    await request(app)
      .post(`/amm/perp/market-prices`)
      .send({
        chain: 'ethereum',
        network: 'optimism',
        connector: 'perp',
        quote: '1234',
        base: 'WETH',
      })
      .set('Accept', 'application/json')
      .expect(500);
  });
});

describe('POST /amm/perp/market-status', () => {
  it('should return 200 with right parameter', async () => {
    patchInit();
    patchGasPrice();
    patchMarket();

    await request(app)
      .post(`/amm/perp/market-status`)
      .send({
        chain: 'ethereum',
        network: 'optimism',
        connector: 'perp',
        quote: 'DAI',
        base: 'WETH',
      })
      .set('Accept', 'application/json')
      .expect(200)
      .then((res: any) => {
        expect(res.body.isActive).toEqual(true);
      });
  });

  it('should return 500 with wrong paramters', async () => {
    patchInit();
    patchGasPrice();
    patchMarket();

    await request(app)
      .post(`/amm/perp/market-status`)
      .send({
        chain: 'ethereum',
        network: 'optimism',
        connector: 'perp',
        quote: '1234',
        base: 'WETH',
      })
      .set('Accept', 'application/json')
      .expect(500);
  });
});

describe('POST /amm/perp/pairs', () => {
  it('should return list of available pairs', async () => {
    patchInit();
    patchGasPrice();
    patchMarket();

    await request(app)
      .post(`/amm/perp/pairs`)
      .send({
        chain: 'ethereum',
        network: 'optimism',
        connector: 'perp',
      })
      .set('Accept', 'application/json')
      .expect(200)
      .then((res: any) => {
        expect(res.body.isActive).toEqual(true);
      });
  });
});

describe('POST /amm/perp/position', () => {
  it('should return list of available pairs', async () => {
    patchInit();
    patchGasPrice();
    patchPosition();
    patchGetWallet();

    await request(app)
      .post(`/amm/perp/position`)
      .send({
        chain: 'ethereum',
        network: 'optimism',
        connector: 'perp',
        quote: 'DAI',
        base: 'WETH',
        address: address,
      })
      .set('Accept', 'application/json')
      .expect(200)
      .then((res: any) => {
        expect(res.body).toHaveProperty('positionAmt');
        expect(res.body).toHaveProperty('positionSide');
        expect(res.body).toHaveProperty('unRealizedProfit');
        expect(res.body).toHaveProperty('leverage');
        expect(res.body).toHaveProperty('entryPrice');
        expect(res.body).toHaveProperty('tickerSymbol');
      });
  });
});

describe('POST /amm/perp/open and /amm/perp/close', () => {
  it('open should return with hash', async () => {
    patchInit();
    patchGasPrice();
    patchPosition();
    patchCH();
    patchGetWallet();
    patchGetNonce();

    await request(app)
      .post(`/amm/perp/open`)
      .send({
        chain: 'ethereum',
        network: 'optimism',
        connector: 'perp',
        quote: 'DAI',
        base: 'WETH',
        amount: '0.01',
        side: 'LONG',
        address: address,
      })
      .set('Accept', 'application/json')
      .expect(200)
      .then((res: any) => {
        expect(res.body).toHaveProperty('hash');
      });
  });

  it('close should return error', async () => {
    patchInit();
    patchGasPrice();
    patchPosition();
    patchCH();
    patchGetWallet();
    patchGetNonce();

    await request(app)
      .post(`/amm/perp/close`)
      .send({
        chain: 'ethereum',
        network: 'optimism',
        connector: 'perp',
        quote: 'DAI',
        base: 'WETH',
        address: address,
      })
      .set('Accept', 'application/json')
      .expect(500);
  });
});

describe('POST /amm/perp/estimateGas', () => {
  it('should return 200 with right parameter', async () => {
    patchInit();
    patchGasPrice();

    await request(app)
      .post('/amm//perp/estimateGas')
      .send({
        chain: 'ethereum',
        network: 'optimism',
        connector: 'perp',
      })
      .set('Accept', 'application/json')
      .expect(200)
      .then((res: any) => {
        expect(res.body.network).toEqual('optimism');
        expect(res.body.gasPrice).toEqual(100);
        expect(res.body.gasCost).toEqual(
          gasCostInEthString(100, perp.gasLimit)
        );
      });
  });

  it('should return 500 for invalid connector', async () => {
    patchInit();
    patchGasPrice();

    await request(app)
      .post('/amm/estimateGas')
      .send({
        chain: 'ethereum',
        network: 'optimism',
        connector: 'pangolin',
      })
      .set('Accept', 'application/json')
      .expect(500);
  });
});
