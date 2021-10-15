import request from 'supertest';
import { Ethereum } from '../../../src/chains/ethereum/ethereum';
import { patch, unpatch } from '../../services/patch';
import * as transactionOutOfGas from './fixtures/transaction-out-of-gas.json';
import * as transactionOutOfGasReceipt from './fixtures/transaction-out-of-gas-receipt.json';
import { app } from '../../../src/app';
import {
  NETWORK_ERROR_CODE,
  RATE_LIMIT_ERROR_CODE,
  OUT_OF_GAS_ERROR_CODE,
  UNKNOWN_ERROR_ERROR_CODE,
} from '../../../src/services/error-handler';
import * as transactionSuccesful from './fixtures/transaction-succesful.json';
import * as transactionSuccesfulReceipt from './fixtures/transaction-succesful-receipt.json';

let eth: Ethereum;

beforeAll(async () => {
  eth = Ethereum.getInstance();
  await eth.init();
});

afterEach(() => {
  unpatch();
});

describe('GET /eth', () => {
  it('should return 200', async () => {
    request(app)
      .get(`/eth`)
      .expect('Content-Type', /json/)
      .expect(200)
      .expect((res) => expect(res.body.connection).toBe(true));
  });
});

const patchGetWallet = () => {
  patch(eth, 'getWallet', () => {
    return {
      address: '0xFaA12FD102FE8623C9299c72B03E45107F2772B5',
    };
  });
};

const patchGetNonce = () => {
  patch(eth.nonceManager, 'getNonce', () => 2);
};

const patchGetTokenBySymbol = () => {
  patch(eth, 'getTokenBySymbol', () => {
    return {
      chainId: 42,
      name: 'WETH',
      symbol: 'WETH',
      address: '0xd0A1E359811322d97991E03f863a0C30C2cF029C',
      decimals: 18,
    };
  });
};

const patchApproveERC20 = () => {
  patch(eth, 'approveERC20', () => {
    return {
      chainId: 42,
      name: 'WETH',
      symbol: 'WETH',
      address: '0xd0A1E359811322d97991E03f863a0C30C2cF029C',
      decimals: 18,
      nonce: 23,
    };
  });
};

describe('POST /eth/nonce', () => {
  it('should return 200', async () => {
    patchGetWallet();
    patchGetNonce();

    await request(app)
      .post(`/eth/nonce`)
      .send({
        privateKey:
          'da857cbda0ba96757fed842617a40693d06d00001e55aa972955039ae747bac4',
      })
      .set('Accept', 'application/json')
      .expect('Content-Type', /json/)
      .expect(200)
      .expect((res) => expect(res.body.nonce).toBe(2));
  });

  it('should return 404 when parameters are invalid', async () => {
    await request(app)
      .post(`/eth/nonce`)
      .send({
        privateKey: 'da857cbda0ba96757fed842617a4',
      })
      .expect(404);
  });
});

describe('POST /eth/approve', () => {
  it('should return 200', async () => {
    patchGetWallet();
    patchGetNonce();
    patchGetTokenBySymbol();
    patchApproveERC20();

    await request(app)
      .post(`/eth/approve`)
      .send({
        privateKey:
          'da857cbda0ba96757fed842617a40693d06d00001e55aa972955039ae747bac4',
        spender: 'uniswap',
        token: 'WETH',
        nonce: 23,
      })
      .set('Accept', 'application/json')
      .expect('Content-Type', /json/)
      .expect(200)
      .then((res: any) => {
        expect(res.body.nonce).toEqual(23);
      });
  });

  it('should return 404 when parameters are invalid', async () => {
    await request(app)
      .post(`/eth/approve`)
      .send({
        privateKey:
          'da857cbda0ba96757fed842617a40693d06d00001e55aa972955039ae747bac4',
        spender: 'uniswap',
        token: 123,
        nonce: '23',
      })
      .expect(404);
  });
});

describe('POST /eth/cancel', () => {
  it('should return 200', async () => {
    // override getWallet (network call)
    eth.getWallet = jest.fn().mockReturnValue({
      address: '0xFaA12FD102FE8623C9299c72B03E45107F2772B5',
    });

    eth.cancelTx = jest.fn().mockReturnValue({
      hash: '0xf6b9e7cec507cb3763a1179ff7e2a88c6008372e3a6f297d9027a0b39b0fff77',
    });

    await request(app)
      .post(`/eth/cancel`)
      .send({
        privateKey:
          'da857cbda0ba96757fed842617a40693d06d00001e55aa972955039ae747bac4',
        nonce: 23,
      })
      .set('Accept', 'application/json')
      .expect('Content-Type', /json/)
      .expect(200)
      .then((res: any) => {
        expect(res.body.txHash).toEqual(
          '0xf6b9e7cec507cb3763a1179ff7e2a88c6008372e3a6f297d9027a0b39b0fff77'
        );
      });
  });

  it('should return 404 when parameters are invalid', async () => {
    await request(app)
      .post(`/eth/cancel`)
      .send({
        privateKey: '',
        nonce: '23',
      })
      .expect(404);
  });
});

class RateLimitError extends Error {
  code: number;
  constructor() {
    super('-32005');
    this.code = -32005;
  }
}

class NetworkError extends Error {
  code: string;
  constructor() {
    super('NETWORK_ERROR');
    this.code = 'NETWORK_ERROR';
  }
}

describe('POST /eth/poll', () => {
  it('should get a NETWORK_ERROR_CODE when the network is unavailable', async () => {
    patch(eth, 'getCurrentBlockNumber', () => {
      throw new NetworkError();
    });

    const res = await request(app).post('/eth/poll').send({
      txHash:
        '0x2faeb1aa55f96c1db55f643a8cf19b0f76bf091d0b7d1b068d2e829414576362',
    });

    expect(res.statusCode).toEqual(503);
    expect(res.body.errorCode).toEqual(NETWORK_ERROR_CODE);
  });

  it('should get a UNKNOWN_ERROR_ERROR_CODE when an unknown error is thrown', async () => {
    patch(eth, 'getCurrentBlockNumber', () => {
      throw new Error();
    });

    const res = await request(app).post('/eth/poll').send({
      txHash:
        '0x2faeb1aa55f96c1db55f643a8cf19b0f76bf091d0b7d1b068d2e829414576362',
    });

    expect(res.statusCode).toEqual(503);
    expect(res.body.errorCode).toEqual(UNKNOWN_ERROR_ERROR_CODE);
  });

  it('should get an RATE_LIMIT_ERROR_CODE when the blockchain API is rate limited', async () => {
    patch(eth, 'getCurrentBlockNumber', () => {
      throw new RateLimitError();
    });

    const res = await request(app).post('/eth/poll').send({
      txHash:
        '0x2faeb1aa55f96c1db55f643a8cf19b0f76bf091d0b7d1b068d2e829414576362',
    });

    expect(res.statusCode).toEqual(503);
    expect(res.body.errorCode).toEqual(RATE_LIMIT_ERROR_CODE);
  });

  it('should get an OUT of GAS error for failed out of gas transactions', async () => {
    patch(eth, 'getCurrentBlockNumber', () => 1);
    patch(eth, 'getTransaction', () => transactionOutOfGas);
    patch(eth, 'getTransactionReceipt', () => transactionOutOfGasReceipt);
    const res = await request(app).post('/eth/poll').send({
      txHash:
        '0x2faeb1aa55f96c1db55f643a8cf19b0f76bf091d0b7d1b068d2e829414576362',
    });

    expect(res.statusCode).toEqual(503);
    expect(res.body.errorCode).toEqual(OUT_OF_GAS_ERROR_CODE);
  });

  it('should get a null in txReceipt for Tx in the mempool', async () => {
    patch(eth, 'getCurrentBlockNumber', () => 1);
    patch(eth, 'getTransaction', () => transactionOutOfGas);
    patch(eth, 'getTransactionReceipt', () => null);
    const res = await request(app).post('/eth/poll').send({
      txHash:
        '0x2faeb1aa55f96c1db55f643a8cf19b0f76bf091d0b7d1b068d2e829414576362',
    });
    expect(res.statusCode).toEqual(200);
    expect(res.body.txReceipt).toEqual(null);
    expect(res.body.txData).toBeDefined();
  });

  it('should get a null in txReceipt and txData for Tx that didnt reach the mempool and TxReceipt is null', async () => {
    patch(eth, 'getCurrentBlockNumber', () => 1);
    patch(eth, 'getTransaction', () => null);
    patch(eth, 'getTransactionReceipt', () => null);
    const res = await request(app).post('/eth/poll').send({
      txHash:
        '0x2faeb1aa55f96c1db55f643a8cf19b0f76bf091d0b7d1b068d2e829414576362',
    });
    expect(res.statusCode).toEqual(200);
    expect(res.body.txReceipt).toEqual(null);
    expect(res.body.txData).toEqual(null);
  });

  it('should get txStatus = 1 for a succesful query', async () => {
    patch(eth, 'getCurrentBlockNumber', () => 1);
    patch(eth, 'getTransaction', () => transactionSuccesful);
    patch(eth, 'getTransactionReceipt', () => transactionSuccesfulReceipt);
    const res = await request(app).post('/eth/poll').send({
      txHash:
        '0x6d068067a5e5a0f08c6395b31938893d1cdad81f54a54456221ecd8c1941294d',
    });
    expect(res.statusCode).toEqual(200);
    expect(res.body.txReceipt).toBeDefined();
    expect(res.body.txData).toBeDefined();
  });
});
