import request from 'supertest';
import { Near } from '../../../src/chains/near/near';
import { patch, unpatch } from '../../services/patch';
import { gatewayApp } from '../../../src/app';
import {
  NETWORK_ERROR_CODE,
  RATE_LIMIT_ERROR_CODE,
  UNKNOWN_ERROR_ERROR_CODE,
  NETWORK_ERROR_MESSAGE,
  RATE_LIMIT_ERROR_MESSAGE,
  UNKNOWN_ERROR_MESSAGE,
} from '../../../src/services/error-handler';
import * as transactionSuccesful from './fixtures/getTransaction.json';
let near: Near;

beforeAll(async () => {
  near = Near.getInstance('testnet');
});

afterEach(() => {
  unpatch();
});

afterAll(async () => {
  await near.close();
});

const patchGetWallet = () => {
  patch(near, 'getWallet', () => {
    return {
      address: 'test.near',
    };
  });
};

const patchGetFTBalance = () => {
  patch(near, 'getFungibleTokenBalance', () => '0.01');
};

const patchGetNativeBalance = () => {
  patch(near, 'getNativeBalance', () => '0.01');
};

const patchGetTokenBySymbol = () => {
  patch(near, 'getTokenBySymbol', (symbol: string) => {
    let result;
    switch (symbol) {
      case 'WETH':
        result = {
          chainId: 42,
          name: 'WETH',
          symbol: 'WETH',
          address: 'weth.near',
          decimals: 18,
        };
        break;
      case 'DAI':
        result = {
          chainId: 42,
          name: 'DAI',
          symbol: 'DAI',
          address: 'dai.near',
          decimals: 18,
        };
        break;
    }
    return result;
  });
};

describe('POST /near/balances', () => {
  it('should return 500 for unsupported tokens', async () => {
    patchGetWallet();
    patchGetTokenBySymbol();
    patchGetNativeBalance();
    patchGetFTBalance();
    near.getContract = jest.fn().mockReturnValue({
      address: 'test.near',
    });

    await request(gatewayApp)
      .post(`/near/balances`)
      .send({
        chain: 'near',
        network: 'testnet',
        address: 'test.near',
        tokenSymbols: ['XXX', 'YYY'],
      })
      .set('Accept', 'application/json')
      .expect('Content-Type', /json/)
      .expect(500);
  });

  it('should return 404 when parameters are invalid', async () => {
    await request(gatewayApp)
      .post(`/near/balances`)
      .send({
        chain: 'near',
        network: 'testnet',
        address: 'da857cbda0ba96757fed842617a4',
      })
      .expect(404);
  });
});

describe('POST /near/poll', () => {
  it('should get a NETWORK_ERROR_CODE when the network is unavailable', async () => {
    patch(near, 'getCurrentBlockNumber', () => {
      const error: any = new Error('somnearing went wrong');
      error.code = 'NETWORK_ERROR';
      throw error;
    });

    const res = await request(gatewayApp).post('/near/poll').send({
      address: 'test.near',
      network: 'testnet',
      txHash:
        '2faeb1aa55f96c1db55f643a8cf19b0f76bf091d0b7d1b068d2e829414576362', // noqa: mock
    });

    expect(res.statusCode).toEqual(503);
    expect(res.body.errorCode).toEqual(NETWORK_ERROR_CODE);
    expect(res.body.message).toEqual(NETWORK_ERROR_MESSAGE);
  });

  it('should get a UNKNOWN_ERROR_ERROR_CODE when an unknown error is thrown', async () => {
    patch(near, 'getCurrentBlockNumber', () => {
      throw new Error();
    });

    const res = await request(gatewayApp).post('/near/poll').send({
      address: 'test.near',
      network: 'testnet',
      txHash:
        '2faeb1aa55f96c1db55f643a8cf19b0f76bf091d0b7d1b068d2e829414576362', // noqa: mock
    });

    expect(res.statusCode).toEqual(503);
    expect(res.body.errorCode).toEqual(UNKNOWN_ERROR_ERROR_CODE);
  });

  it('should get txStatus = 1 for a succesful query', async () => {
    patch(near, 'getCurrentBlockNumber', () => 1);
    patch(near, 'getTransaction', () => transactionSuccesful);
    const res = await request(gatewayApp).post('/near/poll').send({
      address: 'test.near',
      network: 'testnet',
      txHash:
        '0x6d068067a5e5a0f08c6395b31938893d1cdad81f54a54456221ecd8c1941294d', // noqa: mock
    });
    expect(res.statusCode).toEqual(200);
    expect(res.body.txReceipt).toBeDefined();
  });

  it('should get an RATE_LIMIT_ERROR_CODE when the blockchain API is rate limited', async () => {
    patch(near, 'getCurrentBlockNumber', () => {
      const error: any = new Error(
        'daily request count exceeded, request rate limited'
      );
      error.code = -32005;
      error.data = {
        see: 'https://infura.io/docs/near/jsonrpc/ratelimits',
        current_rps: 13.333,
        allowed_rps: 10.0,
        backoff_seconds: 30.0,
      };
      throw error;
    });
    const res = await request(gatewayApp).post('/near/poll').send({
      address: 'test.near',
      network: 'testnet',
      txHash:
        '2faeb1aa55f96c1db55f643a8cf19b0f76bf091d0b7d1b068d2e829414576362', // noqa: mock
    });
    expect(res.statusCode).toEqual(503);
    expect(res.body.errorCode).toEqual(RATE_LIMIT_ERROR_CODE);
    expect(res.body.message).toEqual(RATE_LIMIT_ERROR_MESSAGE);
  });

  it('should get unknown error', async () => {
    patch(near, 'getCurrentBlockNumber', () => {
      const error: any = new Error('somnearing went wrong');
      error.code = -32006;
      throw error;
    });
    const res = await request(gatewayApp).post('/near/poll').send({
      address: 'test.near',
      network: 'testnet',
      txHash:
        '2faeb1aa55f96c1db55f643a8cf19b0f76bf091d0b7d1b068d2e829414576362', // noqa: mock
    });
    expect(res.statusCode).toEqual(503);
    expect(res.body.errorCode).toEqual(UNKNOWN_ERROR_ERROR_CODE);
    expect(res.body.message).toEqual(UNKNOWN_ERROR_MESSAGE);
  });
});
