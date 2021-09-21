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
    request(app)
      .get(`/eth`)
      .expect('Content-Type', /json/)
      .expect(200)
      .expect((res) => expect(res.body.connection).toBe(true));
  });
});

describe('POST /eth/nonce', () => {
  it('should return 200', async () => {
    EthereumRoutes.ethereum.getWallet = jest.fn().mockReturnValue({
      address: '0x0000000000000000000',
    });
    EthereumRoutes.ethereum.nonceManager.getNonce = jest
      .fn()
      .mockReturnValue(2);
    await request(app)
      .post(`/eth/nonce`)
      .send({ privateKey: 'abc123' })
      .set('Accept', 'application/json')
      .expect('Content-Type', /json/)
      .expect(200)
      .expect((res) => expect(res.body.nonce).toBe(2));
  });
});

describe('POST /eth/approve', () => {
  it('should return 200', async () => {
    // override getWallet (network call)
    EthereumRoutes.ethereum.getWallet = jest.fn().mockReturnValue({
      address: '0x0000000000000000000',
    });

    // override getTokenBySymbol (network call, read file and config dependency)
    EthereumRoutes.ethereum.getTokenBySymbol = jest.fn().mockReturnValue({
      chainId: 42,
      name: 'WETH',
      symbol: 'WETH',
      address: '0xd0A1E359811322d97991E03f863a0C30C2cF029C',
      decimals: 18,
    });

    // override getNonce (network call)
    EthereumRoutes.ethereum.nonceManager.getNonce = jest
      .fn()
      .mockReturnValue(2);

    // override approveERC20 (network call)
    EthereumRoutes.ethereum.approveERC20 = jest.fn().mockReturnValue({
      chainId: 42,
      name: 'WETH',
      symbol: 'WETH',
      address: '0xd0A1E359811322d97991E03f863a0C30C2cF029C',
      decimals: 18,
      nonce: 23,
    });

    await request(app)
      .post(`/eth/approve`)
      .send({
        privateKey: 'abc123',
        spender: 'xyz098',
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
});
