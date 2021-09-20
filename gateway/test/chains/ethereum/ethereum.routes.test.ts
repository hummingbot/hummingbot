import express from 'express';
import { Express } from 'express-serve-static-core';
import request from 'supertest';
import { EthereumRoutes } from '../../../src/chains/ethereum/ethereum.routes';

let app: Express;

beforeAll(async () => {
  app = express();
  app.use(express.json());
  app.use('/eth', EthereumRoutes.router);
});

describe('GET /eth', () => {
  it('should return 200', async () => {
    request(app).get(`/eth`).expect('Content-Type', /json/).expect(200);
  });
});

describe('POST /eth/nonce', () => {
  it('should return 200', async () => {
    EthereumRoutes.ethereum.getWallet = jest.fn().mockReturnValue(() => {
      address: '0x0000000000000000000';
    });
    EthereumRoutes.ethereum.nonceManager.getNonce = jest
      .fn()
      .mockReturnValue(() => Promise.resolve(2));
    const res = await request(app)
      .post(`/eth/nonce`)
      .send({ privateKey: 'abc123' })
      .set('Accept', 'application/json');
    expect(res.statusCode).toEqual(200);
  });
});

describe('POST /eth/approve', () => {
  it('should return 200', async () => {
    EthereumRoutes.ethereum.getWallet = jest.fn().mockReturnValue(() => {
      address: '0x0000000000000000000';
    });
    EthereumRoutes.ethereum.getTokenBySymbol = jest.fn().mockReturnValue(() => {
      chainId: 42;
      name: 'WETH';
      symbol: 'WETH';
      address: '0xd0A1E359811322d97991E03f863a0C30C2cF029C';
      decimals: 18;
    });
    EthereumRoutes.ethereum.nonceManager.getNonce = jest
      .fn()
      .mockReturnValue(() => Promise.resolve(2));
    EthereumRoutes.ethereum.approveERC20 = jest.fn().mockReturnValue(() => {
      chainId: 42;
      name: 'WETH';
      symbol: 'WETH';
      address: '0xd0A1E359811322d97991E03f863a0C30C2cF029C';
      decimals: 18;
    });

    EthereumRoutes.ethereum.getContract = jest.fn().mockReturnValue(() => {
      getNonce: () =>
        Promise.resolve({
          hash: '',
          to: '',
          from: '',
          nonce: '',
          gasLimit: '',
          gasPrice: '',
          maxFeePerGas: '',
          maxPriorityFeePerGas: '',
          data: '',
          value: '',
          chainId: '',
          r: '',
          s: '',
          v: '',
        });
    });
    const res = await request(app)
      .post(`/eth/nonce`)
      .send({
        privateKey: 'abc123',
        spender: 'xyz098',
        token: 'WETH',
        nonce: '23',
      })
      .set('Accept', 'application/json');
    expect(res.statusCode).toEqual(200);
  });
});
